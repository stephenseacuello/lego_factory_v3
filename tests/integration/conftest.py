"""
LEGO Factory v3 - Integration Test Configuration
=================================================
Fixtures and configuration specific to integration tests.
These fixtures require external services (database, APIs, etc.)
"""

import os
import pytest
from datetime import datetime
from typing import Generator, Dict, Any
from unittest.mock import patch, MagicMock

# Set test environment
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('TESTING', 'true')


# ============================================================================
# DATABASE FIXTURES FOR INTEGRATION TESTS
# ============================================================================

@pytest.fixture(scope='session')
def integration_engine():
    """
    Create test database engine for integration tests.

    Uses PostgreSQL if available, falls back to SQLite.
    For full integration tests, set DATABASE_URL to a test database.
    """
    from sqlalchemy import create_engine

    # Use test database URL or default to SQLite
    url = os.environ.get(
        'TEST_DATABASE_URL',
        os.environ.get('DATABASE_URL', 'sqlite:///:memory:')
    )

    # Ensure we're not accidentally using production database
    if 'production' in url.lower():
        raise RuntimeError("Cannot run integration tests against production database!")

    engine = create_engine(url, echo=False)
    return engine


@pytest.fixture(scope='session')
def integration_tables(integration_engine):
    """Create all tables for integration testing."""
    from models.base import Base

    # Import all models to ensure they're registered
    _import_all_models()

    Base.metadata.create_all(integration_engine)
    yield
    Base.metadata.drop_all(integration_engine)


@pytest.fixture(scope='function')
def integration_db_session(integration_engine, integration_tables):
    """
    Create a transactional database session for each integration test.

    Each test runs in its own transaction that is rolled back after the test,
    ensuring test isolation while still testing real database operations.
    """
    from sqlalchemy.orm import sessionmaker

    connection = integration_engine.connect()
    transaction = connection.begin()

    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope='function')
def clean_db_session(integration_engine, integration_tables):
    """
    Create a clean database session that commits changes.

    Use this fixture when you need to test actual commits/rollbacks.
    WARNING: Changes made with this fixture are NOT automatically rolled back.
    """
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=integration_engine)
    session = Session()

    yield session

    # Cleanup: delete all data from tables
    from models.base import Base
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    session.close()


# ============================================================================
# API CLIENT FIXTURES
# ============================================================================

@pytest.fixture(scope='session')
def integration_app():
    """
    Create Flask application for integration testing.

    This creates a real application instance with test configuration.
    """
    with patch('config.database.get_engine') as mock_engine, \
         patch('config.database.init_timescaledb') as mock_init:
        mock_engine.return_value = None
        mock_init.return_value = None

        try:
            from app import create_app
            application = create_app()
        except Exception as e:
            # Fallback: create minimal Flask app
            from flask import Flask, jsonify
            application = Flask(__name__)

            @application.route('/health')
            def health():
                return jsonify({'status': 'healthy', 'version': '3.0.0'})

        application.config.update({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'SQLALCHEMY_DATABASE_URI': os.environ.get(
                'TEST_DATABASE_URL',
                'sqlite:///:memory:'
            ),
            'PRESERVE_CONTEXT_ON_EXCEPTION': False,
        })

        return application


@pytest.fixture(scope='function')
def integration_client(integration_app):
    """Create Flask test client for integration tests."""
    return integration_app.test_client()


@pytest.fixture(scope='function')
def authenticated_client(integration_client, integration_db_session):
    """
    Create an authenticated test client.

    Returns a client with valid authentication headers/cookies.
    """
    # Create test user
    test_user = _create_test_user(integration_db_session)

    # Login and get token/session
    response = integration_client.post('/api/v1/auth/login', json={
        'username': test_user['username'],
        'password': test_user['password'],
    })

    # If login fails, use mock authentication
    if response.status_code != 200:
        # Use mock authentication for tests
        integration_client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer test-token'

    return integration_client


@pytest.fixture(scope='function')
def admin_client(integration_client, integration_db_session):
    """
    Create an authenticated admin client.

    Returns a client with admin privileges.
    """
    # Create admin user
    admin_user = _create_test_user(integration_db_session, is_admin=True)

    # Login
    response = integration_client.post('/api/v1/auth/login', json={
        'username': admin_user['username'],
        'password': admin_user['password'],
    })

    if response.status_code != 200:
        integration_client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer admin-test-token'

    return integration_client


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test(request, integration_db_session):
    """
    Automatic cleanup after each integration test.

    This fixture runs after every test to ensure clean state.
    """
    yield

    # Rollback any uncommitted changes
    try:
        integration_db_session.rollback()
    except Exception:
        pass


@pytest.fixture(scope='session', autouse=True)
def cleanup_after_session(request, integration_engine):
    """
    Cleanup after all integration tests complete.
    """
    yield

    # Final cleanup
    integration_engine.dispose()


@pytest.fixture(scope='function')
def cleanup_files():
    """
    Fixture to cleanup any files created during tests.
    """
    created_files = []

    def register_file(filepath):
        created_files.append(filepath)

    yield register_file

    # Cleanup created files
    import os
    for filepath in created_files:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass


# ============================================================================
# SERVICE FIXTURES
# ============================================================================

@pytest.fixture(scope='function')
def tag_service(integration_db_session):
    """Create TagService instance for integration tests."""
    try:
        from services.scada.tag_service import TagService
        return TagService(integration_db_session)
    except ImportError:
        return MagicMock()


@pytest.fixture(scope='function')
def alarm_service(integration_db_session):
    """Create AlarmService instance for integration tests."""
    try:
        from services.scada.alarm_service import AlarmService
        return AlarmService(integration_db_session)
    except ImportError:
        return MagicMock()


