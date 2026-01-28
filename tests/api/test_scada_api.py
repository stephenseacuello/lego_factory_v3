"""
LEGO Factory v3 - SCADA API Tests
=================================
Integration tests for SCADA API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
import json


@pytest.fixture
def app():
    """Create test Flask application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'
    app.config['JWT_TOKEN_LOCATION'] = ['headers']

    JWTManager(app)

    # Import and register blueprint
    from api.routes.scada_api import scada_api_bp
    app.register_blueprint(scada_api_bp)

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


class TestMachinesAPI:
    """Test machines API endpoints."""

    def test_list_machines_unauthorized(self, client):
        """Test that listing machines requires authentication."""
        response = client.get('/api/scada/machines')
        assert response.status_code == 401

    def test_list_machines_authorized(self, client, auth_headers):
        """Test listing machines with valid authentication."""
        # Mock the config file
        with patch('api.routes.scada_api.load_machines_config') as mock_config:
            mock_config.return_value = [
                {
                    'machine_id': 'test-machine-1',
                    'name': 'Test Machine 1',
                    'description': 'Test description',
                    'machine_type': 'printer_3d',
                    'controller_type': 'marlin',
                    'connection_type': 'serial',
                }
            ]
            response = client.get('/api/scada/machines', headers=auth_headers)
            assert response.status_code == 200

            data = json.loads(response.data)
            assert 'machines' in data
            assert len(data['machines']) >= 1

    def test_get_machine_not_found(self, client, auth_headers):
        """Test getting non-existent machine."""
        with patch('api.routes.scada_api.load_machines_config') as mock_config:
            mock_config.return_value = []
            response = client.get('/api/scada/machines/nonexistent', headers=auth_headers)
            assert response.status_code == 404


class TestTagsAPI:
    """Test SCADA tags API endpoints."""

    def test_list_tags_unauthorized(self, client):
        """Test that listing tags requires authentication."""
        response = client.get('/api/scada/tags')
        assert response.status_code == 401


class TestAlarmsAPI:
    """Test alarms API endpoints."""

    def test_list_alarms_unauthorized(self, client):
        """Test that listing alarms requires authentication."""
        response = client.get('/api/scada/alarms')
        assert response.status_code == 401


class TestGCodeValidation:
    """Test G-code command validation."""

    def test_gcode_send_unauthorized(self, client):
        """Test that sending G-code requires authentication."""
        response = client.post(
            '/api/scada/machines/test-machine/gcode',
            json={'gcode': 'G28'}
        )
        assert response.status_code == 401

    def test_gcode_send_invalid_machine(self, client, auth_headers):
        """Test sending G-code to invalid machine."""
        with patch('api.routes.scada_api.load_machines_config') as mock_config:
            mock_config.return_value = []
            response = client.post(
                '/api/scada/machines/invalid-machine/gcode',
                json={'gcode': 'G28'},
                headers=auth_headers
            )
            assert response.status_code in [404, 400]


class TestHistorianAPI:
    """Test historian API endpoints."""

    def test_write_tag_value_unauthorized(self, client):
        """Test that writing tag values requires authentication."""
        response = client.post(
            '/api/scada/historian/write',
            json={'tag_id': 'test-tag', 'value': 42.0}
        )
        assert response.status_code == 401
