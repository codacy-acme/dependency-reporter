#!/usr/bin/env python3
"""
Codacy Dependency Reporter

A utility to scan all repositories in a Codacy organization and report on dependencies
across repositories, showing where each dependency is used with file paths and names.
"""

import os
import sys
import json
import requests
import re
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

class CodacyAPIClient:
    """Client for interacting with the Codacy API"""
    
    def __init__(self, api_token: str, base_url: str = "https://app.codacy.com/api/v3"):
        self.api_token = api_token
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "api-token": api_token,
            "Content-Type": "application/json"
        })
    
    def get_organization_repositories(self, provider: str, organization: str) -> List[Dict[str, Any]]:
        """Get all repositories for an organization"""
        repositories = []
        cursor = None
        
        while True:
            url = f"{self.base_url}/organizations/{provider}/{organization}/repositories"
            params = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                repositories.extend(data.get("data", []))
                
                # Check if there are more pages
                pagination = data.get("pagination", {})
                cursor = pagination.get("cursor")
                if not cursor:
                    break
                    
            except requests.exceptions.RequestException as e:
                click.echo(f"Error fetching repositories: {e}", err=True)
                break
        
        return repositories
    
    def search_sbom_dependencies(self, provider: str, organization: str, 
                                cursor: Optional[str] = None, 
                                limit: int = 100) -> Dict[str, Any]:
        """Search for SBOM dependencies in the organization"""
        url = f"{self.base_url}/organizations/{provider}/{organization}/sbom/dependencies/search"
        
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        
        # Empty body for now - we want all dependencies
        body = {}
        
        try:
            response = self.session.post(url, params=params, json=body)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            click.echo(f"Error searching SBOM dependencies: {e}", err=True)
            return {}
    
    def search_repositories_of_dependency(self, provider: str, organization: str, 
                                        dependency_full_name: str,
                                        cursor: Optional[str] = None,
                                        limit: int = 100) -> Dict[str, Any]:
        """Search for repositories that use a specific dependency"""
        url = f"{self.base_url}/organizations/{provider}/{organization}/sbom/dependencies/repositories/search"
        
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        
        body = {"dependencyFullName": dependency_full_name}
        
        try:
            response = self.session.post(url, params=params, json=body)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            click.echo(f"Error searching repositories for dependency {dependency_full_name}: {e}", err=True)
            return {}
    
    def get_repository_files(self, provider: str, organization: str, repository: str,
                           search_pattern: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get files from a repository, optionally filtered by search pattern"""
        url = f"{self.base_url}/organizations/{provider}/{organization}/repositories/{repository}/files"
        
        params = {"limit": 100}
        if search_pattern:
            params["search"] = search_pattern
        
        files = []
        cursor = None
        
        while True:
            if cursor:
                params["cursor"] = cursor
            
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                files.extend(data.get("data", []))
                
                # Check pagination
                pagination = data.get("pagination", {})
                cursor = pagination.get("cursor")
                if not cursor:
                    break
                    
            except requests.exceptions.RequestException as e:
                click.echo(f"Error fetching files for repository {repository}: {e}", err=True)
                break
        
        return files

class DependencyReporter:
    """Main class for dependency reporting functionality"""
    
    def __init__(self, api_client: CodacyAPIClient):
        self.api_client = api_client
        self.dependencies_data = defaultdict(list)
    
    def scan_organization_dependencies(self, provider: str, organization: str, limit: Optional[int] = None) -> Dict[str, List[DependencyInfo]]:
        """Scan all dependencies across the organization"""
        click.echo(f"Scanning dependencies for organization: {organization}")
        if limit:
            click.echo(f"Limiting scan to first {limit} dependencies")
        
        # First, get all dependencies in the organization
        all_dependencies = []
        cursor = None
        
        while True:
            click.echo("Fetching dependencies...")
            result = self.api_client.search_sbom_dependencies(provider, organization, cursor)
            
            if not result or "data" not in result:
                break
            
            dependencies = result["data"]
            all_dependencies.extend(dependencies)
            
            # Check pagination
            pagination = result.get("pagination", {})
            cursor = pagination.get("cursor")
            if not cursor:
                break
        
        total_dependencies = len(all_dependencies)
        
        # Apply limit if specified
        if limit and limit < total_dependencies:
            all_dependencies = all_dependencies[:limit]
            click.echo(f"Found {total_dependencies} unique dependencies, processing first {limit}")
        else:
            click.echo(f"Found {total_dependencies} unique dependencies")
        
        # For each dependency, find which repositories use it
        dependency_usage = defaultdict(list)
        
        for i, dep in enumerate(all_dependencies, 1):
            dep_name = dep.get("fullName", "")
            if not dep_name:
                continue
            
            progress_info = f"{i}/{len(all_dependencies)}"
            if limit and limit < total_dependencies:
                progress_info += f" (limited from {total_dependencies})"
            
            click.echo(f"Processing dependency {progress_info}: {dep_name}")
            
            # Get repositories that use this dependency
            repos_cursor = None
            while True:
                repos_result = self.api_client.search_repositories_of_dependency(
                    provider, organization, dep_name, repos_cursor
                )
                
                if not repos_result or "data" not in repos_result:
                    break
                
                repositories = repos_result["data"]
                
                for repo in repositories:
                    repo_name = repo.get("name", "")
                    dep_version = repo.get("dependencyVersion", "")
                    dep_type = self._extract_dependency_type(dep_name)
                    
                    # Try to find dependency files in the repository
                    dependency_files = self._find_dependency_files(provider, organization, repo_name, dep_type)
                    
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
                            dependency_usage[dep_name].append(dep_info)
                    else:
                        # No specific files found, create entry without file path
                        dep_info = DependencyInfo(
                            repository_name=repo_name,
                            file_path="",  # No specific file found
                            dependency_name=dep_name,
                            dependency_version=dep_version,
                            dependency_type=dep_type
                        )
                        dependency_usage[dep_name].append(dep_info)
                
                # Check pagination for repositories
                repos_pagination = repos_result.get("pagination", {})
                repos_cursor = repos_pagination.get("cursor")
                if not repos_cursor:
                    break
        
        return dict(dependency_usage)
    
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
    
    def _find_dependency_files(self, provider: str, organization: str, repository: str, 
                              dependency_type: str) -> List[str]:
        """Find dependency files in a repository based on dependency type"""
        patterns = self._get_dependency_file_patterns(dependency_type)
        found_files = []
        
        for pattern in patterns:
            files = self.api_client.get_repository_files(provider, organization, repository, pattern)
            for file_info in files:
                file_path = file_info.get("path", "")
                if file_path and file_path not in found_files:
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
def main(provider: str, organization: str, api_token: Optional[str], 
         output: str, output_file: Optional[str], limit: Optional[int]):
    """
    Scan Codacy organization for dependencies and generate a report.
    
    This tool will scan all repositories in the specified Codacy organization
    and create a report showing where each dependency is used.
    """
    
    # Get API token from parameter or environment
    if not api_token:
        api_token = os.getenv("CODACY_API_TOKEN")
    
    if not api_token:
        click.echo("Error: API token is required. Use --api-token or set CODACY_API_TOKEN environment variable.", err=True)
        sys.exit(1)
    
    try:
        # Initialize API client
        api_client = CodacyAPIClient(api_token)
        
        # Initialize reporter
        reporter = DependencyReporter(api_client)
        
        # Scan dependencies
        dependencies = reporter.scan_organization_dependencies(provider, organization, limit)
        
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
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
