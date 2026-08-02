#!/bin/bash
# scripts/reset_db.sh
# Resets the integration database by dropping and recreating it.

set -euo pipefail

# Navigate to the project root
cd "$(dirname "$0")/.."

# Database configuration
DB_NAME=${POSTGRES_INTEGRATION_DB:-banking_integration}
DB_USER=${POSTGRES_INTEGRATION_USER:-integration_user}
DB_HOST=${POSTGRES_INTEGRATION_HOST:-localhost}
DB_PORT=${POSTGRES_INTEGRATION_PORT:-5435}

# Drop and recreate the database
echo "Resetting integration database..."
if ! docker exec -i banking_postgres_integration dropdb -U "$DB_USER" "$DB_NAME" --if-exists; then
    echo "Failed to drop database."
    exit 1
fi

if ! docker exec -i banking_postgres_integration createdb -U "$DB_USER" "$DB_NAME"; then
    echo "Failed to recreate database."
    exit 1
fi

echo "Integration database reset successfully."