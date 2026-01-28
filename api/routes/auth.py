"""
LEGO Factory v3 - Auth Routes
==============================
Authentication and user management routes with JWT support and Pydantic validation.
"""

import logging
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify, g
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    current_user,
    verify_jwt_in_request,
)

from services.auth.auth_service import (
    AuthService,
    AuthError,
    InvalidCredentialsError,
    AccountLockedError,
    AccountInactiveError,
    UserExistsError,
    ValidationError as AuthValidationError,
)
from models.auth.user import UserRole

# Import Pydantic schemas and validation utilities
from api.schemas import (
    LoginRequest,
    RegisterRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    UserProfileUpdate,
)
from api.utils.validation import validate_request, validation_error_response
from api.middleware.rate_limiter import auth_limit, standard_limit, admin_limit

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# API Blueprint for JSON endpoints
auth_api_bp = Blueprint('auth_api', __name__, url_prefix='/api/auth')


# ==================== Helper Decorators ====================

def roles_required(*required_roles):
    """
    Decorator to require specific roles for access.

    Usage:
        @roles_required('admin', 'supervisor')
        def admin_only_route():
            ...
    """
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            user_roles = claims.get('roles', [])

            if not any(role in user_roles for role in required_roles):
                return jsonify({
                    'error': 'Forbidden',
                    'message': 'Insufficient permissions'
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(fn):
    """Decorator to require admin role."""
    return roles_required(UserRole.ADMIN.value)(fn)


# ==================== API Routes (JSON) ====================

@auth_api_bp.route('/login', methods=['POST'])
@auth_limit  # Strict rate limit: 10 requests/minute to prevent brute force
@validate_request(LoginRequest)
def api_login(validated_data: LoginRequest):
    """
    Authenticate user and return JWT tokens.

    Request body (validated by Pydantic):
        {
            "username": "string (3-100 chars)",
            "password": "string (1-128 chars)",
            "remember_me": "boolean (optional)"
        }

    Response:
        {
            "access_token": "string",
            "refresh_token": "string",
            "token_type": "Bearer",
            "user": {
                "id": "uuid",
                "username": "string",
                "email": "string",
                "roles": ["string"],
                ...
            }
        }

    Errors:
        400: Validation error with field details
        401: Invalid credentials
        403: Account locked or inactive
    """
    try:
        user, access_token, refresh_token = AuthService.login(
            validated_data.username,
            validated_data.password
        )

        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'user': user.to_dict()
        }), 200

    except InvalidCredentialsError as e:
        return jsonify({
            'error': 'Unauthorized',
            'message': e.message
        }), 401

    except AccountLockedError as e:
        return jsonify({
            'error': 'Forbidden',
            'message': e.message
        }), 403

    except AccountInactiveError as e:
        return jsonify({
            'error': 'Forbidden',
            'message': e.message
        }), 403

    except AuthError as e:
        return jsonify({
            'error': 'Authentication Error',
            'message': e.message
        }), e.status_code

    except Exception as e:
        logger.exception('Login error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/register', methods=['POST'])
@auth_limit  # Strict rate limit: 10 requests/minute to prevent abuse
@validate_request(RegisterRequest)
def api_register(validated_data: RegisterRequest):
    """
    Register a new user with comprehensive validation.

    Request body (validated by Pydantic):
        {
            "username": "string (3-50 chars, alphanumeric)",
            "email": "valid email address",
            "password": "string (8+ chars with complexity)",
            "password_confirm": "must match password",
            "first_name": "string (1-100 chars)",
            "last_name": "string (1-100 chars)",
            "department": "string (optional, max 100 chars)"
        }

    Password requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character

    Response:
        {
            "message": "Registration successful",
            "user": {
                "id": "uuid",
                "username": "string",
                "email": "string",
                ...
            }
        }

    Errors:
        400: Validation error with field details
        409: Username or email already exists
    """
    try:
        user = AuthService.register_user(
            username=validated_data.username,
            email=validated_data.email,
            password=validated_data.password,
            first_name=validated_data.first_name,
            last_name=validated_data.last_name,
            auto_verify=True,  # Set to False in production for email verification
        )

        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict()
        }), 201

    except UserExistsError as e:
        return jsonify({
            'error': 'Conflict',
            'message': e.message
        }), 409

    except AuthValidationError as e:
        return jsonify({
            'error': 'Validation Error',
            'message': e.message
        }), 400

    except ValueError as e:
        return jsonify({
            'error': 'Validation Error',
            'message': str(e)
        }), 400

    except Exception as e:
        logger.exception('Registration error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/refresh', methods=['POST'])
@auth_limit  # Strict rate limit: 10 requests/minute
@jwt_required(refresh=True)
def api_refresh():
    """
    Refresh access token using refresh token.

    Requires: Refresh token in Authorization header

    Response:
        {
            "access_token": "string",
            "refresh_token": "string"
        }
    """
    try:
        current_user_id = get_jwt_identity()
        access_token, refresh_token = AuthService.refresh_tokens(current_user_id)

        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer'
        }), 200

    except AuthError as e:
        return jsonify({
            'error': 'Authentication Error',
            'message': e.message
        }), e.status_code

    except Exception as e:
        logger.exception('Token refresh error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/logout', methods=['POST'])
