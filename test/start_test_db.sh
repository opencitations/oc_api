#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

wait_for_ready() {
    local port="$1"
    local name="$2"
    local max_attempts=30
    for i in $(seq 1 $max_attempts); do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" 2>/dev/null | grep -q "^[2-4]"; then
            echo "$name is ready on port $port"
            return 0
        fi
        sleep 1
    done
    echo "ERROR: $name did not become ready on port $port within ${max_attempts}s"
    return 1
}

# --- Meta: Virtuoso ---
META_CONTAINER="virtuoso-meta-test"
META_PORT="8891"
META_ISQL_PORT="1112"
META_DATA_DIR="$SCRIPT_DIR/virtuoso-meta-data"

docker rm -f "$META_CONTAINER" 2>/dev/null || true
docker run -d \
    --name "$META_CONTAINER" \
    -p "$META_PORT:8890" \
    -p "$META_ISQL_PORT:1111" \
    -e DBA_PASSWORD=dba \
    -e VIRT_Parameters_DirsAllowed=/ \
    -v "$META_DATA_DIR:/data" \
    openlink/virtuoso-opensource-7

echo "Waiting for Virtuoso to start..."
until docker exec "$META_CONTAINER" isql 1111 dba dba exec="SELECT 1;" > /dev/null 2>&1; do
    sleep 1
done
echo "Virtuoso is ready"

docker exec "$META_CONTAINER" isql 1111 dba dba \
    exec="ld_dir('/data', 'meta_subset.nq', ''); rdf_loader_run(); checkpoint;"

echo "Meta data loaded into Virtuoso"

# --- Index: QLever ---
INDEX_NAME="oc-index-test"
INDEX_PORT="7011"
INDEX_DATA_DIR="$SCRIPT_DIR/qlever-index-data"
INDEX_CONTAINER="qlever.server.$INDEX_NAME"

cd "$INDEX_DATA_DIR"
uv run --project "$PROJECT_DIR" qlever index \
    --name "$INDEX_NAME" \
    --format nt \
    --input-files "index_subset.nt" \
    --cat-input-files "cat index_subset.nt" \
    --overwrite-existing

docker rm -f "$INDEX_CONTAINER" 2>/dev/null || true
docker run -d --restart=unless-stopped \
    -u "$(id -u):$(id -g)" \
    -v /etc/localtime:/etc/localtime:ro \
    --mount type=bind,src="$(pwd)",target=/index \
    -p "$INDEX_PORT:$INDEX_PORT" \
    -w /index \
    --name "$INDEX_CONTAINER" \
    --init --entrypoint bash \
    docker.io/adfreiburg/qlever \
    -c "qlever-server -i $INDEX_NAME -j 8 -p $INDEX_PORT -m 5G -c 2G -e 1G -k 200 -s 30s > $INDEX_NAME.server-log.txt 2>&1"

wait_for_ready "$INDEX_PORT" "$INDEX_NAME"
