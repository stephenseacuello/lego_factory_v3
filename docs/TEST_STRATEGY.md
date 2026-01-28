# Test Strategy

This document outlines the testing approach for LEGO Factory v3, covering the test pyramid, patterns, coverage targets, and best practices.

## Test Pyramid

```
                    /\
                   /  \
                  /E2E \        <- Few, slow, valuable
                 /------\
                /        \
               /Integration\    <- Some, moderate speed
              /--------------\
             /                \
            /    Unit Tests    \  <- Many, fast, focused
           /--------------------\
```

| Level | Count | Speed | Scope |
|-------|-------|-------|-------|
| Unit | ~500+ | < 1s each | Single function/class |
| Integration | ~50+ | < 5s each | Multiple components |
| E2E | ~20+ | < 30s each | Full workflows |

## Coverage Targets

| Module | Target | Critical Paths |
|--------|--------|----------------|
| `services/erp/` | 80%+ | MRP explosion, BOM recursion |
| `services/mes/` | 80%+ | Scheduling algorithms, OEE calculation |
| `services/qms/` | 80%+ | E-signature workflow, NCR lifecycle |
| `services/cmms/` | 80%+ | PM generation, work order completion |
| `services/scada/` | 75%+ | Tag processing, alarm handling |
| `api/routes/` | 70%+ | Request validation, error handling |
| `models/` | 60%+ | Model relationships, constraints |

## Test Organization

```
tests/
├── conftest.py           # Shared fixtures
├── factories.py          # Test data factories
├── unit/                 # Unit tests
│   ├── services/         # Service layer tests
│   ├── models/           # Model tests
│   └── utils/            # Utility tests
├── integration/          # Integration tests
│   ├── test_erp_workflow.py
│   ├── test_cmms_workflow.py
│   └── test_full_workflow.py
├── api/                  # API endpoint tests
│   ├── test_erp_api.py
│   └── test_auth_api.py
├── e2e/                  # End-to-end tests
│   └── test_order_to_ship.py
├── performance/          # Performance tests
│   └── test_mrp_performance.py
└── fixtures/             # Test data files
    ├── sample_items.json
    └── sample_boms.json
```

## Test Patterns

### Unit Test Pattern

```python
# tests/unit/services/test_item_service.py
import pytest
from unittest.mock import MagicMock, patch

class TestItemService:
    """Tests for ItemService."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create service instance with mock session."""
        from services.erp.item_service import ItemService
        return ItemService(mock_session)

    def test_create_item_success(self, service, mock_session):
        """Should create item with valid data."""
        # Arrange
        data = {'name': 'Test Item', 'item_type': 'raw_material'}

        # Act
        result = service.create_item(data)

        # Assert
        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_create_item_missing_required_field(self, service):
        """Should raise error when required field missing."""
        # Arrange
        data = {}  # Missing 'name'

        # Act & Assert
        with pytest.raises(KeyError):
            service.create_item(data)

    def test_get_item_not_found(self, service, mock_session):
        """Should return None for non-existent item."""
        # Arrange
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = service.get_item('NONEXISTENT')

        # Assert
        assert result is None
```

### Integration Test Pattern

```python
# tests/integration/test_erp_workflow.py
import pytest
from tests.factories import ItemFactory, SalesOrderFactory

class TestERPWorkflow:
    """Integration tests for ERP workflow."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        """Setup test data."""
        self.session = db_session

    def test_order_to_shipment_flow(self, db_session):
        """Test complete order to shipment workflow."""
        # Create item
        item = ItemFactory.create(db_session, item_type='finished_good')

        # Create sales order
        order = SalesOrderFactory.create(db_session, lines=[
            {'item_id': item.item_id, 'quantity': 10}
        ])

        # Release order
        from services.erp.sales_service import SalesService
        sales = SalesService(db_session)
        sales.release_order(order.order_number, 'test_user')

        # Create shipment
        shipment = sales.create_shipment(order.order_number, {
            'lines': [{'line_number': 1, 'quantity_shipped': 10}]
        })

        # Verify
        assert shipment is not None
        assert order.status.value == 'shipped'
```

### API Test Pattern

```python
# tests/api/test_erp_api.py
import pytest
from flask import url_for

class TestItemsAPI:
    """Tests for Items API endpoints."""

    def test_list_items(self, client, auth_token):
        """GET /api/v1/erp/items should return item list."""
        response = client.get(
            '/api/v1/erp/items',
            headers={'Authorization': f'Bearer {auth_token}'}
        )

        assert response.status_code == 200
        assert isinstance(response.json, list)

    def test_create_item(self, client, auth_token):
        """POST /api/v1/erp/items should create new item."""
        response = client.post(
            '/api/v1/erp/items',
            headers={'Authorization': f'Bearer {auth_token}'},
            json={'name': 'Test Item', 'item_type': 'raw_material'}
        )

        assert response.status_code == 201
        assert 'item_id' in response.json

    def test_create_item_unauthorized(self, client):
        """POST /api/v1/erp/items without auth should return 401."""
        response = client.post(
            '/api/v1/erp/items',
            json={'name': 'Test Item'}
        )

        assert response.status_code == 401
```

## Fixtures (conftest.py)

### Core Fixtures

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope='session')
def engine():
    """Create test database engine."""
    return create_engine('sqlite:///:memory:')

