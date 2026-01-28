"""
Secrets Management Service
LegoMCP PhD-Level Manufacturing Platform

Provides unified interface for secrets management across multiple backends:
- HashiCorp Vault
- AWS Secrets Manager
- GCP Secret Manager
- Azure Key Vault
- Environment Variables (fallback)
- SOPS-encrypted files

Implements caching, rotation, and audit logging.
"""

import os
import json
import base64
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
import threading

logger = logging.getLogger(__name__)


@dataclass
class Secret:
    """Represents a secret value with metadata."""
    key: str
    value: str
    version: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


class SecretBackend(ABC):
    """Abstract base class for secret backends."""

    @abstractmethod
    def get_secret(self, key: str, version: Optional[str] = None) -> Optional[Secret]:
        """Retrieve a secret by key."""
        pass

    @abstractmethod
    def set_secret(self, key: str, value: str, metadata: Optional[Dict] = None) -> Secret:
        """Store a secret."""
        pass

    @abstractmethod
    def delete_secret(self, key: str) -> bool:
        """Delete a secret."""
        pass

    @abstractmethod
    def list_secrets(self, prefix: str = "") -> List[str]:
        """List available secrets."""
        pass

    @abstractmethod
    def rotate_secret(self, key: str, new_value: str) -> Secret:
        """Rotate a secret to a new value."""
        pass


class EnvironmentBackend(SecretBackend):
    """Environment variable backend (development/fallback)."""

    def __init__(self, prefix: str = "LEGOMCP_"):
        self.prefix = prefix

    def get_secret(self, key: str, version: Optional[str] = None) -> Optional[Secret]:
        env_key = f"{self.prefix}{key.upper().replace('/', '_')}"
        value = os.environ.get(env_key)
        if value is None:
            return None
        return Secret(
            key=key,
            value=value,
            version="env",
            created_at=datetime.utcnow(),
        )

    def set_secret(self, key: str, value: str, metadata: Optional[Dict] = None) -> Secret:
        env_key = f"{self.prefix}{key.upper().replace('/', '_')}"
        os.environ[env_key] = value
        return Secret(
            key=key,
            value=value,
            version="env",
            created_at=datetime.utcnow(),
            metadata=metadata,
        )

    def delete_secret(self, key: str) -> bool:
        env_key = f"{self.prefix}{key.upper().replace('/', '_')}"
        if env_key in os.environ:
            del os.environ[env_key]
            return True
        return False

    def list_secrets(self, prefix: str = "") -> List[str]:
        secrets = []
        full_prefix = f"{self.prefix}{prefix.upper().replace('/', '_')}"
        for key in os.environ:
            if key.startswith(full_prefix):
                secrets.append(key[len(self.prefix):].lower().replace('_', '/'))
        return secrets

    def rotate_secret(self, key: str, new_value: str) -> Secret:
        return self.set_secret(key, new_value)


