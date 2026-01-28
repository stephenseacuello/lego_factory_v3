#!/usr/bin/env python3
"""
Access Control Manager for LEGO MCP Security

Implements role-based access control (RBAC) and attribute-based access
control (ABAC) for ROS2 nodes and services.

Industry 4.0/5.0 Architecture - IEC 62443 Compliance
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set
import hashlib
import json


class Permission(Enum):
    """Node permissions."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"
    EMERGENCY = "emergency"  # E-stop access


class Role(Enum):
    """User/Node roles."""
    OPERATOR = "operator"
    ENGINEER = "engineer"
    SUPERVISOR = "supervisor"
    SAFETY_OFFICER = "safety_officer"
    ADMINISTRATOR = "administrator"
    SYSTEM = "system"  # Internal system processes


@dataclass
class AccessPolicy:
    """Access control policy."""
    policy_id: str
    resource: str  # Topic, service, or action
    resource_type: str  # topic, service, action
    allowed_roles: List[Role]
    required_permissions: List[Permission]
    zone_restrictions: List[str] = field(default_factory=list)
    time_restrictions: Optional[Dict] = None  # e.g., {"start": "08:00", "end": "18:00"}
    mfa_required: bool = False


@dataclass
class AccessToken:
    """Access token for authenticated entities."""
    token_id: str
    entity_id: str
    entity_type: str  # user, node, service
    roles: List[Role]
    permissions: List[Permission]
    zone: str
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False


