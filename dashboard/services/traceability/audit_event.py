"""
Audit Event - Tamper-Evident Audit Trail Events

LegoMCP World-Class Manufacturing System v5.0
Digital Thread Audit Trail with Cryptographic Hash Chains

This module defines the AuditEvent dataclass for tracking manufacturing events
with tamper-evident properties through cryptographic hash chaining.

Author: LegoMCP Team
Version: 2.0.0
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class AuditEventType(Enum):
    """Types of auditable events in the digital thread."""

    # Work Order Events
    WORK_ORDER_CREATED = "work_order.created"
    WORK_ORDER_STARTED = "work_order.started"
    WORK_ORDER_COMPLETED = "work_order.completed"
    WORK_ORDER_CANCELLED = "work_order.cancelled"
    WORK_ORDER_MODIFIED = "work_order.modified"

    # Part Events
    PART_CREATED = "part.created"
    PART_MODIFIED = "part.modified"
    PART_INSPECTED = "part.inspected"
    PART_SHIPPED = "part.shipped"
    PART_RECEIVED = "part.received"
    PART_SCRAPPED = "part.scrapped"
    PART_REWORKED = "part.reworked"

    # Equipment Events
    EQUIPMENT_STARTED = "equipment.started"
    EQUIPMENT_STOPPED = "equipment.stopped"
    EQUIPMENT_MAINTENANCE = "equipment.maintenance"
    EQUIPMENT_CALIBRATED = "equipment.calibrated"
    EQUIPMENT_FAULT = "equipment.fault"
    EQUIPMENT_PARAMETER_CHANGE = "equipment.parameter_change"

    # Quality Events
    QUALITY_INSPECTION = "quality.inspection"
    QUALITY_DEFECT_DETECTED = "quality.defect_detected"
    QUALITY_HOLD_PLACED = "quality.hold_placed"
    QUALITY_HOLD_RELEASED = "quality.hold_released"
    QUALITY_NCR_CREATED = "quality.ncr_created"
    QUALITY_CAPA_INITIATED = "quality.capa_initiated"

    # Material Events
    MATERIAL_RECEIVED = "material.received"
    MATERIAL_CONSUMED = "material.consumed"
    MATERIAL_LOT_CREATED = "material.lot_created"
    MATERIAL_QUARANTINED = "material.quarantined"

    # System Events
    SYSTEM_CONFIG_CHANGE = "system.config_change"
    SYSTEM_USER_LOGIN = "system.user_login"
    SYSTEM_USER_LOGOUT = "system.user_logout"
    SYSTEM_ACCESS_DENIED = "system.access_denied"

    # Custom Events
    CUSTOM = "custom"


class EntityType(Enum):
    """Types of entities that can be tracked in the audit trail."""

    WORK_ORDER = "work_order"
    PART = "part"
    EQUIPMENT = "equipment"
    MATERIAL = "material"
    QUALITY_RECORD = "quality_record"
    USER = "user"
    SYSTEM = "system"
    CUSTOM = "custom"


@dataclass
class AuditEvent:
    """
    Immutable audit event with cryptographic hash chain properties.

    Each event contains:
    - Unique identifier
    - Event type and metadata
    - Entity reference (what was affected)
    - Previous event hash (for chain integrity)
    - Computed hash (tamper detection)
    - Timestamp and user info

    The hash chain ensures that any modification to historical events
    can be detected during chain verification.
    """

    # Core identifiers
    event_id: str = field(default_factory=lambda: str(uuid4()))
    sequence_number: int = 0

    # Event classification
    event_type: AuditEventType = AuditEventType.CUSTOM
    event_subtype: str = ""

    # Entity reference
    entity_type: EntityType = EntityType.CUSTOM
    entity_id: str = ""
    entity_name: str = ""

    # Event data
    action: str = ""
    description: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Change tracking (for modifications)
    previous_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None

    # User and context
    user_id: str = ""
    user_name: str = ""
    session_id: str = ""
    source_system: str = "lego_mcp"
    source_ip: str = ""

    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Hash chain properties
    previous_hash: str = ""
    event_hash: str = ""

    # Signature (for additional verification)
    signature: str = ""
    signature_algorithm: str = "sha256"

    def __post_init__(self):
        """Compute hash after initialization if not already set."""
        if not self.event_hash:
            self.event_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of the event data.

        The hash includes all critical fields to ensure
        any tampering can be detected.
        """
        hash_input = {
            'event_id': self.event_id,
            'sequence_number': self.sequence_number,
            'event_type': self.event_type.value,
            'event_subtype': self.event_subtype,
            'entity_type': self.entity_type.value,
            'entity_id': self.entity_id,
            'entity_name': self.entity_name,
            'action': self.action,
            'description': self.description,
            'data': self.data,
            'previous_value': self.previous_value,
            'new_value': self.new_value,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat(),
            'previous_hash': self.previous_hash,
        }

        # Create deterministic JSON string
        json_str = json.dumps(hash_input, sort_keys=True, default=str)

        # Compute SHA-256 hash
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

    def verify_hash(self) -> bool:
        """
        Verify that the stored hash matches the computed hash.

        Returns True if the event has not been tampered with.
        """
        return self.event_hash == self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            'event_id': self.event_id,
            'sequence_number': self.sequence_number,
            'event_type': self.event_type.value,
            'event_subtype': self.event_subtype,
            'entity_type': self.entity_type.value,
            'entity_id': self.entity_id,
            'entity_name': self.entity_name,
            'action': self.action,
            'description': self.description,
            'data': self.data,
            'metadata': self.metadata,
            'previous_value': self.previous_value,
            'new_value': self.new_value,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'session_id': self.session_id,
            'source_system': self.source_system,
            'source_ip': self.source_ip,
            'timestamp': self.timestamp.isoformat(),
            'previous_hash': self.previous_hash,
            'event_hash': self.event_hash,
            'signature': self.signature,
            'signature_algorithm': self.signature_algorithm,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """Create an AuditEvent from a dictionary."""
        # Parse enums
        event_type = AuditEventType(data.get('event_type', 'custom'))
        entity_type = EntityType(data.get('entity_type', 'custom'))

        # Parse timestamp
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.utcnow()

        event = cls(
            event_id=data.get('event_id', str(uuid4())),
            sequence_number=data.get('sequence_number', 0),
            event_type=event_type,
            event_subtype=data.get('event_subtype', ''),
            entity_type=entity_type,
            entity_id=data.get('entity_id', ''),
            entity_name=data.get('entity_name', ''),
            action=data.get('action', ''),
            description=data.get('description', ''),
            data=data.get('data', {}),
            metadata=data.get('metadata', {}),
            previous_value=data.get('previous_value'),
            new_value=data.get('new_value'),
            user_id=data.get('user_id', ''),
            user_name=data.get('user_name', ''),
            session_id=data.get('session_id', ''),
            source_system=data.get('source_system', 'lego_mcp'),
            source_ip=data.get('source_ip', ''),
            timestamp=timestamp,
            previous_hash=data.get('previous_hash', ''),
            event_hash=data.get('event_hash', ''),
            signature=data.get('signature', ''),
            signature_algorithm=data.get('signature_algorithm', 'sha256'),
        )

        # Don't recompute hash if it was provided
        if not data.get('event_hash'):
            event.event_hash = event.compute_hash()

        return event

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, json_str: str) -> 'AuditEvent':
        """Deserialize event from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"AuditEvent[{self.sequence_number}] "
            f"{self.event_type.value} on {self.entity_type.value}:{self.entity_id} "
            f"at {self.timestamp.isoformat()}"
        )

    def __repr__(self) -> str:
        """Detailed string representation."""
        return (
            f"AuditEvent("
            f"event_id='{self.event_id}', "
            f"sequence={self.sequence_number}, "
            f"type={self.event_type.value}, "
            f"entity={self.entity_type.value}:{self.entity_id}, "
            f"hash={self.event_hash[:16]}...)"
        )


@dataclass
class AuditChainStatus:
    """Status of audit chain verification."""

    is_valid: bool = True
    total_events: int = 0
    verified_events: int = 0
    first_invalid_sequence: Optional[int] = None
    first_invalid_event_id: Optional[str] = None
    error_message: str = ""
    verification_timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'is_valid': self.is_valid,
            'total_events': self.total_events,
            'verified_events': self.verified_events,
            'first_invalid_sequence': self.first_invalid_sequence,
            'first_invalid_event_id': self.first_invalid_event_id,
            'error_message': self.error_message,
            'verification_timestamp': self.verification_timestamp.isoformat(),
        }


@dataclass
class EntityHistory:
    """Complete history of an entity from the audit trail."""

    entity_type: EntityType
    entity_id: str
    entity_name: str
    events: List[AuditEvent] = field(default_factory=list)
    first_event_timestamp: Optional[datetime] = None
    last_event_timestamp: Optional[datetime] = None
    total_events: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'entity_type': self.entity_type.value,
            'entity_id': self.entity_id,
            'entity_name': self.entity_name,
            'events': [e.to_dict() for e in self.events],
            'first_event_timestamp': self.first_event_timestamp.isoformat() if self.first_event_timestamp else None,
            'last_event_timestamp': self.last_event_timestamp.isoformat() if self.last_event_timestamp else None,
            'total_events': self.total_events,
        }
