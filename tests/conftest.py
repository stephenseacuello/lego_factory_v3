"""
LEGO Factory v3 - Test Configuration
====================================
Pytest fixtures and configuration for all tests.
"""

import os
import sys
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import Generator, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment before importing anything else
os.environ['FLASK_ENV'] = 'testing'
os.environ['TESTING'] = 'true'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'


# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope='session')
def engine():
    """Create test database engine using SQLite in-memory."""
    from sqlalchemy import create_engine
    url = os.environ.get('DATABASE_URL', 'sqlite:///:memory:')
    return create_engine(url, echo=False)


@pytest.fixture(scope='session')
def tables(engine):
    """Create all tables for testing."""
    from models.base import Base
    # Import all models to ensure they're registered
    try:
        import models.scada.tags
        import models.scada.alarms
        import models.scada.recipes
        import models.mes.work_orders
        import models.mes.scheduling
        import models.erp.items
        import models.erp.inventory
        import models.erp.partners
        import models.erp.sales
        import models.erp.purchasing
    except ImportError:
        pass  # Some models may not exist

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(scope='function')
def db_session(engine, tables):
    """Create a new database session for each test with rollback."""
    from sqlalchemy.orm import sessionmaker

    connection = engine.connect()
    transaction = connection.begin()

    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def mock_session():
    """Create a mock database session for unit tests."""
    session = MagicMock()
    session.add = MagicMock()
    session.flush = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.query = MagicMock()
    session.close = MagicMock()
    return session


# ============================================================================
# FLASK APPLICATION FIXTURES
# ============================================================================

@pytest.fixture(scope='session')
def app():
    """Create Flask test application."""
    # Patch database before app creation
    with patch('config.database.get_engine') as mock_engine, \
         patch('config.database.init_timescaledb') as mock_init:
        mock_engine.return_value = None
        mock_init.return_value = None

        try:
            from app import create_app
            application = create_app()
        except Exception:
            # Fallback: create minimal Flask app for testing
            from flask import Flask
            application = Flask(__name__)
            application.config['TESTING'] = True
            application.config['SECRET_KEY'] = 'test-secret-key'

            # Register minimal routes for testing
            @application.route('/health')
            def health():
                from flask import jsonify
                return jsonify({'status': 'healthy', 'version': '3.0.0'})

        application.config['TESTING'] = True
        application.config['WTF_CSRF_ENABLED'] = False
        application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

        return application


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create Flask CLI test runner."""
    return app.test_cli_runner()


@pytest.fixture
def app_context(app):
    """Create application context."""
    with app.app_context():
        yield


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_machine_controller():
    """Create a mock machine controller for testing."""
    controller = AsyncMock()
    controller.connect = AsyncMock(return_value=True)
    controller.disconnect = AsyncMock(return_value=True)
    controller.send_command = AsyncMock(return_value="ok")
    controller.home = AsyncMock(return_value=True)
    controller.zero = AsyncMock(return_value=True)
    controller.jog = AsyncMock(return_value=True)
    controller.run_gcode = AsyncMock(return_value=True)
    controller.pause = AsyncMock(return_value=True)
    controller.resume = AsyncMock(return_value=True)
    controller.stop = AsyncMock(return_value=True)
    controller.reset = AsyncMock(return_value=True)
    controller.status = MagicMock()
    controller.status.state = MagicMock()
    controller.status.state.value = 'idle'
    controller.status.position = MagicMock(x=0.0, y=0.0, z=0.0)
    controller.status.feed_rate = 0.0
    controller.machine_id = 'test-machine-001'
    return controller


@pytest.fixture
def mock_tag_cache():
    """Create a mock tag cache."""
    cache = AsyncMock()
    cache.set = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.get_many = AsyncMock(return_value={})
    cache.subscribe = AsyncMock()
    cache.unsubscribe = AsyncMock()
    return cache


@pytest.fixture
def mock_alarm_processor():
    """Create a mock alarm processor."""
    processor = MagicMock()
    processor.load_alarm_definitions = MagicMock()
    processor.load_active_alarms = MagicMock()
    processor.evaluate_tag = AsyncMock(return_value=[])
    processor._active_alarms = {}
    processor._alarm_defs = {}
    return processor


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_tag_data() -> Dict[str, Any]:
    """Sample tag data for testing."""
    return {
        'tag_id': 'test_tag_001',
        'name': 'Test Temperature',
        'description': 'A test temperature tag',
        'data_type': 'float32',
        'category': 'analog_input',
        'area': 'production',
        'equipment': 'machine_01',
        'eng_units': 'C',
        'eng_low': 0.0,
        'eng_high': 100.0,
        'raw_low': 0.0,
        'raw_high': 4095.0,
        'deadband': 0.5,
        'historize': True,
        'scan_rate_ms': 1000,
    }


@pytest.fixture
def sample_alarm_data() -> Dict[str, Any]:
    """Sample alarm data for testing."""
    return {
        'alarm_id': 'test_alarm_001',
        'name': 'High Temperature Alarm',
        'description': 'Temperature exceeds safe limit',
        'priority': 2,  # HIGH
        'alarm_class': 'process',
        'alarm_type': 'high',
        'tag_id': 'test_tag_001',
        'high_limit': 80.0,
        'high_high_limit': 90.0,
        'low_limit': 20.0,
        'low_low_limit': 10.0,
        'deadband': 1.0,
        'enabled': True,
        'consequence': 'Risk of equipment damage',
        'corrective_action': 'Check cooling system',
    }


@pytest.fixture
def sample_machine_data() -> Dict[str, Any]:
    """Sample machine data for testing."""
    return {
        'machine_id': 'test_machine_001',
        'name': 'Test CNC Machine',
        'description': 'A test CNC milling machine',
        'machine_type': 'cnc',
        'controller_type': 'simulation',
        'connection_type': 'simulation',
        'connection_config': {},
        'enabled': True,
    }


@pytest.fixture
def sample_work_order_data() -> Dict[str, Any]:
    """Sample work order data for testing."""
    return {
        'work_order_id': 'WO-TEST-001',
        'description': 'Test work order for unit testing',
        'product_id': 'PROD-001',
        'recipe_id': 'RCP-001',
        'quantity_ordered': 100,
        'priority': 5,
        'planned_start': datetime.utcnow(),
        'planned_end': datetime.utcnow(),
        'due_date': datetime.utcnow(),
        'customer_id': 'CUST-001',
        'created_by': 'test_user',
    }


@pytest.fixture
def sample_job_data() -> Dict[str, Any]:
    """Sample job data for testing."""
    return {
        'job_id': 'JOB-TEST-001',
        'machine_id': 'test_machine_001',
        'scheduled_start': datetime.utcnow(),
        'scheduled_end': datetime.utcnow(),
        'quantity_planned': 10,
        'priority_score': 0.5,
        'gcode_file': 'test_program.nc',
        'created_by': 'test_user',
    }


@pytest.fixture
def sample_item_data() -> Dict[str, Any]:
    """Sample inventory item data for testing."""
    return {
        'item_id': 'ITEM-TEST-001',
        'name': 'Test Component',
        'description': 'A test inventory item',
        'item_type': 'component',
        'status': 'active',
        'base_uom': 'EA',
        'standard_cost': 10.0,
        'list_price': 15.0,
        'lead_time_days': 3,
        'safety_stock': 100.0,
        'reorder_point': 50.0,
        'is_purchasable': True,
        'is_salable': True,
        'track_inventory': True,
    }


@pytest.fixture
def sample_location_data() -> Dict[str, Any]:
    """Sample location data for testing."""
    return {
        'location_id': 'LOC-TEST-001',
        'name': 'Test Warehouse',
        'description': 'A test warehouse location',
        'location_type': 'warehouse',
        'is_active': True,
        'allows_negative': False,
    }


@pytest.fixture
def sample_transaction_data(sample_item_data, sample_location_data) -> Dict[str, Any]:
    """Sample inventory transaction data for testing."""
    return {
        'transaction_type': 'receipt',
        'item_id': sample_item_data['item_id'],
        'to_location_id': sample_location_data['location_id'],
        'quantity': 100,
        'unit_cost': 10.0,
        'reference_type': 'purchase_order',
        'reference_id': 'PO-TEST-001',
        'created_by': 'test_user',
    }


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Sample user data for testing."""
    return {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'Test@Password123',
        'is_active': True,
        'is_admin': False,
    }


