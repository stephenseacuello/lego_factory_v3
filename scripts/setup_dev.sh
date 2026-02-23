#!/bin/bash
# =============================================================================
# LEGO MCP v8.0 Development Environment Setup
# DoD/ONR-Class Manufacturing System
# =============================================================================
#
# This script sets up a complete development environment.
#
# Usage:
#   ./scripts/setup_dev.sh [options]
#
# Options:
#   --skip-docker    Skip Docker setup
#   --skip-venv      Skip virtual environment setup
#   --skip-hooks     Skip pre-commit hooks installation
#   --clean          Clean existing setup before installing
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_VERSION="3.11"
NODE_VERSION="20"

# Options
SKIP_DOCKER=false
SKIP_VENV=false
SKIP_HOOKS=false
CLEAN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-docker) SKIP_DOCKER=true; shift ;;
        --skip-venv) SKIP_VENV=true; shift ;;
        --skip-hooks) SKIP_HOOKS=true; shift ;;
        --clean) CLEAN=true; shift ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
    esac
done

# Logging
log() {
    local level=$1
    shift
    case $level in
        INFO) echo -e "${BLUE}[INFO]${NC} $*" ;;
        SUCCESS) echo -e "${GREEN}[SUCCESS]${NC} $*" ;;
        WARNING) echo -e "${YELLOW}[WARNING]${NC} $*" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $*" ;;
    esac
}

# Check command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log ERROR "$1 is not installed"
        return 1
    fi
    return 0
}

# Header
echo ""
echo "=========================================="
echo "  LEGO MCP v8.0 Development Setup"
echo "=========================================="
echo ""

cd "$PROJECT_ROOT"

# =============================================================================
# Prerequisites Check
# =============================================================================

log INFO "Checking prerequisites..."

MISSING=()

check_command python3 || MISSING+=("python3")
check_command pip3 || MISSING+=("pip3")
check_command git || MISSING+=("git")

if [ "$SKIP_DOCKER" = false ]; then
    check_command docker || MISSING+=("docker")
    check_command docker-compose || MISSING+=("docker-compose")
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    log ERROR "Missing prerequisites: ${MISSING[*]}"
    echo ""
    echo "Please install missing tools and try again."
    exit 1
fi

log SUCCESS "All prerequisites met"

# =============================================================================
# Clean (if requested)
# =============================================================================

if [ "$CLEAN" = true ]; then
    log INFO "Cleaning existing setup..."

    # Remove virtual environment
    rm -rf "$PROJECT_ROOT/venv"

    # Remove node_modules
    rm -rf "$PROJECT_ROOT/mcp-server/node_modules"

    # Remove Python cache
    find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true

    # Remove Docker volumes (careful!)
    if [ "$SKIP_DOCKER" = false ]; then
        docker-compose down -v 2>/dev/null || true
    fi

    log SUCCESS "Cleanup complete"
fi

# =============================================================================
# Python Virtual Environment
# =============================================================================

if [ "$SKIP_VENV" = false ]; then
    log INFO "Setting up Python virtual environment..."

    # Create venv if not exists
    if [ ! -d "$PROJECT_ROOT/venv" ]; then
        python3 -m venv "$PROJECT_ROOT/venv"
        log SUCCESS "Virtual environment created"
    fi

    # Activate venv
    source "$PROJECT_ROOT/venv/bin/activate"

    # Upgrade pip
    pip install --upgrade pip wheel setuptools

    # Install main requirements
    log INFO "Installing Python dependencies..."
    pip install -r requirements.txt

    # Install development requirements
    if [ -f "requirements-dev.txt" ]; then
        pip install -r requirements-dev.txt
    fi

    # Install test requirements
    if [ -f "tests/requirements-test.txt" ]; then
        pip install -r tests/requirements-test.txt
    fi

    log SUCCESS "Python dependencies installed"
fi

# =============================================================================
# Node.js Dependencies (MCP Server)
# =============================================================================

if [ -d "$PROJECT_ROOT/mcp-server" ]; then
    log INFO "Setting up MCP Server dependencies..."

    cd "$PROJECT_ROOT/mcp-server"

    if check_command npm; then
        npm install
        log SUCCESS "Node.js dependencies installed"
    else
        log WARNING "npm not found, skipping MCP Server setup"
    fi

    cd "$PROJECT_ROOT"