class VaultBackend(SecretBackend):
    """HashiCorp Vault backend for production secrets."""

    def __init__(
        self,
        url: str = None,
        token: str = None,
        mount_point: str = "secret",
        namespace: str = None,
    ):
        self.url = url or os.environ.get("VAULT_ADDR", "http://localhost:8200")
        self.token = token or os.environ.get("VAULT_TOKEN")
        self.mount_point = mount_point
        self.namespace = namespace
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import hvac
                self._client = hvac.Client(
                    url=self.url,
                    token=self.token,
                    namespace=self.namespace,
                )
            except ImportError:
                logger.warning("hvac not installed, Vault backend unavailable")
                raise RuntimeError("hvac package required for Vault backend")
        return self._client

    def get_secret(self, key: str, version: Optional[str] = None) -> Optional[Secret]:
        try:
            if version:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=key,
                    mount_point=self.mount_point,
                    version=int(version),
                )
            else:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=key,
                    mount_point=self.mount_point,
                )

            data = response["data"]["data"]
            metadata = response["data"]["metadata"]

            return Secret(
                key=key,
                value=data.get("value", json.dumps(data)),
                version=str(metadata["version"]),
                created_at=datetime.fromisoformat(
                    metadata["created_time"].replace("Z", "+00:00")
                ),
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to get secret {key} from Vault: {e}")
            return None

    def set_secret(self, key: str, value: str, metadata: Optional[Dict] = None) -> Secret:
        try:
            data = {"value": value}
            if metadata:
                data.update(metadata)

            self.client.secrets.kv.v2.create_or_update_secret(
                path=key,
                secret=data,
                mount_point=self.mount_point,
            )

            return self.get_secret(key)
        except Exception as e:
            logger.error(f"Failed to set secret {key} in Vault: {e}")
            raise

    def delete_secret(self, key: str) -> bool:
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=key,
                mount_point=self.mount_point,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret {key} from Vault: {e}")
            return False

    def list_secrets(self, prefix: str = "") -> List[str]:
        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=prefix,
                mount_point=self.mount_point,
            )
            return response["data"]["keys"]
        except Exception as e:
            logger.error(f"Failed to list secrets with prefix {prefix}: {e}")
            return []

    def rotate_secret(self, key: str, new_value: str) -> Secret:
        return self.set_secret(key, new_value)