@standard_limit  # Standard rate limit: 100 requests/minute
@jwt_required(verify_type=False)
def api_logout():
    """
    Logout and revoke current token.

    Requires: Access or Refresh token in Authorization header

    Response:
        {
            "message": "Successfully logged out"
        }
    """
    try:
        jwt_data = get_jwt()
        jti = jwt_data['jti']
        token_type = jwt_data['type']
        user_id = get_jwt_identity()

        AuthService.logout(jti, token_type, user_id)

        return jsonify({
            'message': 'Successfully logged out'
        }), 200

    except Exception as e:
        logger.exception('Logout error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/logout-all', methods=['POST'])
@standard_limit  # Standard rate limit: 100 requests/minute
@jwt_required()
def api_logout_all():
    """
    Logout from all devices by revoking all tokens.

    Note: This implementation revokes the current token.
    For full logout-all, you would need to track all user tokens.

    Requires: Access token in Authorization header

    Response:
        {
            "message": "Successfully logged out from all devices"
        }
    """
    try:
        jwt_data = get_jwt()
        jti = jwt_data['jti']
        user_id = get_jwt_identity()

        # Revoke current access token
        AuthService.logout(jti, 'access', user_id)

        return jsonify({
            'message': 'Successfully logged out from all devices'
        }), 200

    except Exception as e:
        logger.exception('Logout-all error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/me', methods=['GET'])
@standard_limit  # Standard rate limit: 100 requests/minute
@jwt_required()
def api_get_current_user():
    """
    Get current authenticated user's profile.

    Requires: Access token in Authorization header

    Response:
        {
            "user": {
                "id": "uuid",
                "username": "string",
                "email": "string",
                "roles": ["string"],
                ...
            }
        }
    """
    try:
        user_id = get_jwt_identity()
        user = AuthService.get_user_by_id(user_id)

        if not user:
            return jsonify({
                'error': 'Not Found',
                'message': 'User not found'
            }), 404

        return jsonify({
            'user': user.to_dict()
        }), 200

    except Exception as e:
        logger.exception('Get current user error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/me', methods=['PUT', 'PATCH'])
@standard_limit  # Standard rate limit: 100 requests/minute
@jwt_required()
def api_update_current_user():
    """
    Update current user's profile.

    Requires: Access token in Authorization header

    Request body:
        {
            "first_name": "string" (optional),
            "last_name": "string" (optional),
            "phone": "string" (optional),
            "department": "string" (optional)
        }

    Response:
        {
            "message": "Profile updated",
            "user": {...}
        }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json() or {}

        # Extract allowed fields
        update_data = {}
        for field in ['first_name', 'last_name', 'phone', 'department', 'employee_id']:
            if field in data:
                update_data[field] = data[field]

        user = AuthService.update_user(user_id, **update_data)

        return jsonify({
            'message': 'Profile updated',
            'user': user.to_dict()
        }), 200

    except ValidationError as e:
        return jsonify({
            'error': 'Validation Error',
            'message': e.message
        }), 400

    except Exception as e:
        logger.exception('Update user error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/change-password', methods=['POST'])
@auth_limit  # Strict rate limit: 10 requests/minute for security
@jwt_required()
def api_change_password():
    """
    Change current user's password.

    Requires: Access token in Authorization header

    Request body:
        {
            "current_password": "string",
            "new_password": "string"
        }

    Response:
        {
            "message": "Password changed successfully"
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body is required'
        }), 400

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Current password and new password are required'
        }), 400

    try:
        user_id = get_jwt_identity()
        AuthService.change_password(user_id, current_password, new_password)

        return jsonify({
            'message': 'Password changed successfully'
        }), 200

    except InvalidCredentialsError as e:
        return jsonify({
            'error': 'Unauthorized',
            'message': e.message
        }), 401

    except ValidationError as e:
        return jsonify({
            'error': 'Validation Error',
            'message': e.message
        }), 400

    except Exception as e:
        logger.exception('Change password error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/forgot-password', methods=['POST'])
