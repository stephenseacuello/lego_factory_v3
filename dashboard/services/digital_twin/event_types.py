"""
Event Types - Digital Twin Event Definitions

LegoMCP World-Class Manufacturing System v6.0
Phase 26: Vision AI & ML Training

Defines event types for:
- State changes
- Sensor updates
- Maintenance events
- Quality events
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import uuid


class EventCategory(Enum):
    """Event categories."""
    STATE_CHANGE = "state_change"
    SENSOR_UPDATE = "sensor_update"
    MAINTENANCE = "maintenance"
    QUALITY = "quality"
    COMMAND = "command"
    ALERT = "alert"
    SYSTEM = "system"
    VISION = "vision"


class EventPriority(Enum):
    """Event priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class StateChangeType(Enum):
    """Types of state changes."""
    PROPERTY_UPDATE = "property_update"
    STATUS_CHANGE = "status_change"
    MODE_CHANGE = "mode_change"
    CONFIGURATION_CHANGE = "configuration_change"


class MaintenanceType(Enum):
    """Types of maintenance events."""
    SCHEDULED = "scheduled"
    PREDICTIVE = "predictive"
    CORRECTIVE = "corrective"
    CALIBRATION = "calibration"
    CLEANING = "cleaning"


class QualityEventType(Enum):
    """Types of quality events."""
    INSPECTION = "inspection"
    DEFECT_DETECTED = "defect_detected"
    MEASUREMENT = "measurement"
    SPC_VIOLATION = "spc_violation"
    REWORK = "rework"


class VisionEventType(Enum):
    """Types of vision events."""
    DETECTION = "detection"
    CLASSIFICATION = "classification"
    DEFECT = "defect"
    LAYER_ANALYSIS = "layer_analysis"
    MODEL_INFERENCE = "model_inference"


@dataclass
class EventMetadata:
    """Common event metadata."""
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    source_system: str = "legomcp"
    tags: List[str] = field(default_factory=list)