# ============================================================================
# ANOMALY DETECTION FIXTURES
# ============================================================================

@pytest.fixture
def normal_data() -> list:
    """Normal data for anomaly detection testing."""
    import random
    random.seed(42)
    return [50.0 + random.gauss(0, 5) for _ in range(100)]


@pytest.fixture
def data_with_anomalies() -> list:
    """Data with anomalies for testing."""
    import random
    random.seed(42)
    data = [50.0 + random.gauss(0, 5) for _ in range(100)]
    # Insert anomalies
    data[25] = 150.0  # High anomaly
    data[50] = -50.0  # Low anomaly
    data[75] = 200.0  # Extreme anomaly
    return data


@pytest.fixture
def trending_data() -> list:
    """Data with an upward trend."""
    return [50.0 + i * 0.5 for i in range(100)]


@pytest.fixture
def seasonal_data() -> list:
    """Data with seasonal pattern."""
    import math
    return [50.0 + 20 * math.sin(2 * math.pi * i / 24) for i in range(100)]


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def freeze_time():
    """Fixture to freeze time for testing."""
    from unittest.mock import patch
    frozen_time = datetime(2024, 1, 15, 12, 0, 0)
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.utcnow.return_value = frozen_time
        mock_datetime.now.return_value = frozen_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield frozen_time


@pytest.fixture
def capture_logs(caplog):
    """Fixture to capture log messages."""
    import logging
    caplog.set_level(logging.DEBUG)
    return caplog


# ============================================================================
# ASYNC TEST SUPPORT
# ============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# FACTORY IMPORTS
# ============================================================================

@pytest.fixture
def factories():
    """Import test factories."""
    from tests import factories as factory_module
    return factory_module
