"""
LEGO Factory v3 - Authentication Pydantic Schemas
==================================================
Validation schemas for user authentication, registration,
password management, and session handling.

These schemas enforce security best practices for authentication
including password complexity, email validation, and token formats.
"""

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from api.schemas.common_schemas import BaseSchema, AuditMixin


# ============================================================================
# Login Schemas
# ============================================================================

class LoginRequest(BaseSchema):
    """
    User login request validation.

    Validates username and password with appropriate length
    constraints and format requirements.

    Attributes:
        username: User's username or email address
        password: User's password (not logged or stored in plain text)
        remember_me: Optional flag for extended session duration
    """
    username: str = Field(
        min_length=3,
        max_length=100,
        description="Username or email address"
    )
    password: str = Field(
        min_length=1,
        max_length=128,
        description="User's password"
    )
    remember_me: bool = Field(
        default=False,
        description="Whether to extend session duration"
    )

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Validate username format.

        Allows alphanumeric characters, underscores, hyphens,
        periods, and @ for email-style usernames.
        """
        v = v.strip().lower()
        if not re.match(r'^[a-zA-Z0-9_.@-]+$', v):
            raise ValueError(
                'Username must contain only letters, numbers, '
                'underscores, hyphens, periods, or @ symbol'
            )
        return v


class LoginResponse(BaseSchema):
    """
    Successful login response.

    Returns authentication token and user information
    for client-side session management.

    Attributes:
        access_token: JWT access token for API authentication
        token_type: Token type (always 'bearer')
        expires_in: Token expiration time in seconds
        user: Basic user information
    """
    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(
        ge=0,
        description="Token expiration time in seconds"
    )
    user: "UserInfo" = Field(description="Authenticated user information")


# ============================================================================
# Registration Schemas
# ============================================================================

class RegisterRequest(BaseSchema):
    """
    User registration request validation.

    Enforces password complexity requirements and validates
    email format. All registration data is validated before
    account creation.

    Attributes:
        username: Desired username (3-50 characters, alphanumeric)
        email: Valid email address for account verification
        password: Password meeting complexity requirements
        password_confirm: Password confirmation (must match)
        first_name: User's first name
        last_name: User's last name
        department: Optional department assignment
    """
    username: str = Field(
        min_length=3,
        max_length=50,
        description="Desired username"
    )
    email: EmailStr = Field(description="Valid email address")
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password (8+ characters with complexity requirements)"
    )
    password_confirm: str = Field(
        min_length=8,
        max_length=128,
        description="Password confirmation"
    )
    first_name: str = Field(
        min_length=1,
        max_length=100,
        description="User's first name"
    )
    last_name: str = Field(
        min_length=1,
        max_length=100,
        description="User's last name"
    )
    department: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Department assignment"
    )

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Validate username format.

        Username must start with a letter and contain only
        alphanumeric characters and underscores.
        """
        v = v.strip()
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', v):
            raise ValueError(
                'Username must start with a letter and contain '
                'only letters, numbers, and underscores'
            )
        return v.lower()

    @field_validator('password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """
        Validate password meets complexity requirements.

        Password must contain:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        """
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~]', v):
            raise ValueError('Password must contain at least one special character')
        return v

    @field_validator('password_confirm')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Validate password confirmation matches password."""
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Passwords do not match')
        return v

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name contains only valid characters."""
        v = v.strip()
        if not re.match(r"^[a-zA-Z\s\-']+$", v):
            raise ValueError(
                'Name must contain only letters, spaces, hyphens, or apostrophes'
            )
        return v


class RegisterResponse(BaseSchema):
    """
    Successful registration response.

    Attributes:
        user_id: Newly created user's ID
        username: Confirmed username
        email: Confirmed email address
        message: Success message
        requires_verification: Whether email verification is required
    """
    user_id: str = Field(description="Newly created user ID")
    username: str = Field(description="Confirmed username")
    email: str = Field(description="Confirmed email address")
    message: str = Field(
        default="Registration successful",
        description="Success message"
    )
    requires_verification: bool = Field(
        default=True,
        description="Whether email verification is required"
    )


# ============================================================================
# Token Schemas
# ============================================================================

class TokenResponse(BaseSchema):
    """
    JWT token response for authentication.

    Standard OAuth2-compatible token response format.

    Attributes:
        access_token: JWT access token
        refresh_token: Optional refresh token for token renewal
        token_type: Token type (always 'bearer')
        expires_in: Access token expiration in seconds
        scope: Optional granted scopes
    """
    access_token: str = Field(description="JWT access token")
    refresh_token: Optional[str] = Field(
        default=None,
        description="Refresh token for token renewal"
    )
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(
        ge=0,
        description="Token expiration in seconds"
    )
    scope: Optional[str] = Field(
        default=None,
        description="Granted permission scopes"
    )


class RefreshTokenRequest(BaseSchema):
    """
    Request to refresh an access token.

    Attributes:
        refresh_token: Valid refresh token
    """
    refresh_token: str = Field(
        min_length=1,
        description="Refresh token from previous authentication"
    )


class TokenValidationRequest(BaseSchema):
    """
    Request to validate a token.

    Attributes:
        token: Token to validate
    """
    token: str = Field(
        min_length=1,
        description="Token to validate"
    )


class TokenValidationResponse(BaseSchema):
    """
    Token validation response.

    Attributes:
        valid: Whether the token is valid
        expires_at: Token expiration timestamp
        user_id: User ID associated with the token
        scopes: Permission scopes granted by the token
    """
    valid: bool = Field(description="Whether the token is valid")
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Token expiration timestamp"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID associated with the token"
    )
    scopes: Optional[List[str]] = Field(
        default=None,
        description="Permission scopes"
    )


# ============================================================================
# Password Management Schemas
# ============================================================================

class PasswordChangeRequest(BaseSchema):
    """
    Request to change user password.

    Requires current password for verification before
    allowing password change.

    Attributes:
        current_password: User's current password
        new_password: New password (must meet complexity requirements)
        new_password_confirm: New password confirmation
    """
    current_password: str = Field(
        min_length=1,
        max_length=128,
        description="Current password for verification"
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password"
    )
    new_password_confirm: str = Field(
        min_length=8,
        max_length=128,
        description="New password confirmation"
    )

    @field_validator('new_password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Validate new password meets complexity requirements."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;\'`~]', v):
            raise ValueError('Password must contain at least one special character')
        return v

    @field_validator('new_password_confirm')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Validate password confirmation matches."""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v


class PasswordResetRequest(BaseSchema):
    """
    Request password reset email.

    Attributes:
        email: Email address associated with the account
    """
    email: EmailStr = Field(description="Account email address")


class PasswordResetConfirm(BaseSchema):
    """
    Confirm password reset with token.

    Attributes:
        token: Password reset token from email
        new_password: New password
        new_password_confirm: New password confirmation
    """
    token: str = Field(
        min_length=1,
        description="Password reset token"
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password"
    )
    new_password_confirm: str = Field(
        min_length=8,
        max_length=128,
        description="New password confirmation"
    )

    @field_validator('new_password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Validate new password meets complexity requirements."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v

    @field_validator('new_password_confirm')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Validate password confirmation matches."""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v


# ============================================================================
# User Information Schemas
# ============================================================================

class UserInfo(BaseSchema):
    """
    Basic user information for responses.

    Contains non-sensitive user data suitable for
    API responses and session display.

    Attributes:
        user_id: User's unique identifier
        username: User's username
        email: User's email address
        first_name: User's first name
        last_name: User's last name
        department: User's department
        roles: List of assigned roles
        is_active: Whether the account is active
    """
    user_id: str = Field(description="User's unique identifier")
    username: str = Field(description="Username")
    email: str = Field(description="Email address")
    first_name: Optional[str] = Field(default=None, description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    department: Optional[str] = Field(default=None, description="Department")
    roles: List[str] = Field(
        default_factory=list,
        description="Assigned roles"
    )
    is_active: bool = Field(default=True, description="Account active status")


class UserProfileUpdate(BaseSchema):
    """
    User profile update request.

    Allows updating non-sensitive profile information.

    Attributes:
        first_name: Updated first name
        last_name: Updated last name
        email: Updated email address
        department: Updated department
    """
    first_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="First name"
    )
    last_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Last name"
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Email address"
    )
    department: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Department"
    )

    @field_validator('first_name', 'last_name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate name format if provided."""
        if v is not None:
            v = v.strip()
            if not re.match(r"^[a-zA-Z\s\-']+$", v):
                raise ValueError(
                    'Name must contain only letters, spaces, hyphens, or apostrophes'
                )
        return v


# ============================================================================
# Session Schemas
# ============================================================================

class SessionInfo(BaseSchema):
    """
    Active session information.

    Attributes:
        session_id: Unique session identifier
        user_id: Associated user ID
        created_at: Session creation timestamp
        last_activity: Last activity timestamp
        ip_address: Session IP address
        user_agent: Client user agent string
        is_current: Whether this is the current session
    """
    session_id: str = Field(description="Session identifier")
    user_id: str = Field(description="Associated user ID")
    created_at: datetime = Field(description="Session creation time")
    last_activity: datetime = Field(description="Last activity time")
    ip_address: Optional[str] = Field(
        default=None,
        description="Session IP address"
    )
    user_agent: Optional[str] = Field(
        default=None,
        description="Client user agent"
    )
    is_current: bool = Field(
        default=False,
        description="Whether this is the current session"
    )


class RevokeSessionRequest(BaseSchema):
    """
    Request to revoke a specific session.

    Attributes:
        session_id: Session ID to revoke
    """
    session_id: str = Field(
        min_length=1,
        description="Session ID to revoke"
    )


# Resolve forward reference
LoginResponse.model_rebuild()
