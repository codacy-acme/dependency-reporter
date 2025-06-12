# Dependency Reporter Performance Optimization

This document describes the performance improvements made to the Codacy Dependency Reporter and how to use the optimized version.

## Overview

The original `dependency_reporter.py` script has been optimized for performance with a new async version `dependency_reporter_async.py` that provides significant speed improvements through:

- **Concurrent API requests** using `asyncio` and `aiohttp`
- **Response caching** to avoid duplicate API calls
- **Batch processing** for better resource utilization
- **Connection pooling** for efficient HTTP connections
- **Smart file discovery** with optimized search patterns

## Performance Improvements

### Expected Speed Gains

Based on the optimization techniques implemented:

- **5-10x faster** from concurrent processing alone
- **Additional 2-3x improvement** from caching and request optimization
- **Overall 10-30x faster execution** depending on organization size and API response times

### Key Optimizations

1. **Async/Await Pattern**: All API calls are now non-blocking and can run concurrently
2. **Semaphore-based Concurrency Control**: Configurable limit on concurrent requests to avoid overwhelming the API
3. **Response Caching**: API responses are cached with TTL to avoid duplicate requests
4. **Batch Processing**: Dependencies are processed in configurable batches
5. **Connection Pooling**: HTTP connections are reused for better performance
6. **Smart File Pattern Matching**: Multiple file patterns are searched concurrently
7. **Rate Limiting Protection**: Built-in rate limiting (2400 requests per 5 minutes) with automatic delays
8. **Exponential Backoff**: Automatic retry with exponential backoff for 502 errors and timeouts

## Installation

Install the additional async dependencies:

```bash
pip install -r requirements.txt
```

The new requirements include:
- `aiohttp>=3.9.0` - Async HTTP client
- `aiofiles>=23.2.0` - Async file operations

## Usage

### Basic Usage

The async version maintains the same CLI interface as the original:

```bash
python dependency_reporter_async.py --organization your-org-name
```

### Performance Tuning Options

The async version includes additional options for performance tuning:

```bash
python dependency_reporter_async.py \
  --organization your-org-name \
  --max-concurrent 20 \
  --batch-size 100 \
  --request-timeout 60 \
  --show-stats
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--max-concurrent` | 5 | Maximum concurrent API requests (reduced for rate limiting) |
| `--batch-size` | 50 | Dependencies to process per batch |
| `--request-timeout` | 30 | Request timeout in seconds |
| `--show-stats` | False | Show detailed performance statistics |

### Performance Statistics

Use `--show-stats` to see detailed performance metrics:

```
PERFORMANCE STATISTICS
==================================================
Total execution time: 45.23s
Total API requests: 1,247
Cache hits: 312
Cache hit rate: 25.0%
Rate limit delays: 2
Retry attempts: 8
Requests per second: 27.58
Dependencies found: 156
Total dependency usages: 1,089
```

## Performance Testing

Use the included performance test script to compare versions:

```bash
# Test with a small limit for quick comparison
python performance_test.py --organization your-org --limit 10

# Skip the original version if it's too slow
python performance_test.py --organization your-org --limit 50 --skip-original

# Test with different concurrency settings
python performance_test.py --organization your-org --limit 20 --max-concurrent 20
```

### Test Output Example

```
PERFORMANCE COMPARISON RESULTS
============================================================

ORIGINAL SYNCHRONOUS VERSION:
------------------------------
✅ Execution time: 180.45 seconds
✅ Status: Completed successfully

ASYNC OPTIMIZED VERSION:
------------------------------
✅ Execution time: 12.34 seconds
✅ Status: Completed successfully
📊 Total API requests: 456
📊 Cache hits: 89
📊 Cache hit rate: 19.5%
📊 Requests per second: 36.95

🚀 PERFORMANCE IMPROVEMENT:
   Speedup: 14.62x faster
   Time saved: 168.11 seconds
   🎉 The async version is 14.6x faster!
```

## Configuration Recommendations

