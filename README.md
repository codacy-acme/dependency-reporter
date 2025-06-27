# Codacy Dependency Reporter

A Python utility to scan Codacy organizations for dependencies and generate reports showing where each dependency is used across repositories.

## Features

- Scans all repositories in a Codacy organization
- Identifies dependencies using Codacy's SBOM (Software Bill of Materials) API
- Shows which repositories use each dependency with specific file paths
- Detects dependencies across multiple package managers (npm, Maven, pip, Gradle, etc.)
- Provides dependency versions and types
- Supports multiple output formats (JSON, CSV, text)
- Command-line interface with flexible options
- File-level dependency mapping for precise location tracking
- Asynchronous processing for improved performance
- License information retrieval with caching
- Rate limiting and retry mechanisms

## Prerequisites

- Python 3.7+
- Codacy API token with access to the organization
- Organization must have SBOM data available (requires dependency scanning to be enabled)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd dependency-reporter
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your API token:
```bash
cp .env.example .env
# Edit .env and add your Codacy API token
```

## Usage

### Basic Usage

```bash
python dependency_reporter_async.py --provider gh --organization your-organization-name
```

### With API Token

```bash
python dependency_reporter_async.py --provider gh --organization your-organization-name --api-token your_api_token
```

### Different Output Formats

```bash
# CSV output
python dependency_reporter_async.py --provider gh --organization your-org --output csv

# JSON output
python dependency_reporter_async.py --provider gh --organization your-org --output json

# Save to file
python dependency_reporter_async.py --provider gh --organization your-org --output csv --output-file dependencies.csv
```

### Different Git Providers

```bash
# GitHub (default)
python dependency_reporter_async.py --provider gh --organization your-org

# GitLab
python dependency_reporter_async.py --provider gl --organization your-org

# Bitbucket
python dependency_reporter_async.py --provider bb --organization your-org
```

### Additional Options

```bash
# Limit number of dependencies processed
python dependency_reporter_async.py --provider gh --organization your-org --limit 10

# Show performance statistics
python dependency_reporter_async.py --provider gh --organization your-org --show-stats

# Disable license caching
python dependency_reporter_async.py --provider gh --organization your-org --no-cache
```

## Command Line Options

- `--provider`: Git provider (gh, gl, bb) - default: gh
- `--organization`: Organization name (required)
- `--api-token`: Codacy API token (or set CODACY_API_TOKEN env var)
- `--output`: Output format (json, csv, text) - default: text
- `--output-file`: Output file path (default: stdout)
- `--limit`: Limit number of dependencies to process
- `--show-stats`: Show performance statistics
- `--no-cache`: Disable license caching

## API Token Setup

1. Go to [Codacy API Tokens](https://app.codacy.com/account/api-tokens)
2. Create a new account API token
3. Set it in your environment:
   ```bash
   export CODACY_API_TOKEN=your_token_here
   ```
   Or add it to your `.env` file

## Sample Output

### CSV Format
```csv
Dependency Name,Version,Type,License Name,Repository,File Path
npm/lodash,4.17.21,npm,MIT License,frontend-app,package.json
npm/lodash,4.17.21,npm,MIT License,frontend-app,yarn.lock
maven/com.fasterxml.jackson.core/jackson-core,2.15.2,maven,Apache License 2.0,my-api-service,pom.xml
```

### JSON Format
```json
{
  "npm/lodash": [
    {
      "repository": "frontend-app",
      "file_paths": ["package.json", "yarn.lock"],
      "version": "4.17.21",
      "type": "npm",
      "license": "MIT License"
    }
  ],
  "maven/com.fasterxml.jackson.core/jackson-core": [
    {
      "repository": "my-api-service",
      "file_paths": ["pom.xml"],
      "version": "2.15.2",
      "type": "maven",
      "license": "Apache License 2.0"
    }
  ]
}
```

### Text Format
```
DEPENDENCY USAGE REPORT

Dependency: npm/lodash
License: MIT License
Used in 1 repositories:

  Repository: frontend-app
    Files: package.json, yarn.lock
    Version: 4.17.21
    Type: npm

------------------------------

Dependency: maven/com.fasterxml.jackson.core/jackson-core
License: Apache License 2.0
Used in 1 repositories:

  Repository: my-api-service
    Files: pom.xml
    Version: 2.15.2
    Type: maven

------------------------------
```

## Performance Features

- **Asynchronous Processing**: Uses async/await for concurrent API calls
- **License Caching**: Caches license information to reduce API calls
- **Rate Limiting**: Automatically handles API rate limits with exponential backoff
- **Progress Tracking**: Shows real-time progress for large organizations
- **Statistics**: Optional performance statistics display

## Limitations

- Requires SBOM data to be available in Codacy (dependency scanning must be enabled)
- Rate limited by Codacy API limits
- File content analysis is performed for each repository, which may increase processing time for large organizations

## Error Handling

The tool includes comprehensive error handling for:
- Invalid API tokens
- Network connectivity issues
- API rate limits
- Missing organizations or repositories
- Malformed dependency data

## Development

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]