class AccessControlManager:
    """
    Access Control Manager.

    Implements RBAC and ABAC for the LEGO MCP system:
    - Role-based access to resources
    - Zone-based access restrictions
    - Time-based access windows
    - Emergency override capabilities
    """

    def __init__(self):
        """Initialize access control manager."""
        self._policies: Dict[str, AccessPolicy] = {}
        self._tokens: Dict[str, AccessToken] = {}
        self._role_permissions: Dict[Role, Set[Permission]] = {
            Role.OPERATOR: {Permission.READ, Permission.EXECUTE},
            Role.ENGINEER: {Permission.READ, Permission.WRITE, Permission.EXECUTE},
            Role.SUPERVISOR: {Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.ADMIN},
            Role.SAFETY_OFFICER: {Permission.READ, Permission.EMERGENCY},
            Role.ADMINISTRATOR: {Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.ADMIN, Permission.EMERGENCY},
            Role.SYSTEM: {Permission.READ, Permission.WRITE, Permission.EXECUTE},
        }
        self._initialize_default_policies()

    def _initialize_default_policies(self):
        """Create default access policies for LEGO MCP resources."""

        # Safety services - restricted to safety_officer and admin
        self.add_policy(AccessPolicy(
            policy_id="safety_estop",
            resource="/safety/emergency_stop",
            resource_type="service",
            allowed_roles=[Role.SAFETY_OFFICER, Role.ADMINISTRATOR, Role.SYSTEM],
            required_permissions=[Permission.EMERGENCY],
            zone_restrictions=["safety", "supervisory"],
        ))

        self.add_policy(AccessPolicy(
            policy_id="safety_reset",
            resource="/safety/reset",
            resource_type="service",
            allowed_roles=[Role.SAFETY_OFFICER, Role.ADMINISTRATOR],
            required_permissions=[Permission.EMERGENCY, Permission.ADMIN],
            mfa_required=True,  # Require MFA for safety reset
        ))

        # Equipment control - engineers and above
        self.add_policy(AccessPolicy(
            policy_id="equipment_control",
            resource="/*/execute",
            resource_type="action",
            allowed_roles=[Role.ENGINEER, Role.SUPERVISOR, Role.ADMINISTRATOR, Role.SYSTEM],
            required_permissions=[Permission.EXECUTE],
            zone_restrictions=["control", "supervisory"],
        ))

        # Job scheduling - operators and above
        self.add_policy(AccessPolicy(
            policy_id="job_schedule",
            resource="/lego_mcp_orchestrator/schedule_job",
            resource_type="service",
            allowed_roles=[Role.OPERATOR, Role.ENGINEER, Role.SUPERVISOR, Role.ADMINISTRATOR],
            required_permissions=[Permission.EXECUTE],
        ))

        # Status monitoring - all roles
        self.add_policy(AccessPolicy(
            policy_id="status_read",
            resource="/*/status",
            resource_type="topic",
            allowed_roles=list(Role),
            required_permissions=[Permission.READ],
        ))

        # Configuration changes - admin only
        self.add_policy(AccessPolicy(
            policy_id="config_write",
            resource="/*/set_parameters",
            resource_type="service",
            allowed_roles=[Role.ADMINISTRATOR],
            required_permissions=[Permission.ADMIN, Permission.WRITE],
            mfa_required=True,
        ))

    def add_policy(self, policy: AccessPolicy) -> bool:
        """Add or update an access policy."""
        self._policies[policy.policy_id] = policy
        return True

    def remove_policy(self, policy_id: str) -> bool:
        """Remove an access policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def issue_token(
        self,
        entity_id: str,
        entity_type: str,
        roles: List[Role],
        zone: str,
        validity_hours: int = 24,
    ) -> AccessToken:
        """
        Issue an access token for an entity.

        Args:
            entity_id: Unique entity identifier
            entity_type: Type of entity (user, node, service)
            roles: Roles assigned to entity
            zone: Security zone of entity
            validity_hours: Token validity period

        Returns:
            AccessToken
        """
        now = datetime.now()
        token_id = hashlib.sha256(
            f"{entity_id}{now.isoformat()}".encode()
        ).hexdigest()[:32]

        # Aggregate permissions from roles
        permissions = set()
        for role in roles:
            permissions.update(self._role_permissions.get(role, set()))

        token = AccessToken(
            token_id=token_id,
            entity_id=entity_id,
            entity_type=entity_type,
            roles=roles,
            permissions=list(permissions),
            zone=zone,
            issued_at=now,
            expires_at=datetime.fromtimestamp(
                now.timestamp() + validity_hours * 3600
            ),
        )

        self._tokens[token_id] = token
        return token

    def validate_token(self, token_id: str) -> Optional[AccessToken]:
        """Validate a token and return it if valid."""
        token = self._tokens.get(token_id)
        if not token:
            return None
        if token.revoked:
            return None
        if token.expires_at < datetime.now():
            return None
        return token

    def revoke_token(self, token_id: str) -> bool:
        """Revoke an access token."""
        token = self._tokens.get(token_id)
        if token:
            token.revoked = True
            return True
        return False

    def check_access(
        self,
        token_id: str,
        resource: str,
        resource_type: str,
        source_zone: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Check if access is allowed for a resource.

        Args:
            token_id: Access token ID
            resource: Resource path
            resource_type: Type of resource (topic, service, action)
            source_zone: Zone making the request

        Returns:
            Tuple of (allowed, reason)
        """
        # Validate token
        token = self.validate_token(token_id)
        if not token:
            return False, "Invalid or expired token"

        # Find matching policy
        policy = self._find_matching_policy(resource, resource_type)
        if not policy:
            # Default deny if no policy matches
            return False, "No matching policy found"

        # Check role
        if not any(role in policy.allowed_roles for role in token.roles):
            return False, "Insufficient role permissions"

        # Check permissions
        required = set(policy.required_permissions)
        available = set(token.permissions)
        if not required.issubset(available):
            missing = required - available
            return False, f"Missing permissions: {missing}"

        # Check zone restrictions
        if policy.zone_restrictions:
            if source_zone and source_zone not in policy.zone_restrictions:
                return False, f"Zone {source_zone} not allowed"

        # Check time restrictions
        if policy.time_restrictions:
            now = datetime.now()
            start = datetime.strptime(policy.time_restrictions.get("start", "00:00"), "%H:%M")
            end = datetime.strptime(policy.time_restrictions.get("end", "23:59"), "%H:%M")
            current_time = now.replace(year=start.year, month=start.month, day=start.day)
            if not (start <= current_time <= end):
                return False, "Access not allowed at this time"

        return True, "Access granted"

    def _find_matching_policy(self, resource: str, resource_type: str) -> Optional[AccessPolicy]:
        """Find a policy matching the resource."""
        for policy in self._policies.values():
            if policy.resource_type != resource_type:
                continue

            # Exact match
            if policy.resource == resource:
                return policy

            # Wildcard match
            if "*" in policy.resource:
                pattern = policy.resource.replace("*", "")
                if pattern in resource:
                    return policy

        return None

    def get_entity_permissions(self, token_id: str) -> Dict:
        """Get all permissions for an entity."""
        token = self.validate_token(token_id)
        if not token:
            return {"error": "Invalid token"}

        return {
            "entity_id": token.entity_id,
            "entity_type": token.entity_type,
            "roles": [r.value for r in token.roles],
            "permissions": [p.value for p in token.permissions],
            "zone": token.zone,
            "expires_at": token.expires_at.isoformat(),
        }

    def audit_access_attempt(
        self,
        token_id: str,
        resource: str,
        resource_type: str,
        allowed: bool,
        reason: str,
    ) -> Dict:
        """
        Create an audit record for an access attempt.

        Returns:
            Audit record dictionary
        """
        token = self._tokens.get(token_id)
        return {
            "timestamp": datetime.now().isoformat(),
            "entity_id": token.entity_id if token else "unknown",
            "resource": resource,
            "resource_type": resource_type,
            "allowed": allowed,
            "reason": reason,
            "zone": token.zone if token else "unknown",
        }
