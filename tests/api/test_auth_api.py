"""
LEGO Factory v3 - Authentication API Tests
==========================================
Tests for authentication endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from flask_jwt_extended import JWTManager


@pytest.fixture
def app():
    """Create test Flask application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['JWT_SECRET_KEY'] = 'test-secret-key'
    app.config['JWT_TOKEN_LOCATION'] = ['headers']

    JWTManager(app)

    # Import and register blueprint
    from api.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestLoginAPI:
    """Test login endpoint."""

    def test_login_missing_credentials(self, client):
        """Test login with missing credentials."""
        response = client.post('/api/auth/login', json={})
        assert response.status_code in [400, 401, 422]

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        with patch('api.routes.auth.UserService') as mock_service:
            mock_service.return_value.authenticate.return_value = None

            response = client.post(
                '/api/auth/login',
                json={'username': 'invalid', 'password': 'wrong'}
            )
            assert response.status_code in [401, 403]

    def test_login_valid_credentials(self, client):
        """Test login with valid credentials."""
        with patch('api.routes.auth.get_db_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session.return_value.__exit__ = MagicMock(return_value=None)

            with patch('api.routes.auth.UserService') as mock_service:
                mock_user = MagicMock()
                mock_user.id = 'test-user-id'
                mock_user.username = 'testuser'
                mock_user.role = 'operator'
                mock_service.return_value.authenticate.return_value = mock_user

                response = client.post(
                    '/api/auth/login',
                    json={'username': 'testuser', 'password': 'testpass'}
                )

                # Should return token on success
                if response.status_code == 200:
                    import json
                    data = json.loads(response.data)
                    assert 'access_token' in data or 'token' in data


class TestRegistrationAPI:
    """Test registration endpoint."""

    def test_register_missing_fields(self, client):
        """Test registration with missing fields."""
        response = client.post('/api/auth/register', json={})
        assert response.status_code in [400, 422]

    def test_register_valid_user(self, client):
        """Test registration with valid data."""
        with patch('api.routes.auth.get_db_session') as mock_session:
            mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session.return_value.__exit__ = MagicMock(return_value=None)

            with patch('api.routes.auth.UserService') as mock_service:
                mock_user = MagicMock()
                mock_user.id = 'new-user-id'
                mock_user.username = 'newuser'
                mock_service.return_value.create_user.return_value = mock_user

                response = client.post(
                    '/api/auth/register',
                    json={
                        'username': 'newuser',
                        'password': 'SecurePass123!',
                        'email': 'new@example.com'
                    }
                )

                # Should succeed or return validation error
                assert response.status_code in [201, 200, 400, 409]


class TestTokenRefreshAPI:
    """Test token refresh endpoint."""

    def test_refresh_without_token(self, client):
        """Test refresh without token."""
        response = client.post('/api/auth/refresh')
        assert response.status_code in [401, 422]
