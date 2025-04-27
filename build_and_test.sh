#!/usr/bin/env bash

# Always shutdown containers
function down {
    docker compose down
}

trap down EXIT
down

# Build images
docker compose build

# Start containers in the background
docker compose up -d postgres

# Waiting for the postgres service to be ready
until docker compose exec postgres pg_isready -U postgres > /dev/null 2>&1; do
  sleep 1
done

# Run tests
docker compose run --rm --entrypoint "" app bash -c "alembic upgrade head"
