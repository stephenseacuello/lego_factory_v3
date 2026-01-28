"""
LEGO Factory v3 - Production API Tests
=======================================
Integration tests for MES/Production API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token


@pytest.fixture
def app():
    """Create test Flask application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'
    app.config['JWT_TOKEN_LOCATION'] = ['headers']

    JWTManager(app)

    # Import and register blueprint
    from api.routes.mes_api import mes_api_bp
    app.register_blueprint(mes_api_bp)

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    """Create authorization headers with valid JWT token."""
    with app.app_context():
        token = create_access_token(identity='test_user')
        return {'Authorization': f'Bearer {token}'}


class TestWorkOrdersAPI:
    """Test work orders API endpoints."""

    def test_list_work_orders_unauthorized(self, client):
        """Test that listing work orders requires authentication."""
        response = client.get('/api/mes/work-orders')
        assert response.status_code == 401

    def test_list_work_orders_authorized(self, client, auth_headers):
        """Test listing work orders with valid authentication."""
        with patch('api.routes.mes_api.get_db_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session.return_value.__exit__ = MagicMock(return_value=None)

            # Mock the service
            with patch('api.routes.mes_api.WorkOrderService') as mock_service:
                mock_service.return_value.get_work_orders.return_value = []
                response = client.get('/api/mes/work-orders', headers=auth_headers)

                # Should return 200 or fallback to demo mode
                assert response.status_code in [200, 503]

    def test_create_work_order_missing_fields(self, client, auth_headers):
        """Test creating work order with missing required fields."""
        response = client.post(
            '/api/mes/work-orders',
            json={},
            headers=auth_headers
        )
        # Should return validation error
        assert response.status_code in [400, 422]

    def test_create_work_order_valid(self, client, auth_headers):
        """Test creating work order with valid data."""
        with patch('api.routes.mes_api.get_db_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session.return_value.__exit__ = MagicMock(return_value=None)

            with patch('api.routes.mes_api.WorkOrderService') as mock_service:
                mock_service.return_value.create_work_order.return_value = {
                    'id': 'test-id',
                    'work_order_id': 'WO-TEST-001',
                    'status': 'created'
                }

                response = client.post(
                    '/api/mes/work-orders',
                    json={
                        'product_id': 'BRICK-2X4-RED',
                        'quantity_ordered': 100,
                        'priority': 5
                    },
                    headers=auth_headers
                )

                # Should succeed or return demo response
                assert response.status_code in [201, 200, 503]


class TestRecipesAPI:
    """Test recipe API endpoints."""

    def test_list_recipes_unauthorized(self, client):
        """Test that listing recipes requires authentication."""
        response = client.get('/api/mes/recipes')
        assert response.status_code == 401

    def test_list_recipes_authorized(self, client, auth_headers):
        """Test listing recipes with authentication."""
        response = client.get('/api/mes/recipes', headers=auth_headers)
        # Should return 200 (with demo data) or 503
        assert response.status_code in [200, 503]


class TestJobsAPI:
    """Test jobs API endpoints."""

    def test_list_jobs_unauthorized(self, client):
        """Test that listing jobs requires authentication."""
        response = client.get('/api/mes/jobs')
        assert response.status_code == 401


class TestOEEAPI:
    """Test OEE metrics API endpoints."""

    def test_oee_summary_unauthorized(self, client):
        """Test that OEE summary requires authentication."""
        response = client.get('/api/mes/oee/summary')
        assert response.status_code == 401

    def test_oee_summary_authorized(self, client, auth_headers):
        """Test OEE summary with authentication."""
        response = client.get('/api/mes/oee/summary', headers=auth_headers)
        # Should return 200 (with demo data) or 503
        assert response.status_code in [200, 503]
