"""
Audit Trail - Compliance & Traceability

LegoMCP World-Class Manufacturing System v5.0
Phase 24: Compliance & Audit Trail

FDA 21 CFR Part 11 compliance:
- Immutable audit log
- Electronic signatures
- ALCOA+ data integrity
- Change control
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Type of auditable action."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    SIGN = "sign"
    PRINT = "print"
    EXPORT = "export"
    LOGIN = "login"
    LOGOUT = "logout"


@dataclass
class ElectronicSignature:
    """Electronic signature for approvals."""
    signature_id: str
    user_id: str
    user_name: str
    meaning: str  # e.g., "Approved", "Reviewed", "Authored"
    timestamp: datetime
    ip_address: Optional[str] = None

    # Verification
    signature_hash: Optional[str] = None

    def __post_init__(self):
        if not self.signature_id:
            self.signature_id = str(uuid4())
        self._create_hash()

    def _create_hash(self) -> None:
        """Create signature hash for verification."""
        data = f"{self.user_id}:{self.meaning}:{self.timestamp.isoformat()}"
        self.signature_hash = hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'signature_id': self.signature_id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'meaning': self.meaning,
            'timestamp': self.timestamp.isoformat(),
            'signature_hash': self.signature_hash,
        }


@dataclass
class AuditEntry:
    """Single audit trail entry."""
    entry_id: str
    timestamp: datetime
    user_id: str
    user_name: str
    action_type: ActionType

    # What was affected
    entity_type: str  # WorkOrder, Inspection, etc.
    entity_id: str
    entity_description: str = ""

    # Change details
    old_values: Dict[str, Any] = field(default_factory=dict)
    new_values: Dict[str, Any] = field(default_factory=dict)

    # Context
    reason: str = ""
    ip_address: Optional[str] = None
    session_id: Optional[str] = None

    # Signature if applicable
    signature: Optional[ElectronicSignature] = None

    # Integrity
    entry_hash: Optional[str] = None
    previous_hash: Optional[str] = None

    def __post_init__(self):
        if not self.entry_id:
            self.entry_id = str(uuid4())

    def calculate_hash(self, previous_hash: str = "") -> str:
        """Calculate entry hash for chain integrity."""
        data = (
            f"{self.entry_id}:{self.timestamp.isoformat()}:"
            f"{self.user_id}:{self.action_type.value}:"
            f"{self.entity_type}:{self.entity_id}:{previous_hash}"
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'entry_id': self.entry_id,
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'user_name': self.user_name,
            'action_type': self.action_type.value,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'entity_description': self.entity_description,
            'old_values': self.old_values,
            'new_values': self.new_values,
            'reason': self.reason,
            'signature': self.signature.to_dict() if self.signature else None,
            'entry_hash': self.entry_hash,
        }


class AuditTrailService:
    """
    Audit Trail Service.

    Maintains immutable, tamper-evident audit log.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._entries: List[AuditEntry] = []
        self._by_entity: Dict[str, List[str]] = {}  # entity_id -> [entry_ids]

    def log_action(
        self,
        user_id: str,
        user_name: str,
        action_type: ActionType,
        entity_type: str,
        entity_id: str,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        reason: str = "",
        ip_address: Optional[str] = None,
    ) -> AuditEntry:
        """Log an auditable action."""
        # Get previous hash for chain
        previous_hash = self._entries[-1].entry_hash if self._entries else ""

        entry = AuditEntry(
            entry_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_name=user_name,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_values=old_values or {},
            new_values=new_values or {},
            reason=reason,
            ip_address=ip_address,
            previous_hash=previous_hash,
        )

        # Calculate and set hash
        entry.entry_hash = entry.calculate_hash(previous_hash)

        self._entries.append(entry)

        # Index by entity
        if entity_id not in self._by_entity:
            self._by_entity[entity_id] = []
        self._by_entity[entity_id].append(entry.entry_id)

        logger.info(
            f"Audit: {user_name} {action_type.value} {entity_type} {entity_id}"
        )

        return entry

    def log_signature(
        self,
        user_id: str,
        user_name: str,
        entity_type: str,
        entity_id: str,
        meaning: str,
        ip_address: Optional[str] = None,
    ) -> AuditEntry:
        """Log an electronic signature."""
        signature = ElectronicSignature(
            signature_id=str(uuid4()),
            user_id=user_id,
            user_name=user_name,
            meaning=meaning,
            timestamp=datetime.utcnow(),
            ip_address=ip_address,
        )

        entry = self.log_action(
            user_id=user_id,
            user_name=user_name,
            action_type=ActionType.SIGN,
            entity_type=entity_type,
            entity_id=entity_id,
            new_values={'signature_meaning': meaning},
            ip_address=ip_address,
        )
        entry.signature = signature

        return entry

    def get_entity_history(self, entity_id: str) -> List[AuditEntry]:
        """Get audit history for an entity."""
        entry_ids = self._by_entity.get(entity_id, [])
        return [e for e in self._entries if e.entry_id in entry_ids]

    def verify_chain_integrity(self) -> Dict[str, Any]:
        """Verify audit trail chain integrity."""
        if not self._entries:
            return {'valid': True, 'entries_checked': 0}

        valid = True
        broken_at = None

        previous_hash = ""
        for entry in self._entries:
            expected_hash = entry.calculate_hash(previous_hash)
            if entry.entry_hash != expected_hash:
                valid = False
                broken_at = entry.entry_id
                break
            previous_hash = entry.entry_hash

        return {
            'valid': valid,
            'entries_checked': len(self._entries),
            'broken_at': broken_at,
        }

    def search(
        self,
        user_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        action_type: Optional[ActionType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditEntry]:
        """Search audit entries."""
        results = self._entries

        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        if action_type:
            results = [e for e in results if e.action_type == action_type]
        if start_date:
            results = [e for e in results if e.timestamp >= start_date]
        if end_date:
            results = [e for e in results if e.timestamp <= end_date]

        return results

    def generate_report(
        self,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate audit report."""
        entries = self.search(
            entity_type=entity_type,
            start_date=start_date,
            end_date=end_date,
        )

        by_action = {}
        by_user = {}
        by_entity = {}

        for entry in entries:
            # Count by action
            action = entry.action_type.value
            by_action[action] = by_action.get(action, 0) + 1

            # Count by user
            user = entry.user_name
            by_user[user] = by_user.get(user, 0) + 1

            # Count by entity type
            entity = entry.entity_type
            by_entity[entity] = by_entity.get(entity, 0) + 1

        return {
            'report_date': datetime.utcnow().isoformat(),
            'total_entries': len(entries),
            'by_action': by_action,
            'by_user': by_user,
            'by_entity_type': by_entity,
            'chain_integrity': self.verify_chain_integrity(),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get audit trail summary."""
        return {
            'total_entries': len(self._entries),
            'entities_tracked': len(self._by_entity),
            'chain_integrity': self.verify_chain_integrity()['valid'],
        }


# Singleton instance
_audit_trail_service: Optional[AuditTrailService] = None


def get_audit_trail() -> AuditTrailService:
    """Get the singleton audit trail service instance."""
    global _audit_trail_service
    if _audit_trail_service is None:
        _audit_trail_service = AuditTrailService()
    return _audit_trail_service
