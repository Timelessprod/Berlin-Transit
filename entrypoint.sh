#!/usr/bin/env bash

set -ex

# Run migrations of the DB if needed
alembic upgrade head