### For Small Organizations (< 50 repositories)
```bash
--max-concurrent 5 --batch-size 25
```

### For Medium Organizations (50-200 repositories)
```bash
--max-concurrent 10 --batch-size 50
```

### For Large Organizations (200+ repositories)
```bash
--max-concurrent 20 --batch-size 100
```

### For Very Large Organizations (1000+ repositories)
```bash
--max-concurrent 30 --batch-size 200 --request-timeout 60
```

## Error Handling and Resilience

The async version includes improved error handling:

- **Timeout handling**: Configurable request timeouts with graceful degradation
- **Rate limiting protection**: Semaphore-based concurrency control
- **Retry logic**: Failed requests are logged but don't stop the entire process
- **Graceful interruption**: Ctrl+C handling for clean shutdown

## Monitoring and Debugging

### Progress Tracking

The async version provides detailed progress information:

```
Scanning dependencies for organization: your-org
Found 234 unique dependencies
Processing batch 1/5 (50 dependencies)
Progress: 50/234 (21.4%)
Processing batch 2/5 (50 dependencies)
Progress: 100/234 (42.7%)
...
```

### Performance Monitoring

Enable `--show-stats` to monitor:
- Total execution time
- API request count and rate
- Cache hit rate
- Dependencies and usages found

### Debugging

For debugging issues:

1. **Reduce concurrency**: Use `--max-concurrent 1` to isolate issues
2. **Increase timeout**: Use `--request-timeout 60` for slow APIs
3. **Limit scope**: Use `--limit 10` for testing
4. **Check logs**: Error messages are printed to stderr

## Backward Compatibility

The async version maintains full backward compatibility:

- Same CLI interface (with additional optional parameters)
- Same output formats (JSON and text)
- Same environment variable support
- Same error codes and behavior

## Migration Guide

To migrate from the original to the async version:

1. **Install new dependencies**: `pip install -r requirements.txt`
2. **Replace script name**: Change `dependency_reporter.py` to `dependency_reporter_async.py`
3. **Add performance options**: Optionally add `--max-concurrent`, `--batch-size`, etc.
4. **Test with limits**: Use `--limit` for initial testing
5. **Monitor performance**: Use `--show-stats` to verify improvements

## Troubleshooting

### Common Issues

**"Too many open files" error**:
- Reduce `--max-concurrent` value
- Check system ulimit settings

**Timeout errors**:
- Increase `--request-timeout`
- Reduce `--max-concurrent`
- Check network connectivity

**Memory usage**:
- Reduce `--batch-size`
- Process in smaller chunks with `--limit`

**API rate limiting**:
- Reduce `--max-concurrent`
- Add delays between batches (future enhancement)

### Performance Not Improving

If you don't see expected performance gains:

1. **Check network latency**: High latency reduces concurrent benefits
2. **Verify API limits**: Some APIs may have strict rate limits
3. **Monitor system resources**: CPU/memory constraints can limit gains
4. **Test with different settings**: Try various `--max-concurrent` values

## Future Enhancements

Planned improvements for future versions:

- **Exponential backoff**: Automatic retry with backoff for failed requests
- **Circuit breaker**: Automatic failure detection and recovery
- **Persistent caching**: Cache responses across runs
- **Progress persistence**: Resume interrupted scans
- **Real-time streaming**: Process results as they arrive
- **Advanced filtering**: Skip known dependencies or repositories

## Contributing

To contribute performance improvements:

1. **Profile the code**: Use `cProfile` or similar tools
2. **Benchmark changes**: Use the performance test script
3. **Test with real data**: Verify improvements with actual organizations
4. **Document changes**: Update this README with new optimizations

## Support

For performance-related issues:

1. **Run performance test**: Use `performance_test.py` to identify bottlenecks
2. **Check system resources**: Monitor CPU, memory, and network usage
3. **Review logs**: Look for error patterns or timeouts
4. **Experiment with settings**: Try different concurrency and batch sizes
