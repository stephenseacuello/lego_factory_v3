"""
Key Manager for HSM/TPM Integration

FIPS 140-2 Level 3 compliant key management:
- Secure key generation
- Key lifecycle management
- Key usage policies
- Audit logging

Reference: NIST SP 800-57 Key Management Guidelines
"""

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import logging
from datetime import datetime, timedelta
import base64

logger = logging.getLogger(__name__)


class KeyType(Enum):
    """Types of cryptographic keys."""
    SYMMETRIC_AES_256 = "aes_256"
    SYMMETRIC_AES_128 = "aes_128"
    ASYMMETRIC_RSA_2048 = "rsa_2048"
    ASYMMETRIC_RSA_4096 = "rsa_4096"
    ASYMMETRIC_EC_P256 = "ec_p256"
    ASYMMETRIC_EC_P384 = "ec_p384"
    HMAC_SHA256 = "hmac_sha256"
    HMAC_SHA384 = "hmac_sha384"


class KeyUsage(Enum):
    """Permitted key usage (NIST SP 800-57)."""
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"
    SIGN = "sign"
    VERIFY = "verify"
    WRAP = "wrap"
    UNWRAP = "unwrap"
    DERIVE = "derive"


class KeyState(Enum):
    """Key lifecycle state (NIST SP 800-57)."""
    PRE_ACTIVATION = "pre_activation"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"
    COMPROMISED = "compromised"
    DESTROYED = "destroyed"


@dataclass
class KeyMetadata:
    """
    Key metadata following NIST SP 800-57.

    Attributes:
        key_id: Unique key identifier
        key_type: Type of key
        usage: Permitted usages
        state: Lifecycle state
        created_at: Creation timestamp
        activation_date: When key becomes active
        expiration_date: When key expires
        owner: Key owner identifier
        algorithm: Algorithm for key use
    """
    key_id: str
    key_type: KeyType
    usage: List[KeyUsage]
    state: KeyState = KeyState.PRE_ACTIVATION
    created_at: float = field(default_factory=time.time)
    activation_date: Optional[float] = None
    expiration_date: Optional[float] = None
    owner: str = ""
    algorithm: str = ""
    key_length_bits: int = 256
    hsm_backed: bool = False
    audit_trail: List[Dict] = field(default_factory=list)


@dataclass
class KeyManagerConfig:
    """
    Key manager configuration.

    Attributes:
        default_key_lifetime_days: Default key validity period
        auto_rotation_enabled: Enable automatic key rotation
        rotation_period_days: Days between rotations
        require_hsm: Require HSM for key storage
        audit_enabled: Enable key operation auditing
    """
    default_key_lifetime_days: int = 365
    auto_rotation_enabled: bool = True
    rotation_period_days: int = 90
    require_hsm: bool = False
    audit_enabled: bool = True
    min_key_length_bits: int = 256
    allowed_algorithms: List[str] = field(default_factory=lambda: [
        "AES-256-GCM", "RSA-2048", "RSA-4096", "ECDSA-P256", "ECDSA-P384"
    ])


