#!/usr/bin/env python3
"""
Performance Test Script for Dependency Reporter

This script helps compare the performance between the original synchronous version
and the new async optimized version of the dependency reporter.
"""

import os
import sys
import time
import subprocess
import argparse
from typing import Dict, Any

def run_command(command: list, timeout: int = 300) -> Dict[str, Any]:
    """Run a command and return timing and output information"""
    start_time = time.time()
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        return {
            "success": result.returncode == 0,
            "execution_time": execution_time,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "execution_time": timeout,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "returncode": -1
        }
    except Exception as e:
        return {
            "success": False,
            "execution_time": 0,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1
        }

def test_original_version(provider: str, organization: str, limit: int = None) -> Dict[str, Any]:
    """Test the original synchronous version"""
    print("Testing original synchronous version...")
    
    command = [
        sys.executable, "dependency_reporter.py",
        "--provider", provider,
        "--organization", organization,
        "--output", "json"
    ]
    
    if limit:
        command.extend(["--limit", str(limit)])
    
    return run_command(command)

def test_async_version(provider: str, organization: str, limit: int = None, 
                      max_concurrent: int = 10, batch_size: int = 50) -> Dict[str, Any]:
    """Test the new async optimized version"""
    print("Testing async optimized version...")
    
    command = [
        sys.executable, "dependency_reporter_async.py",
        "--provider", provider,
        "--organization", organization,
        "--output", "json",
        "--max-concurrent", str(max_concurrent),
        "--batch-size", str(batch_size),
        "--show-stats"
    ]
    
    if limit:
        command.extend(["--limit", str(limit)])
    
    return run_command(command)

def compare_results(original_result: Dict[str, Any], async_result: Dict[str, Any]):
    """Compare and display the results of both versions"""
    print("\n" + "=" * 60)
    print("PERFORMANCE COMPARISON RESULTS")
    print("=" * 60)
    
    # Original version results
    print("\nORIGINAL SYNCHRONOUS VERSION:")
    print("-" * 30)
    if original_result["success"]:
        print(f"✅ Execution time: {original_result['execution_time']:.2f} seconds")
        print(f"✅ Status: Completed successfully")
    else:
        print(f"❌ Status: Failed (return code: {original_result['returncode']})")
        print(f"⏱️  Execution time: {original_result['execution_time']:.2f} seconds")
        if original_result["stderr"]:
            print(f"Error: {original_result['stderr'][:200]}...")
    
    # Async version results
    print("\nASYNC OPTIMIZED VERSION:")
    print("-" * 30)
    if async_result["success"]:
        print(f"✅ Execution time: {async_result['execution_time']:.2f} seconds")
        print(f"✅ Status: Completed successfully")
        
        # Extract performance stats from output if available
        if "PERFORMANCE STATISTICS" in async_result["stdout"]:
            stats_section = async_result["stdout"].split("PERFORMANCE STATISTICS")[1]
            for line in stats_section.split('\n')[:10]:  # First 10 lines of stats
                if line.strip() and not line.startswith('='):
                    print(f"📊 {line.strip()}")
    else:
        print(f"❌ Status: Failed (return code: {async_result['returncode']})")
        print(f"⏱️  Execution time: {async_result['execution_time']:.2f} seconds")
        if async_result["stderr"]:
            print(f"Error: {async_result['stderr'][:200]}...")
    
    # Performance comparison
    if original_result["success"] and async_result["success"]:
        speedup = original_result["execution_time"] / async_result["execution_time"]
        print(f"\n🚀 PERFORMANCE IMPROVEMENT:")
        print(f"   Speedup: {speedup:.2f}x faster")
        print(f"   Time saved: {original_result['execution_time'] - async_result['execution_time']:.2f} seconds")
        
        if speedup > 1:
            print(f"   🎉 The async version is {speedup:.1f}x faster!")
        else:
            print(f"   ⚠️  The async version was slower by {1/speedup:.1f}x")
    
    print("\n" + "=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Performance test for dependency reporter")
    parser.add_argument("--provider", "-p", default="gh", help="Git provider (gh, gl, bb)")
    parser.add_argument("--organization", "-o", required=True, help="Organization name")
    parser.add_argument("--limit", "-l", type=int, default=10, 
                       help="Limit dependencies for testing (default: 10)")
    parser.add_argument("--max-concurrent", type=int, default=10,
                       help="Max concurrent requests for async version (default: 10)")
    parser.add_argument("--batch-size", type=int, default=50,
                       help="Batch size for async version (default: 50)")
    parser.add_argument("--skip-original", action="store_true",
                       help="Skip testing the original version (useful if it's too slow)")
    parser.add_argument("--timeout", type=int, default=300,
                       help="Timeout for each test in seconds (default: 300)")
    
    args = parser.parse_args()
    
    # Check if API token is available
    if not os.getenv("CODACY_API_TOKEN"):
        print("Error: CODACY_API_TOKEN environment variable is required")
        sys.exit(1)
    
    print(f"Performance testing with organization: {args.organization}")
    print(f"Dependency limit: {args.limit}")
    print(f"Timeout: {args.timeout} seconds")
    print("-" * 60)
    
    # Test original version (unless skipped)
    original_result = None
    if not args.skip_original:
        original_result = test_original_version(args.provider, args.organization, args.limit)
    else:
        print("Skipping original version test...")
        original_result = {
            "success": False,
            "execution_time": float('inf'),
            "stdout": "",
            "stderr": "Skipped",
            "returncode": 0
        }
    
    # Test async version
    async_result = test_async_version(
        args.provider, args.organization, args.limit,
        args.max_concurrent, args.batch_size
    )
    
    # Compare results
    compare_results(original_result, async_result)
    
    # Save detailed results to file
    results_file = f"performance_test_results_{int(time.time())}.txt"
    with open(results_file, 'w') as f:
        f.write("DEPENDENCY REPORTER PERFORMANCE TEST RESULTS\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Test parameters:\n")
        f.write(f"  Organization: {args.organization}\n")
        f.write(f"  Provider: {args.provider}\n")
        f.write(f"  Dependency limit: {args.limit}\n")
        f.write(f"  Max concurrent: {args.max_concurrent}\n")
        f.write(f"  Batch size: {args.batch_size}\n\n")
        
        f.write("ORIGINAL VERSION RESULTS:\n")
        f.write("-" * 30 + "\n")
        f.write(f"Success: {original_result['success']}\n")
        f.write(f"Execution time: {original_result['execution_time']:.2f}s\n")
        f.write(f"Return code: {original_result['returncode']}\n")
        if original_result['stderr']:
            f.write(f"Stderr: {original_result['stderr']}\n")
        f.write("\n")
        
        f.write("ASYNC VERSION RESULTS:\n")
        f.write("-" * 30 + "\n")
        f.write(f"Success: {async_result['success']}\n")
        f.write(f"Execution time: {async_result['execution_time']:.2f}s\n")
        f.write(f"Return code: {async_result['returncode']}\n")
        if async_result['stderr']:
            f.write(f"Stderr: {async_result['stderr']}\n")
        f.write(f"Stdout:\n{async_result['stdout']}\n")
    
    print(f"\nDetailed results saved to: {results_file}")

if __name__ == "__main__":
    main()
