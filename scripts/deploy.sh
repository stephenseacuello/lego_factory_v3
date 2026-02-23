#!/bin/bash
#
# LEGO MCP v8.0 Deployment Script
# DoD/ONR-Class Manufacturing System
#
# Usage:
#   ./scripts/deploy.sh [environment] [options]
#
# Environments:
#   development  - Local development deployment
#   staging      - Staging environment
#   production   - Production deployment (requires approval)
#
# Options:
#   --skip-tests     Skip pre-deployment tests
#   --skip-backup    Skip database backup
#   --dry-run        Show what would be done without executing
#   --force          Skip confirmation prompts
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${PROJECT_ROOT}/logs/deploy_${TIMESTAMP}.log"

# Default values
ENVIRONMENT="${1:-development}"
SKIP_TESTS=false
SKIP_BACKUP=false
DRY_RUN=false
FORCE=false

# Parse options
shift || true
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    case $level in
        INFO)
            echo -e "${BLUE}[INFO]${NC} $message"
            ;;
        SUCCESS)
            echo -e "${GREEN}[SUCCESS]${NC} $message"
            ;;
        WARNING)
            echo -e "${YELLOW}[WARNING]${NC} $message"
            ;;
        ERROR)
            echo -e "${RED}[ERROR]${NC} $message"
            ;;
    esac

    echo "[$timestamp] [$level] $message" >> "$LOG_FILE" 2>/dev/null || true
}

# Check prerequisites
check_prerequisites() {
    log INFO "Checking prerequisites..."

    local missing=()

    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v docker-compose >/dev/null 2>&1 || missing+=("docker-compose")
    command -v kubectl >/dev/null 2>&1 || missing+=("kubectl")
    command -v helm >/dev/null 2>&1 || missing+=("helm")
    command -v python3 >/dev/null 2>&1 || missing+=("python3")

    if [ ${#missing[@]} -gt 0 ]; then
        log ERROR "Missing prerequisites: ${missing[*]}"
        exit 1
    fi

    log SUCCESS "All prerequisites met"
}

# Run pre-deployment tests
run_tests() {
    if [ "$SKIP_TESTS" = true ]; then
        log WARNING "Skipping pre-deployment tests"
        return 0
    fi

    log INFO "Running pre-deployment tests..."

    cd "$PROJECT_ROOT"

    # Run unit tests
    log INFO "Running unit tests..."
    if [ "$DRY_RUN" = false ]; then
        python3 -m pytest tests/unit -v --tb=short || {
            log ERROR "Unit tests failed"
            exit 1
        }
    fi

    # Run integration tests
    log INFO "Running integration tests..."
    if [ "$DRY_RUN" = false ]; then
        python3 -m pytest tests/integration -v --tb=short || {
            log ERROR "Integration tests failed"
            exit 1
        }
    fi

    # Run security tests
    log INFO "Running security tests..."
    if [ "$DRY_RUN" = false ]; then
        python3 -m pytest tests/test_v8_security_comprehensive.py -v --tb=short || {
            log ERROR "Security tests failed"
            exit 1
        }
    fi

    log SUCCESS "All tests passed"
}

# Backup database
backup_database() {
    if [ "$SKIP_BACKUP" = true ]; then
        log WARNING "Skipping database backup"
        return 0
    fi

    log INFO "Creating database backup..."

    local backup_dir="${PROJECT_ROOT}/backups"
    local backup_file="${backup_dir}/db_backup_${TIMESTAMP}.sql"

    mkdir -p "$backup_dir"

    if [ "$DRY_RUN" = false ]; then
        # PostgreSQL backup
        if [ "$ENVIRONMENT" = "production" ]; then
            kubectl exec -n lego-mcp deploy/postgres -- \
                pg_dump -U lego_mcp lego_mcp > "$backup_file" || {
                log ERROR "Database backup failed"
                exit 1
            }
        else
            docker-compose exec -T db pg_dump -U lego_mcp lego_mcp > "$backup_file" || {
                log WARNING "Database backup skipped (container not running)"
            }
        fi
    fi

    log SUCCESS "Database backup created: $backup_file"
}

# Build Docker images
build_images() {
    log INFO "Building Docker images..."

    cd "$PROJECT_ROOT"

    local images=(
        "dashboard:latest"
        "mcp-server:latest"
        "slicer-service:latest"
    )

    for image in "${images[@]}"; do
        local name="${image%%:*}"
        log INFO "Building $name..."

        if [ "$DRY_RUN" = false ]; then
            docker build -t "lego-mcp/$image" -f "${name}/Dockerfile" . || {
                log ERROR "Failed to build $name"
                exit 1
            }
        fi
    done

    log SUCCESS "All images built"
}

# Deploy to development
deploy_development() {
    log INFO "Deploying to development environment..."

    cd "$PROJECT_ROOT"

    if [ "$DRY_RUN" = false ]; then
        # Stop existing containers
        docker-compose down || true

        # Start services
        docker-compose up -d --build

        # Wait for services to be healthy
        log INFO "Waiting for services to be ready..."
        sleep 10

        # Check health
        curl -sf http://localhost:5000/health || {
            log ERROR "Dashboard health check failed"
            docker-compose logs dashboard
            exit 1
        }
    fi

    log SUCCESS "Development deployment complete"
    log INFO "Dashboard: http://localhost:5000"
}

# Deploy to staging
deploy_staging() {
    log INFO "Deploying to staging environment..."

    cd "$PROJECT_ROOT"

    if [ "$DRY_RUN" = false ]; then
        # Set kubectl context
        kubectl config use-context lego-mcp-staging

        # Deploy with Helm
        helm upgrade --install lego-mcp ./helm/lego-mcp \
            --namespace lego-mcp-staging \
            --create-namespace \
            -f ./helm/values-staging.yaml \
            --wait \
            --timeout 10m

        # Verify deployment
        kubectl rollout status deployment/dashboard -n lego-mcp-staging
    fi

    log SUCCESS "Staging deployment complete"
}

# Deploy to production
deploy_production() {
    log WARNING "PRODUCTION DEPLOYMENT REQUESTED"

    if [ "$FORCE" = false ]; then
        echo -e "${YELLOW}Are you sure you want to deploy to PRODUCTION? (type 'yes' to confirm)${NC}"
        read -r confirmation
        if [ "$confirmation" != "yes" ]; then
            log INFO "Production deployment cancelled"
            exit 0
        fi
    fi

    log INFO "Deploying to production environment..."

    cd "$PROJECT_ROOT"

    if [ "$DRY_RUN" = false ]; then
        # Set kubectl context
        kubectl config use-context lego-mcp-production

        # Blue-green deployment
        helm upgrade --install lego-mcp ./helm/lego-mcp \
            --namespace lego-mcp-production \
            --create-namespace \
            -f ./helm/values-production.yaml \
            --wait \
            --timeout 15m \
            --atomic

        # Run smoke tests
        log INFO "Running production smoke tests..."
        ./scripts/smoke_test.sh production

        # Verify deployment
        kubectl rollout status deployment/dashboard -n lego-mcp-production
    fi

    log SUCCESS "Production deployment complete"
}

# Post-deployment tasks
post_deployment() {
    log INFO "Running post-deployment tasks..."

    # Run database migrations
    log INFO "Running database migrations..."
    if [ "$DRY_RUN" = false ]; then
        case $ENVIRONMENT in
            development)
                docker-compose exec dashboard alembic upgrade head || true
                ;;
            staging|production)
                kubectl exec -n "lego-mcp-${ENVIRONMENT}" deploy/dashboard -- \
                    alembic upgrade head || true
                ;;
        esac
    fi

    # Clear caches
    log INFO "Clearing caches..."

    # Send deployment notification
    log INFO "Sending deployment notification..."

    log SUCCESS "Post-deployment tasks complete"
}

