"""Add resource tracking tables for MESA-11 Resource Allocation & Data Collection

Revision ID: 005_resource_tracking
Revises: 004_routing_eligible
Create Date: 2026-01-28

Creates:
- resource_status: Real-time machine status tracking
- tool_inventory: Tool tracking with wear monitoring
- material_lots: Material inventory with lot tracking
- material_reservations: Material reservations for jobs
- sensor_readings: TimescaleDB hypertable for time-series sensor data
- data_collection_events: Machine events log
- machine_heartbeats: Connection monitoring
- tag_definitions: Sensor tag metadata
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '005_resource_tracking'
down_revision = '004_routing_eligible'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # Resource Status - Real-time machine status
    # =========================================================================
    op.create_table(
        'resource_status',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),

        # Machine identification
        sa.Column('machine_id', sa.String(50), nullable=False, unique=True),
        sa.Column('machine_name', sa.String(200)),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='offline'),
        sa.Column('previous_status', sa.String(20)),
        sa.Column('status_changed_at', sa.DateTime(timezone=True)),

        # Current work
        sa.Column('current_job_id', sa.String(50)),
        sa.Column('current_work_order_id', sa.String(50)),
        sa.Column('current_operation_name', sa.String(200)),
        sa.Column('current_material_type', sa.String(50)),
        sa.Column('current_material_lot', sa.String(50)),

        # Utilization
        sa.Column('utilization_1hr', sa.Float, server_default='0'),
        sa.Column('utilization_8hr', sa.Float, server_default='0'),
        sa.Column('utilization_24hr', sa.Float, server_default='0'),

        # Connection
        sa.Column('is_connected', sa.Boolean, server_default='false'),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True)),
        sa.Column('connection_error', sa.Text),

        # Position
        sa.Column('position_x', sa.Float),
        sa.Column('position_y', sa.Float),
        sa.Column('position_z', sa.Float),

        # Sensors
        sa.Column('spindle_rpm', sa.Float),
        sa.Column('extruder_temp', sa.Float),
        sa.Column('bed_temp', sa.Float),

        # Job progress
        sa.Column('job_progress_pct', sa.Float, server_default='0'),
        sa.Column('estimated_completion', sa.DateTime(timezone=True)),

        # Alarm
        sa.Column('has_alarm', sa.Boolean, server_default='false'),
        sa.Column('alarm_code', sa.String(50)),
        sa.Column('alarm_message', sa.Text),

        # Extra
        sa.Column('extra_data', postgresql.JSONB, server_default='{}'),
    )
    op.create_index('ix_resource_status_machine_id', 'resource_status', ['machine_id'])
    op.create_index('ix_resource_status_status', 'resource_status', ['status'])

    # =========================================================================
    # Tool Inventory
    # =========================================================================
    op.create_table(
        'tool_inventory',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
        sa.Column('is_deleted', sa.Boolean, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.Column('deleted_by', sa.String(100)),

        # Tool identification
        sa.Column('tool_id', sa.String(50), nullable=False, unique=True),
        sa.Column('tool_number', sa.Integer),
        sa.Column('tool_type', sa.String(100), nullable=False),
        sa.Column('tool_name', sa.String(200)),
        sa.Column('description', sa.Text),

        # Specs
        sa.Column('diameter_mm', sa.Float),
        sa.Column('length_mm', sa.Float),
        sa.Column('flute_count', sa.Integer),
        sa.Column('material', sa.String(50)),
        sa.Column('coating', sa.String(50)),

        # Location
        sa.Column('machine_id', sa.String(50)),
        sa.Column('magazine_slot', sa.Integer),
        sa.Column('storage_location', sa.String(100)),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='available'),

        # Wear
        sa.Column('wear_percent', sa.Float, server_default='0'),
        sa.Column('remaining_life_mins', sa.Float),
        sa.Column('total_cutting_time_mins', sa.Float, server_default='0'),
        sa.Column('cut_count', sa.Integer, server_default='0'),
        sa.Column('expected_life_mins', sa.Float),
        sa.Column('wear_rate_per_min', sa.Float),

        # Installation
        sa.Column('installed_at', sa.DateTime(timezone=True)),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),

        # Calibration
        sa.Column('length_offset', sa.Float, server_default='0'),
        sa.Column('diameter_offset', sa.Float, server_default='0'),
        sa.Column('last_calibrated_at', sa.DateTime(timezone=True)),

        # Cost
        sa.Column('purchase_cost', sa.Numeric(10, 2)),
        sa.Column('cost_per_minute', sa.Numeric(10, 4)),

        # Notes
        sa.Column('notes', sa.Text),
        sa.Column('extra_data', postgresql.JSONB, server_default='{}'),
    )
    op.create_index('ix_tool_inventory_tool_id', 'tool_inventory', ['tool_id'])
    op.create_index('ix_tool_inventory_machine', 'tool_inventory', ['machine_id', 'status'])
    op.create_index('ix_tool_inventory_type', 'tool_inventory', ['tool_type'])

    # =========================================================================
    # Material Lots
    # =========================================================================
    op.create_table(
        'material_lots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
        sa.Column('is_deleted', sa.Boolean, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.Column('deleted_by', sa.String(100)),

        # Lot identification
        sa.Column('lot_number', sa.String(50), nullable=False, unique=True),
        sa.Column('material_type', sa.String(50), nullable=False),
        sa.Column('material_code', sa.String(50)),
        sa.Column('material_name', sa.String(200)),
        sa.Column('description', sa.Text),

        # Properties
        sa.Column('material_category', sa.String(50)),
        sa.Column('color', sa.String(50)),
        sa.Column('color_hex', sa.String(7)),
        sa.Column('grade', sa.String(50)),

        # Quantities
        sa.Column('quantity_received', sa.Float, nullable=False),
        sa.Column('quantity_available', sa.Float, nullable=False),
        sa.Column('quantity_reserved', sa.Float, server_default='0'),
        sa.Column('quantity_consumed', sa.Float, server_default='0'),
        sa.Column('unit_of_measure', sa.String(20), server_default="'g'"),

        # Location
        sa.Column('location', sa.String(100)),
        sa.Column('bin_number', sa.String(50)),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='available'),

        # Supplier
        sa.Column('supplier', sa.String(200)),
        sa.Column('supplier_lot', sa.String(100)),
        sa.Column('purchase_order', sa.String(50)),

        # Dates
        sa.Column('received_date', sa.DateTime(timezone=True)),
        sa.Column('manufacture_date', sa.DateTime(timezone=True)),
        sa.Column('expiry_date', sa.DateTime(timezone=True)),
        sa.Column('opened_date', sa.DateTime(timezone=True)),

        # Quality
        sa.Column('certificate_of_analysis', sa.String(500)),
        sa.Column('inspection_status', sa.String(50)),
        sa.Column('quality_notes', sa.Text),

        # Cost
        sa.Column('cost_per_unit', sa.Numeric(10, 4)),
        sa.Column('total_cost', sa.Numeric(10, 2)),

        # Filament specific
        sa.Column('spool_weight_g', sa.Float),
        sa.Column('filament_diameter_mm', sa.Float),
        sa.Column('print_temp_min', sa.Float),
        sa.Column('print_temp_max', sa.Float),
        sa.Column('bed_temp_min', sa.Float),
        sa.Column('bed_temp_max', sa.Float),

        # Metal specific
        sa.Column('thickness_mm', sa.Float),
        sa.Column('width_mm', sa.Float),
        sa.Column('length_mm', sa.Float),
        sa.Column('hardness', sa.String(20)),

        # Notes
        sa.Column('notes', sa.Text),
        sa.Column('extra_data', postgresql.JSONB, server_default='{}'),
    )
    op.create_index('ix_material_lots_lot_number', 'material_lots', ['lot_number'])
    op.create_index('ix_material_lots_type_status', 'material_lots', ['material_type', 'status'])
    op.create_index('ix_material_lots_location', 'material_lots', ['location'])

    # =========================================================================
    # Material Reservations
    # =========================================================================
    op.create_table(
        'material_reservations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),

        # References
        sa.Column('lot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_lots.id'), nullable=False),
        sa.Column('job_id', sa.String(50), nullable=False),
        sa.Column('work_order_id', sa.String(50)),

        # Quantities
        sa.Column('quantity_reserved', sa.Float, nullable=False),
        sa.Column('quantity_consumed', sa.Float, server_default='0'),
        sa.Column('unit_of_measure', sa.String(20)),

        # Status
        sa.Column('status', sa.String(20), server_default='active'),

        # Timing
        sa.Column('reserved_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('consumed_at', sa.DateTime(timezone=True)),
        sa.Column('released_at', sa.DateTime(timezone=True)),

        # Audit
        sa.Column('reserved_by', sa.String(100)),
        sa.Column('notes', sa.Text),
    )
    op.create_index('ix_material_reservations_job', 'material_reservations', ['job_id'])
    op.create_index('ix_material_reservations_lot', 'material_reservations', ['lot_id', 'status'])

    # =========================================================================
    # Sensor Readings - TimescaleDB Hypertable
    # =========================================================================
    op.create_table(
        'sensor_readings',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),

        # Source
        sa.Column('machine_id', sa.String(50), nullable=False),
        sa.Column('tag_name', sa.String(100), nullable=False),

        # Values
        sa.Column('value_float', sa.Float),
        sa.Column('value_int', sa.Integer),
        sa.Column('value_str', sa.String(500)),
        sa.Column('value_bool', sa.Boolean),

        # Metadata
        sa.Column('unit', sa.String(20)),
        sa.Column('quality', sa.Integer, server_default='192'),
        sa.Column('source', sa.String(50)),
    )
    op.create_index('ix_sensor_readings_machine_tag_time', 'sensor_readings', ['machine_id', 'tag_name', 'timestamp'])
    op.create_index('ix_sensor_readings_time', 'sensor_readings', ['timestamp'])

    # Convert to TimescaleDB hypertable (if TimescaleDB is available)
    try:
        op.execute("SELECT create_hypertable('sensor_readings', 'timestamp', if_not_exists => TRUE)")
    except Exception as e:
        print(f"Note: Could not create hypertable (TimescaleDB may not be installed): {e}")

    # =========================================================================
    # Data Collection Events
    # =========================================================================
    op.create_table(
        'data_collection_events',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),

        # Machine
        sa.Column('machine_id', sa.String(50), nullable=False),

        # Event
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_code', sa.String(50)),
        sa.Column('description', sa.Text),

        # State transition
        sa.Column('previous_state', sa.String(50)),
        sa.Column('new_state', sa.String(50)),

        # Related objects
        sa.Column('job_id', sa.String(50)),
        sa.Column('work_order_id', sa.String(50)),
        sa.Column('operation_id', sa.String(50)),

        # Data
        sa.Column('data', postgresql.JSONB, server_default='{}'),
        sa.Column('severity', sa.String(20)),

        # Acknowledgment
        sa.Column('acknowledged', sa.Boolean, server_default='false'),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True)),
        sa.Column('acknowledged_by', sa.String(100)),

        # Source
        sa.Column('source', sa.String(50)),
        sa.Column('operator_id', sa.String(50)),
    )
    op.create_index('ix_data_collection_events_machine_time', 'data_collection_events', ['machine_id', 'timestamp'])
    op.create_index('ix_data_collection_events_type', 'data_collection_events', ['event_type', 'timestamp'])
    op.create_index('ix_data_collection_events_job', 'data_collection_events', ['job_id'])

    # =========================================================================
    # Machine Heartbeats
    # =========================================================================
    op.create_table(
        'machine_heartbeats',
        sa.Column('machine_id', sa.String(50), primary_key=True),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=False),
        sa.Column('heartbeat_interval_sec', sa.Integer, server_default='10'),
        sa.Column('is_connected', sa.Boolean, server_default='true'),
        sa.Column('connection_type', sa.String(50)),
        sa.Column('ip_address', sa.String(50)),
        sa.Column('port', sa.Integer),
        sa.Column('last_error', sa.Text),
        sa.Column('consecutive_failures', sa.Integer, server_default='0'),
    )

    # =========================================================================
    # Tag Definitions
    # =========================================================================
    op.create_table(
        'tag_definitions',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),

        # Tag identification
        sa.Column('tag_name', sa.String(100), nullable=False, unique=True),
        sa.Column('display_name', sa.String(200)),
        sa.Column('description', sa.Text),

        # Machine
        sa.Column('machine_id', sa.String(50)),
        sa.Column('machine_type', sa.String(50)),

        # Data type
        sa.Column('data_type', sa.String(20), nullable=False),
        sa.Column('unit', sa.String(20)),
        sa.Column('precision', sa.Integer),

        # Constraints
        sa.Column('min_value', sa.Float),
        sa.Column('max_value', sa.Float),
        sa.Column('default_value', sa.String(100)),

        # Alarms
        sa.Column('alarm_high_high', sa.Float),
        sa.Column('alarm_high', sa.Float),
        sa.Column('alarm_low', sa.Float),
        sa.Column('alarm_low_low', sa.Float),

        # Collection
        sa.Column('collection_rate_ms', sa.Integer, server_default='1000'),
        sa.Column('deadband', sa.Float),
        sa.Column('is_active', sa.Boolean, server_default='true'),

        # Aggregation
        sa.Column('aggregate_type', sa.String(20)),
        sa.Column('retention_days', sa.Integer, server_default='365'),

        # Category
        sa.Column('category', sa.String(50)),
        sa.Column('group_name', sa.String(100)),

        # Source
        sa.Column('source_address', sa.String(200)),
        sa.Column('source_type', sa.String(50)),
    )
    op.create_index('ix_tag_definitions_tag_name', 'tag_definitions', ['tag_name'])
    op.create_index('ix_tag_definitions_machine', 'tag_definitions', ['machine_id'])


def downgrade() -> None:
    op.drop_table('tag_definitions')
    op.drop_table('machine_heartbeats')
    op.drop_table('data_collection_events')
    op.drop_table('sensor_readings')
    op.drop_table('material_reservations')
    op.drop_table('material_lots')
    op.drop_table('tool_inventory')
    op.drop_table('resource_status')
