#!/usr/bin/env bash

set -ex

# Always shutdown containers
function down {
    docker compose down
}

trap down EXIT
down

# Build images
docker compose build

# Start containers
docker compose up
