"""
Zero-Trust Architecture Implementation

Implements zero-trust security model for LEGO MCP Manufacturing System.
Every request is authenticated and authorized regardless of source.

Principles:
- Never trust, always verify
- Assume breach
- Verify explicitly
- Use least privilege access
- Microsegmentation

Standards:
- NIST SP 800-207 Zero Trust Architecture
- IEC 62443 Security Levels

Author: LEGO MCP Security Engineering
"""

import logging
import hashlib
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from functools import wraps
import threading
import json

logger = logging.getLogger(__name__)


class TrustLevel(Enum):
    """Zero-trust verification levels."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AuthenticationMethod(Enum):
    """Supported authentication methods."""
    API_KEY = "api_key"
    CERTIFICATE = "certificate"
    TOKEN = "token"
    MTLS = "mtls"
    HSM = "hsm"
    BIOMETRIC = "biometric"
    MFA = "mfa"


class ResourceType(Enum):
    """Resource types for access control."""
    EQUIPMENT = "equipment"
    DATA = "data"
    API = "api"
    TOPIC = "topic"
    SERVICE = "service"
    ADMIN = "admin"


@dataclass
class Identity:
    """Verified identity."""
    id: str
    type: str  # user, service, device
    name: str
    auth_method: AuthenticationMethod
    trust_level: TrustLevel
    attributes: Dict[str, Any] = field(default_factory=dict)
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "auth_method": self.auth_method.value,
            "trust_level": self.trust_level.name,
            "attributes": self.attributes,
            "verified_at": self.verified_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class AccessRequest:
    """Access request for authorization."""
    identity: Identity
    resource_type: ResourceType
    resource_id: str
    action: str  # read, write, execute, admin
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AccessDecision:
    """Authorization decision."""
    allowed: bool
    reason: str
    conditions: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    audit_id: str = field(default_factory=lambda: secrets.token_hex(8))


@dataclass
class SecurityPolicy:
    """Zero-trust security policy."""
    name: str
    resource_type: ResourceType
    required_trust_level: TrustLevel
    allowed_actions: Set[str]
    required_attributes: Dict[str, Any] = field(default_factory=dict)
    time_restrictions: Optional[Dict[str, Any]] = None
    rate_limit: Optional[int] = None  # requests per minute


@dataclass
class SecurityZone:
    """Network microsegmentation zone."""
    zone_id: str
    name: str
    trust_level: TrustLevel
    allowed_ingress: Set[str] = field(default_factory=set)
    allowed_egress: Set[str] = field(default_factory=set)
    encryption_required: bool = True
    inspection_level: str = "full"


class SessionManager:
    """
    Zero-trust session manager.
    
    Sessions are short-lived and continuously verified.
    No persistent sessions - re-authentication required.
    """
    
    DEFAULT_SESSION_DURATION = timedelta(minutes=15)
    MAX_SESSION_DURATION = timedelta(hours=1)
    
    def __init__(self):
        self._sessions: Dict[str, Identity] = {}
        self._session_tokens: Dict[str, str] = {}  # token -> session_id
        self._lock = threading.Lock()
    
    def create_session(
        self,
        identity: Identity,
        duration: Optional[timedelta] = None,
    ) -> str:
        """Create a new session."""
        if duration is None:
            duration = self.DEFAULT_SESSION_DURATION
        
        if duration > self.MAX_SESSION_DURATION:
            duration = self.MAX_SESSION_DURATION
        
        session_id = secrets.token_hex(32)
        token = secrets.token_urlsafe(64)
        
        identity.expires_at = datetime.now(timezone.utc) + duration
        
        with self._lock:
            self._sessions[session_id] = identity
            self._session_tokens[token] = session_id
        
        logger.info(f"Created session for {identity.name} (expires: {identity.expires_at})")
        return token
    
    def validate_session(self, token: str) -> Optional[Identity]:
        """Validate a session token."""
        with self._lock:
            session_id = self._session_tokens.get(token)
            if not session_id:
                return None
            
            identity = self._sessions.get(session_id)
            if not identity:
                return None
            
            if identity.is_expired():
                self._invalidate_session(session_id, token)
                return None
            
            return identity
    
    def invalidate_session(self, token: str) -> bool:
        """Invalidate a session."""
        with self._lock:
            session_id = self._session_tokens.get(token)
            if not session_id:
                return False
            return self._invalidate_session(session_id, token)
    
    def _invalidate_session(self, session_id: str, token: str) -> bool:
        """Internal session invalidation."""
        self._sessions.pop(session_id, None)
        self._session_tokens.pop(token, None)
        return True
    
    def cleanup_expired(self) -> int:
        """Remove expired sessions."""
        with self._lock:
            expired = [
                (sid, tok)
                for tok, sid in self._session_tokens.items()
                if self._sessions.get(sid, Identity(
                    id="", type="", name="", 
                    auth_method=AuthenticationMethod.TOKEN,
                    trust_level=TrustLevel.NONE,
                    expires_at=datetime.min.replace(tzinfo=timezone.utc)
                )).is_expired()
            ]
            
            for sid, tok in expired:
                self._invalidate_session(sid, tok)
            
            return len(expired)


class PolicyEngine:
    """
    Zero-trust policy decision point.
    
    Evaluates access requests against security policies.
    """
    
    def __init__(self):
        self._policies: Dict[str, SecurityPolicy] = {}
        self._zones: Dict[str, SecurityZone] = {}
        self._setup_default_policies()
    
    def _setup_default_policies(self):
        """Setup default security policies."""
        # Equipment access policy
        self.add_policy(SecurityPolicy(
            name="equipment_access",
            resource_type=ResourceType.EQUIPMENT,
            required_trust_level=TrustLevel.MEDIUM,
            allowed_actions={"read", "write", "execute"},
        ))
        
        # Data access policy
        self.add_policy(SecurityPolicy(
            name="data_access",
            resource_type=ResourceType.DATA,
            required_trust_level=TrustLevel.LOW,
            allowed_actions={"read"},
        ))
        
        # Admin access policy
        self.add_policy(SecurityPolicy(
            name="admin_access",
            resource_type=ResourceType.ADMIN,
            required_trust_level=TrustLevel.CRITICAL,
            allowed_actions={"read", "write", "admin"},
            required_attributes={"role": "admin"},
        ))
        
        # Safety-critical access
        self.add_policy(SecurityPolicy(
            name="safety_critical",
            resource_type=ResourceType.EQUIPMENT,
            required_trust_level=TrustLevel.HIGH,
            allowed_actions={"estop", "safety_override"},
            required_attributes={"safety_certified": True},
        ))
    
    def add_policy(self, policy: SecurityPolicy) -> None:
        """Add a security policy."""
        self._policies[policy.name] = policy
    
    def add_zone(self, zone: SecurityZone) -> None:
        """Add a security zone."""
        self._zones[zone.zone_id] = zone
    
    def evaluate(self, request: AccessRequest) -> AccessDecision:
        """Evaluate an access request."""
        # Find applicable policies
        applicable_policies = [
            p for p in self._policies.values()
            if p.resource_type == request.resource_type
        ]
        
        if not applicable_policies:
            return AccessDecision(
                allowed=False,
                reason="No applicable policy found",
            )
        
        for policy in applicable_policies:
            decision = self._evaluate_policy(request, policy)
            if not decision.allowed:
                return decision
        
        return AccessDecision(
            allowed=True,
            reason="All policies satisfied",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
    
    def _evaluate_policy(
        self,
        request: AccessRequest,
        policy: SecurityPolicy,
    ) -> AccessDecision:
        """Evaluate request against a single policy."""
        # Check trust level
        if request.identity.trust_level.value < policy.required_trust_level.value:
            return AccessDecision(
                allowed=False,
                reason=f"Insufficient trust level: {request.identity.trust_level.name} < {policy.required_trust_level.name}",
            )
        
        # Check action
        if request.action not in policy.allowed_actions:
            return AccessDecision(
                allowed=False,
                reason=f"Action '{request.action}' not allowed by policy '{policy.name}'",
            )
        
        # Check required attributes
        for attr, value in policy.required_attributes.items():
            if request.identity.attributes.get(attr) != value:
                return AccessDecision(
                    allowed=False,
                    reason=f"Missing required attribute: {attr}={value}",
                )
        
        # Check time restrictions
        if policy.time_restrictions:
            if not self._check_time_restrictions(policy.time_restrictions):
                return AccessDecision(
                    allowed=False,
                    reason="Access denied due to time restrictions",
                )
        
        return AccessDecision(
            allowed=True,
            reason=f"Policy '{policy.name}' satisfied",
        )
    
    def _check_time_restrictions(self, restrictions: Dict[str, Any]) -> bool:
        """Check time-based restrictions."""
        now = datetime.now(timezone.utc)
        
        # Check allowed hours
        allowed_hours = restrictions.get("allowed_hours")
        if allowed_hours:
            start, end = allowed_hours
            if not (start <= now.hour < end):
                return False
        
        # Check allowed days
        allowed_days = restrictions.get("allowed_days")
        if allowed_days:
            if now.weekday() not in allowed_days:
                return False
        
        return True


class ZeroTrustGateway:
    """
    Zero-Trust Security Gateway.
    
    Main entry point for zero-trust security enforcement.
    All requests must pass through the gateway.
    
    Usage:
        gateway = ZeroTrustGateway()
        
        # Authenticate
        identity = gateway.authenticate(credentials)
        
        # Create session
        token = gateway.create_session(identity)
        
        # Authorize request
        decision = gateway.authorize(
            token=token,
            resource_type=ResourceType.EQUIPMENT,
            resource_id="CNC_001",
            action="read",
        )
        
        if decision.allowed:
            # Proceed with request
            pass
    """
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.policy_engine = PolicyEngine()
        self._authenticators: Dict[AuthenticationMethod, Callable] = {}
        self._audit_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        
        self._setup_default_authenticators()
        
        logger.info("Zero-Trust Gateway initialized")
    
    def _setup_default_authenticators(self):
        """Setup default authentication methods."""
        self._authenticators[AuthenticationMethod.API_KEY] = self._auth_api_key
        self._authenticators[AuthenticationMethod.TOKEN] = self._auth_token
        self._authenticators[AuthenticationMethod.CERTIFICATE] = self._auth_certificate
    
    def register_authenticator(
        self,
        method: AuthenticationMethod,
        authenticator: Callable[[Dict[str, Any]], Optional[Identity]],
    ) -> None:
        """Register a custom authenticator."""
        self._authenticators[method] = authenticator
    
    def authenticate(
        self,
        credentials: Dict[str, Any],
        method: AuthenticationMethod = AuthenticationMethod.API_KEY,
    ) -> Optional[Identity]:
        """Authenticate credentials and return identity."""
        authenticator = self._authenticators.get(method)
        if not authenticator:
            logger.warning(f"Unknown authentication method: {method}")
            return None
        
        identity = authenticator(credentials)
        
        self._audit("authentication", {
            "method": method.value,
            "success": identity is not None,
            "identity_id": identity.id if identity else None,
        })
        
        return identity
    
    def create_session(
        self,
        identity: Identity,
        duration: Optional[timedelta] = None,
    ) -> str:
        """Create a session for authenticated identity."""
        token = self.session_manager.create_session(identity, duration)
        
        self._audit("session_created", {
            "identity_id": identity.id,
            "identity_name": identity.name,
        })
        
        return token
    
    def authorize(
        self,
        token: str,
        resource_type: ResourceType,
        resource_id: str,
        action: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AccessDecision:
        """Authorize an access request."""
        # Validate session
        identity = self.session_manager.validate_session(token)
        if not identity:
            decision = AccessDecision(
                allowed=False,
                reason="Invalid or expired session",
            )
            self._audit("authorization", {
                "allowed": False,
                "reason": decision.reason,
            })
            return decision
        
        # Create access request
        request = AccessRequest(
            identity=identity,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            context=context or {},
        )
        
        # Evaluate policies
        decision = self.policy_engine.evaluate(request)
        
        self._audit("authorization", {
            "identity_id": identity.id,
            "resource_type": resource_type.value,
            "resource_id": resource_id,
            "action": action,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "audit_id": decision.audit_id,
        })
        
        return decision
    
    def verify_continuous(
        self,
        token: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Perform continuous verification."""
        identity = self.session_manager.validate_session(token)
        if not identity:
            return False
        
        # Additional verification checks
        if context:
            # Check for anomalies
            if self._detect_anomaly(identity, context):
                self.session_manager.invalidate_session(token)
                return False
        
        return True
    
    def invalidate_session(self, token: str) -> bool:
        """Invalidate a session."""
        result = self.session_manager.invalidate_session(token)
        self._audit("session_invalidated", {"success": result})
        return result
    
    def _auth_api_key(self, credentials: Dict[str, Any]) -> Optional[Identity]:
        """API key authentication."""
        api_key = credentials.get("api_key")
        if not api_key:
            return None
        
        # In production, validate against key store
        # Here we create a basic identity
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        
        return Identity(
            id=f"apikey_{key_hash}",
            type="service",
            name=credentials.get("name", "API Client"),
            auth_method=AuthenticationMethod.API_KEY,
            trust_level=TrustLevel.MEDIUM,
            attributes=credentials.get("attributes", {}),
        )
    
    def _auth_token(self, credentials: Dict[str, Any]) -> Optional[Identity]:
        """Token authentication."""
        token = credentials.get("token")
        if not token:
            return None
        
        # Validate existing session
        return self.session_manager.validate_session(token)
    
    def _auth_certificate(self, credentials: Dict[str, Any]) -> Optional[Identity]:
        """Certificate authentication."""
        cert = credentials.get("certificate")
        if not cert:
            return None
        
        # In production, validate certificate chain
        cert_hash = hashlib.sha256(str(cert).encode()).hexdigest()[:16]
        
        return Identity(
            id=f"cert_{cert_hash}",
            type="device",
            name=credentials.get("cn", "Certificate Client"),
            auth_method=AuthenticationMethod.CERTIFICATE,
            trust_level=TrustLevel.HIGH,
            attributes=credentials.get("attributes", {}),
        )
    
    def _detect_anomaly(
        self,
        identity: Identity,
        context: Dict[str, Any],
    ) -> bool:
        """Detect anomalous behavior."""
        # Placeholder for anomaly detection
        # In production, check:
        # - Unusual access patterns
        # - Geographic anomalies
        # - Time-based anomalies
        # - Behavioral deviations
        return False
    
    def _audit(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log audit event."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            **data,
        }
        
        with self._lock:
            self._audit_log.append(event)
            # Keep last 10000 events
            if len(self._audit_log) > 10000:
                self._audit_log = self._audit_log[-10000:]
        
        logger.debug(f"Audit: {event_type} - {data}")
    
    def get_audit_log(
        self,
        limit: int = 100,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent audit events."""
        with self._lock:
            events = self._audit_log
            if event_type:
                events = [e for e in events if e.get("event_type") == event_type]
            return events[-limit:]


# Decorator for zero-trust protected functions
def zero_trust_protected(
    gateway: ZeroTrustGateway,
    resource_type: ResourceType,
    action: str,
):
    """Decorator to protect functions with zero-trust authorization."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, token: str = None, resource_id: str = None, **kwargs):
            if not token:
                raise PermissionError("Authentication token required")
            
            decision = gateway.authorize(
                token=token,
                resource_type=resource_type,
                resource_id=resource_id or func.__name__,
                action=action,
            )
            
            if not decision.allowed:
                raise PermissionError(f"Access denied: {decision.reason}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Factory function
def create_zero_trust_gateway() -> ZeroTrustGateway:
    """Create a configured zero-trust gateway."""
    return ZeroTrustGateway()


__all__ = [
    "ZeroTrustGateway",
    "Identity",
    "AccessRequest",
    "AccessDecision",
    "SecurityPolicy",
    "SecurityZone",
    "TrustLevel",
    "AuthenticationMethod",
    "ResourceType",
    "SessionManager",
    "PolicyEngine",
    "zero_trust_protected",
    "create_zero_trust_gateway",
]
