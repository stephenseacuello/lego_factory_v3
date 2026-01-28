"""
LEGO Factory v3 - Sensor Data Models
=====================================
Data collection models for MESA-11 Data Collection/Acquisition function.
TimescaleDB-optimized for time-series sensor data.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, Text,
    Index, JSON
)
from sqlalchemy.dialects.postgresql import UUID

from models.base import Base, TimestampMixin


class EventType(str, Enum):
    """Machine event types."""
    STATE_CHANGE = 'state_change'
    ALARM_RAISED = 'alarm_raised'
    ALARM_CLEARED = 'alarm_cleared'
    JOB_STARTED = 'job_started'
    JOB_COMPLETED = 'job_completed'
    JOB_FAILED = 'job_failed'
    MATERIAL_LOADED = 'material_loaded'
    MATERIAL_UNLOADED = 'material_unloaded'
    TOOL_CHANGED = 'tool_changed'
    PARAMETER_CHANGED = 'parameter_changed'
    MAINTENANCE_STARTED = 'maintenance_started'
    MAINTENANCE_COMPLETED = 'maintenance_completed'
    CONNECTION_LOST = 'connection_lost'
    CONNECTION_RESTORED = 'connection_restored'
    OPERATOR_ACTION = 'operator_action'
    SYSTEM_EVENT = 'system_event'


class SensorReading(Base, TimestampMixin):
    """
    Time-series sensor readings.
    Designed for TimescaleDB hypertable partitioning on timestamp.

    Common tags:
    - position_x, position_y, position_z
    - spindle_rpm, spindle_load
    - feed_rate, feed_override
    - extruder_temp, bed_temp
    - vibration_x, vibration_y, vibration_z
    - power_consumption
    - coolant_temp, coolant_flow
    """

    __tablename__ = 'sensor_readings'

    # Use composite primary key for TimescaleDB
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Machine/source identification
    machine_id = Column(String(50), nullable=False, index=True)
    tag_name = Column(String(100), nullable=False, index=True)

    # Values (use appropriate column based on data type)
    value_float = Column(Float)
    value_int = Column(Integer)
    value_str = Column(String(500))
    value_bool = Column(Boolean)

    # Metadata
    unit = Column(String(20))  # e.g., 'mm', 'rpm', 'C', 'W'
    quality = Column(Integer, default=192)  # OPC quality code (192 = good)

    # Source
    source = Column(String(50))  # 'plc', 'sensor', 'calculated', 'manual'

    __table_args__ = (
        Index('ix_sensor_readings_machine_tag_time', 'machine_id', 'tag_name', 'timestamp'),
        Index('ix_sensor_readings_time', 'timestamp'),
        # Note: TimescaleDB will partition by timestamp automatically when converted to hypertable
    )

    def to_dict(self) -> Dict[str, Any]:
        # Determine the value based on which column is populated
        value = self.value_float
        if value is None:
            value = self.value_int
        if value is None:
            value = self.value_str
        if value is None:
            value = self.value_bool

        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'machine_id': self.machine_id,
            'tag_name': self.tag_name,
            'value': value,
            'unit': self.unit,
            'quality': self.quality,
            'source': self.source,
        }


class DataCollectionEvent(Base, TimestampMixin):
    """
    Machine events and state changes.
    Stores discrete events (not continuous sensor data).
    """

    __tablename__ = 'data_collection_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)

    # Machine identification
    machine_id = Column(String(50), nullable=False, index=True)

    # Event details
    event_type = Column(String(50), nullable=False, index=True)
    event_code = Column(String(50))
    description = Column(Text)

    # State transition
    previous_state = Column(String(50))
    new_state = Column(String(50))

    # Related objects
    job_id = Column(String(50), index=True)
    work_order_id = Column(String(50))
    operation_id = Column(String(50))

    # Event data
    data = Column(JSON, default=dict)

    # Severity (for alarms)
    severity = Column(String(20))  # 'info', 'warning', 'error', 'critical'

    # Acknowledgment
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True))
    acknowledged_by = Column(String(100))

    # Source
    source = Column(String(50))  # 'machine', 'operator', 'system', 'scheduler'
    operator_id = Column(String(50))

    __table_args__ = (
        Index('ix_data_collection_events_machine_time', 'machine_id', 'timestamp'),
        Index('ix_data_collection_events_type', 'event_type', 'timestamp'),
        Index('ix_data_collection_events_job', 'job_id'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'machine_id': self.machine_id,
            'event_type': self.event_type,
            'event_code': self.event_code,
            'description': self.description,
            'previous_state': self.previous_state,
            'new_state': self.new_state,
            'job_id': self.job_id,
            'work_order_id': self.work_order_id,
            'data': self.data,
            'severity': self.severity,
            'acknowledged': self.acknowledged,
            'source': self.source,
        }


class MachineHeartbeat(Base):
    """
    Machine heartbeat for connection monitoring.
    Lightweight table updated frequently.
    """

    __tablename__ = 'machine_heartbeats'

    machine_id = Column(String(50), primary_key=True)
    last_heartbeat = Column(DateTime(timezone=True), nullable=False)
    heartbeat_interval_sec = Column(Integer, default=10)
    is_connected = Column(Boolean, default=True)
    connection_type = Column(String(50))  # 'mqtt', 'opcua', 'modbus', 'serial', 'http'
    ip_address = Column(String(50))
    port = Column(Integer)
    last_error = Column(Text)
    consecutive_failures = Column(Integer, default=0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'machine_id': self.machine_id,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'is_connected': self.is_connected,
            'connection_type': self.connection_type,
            'consecutive_failures': self.consecutive_failures,
        }


class TagDefinition(Base, TimestampMixin):
    """
    Tag definitions for sensor data.
    Metadata about each tag that can be collected.
    """

    __tablename__ = 'tag_definitions'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Tag identification
    tag_name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200))
    description = Column(Text)

    # Machine association
    machine_id = Column(String(50), index=True)  # Null for global tags
    machine_type = Column(String(50))  # e.g., 'cnc_mill', 'fdm_printer'

    # Data type
    data_type = Column(String(20), nullable=False)  # 'float', 'int', 'string', 'bool'
    unit = Column(String(20))
    precision = Column(Integer)  # Decimal places for float

    # Value constraints
    min_value = Column(Float)
    max_value = Column(Float)
    default_value = Column(String(100))

    # Alarm thresholds
    alarm_high_high = Column(Float)
    alarm_high = Column(Float)
    alarm_low = Column(Float)
    alarm_low_low = Column(Float)

    # Collection settings
    collection_rate_ms = Column(Integer, default=1000)  # How often to collect
    deadband = Column(Float)  # Change threshold to trigger storage
    is_active = Column(Boolean, default=True)

    # Aggregation
    aggregate_type = Column(String(20))  # 'avg', 'min', 'max', 'sum', 'last'
    retention_days = Column(Integer, default=365)

    # Category
    category = Column(String(50))  # 'position', 'temperature', 'pressure', etc.
    group_name = Column(String(100))

    # Source
    source_address = Column(String(200))  # PLC address, OPC node, etc.
    source_type = Column(String(50))  # 'plc', 'opcua', 'modbus', 'mqtt'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'tag_name': self.tag_name,
            'display_name': self.display_name,
            'description': self.description,
            'machine_id': self.machine_id,
            'data_type': self.data_type,
            'unit': self.unit,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'alarm_high': self.alarm_high,
            'alarm_low': self.alarm_low,
            'collection_rate_ms': self.collection_rate_ms,
            'is_active': self.is_active,
            'category': self.category,
        }
