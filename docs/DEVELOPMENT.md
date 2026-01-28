# Development Guide

This guide covers development setup, coding standards, testing practices, and contribution guidelines for LEGO Factory v3.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Database](#database)
- [Adding New Features](#adding-new-features)
- [Debugging](#debugging)
- [Contributing](#contributing)

---

## Development Setup

### Prerequisites

```bash
# Required
python3 --version  # 3.11+
pip --version      # 23+

# Recommended
docker --version   # 24+
make --version     # GNU Make
```

### Initial Setup

```bash
# 1. Clone repository
cd lego_factory

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Or using make:
make dev-install

# 4. Setup environment
cp .env.example .env
# Edit .env for your local setup

# 5. Start supporting services
docker-compose up -d postgres redis

# 6. Run migrations
flask db upgrade

# 7. Start development server
python run.py
```

### IDE Setup

#### VS Code

Recommended extensions:
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Python Test Explorer
- SQLAlchemy Autocomplete

`.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/"],
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

#### PyCharm

1. Set interpreter to `.venv/bin/python`
2. Mark directories as source roots: `app/`, `services/`, `models/`, `api/`
3. Configure pytest as test runner

---

## Project Structure

```
lego_factory/
├── app/                    # Flask application factory
│   ├── __init__.py
│   └── main.py             # create_app() factory
├── api/                    # REST API layer
│   ├── __init__.py
│   └── routes/             # API route blueprints
│       ├── erp_api.py
│       ├── mes_api.py
│       ├── scada_api.py
│       └── ...
├── config/                 # Configuration
│   ├── settings.py         # Main config with DEMO_MODE
│   ├── database.py         # SQLAlchemy setup
│   └── validators.py       # Config validation
├── models/                 # SQLAlchemy ORM models
│   ├── base.py             # Base model with audit fields
│   ├── erp/                # ERP domain models
│   ├── mes/                # MES domain models
│   ├── scada/              # SCADA domain models
│   ├── cmms/               # CMMS domain models
│   └── qms/                # QMS domain models
├── services/               # Business logic layer
│   ├── erp/                # ERP services
│   │   ├── item_service.py
│   │   ├── sales_service.py
│   │   ├── mrp_service.py
│   │   └── ...
│   ├── mes/                # MES services
│   ├── scada/              # SCADA services
│   ├── cmms/               # CMMS services
│   ├── qms/                # QMS services
│   └── advanced/           # Advanced features
│       ├── ml/             # Machine learning
│       ├── security/       # Security (HSM, TPM)
│       └── observability/  # Health checks, tracing
├── tests/                  # Test suite
│   ├── conftest.py         # Shared fixtures
│   ├── factories.py        # Test data factories
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── api/                # API tests
├── scripts/                # Utility scripts
│   ├── generate_secrets.py
│   └── seed_demo_data.py
├── docs/                   # Documentation
├── docker/                 # Docker configurations
└── k8s/                    # Kubernetes manifests
```

### Layer Responsibilities

| Layer | Responsibility | Dependencies |
|-------|---------------|--------------|
| **API** | HTTP handling, validation, serialization | Services |
| **Services** | Business logic, orchestration | Models, External APIs |
| **Models** | Data persistence, relationships | SQLAlchemy |
| **Config** | Application configuration | Environment |

### Import Rules

```python
# Good: Import from public interfaces
from services.erp.item_service import ItemService, get_item_service

# Avoid: Deep imports from internal modules
from services.erp.item_service.internal import _helper_function  # Bad
```

---

## Coding Standards

### Python Style

We follow PEP 8 with these additions:

```python
# Use type hints
def create_item(data: dict) -> dict:
    """Create a new item.

    Args:
        data: Item data dictionary

    Returns:
        Created item dictionary

    Raises:
        ValueError: If required fields missing
    """
    pass

# Use dataclasses for value objects
from dataclasses import dataclass

@dataclass
class MRPRequirement:
    item_id: str
    quantity: float
    date_required: date
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `ItemService` |
| Functions | snake_case | `create_item()` |
| Variables | snake_case | `item_count` |
| Constants | UPPER_SNAKE | `MAX_RETRIES` |
| Private | _prefix | `_internal_method()` |
| Files | snake_case | `item_service.py` |

### Service Pattern

```python
# services/erp/item_service.py

class ItemService:
    """Service for item management."""

    def __init__(self, session):
        """Initialize with database session."""
        self.session = session

    def create_item(self, data: dict) -> dict:
        """Create a new item.

        Args:
            data: Item attributes

        Returns:
            Created item as dictionary
        """
        item = Item(**data)
        self.session.add(item)
        self.session.flush()
        return item.to_dict()

    def get_item(self, item_id: str) -> Optional[dict]:
        """Get item by ID."""
        item = self.session.query(Item).filter(
            Item.item_id == item_id,
            Item.is_deleted == False
        ).first()
        return item.to_dict() if item else None


def get_item_service(session=None) -> ItemService:
    """Factory function to get ItemService instance."""
    if session:
        return ItemService(session)
    with get_db_session() as session:
        return ItemService(session)
```

### API Route Pattern

```python
# api/routes/erp_api.py

from flask import Blueprint, request, jsonify
from services.erp.item_service import get_item_service

erp_bp = Blueprint('erp', __name__, url_prefix='/api/v1/erp')

@erp_bp.route('/items', methods=['GET'])
def list_items():
    """List all items with optional filters."""
    service = get_item_service()

    items = service.get_items(
        item_type=request.args.get('item_type'),
        limit=int(request.args.get('limit', 100)),
        offset=int(request.args.get('offset', 0))
    )

    return jsonify(items)

@erp_bp.route('/items', methods=['POST'])
def create_item():
    """Create a new item."""
    data = request.get_json()

    if not data.get('name'):
        return jsonify({'error': 'name is required'}), 400

    service = get_item_service()
    item = service.create_item(data)

    return jsonify(item), 201
```

---

## Testing

### Running Tests

```bash
# Run all tests
make test
# Or: pytest tests/ -v

# Run unit tests only
make test-unit
# Or: pytest tests/unit/ -v

# Run integration tests
make test-integration
# Or: pytest tests/integration/ -v

# Run specific test file
pytest tests/unit/services/test_item_service.py -v

# Run specific test class
pytest tests/unit/services/test_item_service.py::TestCreateItem -v

# Run with coverage
make coverage
# Or: pytest --cov=services --cov-report=html

# Run in parallel
pytest tests/ -n auto
```

### Test Structure

```python
# tests/unit/services/test_item_service.py

import pytest
from unittest.mock import Mock, MagicMock, patch

class TestCreateItem:
    """Tests for ItemService.create_item()."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create service with mock session."""
        from services.erp.item_service import ItemService
        return ItemService(mock_session)

    def test_create_item_success(self, service, mock_session):
        """Should create item with valid data."""
        # Arrange
        data = {'name': 'Test Item', 'item_type': 'raw_material'}

        with patch('services.erp.item_service.Item') as MockItem:
            mock_item = Mock()
            mock_item.to_dict.return_value = {'item_id': 'ITM-001', **data}
            MockItem.return_value = mock_item

            # Act
            result = service.create_item(data)

        # Assert
        assert result['name'] == 'Test Item'
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_create_item_missing_name_raises(self, service):
        """Should raise error when name is missing."""
        with pytest.raises(KeyError):
            service.create_item({})
```

### Test Fixtures

```python
# tests/conftest.py

import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_session():
    """Create mock database session for unit tests."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    return session

@pytest.fixture
def app():
    """Create Flask test application."""
    from app.main import create_app
    app = create_app({'TESTING': True, 'DEMO_MODE': True})
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()
```

### Test Factories

```python
# tests/factories.py

from factory import Factory, Faker, LazyAttribute

class ItemFactory(Factory):
    """Factory for Item test data."""

    class Meta:
        model = dict

    item_id = Faker('uuid4')
    name = Faker('word')
    item_type = 'raw_material'
    base_uom = 'EA'
    standard_cost = Faker('pydecimal', min_value=1, max_value=100)

# Usage:
item_data = ItemFactory.build(name='Custom Name')
```

### Coverage Targets

| Module | Target |
|--------|--------|
| `services/erp/` | 80%+ |
| `services/mes/` | 80%+ |
| `services/qms/` | 80%+ |
| `services/cmms/` | 80%+ |
| `api/routes/` | 70%+ |

---

## Database

### Migrations

```bash
# Create new migration
flask db migrate -m "Add new column to items"

# Apply migrations
flask db upgrade

# Rollback last migration
flask db downgrade

# View migration history
flask db history
```

### Model Pattern

```python
# models/erp/item.py

from models.base import Base, AuditMixin
from sqlalchemy import Column, String, Numeric, Boolean, Enum
import enum

class ItemType(enum.Enum):
    raw_material = 'raw_material'
    component = 'component'
    finished_good = 'finished_good'

class Item(Base, AuditMixin):
    """Item master data."""

    __tablename__ = 'items'

    item_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    item_type = Column(Enum(ItemType), nullable=False)
    base_uom = Column(String(10), default='EA')
    standard_cost = Column(Numeric(15, 4), default=0)
    is_deleted = Column(Boolean, default=False)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'item_id': self.item_id,
            'name': self.name,
            'item_type': self.item_type.value,
            'base_uom': self.base_uom,
            'standard_cost': float(self.standard_cost or 0),
        }
```

---

## Adding New Features

### 1. Plan the Feature

1. Define the domain (ERP, MES, SCADA, etc.)
2. Identify models needed
3. Design service methods
4. Plan API endpoints

### 2. Create Models

```bash
# Create model file
touch models/erp/new_feature.py
```

### 3. Create Service

```bash
# Create service file
touch services/erp/new_feature_service.py
```

### 4. Create API Routes

```bash
# Add routes to existing blueprint or create new
# api/routes/erp_api.py
```

### 5. Write Tests

```bash
# Create test file
touch tests/unit/services/test_new_feature_service.py
```

### 6. Create Migration

```bash
flask db migrate -m "Add new_feature tables"
flask db upgrade
```

### 7. Update Documentation

- Add API endpoints to API_REFERENCE.md
- Update README if significant feature

---

## Debugging

### Logging

```python
import logging
logger = logging.getLogger(__name__)

def process_order(order_id):
    logger.info(f"Processing order {order_id}")
    try:
        # ...
    except Exception as e:
        logger.error(f"Failed to process order {order_id}: {e}")
        raise
```

### Debug Mode

```bash
# Enable Flask debug mode
FLASK_DEBUG=true python run.py

# Enable SQL logging
LOG_LEVEL=DEBUG python run.py
```

### Interactive Debugging

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use ipdb for better experience
import ipdb; ipdb.set_trace()
```

### Database Queries

```bash
# Connect to database
docker-compose exec postgres psql -U lego -d lego_factory

# View slow queries
SELECT query, calls, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

---

## Contributing

### Workflow

1. **Fork** the repository
2. **Create branch**: `git checkout -b feature/my-feature`
3. **Make changes** with tests
4. **Run tests**: `make test`
5. **Run linting**: `make lint`
6. **Commit**: `git commit -m "Add my feature"`
7. **Push**: `git push origin feature/my-feature`
8. **Create PR** with description

### Commit Messages

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(erp): add batch costing calculation

Add support for calculating costs based on batch sizes
with configurable overhead allocation.

Closes #123
```

### Code Review Checklist

- [ ] Tests pass
- [ ] Coverage maintained or improved
- [ ] No security vulnerabilities
- [ ] Documentation updated
- [ ] Follows coding standards
- [ ] No breaking changes (or documented)

---

## Useful Commands

```bash
# Development
make test              # Run all tests
make coverage          # Run with coverage
make lint              # Run linters
make format            # Format code

# Database
flask db upgrade       # Apply migrations
flask db downgrade     # Rollback
flask db migrate -m "" # Create migration

# Docker
docker-compose up -d   # Start services
docker-compose logs -f # View logs
docker-compose down    # Stop services

# Secrets
python scripts/generate_secrets.py --output .env.secrets
```
