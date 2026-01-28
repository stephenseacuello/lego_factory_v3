"""
Authentication API Routes for Flask CNC SCADA System
=====================================================
Provides REST API endpoints for JWT and OIDC authentication.

Supports dual authentication:
1. Local JWT authentication (username/password)
2. Keycloak OIDC authentication (enterprise SSO)

Local Auth Endpoints:
- POST /auth/login      - Authenticate with username/password
- POST /auth/logout     - Invalidate token (client-side)
- POST /auth/refresh    - Refresh access token
- GET  /auth/me         - Get current user info
- PUT  /auth/password   - Change own password

OIDC (Keycloak) Endpoints:
- POST /auth/oidc/login    - Authenticate via Keycloak
- POST /auth/oidc/logout   - Logout from Keycloak
- POST /auth/oidc/refresh  - Refresh Keycloak token
- GET  /auth/oidc/userinfo - Get OIDC user info
- GET  /auth/oidc/config   - Get OIDC configuration

Admin endpoints (require admin role):
- GET    /auth/users           - List all users
- POST   /auth/users           - Create new user
- GET    /auth/users/<username> - Get user details
- PUT    /auth/users/<username> - Update user
- DELETE /auth/users/<username> - Delete user
- POST   /auth/users/<username>/reset-password - Reset user password
"""

import logging
from flask import Blueprint, request, jsonify

from services.auth_service import (
    authenticate_user,
    create_tokens,
    verify_token,
    create_user,
    change_password,
    reset_password,
    get_user_store,
    get_current_user,
    require_auth,
    require_role,
    require_permission,
    get_auth_config,
    hash_password,
    logout_user,
    blacklist_token
)

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__, url_prefix='/auth')


# =============================================================================
# Authentication Endpoints
# =============================================================================

@bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate user and return JWT tokens.

    Request body:
        {
            "username": "string",
            "password": "string"
        }

    Response:
        {
            "access_token": "string",
            "refresh_token": "string",
            "token_type": "Bearer",
            "expires_in": 3600,
            "user": {
                "username": "string",
                "role": "string",
                "email": "string"
            }
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Bad Request", "message": "JSON body required"}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({
            "error": "Bad Request",
            "message": "Username and password required"
        }), 400

    user, error = authenticate_user(username, password)
    if not user:
        return jsonify({
            "error": "Unauthorized",
            "message": error
        }), 401

    tokens = create_tokens(user)
    return jsonify({
        **tokens,
        "user": user.to_dict()
    })


@bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """
    Logout current user and invalidate the access token.

    The token is added to a blacklist and will be rejected on future requests.
    Blacklisted tokens are automatically cleaned up after they expire.

    Response:
        {"message": "Logged out successfully"}
    """
    user = get_current_user()

    # Get token from header and blacklist it
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        success, message = logout_user(token)
        if not success:
            logger.warning(f"Failed to blacklist token for user {user.username}")
    else:
        logger.warning(f"No token to blacklist for user {user.username}")

    logger.info(f"User {user.username} logged out")
    return jsonify({"message": "Logged out successfully"})


@bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    Refresh access token using refresh token.

    Request body:
        {
            "refresh_token": "string"
        }

    Response:
        {
            "access_token": "string",
            "token_type": "Bearer",
            "expires_in": 3600
        }
    """
    data = request.get_json()
    if not data or 'refresh_token' not in data:
        return jsonify({
            "error": "Bad Request",
            "message": "Refresh token required"
        }), 400

    payload = verify_token(data['refresh_token'], token_type="refresh")
    if not payload:
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or expired refresh token"
        }), 401

    # Get user and verify still active
    store = get_user_store()
    user = store.get(payload.get('sub'))
    if not user or not user.active:
        return jsonify({
            "error": "Unauthorized",
            "message": "User not found or disabled"
        }), 401

    # Create new access token only (refresh token remains valid)
    from services.auth_service import create_access_token
    config = get_auth_config()

    return jsonify({
        "access_token": create_access_token(user),
        "token_type": "Bearer",
        "expires_in": config.JWT_ACCESS_TOKEN_EXPIRES
    })


@bp.route('/me', methods=['GET'])
@require_auth
def get_me():
    """
    Get current authenticated user info.

    Response:
        {
            "username": "string",
            "role": "string",
            "email": "string",
            "full_name": "string",
            "permissions": ["string"]
        }
    """
    user = get_current_user()
    config = get_auth_config()

    user_data = user.to_dict()
    user_data['permissions'] = config.ROLE_PERMISSIONS.get(user.role, [])

    return jsonify(user_data)


@bp.route('/password', methods=['PUT'])
@require_auth
def update_password():
    """
    Change current user's password.

    Request body:
        {
            "current_password": "string",
            "new_password": "string"
        }

    Response:
        {"message": "Password changed successfully"}
    """
    user = get_current_user()
    data = request.get_json()

    if not data:
        return jsonify({"error": "Bad Request", "message": "JSON body required"}), 400

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({
            "error": "Bad Request",
            "message": "Current and new password required"
        }), 400

    success, error = change_password(user.username, current_password, new_password)
    if not success:
        return jsonify({
            "error": "Bad Request",
            "message": error
        }), 400

    return jsonify({"message": "Password changed successfully"})


# =============================================================================
# User Management Endpoints (Admin)
# =============================================================================

@bp.route('/users', methods=['GET'])
@require_auth
@require_role('management')
def list_users():
    """
    List all users (management and admin only).

    Query params:
        - role: Filter by role
        - active: Filter by active status (true/false)

    Response:
        {
            "users": [
                {
                    "username": "string",
                    "role": "string",
                    "email": "string",
                    "active": true,
                    "last_login": "string"
                }
            ],
            "count": 0
        }
    """
    store = get_user_store()
    users = store.list_all()

    # Apply filters
    role_filter = request.args.get('role')
    active_filter = request.args.get('active')

    if role_filter:
        users = [u for u in users if u.role == role_filter]

    if active_filter is not None:
        active_bool = active_filter.lower() == 'true'
        users = [u for u in users if u.active == active_bool]

    return jsonify({
        "users": [u.to_dict() for u in users],
        "count": len(users)
    })


@bp.route('/users', methods=['POST'])
@require_auth
@require_role('admin')
def create_user_endpoint():
    """
    Create new user (admin only).

    Request body:
        {
            "username": "string",
            "password": "string",
            "role": "operator|maintenance|management|admin",
            "email": "string",
            "full_name": "string"
        }

    Response:
        {
            "message": "User created successfully",
            "user": {...}
        }
    """
    current_user = get_current_user()
    data = request.get_json()

    if not data:
        return jsonify({"error": "Bad Request", "message": "JSON body required"}), 400

    required = ['username', 'password', 'role']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({
            "error": "Bad Request",
            "message": f"Missing required fields: {', '.join(missing)}"
        }), 400

    user, error = create_user(
        username=data['username'],
        password=data['password'],
        role=data['role'],
        email=data.get('email', ''),
        full_name=data.get('full_name', ''),
        created_by=current_user.username
    )

    if not user:
        return jsonify({
            "error": "Bad Request",
            "message": error
        }), 400

    return jsonify({
        "message": "User created successfully",
        "user": user.to_dict()
    }), 201


@bp.route('/users/<username>', methods=['GET'])
@require_auth
@require_role('management')
def get_user(username):
    """
    Get user details (management and admin only).

    Response:
        {
            "username": "string",
            "role": "string",
            "email": "string",
            "full_name": "string",
            "active": true,
            "created_at": "string",
            "last_login": "string"
        }
    """
    store = get_user_store()
    user = store.get(username)

    if not user:
        return jsonify({
            "error": "Not Found",
            "message": f"User {username} not found"
        }), 404

    return jsonify(user.to_dict())


@bp.route('/users/<username>', methods=['PUT'])
@require_auth
@require_role('admin')
def update_user(username):
    """
    Update user (admin only).

    Request body (all fields optional):
        {
            "role": "string",
            "email": "string",
            "full_name": "string",
            "active": true
        }

    Response:
        {
            "message": "User updated successfully",
            "user": {...}
        }
    """
    current_user = get_current_user()
    store = get_user_store()
    user = store.get(username)

    if not user:
        return jsonify({
            "error": "Not Found",
            "message": f"User {username} not found"
        }), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Bad Request", "message": "JSON body required"}), 400

    # Prevent demoting yourself
    if username == current_user.username and 'role' in data:
        if data['role'] != current_user.role:
            return jsonify({
                "error": "Forbidden",
                "message": "Cannot change your own role"
            }), 403

    # Update allowed fields
    if 'role' in data:
        config = get_auth_config()
        if data['role'] not in config.USER_ROLES:
            return jsonify({
                "error": "Bad Request",
                "message": f"Invalid role: {data['role']}"
            }), 400
        user.role = data['role']

    if 'email' in data:
        user.email = data['email']

    if 'full_name' in data:
        user.full_name = data['full_name']

    if 'active' in data:
        # Prevent disabling yourself
        if username == current_user.username and not data['active']:
            return jsonify({
                "error": "Forbidden",
                "message": "Cannot disable your own account"
            }), 403
        user.active = data['active']

    store.update(user)
    logger.info(f"User {username} updated by {current_user.username}")

    return jsonify({
        "message": "User updated successfully",
        "user": user.to_dict()
    })


@bp.route('/users/<username>', methods=['DELETE'])
@require_auth
@require_role('admin')
def delete_user(username):
    """
    Delete user (admin only).

    Response:
        {"message": "User deleted successfully"}
    """
    current_user = get_current_user()

    # Prevent self-deletion
    if username == current_user.username:
        return jsonify({
            "error": "Forbidden",
            "message": "Cannot delete your own account"
        }), 403

    store = get_user_store()
    if not store.delete(username):
        return jsonify({
            "error": "Not Found",
            "message": f"User {username} not found"
        }), 404

    return jsonify({"message": "User deleted successfully"})


@bp.route('/users/<username>/reset-password', methods=['POST'])
@require_auth
@require_role('admin')
def reset_user_password(username):
    """
    Reset user password (admin only).

    Request body:
        {
            "new_password": "string"
        }

    Response:
        {"message": "Password reset successfully"}
    """
    current_user = get_current_user()
    data = request.get_json()

    if not data or 'new_password' not in data:
        return jsonify({
            "error": "Bad Request",
            "message": "New password required"
        }), 400

    success, error = reset_password(
        username,
        data['new_password'],
        admin_user=current_user.username
    )

    if not success:
        return jsonify({
            "error": "Bad Request",
            "message": error
        }), 400

    return jsonify({"message": "Password reset successfully"})


@bp.route('/users/<username>/unlock', methods=['POST'])
@require_auth
@require_role('admin')
def unlock_user(username):
    """
    Unlock a locked user account (admin only).

    Response:
        {"message": "User account unlocked"}
    """
    store = get_user_store()
    user = store.get(username)

    if not user:
        return jsonify({
            "error": "Not Found",
            "message": f"User {username} not found"
        }), 404

    user.failed_attempts = 0
    user.locked_until = None
    store.update(user)

    current_user = get_current_user()
    logger.info(f"User {username} unlocked by {current_user.username}")

    return jsonify({"message": "User account unlocked"})


# =============================================================================
# Role and Permission Info
# =============================================================================

@bp.route('/roles', methods=['GET'])
@require_auth
def list_roles():
    """
    List available roles and their permissions.

    Response:
        {
            "roles": {
                "operator": {
                    "level": 1,
                    "permissions": [...]
                },
                ...
            }
        }
    """
    config = get_auth_config()

    roles = {}
    for role, level in config.USER_ROLES.items():
        roles[role] = {
            "level": level,
            "permissions": config.ROLE_PERMISSIONS.get(role, [])
        }

    return jsonify({"roles": roles})


# =============================================================================
# OIDC (Keycloak) Authentication Endpoints
# =============================================================================

def _get_keycloak():
    """Get Keycloak service (lazy import to avoid circular deps)."""
    try:
        from services.keycloak_service import get_keycloak_service
        return get_keycloak_service()
    except ImportError:
        return None


@bp.route('/oidc/config', methods=['GET'])
def oidc_config():
    """
    Get OIDC configuration for client setup.

    Response:
        {
            "enabled": true,
            "server_url": "http://localhost:8080",
            "realm": "cnc-scada",
            "client_id": "flask-scada",
            "discovery_url": "http://localhost:8080/realms/cnc-scada/.well-known/openid-configuration"
        }
    """
    keycloak = _get_keycloak()
    if not keycloak:
        return jsonify({
            "enabled": False,
            "message": "OIDC not configured"
        })

    return jsonify({
        "enabled": True,
        "server_url": keycloak.server_url,
        "realm": keycloak.realm,
        "client_id": keycloak.client_id,
        "discovery_url": f"{keycloak.realm_url}/.well-known/openid-configuration",
        "available": keycloak.is_available()
    })


@bp.route('/oidc/login', methods=['POST'])
def oidc_login():
    """
    Authenticate via Keycloak (Resource Owner Password Credentials).

    For production, use Authorization Code flow instead.

    Request body:
        {
            "username": "string",
            "password": "string"
        }

    Response:
        {
            "access_token": "string",
            "refresh_token": "string",
            "token_type": "Bearer",
            "expires_in": 300,
            "user": {
                "user_id": "string",
                "username": "string",
                "email": "string",
                "roles": ["string"]
            }
        }
    """
    keycloak = _get_keycloak()
    if not keycloak:
        return jsonify({
            "error": "Service Unavailable",
            "message": "OIDC authentication not configured"
        }), 503

    data = request.get_json()
    if not data:
        return jsonify({"error": "Bad Request", "message": "JSON body required"}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({
            "error": "Bad Request",
            "message": "Username and password required"
        }), 400

    token_info = keycloak.authenticate(username, password)
    if not token_info:
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid credentials"
        }), 401

    # Get user info from token
    user_info = keycloak.validate_token(token_info.access_token)

    response = {
        "access_token": token_info.access_token,
        "refresh_token": token_info.refresh_token,
        "token_type": token_info.token_type,
        "expires_in": token_info.expires_in,
        "scope": token_info.scope
    }

    if user_info:
        response["user"] = {
            "user_id": user_info.user_id,
            "username": user_info.username,
            "email": user_info.email,
            "name": user_info.name,
            "roles": user_info.roles,
            "groups": user_info.groups
        }

    logger.info(f"OIDC login successful for {username}")
    return jsonify(response)


@bp.route('/oidc/refresh', methods=['POST'])
def oidc_refresh():
    """
    Refresh Keycloak access token.

    Request body:
        {
            "refresh_token": "string"
        }

    Response:
        {
            "access_token": "string",
            "refresh_token": "string",
            "token_type": "Bearer",
            "expires_in": 300
        }
    """
    keycloak = _get_keycloak()
    if not keycloak:
        return jsonify({
            "error": "Service Unavailable",
            "message": "OIDC authentication not configured"
        }), 503

    data = request.get_json()
    if not data or 'refresh_token' not in data:
        return jsonify({
            "error": "Bad Request",
            "message": "Refresh token required"
        }), 400

    token_info = keycloak.refresh_token(data['refresh_token'])
    if not token_info:
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or expired refresh token"
        }), 401

    return jsonify({
        "access_token": token_info.access_token,
        "refresh_token": token_info.refresh_token,
        "token_type": token_info.token_type,
        "expires_in": token_info.expires_in
    })


@bp.route('/oidc/logout', methods=['POST'])
def oidc_logout():
    """
    Logout from Keycloak (invalidate tokens server-side).

    Request body:
        {
            "refresh_token": "string"
        }

    Response:
        {"message": "Logged out successfully"}
    """
    keycloak = _get_keycloak()
    if not keycloak:
        return jsonify({
            "error": "Service Unavailable",
            "message": "OIDC authentication not configured"
        }), 503

    data = request.get_json()
    if not data or 'refresh_token' not in data:
        return jsonify({
            "error": "Bad Request",
            "message": "Refresh token required"
        }), 400

    success = keycloak.logout(data['refresh_token'])
    if success:
        logger.info("OIDC logout successful")
        return jsonify({"message": "Logged out successfully"})
    else:
        return jsonify({
            "error": "Internal Server Error",
            "message": "Logout failed"
        }), 500


@bp.route('/oidc/userinfo', methods=['GET'])
def oidc_userinfo():
    """
    Get user info from OIDC access token.

    Headers:
        Authorization: Bearer <access_token>

    Response:
        {
            "user_id": "string",
            "username": "string",
            "email": "string",
            "name": "string",
            "roles": ["string"],
            "groups": ["string"]
        }
    """
    keycloak = _get_keycloak()
    if not keycloak:
        return jsonify({
            "error": "Service Unavailable",
            "message": "OIDC authentication not configured"
        }), 503

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({
            "error": "Unauthorized",
            "message": "Missing or invalid authorization header"
        }), 401

    token = auth_header[7:]
    user_info = keycloak.validate_token(token)

    if not user_info:
        return jsonify({
            "error": "Unauthorized",
            "message": "Invalid or expired token"
        }), 401

    return jsonify({
        "user_id": user_info.user_id,
        "username": user_info.username,
        "email": user_info.email,
        "name": user_info.name,
        "roles": user_info.roles,
        "groups": user_info.groups,
        "attributes": user_info.attributes
    })


@bp.route('/oidc/validate', methods=['POST'])
def oidc_validate():
    """
    Validate an OIDC access token.

    Request body:
        {
            "token": "string"
        }

    Response:
        {
            "valid": true,
            "user": {...}
        }
    """
    keycloak = _get_keycloak()
    if not keycloak:
        return jsonify({
            "error": "Service Unavailable",
            "message": "OIDC authentication not configured"
        }), 503

    data = request.get_json()
    if not data or 'token' not in data:
        return jsonify({
            "error": "Bad Request",
            "message": "Token required"
        }), 400

    user_info = keycloak.validate_token(data['token'])

    if not user_info:
        return jsonify({"valid": False})

    return jsonify({
        "valid": True,
        "user": {
            "user_id": user_info.user_id,
            "username": user_info.username,
            "roles": user_info.roles
        }
    })
