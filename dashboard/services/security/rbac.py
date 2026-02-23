"""
V8 Role-Based Access Control (RBAC) Service
============================================

Implements comprehensive RBAC for the LEGO MCP manufacturing system:
- Role definitions with hierarchical permissions
- Resource-level access control
- Action-based authorization
- Audit logging integration
- Session management
- Multi-tenant support

Compliance: NIST SP 800-53 AC-2, AC-3, AC-6
Industry: ISA/IEC 62443-3-3 SR 2.1

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================
# Enums and Constants
# ============================================

class Permission(Enum):
    """System permissions."""
    # View permissions
    VIEW_DASHBOARD = "view:dashboard"
    VIEW_KPIS = "view:kpis"
    VIEW_ALERTS = "view:alerts"
    VIEW_EQUIPMENT = "view:equipment"
    VIEW_JOBS = "view:jobs"
    VIEW_SIMULATIONS = "view:simulations"
    VIEW_AUDIT = "view:audit"
    VIEW_REPORTS = "view:reports"
    VIEW_USERS = "view:users"
    VIEW_SETTINGS = "view:settings"

    # Action permissions
    CREATE_JOB = "create:job"
    UPDATE_JOB = "update:job"
    DELETE_JOB = "delete:job"
    APPROVE_ACTION = "approve:action"
    REJECT_ACTION = "reject:action"
    EXECUTE_ACTION = "execute:action"

    # Alert permissions
    ACKNOWLEDGE_ALERT = "acknowledge:alert"
    RESOLVE_ALERT = "resolve:alert"
    ESCALATE_ALERT = "escalate:alert"

    # Equipment permissions
    CONTROL_EQUIPMENT = "control:equipment"
    CONFIGURE_EQUIPMENT = "configure:equipment"
    EMERGENCY_STOP = "emergency:stop"
    RESET_EMERGENCY = "reset:emergency"

    # Simulation permissions
    RUN_SIMULATION = "run:simulation"
    STOP_SIMULATION = "stop:simulation"
    CREATE_SCENARIO = "create:scenario"
    DELETE_SCENARIO = "delete:scenario"

    # Workflow permissions
    START_WORKFLOW = "start:workflow"
    PAUSE_WORKFLOW = "pause:workflow"
    RESUME_WORKFLOW = "resume:workflow"
    CANCEL_WORKFLOW = "cancel:workflow"

    # Decision permissions
    APPROVE_DECISION = "approve:decision"
    REJECT_DECISION = "reject:decision"
    ESCALATE_DECISION = "escalate:decision"

    # Admin permissions
    MANAGE_USERS = "manage:users"
    MANAGE_ROLES = "manage:roles"
    MANAGE_SETTINGS = "manage:settings"
    MANAGE_INTEGRATIONS = "manage:integrations"
    SYSTEM_ADMIN = "system:admin"


class Role(Enum):
    """System roles with hierarchical permissions."""
    VIEWER = "viewer"
    OPERATOR = "operator"
    TECHNICIAN = "technician"
    ENGINEER = "engineer"
    SUPERVISOR = "supervisor"
    MANAGER = "manager"
    ADMIN = "admin"
    SYSTEM = "system"


class ResourceType(Enum):
    """Protected resource types."""
    DASHBOARD = "dashboard"
    KPI = "kpi"
    ALERT = "alert"
    EQUIPMENT = "equipment"
    JOB = "job"
    SIMULATION = "simulation"
    WORKFLOW = "workflow"
    DECISION = "decision"
    SCENARIO = "scenario"
    USER = "user"
    ROLE = "role"
    SETTINGS = "settings"
    AUDIT = "audit"
    REPORT = "report"


# ============================================
# Data Classes
# ============================================

@dataclass
class RoleDefinition:
    """Role with permissions."""
    name: Role
    display_name: str
    description: str
    permissions: Set[Permission]
    inherits_from: Optional[Role] = None
    max_session_hours: int = 8
    require_mfa: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name.value,
            "display_name": self.display_name,
            "description": self.description,
            "permissions": [p.value for p in self.permissions],
            "inherits_from": self.inherits_from.value if self.inherits_from else None,
            "max_session_hours": self.max_session_hours,
            "require_mfa": self.require_mfa
        }


@dataclass
class User:
    """User identity with roles."""
    user_id: str
    username: str
    email: str
    roles: Set[Role]
    department: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    last_login: Optional[datetime] = None
    is_active: bool = True
    mfa_enabled: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "roles": [r.value for r in self.roles],
            "department": self.department,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "is_active": self.is_active,
            "mfa_enabled": self.mfa_enabled,
            "attributes": self.attributes
        }


@dataclass
class Session:
    """User session with context."""
    session_id: str
    user: User
    created_at: datetime
    expires_at: datetime
    ip_address: str = ""
    user_agent: str = ""
    is_valid: bool = True
    last_activity: datetime = field(default_factory=datetime.now)

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user.user_id,
            "username": self.user.username,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_valid": self.is_valid and not self.is_expired(),
            "last_activity": self.last_activity.isoformat()
        }


@dataclass
class AccessDecision:
    """Authorization decision with context."""
    allowed: bool
    user_id: str
    resource_type: ResourceType
    resource_id: Optional[str]
    action: Permission
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "user_id": self.user_id,
            "resource_type": self.resource_type.value,
            "resource_id": self.resource_id,
            "action": self.action.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class PolicyRule:
    """Access control policy rule."""
    rule_id: str
    name: str
    resource_type: ResourceType
    actions: Set[Permission]
    conditions: Dict[str, Any] = field(default_factory=dict)
    roles: Set[Role] = field(default_factory=set)
    effect: str = "allow"  # allow or deny
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "resource_type": self.resource_type.value,
            "actions": [a.value for a in self.actions],
            "conditions": self.conditions,
            "roles": [r.value for r in self.roles],
            "effect": self.effect,
            "priority": self.priority
        }


# ============================================
# Role Definitions
# ============================================

DEFAULT_ROLE_DEFINITIONS: Dict[Role, RoleDefinition] = {
    Role.VIEWER: RoleDefinition(
        name=Role.VIEWER,
        display_name="Viewer",
        description="Read-only access to dashboards and reports",
        permissions={
            Permission.VIEW_DASHBOARD,
            Permission.VIEW_KPIS,
            Permission.VIEW_ALERTS,
            Permission.VIEW_EQUIPMENT,
            Permission.VIEW_JOBS,
            Permission.VIEW_REPORTS,
        },
        max_session_hours=8,
        require_mfa=False
    ),

    Role.OPERATOR: RoleDefinition(
        name=Role.OPERATOR,
        display_name="Operator",
        description="Production line operator with basic control",
        permissions={
            Permission.ACKNOWLEDGE_ALERT,
            Permission.VIEW_SIMULATIONS,
        },
        inherits_from=Role.VIEWER,
        max_session_hours=12,
        require_mfa=False
    ),

    Role.TECHNICIAN: RoleDefinition(
        name=Role.TECHNICIAN,
        display_name="Technician",
        description="Equipment technician with maintenance access",
        permissions={
            Permission.CONTROL_EQUIPMENT,
            Permission.CONFIGURE_EQUIPMENT,
            Permission.RESOLVE_ALERT,
        },
        inherits_from=Role.OPERATOR,
        max_session_hours=10,
        require_mfa=False
    ),

    Role.ENGINEER: RoleDefinition(
        name=Role.ENGINEER,
        display_name="Engineer",
        description="Process engineer with simulation and workflow access",
        permissions={
            Permission.CREATE_JOB,
            Permission.UPDATE_JOB,
            Permission.RUN_SIMULATION,
            Permission.STOP_SIMULATION,
            Permission.CREATE_SCENARIO,
            Permission.START_WORKFLOW,
            Permission.PAUSE_WORKFLOW,
            Permission.RESUME_WORKFLOW,
            Permission.VIEW_AUDIT,
        },
        inherits_from=Role.TECHNICIAN,
        max_session_hours=10,
        require_mfa=False
    ),

    Role.SUPERVISOR: RoleDefinition(
        name=Role.SUPERVISOR,
        display_name="Supervisor",
        description="Production supervisor with approval authority",
        permissions={
            Permission.APPROVE_ACTION,
            Permission.REJECT_ACTION,
            Permission.APPROVE_DECISION,
            Permission.REJECT_DECISION,
            Permission.ESCALATE_ALERT,
            Permission.ESCALATE_DECISION,
            Permission.DELETE_JOB,
            Permission.CANCEL_WORKFLOW,
            Permission.DELETE_SCENARIO,
        },
        inherits_from=Role.ENGINEER,
        max_session_hours=10,
        require_mfa=True
    ),

    Role.MANAGER: RoleDefinition(
        name=Role.MANAGER,
        display_name="Manager",
        description="Plant manager with full operational control",
        permissions={
            Permission.EXECUTE_ACTION,
            Permission.EMERGENCY_STOP,
            Permission.RESET_EMERGENCY,
            Permission.VIEW_USERS,
            Permission.VIEW_SETTINGS,
        },
        inherits_from=Role.SUPERVISOR,
        max_session_hours=8,
        require_mfa=True
    ),

    Role.ADMIN: RoleDefinition(
        name=Role.ADMIN,
        display_name="Administrator",
        description="System administrator with full access",
        permissions={
            Permission.MANAGE_USERS,
            Permission.MANAGE_ROLES,
            Permission.MANAGE_SETTINGS,
            Permission.MANAGE_INTEGRATIONS,
        },
        inherits_from=Role.MANAGER,
        max_session_hours=4,
        require_mfa=True
    ),

    Role.SYSTEM: RoleDefinition(
        name=Role.SYSTEM,
        display_name="System",
        description="Internal system account",
        permissions={Permission.SYSTEM_ADMIN},
        max_session_hours=24,
        require_mfa=False
    ),
}


# ============================================
# RBAC Service
# ============================================

class RBACService:
    """Role-Based Access Control service."""

    _instance: Optional[RBACService] = None
    _lock = threading.Lock()

    def __init__(self):
        self._role_definitions = dict(DEFAULT_ROLE_DEFINITIONS)
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, Session] = {}
        self._policy_rules: Dict[str, PolicyRule] = {}
        self._permission_cache: Dict[Tuple[str, Permission], bool] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._cache_timestamps: Dict[str, datetime] = {}

        # Create default system user
        self._create_system_user()

        logger.info("RBAC service initialized")

    @classmethod
    def get_instance(cls) -> RBACService:
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _create_system_user(self):
        """Create internal system user."""
        system_user = User(
            user_id="system",
            username="system",
            email="system@lego-mcp.local",
            roles={Role.SYSTEM},
            department="System",
            is_active=True
        )
        self._users["system"] = system_user

    # ============================================
    # Role Management
    # ============================================

    def get_role_permissions(self, role: Role) -> Set[Permission]:
        """Get all permissions for a role including inherited."""
        permissions: Set[Permission] = set()
        current_role = role

        while current_role is not None:
            role_def = self._role_definitions.get(current_role)
            if role_def:
                permissions.update(role_def.permissions)
                current_role = role_def.inherits_from
            else:
                break

        return permissions

    def get_role_definition(self, role: Role) -> Optional[RoleDefinition]:
        """Get role definition."""
        return self._role_definitions.get(role)

    def list_roles(self) -> List[RoleDefinition]:
        """List all role definitions."""
        return list(self._role_definitions.values())

    # ============================================
    # User Management
    # ============================================

    def create_user(
        self,
        username: str,
        email: str,
        roles: Set[Role],
        department: str = "",
        attributes: Optional[Dict[str, Any]] = None
    ) -> User:
        """Create a new user."""
        user_id = str(uuid.uuid4())

        user = User(
            user_id=user_id,
            username=username,
            email=email,
            roles=roles,
            department=department,
            attributes=attributes or {}
        )

        self._users[user_id] = user
        logger.info(f"Created user: {username} with roles: {[r.value for r in roles]}")

        return user

    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self._users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        for user in self._users.values():
            if user.username == username:
                return user
        return None

    def update_user_roles(self, user_id: str, roles: Set[Role]) -> Optional[User]:
        """Update user roles."""
        user = self._users.get(user_id)
        if user:
            old_roles = user.roles
            user.roles = roles

            # Invalidate permission cache for this user
            self._invalidate_user_cache(user_id)

            logger.info(
                f"Updated roles for {user.username}: "
                f"{[r.value for r in old_roles]} -> {[r.value for r in roles]}"
            )
        return user

    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user."""
        user = self._users.get(user_id)
        if user:
            user.is_active = False

            # Invalidate all sessions for this user
            for session in list(self._sessions.values()):
                if session.user.user_id == user_id:
                    session.is_valid = False

            logger.info(f"Deactivated user: {user.username}")
            return True
        return False

    def list_users(self, active_only: bool = True) -> List[User]:
        """List all users."""
        users = list(self._users.values())
        if active_only:
            users = [u for u in users if u.is_active]
        return users

    def _invalidate_user_cache(self, user_id: str):
        """Invalidate permission cache for a user."""
        keys_to_remove = [k for k in self._permission_cache if k[0] == user_id]
        for key in keys_to_remove:
            del self._permission_cache[key]

    # ============================================
    # Session Management
    # ============================================

    def create_session(
        self,
        user: User,
        ip_address: str = "",
        user_agent: str = ""
    ) -> Session:
        """Create a new session for a user."""
        # Get max session duration from role
        max_hours = 8
        for role in user.roles:
            role_def = self._role_definitions.get(role)
            if role_def:
                max_hours = max(max_hours, role_def.max_session_hours)

        session = Session(
            session_id=str(uuid.uuid4()),
            user=user,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=max_hours),
            ip_address=ip_address,
            user_agent=user_agent
        )

        self._sessions[session.session_id] = session
        user.last_login = datetime.now()

        logger.info(f"Created session for user: {user.username}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        session = self._sessions.get(session_id)
        if session and session.is_valid and not session.is_expired():
            session.last_activity = datetime.now()
            return session
        return None

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        session = self._sessions.get(session_id)
        if session:
            session.is_valid = False
            logger.info(f"Invalidated session for user: {session.user.username}")
            return True
        return False

    def cleanup_sessions(self) -> int:
        """Remove expired sessions."""
        expired = []
        for session_id, session in self._sessions.items():
            if session.is_expired() or not session.is_valid:
                expired.append(session_id)

        for session_id in expired:
            del self._sessions[session_id]

        return len(expired)

    # ============================================
    # Authorization
    # ============================================

    def has_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        if not user.is_active:
            return False

        # Check cache
        cache_key = (user.user_id, permission)
        if cache_key in self._permission_cache:
            cache_time = self._cache_timestamps.get(str(cache_key))
            if cache_time and datetime.now() - cache_time < self._cache_ttl:
                return self._permission_cache[cache_key]

        # Calculate permission
        for role in user.roles:
            role_permissions = self.get_role_permissions(role)
            if permission in role_permissions or Permission.SYSTEM_ADMIN in role_permissions:
                self._permission_cache[cache_key] = True
                self._cache_timestamps[str(cache_key)] = datetime.now()
                return True

        self._permission_cache[cache_key] = False
        self._cache_timestamps[str(cache_key)] = datetime.now()
        return False

    def check_access(
        self,
        user: User,
        resource_type: ResourceType,
        action: Permission,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AccessDecision:
        """Check if user has access to perform action on resource."""
        # Check basic permission
        if not self.has_permission(user, action):
            return AccessDecision(
                allowed=False,
                user_id=user.user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                reason=f"User lacks permission: {action.value}"
            )

        # Check policy rules
        for rule in sorted(self._policy_rules.values(), key=lambda r: -r.priority):
            if rule.resource_type == resource_type and action in rule.actions:
                # Check role match
                if rule.roles and not rule.roles.intersection(user.roles):
                    continue

                # Check conditions
                if rule.conditions and context:
                    condition_met = self._evaluate_conditions(rule.conditions, context)
                    if not condition_met:
                        continue

                # Apply rule effect
                if rule.effect == "deny":
                    return AccessDecision(
                        allowed=False,
                        user_id=user.user_id,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        action=action,
                        reason=f"Denied by policy rule: {rule.name}"
                    )

        return AccessDecision(
            allowed=True,
            user_id=user.user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            reason="Access granted"
        )

    def _evaluate_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate policy conditions against context."""
        for key, expected in conditions.items():
            actual = context.get(key)
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    # ============================================
    # Policy Management
    # ============================================

    def add_policy_rule(self, rule: PolicyRule):
        """Add a policy rule."""
        self._policy_rules[rule.rule_id] = rule
        logger.info(f"Added policy rule: {rule.name}")

    def remove_policy_rule(self, rule_id: str) -> bool:
        """Remove a policy rule."""
        if rule_id in self._policy_rules:
            del self._policy_rules[rule_id]
            return True
        return False

    def list_policy_rules(self) -> List[PolicyRule]:
        """List all policy rules."""
        return list(self._policy_rules.values())

    # ============================================
    # Dashboard Data
    # ============================================

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get RBAC dashboard data."""
        active_sessions = [
            s for s in self._sessions.values()
            if s.is_valid and not s.is_expired()
        ]

        return {
            "users": {
                "total": len(self._users),
                "active": len([u for u in self._users.values() if u.is_active])
            },
            "sessions": {
                "active": len(active_sessions),
                "by_role": self._count_sessions_by_role(active_sessions)
            },
            "roles": {
                "total": len(self._role_definitions),
                "definitions": [r.to_dict() for r in self._role_definitions.values()]
            },
            "policies": {
                "total": len(self._policy_rules),
                "rules": [r.to_dict() for r in self._policy_rules.values()]
            }
        }

    def _count_sessions_by_role(self, sessions: List[Session]) -> Dict[str, int]:
        """Count sessions by primary role."""
        counts: Dict[str, int] = {}
        for session in sessions:
            for role in session.user.roles:
                counts[role.value] = counts.get(role.value, 0) + 1
        return counts


# ============================================
# Decorators
# ============================================

def require_permission(permission: Permission):
    """Decorator to require a permission for a function."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get user from context (Flask g, session, etc.)
            from flask import g, abort

            user = getattr(g, 'current_user', None)
            if not user:
                abort(401, description="Authentication required")

            rbac = get_rbac_service()
            if not rbac.has_permission(user, permission):
                abort(403, description=f"Permission denied: {permission.value}")

            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: Role):
    """Decorator to require a role for a function."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import g, abort

            user = getattr(g, 'current_user', None)
            if not user:
                abort(401, description="Authentication required")

            if role not in user.roles:
                abort(403, description=f"Role required: {role.value}")

            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_role(*roles: Role):
    """Decorator to require any of the specified roles."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import g, abort

            user = getattr(g, 'current_user', None)
            if not user:
                abort(401, description="Authentication required")

            if not any(role in user.roles for role in roles):
                abort(403, description=f"One of these roles required: {[r.value for r in roles]}")

            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================
# Singleton Accessor
# ============================================

_rbac_service: Optional[RBACService] = None


def get_rbac_service() -> RBACService:
    """Get RBAC service singleton."""
    global _rbac_service
    if _rbac_service is None:
        _rbac_service = RBACService.get_instance()
    return _rbac_service


# ============================================
# Convenience Functions
# ============================================

def create_user(
    username: str,
    email: str,
    roles: List[str],
    department: str = ""
) -> User:
    """Create a new user with roles."""
    rbac = get_rbac_service()
    role_set = {Role(r) for r in roles}
    return rbac.create_user(username, email, role_set, department)


def check_permission(user_id: str, permission: str) -> bool:
    """Check if user has permission."""
    rbac = get_rbac_service()
    user = rbac.get_user(user_id)
    if not user:
        return False
    return rbac.has_permission(user, Permission(permission))


def get_user_permissions(user_id: str) -> List[str]:
    """Get all permissions for a user."""
    rbac = get_rbac_service()
    user = rbac.get_user(user_id)
    if not user:
        return []

    permissions: Set[Permission] = set()
    for role in user.roles:
        permissions.update(rbac.get_role_permissions(role))

    return [p.value for p in permissions]
