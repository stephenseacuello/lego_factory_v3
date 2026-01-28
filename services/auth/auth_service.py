"""
LEGO Factory v3 - Authentication Service
=========================================
Handles user registration, login validation, and token management.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from uuid import UUID

from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from config.database import get_db_session
from config.settings import get_config
from config.logging_config import get_structured_logger
from models.auth.user import User, TokenBlocklist, UserStatus, UserRole

logger = get_structured_logger(__name__)


class AuthError(Exception):
    """Base exception for authentication errors."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class InvalidCredentialsError(AuthError):
    """Raised when login credentials are invalid."""

    def __init__(self, message: str = 'Invalid username or password'):
        super().__init__(message, status_code=401)


class AccountLockedError(AuthError):
    """Raised when account is locked due to failed attempts."""

    def __init__(self, message: str = 'Account is locked. Please try again later.'):
        super().__init__(message, status_code=403)


class AccountInactiveError(AuthError):
    """Raised when account is not active."""

    def __init__(self, message: str = 'Account is not active'):
        super().__init__(message, status_code=403)


class UserExistsError(AuthError):
    """Raised when trying to register with existing username/email."""

    def __init__(self, message: str = 'Username or email already exists'):
        super().__init__(message, status_code=409)


class ValidationError(AuthError):
    """Raised when input validation fails."""

    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class AuthService:
    """
    Authentication service handling user registration, login, and token management.

    Uses PBKDF2 for password hashing and JWT for token-based authentication.
    """

    # Account lockout settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30

    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True

    @classmethod
    def register_user(
        cls,
        username: str,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        roles: Optional[list] = None,
        auto_verify: bool = False,
    ) -> User:
        """
        Register a new user.

        Args:
            username: Unique username
            email: Valid email address
            password: Plain text password (will be hashed)
            first_name: User's first name
            last_name: User's last name
            roles: List of role names to assign
            auto_verify: If True, skip email verification

        Returns:
            Created User object

        Raises:
            UserExistsError: If username or email already exists
            ValidationError: If validation fails
        """
        # Validate password strength
        cls._validate_password(password)

        with get_db_session() as session:
            # Check for existing user
            existing = session.query(User).filter(
                (User.username == username.lower()) |
                (User.email == email.lower())
            ).first()

            if existing:
                if existing.username == username.lower():
                    raise UserExistsError('Username already exists')
                raise UserExistsError('Email already exists')

            # Create new user
            user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                status=UserStatus.ACTIVE.value if auto_verify else UserStatus.PENDING_VERIFICATION.value,
                is_verified=auto_verify,
            )

            # Set password using PBKDF2
            user.set_password(password)

            # Set roles
            if roles:
                user.set_roles(roles)
            else:
                user.set_roles([UserRole.VIEWER.value])

            # Generate verification token if not auto-verified
            if not auto_verify:
                user.verification_token = secrets.token_urlsafe(32)

            session.add(user)
            session.commit()
            session.refresh(user)

            logger.info(f'User registered: {user.username} ({user.email})')

            return user

    @classmethod
    def login(cls, username_or_email: str, password: str) -> Tuple[User, str, str]:
        """
        Authenticate a user and generate JWT tokens.

        Args:
            username_or_email: Username or email address
            password: Plain text password

        Returns:
            Tuple of (User, access_token, refresh_token)

        Raises:
            InvalidCredentialsError: If credentials are invalid
            AccountLockedError: If account is locked
            AccountInactiveError: If account is not active
        """
        with get_db_session() as session:
            # Find user by username or email
            user = session.query(User).filter(
                ((User.username == username_or_email.lower()) |
                 (User.email == username_or_email.lower())) &
                (User.is_deleted == False)
            ).first()

            if not user:
                logger.warning(f'Login attempt for non-existent user: {username_or_email}')
                raise InvalidCredentialsError()

            # Check if account is locked
            if user.is_locked:
                logger.warning(f'Login attempt for locked account: {user.username}')
                raise AccountLockedError(
                    f'Account is locked until {user.locked_until.isoformat()}'
                )

            # Check if account is active
            if not user.is_active or user.status == UserStatus.INACTIVE.value:
                logger.warning(f'Login attempt for inactive account: {user.username}')
                raise AccountInactiveError()

            if user.status == UserStatus.SUSPENDED.value:
                logger.warning(f'Login attempt for suspended account: {user.username}')
                raise AccountInactiveError('Account is suspended')

            # Verify password
            if not user.check_password(password):
                user.record_failed_login(
                    max_attempts=cls.MAX_FAILED_ATTEMPTS,
                    lockout_minutes=cls.LOCKOUT_DURATION_MINUTES
                )
                session.commit()

                remaining = cls.MAX_FAILED_ATTEMPTS - user.failed_login_attempts
                if remaining > 0:
                    logger.warning(
                        f'Failed login for {user.username}: '
                        f'{user.failed_login_attempts} attempts, {remaining} remaining'
                    )
                else:
                    logger.warning(f'Account locked due to failed attempts: {user.username}')

                raise InvalidCredentialsError()

            # Successful login
            user.record_successful_login()
            session.commit()

            # Generate tokens
            access_token, refresh_token = cls._generate_tokens(user)

            logger.info(f'User logged in: {user.username}')

            return user, access_token, refresh_token

    @classmethod
    def refresh_tokens(cls, user_id: str) -> Tuple[str, str]:
        """
        Generate new access and refresh tokens for a user.

        Args:
            user_id: UUID of the user

        Returns:
            Tuple of (access_token, refresh_token)

        Raises:
            InvalidCredentialsError: If user not found
            AccountInactiveError: If account is not active
        """
        with get_db_session() as session:
            user = session.query(User).filter(
                (User.id == user_id) &
                (User.is_deleted == False)
            ).first()

            if not user:
                raise InvalidCredentialsError('User not found')

            if not user.is_active:
                raise AccountInactiveError()

            # Generate new tokens
            access_token, refresh_token = cls._generate_tokens(user)

            logger.info(f'Tokens refreshed for user: {user.username}')

            return access_token, refresh_token

    @classmethod
    def logout(cls, jti: str, token_type: str, user_id: Optional[str] = None) -> None:
        """
        Revoke a token by adding it to the blocklist.

        Args:
            jti: JWT ID to revoke
            token_type: 'access' or 'refresh'
            user_id: Optional user ID for the token
        """
        config = get_config()

        # Calculate expiry based on token type
        if token_type == 'access':
            expires_at = datetime.utcnow() + config.jwt.access_token_expires
        else:
            expires_at = datetime.utcnow() + config.jwt.refresh_token_expires

        with get_db_session() as session:
            blocklist_entry = TokenBlocklist(
                jti=jti,
                token_type=token_type,
                user_id=UUID(user_id) if user_id else None,
                expires_at=expires_at,
            )
            session.add(blocklist_entry)
            session.commit()

            logger.info(f'Token revoked: {jti} ({token_type})')

    @classmethod
    def is_token_revoked(cls, jti: str) -> bool:
        """
        Check if a token has been revoked.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is revoked, False otherwise
        """
        with get_db_session() as session:
            token = session.query(TokenBlocklist).filter(
                TokenBlocklist.jti == jti
            ).first()
            return token is not None

    @classmethod
    def get_user_by_id(cls, user_id: str) -> Optional[User]:
        """
        Get a user by their ID.

        Args:
            user_id: UUID of the user

        Returns:
            User object or None if not found
        """
        with get_db_session() as session:
            user = session.query(User).filter(
                (User.id == user_id) &
                (User.is_deleted == False)
            ).first()
            if user:
                # Detach from session to use outside context
                session.expunge(user)
            return user

    @classmethod
    def get_user_by_username(cls, username: str) -> Optional[User]:
        """
        Get a user by their username.

        Args:
            username: Username to look up

        Returns:
            User object or None if not found
        """
        with get_db_session() as session:
            user = session.query(User).filter(
                (User.username == username.lower()) &
                (User.is_deleted == False)
            ).first()
            if user:
                session.expunge(user)
            return user

    @classmethod
    def get_user_by_email(cls, email: str) -> Optional[User]:
        """
        Get a user by their email.

        Args:
            email: Email address to look up

        Returns:
            User object or None if not found
        """
        with get_db_session() as session:
            user = session.query(User).filter(
                (User.email == email.lower()) &
                (User.is_deleted == False)
            ).first()
            if user:
                session.expunge(user)
            return user

    @classmethod
    def update_user(
        cls,
        user_id: str,
        **kwargs
    ) -> User:
        """
        Update user profile fields.

        Args:
            user_id: UUID of the user to update
            **kwargs: Fields to update (first_name, last_name, phone, etc.)

        Returns:
            Updated User object
        """
        allowed_fields = {
            'first_name', 'last_name', 'phone', 'department', 'employee_id'
        }

        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()

            if not user:
                raise ValidationError('User not found')

            for key, value in kwargs.items():
                if key in allowed_fields:
                    setattr(user, key, value)

            session.commit()
            session.refresh(user)
            session.expunge(user)

            logger.info(f'User updated: {user.username}')

            return user

    @classmethod
    def change_password(
        cls,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Change a user's password.

        Args:
            user_id: UUID of the user
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            True if password was changed successfully

        Raises:
            InvalidCredentialsError: If current password is wrong
            ValidationError: If new password doesn't meet requirements
        """
        cls._validate_password(new_password)

        with get_db_session() as session:
            user = session.query(User).filter(User.id == user_id).first()

            if not user:
                raise ValidationError('User not found')

            if not user.check_password(current_password):
                raise InvalidCredentialsError('Current password is incorrect')

            user.set_password(new_password)
            session.commit()

            logger.info(f'Password changed for user: {user.username}')

            return True

    @classmethod
    def generate_password_reset_token(cls, email: str) -> Optional[str]:
        """
        Generate a password reset token for a user.

        Args:
            email: Email address of the user

        Returns:
            Reset token or None if user not found
        """
        with get_db_session() as session:
            user = session.query(User).filter(
                (User.email == email.lower()) &
                (User.is_deleted == False)
            ).first()

            if not user:
                # Don't reveal if email exists
                return None

            token = secrets.token_urlsafe(32)
            user.password_reset_token = token
            user.password_reset_expires = datetime.utcnow() + timedelta(hours=24)
            session.commit()

            logger.info(f'Password reset token generated for: {user.email}')

            return token

    @classmethod
    def reset_password(cls, token: str, new_password: str) -> bool:
        """
        Reset a user's password using a reset token.

        Args:
            token: Password reset token
            new_password: New password to set

        Returns:
            True if password was reset successfully

        Raises:
            ValidationError: If token is invalid or expired
        """
        cls._validate_password(new_password)

        with get_db_session() as session:
            user = session.query(User).filter(
                (User.password_reset_token == token) &
                (User.password_reset_expires > datetime.utcnow()) &
                (User.is_deleted == False)
            ).first()

            if not user:
                raise ValidationError('Invalid or expired reset token')

            user.set_password(new_password)
            user.password_reset_token = None
            user.password_reset_expires = None
            user.failed_login_attempts = 0
            user.locked_until = None
            session.commit()

            logger.info(f'Password reset completed for: {user.email}')

            return True

    @classmethod
    def verify_email(cls, token: str) -> bool:
        """
        Verify a user's email address using verification token.

        Args:
            token: Email verification token

        Returns:
            True if email was verified successfully

        Raises:
            ValidationError: If token is invalid
        """
        with get_db_session() as session:
            user = session.query(User).filter(
                (User.verification_token == token) &
                (User.is_deleted == False)
            ).first()

            if not user:
                raise ValidationError('Invalid verification token')

            user.is_verified = True
            user.verification_token = None
            user.status = UserStatus.ACTIVE.value
            session.commit()

            logger.info(f'Email verified for: {user.email}')

            return True

    @classmethod
    def cleanup_expired_tokens(cls) -> int:
        """
        Remove expired tokens from the blocklist.

        Returns:
            Number of tokens removed
        """
        with get_db_session() as session:
            result = session.query(TokenBlocklist).filter(
                TokenBlocklist.expires_at < datetime.utcnow()
            ).delete()
            session.commit()

            if result > 0:
                logger.info(f'Cleaned up {result} expired blocklist tokens')

            return result

    @classmethod
    def _generate_tokens(cls, user: User) -> Tuple[str, str]:
        """
        Generate access and refresh tokens for a user.

        Args:
            user: User object to generate tokens for

        Returns:
            Tuple of (access_token, refresh_token)
        """
        # Create additional claims
        additional_claims = {
            'username': user.username,
            'email': user.email,
            'roles': user.get_roles(),
            'permissions': user.get_permissions_list(),
        }

        # Create tokens
        access_token = create_access_token(
            identity=str(user.id),
            additional_claims=additional_claims,
        )

        refresh_token = create_refresh_token(
            identity=str(user.id),
            additional_claims={'username': user.username},
        )

        return access_token, refresh_token

    @classmethod
    def _validate_password(cls, password: str) -> None:
        """
        Validate password meets security requirements.

        Args:
            password: Password to validate

        Raises:
            ValidationError: If password doesn't meet requirements
        """
        errors = []

        if len(password) < cls.MIN_PASSWORD_LENGTH:
            errors.append(f'Password must be at least {cls.MIN_PASSWORD_LENGTH} characters')

        if cls.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append('Password must contain at least one uppercase letter')

        if cls.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append('Password must contain at least one lowercase letter')

        if cls.REQUIRE_DIGIT and not any(c.isdigit() for c in password):
            errors.append('Password must contain at least one digit')

        if cls.REQUIRE_SPECIAL:
            special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?')
            if not any(c in special_chars for c in password):
                errors.append('Password must contain at least one special character')

        if errors:
            raise ValidationError('; '.join(errors))
