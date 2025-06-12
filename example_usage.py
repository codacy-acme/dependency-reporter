#!/usr/bin/env python3
"""
Example Usage Script for Async Dependency Reporter

This script demonstrates how to use the async dependency reporter
and shows the performance benefits compared to the original version.
"""

import os
import sys
import asyncio
import time
from dependency_reporter_async import AsyncCodacyAPIClient, AsyncDependencyReporter

async def example_basic_usage():
    """Basic example of using the async dependency reporter"""
    
    # Check for API token
    api_token = os.getenv("CODACY_API_TOKEN")
    if not api_token:
        print("Error: Please set CODACY_API_TOKEN environment variable")
        return
    
    # Configuration
    provider = "gh"  # GitHub
    organization = "your-organization-name"  # Replace with your org
    
    print("🚀 Async Dependency Reporter Example")
    print("=" * 50)
    print(f"Organization: {organization}")
    print(f"Provider: {provider}")
    print()
    
    start_time = time.time()
    
    # Create async API client with optimized settings
    async with AsyncCodacyAPIClient(
        api_token=api_token,
        max_concurrent=15,  # Allow up to 15 concurrent requests
        request_timeout=30   # 30 second timeout per request
    ) as api_client:
        
        # Create reporter with batch processing
        reporter = AsyncDependencyReporter(
            api_client=api_client,
            batch_size=25  # Process 25 dependencies per batch
        )
        
        print("📊 Starting dependency scan...")
        
        # Scan dependencies (limit to 20 for demo purposes)
        dependencies = await reporter.scan_organization_dependencies(
            provider=provider,
            organization=organization,
            limit=20  # Limit for demo - remove for full scan
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        print(f"\n✅ Scan completed in {execution_time:.2f} seconds")
        print(f"📦 Found {len(dependencies)} unique dependencies")
        
        # Calculate total usages
        total_usages = sum(len(usages) for usages in dependencies.values())
        print(f"🔗 Total dependency usages: {total_usages}")
        
        # Show performance stats
        stats = api_client.get_performance_stats()
        print(f"\n📈 Performance Statistics:")
        print(f"   Total API requests: {stats['total_requests']}")
        print(f"   Cache hits: {stats['cache_hits']}")
        print(f"   Cache hit rate: {stats['cache_hit_rate']}")
        print(f"   Requests per second: {stats['requests_per_second']}")
        
        # Show sample dependencies
        print(f"\n📋 Sample Dependencies:")
        for i, (dep_name, usages) in enumerate(list(dependencies.items())[:5]):
            print(f"   {i+1}. {dep_name}")
            print(f"      Used in {len(usages)} repositories")
            if usages:
                sample_repo = usages[0].repository_name
                print(f"      Example: {sample_repo}")
        
        if len(dependencies) > 5:
            print(f"   ... and {len(dependencies) - 5} more dependencies")
        
        # Generate JSON report
        json_report = reporter.generate_report(dependencies, "json")
        
        # Save to file
        output_file = f"dependencies_report_{int(time.time())}.json"
        with open(output_file, 'w') as f:
            f.write(json_report)
        
        print(f"\n💾 Report saved to: {output_file}")

async def example_performance_comparison():
    """Example showing performance comparison techniques"""
    
    print("\n🏁 Performance Comparison Example")
    print("=" * 50)
    
    # Different concurrency settings to test
    concurrency_settings = [
        {"max_concurrent": 5, "batch_size": 10, "name": "Conservative"},
        {"max_concurrent": 10, "batch_size": 25, "name": "Balanced"},
        {"max_concurrent": 20, "batch_size": 50, "name": "Aggressive"},
    ]
    
    api_token = os.getenv("CODACY_API_TOKEN")
    if not api_token:
        print("Error: Please set CODACY_API_TOKEN environment variable")
        return
    
    provider = "gh"
    organization = "your-organization-name"  # Replace with your org
    
    results = []
    
    for settings in concurrency_settings:
        print(f"\n🧪 Testing {settings['name']} settings:")
        print(f"   Max concurrent: {settings['max_concurrent']}")
        print(f"   Batch size: {settings['batch_size']}")
        
        start_time = time.time()
        
        async with AsyncCodacyAPIClient(
            api_token=api_token,
            max_concurrent=settings['max_concurrent'],
            request_timeout=30
        ) as api_client:
            
            reporter = AsyncDependencyReporter(
                api_client=api_client,
                batch_size=settings['batch_size']
            )
            
            # Small test with limited dependencies
            dependencies = await reporter.scan_organization_dependencies(
                provider=provider,
                organization=organization,
                limit=10  # Small test
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            stats = api_client.get_performance_stats()
            
            result = {
                "name": settings['name'],
                "execution_time": execution_time,
                "dependencies_found": len(dependencies),
                "total_requests": stats['total_requests'],
                "cache_hit_rate": stats['cache_hit_rate'],
                "requests_per_second": stats['requests_per_second']
            }
            
            results.append(result)
            
            print(f"   ⏱️  Execution time: {execution_time:.2f}s")
            print(f"   📦 Dependencies found: {len(dependencies)}")
            print(f"   🌐 API requests: {stats['total_requests']}")
            print(f"   💾 Cache hit rate: {stats['cache_hit_rate']}")
    
    # Compare results
    print(f"\n📊 Performance Comparison Summary:")
    print("-" * 50)
    
    fastest = min(results, key=lambda x: x['execution_time'])
    
    for result in results:
        speedup = fastest['execution_time'] / result['execution_time']
        status = "🏆" if result == fastest else "📈"
        
        print(f"{status} {result['name']}:")
        print(f"   Time: {result['execution_time']:.2f}s")
        print(f"   Speedup: {speedup:.2f}x")
        print(f"   Requests/sec: {result['requests_per_second']}")
        print()

async def example_error_handling():
    """Example showing error handling and resilience"""
    
    print("\n🛡️  Error Handling Example")
    print("=" * 50)
    
    api_token = os.getenv("CODACY_API_TOKEN")
    if not api_token:
        print("Error: Please set CODACY_API_TOKEN environment variable")
        return
    
    # Test with aggressive settings that might cause issues
    async with AsyncCodacyAPIClient(
        api_token=api_token,
        max_concurrent=50,  # Very high concurrency
        request_timeout=5   # Short timeout
    ) as api_client:
        
        reporter = AsyncDependencyReporter(api_client, batch_size=100)
        
        try:
            print("🧪 Testing with aggressive settings (high concurrency, short timeout)...")
            
            dependencies = await reporter.scan_organization_dependencies(
                provider="gh",
                organization="your-organization-name",  # Replace with your org
                limit=5  # Small test
            )
            
            print(f"✅ Successfully handled aggressive settings")
            print(f"📦 Found {len(dependencies)} dependencies")
            
            stats = api_client.get_performance_stats()
            print(f"📈 Performance: {stats['requests_per_second']} req/sec")
            
        except Exception as e:
            print(f"❌ Error occurred: {e}")
            print("💡 Try reducing --max-concurrent or increasing --request-timeout")

def main():
    """Main function to run examples"""
    
    print("🎯 Async Dependency Reporter Examples")
    print("=" * 60)
    print()
    print("Before running these examples:")
    print("1. Set CODACY_API_TOKEN environment variable")
    print("2. Replace 'your-organization-name' with your actual organization")
    print("3. Install requirements: pip install -r requirements.txt")
    print()
    
    if len(sys.argv) > 1:
        example_type = sys.argv[1]
    else:
        print("Available examples:")
        print("  basic       - Basic usage example")
        print("  performance - Performance comparison")
        print("  errors      - Error handling example")
        print("  all         - Run all examples")
        print()
        example_type = input("Choose an example (or 'all'): ").strip().lower()
    
    if example_type in ["basic", "all"]:
        asyncio.run(example_basic_usage())
    
    if example_type in ["performance", "all"]:
        asyncio.run(example_performance_comparison())
    
    if example_type in ["errors", "all"]:
        asyncio.run(example_error_handling())
    
    print("\n🎉 Examples completed!")
    print("\nNext steps:")
    print("1. Try the performance test: python performance_test.py --organization your-org --limit 10")
    print("2. Run a full scan: python dependency_reporter_async.py --organization your-org --show-stats")
    print("3. Experiment with different --max-concurrent and --batch-size values")

if __name__ == "__main__":
    main()
