"""
SCADA Database Models
- Tag Management
- Alarm Management (ISA-18.2)
- Historian (TimescaleDB)
- Recipe Management (ISA-88)
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, 
    ForeignKey, UniqueConstraint, Index, Numeric, ARRAY, JSON,
    CheckConstraint, Computed, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, backref
from config.database import Base


# =============================================================================
# TAG MANAGEMENT
# =============================================================================

class TagGroup(Base):
    """Hierarchical grouping of tags"""
    __tablename__ = 'tag_groups'
    
    group_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_group_id = Column(UUID(as_uuid=True), ForeignKey('tag_groups.group_id'), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    path = Column(String(500))  # Materialized path for hierarchy queries
    
    # Relationships
    children = relationship('TagGroup', backref=backref('parent', remote_side=[group_id]))
    tags = relationship('Tag', back_populates='group')


class Tag(Base):
    """Tag definitions - all I/O points in the system"""
    __tablename__ = 'tags'
    
    tag_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tag_name = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text)
    group_id = Column(UUID(as_uuid=True), ForeignKey('tag_groups.group_id'))
    
    # Data type
    data_type = Column(String(20), nullable=False)  # FLOAT, INT, BOOL, STRING
    
    # Engineering units and scaling
    eng_units = Column(String(50))
    eng_low = Column(Numeric(15, 6))
    eng_high = Column(Numeric(15, 6))
    raw_low = Column(Numeric(15, 6))
    raw_high = Column(Numeric(15, 6))
    
    # Alarm limits (default - can override per state)
    alarm_hh = Column(Numeric(15, 6))
    alarm_hi = Column(Numeric(15, 6))
    alarm_lo = Column(Numeric(15, 6))
    alarm_ll = Column(Numeric(15, 6))
    alarm_deadband = Column(Numeric(15, 6))
    
    # Collection settings
    scan_rate_ms = Column(Integer, default=1000)
    historian_enabled = Column(Boolean, default=True)
    compression_enabled = Column(Boolean, default=True)
    compression_deviation = Column(Numeric(15, 6))
    
    # Source configuration
    source_type = Column(String(50))  # MCC_DAQ, ARDUINO, MACHINE, CALCULATED, ROS2
    source_address = Column(String(200))  # Channel, register, topic, etc.
    source_config = Column(JSONB)  # Additional source-specific config
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    group = relationship('TagGroup', back_populates='tags')
    alarms = relationship('AlarmDefinition', back_populates='tag')
    
    __table_args__ = (
        Index('idx_tags_source', 'source_type', 'source_address'),
        Index('idx_tags_active', 'is_active'),
    )


class TagTemplate(Base):
    """Templates for quick tag creation"""
    __tablename__ = 'tag_templates'
    
    template_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_name = Column(String(100), nullable=False)
    description = Column(Text)
    data_type = Column(String(20), nullable=False)
    eng_units = Column(String(50))
    alarm_hh_offset = Column(Numeric(15, 6))
    alarm_hi_offset = Column(Numeric(15, 6))
    alarm_lo_offset = Column(Numeric(15, 6))
    alarm_ll_offset = Column(Numeric(15, 6))
    scan_rate_ms = Column(Integer)
    compression_deviation = Column(Numeric(15, 6))
    source_type = Column(String(50))


# =============================================================================
# ALARM MANAGEMENT (ISA-18.2)
# =============================================================================

class OperatingState(Base):
    """Operating states for state-based alarming"""
    __tablename__ = 'operating_states'
    
    state_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    is_default = Column(Boolean, default=False)


class AlarmDefinition(Base):
    """Alarm configuration"""
    __tablename__ = 'alarm_definitions'
    
    alarm_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tag_id = Column(UUID(as_uuid=True), ForeignKey('tags.tag_id'), nullable=False)
    
    # Alarm type and priority
    alarm_type = Column(String(20), nullable=False)  # HI_HI, HI, LO, LO_LO, RATE, DEV, DISCRETE, ML
    priority = Column(Integer, nullable=False)  # 1=Critical, 2=High, 3=Medium, 4=Low, 5=Diagnostic
    
    # Setpoint and deadband
    setpoint = Column(Numeric(15, 6))
    deadband = Column(Numeric(15, 6), default=0)
    
    # Delays (milliseconds)
    on_delay_ms = Column(Integer, default=0)
    off_delay_ms = Column(Integer, default=0)
    
    # Messages
    message_template = Column(Text, nullable=False)
    consequence = Column(Text)  # What happens if ignored
    response_instruction = Column(Text)  # What operator should do
    
    # Status
    is_enabled = Column(Boolean, default=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True))
    
    # Relationships
    tag = relationship('Tag', back_populates='alarms')
    state_limits = relationship('AlarmStateLimit', back_populates='alarm')
    
    __table_args__ = (
        CheckConstraint('priority BETWEEN 1 AND 5', name='check_alarm_priority'),
        Index('idx_alarm_tag', 'tag_id'),
        Index('idx_alarm_enabled', 'is_enabled'),
    )


class AlarmStateLimit(Base):
    """State-specific alarm limits"""
    __tablename__ = 'alarm_state_limits'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alarm_id = Column(UUID(as_uuid=True), ForeignKey('alarm_definitions.alarm_id'), nullable=False)
    state_id = Column(UUID(as_uuid=True), ForeignKey('operating_states.state_id'), nullable=False)
    setpoint = Column(Numeric(15, 6))
    is_suppressed = Column(Boolean, default=False)
    
    alarm = relationship('AlarmDefinition', back_populates='state_limits')
    
    __table_args__ = (
        UniqueConstraint('alarm_id', 'state_id', name='uq_alarm_state'),
    )


class ActiveAlarm(Base):
    """Currently active alarms"""
    __tablename__ = 'active_alarms'
    
    instance_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alarm_id = Column(UUID(as_uuid=True), ForeignKey('alarm_definitions.alarm_id'), nullable=False)
    tag_id = Column(UUID(as_uuid=True), ForeignKey('tags.tag_id'), nullable=False)
    
    # Current state
    status = Column(String(20), nullable=False)  # ACTIVE_UNACKED, ACKED_ACTIVE, CLEARED_UNACKED
    priority = Column(Integer, nullable=False)
    alarm_value = Column(Numeric(15, 6))
    
    # Timestamps
    alarm_time = Column(DateTime, nullable=False)
    ack_time = Column(DateTime)
    clear_time = Column(DateTime)
    
    # Acknowledgment
    ack_by = Column(UUID(as_uuid=True))
    ack_notes = Column(Text)
    
    # Shelving
    shelved_until = Column(DateTime)
    shelved_by = Column(UUID(as_uuid=True))
    shelve_reason = Column(Text)
    
    __table_args__ = (
        Index('idx_active_alarm_status', 'status'),
        Index('idx_active_alarm_priority', 'priority'),
        Index('idx_active_alarm_time', 'alarm_time'),
    )


class AlarmHistory(Base):
    """Immutable alarm event log (partitioned by time)"""
    __tablename__ = 'alarm_history'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    instance_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    alarm_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    tag_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Event details
    event_type = Column(String(20), nullable=False)  # ACTIVATED, ACKNOWLEDGED, CLEARED, SHELVED, UNSHELVED
    event_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    priority = Column(Integer, nullable=False)
    alarm_value = Column(Numeric(15, 6))
    
    # User action
    user_id = Column(UUID(as_uuid=True))
    notes = Column(Text)
    
    __table_args__ = (
        Index('idx_alarm_history_time', 'event_time'),
        Index('idx_alarm_history_alarm', 'alarm_id'),
    )


class AlarmStatistics(Base):
    """Aggregated alarm statistics for rationalization"""
    __tablename__ = 'alarm_statistics'
    
    stat_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alarm_id = Column(UUID(as_uuid=True), ForeignKey('alarm_definitions.alarm_id'), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Counts
    activation_count = Column(Integer, default=0)
    chattering_count = Column(Integer, default=0)  # Activations within 1 min
    
    # Durations
    avg_duration_seconds = Column(Numeric(10, 2))
    max_duration_seconds = Column(Numeric(10, 2))
    standing_time_seconds = Column(Integer, default=0)
    
    # Response times
    ack_response_avg_seconds = Column(Numeric(10, 2))
    ack_response_max_seconds = Column(Numeric(10, 2))
    
    __table_args__ = (
        UniqueConstraint('alarm_id', 'period_start', name='uq_alarm_stat_period'),
    )


# =============================================================================
# HISTORIAN (TimescaleDB)
# =============================================================================

class TagValue(Base):
    """High-speed time-series data (converted to hypertable)"""
    __tablename__ = 'tag_values'
    
    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    tag_id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    
    # Values (only one populated based on tag data type)
    value_numeric = Column(Float)
    value_text = Column(Text)
    value_bool = Column(Boolean)
    
    # Quality code (OPC-style: 192 = good, 0 = bad)
    quality = Column(Integer, default=192)
    
    # Source that wrote this value
    source = Column(String(50))
    
    __table_args__ = (
        Index('idx_tag_values_tag_time', 'tag_id', 'time'),
    )


class TagValueArchive(Base):
    """Aggregated historical data (1-minute buckets, auto-populated by continuous aggregate)"""
    __tablename__ = 'tag_values_archive'
    
    bucket = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    tag_id = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    
    avg_value = Column(Float)
    min_value = Column(Float)
    max_value = Column(Float)
    sample_count = Column(Integer)
    last_value = Column(Float)


# =============================================================================
# RECIPE MANAGEMENT (ISA-88)
# =============================================================================

class MasterRecipe(Base):
    """Master recipe definitions"""
    __tablename__ = 'master_recipes'
    
    recipe_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_name = Column(String(200), nullable=False)
    recipe_type = Column(String(50), nullable=False)  # GCODE, PRINT_PROFILE, ROBOT_PROGRAM
    product_id = Column(UUID(as_uuid=True))  # Link to items table
    
    # Version control
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), default='draft')  # draft, pending_approval, approved, obsolete
    
    # Content
    content_type = Column(String(50))  # text/gcode, application/json, etc.
    content = Column(Text)  # G-code, JSON parameters, etc.
    content_hash = Column(String(64))  # SHA-256 for integrity
    
    # Parameters
    parameters = Column(JSONB, default={})
    
    # Approval workflow
    created_by = Column(UUID(as_uuid=True))
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_by = Column(UUID(as_uuid=True))
    approved_at = Column(DateTime)
    
    # Relationships
    control_recipes = relationship('ControlRecipe', back_populates='master_recipe')
    parameters_def = relationship('RecipeParameter', back_populates='recipe')
    
    __table_args__ = (
        UniqueConstraint('recipe_name', 'version', name='uq_recipe_version'),
        Index('idx_recipe_name', 'recipe_name'),
        Index('idx_recipe_status', 'status'),
    )


class RecipeParameter(Base):
    """Recipe parameter definitions"""
    __tablename__ = 'recipe_parameters'
    
    param_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id = Column(UUID(as_uuid=True), ForeignKey('master_recipes.recipe_id'), nullable=False)
    param_name = Column(String(100), nullable=False)
    param_type = Column(String(20), nullable=False)  # FLOAT, INT, STRING, BOOL
    default_value = Column(Text)
    min_value = Column(Numeric(15, 6))
    max_value = Column(Numeric(15, 6))
    units = Column(String(50))
    description = Column(Text)
    is_required = Column(Boolean, default=False)
    
    recipe = relationship('MasterRecipe', back_populates='parameters_def')
    
    __table_args__ = (
        UniqueConstraint('recipe_id', 'param_name', name='uq_recipe_param'),
    )


class ControlRecipe(Base):
    """Control recipe instance (specific execution)"""
    __tablename__ = 'control_recipes'
    
    control_recipe_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    master_recipe_id = Column(UUID(as_uuid=True), ForeignKey('master_recipes.recipe_id'), nullable=False)
    work_order_id = Column(UUID(as_uuid=True))  # Link to work orders
    
    # Parameter values for this instance
    parameter_values = Column(JSONB, default={})
    
    # Execution
    status = Column(String(20), default='pending')  # pending, running, completed, aborted
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Results
    actual_parameters = Column(JSONB)  # What was actually used
    execution_log = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    master_recipe = relationship('MasterRecipe', back_populates='control_recipes')


class RecipeChangeLog(Base):
    """Audit trail for recipe changes"""
    __tablename__ = 'recipe_change_log'
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    recipe_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    change_type = Column(String(50), nullable=False)  # CREATED, MODIFIED, APPROVED, OBSOLETED
    changed_by = Column(UUID(as_uuid=True), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    reason = Column(Text)


# =============================================================================
# MACHINE STATE
# =============================================================================

class Machine(Base):
    """Machine definitions"""
    __tablename__ = 'machines'
    
    machine_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    machine_name = Column(String(100), unique=True, nullable=False)
    machine_type = Column(String(50), nullable=False)  # CNC, 3D_PRINTER, ROBOT
    controller_type = Column(String(50))  # TINYG, GRBL, MARLIN, BAMBU, ROS2
    
    # Connection
    connection_type = Column(String(20))  # SERIAL, ETHERNET, MQTT, ROS2
    connection_config = Column(JSONB)  # Port, baud rate, IP, etc.
    
    # Status
    status = Column(String(20), default='disconnected')  # disconnected, idle, running, error, homing
    last_seen = Column(DateTime)
    
    # Capabilities
    capabilities = Column(JSONB)  # Axes, spindle, etc.
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_machine_status', 'status'),
    )


class MachineState(Base):
    """Real-time machine state snapshot"""
    __tablename__ = 'machine_states'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    machine_id = Column(UUID(as_uuid=True), ForeignKey('machines.machine_id'), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Position
    position_x = Column(Float)
    position_y = Column(Float)
    position_z = Column(Float)
    position_a = Column(Float)
    
    # Status
    state = Column(String(20))  # idle, running, hold, homing, alarm
    motion_mode = Column(String(10))  # G0, G1, G2, G3
    
    # Speeds
    feed_rate = Column(Float)
    spindle_speed = Column(Float)
    
    # Job progress
    current_line = Column(Integer)
    total_lines = Column(Integer)
    progress_pct = Column(Float)
    
    # Sensors
    sensor_data = Column(JSONB)
    
    __table_args__ = (
        Index('idx_machine_state_time', 'machine_id', 'timestamp'),
    )
