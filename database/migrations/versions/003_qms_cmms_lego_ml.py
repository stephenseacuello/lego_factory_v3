"""QMS, CMMS, LEGO, ML tables

Revision ID: 003_qms_cmms
Revises: 002_erp_qms
Create Date: 2024-01-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_qms_cmms'
down_revision = '002_erp_qms'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # QMS - Documents
    # ==========================================================================
    op.create_table('document_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['document_categories.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    op.create_table('documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('document_id', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('document_type', sa.String(50), nullable=True),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('current_version', sa.String(20), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('review_date', sa.Date(), nullable=True),
        sa.Column('owner', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['document_categories.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id')
    )

    op.create_table('document_revisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('document_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('revision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('file_path', sa.String(1000), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['revision_id'], ['document_revisions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('document_approvals',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('revision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('approver', sa.String(100), nullable=False),
        sa.Column('role', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['revision_id'], ['document_revisions.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('e_signatures',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('signer', sa.String(100), nullable=False),
        sa.Column('meaning', sa.String(100), nullable=False),
        sa.Column('signed_at', sa.DateTime(), nullable=False),
        sa.Column('signature_hash', sa.String(256), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # QMS - NCR/CAPA
    # ==========================================================================
    op.create_table('ncrs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('ncr_number', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ncr_type', sa.String(50), nullable=True),
        sa.Column('severity', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('lot_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity_affected', sa.Float(), nullable=True),
        sa.Column('disposition', sa.String(50), nullable=True),
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.ForeignKeyConstraint(['lot_id'], ['lots.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ncr_number')
    )

    op.create_table('capas',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('capa_number', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('capa_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('ncr_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('root_cause_analysis', sa.Text(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('owner', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['ncr_id'], ['ncrs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('capa_number')
    )

    op.create_table('capa_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('capa_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=True),
        sa.Column('owner', sa.String(100), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['capa_id'], ['capas.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # QMS - Quality (Audits, Training, Calibration, SPC)
    # ==========================================================================
    op.create_table('audits',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('audit_number', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('audit_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('scheduled_date', sa.Date(), nullable=True),
        sa.Column('completed_date', sa.Date(), nullable=True),
        sa.Column('lead_auditor', sa.String(100), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('audit_number')
    )

    op.create_table('audit_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('finding_number', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('capa_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['audit_id'], ['audits.id']),
        sa.ForeignKeyConstraint(['capa_id'], ['capas.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('training_courses',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('course_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration_hours', sa.Float(), nullable=True),
        sa.Column('validity_months', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('course_code')
    )

    op.create_table('training_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('worker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('course_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('completion_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('trainer', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id']),
        sa.ForeignKeyConstraint(['course_id'], ['training_courses.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('calibrated_equipment',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('equipment_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('serial_number', sa.String(100), nullable=True),
        sa.Column('manufacturer', sa.String(200), nullable=True),
        sa.Column('calibration_interval_days', sa.Integer(), nullable=True),
        sa.Column('last_calibration_date', sa.Date(), nullable=True),
        sa.Column('next_calibration_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('equipment_id')
    )

    op.create_table('calibration_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('calibration_date', sa.Date(), nullable=False),
        sa.Column('next_due_date', sa.Date(), nullable=True),
        sa.Column('result', sa.String(50), nullable=True),
        sa.Column('performed_by', sa.String(100), nullable=True),
        sa.Column('certificate_number', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['equipment_id'], ['calibrated_equipment.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('spc_charts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('chart_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('chart_type', sa.String(50), nullable=True),
        sa.Column('characteristic', sa.String(200), nullable=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ucl', sa.Float(), nullable=True),
        sa.Column('lcl', sa.Float(), nullable=True),
        sa.Column('target', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chart_id')
    )

    op.create_table('spc_data',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('chart_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('sample_size', sa.Integer(), nullable=True),
        sa.Column('out_of_control', sa.Boolean(), default=False),
        sa.ForeignKeyConstraint(['chart_id'], ['spc_charts.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # QMS - Supplier Quality
    # ==========================================================================
    op.create_table('supplier_quality_ratings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('vendor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rating_period', sa.String(20), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('total_lots_received', sa.Integer(), default=0),
        sa.Column('lots_rejected', sa.Integer(), default=0),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('grade', sa.String(10), nullable=True),
        sa.ForeignKeyConstraint(['vendor_id'], ['partners.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('inspection_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('plan_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('inspection_type', sa.String(50), nullable=True),
        sa.Column('sampling_type', sa.String(50), nullable=True),
        sa.Column('sample_size', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plan_id')
    )

    op.create_table('inspection_characteristics',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('characteristic_type', sa.String(50), nullable=True),
        sa.Column('nominal_value', sa.Float(), nullable=True),
        sa.Column('tolerance_plus', sa.Float(), nullable=True),
        sa.Column('tolerance_minus', sa.Float(), nullable=True),
        sa.Column('is_critical', sa.Boolean(), default=False),
        sa.ForeignKeyConstraint(['plan_id'], ['inspection_plans.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('inspection_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('record_id', sa.String(50), nullable=False),
        sa.Column('inspection_type', sa.String(50), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('lot_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('disposition', sa.String(50), nullable=True),
        sa.Column('inspection_date', sa.DateTime(), nullable=False),
        sa.Column('inspector_id', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['inspection_plans.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.ForeignKeyConstraint(['lot_id'], ['lots.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('record_id')
    )

    op.create_table('inspection_measurements',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('characteristic_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('measured_value', sa.Float(), nullable=True),
        sa.Column('is_conforming', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['record_id'], ['inspection_records.id']),
        sa.ForeignKeyConstraint(['characteristic_id'], ['inspection_characteristics.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # CMMS - Assets
    # ==========================================================================
    op.create_table('asset_classes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('class_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('class_code')
    )

    op.create_table('assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('asset_number', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('asset_class_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('criticality', sa.String(50), nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('serial_number', sa.String(100), nullable=True),
        sa.Column('manufacturer', sa.String(200), nullable=True),
        sa.Column('install_date', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['asset_class_id'], ['asset_classes.id']),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('asset_number')
    )

    op.create_table('meters',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('meter_type', sa.String(50), nullable=True),
        sa.Column('unit_of_measure', sa.String(50), nullable=True),
        sa.Column('current_reading', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('meter_readings',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('meter_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reading_date', sa.DateTime(), nullable=False),
        sa.Column('reading_value', sa.Float(), nullable=False),
        sa.Column('recorded_by', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['meter_id'], ['meters.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('spares',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('spare_number', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity_on_hand', sa.Float(), default=0),
        sa.Column('reorder_point', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('spare_number')
    )

    op.create_table('asset_spares',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('spare_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity_per_asset', sa.Float(), default=1),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
        sa.ForeignKeyConstraint(['spare_id'], ['spares.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # CMMS - Maintenance
    # ==========================================================================
    op.create_table('task_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('task_code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('estimated_hours', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_code')
    )

    op.create_table('pm_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('schedule_id', sa.String(50), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_type', sa.String(50), nullable=True),
        sa.Column('frequency_days', sa.Integer(), nullable=True),
        sa.Column('meter_interval', sa.Float(), nullable=True),
        sa.Column('last_completed', sa.Date(), nullable=True),
        sa.Column('next_due', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('schedule_id')
    )

    op.create_table('maintenance_work_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('work_order_number', sa.String(50), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pm_schedule_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('work_type', sa.String(50), nullable=True),
        sa.Column('priority', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('scheduled_start', sa.DateTime(), nullable=True),
        sa.Column('scheduled_end', sa.DateTime(), nullable=True),
        sa.Column('actual_start', sa.DateTime(), nullable=True),
        sa.Column('actual_end', sa.DateTime(), nullable=True),
        sa.Column('assigned_to', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
        sa.ForeignKeyConstraint(['pm_schedule_id'], ['pm_schedules.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('work_order_number')
    )

    op.create_table('work_order_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('work_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['work_order_id'], ['maintenance_work_orders.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('work_order_labor',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('work_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('worker_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('hours_worked', sa.Float(), nullable=False),
        sa.Column('hourly_rate', sa.Float(), nullable=True),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(['work_order_id'], ['maintenance_work_orders.id']),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('work_order_materials',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('work_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('spare_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity_used', sa.Float(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['work_order_id'], ['maintenance_work_orders.id']),
        sa.ForeignKeyConstraint(['spare_id'], ['spares.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # CMMS - Failure Analysis
    # ==========================================================================
    op.create_table('failure_codes',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('failure_type', sa.String(50), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )

    op.create_table('failure_analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('analysis_id', sa.String(50), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('failure_code_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('failure_datetime', sa.DateTime(), nullable=False),
        sa.Column('severity', sa.String(50), nullable=True),
        sa.Column('downtime_hours', sa.Float(), nullable=True),
        sa.Column('root_cause', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
        sa.ForeignKeyConstraint(['failure_code_id'], ['failure_codes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('analysis_id')
    )

    op.create_table('failure_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('total_failures', sa.Integer(), default=0),
        sa.Column('total_downtime_hours', sa.Float(), default=0),
        sa.Column('mean_time_between_failures', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # LEGO Tables
    # ==========================================================================
    op.create_table('brick_colors',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('color_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('hex_code', sa.String(7), nullable=False),
        sa.Column('ldraw_id', sa.Integer(), nullable=True),
        sa.Column('is_transparent', sa.Boolean(), default=False),
        sa.Column('is_current', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('color_id')
    )

    op.create_table('brick_designs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('design_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('brick_type', sa.String(50), nullable=True),
        sa.Column('studs_x', sa.Integer(), nullable=False),
        sa.Column('studs_y', sa.Integer(), nullable=False),
        sa.Column('height_units', sa.Integer(), default=1),
        sa.Column('color_name', sa.String(50), nullable=True),
        sa.Column('color_hex', sa.String(7), nullable=True),
        sa.Column('width_mm', sa.Float(), nullable=True),
        sa.Column('depth_mm', sa.Float(), nullable=True),
        sa.Column('height_mm', sa.Float(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), default=False),
        sa.Column('is_public', sa.Boolean(), default=False),
        sa.Column('owner_id', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('design_id')
    )

    op.create_table('brick_export_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('job_id', sa.String(50), nullable=False),
        sa.Column('design_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('export_format', sa.String(20), nullable=False),
        sa.Column('printer_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('progress', sa.Float(), default=0),
        sa.Column('output_file', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['design_id'], ['brick_designs.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id')
    )

    op.create_table('brick_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('part_number', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('studs_x', sa.Integer(), nullable=True),
        sa.Column('studs_y', sa.Integer(), nullable=True),
        sa.Column('height_plates', sa.Integer(), nullable=True),
        sa.Column('brick_type', sa.String(50), nullable=True),
        sa.Column('is_printable', sa.Boolean(), default=True),
        sa.Column('is_current', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('part_number')
    )

    op.create_table('print_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('profile_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('printer_type', sa.String(100), nullable=False),
        sa.Column('filament_type', sa.String(50), nullable=True),
        sa.Column('layer_height', sa.Float(), nullable=False),
        sa.Column('infill_percent', sa.Integer(), default=20),
        sa.Column('print_speed', sa.Float(), nullable=True),
        sa.Column('nozzle_temp', sa.Integer(), nullable=True),
        sa.Column('bed_temp', sa.Integer(), nullable=True),
        sa.Column('is_lego_optimized', sa.Boolean(), default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_id')
    )

    op.create_table('filament_inventory',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('spool_id', sa.String(50), nullable=False),
        sa.Column('filament_type', sa.String(50), nullable=False),
        sa.Column('material_name', sa.String(200), nullable=False),
        sa.Column('brand', sa.String(100), nullable=True),
        sa.Column('color_name', sa.String(100), nullable=True),
        sa.Column('current_weight_grams', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('spool_id')
    )

    op.create_table('print_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('job_id', sa.String(50), nullable=False),
        sa.Column('design_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('profile_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('filament_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('printer_name', sa.String(200), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('print_duration_mins', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['design_id'], ['brick_designs.id']),
        sa.ForeignKeyConstraint(['profile_id'], ['print_profiles.id']),
        sa.ForeignKeyConstraint(['filament_id'], ['filament_inventory.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id')
    )

    # ==========================================================================
    # ML Tables
    # ==========================================================================
    op.create_table('ml_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('model_type', sa.String(50), nullable=True),
        sa.Column('version', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('model_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_id')
    )

    op.create_table('ml_training_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('run_id', sa.String(100), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('epochs', sa.Integer(), nullable=True),
        sa.Column('final_loss', sa.Float(), nullable=True),
        sa.Column('hyperparameters', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id')
    )

    op.create_table('ml_inference_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('job_id', sa.String(100), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('input_data', postgresql.JSON(), nullable=True),
        sa.Column('output_data', postgresql.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id')
    )

    op.create_table('ml_predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('inference_job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('prediction', postgresql.JSON(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['inference_job_id'], ['ml_inference_jobs.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('gcode_fingerprints',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('fingerprint_id', sa.String(100), nullable=False),
        sa.Column('gcode_hash', sa.String(64), nullable=True),
        sa.Column('embedding', postgresql.ARRAY(sa.Float()), nullable=True),
        sa.Column('metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fingerprint_id')
    )

    op.create_table('tool_wear_predictions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('machine_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tool_id', sa.String(100), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('wear_level', sa.Float(), nullable=True),
        sa.Column('remaining_useful_life_hours', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['machine_id'], ['machines.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ==========================================================================
    # ERP - Planning (additional tables)
    # ==========================================================================
    op.create_table('cost_centers',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('cost_center_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('manager', sa.String(200), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cost_center_id')
    )

    op.create_table('budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('budget_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('cost_center_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('original_amount', sa.Float(), nullable=False),
        sa.Column('actual_amount', sa.Float(), default=0),
        sa.Column('status', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['cost_center_id'], ['cost_centers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('budget_id')
    )

    op.create_table('demand_forecasts',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('forecast_id', sa.String(50), nullable=False),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('forecast_date', sa.Date(), nullable=False),
        sa.Column('forecast_qty', sa.Float(), nullable=False),
        sa.Column('forecast_method', sa.String(50), nullable=True),
        sa.Column('confidence_level', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('forecast_id')
    )

    op.create_table('mrp_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('run_id', sa.String(50), nullable=False),
        sa.Column('run_datetime', sa.DateTime(), nullable=False),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('items_processed', sa.Integer(), nullable=True),
        sa.Column('planned_orders_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id')
    )

    op.create_table('planned_orders',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('order_id', sa.String(50), nullable=False),
        sa.Column('mrp_run_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('order_type', sa.String(50), nullable=False),
        sa.Column('order_qty', sa.Float(), nullable=False),
        sa.Column('required_date', sa.Date(), nullable=False),
        sa.Column('order_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(['mrp_run_id'], ['mrp_runs.id']),
        sa.ForeignKeyConstraint(['item_id'], ['items.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id')
    )


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table('planned_orders')
    op.drop_table('mrp_runs')
    op.drop_table('demand_forecasts')
    op.drop_table('budgets')
    op.drop_table('cost_centers')
    op.drop_table('tool_wear_predictions')
    op.drop_table('gcode_fingerprints')
    op.drop_table('ml_predictions')
    op.drop_table('ml_inference_jobs')
    op.drop_table('ml_training_runs')
    op.drop_table('ml_models')
    op.drop_table('print_jobs')
    op.drop_table('filament_inventory')
    op.drop_table('print_profiles')
    op.drop_table('brick_templates')
    op.drop_table('brick_export_jobs')
    op.drop_table('brick_designs')
    op.drop_table('brick_colors')
    op.drop_table('failure_history')
    op.drop_table('failure_analyses')
    op.drop_table('failure_codes')
    op.drop_table('work_order_materials')
    op.drop_table('work_order_labor')
    op.drop_table('work_order_tasks')
    op.drop_table('maintenance_work_orders')
    op.drop_table('pm_schedules')
    op.drop_table('task_templates')
    op.drop_table('asset_spares')
    op.drop_table('spares')
    op.drop_table('meter_readings')
    op.drop_table('meters')
    op.drop_table('assets')
    op.drop_table('asset_classes')
    op.drop_table('inspection_measurements')
    op.drop_table('inspection_records')
    op.drop_table('inspection_characteristics')
    op.drop_table('inspection_plans')
    op.drop_table('supplier_quality_ratings')
    op.drop_table('spc_data')
    op.drop_table('spc_charts')
    op.drop_table('calibration_records')
    op.drop_table('calibrated_equipment')
    op.drop_table('training_records')
    op.drop_table('training_courses')
    op.drop_table('audit_findings')
    op.drop_table('audits')
    op.drop_table('capa_actions')
    op.drop_table('capas')
    op.drop_table('ncrs')
    op.drop_table('e_signatures')
    op.drop_table('document_approvals')
    op.drop_table('document_files')
    op.drop_table('document_revisions')
    op.drop_table('documents')
    op.drop_table('document_categories')
