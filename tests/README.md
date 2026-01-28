# LEGO Factory v3 - Test Suite

This document describes the test organization, how to run tests, and coverage requirements for the LEGO Factory v3 application.

## Quick Start

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run tests with coverage report
make coverage
```

## Test Organization

```
tests/
├── __init__.py
├── conftest.py              # Global fixtures and configuration
├── factories.py             # Factory Boy factories for test data
├── README.md                # This file
│
├── unit/                    # Unit tests (fast, isolated)
│   ├── __init__.py
│   ├── api/                 # API endpoint unit tests
│   │   └── __init__.py
│   ├── models/              # Model unit tests
│   │   ├── __init__.py
│   │   ├── test_lego_models.py
│   │   ├── test_mes_models.py
│   │   ├── test_ml_models.py
│   │   └── test_scada_models.py
│   └── services/            # Service unit tests
│       ├── __init__.py
│       ├── test_anomaly_detection.py
│       ├── test_auth_service.py
│       ├── test_inventory_service.py
│       ├── test_machine_service.py
│       └── test_work_order_service.py
│
├── integration/             # Integration tests (require database)
│   ├── __init__.py
│   ├── conftest.py          # Integration-specific fixtures
│   ├── test_anomaly_alarm_integration.py
│   ├── test_api_endpoints.py
│   ├── test_auth_api.py
│   ├── test_mes_api.py
│   └── test_scada_api.py
│
├── e2e/                     # End-to-end tests (full system)
│   └── __init__.py
│
├── performance/             # Performance tests
│   └── test_historian_performance.py
│
├── fixtures/                # Shared test fixtures (data files)
│
└── logs/                    # Test execution logs
```

## Test Categories

Tests are organized using pytest markers:

| Marker | Description | Usage |
|--------|-------------|-------|
| `unit` | Fast, isolated tests without external dependencies | `pytest -m unit` |
| `integration` | Tests requiring database or external services | `pytest -m integration` |
| `e2e` | End-to-end tests requiring full system | `pytest -m e2e` |
| `slow` | Long-running tests (excluded by default) | `pytest -m slow` |
| `smoke` | Quick sanity checks for basic functionality | `pytest -m smoke` |
| `regression` | Tests for previously fixed bugs | `pytest -m regression` |
| `security` | Security-related tests | `pytest -m security` |
| `performance` | Performance and load tests | `pytest -m performance` |
| `database` | Tests requiring database access | `pytest -m database` |
| `api` | API endpoint tests | `pytest -m api` |
| `scada` | SCADA-specific tests | `pytest -m scada` |
| `mes` | MES-specific tests | `pytest -m mes` |
| `erp` | ERP-specific tests | `pytest -m erp` |
| `ml` | Machine learning model tests | `pytest -m ml` |

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/services/test_auth_service.py

# Run specific test class
pytest tests/unit/services/test_auth_service.py::TestAuthService

# Run specific test function
pytest tests/unit/services/test_auth_service.py::TestAuthService::test_login_success
```

### Using Markers

```bash
# Run only unit tests
pytest -m unit

# Run integration tests
pytest -m integration

# Run everything except slow tests
pytest -m "not slow"

# Run unit and integration tests
pytest -m "unit or integration"

# Run SCADA-related tests
pytest -m scada

# Run API tests that are not slow
pytest -m "api and not slow"
```

### Parallel Execution

```bash
# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run with specific number of workers
pytest -n 4
```

### Coverage Reports

```bash
# Run with coverage
pytest --cov=app --cov=api --cov=services --cov=models

# Generate HTML coverage report
pytest --cov=app --cov=api --cov=services --cov=models --cov-report=html

# Generate terminal report with missing lines
pytest --cov=app --cov=api --cov=services --cov=models --cov-report=term-missing

# Fail if coverage is below threshold
pytest --cov=app --cov=api --cov=services --cov=models --cov-fail-under=70
```

## Coverage Requirements

### Minimum Coverage

The project requires a **minimum 70% code coverage** to pass CI checks.

### Coverage Configuration

Coverage is configured in `pyproject.toml`:

