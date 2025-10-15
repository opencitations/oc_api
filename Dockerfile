# Base image: Python slim for a lightweight container
FROM python:3.11-slim

# Define environment variables with default values
# These can be overridden during container runtime
ENV BASE_URL="api.opencitations.net" \
    LOG_DIR="/mnt/log_dir/oc_api"  \
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
    apt-get clean

# Set the working directory for our application
WORKDIR /website

# Copy the application code from the repository to the container
# The code is already present in the repo, no need to git clone
COPY . .

# Install Python dependencies from requirements.txt + gunicorn and gevent
RUN pip install -r requirements.txt && \
    pip install gunicorn gevent

# Expose the port that our service will listen on
EXPOSE 8080

# Start the application with gunicorn instead of python directly
CMD ["gunicorn", \
     "-w", "2", \
     "--worker-class", "gevent", \
     "--worker-connections", "500", \
     "--timeout", "1000", \
     "-b", "0.0.0.0:8080", \
     "api_oc:application"]