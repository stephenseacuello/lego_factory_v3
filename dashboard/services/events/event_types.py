"""
Event Types - Typed Event Definitions

LegoMCP World-Class Manufacturing System v5.0
Phase 7: Event-Driven Architecture

Defines all event types used in the manufacturing platform with
full type hints, validation, and serialization support.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
import json


class EventCategory(str, Enum):
    """Event categories aligned with ISA-95 operations."""
    MACHINE = "machine"           # L0-L1: Equipment state, alarms
    QUALITY = "quality"           # L3: SPC, inspections, defects
    SCHEDULING = "scheduling"     # L3: Schedule changes, deviations
    INVENTORY = "inventory"       # L3: Stock movements
    MAINTENANCE = "maintenance"   # L3: Predictive alerts, work orders
    PRODUCTION = "production"     # L3: Work order events
    ERP = "erp"                   # L4: Business events
    SYSTEM = "system"             # Cross-cutting system events


class EventPriority(str, Enum):
    """Event priority levels for processing order."""
    CRITICAL = "critical"   # Immediate processing, may halt production
    HIGH = "high"           # Process within 1 second
    NORMAL = "normal"       # Standard processing
    LOW = "low"             # Batch processing acceptable


class SourceLayer(str, Enum):
    """ISA-95 layer source of the event."""
    L0 = "L0"   # Sensors/Actuators
    L1 = "L1"   # Cell/PLC Control
    L2 = "L2"   # Supervisory/MCP
    L3 = "L3"   # MES/MOM
    L4 = "L4"   # ERP/Business


@dataclass
class EventMetadata:
    """Metadata for event tracing and correlation."""
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ManufacturingEvent:
    """
    Base event class for all manufacturing events.

    All events in the system inherit from this class and provide
    consistent structure for serialization, tracing, and processing.
    """
    event_type: str
    category: EventCategory
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    source_layer: SourceLayer = SourceLayer.L3
    priority: EventPriority = EventPriority.NORMAL
    work_center_id: Optional[str] = None
    work_order_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: EventMetadata = field(default_factory=EventMetadata)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'category': self.category.value,
            'timestamp': self.timestamp.isoformat(),
            'source_layer': self.source_layer.value,
            'priority': self.priority.value,
            'work_center_id': self.work_center_id,
            'work_order_id': self.work_order_id,
            'payload': self.payload,
            'metadata': self.metadata.to_dict(),
        }

    def to_json(self) -> str:
        """Serialize event to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ManufacturingEvent':
        """Deserialize event from dictionary."""
        metadata = EventMetadata(**data.get('metadata', {}))
        return cls(
            event_id=data.get('event_id', str(uuid4())),
            event_type=data['event_type'],
            category=EventCategory(data['category']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            source_layer=SourceLayer(data.get('source_layer', 'L3')),
            priority=EventPriority(data.get('priority', 'normal')),
            work_center_id=data.get('work_center_id'),
            work_order_id=data.get('work_order_id'),
            payload=data.get('payload', {}),
            metadata=metadata,
        )

    @classmethod
    def from_json(cls, json_str: str) -> 'ManufacturingEvent':
        """Deserialize event from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @property
    def stream_key(self) -> str:
        """Redis Stream key for this event category."""
        return f"lego:events:{self.category.value}"


# ============================================================================
# Machine Events (L0-L1)
# ============================================================================

class MachineEventType(str, Enum):
    """Types of machine events."""
    STATE_CHANGE = "machine.state_change"
    ALARM = "machine.alarm"
    ALARM_CLEARED = "machine.alarm_cleared"
    TEMPERATURE = "machine.temperature"
    POSITION = "machine.position"
    SENSOR_DATA = "machine.sensor_data"
    JOB_STARTED = "machine.job_started"
    JOB_COMPLETED = "machine.job_completed"
    JOB_FAILED = "machine.job_failed"
    LAYER_COMPLETED = "machine.layer_completed"  # 3D printing
    TOOL_CHANGE = "machine.tool_change"          # CNC
    POWER_ON = "machine.power_on"
    POWER_OFF = "machine.power_off"


class MachineState(str, Enum):
    """Machine operational states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"
    SETUP = "setup"


@dataclass
class MachineEvent(ManufacturingEvent):
    """Event from physical equipment (L0-L1)."""

    def __init__(
        self,
        event_type: MachineEventType,
        work_center_id: str,
        machine_state: Optional[MachineState] = None,
        alarm_code: Optional[str] = None,
        alarm_message: Optional[str] = None,
        temperature: Optional[Dict[str, float]] = None,
        position: Optional[Dict[str, float]] = None,
        sensor_values: Optional[Dict[str, float]] = None,
        job_id: Optional[str] = None,
        layer_number: Optional[int] = None,
        **kwargs
    ):
        payload = {
            'machine_state': machine_state.value if machine_state else None,
            'alarm_code': alarm_code,
            'alarm_message': alarm_message,
            'temperature': temperature,
            'position': position,
            'sensor_values': sensor_values,
            'job_id': job_id,
            'layer_number': layer_number,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        super().__init__(
            event_type=event_type.value if isinstance(event_type, MachineEventType) else event_type,
            category=EventCategory.MACHINE,
            source_layer=SourceLayer.L1,
            work_center_id=work_center_id,
            payload=payload,
            **kwargs
        )


# ============================================================================
# Quality Events (L3)
# ============================================================================

class QualityEventType(str, Enum):
    """Types of quality events."""
    SPC_SIGNAL = "quality.spc_signal"
    SPC_OUT_OF_CONTROL = "quality.spc_out_of_control"
    INSPECTION_CREATED = "quality.inspection_created"
    INSPECTION_COMPLETED = "quality.inspection_completed"
    MEASUREMENT_RECORDED = "quality.measurement_recorded"
    DEFECT_DETECTED = "quality.defect_detected"
    NCR_CREATED = "quality.ncr_created"
    CLUTCH_POWER_TEST = "quality.clutch_power_test"
    DIMENSIONAL_CHECK = "quality.dimensional_check"
    CV_ANALYSIS = "quality.cv_analysis"


class SPCSignalType(str, Enum):
    """Types of SPC signals (Western Electric rules, etc.)."""
    RULE_1 = "rule_1"   # One point beyond 3σ
    RULE_2 = "rule_2"   # 2 of 3 points beyond 2σ
    RULE_3 = "rule_3"   # 4 of 5 points beyond 1σ
    RULE_4 = "rule_4"   # 8 consecutive points on one side
    TREND = "trend"     # 6 points trending up or down
    SHIFT = "shift"     # 9 points on one side of center
    EWMA = "ewma"       # EWMA signal
    CUSUM = "cusum"     # CUSUM signal


@dataclass
class QualityEvent(ManufacturingEvent):
    """Quality-related events (L3)."""

    def __init__(
        self,
        event_type: QualityEventType,
        inspection_id: Optional[str] = None,
        metric_name: Optional[str] = None,
        target_value: Optional[float] = None,
        actual_value: Optional[float] = None,
        tolerance: Optional[float] = None,
        spc_signal: Optional[SPCSignalType] = None,
        defect_type: Optional[str] = None,
        severity: Optional[str] = None,
        cv_confidence: Optional[float] = None,
        **kwargs
    ):
        payload = {
            'inspection_id': inspection_id,
            'metric_name': metric_name,
            'target_value': target_value,
            'actual_value': actual_value,
            'tolerance': tolerance,
            'spc_signal': spc_signal.value if spc_signal else None,
            'defect_type': defect_type,
            'severity': severity,
            'cv_confidence': cv_confidence,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        priority = EventPriority.CRITICAL if spc_signal or defect_type else EventPriority.NORMAL

        super().__init__(
            event_type=event_type.value if isinstance(event_type, QualityEventType) else event_type,
            category=EventCategory.QUALITY,
            priority=priority,
            payload=payload,
            **kwargs
        )


# ============================================================================
# Scheduling Events (L3)
# ============================================================================

class SchedulingEventType(str, Enum):
    """Types of scheduling events."""
    SCHEDULE_CREATED = "scheduling.schedule_created"
    SCHEDULE_UPDATED = "scheduling.schedule_updated"
    OPERATION_STARTED = "scheduling.operation_started"
    OPERATION_COMPLETED = "scheduling.operation_completed"
    OPERATION_DELAYED = "scheduling.operation_delayed"
    DEVIATION_DETECTED = "scheduling.deviation_detected"
    RESCHEDULE_TRIGGERED = "scheduling.reschedule_triggered"
    BOTTLENECK_DETECTED = "scheduling.bottleneck_detected"
    DUE_DATE_AT_RISK = "scheduling.due_date_at_risk"


@dataclass
class SchedulingEvent(ManufacturingEvent):
    """Scheduling-related events (L3)."""

    def __init__(
        self,
        event_type: SchedulingEventType,
        schedule_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        planned_start: Optional[datetime] = None,
        planned_end: Optional[datetime] = None,
        actual_start: Optional[datetime] = None,
        actual_end: Optional[datetime] = None,
        deviation_minutes: Optional[float] = None,
        reason: Optional[str] = None,
        **kwargs
    ):
        payload = {
            'schedule_id': schedule_id,
            'operation_id': operation_id,
            'planned_start': planned_start.isoformat() if planned_start else None,
            'planned_end': planned_end.isoformat() if planned_end else None,
            'actual_start': actual_start.isoformat() if actual_start else None,
            'actual_end': actual_end.isoformat() if actual_end else None,
            'deviation_minutes': deviation_minutes,
            'reason': reason,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        # Critical if due date at risk or major deviation
        priority = EventPriority.HIGH
        if event_type in [SchedulingEventType.DUE_DATE_AT_RISK, SchedulingEventType.RESCHEDULE_TRIGGERED]:
            priority = EventPriority.CRITICAL

        super().__init__(
            event_type=event_type.value if isinstance(event_type, SchedulingEventType) else event_type,
            category=EventCategory.SCHEDULING,
            priority=priority,
            payload=payload,
            **kwargs
        )


# ============================================================================
# Inventory Events (L3)
# ============================================================================

class InventoryEventType(str, Enum):
    """Types of inventory events."""
    STOCK_RECEIVED = "inventory.stock_received"
    STOCK_ISSUED = "inventory.stock_issued"
    STOCK_ADJUSTED = "inventory.stock_adjusted"
    STOCK_TRANSFERRED = "inventory.stock_transferred"
    LOW_STOCK_ALERT = "inventory.low_stock_alert"
    STOCKOUT = "inventory.stockout"
    CYCLE_COUNT = "inventory.cycle_count"


@dataclass
class InventoryEvent(ManufacturingEvent):
    """Inventory-related events (L3)."""

    def __init__(
        self,
        event_type: InventoryEventType,
        part_id: str,
        location_id: Optional[str] = None,
        quantity: Optional[float] = None,
        from_location_id: Optional[str] = None,
        to_location_id: Optional[str] = None,
        lot_number: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs
    ):
        payload = {
            'part_id': part_id,
            'location_id': location_id,
            'quantity': quantity,
            'from_location_id': from_location_id,
            'to_location_id': to_location_id,
            'lot_number': lot_number,
            'reason': reason,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        priority = EventPriority.CRITICAL if event_type == InventoryEventType.STOCKOUT else EventPriority.NORMAL

        super().__init__(
            event_type=event_type.value if isinstance(event_type, InventoryEventType) else event_type,
            category=EventCategory.INVENTORY,
            priority=priority,
            payload=payload,
            **kwargs
        )


# ============================================================================
# Maintenance Events (L3)
# ============================================================================

class MaintenanceEventType(str, Enum):
    """Types of maintenance events."""
    MAINTENANCE_SCHEDULED = "maintenance.scheduled"
    MAINTENANCE_STARTED = "maintenance.started"
    MAINTENANCE_COMPLETED = "maintenance.completed"
    PREDICTIVE_ALERT = "maintenance.predictive_alert"
    HEALTH_DEGRADED = "maintenance.health_degraded"
    FAILURE_PREDICTED = "maintenance.failure_predicted"
    CALIBRATION_DUE = "maintenance.calibration_due"


class HealthStatus(str, Enum):
    """Equipment health status levels."""
    EXCELLENT = "excellent"   # >90% health
    GOOD = "good"             # 70-90%
    FAIR = "fair"             # 50-70%
    POOR = "poor"             # 30-50%
    CRITICAL = "critical"     # <30%


@dataclass
class MaintenanceEvent(ManufacturingEvent):
    """Maintenance-related events (L3)."""

    def __init__(
        self,
        event_type: MaintenanceEventType,
        work_center_id: str,
        maintenance_id: Optional[str] = None,
        health_score: Optional[float] = None,
        health_status: Optional[HealthStatus] = None,
        predicted_failure_date: Optional[datetime] = None,
        maintenance_type: Optional[str] = None,
        estimated_downtime_hours: Optional[float] = None,
        **kwargs
    ):
        payload = {
            'maintenance_id': maintenance_id,
            'health_score': health_score,
            'health_status': health_status.value if health_status else None,
            'predicted_failure_date': predicted_failure_date.isoformat() if predicted_failure_date else None,
            'maintenance_type': maintenance_type,
            'estimated_downtime_hours': estimated_downtime_hours,
        }
        payload = {k: v for k, v in payload.items() if v is not None}

        priority = EventPriority.NORMAL
        if health_status in [HealthStatus.POOR, HealthStatus.CRITICAL]:
            priority = EventPriority.HIGH
        if event_type == MaintenanceEventType.FAILURE_PREDICTED:
            priority = EventPriority.CRITICAL

        super().__init__(
            event_type=event_type.value if isinstance(event_type, MaintenanceEventType) else event_type,
            category=EventCategory.MAINTENANCE,
            work_center_id=work_center_id,
            priority=priority,
            payload=payload,
            **kwargs
        )