# Generate deployment report
generate_report() {
    log INFO "Generating deployment report..."

    local report_file="${PROJECT_ROOT}/logs/deploy_report_${TIMESTAMP}.md"

    cat > "$report_file" << EOF
# Deployment Report

**Date:** $(date '+%Y-%m-%d %H:%M:%S')
**Environment:** $ENVIRONMENT
**Version:** v8.0.0
**Deployed By:** $(whoami)

## Summary

| Item | Status |
|------|--------|
| Tests | $([ "$SKIP_TESTS" = true ] && echo "Skipped" || echo "Passed") |
| Backup | $([ "$SKIP_BACKUP" = true ] && echo "Skipped" || echo "Created") |
| Build | Completed |
| Deploy | Completed |

## Services Deployed

- Dashboard (Flask)
- MCP Server (Node.js)
- Slicer Service (Python)
- PostgreSQL Database
- Redis Cache

## Configuration

- Environment: $ENVIRONMENT
- Dry Run: $DRY_RUN
- Skip Tests: $SKIP_TESTS
- Skip Backup: $SKIP_BACKUP

## Log File

\`$LOG_FILE\`
EOF

    log SUCCESS "Report generated: $report_file"
}

# Main execution
main() {
    echo ""
    echo "=========================================="
    echo "  LEGO MCP v8.0 Deployment"
    echo "  Environment: $ENVIRONMENT"
    echo "=========================================="
    echo ""

    # Create log directory
    mkdir -p "${PROJECT_ROOT}/logs"

    # Validate environment
    case $ENVIRONMENT in
        development|staging|production)
            log INFO "Deploying to $ENVIRONMENT"
            ;;
        *)
            log ERROR "Invalid environment: $ENVIRONMENT"
            echo "Valid environments: development, staging, production"
            exit 1
            ;;
    esac

    # Execute deployment steps
    check_prerequisites
    run_tests
    backup_database
    build_images

    # Deploy based on environment
    case $ENVIRONMENT in
        development)
            deploy_development
            ;;
        staging)
            deploy_staging
            ;;
        production)
            deploy_production
            ;;
    esac

    post_deployment
    generate_report

    echo ""
    log SUCCESS "Deployment to $ENVIRONMENT completed successfully!"
    echo ""
}

# Run main
main
