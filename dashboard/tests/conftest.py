"""
Pytest Configuration for LegoMCP v5.0 Tests
"""

import pytest
import sys
from pathlib import Path

# Add dashboard to path
dashboard_path = Path(__file__).parent.parent
sys.path.insert(0, str(dashboard_path))


@pytest.fixture(scope='session')
def app():
    """Create test application."""
    from app import create_app
    app = create_app('testing')
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture(scope='function')
def client(app):
    """Create test client for each test."""
    with app.test_client() as client:
        yield client


@pytest.fixture(scope='function')
def runner(app):
    """Create CLI test runner."""
    return app.test_cli_runner()