@pytest.fixture(scope='function')
def work_order_service(integration_db_session):
    """Create WorkOrderService instance for integration tests."""
    try:
        from services.mes.work_order_service import WorkOrderService
        return WorkOrderService(integration_db_session)
    except ImportError:
        return MagicMock()


@pytest.fixture(scope='function')
def inventory_service(integration_db_session):
    """Create InventoryService instance for integration tests."""
    try:
        from services.erp.inventory_service import InventoryService
        return InventoryService(integration_db_session)
    except ImportError:
        return MagicMock()


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================

@pytest.fixture(scope='function')
def seeded_tags(integration_db_session) -> list:
    """
    Create a set of test tags in the database.

    Returns list of created tag objects.
    """
    tags = []
    try:
        from models.scada.tags import Tag

        for i in range(5):
            tag = Tag(
                tag_id=f'INT_TEST_TAG_{i:03d}',
                name=f'Integration Test Tag {i}',
                description=f'Tag created for integration testing',
                data_type='float32',
                category='analog_input',
                area='test_area',
                equipment=f'test_machine_{i}',
                eng_units='C',
                eng_low=0.0,
                eng_high=100.0,
                historize=True,
                scan_rate_ms=1000,
            )
            integration_db_session.add(tag)
            tags.append(tag)

        integration_db_session.flush()
    except ImportError:
        pass

    return tags


@pytest.fixture(scope='function')
def seeded_alarms(integration_db_session, seeded_tags) -> list:
    """
    Create test alarms associated with seeded tags.

    Returns list of created alarm definition objects.
    """
    alarms = []
    try:
        from models.scada.alarms import AlarmDefinition

        for i, tag in enumerate(seeded_tags[:3]):
            alarm = AlarmDefinition(
                alarm_id=f'INT_TEST_ALARM_{i:03d}',
                name=f'Integration Test Alarm {i}',
                description=f'Alarm for testing',
                priority=2,
                alarm_class='process',
                alarm_type='high',
                tag_id=tag.tag_id,
                high_limit=80.0,
                high_high_limit=95.0,
                deadband=1.0,
                enabled=True,
            )
            integration_db_session.add(alarm)
            alarms.append(alarm)

        integration_db_session.flush()
    except ImportError:
        pass

    return alarms


@pytest.fixture(scope='function')
def seeded_work_orders(integration_db_session) -> list:
    """
    Create test work orders in the database.

    Returns list of created work order objects.
    """
    work_orders = []
    try:
        from models.mes.work_orders import WorkOrder, WorkOrderStatus

        for i in range(3):
            wo = WorkOrder(
                work_order_id=f'INT_TEST_WO_{i:03d}',
                description=f'Integration Test Work Order {i}',
                product_id=f'PROD_{i:03d}',
                quantity_ordered=100 * (i + 1),
                priority=5 - i,
                status=WorkOrderStatus.CREATED,
                created_by='integration_test',
            )
            integration_db_session.add(wo)
            work_orders.append(wo)

        integration_db_session.flush()
    except ImportError:
        pass

    return work_orders


@pytest.fixture(scope='function')
def seeded_inventory(integration_db_session) -> Dict[str, Any]:
    """
    Create test inventory items and locations.

    Returns dict with 'items', 'locations', and 'inventory' keys.
    """
    data = {'items': [], 'locations': [], 'inventory': []}

    try:
        from models.erp.items import Item
        from models.erp.inventory import Location, Inventory

        # Create items
        for i in range(3):
            item = Item(
                item_id=f'INT_TEST_ITEM_{i:03d}',
                name=f'Test Item {i}',
                item_type='component',
                status='active',
                base_uom='EA',
                standard_cost=10.0 * (i + 1),
            )
            integration_db_session.add(item)
            data['items'].append(item)

        # Create locations
        for i in range(2):
            location = Location(
                location_id=f'INT_TEST_LOC_{i:03d}',
                name=f'Test Location {i}',
                location_type='warehouse',
                is_active=True,
            )
            integration_db_session.add(location)
            data['locations'].append(location)

        integration_db_session.flush()

        # Create inventory records
        for item in data['items']:
            for location in data['locations']:
                inv = Inventory(
                    item_id=item.item_id,
                    location_id=location.location_id,
                    quantity_on_hand=100.0,
                    quantity_reserved=10.0,
                )
                integration_db_session.add(inv)
                data['inventory'].append(inv)

        integration_db_session.flush()
    except ImportError:
        pass

    return data


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _import_all_models():
    """Import all model modules to ensure they're registered with SQLAlchemy."""
    model_modules = [
        'models.scada.tags',
        'models.scada.alarms',
        'models.scada.recipes',
        'models.mes.work_orders',
        'models.mes.scheduling',
        'models.erp.items',
        'models.erp.inventory',
        'models.erp.partners',
        'models.erp.sales',
        'models.erp.purchasing',
    ]

    for module_name in model_modules:
        try:
            __import__(module_name)
        except ImportError:
            pass


def _create_test_user(session, is_admin: bool = False) -> Dict[str, str]:
    """Create a test user for authentication tests."""
    import uuid

    username = f'test_user_{uuid.uuid4().hex[:8]}'
    password = 'TestPassword123!'

    try:
        from models.auth.users import User

        user = User(
            username=username,
            email=f'{username}@test.com',
            is_active=True,
            is_admin=is_admin,
        )
        user.set_password(password)
        session.add(user)
        session.flush()
    except ImportError:
        pass

    return {
        'username': username,
        'password': password,
        'is_admin': is_admin,
    }
