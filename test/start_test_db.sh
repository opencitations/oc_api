#!/bin/bash

set -e

CONTAINER_NAME="virtuoso-test-api"
HTTP_PORT="8891"
ISQL_PORT="1112"
DATA_DIR="./test/virtuoso-test-data"
DBA_PASSWORD="test123"
MEMORY="1g"

mkdir -p "$DATA_DIR"

uv run virtuoso-launch \
    --name "$CONTAINER_NAME" \
    --http-port "$HTTP_PORT" \
    --isql-port "$ISQL_PORT" \
    --data-dir "$DATA_DIR" \
    --dba-password "$DBA_PASSWORD" \
    --memory "$MEMORY" \
    --mount-volume "./test/meta_subset:/data/meta_subset" \
    --detach \
    --wait-ready \
    --force-remove

uv run virtuoso-bulk-load -d /data/meta_subset/ --port 1111 --docker-container virtuoso-test-api -k test123 