#!/bin/bash

set -e

META_CONTAINER="virtuoso-meta-test"
INDEX_CONTAINER="qlever.server.oc-index-test"

for container in "$META_CONTAINER" "$INDEX_CONTAINER"; do
    if docker ps -q -f name="$container" | grep -q .; then
        docker stop "$container"
    fi
    if docker ps -aq -f name="$container" | grep -q .; then
        docker rm "$container"
    fi
done