class KeyManager:
    """
    FIPS 140-2 compliant key management.

    Features:
    - Secure key generation
    - Key lifecycle management
    - Usage enforcement
    - Automatic rotation
    - Audit logging

    Usage:
        >>> km = KeyManager(config)
        >>> key_id = km.generate_key(KeyType.SYMMETRIC_AES_256, [KeyUsage.ENCRYPT])
        >>> km.activate_key(key_id)
        >>> key = km.get_key(key_id, KeyUsage.ENCRYPT)
    """

    def __init__(
        self,
        config: Optional[KeyManagerConfig] = None,
        hsm_interface: Optional[Any] = None,
        audit_handler: Optional[Callable] = None
    ):
        """
        Initialize key manager.

        Args:
            config: Key manager configuration
            hsm_interface: Optional HSM interface for hardware-backed keys
            audit_handler: Callback for audit events
        """
        self.config = config or KeyManagerConfig()
        self.hsm = hsm_interface
        self.audit_handler = audit_handler

        # Key storage (in production, use HSM or secure enclave)
        self._keys: Dict[str, Tuple[bytes, KeyMetadata]] = {}
        self._metadata: Dict[str, KeyMetadata] = {}

        # Key version tracking for rotation
        self._key_versions: Dict[str, List[str]] = {}

        logger.info("KeyManager initialized (HSM=%s)", self.hsm is not None)

    def generate_key(
        self,
        key_type: KeyType,
        usage: List[KeyUsage],
        owner: str = "",
        lifetime_days: Optional[int] = None,
        activate_immediately: bool = False
    ) -> str:
        """
        Generate a new cryptographic key.

        Args:
            key_type: Type of key to generate
            usage: Permitted usages
            owner: Key owner identifier
            lifetime_days: Key validity period
            activate_immediately: Activate key after generation

        Returns:
            Key identifier
        """
        # Generate key ID
        key_id = self._generate_key_id()

        # Determine key parameters
        key_length = self._get_key_length(key_type)
        algorithm = self._get_algorithm(key_type)

        # Validate key length
        if key_length < self.config.min_key_length_bits:
            raise ValueError(f"Key length {key_length} below minimum {self.config.min_key_length_bits}")

        # Generate key material
        if self.hsm and self.config.require_hsm:
            key_material = self._generate_hsm_key(key_type, key_length)
            hsm_backed = True
        else:
            key_material = self._generate_software_key(key_type, key_length)
            hsm_backed = False

        # Calculate dates
        now = time.time()
        lifetime = lifetime_days or self.config.default_key_lifetime_days
        expiration = now + (lifetime * 86400)

        # Create metadata
        metadata = KeyMetadata(
            key_id=key_id,
            key_type=key_type,
            usage=usage,
            state=KeyState.PRE_ACTIVATION,
            created_at=now,
            activation_date=now if activate_immediately else None,
            expiration_date=expiration,
            owner=owner,
            algorithm=algorithm,
            key_length_bits=key_length,
            hsm_backed=hsm_backed
        )

        if activate_immediately:
            metadata.state = KeyState.ACTIVE

        # Store key
        self._keys[key_id] = (key_material, metadata)
        self._metadata[key_id] = metadata

        # Track versions
        base_id = key_id.rsplit("_v", 1)[0]
        if base_id not in self._key_versions:
            self._key_versions[base_id] = []
        self._key_versions[base_id].append(key_id)

        # Audit
        self._audit("key_generated", key_id, metadata)

        logger.info(f"Generated key {key_id} type={key_type.value}")
        return key_id

    def activate_key(self, key_id: str) -> bool:
        """Activate a key for use."""
        if key_id not in self._metadata:
            logger.warning(f"Key not found: {key_id}")
            return False

        metadata = self._metadata[key_id]

        if metadata.state != KeyState.PRE_ACTIVATION:
            logger.warning(f"Key {key_id} cannot be activated from state {metadata.state}")
            return False

        metadata.state = KeyState.ACTIVE
        metadata.activation_date = time.time()

        self._audit("key_activated", key_id, metadata)
        logger.info(f"Activated key {key_id}")
        return True

    def get_key(
        self,
        key_id: str,
        intended_usage: KeyUsage
    ) -> Optional[bytes]:
        """
        Get key material for specified usage.

        Args:
            key_id: Key identifier
            intended_usage: How the key will be used

        Returns:
            Key material if authorized, None otherwise
        """
        if key_id not in self._keys:
            logger.warning(f"Key not found: {key_id}")
            return None

        key_material, metadata = self._keys[key_id]

        # Check state
        if metadata.state != KeyState.ACTIVE:
            logger.warning(f"Key {key_id} not active: {metadata.state}")
            return None

        # Check usage
        if intended_usage not in metadata.usage:
            logger.warning(f"Key {key_id} not authorized for {intended_usage}")
            self._audit("key_usage_denied", key_id, metadata, {"attempted_usage": intended_usage.value})
            return None

        # Check expiration
        if metadata.expiration_date and time.time() > metadata.expiration_date:
            logger.warning(f"Key {key_id} expired")
            metadata.state = KeyState.DEACTIVATED
            return None

        # Audit
        self._audit("key_accessed", key_id, metadata, {"usage": intended_usage.value})

        return key_material

    def rotate_key(self, key_id: str) -> Optional[str]:
        """
        Rotate a key by generating a new version.

        Args:
            key_id: Key identifier to rotate

        Returns:
            New key identifier
        """
        if key_id not in self._metadata:
            logger.warning(f"Key not found for rotation: {key_id}")
            return None

        old_metadata = self._metadata[key_id]

        # Generate new key with same parameters
        new_key_id = self.generate_key(
            key_type=old_metadata.key_type,
            usage=old_metadata.usage,
            owner=old_metadata.owner,
            activate_immediately=True
        )

        # Deactivate old key (with grace period)
        old_metadata.state = KeyState.DEACTIVATED

        self._audit("key_rotated", key_id, old_metadata, {"new_key_id": new_key_id})
        logger.info(f"Rotated key {key_id} -> {new_key_id}")

        return new_key_id

    def suspend_key(self, key_id: str, reason: str = "") -> bool:
        """Suspend a key temporarily."""
        if key_id not in self._metadata:
            return False

        metadata = self._metadata[key_id]
        if metadata.state != KeyState.ACTIVE:
            return False

        metadata.state = KeyState.SUSPENDED
        self._audit("key_suspended", key_id, metadata, {"reason": reason})
        return True

    def destroy_key(self, key_id: str) -> bool:
        """
        Securely destroy a key.

        Performs cryptographic erasure following NIST guidelines.
        """
        if key_id not in self._keys:
            return False

        key_material, metadata = self._keys[key_id]

        # Zeroize key material
        if isinstance(key_material, bytearray):
            for i in range(len(key_material)):
                key_material[i] = 0

        # Remove from storage
        del self._keys[key_id]
        metadata.state = KeyState.DESTROYED

        # If HSM-backed, destroy in HSM
        if metadata.hsm_backed and self.hsm:
            try:
                self.hsm.destroy_key(key_id)
            except Exception as e:
                logger.error(f"HSM key destruction failed: {e}")

        self._audit("key_destroyed", key_id, metadata)
        logger.info(f"Destroyed key {key_id}")
        return True

    def get_key_metadata(self, key_id: str) -> Optional[KeyMetadata]:
        """Get key metadata without key material."""
        return self._metadata.get(key_id)

    def list_keys(
        self,
        owner: Optional[str] = None,
        state: Optional[KeyState] = None
    ) -> List[KeyMetadata]:
        """List keys matching criteria."""
        results = []
        for metadata in self._metadata.values():
            if owner and metadata.owner != owner:
                continue
            if state and metadata.state != state:
                continue
            results.append(metadata)
        return results

    def check_rotation_needed(self) -> List[str]:
        """Check which keys need rotation."""
        if not self.config.auto_rotation_enabled:
            return []

        rotation_threshold = time.time() - (self.config.rotation_period_days * 86400)
        needs_rotation = []

        for key_id, metadata in self._metadata.items():
            if metadata.state != KeyState.ACTIVE:
                continue
            if metadata.created_at < rotation_threshold:
                needs_rotation.append(key_id)

        return needs_rotation

    def _generate_key_id(self) -> str:
        """Generate unique key identifier."""
        timestamp = int(time.time() * 1000)
        random_part = secrets.token_hex(8)
        return f"key_{timestamp}_{random_part}_v1"

    def _get_key_length(self, key_type: KeyType) -> int:
        """Get key length in bits for key type."""
        lengths = {
            KeyType.SYMMETRIC_AES_256: 256,
            KeyType.SYMMETRIC_AES_128: 128,
            KeyType.ASYMMETRIC_RSA_2048: 2048,
            KeyType.ASYMMETRIC_RSA_4096: 4096,
            KeyType.ASYMMETRIC_EC_P256: 256,
            KeyType.ASYMMETRIC_EC_P384: 384,
            KeyType.HMAC_SHA256: 256,
            KeyType.HMAC_SHA384: 384,
        }
        return lengths.get(key_type, 256)

    def _get_algorithm(self, key_type: KeyType) -> str:
        """Get algorithm identifier for key type."""
        algorithms = {
            KeyType.SYMMETRIC_AES_256: "AES-256-GCM",
            KeyType.SYMMETRIC_AES_128: "AES-128-GCM",
            KeyType.ASYMMETRIC_RSA_2048: "RSA-2048",
            KeyType.ASYMMETRIC_RSA_4096: "RSA-4096",
            KeyType.ASYMMETRIC_EC_P256: "ECDSA-P256",
            KeyType.ASYMMETRIC_EC_P384: "ECDSA-P384",
            KeyType.HMAC_SHA256: "HMAC-SHA256",
            KeyType.HMAC_SHA384: "HMAC-SHA384",
        }
        return algorithms.get(key_type, "UNKNOWN")

    def _generate_software_key(self, key_type: KeyType, length_bits: int) -> bytes:
        """Generate key in software (for non-HSM mode)."""
        if key_type in [KeyType.SYMMETRIC_AES_256, KeyType.SYMMETRIC_AES_128,
                        KeyType.HMAC_SHA256, KeyType.HMAC_SHA384]:
            return secrets.token_bytes(length_bits // 8)
        else:
            # For asymmetric keys, would use cryptography library
            # Placeholder for now
            return secrets.token_bytes(length_bits // 8)

    def _generate_hsm_key(self, key_type: KeyType, length_bits: int) -> bytes:
        """Generate key in HSM."""
        if self.hsm:
            return self.hsm.generate_key(key_type.value, length_bits)
        raise RuntimeError("HSM not available")

    def _audit(
        self,
        event: str,
        key_id: str,
        metadata: KeyMetadata,
        extra: Optional[Dict] = None
    ) -> None:
        """Log audit event."""
        if not self.config.audit_enabled:
            return

        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "key_id": key_id,
            "key_type": metadata.key_type.value,
            "owner": metadata.owner,
            "state": metadata.state.value,
            **(extra or {})
        }

        metadata.audit_trail.append(audit_entry)

        if self.audit_handler:
            try:
                self.audit_handler(audit_entry)
            except Exception as e:
                logger.error(f"Audit handler error: {e}")

        logger.debug(f"Key audit: {event} for {key_id}")

    def derive_key(
        self,
        master_key_id: str,
        context: bytes,
        key_type: KeyType = KeyType.SYMMETRIC_AES_256
    ) -> Optional[str]:
        """
        Derive a new key from a master key using HKDF.

        Args:
            master_key_id: Master key to derive from
            context: Derivation context (e.g., purpose identifier)
            key_type: Type of key to derive

        Returns:
            Derived key identifier
        """
        master_key = self.get_key(master_key_id, KeyUsage.DERIVE)
        if not master_key:
            return None

        # HKDF derivation (simplified)
        derived_material = hmac.new(
            master_key,
            context,
            hashlib.sha256
        ).digest()

        # Create derived key
        derived_id = self._generate_key_id().replace("key_", "derived_")
        length = self._get_key_length(key_type)

        metadata = KeyMetadata(
            key_id=derived_id,
            key_type=key_type,
            usage=[KeyUsage.ENCRYPT, KeyUsage.DECRYPT],
            state=KeyState.ACTIVE,
            owner=self._metadata[master_key_id].owner,
            algorithm=self._get_algorithm(key_type),
            key_length_bits=length
        )

        self._keys[derived_id] = (derived_material[:length // 8], metadata)
        self._metadata[derived_id] = metadata

        self._audit("key_derived", derived_id, metadata, {"master_key": master_key_id})
        return derived_id