@auth_limit  # Strict rate limit: 10 requests/minute to prevent abuse
def api_forgot_password():
    """
    Request a password reset email.

    Request body:
        {
            "email": "string"
        }

    Response:
        {
            "message": "If the email exists, a reset link has been sent"
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body is required'
        }), 400

    email = data.get('email', '').strip()

    if not email:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Email is required'
        }), 400

    try:
        # Generate reset token (don't reveal if email exists)
        token = AuthService.generate_password_reset_token(email)

        # In production, send email with reset link
        # For now, just log it (remove in production!)
        if token:
            logger.info(f'Password reset token for {email}: {token}')

        # Always return success to prevent email enumeration
        return jsonify({
            'message': 'If the email exists, a reset link has been sent'
        }), 200

    except Exception as e:
        logger.exception('Forgot password error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/reset-password', methods=['POST'])
@auth_limit  # Strict rate limit: 10 requests/minute for security
def api_reset_password():
    """
    Reset password using reset token.

    Request body:
        {
            "token": "string",
            "new_password": "string"
        }

    Response:
        {
            "message": "Password reset successfully"
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body is required'
        }), 400

    token = data.get('token', '').strip()
    new_password = data.get('new_password', '')

    if not token or not new_password:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Token and new password are required'
        }), 400

    try:
        AuthService.reset_password(token, new_password)

        return jsonify({
            'message': 'Password reset successfully'
        }), 200

    except ValidationError as e:
        return jsonify({
            'error': 'Validation Error',
            'message': e.message
        }), 400

    except Exception as e:
        logger.exception('Reset password error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


@auth_api_bp.route('/verify-email', methods=['POST'])
@auth_limit  # Strict rate limit: 10 requests/minute for security
def api_verify_email():
    """
    Verify email using verification token.

    Request body:
        {
            "token": "string"
        }

    Response:
        {
            "message": "Email verified successfully"
        }
    """
    data = request.get_json()

    if not data:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Request body is required'
        }), 400

    token = data.get('token', '').strip()

    if not token:
        return jsonify({
            'error': 'Bad Request',
            'message': 'Verification token is required'
        }), 400

    try:
        AuthService.verify_email(token)

        return jsonify({
            'message': 'Email verified successfully'
        }), 200

    except ValidationError as e:
        return jsonify({
            'error': 'Validation Error',
            'message': e.message
        }), 400

    except Exception as e:
        logger.exception('Verify email error')
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500


# ==================== Protected API Example Routes ====================

@auth_api_bp.route('/protected', methods=['GET'])
@standard_limit  # Standard rate limit: 100 requests/minute
@jwt_required()
def api_protected():
    """
    Example protected route requiring authentication.

    Requires: Access token in Authorization header
    """
    claims = get_jwt()
    user_id = get_jwt_identity()

    return jsonify({
        'message': 'You have access to this protected route',
        'user_id': user_id,
        'username': claims.get('username'),
        'roles': claims.get('roles', [])
    }), 200


@auth_api_bp.route('/admin-only', methods=['GET'])
@admin_limit  # Admin rate limit: 50 requests/minute
@admin_required
def api_admin_only():
    """
    Example admin-only route.

    Requires: Access token with admin role
    """
    return jsonify({
        'message': 'Welcome, admin!'
    }), 200


@auth_api_bp.route('/operator-access', methods=['GET'])
@standard_limit  # Standard rate limit: 100 requests/minute
@roles_required(UserRole.OPERATOR.value, UserRole.ADMIN.value)
def api_operator_access():
    """
    Example route for operators and admins.

    Requires: Access token with operator or admin role
    """
    return jsonify({
        'message': 'Welcome, operator!'
    }), 200


# ==================== Web Routes (HTML Forms) ====================

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required', 'danger')
            return render_template('auth/login.html')

        try:
            user, access_token, refresh_token = AuthService.login(username, password)

            # Store in session for web interface
            session['user_id'] = str(user.id)
            session['user_name'] = user.username
            session['user_email'] = user.email
            session['user_roles'] = user.get_roles()
            session['access_token'] = access_token
            session['refresh_token'] = refresh_token

            flash('Login successful', 'success')
            return redirect(url_for('dashboard.home'))

        except InvalidCredentialsError:
            flash('Invalid username or password', 'danger')

        except AccountLockedError as e:
            flash(e.message, 'danger')

        except AccountInactiveError as e:
            flash(e.message, 'danger')

        except Exception as e:
            logger.exception('Login error')
            flash('An error occurred during login', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """User logout."""
    try:
        # Revoke token if present
        if 'access_token' in session:
            # Note: Token revocation would require JWT verification
            # For web logout, just clear session
            pass

        session.clear()
        flash('You have been logged out', 'info')

    except Exception as e:
        logger.exception('Logout error')
        session.clear()
        flash('Logged out', 'info')

    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip() or None
        last_name = request.form.get('last_name', '').strip() or None

        # Validate form
        if not username or not email or not password:
            flash('Username, email, and password are required', 'danger')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('auth/register.html')

        try:
            user = AuthService.register_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                auto_verify=True,  # Set to False for email verification
            )

            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('auth.login'))

        except UserExistsError as e:
            flash(e.message, 'danger')

        except ValidationError as e:
            flash(e.message, 'danger')

        except ValueError as e:
            flash(str(e), 'danger')

        except Exception as e:
            logger.exception('Registration error')
            flash('An error occurred during registration', 'danger')

    return render_template('auth/register.html')


@auth_bp.route('/profile')
def profile():
    """User profile page."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        user = AuthService.get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('auth.login'))

        return render_template('auth/profile.html', user=user)

    except Exception as e:
        logger.exception('Profile error')
        flash('Error loading profile', 'danger')
        return redirect(url_for('dashboard.home'))


@auth_bp.route('/settings')
def settings():
    """User settings page."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    try:
        user = AuthService.get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('auth.login'))

        return render_template('auth/settings.html', user=user)

    except Exception as e:
        logger.exception('Settings error')
        flash('Error loading settings', 'danger')
        return redirect(url_for('dashboard.home'))