fi

# =============================================================================
# Pre-commit Hooks
# =============================================================================

if [ "$SKIP_HOOKS" = false ]; then
    log INFO "Setting up pre-commit hooks..."

    if [ -f ".pre-commit-config.yaml" ]; then
        # Ensure we're in venv
        if [ -d "$PROJECT_ROOT/venv" ]; then
            source "$PROJECT_ROOT/venv/bin/activate"
        fi

        # Install pre-commit if not present
        pip install pre-commit

        # Install hooks
        pre-commit install
        pre-commit install --hook-type commit-msg

        log SUCCESS "Pre-commit hooks installed"
    else
        log WARNING "No .pre-commit-config.yaml found"
    fi
fi

# =============================================================================
# Environment Configuration
# =============================================================================

log INFO "Setting up environment configuration..."

if [ ! -f "$PROJECT_ROOT/.env" ]; then
    if [ -f "$PROJECT_ROOT/config/examples/development.env.example" ]; then
        cp "$PROJECT_ROOT/config/examples/development.env.example" "$PROJECT_ROOT/.env"
        log SUCCESS "Created .env from example"
        log WARNING "Please edit .env with your configuration"
    else
        log WARNING "No .env example found"
    fi
else
    log INFO ".env already exists"
fi

# =============================================================================
# Docker Services
# =============================================================================

if [ "$SKIP_DOCKER" = false ]; then
    log INFO "Starting Docker services..."

    # Pull images
    docker-compose pull

    # Start services
    docker-compose up -d

    # Wait for services
    log INFO "Waiting for services to be ready..."
    sleep 10

    # Check health
    if curl -sf http://localhost:5432 > /dev/null 2>&1 || docker-compose exec -T db pg_isready -U lego_mcp > /dev/null 2>&1; then
        log SUCCESS "PostgreSQL is ready"
    else
        log WARNING "PostgreSQL may not be ready yet"
    fi

    if curl -sf http://localhost:6379 > /dev/null 2>&1 || docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        log SUCCESS "Redis is ready"
    else
        log WARNING "Redis may not be ready yet"
    fi

    log SUCCESS "Docker services started"
fi

# =============================================================================
# Database Setup
# =============================================================================

log INFO "Setting up database..."

if [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Run migrations
if [ -f "$PROJECT_ROOT/alembic.ini" ]; then
    cd "$PROJECT_ROOT"
    alembic upgrade head 2>/dev/null || log WARNING "Could not run migrations (database may not be ready)"
fi

# =============================================================================
# Create Required Directories
# =============================================================================

log INFO "Creating required directories..."

mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/output"
mkdir -p "$PROJECT_ROOT/backups"
mkdir -p "$PROJECT_ROOT/data"

log SUCCESS "Directories created"

# =============================================================================
# Verify Installation
# =============================================================================

log INFO "Verifying installation..."

ERRORS=0

# Check Python imports
python3 -c "import flask; import redis; import sqlalchemy" 2>/dev/null || {
    log ERROR "Python dependencies not properly installed"
    ERRORS=$((ERRORS + 1))
}

# Check pre-commit
if [ "$SKIP_HOOKS" = false ]; then
    pre-commit --version > /dev/null 2>&1 || {
        log ERROR "Pre-commit not properly installed"
        ERRORS=$((ERRORS + 1))
    }
fi

# Check Docker (if not skipped)
if [ "$SKIP_DOCKER" = false ]; then
    docker-compose ps > /dev/null 2>&1 || {
        log ERROR "Docker services not running"
        ERRORS=$((ERRORS + 1))
    }
fi

if [ $ERRORS -eq 0 ]; then
    log SUCCESS "Installation verified"
else
    log WARNING "Installation completed with $ERRORS warning(s)"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Activate virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Edit configuration:"
echo "     nano .env"
echo ""
echo "  3. Start development server:"
echo "     cd dashboard && python app.py"
echo ""
echo "  4. Run tests:"
echo "     pytest tests/ -v"
echo ""
echo "  5. View dashboard:"
echo "     http://localhost:5000"
echo ""

if [ "$SKIP_DOCKER" = false ]; then
    echo "Docker services:"
    docker-compose ps
    echo ""
fi

log SUCCESS "Development environment ready!"
