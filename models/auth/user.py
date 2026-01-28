"""
LEGO Factory v3 - User Model
=============================
User model with password hashing and role-based access control.
"""

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import Column, DateTime, String, Boolean, Text, Index, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from models.base import Base, TimestampMixin, SoftDeleteMixin
from werkzeug.security import generate_password_hash, check_password_hash


class UserStatus(str, Enum):
    """User account status."""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    SUSPENDED = 'suspended'
    PENDING_VERIFICATION = 'pending_verification'


class UserRole(str, Enum):
    """User roles for RBAC."""
    ADMIN = 'admin'
    OPERATOR = 'operator'
    ENGINEER = 'engineer'
    SUPERVISOR = 'supervisor'
    MAINTENANCE = 'maintenance'
    QUALITY = 'quality'
    VIEWER = 'viewer'


# Association table for many-to-many relationship between users and roles
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role', String(50), primary_key=True),
    Column('created_at', DateTime(timezone=True), default=datetime.utcnow),
)


class User(Base, TimestampMixin, SoftDeleteMixin):
    """
    User model for authentication and authorization.

    Uses PBKDF2 password hashing via werkzeug.security.
    """
    __tablename__ = 'users'

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    # Authentication fields
    username: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
        index=True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(256),
        nullable=False
    )

    # Profile fields
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employee_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Account status
    status: Mapped[str] = mapped_column(
        String(50),
        default=UserStatus.PENDING_VERIFICATION.value,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Security fields
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_password_change: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_token: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # Permissions - stored as comma-separated string or JSON
    permissions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index('ix_users_email_active', 'email', 'is_active'),
        Index('ix_users_username_active', 'username', 'is_active'),
        Index('ix_users_status', 'status'),
    )

    # Email validation regex
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    # Username validation regex (alphanumeric, underscore, hyphen, 3-80 chars)
    USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_-]{3,80}$')

    def set_password(self, password: str) -> None:
        """
        Hash and set the user's password using PBKDF2.

        Args:
            password: Plain text password to hash
        """
        self.password_hash = generate_password_hash(
            password,
            method='pbkdf2:sha256',
            salt_length=16
        )
        self.last_password_change = datetime.utcnow()

    def check_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.

        Args:
            password: Plain text password to verify

        Returns:
            True if password matches, False otherwise
        """
        return check_password_hash(self.password_hash, password)

    @validates('email')
    def validate_email(self, key: str, email: str) -> str:
        """
        Validate email format.

        Args:
            key: The attribute key
            email: Email address to validate

        Returns:
            Validated email (lowercase)

        Raises:
            ValueError: If email format is invalid
        """
        if not email:
            raise ValueError('Email address is required')

        email = email.lower().strip()

        if not self.EMAIL_REGEX.match(email):
            raise ValueError('Invalid email address format')

        return email

    @validates('username')
    def validate_username(self, key: str, username: str) -> str:
        """
        Validate username format.

        Args:
            key: The attribute key
            username: Username to validate

        Returns:
            Validated username (lowercase)

        Raises:
            ValueError: If username format is invalid
        """
        if not username:
            raise ValueError('Username is required')

        username = username.lower().strip()

        if not self.USERNAME_REGEX.match(username):
            raise ValueError(
                'Username must be 3-80 characters and contain only '
                'letters, numbers, underscores, and hyphens'
            )

        return username

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        parts = [self.first_name, self.last_name]
        return ' '.join(filter(None, parts)) or self.username

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def get_roles(self) -> List[str]:
        """Get list of user roles from permissions field."""
        if not self.permissions:
            return [UserRole.VIEWER.value]

        try:
            import json
            perms = json.loads(self.permissions)
            return perms.get('roles', [UserRole.VIEWER.value])
        except (json.JSONDecodeError, AttributeError):
            return [UserRole.VIEWER.value]

    def set_roles(self, roles: List[str]) -> None:
        """Set user roles in permissions field."""
        import json

        try:
            perms = json.loads(self.permissions) if self.permissions else {}
        except json.JSONDecodeError:
            perms = {}

        perms['roles'] = roles
        self.permissions = json.dumps(perms)

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.get_roles()

    def has_any_role(self, roles: List[str]) -> bool:
        """Check if user has any of the specified roles."""
        user_roles = self.get_roles()
        return any(role in user_roles for role in roles)

    def get_permissions_list(self) -> List[str]:
        """Get list of specific permissions."""
        if not self.permissions:
            return []

        try:
            import json
            perms = json.loads(self.permissions)
            return perms.get('permissions', [])
        except (json.JSONDecodeError, AttributeError):
            return []

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Admins have all permissions
        if self.has_role(UserRole.ADMIN.value):
            return True
        return permission in self.get_permissions_list()

    def record_failed_login(self, max_attempts: int = 5, lockout_minutes: int = 30) -> None:
        """
        Record a failed login attempt and lock account if threshold exceeded.

        Args:
            max_attempts: Maximum failed attempts before lockout
            lockout_minutes: Duration of lockout in minutes
        """
        from datetime import timedelta

        self.failed_login_attempts += 1

        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)

    def record_successful_login(self) -> None:
        """Record a successful login, resetting failed attempts."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login = datetime.utcnow()

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert user to dictionary representation.

        Args:
            include_sensitive: Include sensitive fields like password_hash

        Returns:
            Dictionary representation of user
        """
        data = {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone': self.phone,
            'department': self.department,
            'employee_id': self.employee_id,
            'status': self.status,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'roles': self.get_roles(),
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_sensitive:
            data['failed_login_attempts'] = self.failed_login_attempts
            data['is_locked'] = self.is_locked
            data['locked_until'] = self.locked_until.isoformat() if self.locked_until else None

        return data

    def __repr__(self) -> str:
        return f'<User {self.username} ({self.email})>'


class TokenBlocklist(Base):
    """
    Blocklist for revoked JWT tokens.

    Stores JTI (JWT ID) of revoked tokens to prevent reuse.
    """
    __tablename__ = 'token_blocklist'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    jti: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True
    )

    token_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False  # 'access' or 'refresh'
    )

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True
    )

    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    # Index for efficient token lookup and cleanup
    __table_args__ = (
        Index('ix_token_blocklist_jti', 'jti'),
        Index('ix_token_blocklist_expires', 'expires_at'),
    )

    def __repr__(self) -> str:
        return f'<TokenBlocklist {self.jti}>'
