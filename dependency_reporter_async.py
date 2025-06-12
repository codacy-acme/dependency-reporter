#!/usr/bin/env python3
"""
Codacy Dependency Reporter - Async Optimized Version

A high-performance utility to scan all repositories in a Codacy organization and report on dependencies
across repositories, showing where each dependency is used with file paths and names.

This version uses async/await patterns and concurrent processing for significant performance improvements.
"""

import os
import sys
import json
import asyncio
import aiohttp
import time
import random
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
import click
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class DependencyInfo:
    """Information about a dependency usage"""
    repository_name: str
    file_path: str
    dependency_name: str
    dependency_version: Optional[str] = None
    dependency_type: Optional[str] = None  # e.g., "maven", "npm", "pip"

class AsyncCodacyAPIClient:
    """Async client for interacting with the Codacy API with performance optimizations and rate limiting"""
    
    def __init__(self, api_token: str, base_url: str = "https://app.codacy.com/api/v3",
                 max_concurrent: int = 5, request_timeout: int = 30):
        self.api_token = api_token
        self.base_url = base_url
        self.max_concurrent = max_concurrent
        self.request_timeout = request_timeout
        self.session = None
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Cache for API responses
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        
        # Rate limiting (2500 requests per 5 minutes = ~8.3 requests per second)
        self.rate_limit_requests = 2400  # Leave some buffer
        self.rate_limit_window = 300  # 5 minutes
        self.request_times = []
        self.rate_limit_lock = asyncio.Lock()
        
        # Performance metrics
        self.request_count = 0
        self.cache_hits = 0
        self.rate_limit_delays = 0
        self.retry_count = 0
        self.start_time = time.time()
    
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=20,  # Per-host connection limit
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )
        
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                "api-token": self.api_token,
                "Content-Type": "application/json"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _get_cache_key(self, url: str, params: dict = None, body: dict = None) -> str:
        """Generate cache key for request"""
        key_parts = [url]
        if params:
            key_parts.append(str(sorted(params.items())))
        if body:
            key_parts.append(str(sorted(body.items())))
        return "|".join(key_parts)
    
    def _is_cache_valid(self, timestamp: float) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - timestamp < self.cache_ttl
    
    async def _wait_for_rate_limit(self):
        """Wait if we're approaching rate limits"""
        async with self.rate_limit_lock:
            current_time = time.time()
            
            # Remove old requests outside the window
            self.request_times = [t for t in self.request_times if current_time - t < self.rate_limit_window]
            
            # Check if we need to wait
            if len(self.request_times) >= self.rate_limit_requests:
                # Calculate how long to wait
                oldest_request = min(self.request_times)
                wait_time = self.rate_limit_window - (current_time - oldest_request)
                
                if wait_time > 0:
                    self.rate_limit_delays += 1
                    click.echo(f"Rate limit reached, waiting {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
            
            # Record this request
            self.request_times.append(current_time)

    async def _make_request_with_retry(self, method: str, url: str, params: dict = None, 
                                     json_data: dict = None, max_retries: int = 3) -> dict:
        """Make HTTP request with exponential backoff retry for rate limit errors"""
        for attempt in range(max_retries + 1):
            try:
                # Wait for rate limit before making request
                await self._wait_for_rate_limit()
                
                if method.upper() == "GET":
                    async with self.session.get(url, params=params) as response:
                        if response.status == 502:  # Bad Gateway - likely rate limit
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=502,
                                message="Bad Gateway - Rate limit"
                            )
                        response.raise_for_status()
                        return await response.json()
                        
                elif method.upper() == "POST":
                    async with self.session.post(url, params=params, json=json_data) as response:
                        if response.status == 502:  # Bad Gateway - likely rate limit
                            raise aiohttp.ClientResponseError(
                                request_info=response.request_info,
                                history=response.history,
                                status=502,
                                message="Bad Gateway - Rate limit"
                            )
                        response.raise_for_status()
                        return await response.json()
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                    
            except aiohttp.ClientResponseError as e:
                if e.status == 502 and attempt < max_retries:
                    # Exponential backoff with jitter for 502 errors
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    self.retry_count += 1
                    click.echo(f"Request failed with 502 (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    click.echo(f"Request failed for {url}: {e.status}, message='{e.message}'", err=True)
                    return {}
            except aiohttp.ClientError as e:
                click.echo(f"Request failed for {url}: {e}", err=True)
                return {}
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    self.retry_count += 1
                    click.echo(f"Request timeout (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    click.echo(f"Request timeout for {url}", err=True)
                    return {}
        
        return {}

    async def _make_request(self, method: str, url: str, params: dict = None, 
                           json_data: dict = None, use_cache: bool = True) -> dict:
        """Make HTTP request with caching, concurrency control, and rate limiting"""
        cache_key = self._get_cache_key(url, params, json_data)
        
        # Check cache first
        if use_cache and cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if self._is_cache_valid(timestamp):
                self.cache_hits += 1
                return cached_data
        
        async with self.semaphore:  # Control concurrency
            self.request_count += 1
            
            # Make request with retry logic
            data = await self._make_request_with_retry(method, url, params, json_data)
            
            # Cache the response if successful
            if data and use_cache:
                self.cache[cache_key] = (data, time.time())
            
            return data
    
    async def get_organization_repositories(self, provider: str, organization: str) -> List[Dict[str, Any]]:
        """Get all repositories for an organization"""
        repositories = []
        cursor = None
        
        while True:
            url = f"{self.base_url}/organizations/{provider}/{organization}/repositories"
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            
            data = await self._make_request("GET", url, params)
            if not data:
                break
                
            repositories.extend(data.get("data", []))
            
            # Check if there are more pages
            pagination = data.get("pagination", {})
            cursor = pagination.get("cursor")
            if not cursor:
                break
        
        return repositories
    
    async def search_sbom_dependencies(self, provider: str, organization: str, 
                                     cursor: Optional[str] = None, 
                                     limit: int = 100) -> Dict[str, Any]:
        """Search for SBOM dependencies in the organization"""
        url = f"{self.base_url}/organizations/{provider}/{organization}/sbom/dependencies/search"
        
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        
        # Empty body for now - we want all dependencies
        body = {}
        
        return await self._make_request("POST", url, params, body)
    
    async def search_repositories_of_dependency(self, provider: str, organization: str, 
                                              dependency_full_name: str,
                                              cursor: Optional[str] = None,
                                              limit: int = 100) -> Dict[str, Any]:
        """Search for repositories that use a specific dependency"""
        url = f"{self.base_url}/organizations/{provider}/{organization}/sbom/dependencies/repositories/search"
        
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        
        body = {"dependencyFullName": dependency_full_name}
        
        return await self._make_request("POST", url, params, body)
    
    async def get_repository_files(self, provider: str, organization: str, repository: str,
                                 search_patterns: List[str] = None) -> List[Dict[str, Any]]:
        """Get files from a repository, optionally filtered by search patterns"""
        if not search_patterns:
            search_patterns = [""]  # Empty pattern to get all files
        
        all_files = []
        seen_files = set()
        
        # Process multiple patterns concurrently
        tasks = []
        for pattern in search_patterns:
            task = self._get_repository_files_for_pattern(provider, organization, repository, pattern)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                continue
            for file_info in result:
                file_path = file_info.get("path", "")
                if file_path and file_path not in seen_files:
                    all_files.append(file_info)
                    seen_files.add(file_path)
        
        return all_files
    
    async def _get_repository_files_for_pattern(self, provider: str, organization: str, 
                                              repository: str, pattern: str) -> List[Dict[str, Any]]:
        """Get files for a specific pattern"""
        url = f"{self.base_url}/organizations/{provider}/{organization}/repositories/{repository}/files"
        
        files = []
        cursor = None
        
        while True:
            params = {"limit": 100}
            if pattern:
                params["search"] = pattern
            if cursor:
                params["cursor"] = cursor
            
            data = await self._make_request("GET", url, params)
            if not data:
                break
                
            files.extend(data.get("data", []))
            
            # Check pagination
            pagination = data.get("pagination", {})
            cursor = pagination.get("cursor")
            if not cursor:
                break
        
        return files
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics"""
        elapsed_time = time.time() - self.start_time
        cache_hit_rate = (self.cache_hits / max(self.request_count, 1)) * 100
        
        return {
            "total_requests": self.request_count,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "rate_limit_delays": self.rate_limit_delays,
            "retry_attempts": self.retry_count,
            "elapsed_time": f"{elapsed_time:.2f}s",
            "requests_per_second": f"{self.request_count / max(elapsed_time, 1):.2f}"
        }

class AsyncDependencyReporter:
    """Main class for async dependency reporting functionality"""
    
    def __init__(self, api_client: AsyncCodacyAPIClient, batch_size: int = 50):
        self.api_client = api_client
        self.batch_size = batch_size
        self.dependencies_data = defaultdict(list)
    
    async def scan_organization_dependencies(self, provider: str, organization: str, 
                                           limit: Optional[int] = None) -> Dict[str, List[DependencyInfo]]:
        """Scan all dependencies across the organization with async processing"""
        click.echo(f"Scanning dependencies for organization: {organization}")
        if limit:
            click.echo(f"Limiting scan to first {limit} dependencies")
        
        # First, get all dependencies in the organization
        all_dependencies = await self._get_all_dependencies(provider, organization)
        total_dependencies = len(all_dependencies)
        
        # Apply limit if specified
        if limit and limit < total_dependencies:
            all_dependencies = all_dependencies[:limit]
            click.echo(f"Found {total_dependencies} unique dependencies, processing first {limit}")
        else:
            click.echo(f"Found {total_dependencies} unique dependencies")
        
        # Process dependencies in batches with concurrent processing
        dependency_usage = defaultdict(list)
        
        for i in range(0, len(all_dependencies), self.batch_size):
            batch = all_dependencies[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(all_dependencies) + self.batch_size - 1) // self.batch_size
            
            click.echo(f"Processing batch {batch_num}/{total_batches} ({len(batch)} dependencies)")
            
            # Process batch concurrently
            batch_results = await self._process_dependency_batch(provider, organization, batch)
            
            # Merge results
            for dep_name, usages in batch_results.items():
                dependency_usage[dep_name].extend(usages)
            
            # Show progress
            processed = min(i + self.batch_size, len(all_dependencies))
            progress = (processed / len(all_dependencies)) * 100
            click.echo(f"Progress: {processed}/{len(all_dependencies)} ({progress:.1f}%)")
        
        return dict(dependency_usage)
    
    async def _get_all_dependencies(self, provider: str, organization: str) -> List[dict]:
        """Get all dependencies from the organization"""
        all_dependencies = []
        cursor = None
        
        while True:
            click.echo("Fetching dependencies...")
            result = await self.api_client.search_sbom_dependencies(provider, organization, cursor)
            
            if not result or "data" not in result:
                break
            
            dependencies = result["data"]
            all_dependencies.extend(dependencies)
            
            # Check pagination
            pagination = result.get("pagination", {})
            cursor = pagination.get("cursor")
            if not cursor:
                break
        
        return all_dependencies
    
    async def _process_dependency_batch(self, provider: str, organization: str, 
                                      dependencies: List[dict]) -> Dict[str, List[DependencyInfo]]:
        """Process a batch of dependencies concurrently"""
        tasks = []
        
        for dep in dependencies:
            dep_name = dep.get("fullName", "")
            if dep_name:
                task = self._process_single_dependency(provider, organization, dep_name)
                tasks.append((dep_name, task))
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        # Collect results
        batch_usage = defaultdict(list)
        for (dep_name, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                click.echo(f"Error processing dependency {dep_name}: {result}", err=True)
                continue
            
            if result:
                batch_usage[dep_name].extend(result)
        
        return batch_usage
    
    async def _process_single_dependency(self, provider: str, organization: str, 
                                       dep_name: str) -> List[DependencyInfo]:
        """Process a single dependency and return its usage information"""
        usage_list = []
        
        # Get repositories that use this dependency
        repos_cursor = None
        while True:
            repos_result = await self.api_client.search_repositories_of_dependency(
                provider, organization, dep_name, repos_cursor
            )
            
            if not repos_result or "data" not in repos_result:
                break
            
            repositories = repos_result["data"]
            
            # Process repositories concurrently
            repo_tasks = []
            for repo in repositories:
                repo_name = repo.get("name", "")
                dep_version = repo.get("dependencyVersion", "")
                dep_type = self._extract_dependency_type(dep_name)
                
                task = self._process_repository_dependency(
                    provider, organization, repo_name, dep_name, dep_version, dep_type
                )
                repo_tasks.append(task)
            
            # Execute repository processing concurrently
            repo_results = await asyncio.gather(*repo_tasks, return_exceptions=True)
            
            for result in repo_results:
                if isinstance(result, Exception):
                    continue
                if result:
                    usage_list.extend(result)
            
            # Check pagination for repositories
            repos_pagination = repos_result.get("pagination", {})
            repos_cursor = repos_pagination.get("cursor")
            if not repos_cursor:
                break
        
        return usage_list
    
    async def _process_repository_dependency(self, provider: str, organization: str, 
                                           repo_name: str, dep_name: str, dep_version: str, 
                                           dep_type: str) -> List[DependencyInfo]:
        """Process dependency usage in a specific repository"""
        usage_list = []
        
        # Try to find dependency files in the repository
        dependency_files = await self._find_dependency_files(provider, organization, repo_name, dep_type)
        
        if dependency_files:
            # Create one entry per file found
            for file_path in dependency_files:
                dep_info = DependencyInfo(
                    repository_name=repo_name,
                    file_path=file_path,
                    dependency_name=dep_name,
                    dependency_version=dep_version,
                    dependency_type=dep_type
                )
                usage_list.append(dep_info)
        else:
            # No specific files found, create entry without file path
            dep_info = DependencyInfo(
                repository_name=repo_name,
                file_path="",  # No specific file found
                dependency_name=dep_name,
                dependency_version=dep_version,
                dependency_type=dep_type
            )
            usage_list.append(dep_info)
        
        return usage_list
    
    def _extract_dependency_type(self, full_name: str) -> str:
        """Extract dependency type from full name (e.g., 'maven/com.example/lib' -> 'maven')"""
        if "/" in full_name:
            return full_name.split("/")[0]
        return "unknown"
    
    def _get_dependency_file_patterns(self, dependency_type: str) -> List[str]:
        """Get file patterns to search for based on dependency type"""
        patterns = {
            "npm": ["package.json", "package-lock.json", "yarn.lock"],
            "maven": ["pom.xml"],
            "gradle": ["build.gradle", "build.gradle.kts"],
            "pip": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
            "golang": ["go.mod", "go.sum"],
            "nuget": ["*.csproj", "*.fsproj", "*.vbproj", "packages.config"],
            "composer": ["composer.json", "composer.lock"],
            "ruby": ["Gemfile", "Gemfile.lock"],
            "cargo": ["Cargo.toml", "Cargo.lock"],
        }
        return patterns.get(dependency_type, [])
    
    async def _find_dependency_files(self, provider: str, organization: str, repository: str, 
                                   dependency_type: str) -> List[str]:
        """Find dependency files in a repository based on dependency type"""
        patterns = self._get_dependency_file_patterns(dependency_type)
        if not patterns:
            return []
        
        files = await self.api_client.get_repository_files(provider, organization, repository, patterns)
        
        found_files = []
        for file_info in files:
            file_path = file_info.get("path", "")
            if file_path:
                found_files.append(file_path)
        
        return found_files
    
    def generate_report(self, dependencies: Dict[str, List[DependencyInfo]], 
                       output_format: str = "json") -> str:
        """Generate a report of dependencies"""
        if output_format == "json":
            return self._generate_json_report(dependencies)
        elif output_format == "text":
            return self._generate_text_report(dependencies)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
    
    def _generate_json_report(self, dependencies: Dict[str, List[DependencyInfo]]) -> str:
        """Generate JSON format report"""
        report_data = {}
        
        for dep_name, usages in dependencies.items():
            report_data[dep_name] = []
            for usage in usages:
                report_data[dep_name].append({
                    "repository": usage.repository_name,
                    "file_path": usage.file_path,
                    "version": usage.dependency_version,
                    "type": usage.dependency_type
                })
        
        return json.dumps(report_data, indent=2)
    
    def _generate_text_report(self, dependencies: Dict[str, List[DependencyInfo]]) -> str:
        """Generate human-readable text report"""
        lines = []
        lines.append("DEPENDENCY USAGE REPORT")
        lines.append("=" * 50)
        lines.append("")
        
        for dep_name, usages in sorted(dependencies.items()):
            lines.append(f"Dependency: {dep_name}")
            lines.append(f"Used in {len(usages)} repositories:")
            lines.append("")
            
            for usage in usages:
                lines.append(f"  Repository: {usage.repository_name}")
                if usage.dependency_version:
                    lines.append(f"    Version: {usage.dependency_version}")
                if usage.dependency_type:
                    lines.append(f"    Type: {usage.dependency_type}")
                if usage.file_path:
                    lines.append(f"    File: {usage.file_path}")
                lines.append("")
            
            lines.append("-" * 30)
            lines.append("")
        
        return "\n".join(lines)

@click.command()
@click.option("--provider", "-p", default="gh", help="Git provider (gh, gl, bb)")
@click.option("--organization", "-o", required=True, help="Organization name")
@click.option("--api-token", "-t", help="Codacy API token (or set CODACY_API_TOKEN env var)")
@click.option("--output", "-f", type=click.Choice(["json", "text"]), default="text", 
              help="Output format")
@click.option("--output-file", help="Output file path (default: stdout)")
@click.option("--limit", "-l", type=int, help="Limit the number of dependencies to process (useful for testing)")
@click.option("--max-concurrent", type=int, default=5, help="Maximum concurrent requests (default: 5, reduced for rate limiting)")
@click.option("--batch-size", type=int, default=50, help="Dependencies to process per batch (default: 50)")
@click.option("--request-timeout", type=int, default=30, help="Request timeout in seconds (default: 30)")
@click.option("--show-stats", is_flag=True, help="Show performance statistics")
def main(provider: str, organization: str, api_token: Optional[str], 
         output: str, output_file: Optional[str], limit: Optional[int],
         max_concurrent: int, batch_size: int, request_timeout: int, show_stats: bool):
    """
    Async Codacy Dependency Reporter - High Performance Version
    
    This tool will scan all repositories in the specified Codacy organization
    and create a report showing where each dependency is used.
    
    Performance optimizations include:
    - Concurrent API requests
    - Response caching
    - Batch processing
    - Connection pooling
    """
    
    # Get API token from parameter or environment
    if not api_token:
        api_token = os.getenv("CODACY_API_TOKEN")
    
    if not api_token:
        click.echo("Error: API token is required. Use --api-token or set CODACY_API_TOKEN environment variable.", err=True)
        sys.exit(1)
    
    async def run_scan():
        start_time = time.time()
        
        async with AsyncCodacyAPIClient(
            api_token, 
            max_concurrent=max_concurrent,
            request_timeout=request_timeout
        ) as api_client:
            
            # Initialize reporter
            reporter = AsyncDependencyReporter(api_client, batch_size=batch_size)
            
            # Scan dependencies
            dependencies = await reporter.scan_organization_dependencies(provider, organization, limit)
            
            if not dependencies:
                click.echo("No dependencies found or error occurred during scanning.")
                return
            
            # Generate report
            report = reporter.generate_report(dependencies, output)
            
            # Output report
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(report)
                click.echo(f"Report saved to: {output_file}")
            else:
                click.echo(report)
            
            # Show performance statistics
            end_time = time.time()
            total_time = end_time - start_time
            
            if show_stats:
                stats = api_client.get_performance_stats()
                click.echo("\n" + "=" * 50)
                click.echo("PERFORMANCE STATISTICS")
                click.echo("=" * 50)
                click.echo(f"Total execution time: {total_time:.2f}s")
                click.echo(f"Total API requests: {stats['total_requests']}")
                click.echo(f"Cache hits: {stats['cache_hits']}")
                click.echo(f"Cache hit rate: {stats['cache_hit_rate']}")
                click.echo(f"Rate limit delays: {stats['rate_limit_delays']}")
                click.echo(f"Retry attempts: {stats['retry_attempts']}")
                click.echo(f"Requests per second: {stats['requests_per_second']}")
                click.echo(f"Dependencies found: {len(dependencies)}")
                
                total_usages = sum(len(usages) for usages in dependencies.values())
                click.echo(f"Total dependency usages: {total_usages}")
    
    try:
        asyncio.run(run_scan())
    except KeyboardInterrupt:
        click.echo("\nScan interrupted by user.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
