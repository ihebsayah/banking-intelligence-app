#!/bin/bash
# scripts/stop_integration_db.sh
# Stops the integration PostgreSQL database and removes its container.

set -euo pipefail

# Navigate to the project root
cd "$(dirname "$0")/.."

# Stop the integration database
if ! docker compose -f docker-compose.integration.yml down; then
    echo "Failed to stop integration database."
    exit 1
fi

echo "Integration database stopped successfully."