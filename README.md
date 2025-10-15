# OpenCitations API Service

[<img src="https://img.shields.io/badge/powered%20by-OpenCitations-%239931FC?labelColor=2D22DE" />](http://opencitations.net)
[![Run tests](https://github.com/opencitations/oc_api/actions/workflows/run_tests.yml/badge.svg?branch=main)](https://github.com/opencitations/oc_api/actions/workflows/run_tests.yml)
![Coverage](test/coverage-badge.svg)

This repository contains the API service for OpenCitations, allowing users to interact with the OpenCitations datasets through RESTful endpoints.

## Overview

The service provides two main API endpoints:

- **Index endpoint** (`/index/v2`): For querying the OpenCitations Index database
- **Meta endpoint** (`/meta/v1`): For querying the OpenCitations Meta database

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
# Run with default settings
python3 api_oc.py

# Run with static sync enabled
python3 api_oc.py --sync-static

# Run on custom port
python3 api_oc.py --port 8085

# Run with both options
python3 api_oc.py --sync-static --port 8085
```

The application supports the following command line arguments:

- `--sync-static`: Synchronize static files at startup and enable periodic sync (every 30 minutes)
- `--port PORT`: Specify the port to run the application on (default: 8080)

### Production Deployment (Docker)

When running in Docker/Kubernetes, the application uses **Gunicorn** as the WSGI HTTP server for better performance and concurrency handling:

- **Server**: Gunicorn with gevent workers
- **Workers**: 4 concurrent worker processes
- **Worker Type**: gevent (async) for handling thousands of simultaneous requests
- **Timeout**: 1000 seconds (to handle long-running SPARQL queries)
- **Connections per worker**: 1000 simultaneous connections

The Docker container automatically uses Gunicorn and is configured with static sync enabled by default.

> **Note**: The application code automatically detects the execution environment. When run with `python3 api_oc.py`, it uses the built-in web.py server. When run with Gunicorn (as in Docker), it uses the WSGI interface.

### Dockerfile
```dockerfile
# Base image: Python slim for a lightweight container
FROM python:3.11-slim

# Define environment variables with default values
# These can be overridden during container runtime
ENV BASE_URL="api.opencitations.net" \
    LOG_DIR="/mnt/log_dir/oc_api"  \
    SPARQL_ENDPOINT_INDEX="http://qlever-service.default.svc.cluster.local:7011" \
    SPARQL_ENDPOINT_META="http://virtuoso-service.default.svc.cluster.local:8890/sparql" \
    SYNC_ENABLED="true"
  # Uncomment the following lines if you are running the application in a local development environment or any non-Kubernetes deployment scenario.
  #  REDIS_ENABLED="true" \
  #  REDIS_HOST="redis-service.default.svc.cluster.local" \
  #  REDIS_PORT="6379" \
  #  REDIS_DB="0" \
  #  REDIS_PASSWORD="your_redis_password"

# Install system dependencies required for Python package compilation
# We clean up apt cache after installation to reduce image size
RUN apt-get update && \
    apt-get install -y \
    git \
    python3-dev \
    build-essential

# Set the working directory for our application
WORKDIR /website

# Copy the application code from the GitHub repo
RUN git clone --single-branch --branch main https://github.com/opencitations/oc_api .

# Install Python dependencies from requirements.txt + gunicorn and gevent
RUN pip install -r requirements.txt

# Expose the port that our service will listen on
EXPOSE 8080

# Start the application with gunicorn for production
CMD ["gunicorn", \
     "-w", "2", \
     "--worker-class", "gevent", \
     "--worker-connections", "800", \
     "--timeout", "1200", \
     "-b", "0.0.0.0:8080", \
     "api_oc:application"]
```

## Testing

### Running Tests Locally

To run the API tests locally, you'll need to have the test environment set up properly. The tests require a Virtuoso database to be running.

#### Prerequisites

1. Install dependencies using uv:
```bash
   uv sync --dev
```

2. Start the test database:
```bash
   ./test/start_test_db.sh
```

#### Running the Tests

Once the test database is running, you can execute the tests with coverage:
```bash
# Run tests with coverage report
uv run pytest --cov=src --cov-report=term-missing --cov-report=html

# Run only specific test files
uv run pytest test/test_metaapi.py

# Run tests with verbose output
uv run pytest -v
```

#### Stopping the Test Database

After running the tests, stop the test database:
```bash
./test/stop_test_db.sh
```
