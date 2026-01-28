#!/bin/bash
# LEGO Factory v3 - Docker Entrypoint Script
# ==========================================
# This script handles database initialization before starting the application.

set -e

# Configuration
MAX_RETRIES=${DB_MAX_RETRIES:-30}
RETRY_INTERVAL=${DB_RETRY_INTERVAL:-2}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Wait for PostgreSQL to be ready
wait_for_db() {
    log_info "Waiting for PostgreSQL to be ready..."

    retries=0
    until python -c "
import sys
import os
from sqlalchemy import create_engine
try:
    engine = create_engine(os.environ.get('DATABASE_URL'))
    conn = engine.connect()
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f'Database not ready: {e}')
    sys.exit(1)
" 2>/dev/null; do
        retries=$((retries + 1))
        if [ $retries -ge $MAX_RETRIES ]; then
            log_error "Database did not become ready in time (${MAX_RETRIES} attempts)"
            exit 1
        fi
        log_warn "Database not ready, retrying in ${RETRY_INTERVAL}s... (attempt $retries/$MAX_RETRIES)"
        sleep $RETRY_INTERVAL
    done

    log_info "Database is ready!"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."

    if [ -f "alembic.ini" ]; then
        # Run Alembic migrations
        alembic upgrade head
        if [ $? -eq 0 ]; then
            log_info "Migrations completed successfully!"
        else
            log_error "Migration failed!"
            exit 1
        fi
    else
        log_warn "No alembic.ini found, skipping migrations"
    fi
}

# Run seed scripts if SEED_DATABASE is set
run_seeds() {
    if [ "${SEED_DATABASE:-false}" = "true" ]; then
        log_info "Seeding database..."

        if [ -f "database/seeds/seed_all.py" ]; then
            python database/seeds/seed_all.py
            if [ $? -eq 0 ]; then
                log_info "Database seeding completed!"
            else
                log_warn "Database seeding failed, continuing anyway..."
            fi
        else
            log_warn "No seed_all.py found, skipping seeding"
        fi
    fi
}

# Main entrypoint
main() {
    log_info "LEGO Factory v3 - Starting up..."

    # Skip database initialization if SKIP_DB_INIT is set
    if [ "${SKIP_DB_INIT:-false}" != "true" ]; then
        wait_for_db
        run_migrations
        run_seeds
    else
        log_warn "Skipping database initialization (SKIP_DB_INIT=true)"
    fi

    log_info "Starting application..."

    # Execute the command passed to the container
    exec "$@"
}

# Run main
main "$@"
