# Codacy Dependency Reporter

A Python utility to scan Codacy organizations for dependencies and generate reports showing where each dependency is used across repositories.

## Features

- Scans all repositories in a Codacy organization
- Identifies dependencies using Codacy's SBOM (Software Bill of Materials) API
- Shows which repositories use each dependency with specific file paths
- Detects dependencies across multiple package managers (npm, Maven, pip, Gradle, etc.)
- Provides dependency versions and types
- Supports multiple output formats (JSON, text)
- Command-line interface with flexible options
- File-level dependency mapping for precise location tracking

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
python dependency_reporter.py -o your-organization-name
```

### With API Token

```bash
python dependency_reporter.py -o your-organization-name -t your_api_token
```

### Different Output Formats

```bash
# JSON output
python dependency_reporter.py -o your-org -f json

# Save to file
python dependency_reporter.py -o your-org -f json --output-file dependencies.json
```

### Different Git Providers

```bash
# GitHub (default)
python dependency_reporter.py -p gh -o your-org

# GitLab
python dependency_reporter.py -p gl -o your-org

# Bitbucket
python dependency_reporter.py -p bb -o your-org
```

## Command Line Options

- `-p, --provider`: Git provider (gh, gl, bb) - default: gh
- `-o, --organization`: Organization name (required)
- `-t, --api-token`: Codacy API token (or set CODACY_API_TOKEN env var)
- `-f, --output`: Output format (json, text) - default: text
- `--output-file`: Output file path (default: stdout)

## API Token Setup

1. Go to [Codacy API Tokens](https://app.codacy.com/account/api-tokens)
2. Create a new account API token
3. Set it in your environment:
   ```bash
   export CODACY_API_TOKEN=your_token_here
   ```
   Or add it to your `.env` file

## Sample Output

### Text Format
```
DEPENDENCY USAGE REPORT

Dependency: maven/com.fasterxml.jackson.core/jackson-core
Used in 3 repositories:

  Repository: my-api-service
    Files: pom.xml, build.gradle
    Version: 2.15.2
    Type: maven

  Repository: data-processor
    Files: pom.xml
    Version: 2.14.1
    Type: maven

------------------------------

Dependency: npm/lodash
Used in 2 repositories:

  Repository: frontend-app
    Files: package.json, yarn.lock
    Version: 4.17.21
    Type: npm

  Repository: admin-dashboard
    Files: package.json, package-lock.json
    Version: 4.17.19
    Type: npm

------------------------------
```

### JSON Format
```json
{
  "maven/com.fasterxml.jackson.core/jackson-core": [
    {
      "repository": "my-api-service",
      "file_paths": ["pom.xml", "build.gradle"],
      "version": "2.15.2",
      "type": "maven"
    },
    {
      "repository": "data-processor",
      "file_paths": ["pom.xml"],
      "version": "2.14.1",
      "type": "maven"
    }
  ],
  "npm/lodash": [
    {
      "repository": "frontend-app",
      "file_paths": ["package.json", "yarn.lock"],
      "version": "4.17.21",
      "type": "npm"
    },
    {
      "repository": "admin-dashboard",
      "file_paths": ["package.json", "package-lock.json"],
      "version": "4.17.19",
      "type": "npm"
    }
  ]
}
```

## Limitations

- File path detection uses pattern matching on common dependency files (may not catch all edge cases)
- Requires SBOM data to be available in Codacy (dependency scanning must be enabled)
- Rate limited by Codacy API limits
- File content analysis is performed for each repository, which may increase processing time for large organizations

## Error Handling

The tool includes comprehensive error handling for:
- Invalid API tokens
- Network connectivity issues
- API rate limits
- Missing organizations or repositories

## Development

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]