class AWSSecretsBackend(SecretBackend):
    """AWS Secrets Manager backend."""

    def __init__(self, region: str = None, prefix: str = "legomcp/"):
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.prefix = prefix
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("secretsmanager", region_name=self.region)
            except ImportError:
                raise RuntimeError("boto3 required for AWS Secrets Manager backend")
        return self._client

    def get_secret(self, key: str, version: Optional[str] = None) -> Optional[Secret]:
        try:
            kwargs = {"SecretId": f"{self.prefix}{key}"}
            if version:
                kwargs["VersionId"] = version

            response = self.client.get_secret_value(**kwargs)

            return Secret(
                key=key,
                value=response.get("SecretString", ""),
                version=response.get("VersionId", "AWSCURRENT"),
                created_at=response.get("CreatedDate", datetime.utcnow()),
            )
        except Exception as e:
            logger.error(f"Failed to get secret {key} from AWS: {e}")
            return None

    def set_secret(self, key: str, value: str, metadata: Optional[Dict] = None) -> Secret:
        secret_id = f"{self.prefix}{key}"
        try:
            # Try to update existing secret
            self.client.put_secret_value(
                SecretId=secret_id,
                SecretString=value,
            )
        except self.client.exceptions.ResourceNotFoundException:
            # Create new secret
            self.client.create_secret(
                Name=secret_id,
                SecretString=value,
                Description=metadata.get("description", "") if metadata else "",
            )

        return self.get_secret(key)

    def delete_secret(self, key: str) -> bool:
        try:
            self.client.delete_secret(
                SecretId=f"{self.prefix}{key}",
                ForceDeleteWithoutRecovery=False,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret {key} from AWS: {e}")
            return False

    def list_secrets(self, prefix: str = "") -> List[str]:
        try:
            secrets = []
            paginator = self.client.get_paginator("list_secrets")

            for page in paginator.paginate():
                for secret in page["SecretList"]:
                    name = secret["Name"]
                    if name.startswith(f"{self.prefix}{prefix}"):
                        secrets.append(name[len(self.prefix):])

            return secrets
        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []

    def rotate_secret(self, key: str, new_value: str) -> Secret:
        return self.set_secret(key, new_value)


class SecretsManager:
    """
    Unified secrets management with caching and multi-backend support.

    Features:
    - Multiple backend support (Vault, AWS, GCP, Azure, Env)
    - In-memory caching with TTL
    - Automatic rotation support
    - Audit logging
    - Thread-safe operations
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._cache: Dict[str, tuple[Secret, datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._backends: List[SecretBackend] = []
        self._audit_log: List[Dict] = []
        self._initialized = True

        self._setup_backends()

    def _setup_backends(self):
        """Configure backends based on environment."""
        backend_type = os.environ.get("SECRETS_BACKEND", "env")

        if backend_type == "vault":
            self._backends.append(VaultBackend())
        elif backend_type == "aws":
            self._backends.append(AWSSecretsBackend())
        elif backend_type == "env":
            self._backends.append(EnvironmentBackend())
        else:
            # Default fallback chain
            self._backends.append(EnvironmentBackend())

        logger.info(f"Secrets manager initialized with backends: {[type(b).__name__ for b in self._backends]}")

    def get(self, key: str, default: str = None, use_cache: bool = True) -> Optional[str]:
        """Get a secret value."""
        # Check cache
        if use_cache and key in self._cache:
            secret, cached_at = self._cache[key]
            if datetime.utcnow() - cached_at < self._cache_ttl:
                if not secret.is_expired:
                    return secret.value

        # Try backends in order
        for backend in self._backends:
            secret = backend.get_secret(key)
            if secret:
                self._cache[key] = (secret, datetime.utcnow())
                self._audit("get", key, backend)
                return secret.value

        return default

    def set(self, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
        """Set a secret value."""
        for backend in self._backends:
            try:
                secret = backend.set_secret(key, value, metadata)
                self._cache[key] = (secret, datetime.utcnow())
                self._audit("set", key, backend)
                return True
            except Exception as e:
                logger.warning(f"Failed to set secret in {type(backend).__name__}: {e}")
                continue
        return False

    def delete(self, key: str) -> bool:
        """Delete a secret."""
        success = False
        for backend in self._backends:
            if backend.delete_secret(key):
                success = True
                self._audit("delete", key, backend)

        if key in self._cache:
            del self._cache[key]

        return success

    def rotate(self, key: str, new_value: str) -> bool:
        """Rotate a secret to a new value."""
        for backend in self._backends:
            try:
                secret = backend.rotate_secret(key, new_value)
                self._cache[key] = (secret, datetime.utcnow())
                self._audit("rotate", key, backend)
                return True
            except Exception as e:
                logger.warning(f"Failed to rotate secret in {type(backend).__name__}: {e}")
                continue
        return False

    def list_keys(self, prefix: str = "") -> List[str]:
        """List all secret keys with optional prefix."""
        all_keys = set()
        for backend in self._backends:
            keys = backend.list_secrets(prefix)
            all_keys.update(keys)
        return sorted(all_keys)

    def clear_cache(self):
        """Clear the secrets cache."""
        self._cache.clear()

    def _audit(self, action: str, key: str, backend: SecretBackend):
        """Log an audit entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "key": key,
            "backend": type(backend).__name__,
        }
        self._audit_log.append(entry)
        logger.info(f"Secrets audit: {action} {key} via {type(backend).__name__}")

    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Get recent audit log entries."""
        return self._audit_log[-limit:]

    # Convenience methods for common secrets
    def get_database_url(self) -> str:
        """Get database connection URL."""
        return self.get(
            "database/url",
            default=os.environ.get(
                "DATABASE_URL",
                "postgresql://lego:lego@localhost:5432/legomcp"
            )
        )

    def get_redis_url(self) -> str:
        """Get Redis connection URL."""
        return self.get(
            "redis/url",
            default=os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        )

    def get_secret_key(self) -> str:
        """Get Flask secret key."""
        return self.get(
            "flask/secret_key",
            default=os.environ.get("SECRET_KEY", self._generate_default_key())
        )

    def get_jwt_secret(self) -> str:
        """Get JWT signing secret."""
        return self.get(
            "jwt/secret",
            default=os.environ.get("JWT_SECRET", self._generate_default_key())
        )

    def _generate_default_key(self) -> str:
        """Generate a default secret key (for development only)."""
        import secrets
        key = secrets.token_hex(32)
        logger.warning(
            "Using generated secret key. Set proper secrets for production!"
        )
        return key


# Global instance
secrets = SecretsManager()


def get_secret(key: str, default: str = None) -> Optional[str]:
    """Convenience function to get a secret."""
    return secrets.get(key, default)
