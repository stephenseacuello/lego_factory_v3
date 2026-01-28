# =============================================================================
# LEGO Factory v3 - Makefile
# =============================================================================
# Build, test, and development automation for the LEGO Factory platform.
#
# Usage:
#   make help          - Show all available commands
#   make test          - Run all tests
#   make coverage      - Run tests with coverage report
# =============================================================================

.PHONY: help install dev-install test test-unit test-integration test-e2e \
        test-fast test-slow coverage coverage-html lint format typecheck \
        clean clean-pyc clean-test docker-test

# Default Python executable
PYTHON ?= python3
PIP ?= pip3

# Pytest configuration
PYTEST_OPTS ?= -v
PYTEST_COV_OPTS ?= --cov=app --cov=api --cov=services --cov=models

# =============================================================================
# HELP
# =============================================================================

help:
	@echo "LEGO Factory v3 - Available Commands"
	@echo "====================================="
	@echo ""
	@echo "Installation:"
	@echo "  make install        Install production dependencies"
	@echo "  make dev-install    Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make test-e2e       Run end-to-end tests"
	@echo "  make test-fast      Run fast tests (exclude slow)"
	@echo "  make test-slow      Run slow tests only"
	@echo "  make test-smoke     Run smoke tests"
	@echo "  make test-parallel  Run tests in parallel"
	@echo ""
	@echo "Coverage:"
	@echo "  make coverage       Run tests with coverage report"
	@echo "  make coverage-html  Generate HTML coverage report"
	@echo "  make coverage-xml   Generate XML coverage report (for CI)"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run linters (ruff, pylint)"
	@echo "  make format         Format code (black, isort)"
	@echo "  make typecheck      Run type checking (mypy)"
	@echo "  make check          Run all quality checks"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Remove all generated files"
	@echo "  make clean-pyc      Remove Python cache files"
	@echo "  make clean-test     Remove test artifacts"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-test    Run tests in Docker container"
	@echo ""

# =============================================================================
# INSTALLATION
# =============================================================================

install:
	$(PIP) install -r requirements.txt

dev-install:
	$(PIP) install -e ".[dev,test]"

# =============================================================================
# TESTING
# =============================================================================

test:
	@echo "Running all tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) tests/

test-unit:
	@echo "Running unit tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "unit" tests/unit/

test-integration:
	@echo "Running integration tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "integration" tests/integration/

test-e2e:
	@echo "Running end-to-end tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "e2e" tests/e2e/

test-fast:
	@echo "Running fast tests (excluding slow tests)..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "not slow" tests/

test-slow:
	@echo "Running slow tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "slow" tests/

test-smoke:
	@echo "Running smoke tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "smoke" tests/

test-parallel:
	@echo "Running tests in parallel..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -n auto tests/

test-scada:
	@echo "Running SCADA tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "scada" tests/

test-mes:
	@echo "Running MES tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "mes" tests/

test-erp:
	@echo "Running ERP tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "erp" tests/

test-security:
	@echo "Running security tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "security" tests/

test-performance:
	@echo "Running performance tests..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) -m "performance" tests/performance/

# Run specific test file
test-file:
	@echo "Running tests in $(FILE)..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) $(FILE)

# =============================================================================
# COVERAGE
# =============================================================================

coverage:
	@echo "Running tests with coverage..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) $(PYTEST_COV_OPTS) \
		--cov-report=term-missing \
		--cov-fail-under=70 \
		tests/

coverage-html:
	@echo "Generating HTML coverage report..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) $(PYTEST_COV_OPTS) \
		--cov-report=html \
		--cov-report=term-missing \
		tests/
	@echo "Coverage report generated at htmlcov/index.html"

coverage-xml:
	@echo "Generating XML coverage report..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) $(PYTEST_COV_OPTS) \
		--cov-report=xml \
		--cov-report=term-missing \
		tests/
	@echo "Coverage report generated at coverage.xml"

coverage-json:
	@echo "Generating JSON coverage report..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) $(PYTEST_COV_OPTS) \
		--cov-report=json \
		--cov-report=term-missing \
		tests/
	@echo "Coverage report generated at coverage.json"

coverage-all:
	@echo "Generating all coverage reports..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) $(PYTEST_COV_OPTS) \
		--cov-report=html \
		--cov-report=xml \
		--cov-report=json \
		--cov-report=term-missing \
		--cov-fail-under=70 \
		tests/

# =============================================================================
# CODE QUALITY
# =============================================================================

lint:
	@echo "Running linters..."
	-$(PYTHON) -m ruff check app/ api/ services/ models/
	-$(PYTHON) -m pylint app/ api/ services/ models/ --exit-zero

format:
	@echo "Formatting code..."
	$(PYTHON) -m black app/ api/ services/ models/ tests/
	$(PYTHON) -m isort app/ api/ services/ models/ tests/

format-check:
	@echo "Checking code formatting..."
	$(PYTHON) -m black --check app/ api/ services/ models/ tests/
	$(PYTHON) -m isort --check-only app/ api/ services/ models/ tests/

typecheck:
	@echo "Running type checking..."
	$(PYTHON) -m mypy app/ api/ services/ models/ --ignore-missing-imports

check: lint format-check typecheck
	@echo "All quality checks completed."

# =============================================================================
# CLEANUP
# =============================================================================

clean: clean-pyc clean-test
	@echo "Cleanup complete."

clean-pyc:
	@echo "Removing Python cache files..."
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type f -name '*.pyo' -delete 2>/dev/null || true
	find . -type f -name '*~' -delete 2>/dev/null || true

clean-test:
	@echo "Removing test artifacts..."
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf .coverage 2>/dev/null || true
	rm -rf coverage.xml 2>/dev/null || true
	rm -rf coverage.json 2>/dev/null || true
	rm -rf .pytest_cache/ 2>/dev/null || true
	rm -rf tests/logs/*.log 2>/dev/null || true
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# DOCKER
# =============================================================================

docker-test:
	@echo "Running tests in Docker..."
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit
	docker-compose -f docker-compose.test.yml down

# =============================================================================
# CI/CD HELPERS
# =============================================================================

ci-test:
	@echo "Running CI test suite..."
	$(PYTHON) -m pytest $(PYTEST_OPTS) $(PYTEST_COV_OPTS) \
		--cov-report=xml \
		--cov-report=term-missing \
		--cov-fail-under=70 \
		--junitxml=test-results.xml \
		-m "not slow and not e2e" \
		tests/

ci-lint:
	@echo "Running CI lint checks..."
	$(PYTHON) -m ruff check app/ api/ services/ models/ --output-format=github
	$(PYTHON) -m black --check app/ api/ services/ models/ tests/

# =============================================================================
# DEVELOPMENT HELPERS
# =============================================================================

# Watch for changes and run tests
test-watch:
	@echo "Watching for changes..."
	$(PYTHON) -m pytest_watch -- $(PYTEST_OPTS) tests/

# Run tests that match a pattern
test-match:
	@echo "Running tests matching pattern: $(PATTERN)"
	$(PYTHON) -m pytest $(PYTEST_OPTS) -k "$(PATTERN)" tests/

# Debug a specific test
test-debug:
	@echo "Running test in debug mode: $(TEST)"
	$(PYTHON) -m pytest $(PYTEST_OPTS) --pdb -x $(TEST)