@pytest.fixture(scope='session')
def tables(engine):
    """Create all tables."""
    from models.base import Base
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def db_session(engine, tables):
    """Create database session for test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def mock_session():
    """Create mock session for unit tests."""
    from unittest.mock import MagicMock
    return MagicMock()

@pytest.fixture
def app():
    """Create Flask test application."""
    from app import create_app
    app = create_app({'TESTING': True})
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()

@pytest.fixture
def auth_token(client):
    """Get authentication token."""
    response = client.post('/api/auth/login', json={
        'username': 'admin',
        'password': 'admin'
    })
    return response.json['access_token']
```

## Test Factories

```python
# tests/factories.py
from factory import Factory, Faker, SubFactory, LazyAttribute
import factory

class ItemFactory(Factory):
    """Factory for Item entities."""

    class Meta:
        model = dict

    item_id = Faker('uuid4')
    name = Faker('word')
    item_type = 'raw_material'
    base_uom = 'EA'
    standard_cost = Faker('pydecimal', min_value=1, max_value=100)

    @classmethod
    def create(cls, session=None, **kwargs):
        """Create item in database."""
        if session:
            from services.erp.item_service import ItemService
            service = ItemService(session)
            return service.create_item(cls.build(**kwargs))
        return cls.build(**kwargs)

class AssetFactory(Factory):
    """Factory for Asset entities."""

    class Meta:
        model = dict

    asset_id = Faker('uuid4')
    name = Faker('word')
    status = 'operational'
    criticality = 'standard'
```

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=services --cov-report=html

# Run specific test file
pytest tests/unit/services/test_item_service.py

# Run specific test class
pytest tests/unit/services/test_item_service.py::TestItemService

# Run specific test
pytest tests/unit/services/test_item_service.py::TestItemService::test_create_item_success

# Run by marker
pytest -m unit
pytest -m integration
pytest -m "not slow"
```

### Coverage Report

```bash
# Generate HTML coverage report
pytest --cov=services --cov=api --cov-report=html

# Open report
open htmlcov/index.html

# Terminal report with missing lines
pytest --cov=services --cov-report=term-missing
```

## Test Markers

```python
# pytest.ini markers
[pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
    asyncio: Async tests
    smoke: Smoke tests
    regression: Regression tests
    security: Security tests
    performance: Performance tests
    database: Database tests
    api: API tests
    scada: SCADA tests
    mes: MES tests
    erp: ERP tests
    ml: ML tests
```

Usage:
```bash
pytest -m unit          # Only unit tests
pytest -m "not slow"    # Skip slow tests
pytest -m "erp and integration"  # ERP integration tests
```

## Mocking Guidelines

### When to Mock

| Mock When | Don't Mock When |
|-----------|-----------------|
| External services (APIs) | Core business logic |
| Database in unit tests | Integration tests |
| Time-dependent operations | Simple utilities |
| File system operations | Pure functions |
| Network calls | Data transformations |

### Mocking Examples

```python
from unittest.mock import MagicMock, patch, AsyncMock

# Mock database query
mock_session.query.return_value.filter.return_value.first.return_value = mock_item

# Mock external API
with patch('services.external.api_client.fetch') as mock_fetch:
    mock_fetch.return_value = {'data': 'test'}
    result = service.call_external()

# Mock datetime
with patch('services.erp.sales_service.datetime') as mock_dt:
    mock_dt.utcnow.return_value = datetime(2024, 1, 1, 12, 0, 0)
    result = service.create_order(data)

# Mock async function
with patch('services.async_service.fetch', new_callable=AsyncMock) as mock:
    mock.return_value = {'status': 'ok'}
    result = await service.async_method()
```

## Best Practices

### Test Naming

```python
# Pattern: test_<action>_<scenario>_<expected_result>

def test_create_item_with_valid_data_returns_item_dict():
    ...

def test_create_item_without_name_raises_key_error():
    ...

def test_get_item_with_nonexistent_id_returns_none():
    ...
```

### Arrange-Act-Assert

```python
def test_complete_work_order_calculates_costs(self, service, mock_session):
    # Arrange
    mock_wo = create_mock_work_order(hours=8, rate=50)
    mock_session.query.return_value.filter.return_value.first.return_value = mock_wo

    # Act
    result = service.complete_work_order('WO-001', actual_hours=8)

    # Assert
    assert result['actual_labor_cost'] == 400
    assert result['status'] == 'completed'
```

### Test Independence

- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order
- Clean up test data after each test

### Test Data

```python
# Use factories for complex objects
item = ItemFactory.create(session, name='Test Widget')

# Use simple dicts for basic data
data = {'name': 'Test', 'quantity': 10}

# Use fixtures for shared test data
@pytest.fixture
def sample_bom():
    return {
        'parent_item_id': 'PARENT-001',
        'lines': [
            {'component_id': 'COMP-001', 'quantity': 2},
            {'component_id': 'COMP-002', 'quantity': 5}
        ]
    }
```

## CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Run tests
        run: pytest --cov=services --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Performance Testing

```python
# tests/performance/test_mrp_performance.py
import pytest
import time

class TestMRPPerformance:
    """Performance tests for MRP service."""

    @pytest.mark.slow
    def test_mrp_explosion_1000_items(self, db_session):
        """MRP should handle 1000 items within 30 seconds."""
        # Setup: Create 1000 items with BOMs
        setup_large_bom_structure(db_session, item_count=1000)

        # Execute
        from services.erp.mrp_service import MRPService
        mrp = MRPService(db_session)

        start = time.time()
        result = mrp.run_mrp(horizon_days=90)
        elapsed = time.time() - start

        # Assert
        assert elapsed < 30, f"MRP took {elapsed}s, expected < 30s"
        assert len(result.requirements) > 0
```