@dataclass
class TwinEvent:
    """
    Base event for Digital Twin event sourcing.

    All events are immutable and append-only.
    """
    event_id: str
    event_type: str
    category: EventCategory
    twin_id: str
    timestamp: datetime
    sequence_number: int
    priority: EventPriority
    data: Dict[str, Any]
    metadata: EventMetadata = field(default_factory=EventMetadata)
    version: int = 1

    @classmethod
    def create(
        cls,
        event_type: str,
        category: EventCategory,
        twin_id: str,
        data: Dict[str, Any],
        sequence_number: int = 0,
        priority: EventPriority = EventPriority.NORMAL,
        metadata: Optional[EventMetadata] = None
    ) -> 'TwinEvent':
        """Create a new event."""
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            category=category,
            twin_id=twin_id,
            timestamp=datetime.utcnow(),
            sequence_number=sequence_number,
            priority=priority,
            data=data,
            metadata=metadata or EventMetadata(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "category": self.category.value,
            "twin_id": self.twin_id,
            "timestamp": self.timestamp.isoformat(),
            "sequence_number": self.sequence_number,
            "priority": self.priority.value,
            "data": self.data,
            "metadata": {
                "correlation_id": self.metadata.correlation_id,
                "causation_id": self.metadata.causation_id,
                "user_id": self.metadata.user_id,
                "source_system": self.metadata.source_system,
                "tags": self.metadata.tags,
            },
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TwinEvent':
        """Create from dictionary."""
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            category=EventCategory(data["category"]),
            twin_id=data["twin_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sequence_number=data["sequence_number"],
            priority=EventPriority(data["priority"]),
            data=data["data"],
            metadata=EventMetadata(
                correlation_id=data.get("metadata", {}).get("correlation_id"),
                causation_id=data.get("metadata", {}).get("causation_id"),
                user_id=data.get("metadata", {}).get("user_id"),
                source_system=data.get("metadata", {}).get("source_system", "legomcp"),
                tags=data.get("metadata", {}).get("tags", []),
            ),
            version=data.get("version", 1),
        )


# Specific event types

@dataclass
class StateChangeEvent(TwinEvent):
    """State change event."""

    @classmethod
    def create_property_update(
        cls,
        twin_id: str,
        property_name: str,
        old_value: Any,
        new_value: Any,
        sequence_number: int = 0
    ) -> 'StateChangeEvent':
        """Create property update event."""
        return cls.create(
            event_type=StateChangeType.PROPERTY_UPDATE.value,
            category=EventCategory.STATE_CHANGE,
            twin_id=twin_id,
            data={
                "property_name": property_name,
                "old_value": old_value,
                "new_value": new_value,
                "change_type": "update",
            },
            sequence_number=sequence_number,
        )


@dataclass
class SensorUpdateEvent(TwinEvent):
    """Sensor data update event."""

    @classmethod
    def create_reading(
        cls,
        twin_id: str,
        sensor_id: str,
        sensor_type: str,
        value: float,
        unit: str,
        quality: str = "good",
        sequence_number: int = 0
    ) -> 'SensorUpdateEvent':
        """Create sensor reading event."""
        return cls.create(
            event_type="sensor_reading",
            category=EventCategory.SENSOR_UPDATE,
            twin_id=twin_id,
            data={
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "value": value,
                "unit": unit,
                "quality": quality,
            },
            sequence_number=sequence_number,
            priority=EventPriority.LOW,
        )


@dataclass
class MaintenanceEvent(TwinEvent):
    """Maintenance event."""

    @classmethod
    def create_maintenance(
        cls,
        twin_id: str,
        maintenance_type: MaintenanceType,
        component: str,
        description: str,
        technician: Optional[str] = None,
        sequence_number: int = 0
    ) -> 'MaintenanceEvent':
        """Create maintenance event."""
        return cls.create(
            event_type=maintenance_type.value,
            category=EventCategory.MAINTENANCE,
            twin_id=twin_id,
            data={
                "maintenance_type": maintenance_type.value,
                "component": component,
                "description": description,
                "technician": technician,
            },
            sequence_number=sequence_number,
            priority=EventPriority.HIGH,
        )


@dataclass
class QualityEvent(TwinEvent):
    """Quality-related event."""

    @classmethod
    def create_defect(
        cls,
        twin_id: str,
        defect_type: str,
        severity: str,
        location: Optional[Dict[str, Any]] = None,
        sequence_number: int = 0
    ) -> 'QualityEvent':
        """Create defect detection event."""
        return cls.create(
            event_type=QualityEventType.DEFECT_DETECTED.value,
            category=EventCategory.QUALITY,
            twin_id=twin_id,
            data={
                "defect_type": defect_type,
                "severity": severity,
                "location": location or {},
            },
            sequence_number=sequence_number,
            priority=EventPriority.HIGH if severity == "critical" else EventPriority.NORMAL,
        )


@dataclass
class VisionEvent(TwinEvent):
    """Vision/CV-related event."""

    @classmethod
    def create_detection(
        cls,
        twin_id: str,
        model_id: str,
        detections: List[Dict[str, Any]],
        image_id: str,
        inference_time_ms: float,
        sequence_number: int = 0
    ) -> 'VisionEvent':
        """Create vision detection event."""
        return cls.create(
            event_type=VisionEventType.DETECTION.value,
            category=EventCategory.VISION,
            twin_id=twin_id,
            data={
                "model_id": model_id,
                "detections": detections,
                "image_id": image_id,
                "inference_time_ms": inference_time_ms,
                "num_detections": len(detections),
            },
            sequence_number=sequence_number,
        )


@dataclass
class AlertEvent(TwinEvent):
    """Alert event."""

    @classmethod
    def create_alert(
        cls,
        twin_id: str,
        alert_type: str,
        message: str,
        severity: str,
        source: str,
        sequence_number: int = 0
    ) -> 'AlertEvent':
        """Create alert event."""
        priority = {
            "critical": EventPriority.CRITICAL,
            "high": EventPriority.HIGH,
            "medium": EventPriority.NORMAL,
            "low": EventPriority.LOW,
        }.get(severity, EventPriority.NORMAL)

        return cls.create(
            event_type=alert_type,
            category=EventCategory.ALERT,
            twin_id=twin_id,
            data={
                "message": message,
                "severity": severity,
                "source": source,
                "acknowledged": False,
            },
            sequence_number=sequence_number,
            priority=priority,
        )


# Event type registry
EVENT_TYPES: Dict[str, type] = {
    "state_change": StateChangeEvent,
    "sensor_update": SensorUpdateEvent,
    "maintenance": MaintenanceEvent,
    "quality": QualityEvent,
    "vision": VisionEvent,
    "alert": AlertEvent,
}


def create_event(
    category: EventCategory,
    event_type: str,
    twin_id: str,
    data: Dict[str, Any],
    **kwargs
) -> TwinEvent:
    """
    Factory function to create events.

    Args:
        category: Event category
        event_type: Specific event type
        twin_id: Digital twin ID
        data: Event data
        **kwargs: Additional event parameters

    Returns:
        Created event
    """
    return TwinEvent.create(
        event_type=event_type,
        category=category,
        twin_id=twin_id,
        data=data,
        **kwargs
    )
