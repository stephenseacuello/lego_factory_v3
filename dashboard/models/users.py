"""
User and Access Models

User management, authentication, and audit logging:
- User: System users with role-based access
- Customer: External customers for orders
- AuditLog: System activity tracking
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
    ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from .base import Base, IS_SQLITE

# Use JSON for SQLite, JSONB for PostgreSQL
JSON_TYPE = Text if IS_SQLITE else JSONB


class UserRole(str, Enum):
    """User role levels for RBAC."""
    ADMIN = 'ADMIN'             # Full system access
    MANAGER = 'MANAGER'         # Production management
    ENGINEER = 'ENGINEER'       # Engineering/design access
    OPERATOR = 'OPERATOR'       # Shop floor operations
    QUALITY = 'QUALITY'         # Quality control
    VIEWER = 'VIEWER'           # Read-only access


class User(Base):
    """
    System User - Authentication and authorization.

    Supports role-based access control (RBAC) with permissions
    defined per role for different system functions.
    """
    __tablename__ = 'users'

    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Authentication (password hash, not plaintext)
    password_hash = Column(String(255))

    # Profile
    first_name = Column(String(100))
    last_name = Column(String(100))
    display_name = Column(String(200))

    # Role and permissions
    role = Column(String(50), default=UserRole.VIEWER.value, index=True)
    permissions = Column(JSON_TYPE)  # Additional granular permissions

    # Work center assignments (operators can be assigned to machines)
    assigned_work_centers = Column(JSON_TYPE)  # List of work center IDs
    default_work_center_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                                    ForeignKey('work_centers.id'))

    # Status
    is_active = Column(Boolean, default=True, index=True)
    last_login = Column(DateTime)

    # Preferences
    preferences = Column(JSON_TYPE)
    timezone = Column(String(50), default='UTC')
    locale = Column(String(10), default='en-US')

    # API access
    api_key = Column(String(100), unique=True)
    api_key_expires = Column(DateTime)

    # Relationships
    default_work_center = relationship('WorkCenter')
    audit_logs = relationship('AuditLog', back_populates='user',
                              foreign_keys='AuditLog.user_id')

    def __repr__(self):
        return f"<User({self.username}, role={self.role})>"

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.display_name or self.username

    @classmethod
    def get_by_username(cls, session, username: str) -> Optional['User']:
        """Find user by username."""
        return session.query(cls).filter(cls.username == username).first()

    @classmethod
    def get_by_email(cls, session, email: str) -> Optional['User']:
        """Find user by email."""
        return session.query(cls).filter(cls.email == email).first()

    @classmethod
    def get_by_api_key(cls, session, api_key: str) -> Optional['User']:
        """Find user by API key."""
        user = session.query(cls).filter(cls.api_key == api_key).first()
        if user and user.api_key_expires:
            if user.api_key_expires < datetime.utcnow():
                return None  # Expired
        return user

    @classmethod
    def get_active_operators(cls, session) -> List['User']:
        """Get all active operators."""
        return session.query(cls).filter(
            cls.is_active == True,
            cls.role == UserRole.OPERATOR.value
        ).all()

    @classmethod
    def get_by_role(cls, session, role: str) -> List['User']:
        """Get all users with a specific role."""
        return session.query(cls).filter(
            cls.is_active == True,
            cls.role == role
        ).all()

    def has_permission(self, permission: str) -> bool:
        """
        Check if user has a specific permission.

        Role-based permissions:
        - ADMIN: All permissions
        - MANAGER: production.*, inventory.*, quality.*, reports.*
        - ENGINEER: parts.*, routing.*, bom.*
        - OPERATOR: operations.*, quality.inspect
        - QUALITY: quality.*
        - VIEWER: *.read
        """
        if self.role == UserRole.ADMIN.value:
            return True

        # Check explicit permissions
        if self.permissions and permission in self.permissions:
            return self.permissions[permission]

        # Role-based defaults
        role_permissions = {
            UserRole.MANAGER.value: [
                'production.*', 'inventory.*', 'quality.*',
                'reports.*', 'work_orders.*'
            ],
            UserRole.ENGINEER.value: [
                'parts.*', 'routing.*', 'bom.*',
                'parts.read', 'work_centers.read'
            ],
            UserRole.OPERATOR.value: [
                'operations.*', 'quality.inspect',
                'work_orders.read', 'parts.read'
            ],
            UserRole.QUALITY.value: [
                'quality.*', 'parts.read', 'work_orders.read'
            ],
            UserRole.VIEWER.value: [
                '*.read'
            ]
        }

        user_perms = role_permissions.get(self.role, [])

        for perm in user_perms:
            if perm == permission:
                return True
            if perm.endswith('.*'):
                prefix = perm[:-2]
                if permission.startswith(prefix):
                    return True
            if perm == '*.read' and permission.endswith('.read'):
                return True

        return False

    def update_login(self, session):
        """Update last login timestamp."""
        self.last_login = datetime.utcnow()
        session.commit()


class Customer(Base):
    """
    Customer - External customer for orders and shipping.

    Tracks customer information for work orders and
    finished goods shipments.
    """
    __tablename__ = 'customers'

    customer_number = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # Contact information
    contact_name = Column(String(200))
    email = Column(String(255))
    phone = Column(String(50))

    # Address
    address_line1 = Column(String(255))
    address_line2 = Column(String(255))
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(20))
    country = Column(String(100), default='USA')

    # Shipping preferences
    shipping_method = Column(String(50))
    shipping_account = Column(String(100))

    # Billing
    payment_terms = Column(String(50), default='NET30')
    credit_limit = Column(Float)

    # Status
    is_active = Column(Boolean, default=True, index=True)

    # Notes and extra data
    notes = Column(Text)
    extra_data = Column(JSON_TYPE)  # Renamed from 'metadata' (reserved in SQLAlchemy)

    def __repr__(self):
        return f"<Customer({self.customer_number}: {self.name})>"

    @classmethod
    def get_by_number(cls, session, customer_number: str) -> Optional['Customer']:
        """Find customer by number."""
        return session.query(cls).filter(cls.customer_number == customer_number).first()

    @classmethod
    def search(cls, session, query: str, limit: int = 50) -> List['Customer']:
        """Search customers by name or number."""
        search_term = f"%{query}%"
        return session.query(cls).filter(
            (cls.name.ilike(search_term)) |
            (cls.customer_number.ilike(search_term))
        ).limit(limit).all()

    @property
    def full_address(self) -> str:
        """Get formatted full address."""
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        parts.append(f"{self.city}, {self.state} {self.postal_code}")
        parts.append(self.country)
        return '\n'.join(parts)


class AuditLog(Base):
    """
    Audit Log - System activity tracking.

    Records all significant system events for:
    - Security auditing
    - Compliance (FDA 21 CFR Part 11 if needed)
    - Troubleshooting
    - Change history
    """
    __tablename__ = 'audit_log'

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Who
    user_id = Column(UUID(as_uuid=True) if not IS_SQLITE else String,
                     ForeignKey('users.id'), index=True)
    username = Column(String(100))  # Cached for deleted users
    ip_address = Column(String(45))
    user_agent = Column(String(500))

    # What
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), index=True)
    resource_id = Column(String(100))

    # Details
    old_value = Column(JSON_TYPE)
    new_value = Column(JSON_TYPE)
    description = Column(Text)

    # Context
    request_id = Column(String(100))  # For correlating related events
    session_id = Column(String(100))

    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text)

    # Relationships
    user = relationship('User', back_populates='audit_logs',
                        foreign_keys=[user_id])

    __table_args__ = (
        Index('idx_audit_user_time', 'user_id', 'timestamp'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_action_time', 'action', 'timestamp'),
    )

    def __repr__(self):
        return f"<AuditLog({self.action}, {self.resource_type}, {self.timestamp})>"

    @classmethod
    def log(cls, session, action: str, resource_type: str = None,
            resource_id: str = None, user_id: str = None,
            username: str = None, old_value: Any = None,
            new_value: Any = None, description: str = None,
            success: bool = True, error_message: str = None,
            **kwargs) -> 'AuditLog':
        """
        Create an audit log entry.

        Args:
            session: Database session
            action: Action performed (CREATE, UPDATE, DELETE, LOGIN, etc.)
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            user_id: User who performed action
            username: Username (cached for deleted users)
            old_value: Previous value (for updates)
            new_value: New value (for creates/updates)
            description: Human-readable description
            success: Whether action succeeded
            error_message: Error message if failed
            **kwargs: Additional fields

        Returns:
            AuditLog entry
        """
        entry = cls(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            username=username,
            old_value=old_value,
            new_value=new_value,
            description=description,
            success=success,
            error_message=error_message,
            **{k: v for k, v in kwargs.items() if hasattr(cls, k)}
        )
        session.add(entry)
        return entry

    @classmethod
    def get_by_user(cls, session, user_id: str,
                    limit: int = 100) -> List['AuditLog']:
        """Get recent audit logs for a user."""
        return session.query(cls).filter(
            cls.user_id == user_id
        ).order_by(cls.timestamp.desc()).limit(limit).all()

    @classmethod
    def get_by_resource(cls, session, resource_type: str,
                        resource_id: str) -> List['AuditLog']:
        """Get audit history for a specific resource."""
        return session.query(cls).filter(
            cls.resource_type == resource_type,
            cls.resource_id == resource_id
        ).order_by(cls.timestamp.desc()).all()

    @classmethod
    def get_recent(cls, session, hours: int = 24,
                   limit: int = 500) -> List['AuditLog']:
        """Get recent audit logs."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return session.query(cls).filter(
            cls.timestamp >= cutoff
        ).order_by(cls.timestamp.desc()).limit(limit).all()

    @classmethod
    def get_failed_logins(cls, session, hours: int = 24) -> List['AuditLog']:
        """Get recent failed login attempts."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return session.query(cls).filter(
            cls.action == 'LOGIN',
            cls.success == False,
            cls.timestamp >= cutoff
        ).order_by(cls.timestamp.desc()).all()


# Standard audit actions
class AuditAction:
    """Standard audit action constants."""
    # Authentication
    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'
    PASSWORD_CHANGE = 'PASSWORD_CHANGE'
    PASSWORD_RESET = 'PASSWORD_RESET'

    # CRUD operations
    CREATE = 'CREATE'
    READ = 'READ'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'

    # Work order lifecycle
    WO_CREATE = 'WO_CREATE'
    WO_RELEASE = 'WO_RELEASE'
    WO_START = 'WO_START'
    WO_COMPLETE = 'WO_COMPLETE'
    WO_CANCEL = 'WO_CANCEL'
    WO_HOLD = 'WO_HOLD'

    # Quality
    QA_INSPECT = 'QA_INSPECT'
    QA_PASS = 'QA_PASS'
    QA_FAIL = 'QA_FAIL'
    QA_DISPOSITION = 'QA_DISPOSITION'

    # Inventory
    INV_RECEIVE = 'INV_RECEIVE'
    INV_ISSUE = 'INV_ISSUE'
    INV_TRANSFER = 'INV_TRANSFER'
    INV_ADJUST = 'INV_ADJUST'
    INV_SCRAP = 'INV_SCRAP'

    # Equipment
    EQUIP_START = 'EQUIP_START'
    EQUIP_STOP = 'EQUIP_STOP'
    EQUIP_MAINTENANCE = 'EQUIP_MAINTENANCE'
    EQUIP_ALARM = 'EQUIP_ALARM'

    # System
    CONFIG_CHANGE = 'CONFIG_CHANGE'
    EXPORT = 'EXPORT'
    IMPORT = 'IMPORT'
    REPORT_GENERATE = 'REPORT_GENERATE'
