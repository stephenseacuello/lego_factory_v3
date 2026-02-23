"""ISO 23247 Digital Twin Schema

Revision ID: 20260101_000001
Revises: 20251231_000001
Create Date: 2026-01-01 00:00:01

ISO 23247 compliant digital twin tables:
- Observable Manufacturing Elements (OME)
- Digital Twin Instances
- Twin Events
- State History
- Sync Records
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20260101_000001'
down_revision: Union[str, None] = '20251231_000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ISO 23247 digital twin tables."""

    # =========================================================================
    # OBSERVABLE MANUFACTURING ELEMENTS (ISO 23247-3)
    # =========================================================================
    op.create_table(
        'observable_manufacturing_elements',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ome_type', sa.String(50), nullable=False),
        # Types: factory, production_line, work_cell, equipment, sensor, actuator, tool, fixture
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('namespace', sa.String(100), default='default', nullable=False),

        # Hierarchy
        sa.Column('parent_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id')),

        # Lifecycle (ISO 23247-3 Section 8.1)
        sa.Column('lifecycle_state', sa.String(50), default='design'),
        # States: design, commissioning, active, maintenance, degraded, standby, offline, retired
        sa.Column('lifecycle_history', sa.JSON()),

        # Static Attributes (ISO 23247-3 Section 7.3.1)
        sa.Column('static_attributes', sa.JSON()),
        # Contains: manufacturer, model, serial_number, dimensions, capabilities, work_envelope, etc.

        # Dynamic Attributes (ISO 23247-3 Section 7.3.2)
        sa.Column('dynamic_attributes', sa.JSON()),
        # Contains: status, temperatures, positions, oee, health_score, etc.

        # Behavior Model (ISO 23247-3 Section 7.4)
        sa.Column('behavior_model', sa.JSON()),
        # Contains: model_type, model_id, parameters, predictions_enabled, etc.

        # 3D Geometry for Unity visualization
        sa.Column('geometry_3d', sa.JSON()),
        # Contains: model_url, position, rotation, scale, color, material

        # Relationships
        sa.Column('relationships', sa.JSON()),

        # Metadata
        sa.Column('tags', sa.JSON()),
        sa.Column('custom_attributes', sa.JSON()),

        # Versioning
        sa.Column('version', sa.Integer(), default=1),
        sa.Column('checksum', sa.String(64)),

        # Sync status
        sa.Column('sync_status', sa.String(50), default='synced'),
        sa.Column('last_sync_at', sa.DateTime()),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(100)),
        sa.Column('updated_by', sa.String(100)),
    )
    op.create_index('ix_ome_namespace', 'observable_manufacturing_elements', ['namespace'])
    op.create_index('ix_ome_type', 'observable_manufacturing_elements', ['ome_type'])
    op.create_index('ix_ome_parent', 'observable_manufacturing_elements', ['parent_id'])
    op.create_index('ix_ome_lifecycle', 'observable_manufacturing_elements', ['lifecycle_state'])
    op.create_index('ix_ome_name', 'observable_manufacturing_elements', ['name'])

    # =========================================================================
    # DIGITAL TWIN INSTANCES
    # =========================================================================
    op.create_table(
        'digital_twin_instances',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ome_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id'), nullable=False),

        # Twin type
        sa.Column('twin_type', sa.String(50), nullable=False),
        # Types: monitoring, simulation, predictive, optimization, training

        # State
        sa.Column('state', sa.String(50), default='initializing'),
        # States: initializing, syncing, active, paused, simulating, error, stopped

        # Synchronization
        sa.Column('sync_mode', sa.String(50), default='realtime'),
        # Modes: realtime, periodic, on_demand, playback
        sa.Column('sync_interval_ms', sa.Integer(), default=1000),
        sa.Column('last_sync_at', sa.DateTime()),
        sa.Column('sync_lag_ms', sa.Float(), default=0.0),

        # Current state snapshot
        sa.Column('current_state', sa.JSON()),

        # Behavior model reference
        sa.Column('model_type', sa.String(50)),
        sa.Column('model_parameters', sa.JSON()),

        # Predictions cache
        sa.Column('predictions', sa.JSON()),

        # Performance metrics
        sa.Column('updates_per_second', sa.Float(), default=0.0),
        sa.Column('total_updates', sa.BigInteger(), default=0),
        sa.Column('error_count', sa.Integer(), default=0),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
        sa.Column('version', sa.Integer(), default=1),
    )
    op.create_index('ix_twin_ome', 'digital_twin_instances', ['ome_id'])
    op.create_index('ix_twin_type', 'digital_twin_instances', ['twin_type'])
    op.create_index('ix_twin_state', 'digital_twin_instances', ['state'])

    # =========================================================================
    # TWIN STATE HISTORY (Time-series)
    # =========================================================================
    op.create_table(
        'twin_state_history',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('twin_id', sa.String(36), sa.ForeignKey('digital_twin_instances.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, index=True),
        sa.Column('state_data', sa.JSON(), nullable=False),
        sa.Column('source', sa.String(50)),  # sensor, simulation, prediction, manual
    )
    op.create_index('ix_state_history_twin_time', 'twin_state_history', ['twin_id', 'timestamp'])

    # =========================================================================
    # TWIN EVENTS (Event Sourcing)
    # =========================================================================
    op.create_table(
        'twin_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('twin_id', sa.String(36), sa.ForeignKey('digital_twin_instances.id'), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        # Types: state_change, sensor_update, maintenance, quality, command, alert, vision

        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('priority', sa.String(20), default='normal'),
        # Priorities: low, normal, high, critical

        sa.Column('sequence_number', sa.BigInteger(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),

        sa.Column('event_data', sa.JSON(), nullable=False),

        # Correlation for tracing
        sa.Column('correlation_id', sa.String(36)),
        sa.Column('causation_id', sa.String(36)),

        # Metadata
        sa.Column('source_system', sa.String(100)),
        sa.Column('user_id', sa.String(100)),
        sa.Column('tags', sa.JSON()),

        sa.Column('version', sa.Integer(), default=1),
    )
    op.create_index('ix_events_twin_seq', 'twin_events', ['twin_id', 'sequence_number'])
    op.create_index('ix_events_type', 'twin_events', ['event_type'])
    op.create_index('ix_events_timestamp', 'twin_events', ['timestamp'])
    op.create_index('ix_events_correlation', 'twin_events', ['correlation_id'])

    # =========================================================================
    # SYNC RECORDS (Bi-directional Sync Tracking)
    # =========================================================================
    op.create_table(
        'sync_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ome_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id'), nullable=False),
        sa.Column('twin_id', sa.String(36), sa.ForeignKey('digital_twin_instances.id')),

        sa.Column('sync_direction', sa.String(50), nullable=False),
        # Directions: physical_to_digital, digital_to_physical, bidirectional

        sa.Column('sync_status', sa.String(50), nullable=False),
        # Statuses: synced, pending, syncing, conflict, error, offline

        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('duration_ms', sa.Float()),

        # Change tracking
        sa.Column('changes', sa.JSON()),
        sa.Column('change_count', sa.Integer(), default=0),

        # Conflict handling
        sa.Column('conflict_detected', sa.Boolean(), default=False),
        sa.Column('conflict_resolution', sa.String(50)),
        # Resolutions: last_write_wins, physical_wins, digital_wins, merge, manual
        sa.Column('conflict_data', sa.JSON()),

        # Integrity
        sa.Column('checksum_before', sa.String(64)),
        sa.Column('checksum_after', sa.String(64)),

        sa.Column('error_message', sa.Text()),
    )
    op.create_index('ix_sync_ome', 'sync_records', ['ome_id'])
    op.create_index('ix_sync_status', 'sync_records', ['sync_status'])
    op.create_index('ix_sync_started', 'sync_records', ['started_at'])

    # =========================================================================
    # PREDICTIONS
    # =========================================================================
    op.create_table(
        'twin_predictions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('twin_id', sa.String(36), sa.ForeignKey('digital_twin_instances.id'), nullable=False),
        sa.Column('ome_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id'), nullable=False),

        sa.Column('prediction_type', sa.String(50), nullable=False),
        # Types: failure, quality, rul, throughput, energy, maintenance

        sa.Column('predicted_value', sa.Float()),
        sa.Column('prediction_data', sa.JSON()),
        sa.Column('confidence', sa.Float()),
        sa.Column('model_id', sa.String(100)),
        sa.Column('model_version', sa.String(50)),

        sa.Column('predicted_at', sa.DateTime(), nullable=False),
        sa.Column('valid_until', sa.DateTime()),

        sa.Column('contributing_factors', sa.JSON()),
        sa.Column('recommendations', sa.JSON()),

        # Validation (when actual outcome known)
        sa.Column('actual_value', sa.Float()),
        sa.Column('actual_at', sa.DateTime()),
        sa.Column('accuracy', sa.Float()),  # Calculated after actual known
    )
    op.create_index('ix_predictions_twin', 'twin_predictions', ['twin_id'])
    op.create_index('ix_predictions_type', 'twin_predictions', ['prediction_type'])
    op.create_index('ix_predictions_valid', 'twin_predictions', ['valid_until'])

    # =========================================================================
    # SIMULATION RUNS
    # =========================================================================
    op.create_table(
        'simulation_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('twin_id', sa.String(36), sa.ForeignKey('digital_twin_instances.id'), nullable=False),

        sa.Column('simulation_type', sa.String(50)),
        # Types: production, what_if, monte_carlo, capacity, failure

        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime()),

        # Configuration
        sa.Column('duration_simulated', sa.Float()),  # Simulated time in seconds
        sa.Column('time_scale', sa.Float(), default=1.0),  # 1.0 = real-time
        sa.Column('initial_state', sa.JSON()),
        sa.Column('parameters', sa.JSON()),
        sa.Column('random_seed', sa.Integer()),

        # Results
        sa.Column('final_state', sa.JSON()),
        sa.Column('metrics', sa.JSON()),
        sa.Column('events', sa.JSON()),
        sa.Column('warnings', sa.JSON()),

        # Time series data (can be large)
        sa.Column('time_series_count', sa.Integer()),
        sa.Column('time_series_url', sa.String(500)),  # External storage for large data

        sa.Column('created_by', sa.String(100)),
    )
    op.create_index('ix_simulation_twin', 'simulation_runs', ['twin_id'])
    op.create_index('ix_simulation_type', 'simulation_runs', ['simulation_type'])

    # =========================================================================
    # UNITY SCENE CONFIGURATION
    # =========================================================================
    op.create_table(
        'unity_scene_configs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('scene_name', sa.String(100), nullable=False),
        sa.Column('namespace', sa.String(100), default='default'),

        # Equipment positions in scene
        sa.Column('equipment_positions', sa.JSON()),
        # Format: {ome_id: {position: {x,y,z}, rotation: {x,y,z}, scale: {x,y,z}}}

        # Camera presets
        sa.Column('camera_presets', sa.JSON()),

        # Visualization settings
        sa.Column('visualization_settings', sa.JSON()),
        # Contains: lighting, materials, LOD settings, etc.

        # Flow paths for material visualization
        sa.Column('flow_paths', sa.JSON()),

        # Annotations
        sa.Column('annotations', sa.JSON()),

        sa.Column('created_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index('ix_scene_namespace', 'unity_scene_configs', ['namespace'])

    # =========================================================================
    # SPATIAL ANCHORS (AR/VR)
    # =========================================================================
    op.create_table(
        'spatial_anchors',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('anchor_id', sa.String(100), nullable=False, unique=True),
        sa.Column('ome_id', sa.String(36), sa.ForeignKey('observable_manufacturing_elements.id')),

        # Position in world coordinates
        sa.Column('position', sa.JSON()),  # {x, y, z}
        sa.Column('rotation', sa.JSON()),  # {x, y, z, w} quaternion

        # Platform-specific data
        sa.Column('platform', sa.String(50)),  # hololens, quest, ios, android
        sa.Column('platform_anchor_data', sa.JSON()),

        # Validity
        sa.Column('is_valid', sa.Boolean(), default=True),
        sa.Column('last_validated', sa.DateTime()),

        sa.Column('created_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_anchor_ome', 'spatial_anchors', ['ome_id'])

    # =========================================================================
    # ISO 23247 COMPLIANCE RECORDS
    # =========================================================================
    op.create_table(
        'iso23247_compliance_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('report_id', sa.String(100), nullable=False, unique=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False),

        sa.Column('overall_level', sa.Integer()),  # 0-4
        sa.Column('overall_score', sa.Float()),

        sa.Column('requirements_status', sa.JSON()),
        sa.Column('gaps_summary', sa.JSON()),
        sa.Column('roadmap', sa.JSON()),

        sa.Column('generated_by', sa.String(100)),
    )
    op.create_index('ix_compliance_generated', 'iso23247_compliance_records', ['generated_at'])


def downgrade() -> None:
    """Drop ISO 23247 digital twin tables."""
    op.drop_table('iso23247_compliance_records')
    op.drop_table('spatial_anchors')
    op.drop_table('unity_scene_configs')
    op.drop_table('simulation_runs')
    op.drop_table('twin_predictions')
    op.drop_table('sync_records')
    op.drop_table('twin_events')
    op.drop_table('twin_state_history')
    op.drop_table('digital_twin_instances')
    op.drop_table('observable_manufacturing_elements')
