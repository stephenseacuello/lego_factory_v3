"""Initial database schema for LegoMCP v5.0

Revision ID: 20251231_000001
Revises:
Create Date: 2025-12-31 00:00:01

LegoMCP PhD-Level Manufacturing Platform
Complete initial schema with all core tables
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '20251231_000001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables for LegoMCP platform."""

    # =========================================================================
    # USERS & AUTHENTICATION
    # =========================================================================
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(100), unique=True, nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), default='operator'),
        sa.Column('department', sa.String(100)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('mfa_enabled', sa.Boolean(), default=False),
        sa.Column('mfa_secret', sa.String(32)),
        sa.Column('last_login', sa.DateTime()),
        sa.Column('failed_attempts', sa.Integer(), default=0),
        sa.Column('locked_until', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_username', 'users', ['username'])

    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100)),
        sa.Column('resource_id', sa.String(100)),
        sa.Column('old_value', sa.JSON()),
        sa.Column('new_value', sa.JSON()),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('signature', sa.String(512)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_audit_log_user_id', 'audit_log', ['user_id'])
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])

    # =========================================================================
    # MANUFACTURING CORE
    # =========================================================================
    op.create_table(
        'work_orders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('order_number', sa.String(50), unique=True, nullable=False),
        sa.Column('product_id', sa.String(36)),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), default=5),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('scheduled_start', sa.DateTime()),
        sa.Column('scheduled_end', sa.DateTime()),
        sa.Column('actual_start', sa.DateTime()),
        sa.Column('actual_end', sa.DateTime()),
        sa.Column('assigned_cell', sa.String(50)),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index('ix_work_orders_status', 'work_orders', ['status'])
    op.create_index('ix_work_orders_scheduled_start', 'work_orders', ['scheduled_start'])

    op.create_table(
        'equipment',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('equipment_type', sa.String(50)),
        sa.Column('model', sa.String(100)),
        sa.Column('manufacturer', sa.String(100)),
        sa.Column('serial_number', sa.String(100)),
        sa.Column('location', sa.String(100)),
        sa.Column('status', sa.String(50), default='operational'),
        sa.Column('oee_target', sa.Float(), default=0.85),
        sa.Column('maintenance_interval_hours', sa.Integer()),
        sa.Column('last_maintenance', sa.DateTime()),
        sa.Column('next_maintenance', sa.DateTime()),
        sa.Column('total_runtime_hours', sa.Float(), default=0),
        sa.Column('metadata', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )

    op.create_table(
        'production_metrics',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('equipment_id', sa.String(36), sa.ForeignKey('equipment.id')),
        sa.Column('work_order_id', sa.String(36), sa.ForeignKey('work_orders.id')),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('availability', sa.Float()),
        sa.Column('performance', sa.Float()),
        sa.Column('quality', sa.Float()),
        sa.Column('oee', sa.Float()),
        sa.Column('cycle_time_seconds', sa.Float()),
        sa.Column('parts_produced', sa.Integer()),
        sa.Column('defects', sa.Integer()),
        sa.Column('downtime_minutes', sa.Float()),
        sa.Column('energy_kwh', sa.Float()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_production_metrics_timestamp', 'production_metrics', ['timestamp'])
    op.create_index('ix_production_metrics_equipment', 'production_metrics', ['equipment_id'])

    # =========================================================================
    # QUALITY MANAGEMENT
    # =========================================================================
    op.create_table(
        'quality_inspections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('work_order_id', sa.String(36), sa.ForeignKey('work_orders.id')),
        sa.Column('equipment_id', sa.String(36), sa.ForeignKey('equipment.id')),
        sa.Column('inspector_id', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('inspection_type', sa.String(50)),
        sa.Column('result', sa.String(50)),
        sa.Column('defect_count', sa.Integer(), default=0),
        sa.Column('measurements', sa.JSON()),
        sa.Column('images', sa.JSON()),
        sa.Column('notes', sa.Text()),
        sa.Column('ai_prediction', sa.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'spc_data',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('equipment_id', sa.String(36), sa.ForeignKey('equipment.id')),
        sa.Column('parameter_name', sa.String(100), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('ucl', sa.Float()),
        sa.Column('lcl', sa.Float()),
        sa.Column('target', sa.Float()),
        sa.Column('out_of_control', sa.Boolean(), default=False),
        sa.Column('rule_violations', sa.JSON()),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_spc_data_timestamp', 'spc_data', ['timestamp'])
    op.create_index('ix_spc_data_parameter', 'spc_data', ['parameter_name'])

    op.create_table(
        'capa_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('capa_number', sa.String(50), unique=True, nullable=False),
        sa.Column('capa_type', sa.String(20)),  # corrective/preventive
        sa.Column('status', sa.String(50), default='open'),
        sa.Column('priority', sa.String(20)),
        sa.Column('source', sa.String(100)),
        sa.Column('description', sa.Text()),
        sa.Column('root_cause', sa.Text()),
        sa.Column('proposed_action', sa.Text()),
        sa.Column('implemented_action', sa.Text()),
        sa.Column('verification_method', sa.Text()),
        sa.Column('effectiveness_check', sa.JSON()),
        sa.Column('assigned_to', sa.String(36), sa.ForeignKey('users.id')),
        sa.Column('due_date', sa.Date()),
        sa.Column('closed_date', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )

    # =========================================================================
    # INVENTORY & SUPPLY CHAIN
    # =========================================================================
    op.create_table(
        'inventory_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sku', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100)),
        sa.Column('quantity_on_hand', sa.Integer(), default=0),
        sa.Column('quantity_reserved', sa.Integer(), default=0),
        sa.Column('quantity_on_order', sa.Integer(), default=0),
        sa.Column('reorder_point', sa.Integer()),
        sa.Column('reorder_quantity', sa.Integer()),
        sa.Column('unit_cost', sa.Numeric(10, 4)),
        sa.Column('location', sa.String(100)),
        sa.Column('abc_class', sa.String(1)),
        sa.Column('xyz_class', sa.String(1)),
        sa.Column('lead_time_days', sa.Integer()),
        sa.Column('supplier_id', sa.String(36)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index('ix_inventory_items_sku', 'inventory_items', ['sku'])

    op.create_table(
        'suppliers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('code', sa.String(50), unique=True),
        sa.Column('tier', sa.Integer(), default=1),
        sa.Column('status', sa.String(50), default='active'),
        sa.Column('quality_rating', sa.Float()),
        sa.Column('delivery_rating', sa.Float()),
        sa.Column('cost_rating', sa.Float()),
        sa.Column('overall_score', sa.Float()),
        sa.Column('contact_name', sa.String(200)),
        sa.Column('contact_email', sa.String(255)),
        sa.Column('contact_phone', sa.String(50)),
        sa.Column('address', sa.JSON()),
        sa.Column('certifications', sa.JSON()),
        sa.Column('risk_score', sa.Float()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )

    # =========================================================================
    # AI/ML MODELS
    # =========================================================================
    op.create_table(
        'ml_models',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('model_type', sa.String(100)),
        sa.Column('framework', sa.String(50)),
        sa.Column('status', sa.String(50), default='training'),
        sa.Column('accuracy', sa.Float()),
        sa.Column('f1_score', sa.Float()),
        sa.Column('precision', sa.Float()),
        sa.Column('recall', sa.Float()),
        sa.Column('hyperparameters', sa.JSON()),
        sa.Column('training_config', sa.JSON()),
        sa.Column('artifact_path', sa.String(500)),
        sa.Column('deployed_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
        sa.UniqueConstraint('name', 'version', name='uq_model_name_version'),
    )

    op.create_table(
        'ml_predictions',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('model_id', sa.String(36), sa.ForeignKey('ml_models.id')),
        sa.Column('input_data', sa.JSON()),
        sa.Column('prediction', sa.JSON()),
        sa.Column('confidence', sa.Float()),
        sa.Column('actual_outcome', sa.JSON()),
        sa.Column('latency_ms', sa.Float()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_ml_predictions_model', 'ml_predictions', ['model_id'])
    op.create_index('ix_ml_predictions_created', 'ml_predictions', ['created_at'])

    op.create_table(
        'model_drift_metrics',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('model_id', sa.String(36), sa.ForeignKey('ml_models.id')),
        sa.Column('metric_type', sa.String(50)),
        sa.Column('value', sa.Float()),
        sa.Column('threshold', sa.Float()),
        sa.Column('is_drifted', sa.Boolean(), default=False),
        sa.Column('window_start', sa.DateTime()),
        sa.Column('window_end', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # =========================================================================
    # SUSTAINABILITY
    # =========================================================================
    op.create_table(
        'energy_consumption',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('equipment_id', sa.String(36), sa.ForeignKey('equipment.id')),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('power_kw', sa.Float()),
        sa.Column('energy_kwh', sa.Float()),
        sa.Column('power_factor', sa.Float()),
        sa.Column('voltage', sa.Float()),
        sa.Column('current', sa.Float()),
        sa.Column('source', sa.String(50)),  # grid/solar/wind
        sa.Column('carbon_kg', sa.Float()),
        sa.Column('cost', sa.Numeric(10, 4)),
    )
    op.create_index('ix_energy_timestamp', 'energy_consumption', ['timestamp'])

    op.create_table(
        'carbon_footprint',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('scope', sa.Integer()),  # 1, 2, 3
        sa.Column('category', sa.String(100)),
        sa.Column('source', sa.String(200)),
        sa.Column('emissions_kg_co2e', sa.Float()),
        sa.Column('calculation_method', sa.String(100)),
        sa.Column('data_quality_score', sa.Float()),
        sa.Column('period_start', sa.Date()),
        sa.Column('period_end', sa.Date()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # =========================================================================
    # DIGITAL TWIN
    # =========================================================================
    op.create_table(
        'digital_twin_state',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('asset_id', sa.String(36)),
        sa.Column('asset_type', sa.String(100)),
        sa.Column('state', sa.JSON(), nullable=False),
        sa.Column('version', sa.BigInteger(), default=1),
        sa.Column('sync_status', sa.String(50), default='synced'),
        sa.Column('last_sync', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now()),
    )
    op.create_index('ix_dt_state_asset', 'digital_twin_state', ['asset_id'])

    op.create_table(
        'digital_twin_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('twin_id', sa.String(36), sa.ForeignKey('digital_twin_state.id')),
        sa.Column('event_type', sa.String(100)),
        sa.Column('payload', sa.JSON()),
        sa.Column('sequence_number', sa.BigInteger()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_dt_events_twin', 'digital_twin_events', ['twin_id'])
    op.create_index('ix_dt_events_seq', 'digital_twin_events', ['sequence_number'])


def downgrade() -> None:
    """Drop all tables in reverse order."""
    op.drop_table('digital_twin_events')
    op.drop_table('digital_twin_state')
    op.drop_table('carbon_footprint')
    op.drop_table('energy_consumption')
    op.drop_table('model_drift_metrics')
    op.drop_table('ml_predictions')
    op.drop_table('ml_models')
    op.drop_table('suppliers')
    op.drop_table('inventory_items')
    op.drop_table('capa_records')
    op.drop_table('spc_data')
    op.drop_table('quality_inspections')
    op.drop_table('production_metrics')
    op.drop_table('equipment')
    op.drop_table('work_orders')
    op.drop_table('audit_log')
    op.drop_table('users')
