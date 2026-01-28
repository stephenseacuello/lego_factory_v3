"""Initial schema with 122 tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute('CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ==========================================================================
    # SCADA Tables
    # ==========================================================================

    op.create_table('machines',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('machine_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('machine_type', sa.String(50), nullable=True),
        sa.Column('controller_type', sa.String(50), nullable=True),
        sa.Column('connection_type', sa.String(50), nullable=True),
        sa.Column('host', sa.String(200), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('serial_port', sa.String(100), nullable=True),
        sa.Column('baud_rate', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('machine_id')
    )
    op.create_index('ix_machines_machine_id', 'machines', ['machine_id'])

    op.create_table('machine_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', postgresql.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('tag_groups',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('tags',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('tag_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('data_type', sa.String(50), nullable=False),
        sa.Column('engineering_units', sa.String(50), nullable=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.ForeignKeyConstraint(['group_id'], ['tag_groups.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tag_id')
    )

    # TimescaleDB hypertable for tag values
    op.create_table('tag_values',
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('string_value', sa.String(500), nullable=True),
        sa.Column('quality', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id']),
        sa.PrimaryKeyConstraint('tag_id', 'timestamp')
    )
    op.execute("SELECT create_hypertable('tag_values', 'timestamp', if_not_exists => TRUE)")

    op.create_table('alarm_groups',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('alarm_definitions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('alarm_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(20), nullable=False),
        sa.Column('alarm_class', sa.String(50), nullable=True),
        sa.Column('tag_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('condition_type', sa.String(50), nullable=True),
        sa.Column('setpoint', sa.Float(), nullable=True),
        sa.Column('deadband', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id']),
        sa.ForeignKeyConstraint(['group_id'], ['alarm_groups.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alarm_id')
    )

    op.create_table('alarm_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('alarm_def_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('acknowledged', sa.Boolean(), default=False),
        sa.Column('acknowledged_by', sa.String(100), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['alarm_def_id'], ['alarm_definitions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('alarm_shelve_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('alarm_def_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('shelved_at', sa.DateTime(), nullable=False),
        sa.Column('shelved_by', sa.String(100), nullable=True),
        sa.Column('unshelved_at', sa.DateTime(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['alarm_def_id'], ['alarm_definitions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('master_recipes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('recipe_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('recipe_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('product_id', sa.String(100), nullable=True),
        sa.Column('gcode_content', sa.Text(), nullable=True),
        sa.Column('parameters', postgresql.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recipe_id', 'version')
    )

    op.create_table('control_recipes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('master_recipe_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('work_order_id', sa.String(100), nullable=True),
        sa.Column('parameters', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['master_recipe_id'], ['master_recipes.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('recipe_approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('recipe_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('approver', sa.String(100), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['master_recipes.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('recipe_parameters',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('recipe_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('value', sa.String(500), nullable=True),
        sa.Column('data_type', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['master_recipes.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # MES Tables
    # ==========================================================================

    op.create_table('workers',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('employee_id', sa.String(50), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(200), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('role', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('hire_date', sa.Date(), nullable=True),
        sa.Column('hourly_rate', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id')
    )

    op.create_table('skills',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('skill_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('requires_certification', sa.Boolean(), default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('skill_code')
    )

    op.create_table('worker_skills',
        sa.Column('worker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('skill_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('level', sa.String(50), nullable=True),
        sa.Column('certified_date', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id']),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
        sa.PrimaryKeyConstraint('worker_id', 'skill_id')
    )

    op.create_table('work_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('work_order_id', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('product_id', sa.String(100), nullable=True),
        sa.Column('quantity_ordered', sa.Float(), nullable=False),
        sa.Column('quantity_completed', sa.Float(), default=0),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('recipe_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['recipe_id'], ['master_recipes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('work_order_id')
    )

    op.create_table('operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('work_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('operation_type', sa.String(50), nullable=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('planned_duration_mins', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id']),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('job_id', sa.String(50), nullable=False),
        sa.Column('operation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('quantity_produced', sa.Float(), default=0),
        sa.ForeignKeyConstraint(['operation_id'], ['operations.id']),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id')
    )

    op.create_table('time_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('worker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('clock_in', sa.DateTime(), nullable=False),
        sa.Column('clock_out', sa.DateTime(), nullable=True),
        sa.Column('break_minutes', sa.Integer(), default=0),
        sa.Column('entry_type', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id']),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('downtime_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('reason', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('production_counts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('good_count', sa.Integer(), default=0),
        sa.Column('reject_count', sa.Integer(), default=0),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('oee_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('availability', sa.Float(), nullable=True),
        sa.Column('performance', sa.Float(), nullable=True),
        sa.Column('quality', sa.Float(), nullable=True),
        sa.Column('oee', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # MES Scheduling Tables
    op.create_table('shifts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('shift_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('shift_type', sa.String(50), nullable=True),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('shift_code')
    )

    op.create_table('shift_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('worker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('shift_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id']),
        sa.ForeignKeyConstraint(['shift_id'], ['shifts.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('dispatch_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('work_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('priority', sa.String(50), nullable=True),
        sa.Column('sequence_number', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('scheduled_start', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id']),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('production_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('schedule_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schedule_id')
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('production_schedules')
    op.drop_table('dispatch_queue')
    op.drop_table('shift_assignments')
    op.drop_table('shifts')
    op.drop_table('oee_records')
    op.drop_table('production_counts')
    op.drop_table('downtime_events')
    op.drop_table('time_entries')
    op.drop_table('jobs')
    op.drop_table('operations')
    op.drop_table('work_orders')
    op.drop_table('worker_skills')
    op.drop_table('skills')
    op.drop_table('workers')
    op.drop_table('recipe_parameters')
    op.drop_table('recipe_approvals')
    op.drop_table('control_recipes')
    op.drop_table('master_recipes')
    op.drop_table('alarm_shelve_log')
    op.drop_table('alarm_events')
    op.drop_table('alarm_definitions')
    op.drop_table('alarm_groups')
    op.drop_table('tag_values')
    op.drop_table('tags')
    op.drop_table('tag_groups')
    op.drop_table('machine_events')
    op.drop_table('machines')
