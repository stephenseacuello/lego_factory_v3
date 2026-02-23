"""
HSM-Backed Audit Trail Sealer

Provides cryptographic sealing of the audit trail using Hardware Security Module
(or software HSM simulation) for tamper-evident compliance logging.

Features:
- Daily cryptographic seals on audit chain
- HSM-backed HMAC signing
- Seal verification and chain validation
- Tamper detection
- NIST 800-171 AU family compliance

Usage:
    from dashboard.services.traceability.hsm_sealer import HSMSealer
    from dashboard.services.security.hsm.key_manager import KeyManager

    key_manager = KeyManager()
    sealer = HSMSealer(key_manager=key_manager)

    # Create daily seal
    seal = sealer.create_seal(chain_hash, event_count)

    # Verify seal
    is_valid = sealer.verify_seal(seal)

Author: LegoMCP Team
Version: 1.0.0
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

# Import HSM components
try:
    from ..security.hsm.key_manager import (
        KeyManager,
        KeyType,
        KeyUsage,
        KeyState,
    )
    HSM_AVAILABLE = True
except ImportError:
    HSM_AVAILABLE = False
    KeyManager = None
    KeyType = None
    KeyUsage = None


class SealType(Enum):
    """Types of audit seals."""
    DAILY = "daily"
    HOURLY = "hourly"
    CHECKPOINT = "checkpoint"
    EMERGENCY = "emergency"


class SealStatus(Enum):
    """Seal verification status."""
    VALID = "valid"
    INVALID = "invalid"
    TAMPERED = "tampered"
    EXPIRED = "expired"
    KEY_NOT_FOUND = "key_not_found"


@dataclass
class AuditSeal:
    """
    Cryptographic seal for audit trail.

    A seal cryptographically binds:
    - The current chain hash
    - Event count at seal time
    - Timestamp
    - Previous seal reference

    This creates a chain of seals that can detect tampering
    even if the underlying audit events are modified.
    """
    seal_id: str
    seal_type: SealType
    chain_hash: str
    event_count: int
    timestamp: datetime
    previous_seal_id: Optional[str]
    previous_seal_hash: Optional[str]
    signature: str
    key_id: str
    algorithm: str = "HMAC-SHA256"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert seal to dictionary."""
        return {
            "seal_id": self.seal_id,
            "seal_type": self.seal_type.value,
            "chain_hash": self.chain_hash,
            "event_count": self.event_count,
            "timestamp": self.timestamp.isoformat(),
            "previous_seal_id": self.previous_seal_id,
            "previous_seal_hash": self.previous_seal_hash,
            "signature": self.signature,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditSeal":
        """Create seal from dictionary."""
        return cls(
            seal_id=data["seal_id"],
            seal_type=SealType(data["seal_type"]),
            chain_hash=data["chain_hash"],
            event_count=data["event_count"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            previous_seal_id=data.get("previous_seal_id"),
            previous_seal_hash=data.get("previous_seal_hash"),
            signature=data["signature"],
            key_id=data["key_id"],
            algorithm=data.get("algorithm", "HMAC-SHA256"),
            metadata=data.get("metadata", {}),
        )

    def compute_hash(self) -> str:
        """Compute hash of seal (for chaining)."""
        hash_input = {
            "seal_id": self.seal_id,
            "seal_type": self.seal_type.value,
            "chain_hash": self.chain_hash,
            "event_count": self.event_count,
            "timestamp": self.timestamp.isoformat(),
            "previous_seal_id": self.previous_seal_id,
            "previous_seal_hash": self.previous_seal_hash,
            "signature": self.signature,
        }
        json_str = json.dumps(hash_input, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()


@dataclass
class SealVerificationResult:
    """Result of seal verification."""
    status: SealStatus
    seal_id: str
    is_valid: bool
    error_message: str = ""
    verified_at: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)


class HSMSealer:
    """
    HSM-backed audit trail sealer.

    Creates cryptographic seals on the audit trail using HSM-protected
    keys for tamper-evident compliance logging.

    Features:
    - HMAC-SHA256 signatures using HSM keys
    - Seal chaining for tamper detection
    - Daily automatic sealing
    - Verification of seal chains
    - Software HSM simulation mode

    Usage:
        >>> key_manager = KeyManager()
        >>> sealer = HSMSealer(key_manager=key_manager)
        >>>
        >>> # Create a seal
        >>> seal = sealer.create_seal(
        ...     chain_hash="abc123...",
        ...     event_count=1000,
        ... )
        >>>
        >>> # Verify seal
        >>> result = sealer.verify_seal(seal)
        >>> print(result.is_valid)
    """

    SEAL_KEY_OWNER = "audit_sealer"
    SEAL_KEY_PREFIX = "audit_seal_key"

    def __init__(
        self,
        key_manager: Optional["KeyManager"] = None,
        seal_key_id: Optional[str] = None,
        auto_create_key: bool = True,
    ):
        """
        Initialize HSM Sealer.

        Args:
            key_manager: KeyManager instance for HSM operations
            seal_key_id: Existing seal key to use
            auto_create_key: Create seal key if not exists
        """
        self._key_manager = key_manager
        self._seal_key_id = seal_key_id
        self._seals: Dict[str, AuditSeal] = {}
        self._last_seal_id: Optional[str] = None

        # Initialize or create seal key
        if self._key_manager is not None:
            if seal_key_id:
                self._seal_key_id = seal_key_id
            elif auto_create_key:
                self._seal_key_id = self._get_or_create_seal_key()

        logger.info(
            f"HSMSealer initialized: key_manager={key_manager is not None}, "
            f"seal_key={self._seal_key_id}"
        )

    def _get_or_create_seal_key(self) -> Optional[str]:
        """Get existing seal key or create new one."""
        if not self._key_manager or not HSM_AVAILABLE:
            return None

        # Look for existing seal key
        existing_keys = self._key_manager.list_keys(
            owner=self.SEAL_KEY_OWNER,
            state=KeyState.ACTIVE,
        )

        if existing_keys:
            # Use most recent active key
            return existing_keys[0].key_id

        # Create new seal key
        key_id = self._key_manager.generate_key(
            key_type=KeyType.HMAC_SHA256,
            usage=[KeyUsage.SIGN, KeyUsage.VERIFY],
            owner=self.SEAL_KEY_OWNER,
            activate_immediately=True,
        )

        logger.info(f"Created new audit seal key: {key_id}")
        return key_id

    def _generate_seal_id(self, seal_type: SealType) -> str:
        """Generate unique seal identifier."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        import secrets
        random_part = secrets.token_hex(4)
        return f"seal_{seal_type.value}_{timestamp}_{random_part}"

    def _compute_signature(
        self,
        chain_hash: str,
        event_count: int,
        timestamp: datetime,
        previous_seal_hash: Optional[str],
    ) -> str:
        """
        Compute HMAC signature for seal.

        Uses HSM key if available, otherwise software HMAC.
        """
        # Create canonical message to sign
        message = json.dumps({
            "chain_hash": chain_hash,
            "event_count": event_count,
            "timestamp": timestamp.isoformat(),
            "previous_seal_hash": previous_seal_hash or "GENESIS",
        }, sort_keys=True).encode()

        if self._key_manager and self._seal_key_id:
            # Use HSM key
            key = self._key_manager.get_key(self._seal_key_id, KeyUsage.SIGN)
            if key:
                signature = hmac.new(key, message, hashlib.sha256).hexdigest()
                return signature

        # Fallback to software key (for testing/development)
        # In production, this should fail or use a secure fallback
        fallback_key = b"DEVELOPMENT_ONLY_NOT_FOR_PRODUCTION"
        logger.warning("Using fallback software key - NOT FOR PRODUCTION")
        return hmac.new(fallback_key, message, hashlib.sha256).hexdigest()

    def _verify_signature(
        self,
        seal: AuditSeal,
    ) -> bool:
        """
        Verify seal signature.

        Uses HSM key if available for verification.
        """
        # Recreate the message that was signed
        message = json.dumps({
            "chain_hash": seal.chain_hash,
            "event_count": seal.event_count,
            "timestamp": seal.timestamp.isoformat(),
            "previous_seal_hash": seal.previous_seal_hash or "GENESIS",
        }, sort_keys=True).encode()

        if self._key_manager and self._seal_key_id:
            # Use HSM key for verification
            key = self._key_manager.get_key(self._seal_key_id, KeyUsage.VERIFY)
            if key:
                expected_signature = hmac.new(key, message, hashlib.sha256).hexdigest()
                return hmac.compare_digest(expected_signature, seal.signature)

        # Fallback verification
        fallback_key = b"DEVELOPMENT_ONLY_NOT_FOR_PRODUCTION"
        expected_signature = hmac.new(fallback_key, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_signature, seal.signature)

    def create_seal(
        self,
        chain_hash: str,
        event_count: int,
        seal_type: SealType = SealType.DAILY,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditSeal:
        """
        Create a cryptographic seal on the audit trail.

        Args:
            chain_hash: Current hash of the audit chain
            event_count: Number of events in the chain
            seal_type: Type of seal (daily, hourly, etc.)
            metadata: Additional metadata to include

        Returns:
            AuditSeal with cryptographic signature
        """
        timestamp = datetime.utcnow()
        seal_id = self._generate_seal_id(seal_type)

        # Get previous seal info for chaining
        previous_seal_id = self._last_seal_id
        previous_seal_hash = None
        if previous_seal_id and previous_seal_id in self._seals:
            previous_seal_hash = self._seals[previous_seal_id].compute_hash()

        # Compute signature
        signature = self._compute_signature(
            chain_hash=chain_hash,
            event_count=event_count,
            timestamp=timestamp,
            previous_seal_hash=previous_seal_hash,
        )

        # Create seal
        seal = AuditSeal(
            seal_id=seal_id,
            seal_type=seal_type,
            chain_hash=chain_hash,
            event_count=event_count,
            timestamp=timestamp,
            previous_seal_id=previous_seal_id,
            previous_seal_hash=previous_seal_hash,
            signature=signature,
            key_id=self._seal_key_id or "software_fallback",
            metadata=metadata or {},
        )

        # Store seal
        self._seals[seal_id] = seal
        self._last_seal_id = seal_id

        logger.info(
            f"Created {seal_type.value} seal {seal_id}: "
            f"events={event_count}, chain_hash={chain_hash[:16]}..."
        )

        return seal

    def verify_seal(self, seal: AuditSeal) -> SealVerificationResult:
        """
        Verify a single seal's integrity.

        Checks:
        1. Signature is valid (using HSM key)
        2. Chain hash is consistent
        3. Previous seal reference is valid

        Args:
            seal: AuditSeal to verify

        Returns:
            SealVerificationResult with status and details
        """
        # Verify signature
        if not self._verify_signature(seal):
            return SealVerificationResult(
                status=SealStatus.TAMPERED,
                seal_id=seal.seal_id,
                is_valid=False,
                error_message="Signature verification failed - seal may be tampered",
            )

        # Verify previous seal reference if exists
        if seal.previous_seal_id:
            if seal.previous_seal_id not in self._seals:
                # Previous seal not in our storage - might be OK if loaded from DB
                logger.debug(f"Previous seal {seal.previous_seal_id} not in memory")
            else:
                prev_seal = self._seals[seal.previous_seal_id]
                expected_hash = prev_seal.compute_hash()
                if seal.previous_seal_hash != expected_hash:
                    return SealVerificationResult(
                        status=SealStatus.TAMPERED,
                        seal_id=seal.seal_id,
                        is_valid=False,
                        error_message="Previous seal hash mismatch - chain broken",
                        details={
                            "expected_hash": expected_hash,
                            "actual_hash": seal.previous_seal_hash,
                        }
                    )

        return SealVerificationResult(
            status=SealStatus.VALID,
            seal_id=seal.seal_id,
            is_valid=True,
            details={
                "event_count": seal.event_count,
                "timestamp": seal.timestamp.isoformat(),
            }
        )

    def verify_seal_chain(
        self,
        seals: List[AuditSeal],
    ) -> Tuple[bool, List[SealVerificationResult]]:
        """
        Verify a chain of seals.

        Args:
            seals: List of seals in chronological order

        Returns:
            Tuple of (all_valid, list of verification results)
        """
        results = []
        all_valid = True

        for i, seal in enumerate(seals):
            result = self.verify_seal(seal)
            results.append(result)

            if not result.is_valid:
                all_valid = False
                logger.error(f"Seal chain broken at {seal.seal_id}: {result.error_message}")
                continue

            # Verify chain linkage
            if i > 0:
                expected_prev = seals[i - 1]
                if seal.previous_seal_id != expected_prev.seal_id:
                    all_valid = False
                    results[-1] = SealVerificationResult(
                        status=SealStatus.TAMPERED,
                        seal_id=seal.seal_id,
                        is_valid=False,
                        error_message=f"Chain linkage error: expected previous {expected_prev.seal_id}",
                    )

        return all_valid, results

    def get_seal(self, seal_id: str) -> Optional[AuditSeal]:
        """Get a seal by ID."""
        return self._seals.get(seal_id)

    def get_latest_seal(self) -> Optional[AuditSeal]:
        """Get the most recent seal."""
        if self._last_seal_id:
            return self._seals.get(self._last_seal_id)
        return None

    def list_seals(
        self,
        seal_type: Optional[SealType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[AuditSeal]:
        """
        List seals matching criteria.

        Args:
            seal_type: Filter by seal type
            start_time: Filter seals after this time
            end_time: Filter seals before this time

        Returns:
            List of matching AuditSeals
        """
        results = []
        for seal in self._seals.values():
            if seal_type and seal.seal_type != seal_type:
                continue
            if start_time and seal.timestamp < start_time:
                continue
            if end_time and seal.timestamp > end_time:
                continue
            results.append(seal)

        # Sort by timestamp
        results.sort(key=lambda s: s.timestamp)
        return results

    def export_seals(self, output_path: str) -> int:
        """
        Export all seals to a JSON file.

        Args:
            output_path: Path to output file

        Returns:
            Number of seals exported
        """
        seals_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "seal_count": len(self._seals),
            "seals": [seal.to_dict() for seal in self._seals.values()],
        }

        with open(output_path, 'w') as f:
            json.dump(seals_data, f, indent=2)

        logger.info(f"Exported {len(self._seals)} seals to {output_path}")
        return len(self._seals)

    def import_seals(self, input_path: str) -> int:
        """
        Import seals from a JSON file.

        Args:
            input_path: Path to input file

        Returns:
            Number of seals imported
        """
        with open(input_path, 'r') as f:
            data = json.load(f)

        count = 0
        for seal_data in data.get("seals", []):
            seal = AuditSeal.from_dict(seal_data)
            self._seals[seal.seal_id] = seal
            count += 1

            # Track latest seal
            if self._last_seal_id is None or seal.timestamp > self._seals.get(self._last_seal_id, seal).timestamp:
                self._last_seal_id = seal.seal_id

        logger.info(f"Imported {count} seals from {input_path}")
        return count

    def get_statistics(self) -> Dict[str, Any]:
        """Get sealing statistics."""
        seals = list(self._seals.values())

        if not seals:
            return {
                "total_seals": 0,
                "seals_by_type": {},
                "first_seal": None,
                "last_seal": None,
            }

        seals_by_type = {}
        for seal in seals:
            seal_type = seal.seal_type.value
            seals_by_type[seal_type] = seals_by_type.get(seal_type, 0) + 1

        timestamps = [s.timestamp for s in seals]

        return {
            "total_seals": len(seals),
            "seals_by_type": seals_by_type,
            "first_seal": min(timestamps).isoformat(),
            "last_seal": max(timestamps).isoformat(),
            "seal_key_id": self._seal_key_id,
        }
