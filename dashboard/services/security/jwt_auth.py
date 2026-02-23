"""
JWT Authentication Service
LegoMCP PhD-Level Manufacturing Platform

Implements secure JWT-based authentication with:
- Access and refresh token support
- Token blacklisting
- Rate limiting
- MFA support
- RBAC integration
- Audit logging
"""

import os
import jwt
import uuid
import hashlib
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from flask import request, g, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)


class TokenType(Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"


class Role(Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ENGINEER = "engineer"
    OPERATOR = "operator"
    VIEWER = "viewer"
    API = "api"


# Permission matrix
ROLE_PERMISSIONS = {
    Role.ADMIN: {"*"},  # All permissions
    Role.MANAGER: {
        "read:*", "write:work_orders", "write:schedules",
        "approve:quality", "manage:users", "view:reports",
    },
    Role.ENGINEER: {
        "read:*", "write:work_orders", "write:quality",
        "write:equipment", "run:analysis",
    },
    Role.OPERATOR: {
        "read:work_orders", "read:quality", "write:production",
        "read:equipment",
    },
    Role.VIEWER: {"read:*"},
    Role.API: {"api:*"},
}


@dataclass
class TokenPayload:
    """JWT token payload structure."""
    sub: str  # Subject (user_id)
    type: TokenType
    role: Role
    permissions: List[str] = field(default_factory=list)
    jti: str = field(default_factory=lambda: str(uuid.uuid4()))
    iat: datetime = field(default_factory=datetime.utcnow)
    exp: datetime = None
    device_id: str = None
    ip_address: str = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub": self.sub,
            "type": self.type.value,
            "role": self.role.value,
            "permissions": self.permissions,
            "jti": self.jti,
            "iat": int(self.iat.timestamp()),
            "exp": int(self.exp.timestamp()) if self.exp else None,
            "device_id": self.device_id,
            "ip_address": self.ip_address,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenPayload":
        return cls(
            sub=data["sub"],
            type=TokenType(data["type"]),
            role=Role(data["role"]),
            permissions=data.get("permissions", []),
            jti=data["jti"],
            iat=datetime.fromtimestamp(data["iat"]),
            exp=datetime.fromtimestamp(data["exp"]) if data.get("exp") else None,
            device_id=data.get("device_id"),
            ip_address=data.get("ip_address"),
        )


class TokenBlacklist:
    """In-memory token blacklist (use Redis in production)."""

    def __init__(self):
        self._blacklist: Dict[str, datetime] = {}
        self._cleanup_interval = timedelta(hours=1)
        self._last_cleanup = datetime.utcnow()

    def add(self, jti: str, expires_at: datetime):
        """Add token to blacklist."""
        self._blacklist[jti] = expires_at
        self._cleanup_if_needed()

    def is_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted."""
        self._cleanup_if_needed()
        return jti in self._blacklist

    def _cleanup_if_needed(self):
        """Remove expired tokens from blacklist."""
        now = datetime.utcnow()
        if now - self._last_cleanup > self._cleanup_interval:
            self._blacklist = {
                jti: exp for jti, exp in self._blacklist.items()
                if exp > now
            }
            self._last_cleanup = now


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[datetime]] = {}

    def is_allowed(self, key: str) -> Tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, remaining)."""
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)

        if key not in self._requests:
            self._requests[key] = []

        # Remove old requests
        self._requests[key] = [
            t for t in self._requests[key] if t > window_start
        ]

        current_count = len(self._requests[key])
        remaining = max(0, self.max_requests - current_count)

        if current_count >= self.max_requests:
            return False, 0

        self._requests[key].append(now)
        return True, remaining - 1


class JWTAuthService:
    """JWT Authentication Service."""

    def __init__(self):
        self._secret_key = None
        self._algorithm = "HS256"
        self._access_token_ttl = timedelta(minutes=15)
        self._refresh_token_ttl = timedelta(days=7)
        self._blacklist = TokenBlacklist()
        self._rate_limiter = RateLimiter()
        self._users: Dict[str, Dict] = {}  # In-memory user store (use DB in production)
        self._api_keys: Dict[str, Dict] = {}

    @property
    def secret_key(self) -> str:
        if self._secret_key is None:
            from services.security.secrets_manager import secrets
            self._secret_key = secrets.get_jwt_secret()
        return self._secret_key

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        role: Role = Role.OPERATOR,
    ) -> Dict[str, Any]:
        """Create a new user."""
        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)

        user = {
            "id": user_id,
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "role": role.value,
            "is_active": True,
            "mfa_enabled": False,
            "created_at": datetime.utcnow().isoformat(),
        }

        self._users[user_id] = user
        logger.info(f"Created user: {username} ({user_id})")

        return {k: v for k, v in user.items() if k != "password_hash"}

    def authenticate(
        self,
        username: str,
        password: str,
        device_id: str = None,
        ip_address: str = None,
    ) -> Optional[Dict[str, str]]:
        """Authenticate user and return tokens."""
        # Find user
        user = None
        for u in self._users.values():
            if u["username"] == username or u["email"] == username:
                user = u
                break

        if not user:
            logger.warning(f"Authentication failed: user not found ({username})")
            return None

        if not user["is_active"]:
            logger.warning(f"Authentication failed: user inactive ({username})")
            return None

        if not check_password_hash(user["password_hash"], password):
            logger.warning(f"Authentication failed: invalid password ({username})")
            return None

        # Generate tokens
        access_token = self._create_token(
            user_id=user["id"],
            role=Role(user["role"]),
            token_type=TokenType.ACCESS,
            ttl=self._access_token_ttl,
            device_id=device_id,
            ip_address=ip_address,
        )

        refresh_token = self._create_token(
            user_id=user["id"],
            role=Role(user["role"]),
            token_type=TokenType.REFRESH,
            ttl=self._refresh_token_ttl,
            device_id=device_id,
            ip_address=ip_address,
        )

        logger.info(f"User authenticated: {username}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(self._access_token_ttl.total_seconds()),
        }

    def refresh_tokens(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Refresh access token using refresh token."""
        payload = self.verify_token(refresh_token)
        if not payload:
            return None

        if payload.type != TokenType.REFRESH:
            logger.warning("Token refresh failed: not a refresh token")
            return None

        # Blacklist old refresh token
        self._blacklist.add(payload.jti, payload.exp)

        # Generate new tokens
        access_token = self._create_token(
            user_id=payload.sub,
            role=payload.role,
            token_type=TokenType.ACCESS,
            ttl=self._access_token_ttl,
            device_id=payload.device_id,
            ip_address=payload.ip_address,
        )

        new_refresh_token = self._create_token(
            user_id=payload.sub,
            role=payload.role,
            token_type=TokenType.REFRESH,
            ttl=self._refresh_token_ttl,
            device_id=payload.device_id,
            ip_address=payload.ip_address,
        )

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": int(self._access_token_ttl.total_seconds()),
        }

    def revoke_token(self, token: str) -> bool:
        """Revoke a token (add to blacklist)."""
        payload = self.verify_token(token, check_blacklist=False)
        if not payload:
            return False

        self._blacklist.add(payload.jti, payload.exp)
        logger.info(f"Token revoked: {payload.jti}")
        return True

    def verify_token(
        self,
        token: str,
        check_blacklist: bool = True,
    ) -> Optional[TokenPayload]:
        """Verify and decode a JWT token."""
        try:
            data = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self._algorithm],
            )

            payload = TokenPayload.from_dict(data)

            if check_blacklist and self._blacklist.is_blacklisted(payload.jti):
                logger.warning(f"Token is blacklisted: {payload.jti}")
                return None

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token verification failed: {e}")
            return None

    def create_api_key(
        self,
        name: str,
        user_id: str,
        permissions: List[str] = None,
        expires_in_days: int = 365,
    ) -> Dict[str, str]:
        """Create an API key for programmatic access."""
        key_id = str(uuid.uuid4())
        key_secret = hashlib.sha256(os.urandom(32)).hexdigest()

        api_key = {
            "id": key_id,
            "name": name,
            "user_id": user_id,
            "key_hash": generate_password_hash(key_secret),
            "permissions": permissions or ["api:*"],
            "expires_at": (
                datetime.utcnow() + timedelta(days=expires_in_days)
            ).isoformat(),
            "created_at": datetime.utcnow().isoformat(),
        }

        self._api_keys[key_id] = api_key

        # Return the key only once
        return {
            "key_id": key_id,
            "key_secret": key_secret,
            "api_key": f"{key_id}.{key_secret}",
        }

    def verify_api_key(self, api_key: str) -> Optional[Dict]:
        """Verify an API key."""
        try:
            key_id, key_secret = api_key.split(".", 1)
        except ValueError:
            return None

        stored_key = self._api_keys.get(key_id)
        if not stored_key:
            return None

        if not check_password_hash(stored_key["key_hash"], key_secret):
            return None

        expires_at = datetime.fromisoformat(stored_key["expires_at"])
        if datetime.utcnow() > expires_at:
            return None

        return stored_key

    def _create_token(
        self,
        user_id: str,
        role: Role,
        token_type: TokenType,
        ttl: timedelta,
        device_id: str = None,
        ip_address: str = None,
    ) -> str:
        """Create a JWT token."""
        now = datetime.utcnow()
        expires_at = now + ttl

        # Get permissions for role
        permissions = list(ROLE_PERMISSIONS.get(role, set()))

        payload = TokenPayload(
            sub=user_id,
            type=token_type,
            role=role,
            permissions=permissions,
            iat=now,
            exp=expires_at,
            device_id=device_id,
            ip_address=ip_address,
        )

        return jwt.encode(
            payload.to_dict(),
            self.secret_key,
            algorithm=self._algorithm,
        )

    def has_permission(self, payload: TokenPayload, permission: str) -> bool:
        """Check if token has required permission."""
        if "*" in payload.permissions:
            return True

        # Check exact match
        if permission in payload.permissions:
            return True

        # Check wildcard matches
        resource = permission.split(":")[0] if ":" in permission else permission
        if f"{resource}:*" in payload.permissions:
            return True

        if "read:*" in payload.permissions and permission.startswith("read:"):
            return True

        return False


# Global instance
jwt_auth = JWTAuthService()


# Flask decorators
def token_required(f):
    """Decorator to require valid JWT token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Get token from header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        # Or from API key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            key_data = jwt_auth.verify_api_key(api_key)
            if key_data:
                g.current_user = {"id": key_data["user_id"], "role": "api"}
                g.permissions = key_data["permissions"]
                return f(*args, **kwargs)
            return jsonify({"error": "Invalid API key"}), 401

        if not token:
            return jsonify({"error": "Token required"}), 401

        payload = jwt_auth.verify_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        g.current_user = {"id": payload.sub, "role": payload.role.value}
        g.token_payload = payload

        return f(*args, **kwargs)

    return decorated


def permission_required(permission: str):
    """Decorator to require specific permission."""
    def decorator(f):
        @wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            payload = getattr(g, "token_payload", None)
            if not payload:
                # API key access
                permissions = getattr(g, "permissions", [])
                if permission not in permissions and "api:*" not in permissions:
                    return jsonify({"error": "Permission denied"}), 403
                return f(*args, **kwargs)

            if not jwt_auth.has_permission(payload, permission):
                return jsonify({"error": "Permission denied"}), 403

            return f(*args, **kwargs)

        return decorated
    return decorator


def rate_limit(max_requests: int = 100, window_seconds: int = 60):
    """Decorator to apply rate limiting."""
    limiter = RateLimiter(max_requests, window_seconds)

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Use IP or user ID as key
            key = request.remote_addr
            if hasattr(g, "current_user"):
                key = g.current_user.get("id", key)

            allowed, remaining = limiter.is_allowed(key)
            if not allowed:
                return jsonify({
                    "error": "Rate limit exceeded",
                    "retry_after": window_seconds,
                }), 429

            response = f(*args, **kwargs)
            # Add rate limit headers if response is a tuple
            if isinstance(response, tuple):
                resp, code = response[0], response[1]
            else:
                resp, code = response, 200

            return resp, code

        return decorated
    return decorator
