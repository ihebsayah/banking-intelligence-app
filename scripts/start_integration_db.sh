#!/bin/bash
# scripts/start_integration_db.sh
# Starts the integration PostgreSQL database using Docker Compose.

set -euo pipefail

# Navigate to the project root
cd "$(dirname "$0")/.."

# Start the integration database
if ! docker compose -f docker-compose.integration.yml up -d postgres-integration; then
    echo "Failed to start integration database."
    exit 1
fi

# Wait for the database to be healthy
echo "Waiting for integration database to be healthy..."
for i in {1..30}; do
    if docker inspect --format='{{json .State.Health.Status}}' banking_postgres_integration | grep -q '"healthy"'; then
        echo "Integration database is healthy."
        exit 0
    fi
    sleep 2
    echo -n "."
done

echo "Integration database did not become healthy in time."
exit 1