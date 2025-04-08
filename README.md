# OpenCitations SPARQL Service

This repository contains the SPARQL service for OpenCitations, allowing users to query the OpenCitations datasets using SPARQL.

## Overview

The service provides two main SPARQL endpoints:

- **Index endpoint** (`/index`): For querying the OpenCitations Index database
- **Meta endpoint** (`/meta`): For querying the OpenCitations Meta database

## Features

- SPARQL query interface powered by YASQE/YASR
- Support for both GET and POST SPARQL queries 
- SPARQL Update queries are not permitted
- Request logging
- Docker deployment ready

## Configuration

### Environment Variables

The service requires the following environment variables. These values take precedence over the ones defined in `conf.json`:

- `SPARQL_BASE_URL`: Base URL for the SPARQL endpoint
- `SPARQL_ENDPOINT_INDEX`: URL for the index SPARQL endpoint
- `SPARQL_ENDPOINT_META`: URL for the meta SPARQL endpoint
- `SYNC_ENABLED`: Enable/disable static files synchronization (default: false)

For instance:

```env
SPARQL_BASE_URL=sparql.opencitations.net
SPARQL_ENDPOINT_INDEX=http://qlever-service.default.svc.cluster.local:7011  
SPARQL_ENDPOINT_META=http://virtuoso-service.default.svc.cluster.local:8890/sparql
SYNC_ENABLED=true
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

The application supports the following command line arguments:

- `--sync-static`: Synchronize static files at startup and enable periodic sync (every 30 minutes)
- `--port PORT`: Specify the port to run the application on (default: 8080)

Examples:
```bash
# Run with default settings
python3 sparql_oc.py

# Run with static sync enabled
python3 sparql_oc.py --sync-static

# Run on custom port
python3 sparql_oc.py --port 8085

# Run with both options
python3 sparql_oc.py --sync-static --port 8085
```

The Docker container is configured to run with `--sync-static` enabled by default.

### Dockerfile

You can change these variables in the Dockerfile:

```dockerfile
# Base image: Python slim for a lightweight container
FROM python:3.11-slim

# Define environment variables with default values
# These can be overridden during container runtime
ENV SPARQL_BASE_URL="sparql.opencitations.net" \
    SPARQL_ENDPOINT_INDEX="http://qlever-service.default.svc.cluster.local:7011" \
    SPARQL_ENDPOINT_META="http://virtuoso-service.default.svc.cluster.local:8890/sparql" \
    SYNC_ENABLED="true"

# Install system dependencies required for Python package compilation
# We clean up apt cache after installation to reduce image size
RUN apt-get update && \
    apt-get install -y \
    git \
    python3-dev \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory for our application
WORKDIR /website

# Clone the specific branch (sparql) from the repository
# The dot at the end means clone into current directory
RUN git clone --single-branch --branch main https://github.com/opencitations/oc_sparql .

# Install Python dependencies from requirements.txt
RUN pip install -r requirements.txt

# Expose the port that our service will listen on
EXPOSE 8080

# Start the application
# The Python script will now read environment variables for SPARQL configurations
CMD ["python3", "sparql_oc.py"]