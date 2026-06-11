# OpenCitations API Service

[<img src="https://img.shields.io/badge/powered%20by-OpenCitations-%239931FC?labelColor=2D22DE" />](http://opencitations.net)
[![Run tests](https://github.com/opencitations/oc_api/actions/workflows/run_tests.yml/badge.svg?branch=main)](https://github.com/opencitations/oc_api/actions/workflows/run_tests.yml)
[![Coverage](test/coverage-badge.svg)](https://opencitations.github.io/oc_api/coverage/)

This repository contains the API service for OpenCitations, allowing users to interact with the OpenCitations datasets through RESTful endpoints.

## Overview

The service provides three main API endpoints:

- **Index endpoint** (`/index/v2`): For querying the OpenCitations Index database
- **Meta endpoint** (`/meta/v1`): For querying the OpenCitations Meta database
- **SKG-IF endpoint** (`/skg-if/v1`): For accessing OpenCitations data as JSON-LD compliant with the [Scientific Knowledge Graph Interoperability Framework](https://skg-if.github.io/interoperability-framework/); it combines bibliographic metadata from Meta with citation data from Index

## Configuration

### Environment Variables

The service requires the following environment variables. These values take precedence over the ones defined in `conf.json`:

- `BASE_URL`: Base URL for the API service
- `SPARQL_ENDPOINT_INDEX`: URL for the internal Index SPARQL endpoint (used by the API)
- `SPARQL_ENDPOINT_META`: URL for the internal Meta SPARQL endpoint (used by the API)
- `LOG_DIR`: Directory path where log files will be stored
- `SYNC_ENABLED`: Enable/disable static files synchronization (default: false)
- `REDIS_ENABLED`: Enable/disable Redis database used for storing tokens (default: false)
- `REDIS_HOST`: Redis server hostname (default from conf.json)
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis authentication password

For instance:
```env
# API Configuration
BASE_URL=api.opencitations.net
LOG_DIR=/home/dir/log/
SPARQL_ENDPOINT_INDEX=http://qlever-service.default.svc.cluster.local:7011  
SPARQL_ENDPOINT_META=http://virtuoso-service.default.svc.cluster.local:8890/sparql
SYNC_ENABLED=true

# Redis Configuration
REDIS_ENABLED=true
REDIS_HOST=redis-service.default.svc.cluster.local
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
```

> **Note**: When running with Docker, environment variables always override the corresponding values in `conf.json`. If an environment variable is not set, the application will fall back to the values defined in `conf.json`.

### Static Files Synchronization

The application can synchronize static files from a GitHub repository. This configuration is managed in `conf.json`:
```json
{
  "oc_services_templates": "https://github.com/opencitations/oc_services_templates",
  "sync": {
    "folders": [
      "static",
      "html-template/common"
    ],
    "files": [
      "test.txt"
    ]
  }
}
```

- `oc_services_templates`: The GitHub repository URL to sync files from
- `sync.folders`: List of folders to synchronize
- `sync.files`: List of individual files to synchronize

When static sync is enabled (via `--sync-static` or `SYNC_ENABLED=true`), the application will:
1. Clone the specified repository
2. Copy the specified folders and files
3. Keep the local static files up to date

> **Note**: Make sure the specified folders and files exist in the source repository.

## Running Options

### Local Development

For local development and testing, the application uses the built-in web.py HTTP server:
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Run with default settings
uv run python api_oc.py

# Run with static sync enabled
uv run python api_oc.py --sync-static

# Run on custom port
uv run python api_oc.py --port 8085

# Run with both options
uv run python api_oc.py --sync-static --port 8085
```

The application supports the following command line arguments:

- `--sync-static`: Synchronize static files at startup and enable periodic sync (every 30 minutes)
- `--port PORT`: Specify the port to run the application on (default: 8080)

### Production Deployment (Docker)

When running in Docker/Kubernetes, the application uses **Gunicorn** as the WSGI HTTP server for better performance and concurrency handling:

- **Server**: Gunicorn with gevent workers
- **Workers**: 4 concurrent worker processes
- **Worker Type**: gevent (async) for handling simultaneous requests
- **Timeout**: 180 seconds
- **Connections per worker**: 200 simultaneous connections

The Docker image version is read from `pyproject.toml` (single source of truth). To publish a new image on DockerHub, update the `version` field in `pyproject.toml` and push to `main` — the GitHub Actions workflow will build and push the new tag automatically, skipping the build if that version already exists.

```bash
VERSION=$(grep -m1 '^version' pyproject.toml | cut -d'"' -f2)

docker build -t opencitations/oc_api:$VERSION .
docker run -p 8080:8080 \
  -e SPARQL_ENDPOINT_INDEX=http://qlever:7011 \
  -e SPARQL_ENDPOINT_META=http://virtuoso:8890/sparql \
  opencitations/oc_api:$VERSION
```

The Docker container automatically uses Gunicorn and is configured with static sync enabled by default.

> **Note**: The application code automatically detects the execution environment. When run with `uv run python api_oc.py`, it uses the built-in web.py server. When run with Gunicorn (as in Docker), it uses the WSGI interface.

You can customize the Gunicorn server configuration by modifying the `gunicorn.conf.py` file.

## Testing

### Running Tests Locally

The tests require Docker. Pytest fixtures in `test/conftest.py` automatically start and stop the QLever and Virtuoso containers.

1. Install dependencies:
```bash
uv sync --dev
```

2. Run the tests:
```bash
uv run pytest --cov=src --cov-report=term-missing --cov-report=html
```