```toml
[tool.coverage.run]
branch = true
source = ["app", "api", "services", "models"]
omit = [
    "*/tests/*",
    "*/__pycache__/*",
    "*/migrations/*",
    "services/flask_cnc_legacy/*",
    "services/advanced/*",
]

[tool.coverage.report]
fail_under = 70
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

### Excluded from Coverage

- Test files (`*/tests/*`)
- Cache directories (`*/__pycache__/*`)
- Database migrations (`*/migrations/*`)
- Legacy code (`services/flask_cnc_legacy/*`)
- Experimental code (`services/advanced/*`)

### Coverage Best Practices

1. Write tests for all new features
2. Aim for 80%+ coverage on critical paths
3. Use `# pragma: no cover` sparingly for unreachable code
4. Focus on meaningful tests over coverage percentage

## Writing Tests

### Test File Naming

- Test files must start with `test_` or end with `_test.py`
- Test classes must start with `Test`
- Test functions must start with `test_`

### Using Fixtures

Fixtures are defined in `conftest.py` files. Common fixtures include:

```python
# Database session (transaction-isolated)
def test_create_item(db_session):
    item = Item(name="Test")
    db_session.add(item)
    db_session.flush()
    assert item.id is not None

# Flask test client
def test_api_endpoint(client):
    response = client.get('/health')
    assert response.status_code == 200

# Mock session for unit tests
def test_service_logic(mock_session):
    service = MyService(mock_session)
    result = service.process()
    assert result is True

# Sample data fixtures
def test_tag_creation(sample_tag_data):
    tag = Tag(**sample_tag_data)
    assert tag.tag_id == 'test_tag_001'
```

### Using Markers

```python
import pytest

@pytest.mark.unit
def test_fast_function():
    """Fast unit test."""
    assert True

@pytest.mark.integration
@pytest.mark.database
def test_database_operation(db_session):
    """Integration test requiring database."""
    pass

@pytest.mark.slow
def test_long_running_operation():
    """Slow test - excluded by default."""
    pass

@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_doubling(input, expected):
    """Parametrized test."""
    assert input * 2 == expected
```

### Using Factories

```python
from tests.factories import TagFactory, AlarmFactory

def test_alarm_trigger(db_session):
    # Create test data using factories
    tag = TagFactory(value=100.0)
    alarm = AlarmFactory(tag=tag, high_limit=80.0)

    # Test alarm logic
    assert alarm.is_triggered()
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    """Async test using pytest-asyncio."""
    result = await some_async_function()
    assert result is not None
```

## Adding New Tests

### Step-by-Step Guide

1. **Determine test type** (unit, integration, e2e)
2. **Create test file** in appropriate directory:
   - Unit tests: `tests/unit/<module>/test_<feature>.py`
   - Integration tests: `tests/integration/test_<feature>.py`
   - E2E tests: `tests/e2e/test_<scenario>.py`
3. **Add appropriate markers** to test functions
4. **Use fixtures** for common setup/teardown
5. **Run tests** to verify they pass
6. **Check coverage** to ensure new code is tested

### Example: Adding a New Service Test

```python
# tests/unit/services/test_new_service.py
"""Tests for the new service module."""

import pytest
from unittest.mock import MagicMock, patch


class TestNewService:
    """Test suite for NewService."""

    @pytest.mark.unit
    def test_initialization(self, mock_session):
        """Test service initializes correctly."""
        from services.new_service import NewService

        service = NewService(mock_session)
        assert service is not None

    @pytest.mark.unit
    def test_process_valid_input(self, mock_session):
        """Test processing with valid input."""
        from services.new_service import NewService

        service = NewService(mock_session)
        result = service.process({"key": "value"})

        assert result.success is True

    @pytest.mark.unit
    def test_process_invalid_input(self, mock_session):
        """Test processing with invalid input raises error."""
        from services.new_service import NewService

        service = NewService(mock_session)

        with pytest.raises(ValueError):
            service.process(None)
```

## Troubleshooting

### Common Issues

**Tests not discovered:**
- Ensure file names start with `test_` or end with `_test.py`
- Ensure test functions start with `test_`
- Check that `__init__.py` exists in test directories

**Import errors:**
- Verify project root is in Python path
- Check `conftest.py` adds project root to `sys.path`

**Database connection errors:**
- Integration tests require `DATABASE_URL` environment variable
- Unit tests should use `mock_session` fixture

**Timeout errors:**
- Increase timeout: `pytest --timeout=60`
- Mark slow tests: `@pytest.mark.slow`

### Debug Mode

```bash
# Run with full traceback
pytest --tb=long

# Run with debugger on failure
pytest --pdb

# Run with verbose logging
pytest --log-cli-level=DEBUG

# Run single test with maximum verbosity
pytest -vvv tests/unit/test_specific.py::test_function
```

## Continuous Integration

Tests are automatically run in CI/CD pipeline with:

1. All unit tests
2. All integration tests
3. Coverage threshold enforcement (70%)
4. Linting and type checking

See `.github/workflows/` for CI configuration details.
