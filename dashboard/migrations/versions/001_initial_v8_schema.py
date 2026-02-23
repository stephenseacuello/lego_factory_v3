"""
LEGO MCP v8.0 Initial Database Schema

Revision ID: 001_initial_v8
Revises: None
Create Date: 2024-01-15

This migration creates the initial v8.0 database schema including:
- Manufacturing entities (equipment, jobs, orders)
- Digital twin state tables
- AI/ML model tracking
- Audit trail with chain integrity
- Compliance tracking (CMMC)
- User and access control
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_v8'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial v8.0 schema."""

    # ==========================================================================
    # User and Authentication Tables
    # ==========================================================================

    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, default='operator'),
        sa.Column('department', sa.String(100)),
        sa.Column('spiffe_id', sa.String(255), unique=True),
        sa.Column('mfa_enabled', sa.Boolean, default=False),
        sa.Column('mfa_secret', sa.LargeBinary),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('last_login', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_spiffe_id', 'users', ['spiffe_id'])

    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('key_prefix', sa.String(10), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.String), default=[]),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('last_used', sa.DateTime(timezone=True)),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_api_keys_prefix', 'api_keys', ['key_prefix'])

    # ==========================================================================
    # Equipment Tables
    # ==========================================================================

    op.create_table(
        'equipment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('equipment_id', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),  # cnc, 3d_printer, robot_arm, injection
        sa.Column('manufacturer', sa.String(100)),
        sa.Column('model', sa.String(100)),
        sa.Column('serial_number', sa.String(100)),
        sa.Column('location', sa.String(100)),
        sa.Column('status', sa.String(50), default='offline'),  # offline, idle, running, maintenance, failed
        sa.Column('health_score', sa.Float, default=1.0),
        sa.Column('configuration', postgresql.JSONB),
        sa.Column('capabilities', postgresql.ARRAY(sa.String)),
        sa.Column('installed_at', sa.DateTime(timezone=True)),
        sa.Column('last_maintenance', sa.DateTime(timezone=True)),
        sa.Column('next_maintenance', sa.DateTime(timezone=True)),
        sa.Column('total_runtime_hours', sa.Float, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_equipment_id', 'equipment', ['equipment_id'])
    op.create_index('ix_equipment_type', 'equipment', ['type'])
    op.create_index('ix_equipment_status', 'equipment', ['status'])

    op.create_table(
        'equipment_metrics',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('equipment.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metric_type', sa.String(50), nullable=False),
        sa.Column('value', sa.Float, nullable=False),
        sa.Column('unit', sa.String(20)),
        sa.Column('metadata', postgresql.JSONB),
    )
    op.create_index('ix_equipment_metrics_ts', 'equipment_metrics', ['equipment_id', 'timestamp'])

    # ==========================================================================
    # Manufacturing Job Tables
    # ==========================================================================

    op.create_table(
        'manufacturing_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_number', sa.String(50), unique=True, nullable=False),
        sa.Column('customer', sa.String(255)),
        sa.Column('priority', sa.Integer, default=5),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('quantity', sa.Integer, nullable=False),
        sa.Column('completed_quantity', sa.Integer, default=0),
        sa.Column('defect_quantity', sa.Integer, default=0),
        sa.Column('product_spec', postgresql.JSONB),
        sa.Column('due_date', sa.DateTime(timezone=True)),
        sa.Column('scheduled_start', sa.DateTime(timezone=True)),
        sa.Column('actual_start', sa.DateTime(timezone=True)),
        sa.Column('actual_end', sa.DateTime(timezone=True)),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index('ix_mfg_orders_number', 'manufacturing_orders', ['order_number'])
    op.create_index('ix_mfg_orders_status', 'manufacturing_orders', ['status'])

    op.create_table(
        'manufacturing_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_number', sa.String(50), unique=True, nullable=False),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('manufacturing_orders.id')),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('equipment.id')),
        sa.Column('operation_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('parameters', postgresql.JSONB),
        sa.Column('sequence', sa.Integer, default=1),
        sa.Column('estimated_duration', sa.Interval),
        sa.Column('actual_duration', sa.Interval),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('result', postgresql.JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_mfg_jobs_number', 'manufacturing_jobs', ['job_number'])
    op.create_index('ix_mfg_jobs_status', 'manufacturing_jobs', ['status'])

    # ==========================================================================
    # Digital Twin Tables
    # ==========================================================================

    op.create_table(
        'digital_twin_states',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('equipment.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('state_type', sa.String(50), nullable=False),  # thermal, structural, process
        sa.Column('predicted_values', postgresql.JSONB, nullable=False),
        sa.Column('actual_values', postgresql.JSONB),
        sa.Column('uncertainty', postgresql.JSONB),
        sa.Column('physics_residual', sa.Float),
        sa.Column('drift_score', sa.Float),
        sa.Column('model_version', sa.String(20)),
    )
    op.create_index('ix_twin_states_ts', 'digital_twin_states', ['equipment_id', 'timestamp'])

    op.create_table(
        'pinn_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('model_type', sa.String(50), nullable=False),  # thermal, structural
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('architecture', postgresql.JSONB),
        sa.Column('hyperparameters', postgresql.JSONB),
        sa.Column('training_metrics', postgresql.JSONB),
        sa.Column('validation_metrics', postgresql.JSONB),
        sa.Column('model_path', sa.String(500)),
        sa.Column('is_active', sa.Boolean, default=False),
        sa.Column('trained_at', sa.DateTime(timezone=True)),
        sa.Column('deployed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_pinn_models_type', 'pinn_models', ['model_type', 'is_active'])

    # ==========================================================================
    # AI/ML Tables
    # ==========================================================================

    op.create_table(
        'ai_predictions',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pinn_models.id')),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('equipment.id')),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('prediction_type', sa.String(50), nullable=False),
        sa.Column('prediction', postgresql.JSONB, nullable=False),
        sa.Column('confidence', sa.Float),
        sa.Column('uncertainty_lower', sa.Float),
        sa.Column('uncertainty_upper', sa.Float),
        sa.Column('actual_outcome', postgresql.JSONB),
        sa.Column('was_correct', sa.Boolean),
        sa.Column('trace_id', sa.String(32)),
    )
    op.create_index('ix_ai_predictions_ts', 'ai_predictions', ['timestamp'])
    op.create_index('ix_ai_predictions_trace', 'ai_predictions', ['trace_id'])

    op.create_table(
        'guardrail_events',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('guardrail_type', sa.String(50), nullable=False),
        sa.Column('triggered', sa.Boolean, nullable=False),
        sa.Column('input_data', postgresql.JSONB),
        sa.Column('output_data', postgresql.JSONB),
        sa.Column('confidence', sa.Float),
        sa.Column('action_taken', sa.String(100)),
        sa.Column('human_override', sa.Boolean, default=False),
        sa.Column('override_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('trace_id', sa.String(32)),
    )
    op.create_index('ix_guardrail_events_ts', 'guardrail_events', ['timestamp'])

    # ==========================================================================
    # Quality Control Tables
    # ==========================================================================

    op.create_table(
        'quality_inspections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('manufacturing_jobs.id')),
        sa.Column('inspection_type', sa.String(50), nullable=False),
        sa.Column('inspector', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('result', sa.String(20), nullable=False),  # pass, fail, rework
        sa.Column('measurements', postgresql.JSONB),
        sa.Column('defects', postgresql.JSONB),
        sa.Column('images', postgresql.ARRAY(sa.String)),
        sa.Column('notes', sa.Text),
    )
    op.create_index('ix_quality_inspections_job', 'quality_inspections', ['job_id'])

    # ==========================================================================
    # Audit Trail Tables
    # ==========================================================================

    op.create_table(
        'audit_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('actor_spiffe', sa.String(255)),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=False),
        sa.Column('resource_id', sa.String(100)),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('details', postgresql.JSONB),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('trace_id', sa.String(32)),
        sa.Column('span_id', sa.String(16)),
        sa.Column('previous_hash', sa.String(64)),
        sa.Column('entry_hash', sa.String(64), nullable=False),
        sa.Column('signature', sa.LargeBinary),
    )
    op.create_index('ix_audit_timestamp', 'audit_entries', ['timestamp'])
    op.create_index('ix_audit_actor', 'audit_entries', ['actor_id'])
    op.create_index('ix_audit_resource', 'audit_entries', ['resource_type', 'resource_id'])
    op.create_index('ix_audit_trace', 'audit_entries', ['trace_id'])

    op.create_table(
        'audit_seals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('seal_date', sa.Date, nullable=False),
        sa.Column('first_entry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('audit_entries.id')),
        sa.Column('last_entry_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('audit_entries.id')),
        sa.Column('entry_count', sa.Integer, nullable=False),
        sa.Column('chain_hash', sa.String(64), nullable=False),
        sa.Column('hsm_signature', sa.LargeBinary, nullable=False),
        sa.Column('hsm_key_id', sa.String(50)),
        sa.Column('sealed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verified', sa.Boolean, default=False),
        sa.Column('verified_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_audit_seals_date', 'audit_seals', ['seal_date'])

    # ==========================================================================
    # Compliance Tables
    # ==========================================================================

    op.create_table(
        'cmmc_practices',
        sa.Column('id', sa.String(20), primary_key=True),  # e.g., AC.L2-3.1.1
        sa.Column('domain', sa.String(50), nullable=False),
        sa.Column('level', sa.Integer, nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('status', sa.String(20), default='not_implemented'),
        sa.Column('evidence', postgresql.JSONB),
        sa.Column('last_assessed', sa.DateTime(timezone=True)),
        sa.Column('next_assessment', sa.DateTime(timezone=True)),
        sa.Column('owner', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
    )

    op.create_table(
        'compliance_assessments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('practice_id', sa.String(20), sa.ForeignKey('cmmc_practices.id'), nullable=False),
        sa.Column('assessor', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('result', sa.String(20), nullable=False),  # met, not_met, partial
        sa.Column('findings', sa.Text),
        sa.Column('evidence_refs', postgresql.ARRAY(sa.String)),
        sa.Column('corrective_actions', postgresql.JSONB),
    )

    # ==========================================================================
    # Command Center Tables (V8)
    # ==========================================================================

    op.create_table(
        'actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', sa.String(100)),
        sa.Column('parameters', postgresql.JSONB),
        sa.Column('priority', sa.Integer, default=5),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('source', sa.String(50)),  # ai, manual, automation
        sa.Column('confidence', sa.Float),
        sa.Column('requires_approval', sa.Boolean, default=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('approved_at', sa.DateTime(timezone=True)),
        sa.Column('executed_at', sa.DateTime(timezone=True)),
        sa.Column('result', postgresql.JSONB),
        sa.Column('trace_id', sa.String(32)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_actions_status', 'actions', ['status'])
    op.create_index('ix_actions_created', 'actions', ['created_at'])

    op.create_table(
        'cosim_scenarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('scenario_type', sa.String(50), nullable=False),
        sa.Column('parameters', postgresql.JSONB),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('results', postgresql.JSONB),
        sa.Column('confidence', sa.Float),
        sa.Column('monte_carlo_iterations', sa.Integer),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_cosim_scenarios_status', 'cosim_scenarios', ['status'])


def downgrade() -> None:
    """Drop all v8.0 tables."""

    # Drop in reverse order due to foreign keys
    op.drop_table('cosim_scenarios')
    op.drop_table('actions')
    op.drop_table('compliance_assessments')
    op.drop_table('cmmc_practices')
    op.drop_table('audit_seals')
    op.drop_table('audit_entries')
    op.drop_table('quality_inspections')
    op.drop_table('guardrail_events')
    op.drop_table('ai_predictions')
    op.drop_table('pinn_models')
    op.drop_table('digital_twin_states')
    op.drop_table('manufacturing_jobs')
    op.drop_table('manufacturing_orders')
    op.drop_table('equipment_metrics')
    op.drop_table('equipment')
    op.drop_table('api_keys')
    op.drop_table('users')
