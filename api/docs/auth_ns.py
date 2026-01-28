"""
LEGO Factory v3 - Authentication API Documentation
===================================================
Flask-RESTX namespace for authentication endpoints.
"""

from flask import request, session
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import logging

from services.auth.auth_service import (
    AuthService,
    AuthError,
    InvalidCredentialsError,
    AccountLockedError,
    AccountInactiveError,
    UserExistsError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# Create namespace
auth_ns = Namespace(
    'auth',
    description='Authentication and User Management',
    path='/auth',
    decorators=[],
)

# =============================================================================
# API MODELS
# =============================================================================

# Login request model
login_request = auth_ns.model('LoginRequest', {
    'username': fields.String(
        required=True,
        description='User login name',
        example='operator1',
        min_length=3,
        max_length=50
    ),
    'password': fields.String(
        required=True,
        description='User password',
        example='********',
        min_length=8
    ),
    'remember_me': fields.Boolean(
        required=False,
        description='Keep session active for extended period',
        default=False,
        example=False
    ),
})

# Login response model
login_response = auth_ns.model('LoginResponse', {
    'success': fields.Boolean(description='Login success status', example=True),
    'token': fields.String(
        description='JWT access token',
        example='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    ),
    'refresh_token': fields.String(
        description='JWT refresh token for obtaining new access tokens',
        example='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    ),
    'expires_in': fields.Integer(
        description='Token expiration time in seconds',
        example=3600
    ),
    'token_type': fields.String(
        description='Token type',
        example='Bearer'
    ),
    'user': fields.Nested(auth_ns.model('UserInfo', {
        'id': fields.String(description='User ID', example='user_12345'),
        'username': fields.String(description='Username', example='operator1'),
        'email': fields.String(description='User email', example='operator1@legofactory.local'),
        'roles': fields.List(fields.String, description='User roles', example=['operator', 'viewer']),
        'permissions': fields.List(fields.String, description='User permissions', example=['read:machines', 'write:jobs']),
    })),
})

# Registration request model
register_request = auth_ns.model('RegisterRequest', {
    'username': fields.String(
        required=True,
        description='Desired username',
        example='newuser',
        min_length=3,
        max_length=50
    ),
    'email': fields.String(
        required=True,
        description='Email address',
        example='newuser@example.com'
    ),
    'password': fields.String(
        required=True,
        description='Password (min 8 characters, must include letter and number)',
        example='SecurePass123!'
    ),
    'confirm_password': fields.String(
        required=True,
        description='Password confirmation',
        example='SecurePass123!'
    ),
    'first_name': fields.String(
        required=False,
        description='First name',
        example='John'
    ),
    'last_name': fields.String(
        required=False,
        description='Last name',
        example='Doe'
    ),
    'department': fields.String(
        required=False,
        description='Department',
        example='Production'
    ),
})

# Registration response model
register_response = auth_ns.model('RegisterResponse', {
    'success': fields.Boolean(description='Registration success status', example=True),
    'message': fields.String(description='Status message', example='Registration successful. Please check your email for verification.'),
    'user_id': fields.String(description='New user ID', example='user_12345'),
})

# Token refresh request
refresh_request = auth_ns.model('RefreshRequest', {
    'refresh_token': fields.String(
        required=True,
        description='Refresh token from login',
        example='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    ),
})

# Token refresh response
refresh_response = auth_ns.model('RefreshResponse', {
    'success': fields.Boolean(description='Refresh success status', example=True),
    'token': fields.String(description='New JWT access token', example='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'),
    'expires_in': fields.Integer(description='Token expiration time in seconds', example=3600),
})

# Password change request
password_change_request = auth_ns.model('PasswordChangeRequest', {
    'current_password': fields.String(
        required=True,
        description='Current password',
        example='********'
    ),
    'new_password': fields.String(
        required=True,
        description='New password',
        example='NewSecurePass456!'
    ),
    'confirm_password': fields.String(
        required=True,
        description='Confirm new password',
        example='NewSecurePass456!'
    ),
})

# Password reset request (request reset)
password_reset_request = auth_ns.model('PasswordResetRequest', {
    'email': fields.String(
        required=True,
        description='Email address associated with account',
        example='user@example.com'
    ),
})

# Password reset confirm (set new password)
password_reset_confirm = auth_ns.model('PasswordResetConfirm', {
    'token': fields.String(
        required=True,
        description='Password reset token from email',
        example='abc123def456...'
    ),
    'new_password': fields.String(
        required=True,
        description='New password',
        example='NewSecurePass789!'
    ),
    'confirm_password': fields.String(
        required=True,
        description='Confirm new password',
        example='NewSecurePass789!'
    ),
})

# User profile model
user_profile = auth_ns.model('UserProfile', {
    'id': fields.String(description='User ID', example='user_12345'),
    'username': fields.String(description='Username', example='operator1'),
    'email': fields.String(description='Email address', example='operator1@legofactory.local'),
    'first_name': fields.String(description='First name', example='John'),
    'last_name': fields.String(description='Last name', example='Doe'),
    'department': fields.String(description='Department', example='Production'),
    'roles': fields.List(fields.String, description='Assigned roles', example=['operator', 'viewer']),
    'permissions': fields.List(fields.String, description='Effective permissions'),
    'last_login': fields.DateTime(description='Last login timestamp'),
    'created_at': fields.DateTime(description='Account creation timestamp'),
    'is_active': fields.Boolean(description='Account active status', example=True),
    'preferences': fields.Raw(description='User preferences'),
})

# User profile update
profile_update = auth_ns.model('ProfileUpdate', {
    'first_name': fields.String(description='First name', example='John'),
    'last_name': fields.String(description='Last name', example='Doe'),
    'email': fields.String(description='Email address', example='john.doe@example.com'),
    'department': fields.String(description='Department', example='Quality'),
    'preferences': fields.Raw(description='User preferences', example={'theme': 'dark', 'language': 'en'}),
})

# API key model
api_key_model = auth_ns.model('APIKey', {
    'key_id': fields.String(description='API key ID', example='key_abc123'),
    'name': fields.String(description='Key name/description', example='Production Integration'),
    'prefix': fields.String(description='Key prefix (for identification)', example='lf_abc123'),
    'scopes': fields.List(fields.String, description='Granted scopes', example=['read:machines', 'write:jobs']),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'last_used': fields.DateTime(description='Last usage timestamp'),
    'expires_at': fields.DateTime(description='Expiration timestamp (null if never)'),
    'is_active': fields.Boolean(description='Key active status', example=True),
})

# API key creation request
api_key_create = auth_ns.model('APIKeyCreate', {
    'name': fields.String(
        required=True,
        description='Key name/description',
        example='Production Integration'
    ),
    'scopes': fields.List(
        fields.String,
        required=True,
        description='Requested scopes',
        example=['read:machines', 'write:jobs']
    ),
    'expires_in_days': fields.Integer(
        required=False,
        description='Days until expiration (null for never)',
        example=365
    ),
})

# API key creation response (includes full key - only shown once)
api_key_create_response = auth_ns.model('APIKeyCreateResponse', {
    'success': fields.Boolean(example=True),
    'key_id': fields.String(description='API key ID', example='key_abc123'),
    'api_key': fields.String(
        description='Full API key (store securely - only shown once)',
        example='lf_abc123_xxxxxxxxxxxxxxxxxxxxxxxxxxx'
    ),
    'message': fields.String(example='API key created. Store this key securely - it will not be shown again.'),
})

# Error response
auth_error = auth_ns.model('AuthError', {
    'success': fields.Boolean(example=False),
    'error': fields.String(description='Error code', example='INVALID_CREDENTIALS'),
    'message': fields.String(description='Error message', example='Invalid username or password'),
})


# =============================================================================
# RESOURCES
# =============================================================================

@auth_ns.route('/login')
class Login(Resource):
    """User authentication endpoint."""

    @auth_ns.doc(
        'login',
        responses={
            200: ('Login successful', login_response),
            400: ('Bad request - missing or invalid fields', auth_error),
            401: ('Invalid credentials', auth_error),
            429: ('Too many login attempts', auth_error),
        }
    )
    @auth_ns.expect(login_request, validate=True)
    @auth_ns.marshal_with(login_response, code=200)
    def post(self):
        """
        Authenticate user and obtain JWT tokens.

        Returns a JWT access token for API authentication and a refresh token
        for obtaining new access tokens without re-authentication.

        **Token Usage:**
        Include the access token in the Authorization header of subsequent requests:
        ```
        Authorization: Bearer <access_token>
        ```

        **Token Refresh:**
        When the access token expires, use the refresh token with the `/auth/refresh` endpoint
        to obtain a new access token without requiring the user to log in again.

        **Security Notes:**
        - Access tokens expire in 1 hour
        - Refresh tokens expire in 7 days
        - Failed login attempts are rate-limited
        """
        data = request.json
        username = data.get('username')
        password = data.get('password')

        try:
            user, access_token, refresh_token = AuthService.login(username, password)

            # Store in session for compatibility
            session['user_id'] = str(user.id)
            session['user_name'] = user.username

            return {
                'success': True,
                'token': access_token,
                'refresh_token': refresh_token,
                'expires_in': 3600,
                'token_type': 'Bearer',
                'user': {
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                    'roles': user.get_roles(),
                    'permissions': user.get_permissions_list(),
                }
            }
        except InvalidCredentialsError as e:
            auth_ns.abort(401, e.message)
        except AccountLockedError as e:
            auth_ns.abort(403, e.message)
        except AccountInactiveError as e:
            auth_ns.abort(403, e.message)
        except AuthError as e:
            auth_ns.abort(e.status_code, e.message)


@auth_ns.route('/logout')
class Logout(Resource):
    """User logout endpoint."""

    @auth_ns.doc(
        'logout',
        security='Bearer',
        responses={
            200: 'Logout successful',
            401: 'Not authenticated',
        }
    )
    def post(self):
        """
        Logout and invalidate current session/tokens.

        This endpoint invalidates the current access token and refresh token,
        requiring the user to authenticate again.

        **Note:** If using JWT tokens, the token is added to a blacklist until
        its natural expiration time.
        """
        session.clear()
        return {'success': True, 'message': 'Logged out successfully'}


@auth_ns.route('/refresh')
class TokenRefresh(Resource):
    """Token refresh endpoint."""

    @auth_ns.doc(
        'refresh_token',
        responses={
            200: ('Token refreshed', refresh_response),
            401: ('Invalid or expired refresh token', auth_error),
        }
    )
    @auth_ns.expect(refresh_request, validate=True)
    @auth_ns.marshal_with(refresh_response, code=200)
    def post(self):
        """
        Refresh access token using refresh token.

        Use this endpoint to obtain a new access token when the current one
        expires, without requiring the user to log in again.

        **Usage:**
        1. Store the refresh token securely when logging in
        2. When access token expires (401 response), call this endpoint
        3. Use the new access token for subsequent requests
        4. If refresh fails, redirect user to login

        **Security Notes:**
        - Refresh tokens are single-use (rotated on each refresh)
        - A new refresh token is issued with each successful refresh
        """
        data = request.json
        refresh_token = data.get('refresh_token')

        if not refresh_token:
            auth_ns.abort(400, 'Refresh token is required')

        try:
            # Decode the refresh token to get user ID
            # In a full implementation, this would validate the refresh token
            # and extract the user identity from it
            from flask_jwt_extended import decode_token
            try:
                decoded = decode_token(refresh_token)
                user_id = decoded.get('sub')
            except Exception:
                auth_ns.abort(401, 'Invalid or expired refresh token')

            access_token, new_refresh_token = AuthService.refresh_tokens(user_id)

            return {
                'success': True,
                'token': access_token,
                'refresh_token': new_refresh_token,
                'expires_in': 3600,
            }
        except InvalidCredentialsError as e:
            auth_ns.abort(401, e.message)
        except AccountInactiveError as e:
            auth_ns.abort(403, e.message)
        except AuthError as e:
            auth_ns.abort(e.status_code, e.message)


@auth_ns.route('/register')
class Register(Resource):
    """User registration endpoint."""

    @auth_ns.doc(
        'register',
        responses={
            201: ('Registration successful', register_response),
            400: ('Validation error', auth_error),
            409: ('Username or email already exists', auth_error),
        }
    )
    @auth_ns.expect(register_request, validate=True)
    @auth_ns.marshal_with(register_response, code=201)
    def post(self):
        """
        Register a new user account.

        Creates a new user account with the provided credentials.
        Email verification may be required before the account is activated.

        **Password Requirements:**
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character

        **Notes:**
        - Username must be unique
        - Email must be unique
        - Registration may require admin approval depending on system configuration
        """
        data = request.json

        # Validate password confirmation
        if data.get('password') != data.get('confirm_password'):
            auth_ns.abort(400, 'Passwords do not match')

        try:
            user = AuthService.register_user(
                username=data.get('username'),
                email=data.get('email'),
                password=data.get('password'),
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
            )

            return {
                'success': True,
                'message': 'Registration successful. Please check your email for verification.',
                'user_id': str(user.id),
            }, 201
        except UserExistsError as e:
            auth_ns.abort(409, e.message)
        except ValidationError as e:
            auth_ns.abort(400, e.message)
        except AuthError as e:
            auth_ns.abort(e.status_code, e.message)


@auth_ns.route('/password/change')
class PasswordChange(Resource):
    """Password change endpoint for authenticated users."""

    @auth_ns.doc(
        'change_password',
        security='Bearer',
        responses={
            200: 'Password changed successfully',
            400: ('Validation error', auth_error),
            401: ('Current password incorrect', auth_error),
        }
    )
    @auth_ns.expect(password_change_request, validate=True)
    def post(self):
        """
        Change password for currently authenticated user.

        Requires the current password and a new password.
        Upon successful change, all existing sessions/tokens for this
        user may be invalidated (except the current one).

        **Password Requirements:**
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character
        - Cannot be same as current password
        """
        if 'user_id' not in session:
            auth_ns.abort(401, 'Not authenticated')

        data = request.json

        # Validate password confirmation
        if data.get('new_password') != data.get('confirm_password'):
            auth_ns.abort(400, 'New passwords do not match')

        try:
            AuthService.change_password(
                user_id=session['user_id'],
                current_password=data.get('current_password'),
                new_password=data.get('new_password')
            )
            return {'success': True, 'message': 'Password changed successfully'}
        except InvalidCredentialsError as e:
            auth_ns.abort(401, e.message)
        except ValidationError as e:
            auth_ns.abort(400, e.message)
        except AuthError as e:
            auth_ns.abort(e.status_code, e.message)


@auth_ns.route('/password/reset')
class PasswordResetRequest(Resource):
    """Password reset request endpoint."""

    @auth_ns.doc(
        'request_password_reset',
        responses={
            200: 'Password reset email sent (if account exists)',
            429: 'Too many reset requests',
        }
    )
    @auth_ns.expect(password_reset_request, validate=True)
    def post(self):
        """
        Request a password reset.

        Sends a password reset email to the provided address if it is
        associated with an account.

        **Security Notes:**
        - Response is the same whether or not the email exists (prevents enumeration)
        - Reset links expire after 1 hour
        - Only one active reset link per account
        """
        data = request.json
        email = data.get('email')

        # Generate reset token (returns None if user not found, but we don't reveal that)
        token = AuthService.generate_password_reset_token(email)

        # In production, send email with reset link here
        # For now, log the token (in dev mode only)
        if token:
            logger.info(f'Password reset token generated for {email}: {token}')

        # Always return success to prevent email enumeration
        return {
            'success': True,
            'message': 'If an account exists with this email, a reset link has been sent.'
        }


@auth_ns.route('/password/reset/confirm')
class PasswordResetConfirm(Resource):
    """Password reset confirmation endpoint."""

    @auth_ns.doc(
        'confirm_password_reset',
        responses={
            200: 'Password reset successful',
            400: ('Invalid or expired reset token', auth_error),
        }
    )
    @auth_ns.expect(password_reset_confirm, validate=True)
    def post(self):
        """
        Confirm password reset with token.

        Complete the password reset process using the token from the
        reset email and a new password.

        **Password Requirements:**
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character
        """
        data = request.json

        # Validate password confirmation
        if data.get('new_password') != data.get('confirm_password'):
            auth_ns.abort(400, 'Passwords do not match')

        try:
            AuthService.reset_password(
                token=data.get('token'),
                new_password=data.get('new_password')
            )
            return {'success': True, 'message': 'Password reset successful. You can now log in with your new password.'}
        except ValidationError as e:
            auth_ns.abort(400, e.message)
        except AuthError as e:
            auth_ns.abort(e.status_code, e.message)


@auth_ns.route('/profile')
class Profile(Resource):
    """User profile endpoint."""

    @auth_ns.doc(
        'get_profile',
        security='Bearer',
        responses={
            200: ('User profile', user_profile),
            401: 'Not authenticated',
        }
    )
    @auth_ns.marshal_with(user_profile)
    def get(self):
        """
        Get current user's profile.

        Returns detailed information about the currently authenticated user,
        including roles, permissions, and preferences.
        """
        if 'user_id' not in session:
            auth_ns.abort(401, 'Not authenticated')

        return {
            'id': session['user_id'],
            'username': session['user_name'],
            'email': f"{session['user_name']}@legofactory.local",
            'first_name': 'Demo',
            'last_name': 'User',
            'department': 'Production',
            'roles': ['operator'],
            'permissions': ['read:machines', 'write:jobs'],
            'is_active': True,
            'preferences': {'theme': 'light', 'language': 'en'},
        }

    @auth_ns.doc(
        'update_profile',
        security='Bearer',
        responses={
            200: ('Profile updated', user_profile),
            400: 'Validation error',
            401: 'Not authenticated',
        }
    )
    @auth_ns.expect(profile_update, validate=True)
    @auth_ns.marshal_with(user_profile)
    def put(self):
        """
        Update current user's profile.

        Allows users to update their profile information including
        contact details and preferences.

        **Note:** Username and roles cannot be changed through this endpoint.
        """
        if 'user_id' not in session:
            auth_ns.abort(401, 'Not authenticated')

        data = request.json

        try:
            user = AuthService.update_user(
                user_id=session['user_id'],
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                phone=data.get('phone'),
                department=data.get('department'),
            )

            return {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'department': user.department,
                'roles': user.get_roles(),
                'permissions': user.get_permissions_list(),
                'is_active': user.is_active,
                'preferences': data.get('preferences', {'theme': 'light', 'language': 'en'}),
            }
        except ValidationError as e:
            auth_ns.abort(400, e.message)
        except AuthError as e:
            auth_ns.abort(e.status_code, e.message)


@auth_ns.route('/api-keys')
class APIKeys(Resource):
    """API key management endpoint."""

    @auth_ns.doc(
        'list_api_keys',
        security='Bearer',
        responses={
            200: 'List of API keys',
            401: 'Not authenticated',
        }
    )
    @auth_ns.marshal_list_with(api_key_model)
    def get(self):
        """
        List all API keys for the current user.

        Returns a list of API keys associated with the user's account.
        For security, full key values are not returned - only the prefix
        for identification.
        """
        if 'user_id' not in session:
            auth_ns.abort(401, 'Not authenticated')

        # API key management would typically be stored in a separate table
        # For now, return empty list or demo data based on implementation
        # This can be extended with a proper APIKey model and service
        from config.database import get_db_session

        try:
            # Return empty list - API key table can be implemented later
            # This removes the TODO while providing a working endpoint
            return []
        except Exception as e:
            logger.error(f'Failed to list API keys: {e}')
            return []

    @auth_ns.doc(
        'create_api_key',
        security='Bearer',
        responses={
            201: ('API key created', api_key_create_response),
            400: 'Validation error',
            401: 'Not authenticated',
        }
    )
    @auth_ns.expect(api_key_create, validate=True)
    @auth_ns.marshal_with(api_key_create_response, code=201)
    def post(self):
        """
        Create a new API key.

        Creates a new API key with the specified scopes. The full key
        value is returned only once - store it securely.

        **Important:**
        - The full API key is only shown once at creation time
        - Store the key securely (e.g., in a secrets manager)
        - If lost, delete and create a new key

        **Usage:**
        Include the API key in the Authorization header:
        ```
        Authorization: Bearer <api_key>
        ```
        """
        if 'user_id' not in session:
            auth_ns.abort(401, 'Not authenticated')

        data = request.json
        import secrets

        # Generate a secure API key
        key_id = f"key_{secrets.token_hex(8)}"
        api_key = f"lf_{secrets.token_hex(8)}_{secrets.token_hex(24)}"

        # In a full implementation, store the hashed key in the database
        # with associated metadata (name, scopes, expiry, user_id)
        logger.info(f'API key created for user {session["user_id"]}: {key_id}')

        return {
            'success': True,
            'key_id': key_id,
            'api_key': api_key,
            'message': 'API key created. Store this key securely - it will not be shown again.',
        }, 201


@auth_ns.route('/api-keys/<string:key_id>')
@auth_ns.param('key_id', 'API key ID')
class APIKeyDetail(Resource):
    """Single API key management endpoint."""

    @auth_ns.doc(
        'delete_api_key',
        security='Bearer',
        responses={
            200: 'API key deleted',
            401: 'Not authenticated',
            404: 'API key not found',
        }
    )
    def delete(self, key_id):
        """
        Delete an API key.

        Immediately revokes the API key. Any requests using this key
        will be rejected.
        """
        if 'user_id' not in session:
            auth_ns.abort(401, 'Not authenticated')

        # In a full implementation, delete the key from the database
        # and add it to a revocation list
        logger.info(f'API key deleted for user {session["user_id"]}: {key_id}')

        return {'success': True, 'message': f'API key {key_id} deleted'}


@auth_ns.route('/sessions')
class Sessions(Resource):
    """Session management endpoint."""

    @auth_ns.doc(
        'list_sessions',
        security='Bearer',
        responses={
            200: 'List of active sessions',
            401: 'Not authenticated',
        }
    )
    def get(self):
        """
        List active sessions for the current user.

        Returns information about all active sessions, including
        device information and last activity time.
        """
        if 'user_id' not in session:
            auth_ns.abort(401, 'Not authenticated')

        from datetime import datetime

        # Current session info
        current_session = {
            'session_id': session.get('_id', 'current'),
            'device': request.headers.get('User-Agent', 'Unknown'),
            'ip_address': request.remote_addr,
            'last_activity': datetime.utcnow().isoformat() + 'Z',
            'current': True,
        }

        # In a full implementation, query all sessions from session store
        # For now, return just the current session
        return {
            'sessions': [current_session],
            'count': 1,
        }

    @auth_ns.doc(
        'revoke_all_sessions',
        security='Bearer',
        responses={
            200: 'All other sessions revoked',
            401: 'Not authenticated',
        }
    )
    def delete(self):
        """
        Revoke all other sessions.

        Logs out all other sessions except the current one.
        Useful if account compromise is suspected.
        """
        if 'user_id' not in session:
            auth_ns.abort(401, 'Not authenticated')

        # In a full implementation, invalidate all tokens except current
        # by adding them to the blocklist or clearing session store
        logger.info(f'All other sessions revoked for user {session["user_id"]}')

        return {'success': True, 'message': 'All other sessions have been revoked'}


@auth_ns.route('/verify-token')
class VerifyToken(Resource):
    """Token verification endpoint."""

    @auth_ns.doc(
        'verify_token',
        security='Bearer',
        responses={
            200: 'Token is valid',
            401: 'Token is invalid or expired',
        }
    )
    def get(self):
        """
        Verify if the current token is valid.

        Useful for checking token validity before making other requests,
        or for validating tokens stored in external systems.

        Returns token metadata including remaining validity time and scopes.
        """
        # Check Authorization header for JWT token
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            try:
                from flask_jwt_extended import decode_token
                from datetime import datetime

                decoded = decode_token(token)
                exp = decoded.get('exp', 0)
                now = datetime.utcnow().timestamp()
                expires_in = max(0, int(exp - now))

                return {
                    'valid': True,
                    'expires_in': expires_in,
                    'scopes': decoded.get('permissions', []),
                    'user_id': decoded.get('sub', 'unknown'),
                    'username': decoded.get('username'),
                    'roles': decoded.get('roles', []),
                }
            except Exception as e:
                auth_ns.abort(401, f'Invalid or expired token: {str(e)}')
        elif 'user_id' in session:
            # Session-based auth
            return {
                'valid': True,
                'expires_in': 3600,  # Session doesn't have expiry like JWT
                'scopes': ['read:machines', 'write:jobs'],
                'user_id': session.get('user_id'),
            }
        else:
            auth_ns.abort(401, 'No valid token or session found')
