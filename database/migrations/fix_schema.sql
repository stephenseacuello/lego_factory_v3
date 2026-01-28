-- LEGO Factory v3 - Comprehensive Database Schema Fix
-- =====================================================
-- This script adds ALL missing columns to existing tables.
-- Run this in the Docker PostgreSQL container.
-- Safe to run multiple times (idempotent).

-- ============================================
-- Fix work_orders table
-- ============================================
DO $$
BEGIN
    -- Base model columns (UUIDMixin + TimestampMixin)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'id') THEN
        ALTER TABLE work_orders ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'created_at') THEN
        ALTER TABLE work_orders ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'updated_at') THEN
        ALTER TABLE work_orders ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    -- Audit columns (AuditMixin)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'created_by') THEN
        ALTER TABLE work_orders ADD COLUMN created_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'updated_by') THEN
        ALTER TABLE work_orders ADD COLUMN updated_by VARCHAR(100);
    END IF;

    -- Soft delete columns (SoftDeleteMixin)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'is_deleted') THEN
        ALTER TABLE work_orders ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'deleted_at') THEN
        ALTER TABLE work_orders ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'deleted_by') THEN
        ALTER TABLE work_orders ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    -- Work order specific columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'work_order_id') THEN
        ALTER TABLE work_orders ADD COLUMN work_order_id VARCHAR(50) UNIQUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'description') THEN
        ALTER TABLE work_orders ADD COLUMN description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'product_id') THEN
        ALTER TABLE work_orders ADD COLUMN product_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'recipe_id') THEN
        ALTER TABLE work_orders ADD COLUMN recipe_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'quantity_ordered') THEN
        ALTER TABLE work_orders ADD COLUMN quantity_ordered INTEGER DEFAULT 1;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'quantity_completed') THEN
        ALTER TABLE work_orders ADD COLUMN quantity_completed INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'status') THEN
        ALTER TABLE work_orders ADD COLUMN status VARCHAR(20) DEFAULT 'draft';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'priority') THEN
        ALTER TABLE work_orders ADD COLUMN priority INTEGER DEFAULT 5;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'planned_start') THEN
        ALTER TABLE work_orders ADD COLUMN planned_start TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'planned_end') THEN
        ALTER TABLE work_orders ADD COLUMN planned_end TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'actual_start') THEN
        ALTER TABLE work_orders ADD COLUMN actual_start TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'actual_end') THEN
        ALTER TABLE work_orders ADD COLUMN actual_end TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'due_date') THEN
        ALTER TABLE work_orders ADD COLUMN due_date TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'customer_id') THEN
        ALTER TABLE work_orders ADD COLUMN customer_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'sales_order_id') THEN
        ALTER TABLE work_orders ADD COLUMN sales_order_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'notes') THEN
        ALTER TABLE work_orders ADD COLUMN notes TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'work_orders' AND column_name = 'extra_data') THEN
        ALTER TABLE work_orders ADD COLUMN extra_data JSONB DEFAULT '{}';
    END IF;
END $$;

-- ============================================
-- Fix operations table
-- ============================================
DO $$
BEGIN
    -- Base columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'id') THEN
        ALTER TABLE operations ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'created_at') THEN
        ALTER TABLE operations ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'updated_at') THEN
        ALTER TABLE operations ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    -- Soft delete columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'is_deleted') THEN
        ALTER TABLE operations ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'deleted_at') THEN
        ALTER TABLE operations ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'deleted_by') THEN
        ALTER TABLE operations ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    -- Operation specific columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'work_order_id') THEN
        ALTER TABLE operations ADD COLUMN work_order_id UUID REFERENCES work_orders(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'operation_id') THEN
        ALTER TABLE operations ADD COLUMN operation_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'sequence') THEN
        ALTER TABLE operations ADD COLUMN sequence INTEGER DEFAULT 10;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'operation_type') THEN
        ALTER TABLE operations ADD COLUMN operation_type VARCHAR(30);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'name') THEN
        ALTER TABLE operations ADD COLUMN name VARCHAR(200);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'description') THEN
        ALTER TABLE operations ADD COLUMN description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'work_center_id') THEN
        ALTER TABLE operations ADD COLUMN work_center_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'machine_id') THEN
        ALTER TABLE operations ADD COLUMN machine_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'setup_time') THEN
        ALTER TABLE operations ADD COLUMN setup_time FLOAT DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'run_time') THEN
        ALTER TABLE operations ADD COLUMN run_time FLOAT DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'teardown_time') THEN
        ALTER TABLE operations ADD COLUMN teardown_time FLOAT DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'actual_setup_time') THEN
        ALTER TABLE operations ADD COLUMN actual_setup_time FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'actual_run_time') THEN
        ALTER TABLE operations ADD COLUMN actual_run_time FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'status') THEN
        ALTER TABLE operations ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'started_at') THEN
        ALTER TABLE operations ADD COLUMN started_at TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'completed_at') THEN
        ALTER TABLE operations ADD COLUMN completed_at TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'operations' AND column_name = 'parameters') THEN
        ALTER TABLE operations ADD COLUMN parameters JSONB DEFAULT '{}';
    END IF;
END $$;

-- ============================================
-- Fix jobs table
-- ============================================
DO $$
BEGIN
    -- Base columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'id') THEN
        ALTER TABLE jobs ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'created_at') THEN
        ALTER TABLE jobs ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'updated_at') THEN
        ALTER TABLE jobs ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    -- Audit columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'created_by') THEN
        ALTER TABLE jobs ADD COLUMN created_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'updated_by') THEN
        ALTER TABLE jobs ADD COLUMN updated_by VARCHAR(100);
    END IF;

    -- Soft delete columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'is_deleted') THEN
        ALTER TABLE jobs ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'deleted_at') THEN
        ALTER TABLE jobs ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'deleted_by') THEN
        ALTER TABLE jobs ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    -- Job specific columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'job_id') THEN
        ALTER TABLE jobs ADD COLUMN job_id VARCHAR(50) UNIQUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'work_order_id') THEN
        ALTER TABLE jobs ADD COLUMN work_order_id UUID REFERENCES work_orders(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'operation_id') THEN
        ALTER TABLE jobs ADD COLUMN operation_id UUID REFERENCES operations(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'machine_id') THEN
        ALTER TABLE jobs ADD COLUMN machine_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'scheduled_start') THEN
        ALTER TABLE jobs ADD COLUMN scheduled_start TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'scheduled_end') THEN
        ALTER TABLE jobs ADD COLUMN scheduled_end TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'actual_start') THEN
        ALTER TABLE jobs ADD COLUMN actual_start TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'actual_end') THEN
        ALTER TABLE jobs ADD COLUMN actual_end TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'status') THEN
        ALTER TABLE jobs ADD COLUMN status VARCHAR(20) DEFAULT 'pending';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'priority_score') THEN
        ALTER TABLE jobs ADD COLUMN priority_score FLOAT DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'quantity_planned') THEN
        ALTER TABLE jobs ADD COLUMN quantity_planned INTEGER DEFAULT 1;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'quantity_completed') THEN
        ALTER TABLE jobs ADD COLUMN quantity_completed INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'quantity_rejected') THEN
        ALTER TABLE jobs ADD COLUMN quantity_rejected INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'assigned_worker_id') THEN
        ALTER TABLE jobs ADD COLUMN assigned_worker_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'gcode_file') THEN
        ALTER TABLE jobs ADD COLUMN gcode_file VARCHAR(500);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'gcode_hash') THEN
        ALTER TABLE jobs ADD COLUMN gcode_hash VARCHAR(64);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'jobs' AND column_name = 'runtime_data') THEN
        ALTER TABLE jobs ADD COLUMN runtime_data JSONB DEFAULT '{}';
    END IF;
END $$;

-- ============================================
-- Fix asset_classes table
-- ============================================
DO $$
BEGIN
    -- Base columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'id') THEN
        ALTER TABLE asset_classes ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'created_at') THEN
        ALTER TABLE asset_classes ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'updated_at') THEN
        ALTER TABLE asset_classes ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'created_by') THEN
        ALTER TABLE asset_classes ADD COLUMN created_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'updated_by') THEN
        ALTER TABLE asset_classes ADD COLUMN updated_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'is_deleted') THEN
        ALTER TABLE asset_classes ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'deleted_at') THEN
        ALTER TABLE asset_classes ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'deleted_by') THEN
        ALTER TABLE asset_classes ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    -- Specific columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'code') THEN
        ALTER TABLE asset_classes ADD COLUMN code VARCHAR(50) UNIQUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'name') THEN
        ALTER TABLE asset_classes ADD COLUMN name VARCHAR(200);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'description') THEN
        ALTER TABLE asset_classes ADD COLUMN description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'parent_class_id') THEN
        ALTER TABLE asset_classes ADD COLUMN parent_class_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'default_pm_interval_days') THEN
        ALTER TABLE asset_classes ADD COLUMN default_pm_interval_days INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'default_pm_interval_hours') THEN
        ALTER TABLE asset_classes ADD COLUMN default_pm_interval_hours FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'expected_lifespan_years') THEN
        ALTER TABLE asset_classes ADD COLUMN expected_lifespan_years FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'asset_classes' AND column_name = 'spec_template') THEN
        ALTER TABLE asset_classes ADD COLUMN spec_template JSONB DEFAULT '{}';
    END IF;
END $$;

-- ============================================
-- Fix assets table
-- ============================================
DO $$
BEGIN
    -- Base columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'id') THEN
        ALTER TABLE assets ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'created_at') THEN
        ALTER TABLE assets ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'updated_at') THEN
        ALTER TABLE assets ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'created_by') THEN
        ALTER TABLE assets ADD COLUMN created_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'updated_by') THEN
        ALTER TABLE assets ADD COLUMN updated_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'is_deleted') THEN
        ALTER TABLE assets ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'deleted_at') THEN
        ALTER TABLE assets ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'deleted_by') THEN
        ALTER TABLE assets ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    -- Asset specific columns
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'asset_id') THEN
        ALTER TABLE assets ADD COLUMN asset_id VARCHAR(50) UNIQUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'name') THEN
        ALTER TABLE assets ADD COLUMN name VARCHAR(200);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'description') THEN
        ALTER TABLE assets ADD COLUMN description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'asset_class_id') THEN
        ALTER TABLE assets ADD COLUMN asset_class_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'status') THEN
        ALTER TABLE assets ADD COLUMN status VARCHAR(30) DEFAULT 'operational';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'criticality') THEN
        ALTER TABLE assets ADD COLUMN criticality VARCHAR(20) DEFAULT 'standard';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'location_id') THEN
        ALTER TABLE assets ADD COLUMN location_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'location_description') THEN
        ALTER TABLE assets ADD COLUMN location_description VARCHAR(200);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'work_center_id') THEN
        ALTER TABLE assets ADD COLUMN work_center_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'serial_number') THEN
        ALTER TABLE assets ADD COLUMN serial_number VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'model_number') THEN
        ALTER TABLE assets ADD COLUMN model_number VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'manufacturer') THEN
        ALTER TABLE assets ADD COLUMN manufacturer VARCHAR(200);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'vendor_id') THEN
        ALTER TABLE assets ADD COLUMN vendor_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'purchase_date') THEN
        ALTER TABLE assets ADD COLUMN purchase_date DATE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'installation_date') THEN
        ALTER TABLE assets ADD COLUMN installation_date DATE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'warranty_expiry') THEN
        ALTER TABLE assets ADD COLUMN warranty_expiry DATE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'expected_retirement') THEN
        ALTER TABLE assets ADD COLUMN expected_retirement DATE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'purchase_cost') THEN
        ALTER TABLE assets ADD COLUMN purchase_cost FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'replacement_cost') THEN
        ALTER TABLE assets ADD COLUMN replacement_cost FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'salvage_value') THEN
        ALTER TABLE assets ADD COLUMN salvage_value FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'machine_id') THEN
        ALTER TABLE assets ADD COLUMN machine_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'parent_asset_id') THEN
        ALTER TABLE assets ADD COLUMN parent_asset_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'specifications') THEN
        ALTER TABLE assets ADD COLUMN specifications JSONB DEFAULT '{}';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'assets' AND column_name = 'documents') THEN
        ALTER TABLE assets ADD COLUMN documents JSONB DEFAULT '[]';
    END IF;
END $$;

-- ============================================
-- Fix meters table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'id') THEN
        ALTER TABLE meters ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'created_at') THEN
        ALTER TABLE meters ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'updated_at') THEN
        ALTER TABLE meters ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'created_by') THEN
        ALTER TABLE meters ADD COLUMN created_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'updated_by') THEN
        ALTER TABLE meters ADD COLUMN updated_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'is_deleted') THEN
        ALTER TABLE meters ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'deleted_at') THEN
        ALTER TABLE meters ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'deleted_by') THEN
        ALTER TABLE meters ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'meter_id') THEN
        ALTER TABLE meters ADD COLUMN meter_id VARCHAR(50) UNIQUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'asset_id') THEN
        ALTER TABLE meters ADD COLUMN asset_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'name') THEN
        ALTER TABLE meters ADD COLUMN name VARCHAR(200);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'description') THEN
        ALTER TABLE meters ADD COLUMN description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'meter_type') THEN
        ALTER TABLE meters ADD COLUMN meter_type VARCHAR(20) DEFAULT 'continuous';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'unit_of_measure') THEN
        ALTER TABLE meters ADD COLUMN unit_of_measure VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'last_reading') THEN
        ALTER TABLE meters ADD COLUMN last_reading FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'last_reading_date') THEN
        ALTER TABLE meters ADD COLUMN last_reading_date TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'warning_threshold') THEN
        ALTER TABLE meters ADD COLUMN warning_threshold FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'critical_threshold') THEN
        ALTER TABLE meters ADD COLUMN critical_threshold FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'rollover_value') THEN
        ALTER TABLE meters ADD COLUMN rollover_value FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'meters' AND column_name = 'average_daily_usage') THEN
        ALTER TABLE meters ADD COLUMN average_daily_usage FLOAT;
    END IF;
END $$;

-- ============================================
-- Fix spares table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'id') THEN
        ALTER TABLE spares ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'created_at') THEN
        ALTER TABLE spares ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'updated_at') THEN
        ALTER TABLE spares ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'created_by') THEN
        ALTER TABLE spares ADD COLUMN created_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'updated_by') THEN
        ALTER TABLE spares ADD COLUMN updated_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'is_deleted') THEN
        ALTER TABLE spares ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'deleted_at') THEN
        ALTER TABLE spares ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'deleted_by') THEN
        ALTER TABLE spares ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'spare_id') THEN
        ALTER TABLE spares ADD COLUMN spare_id VARCHAR(50) UNIQUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'name') THEN
        ALTER TABLE spares ADD COLUMN name VARCHAR(200);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'description') THEN
        ALTER TABLE spares ADD COLUMN description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'item_id') THEN
        ALTER TABLE spares ADD COLUMN item_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'quantity_on_hand') THEN
        ALTER TABLE spares ADD COLUMN quantity_on_hand INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'reorder_point') THEN
        ALTER TABLE spares ADD COLUMN reorder_point INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'reorder_quantity') THEN
        ALTER TABLE spares ADD COLUMN reorder_quantity INTEGER DEFAULT 1;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'unit_cost') THEN
        ALTER TABLE spares ADD COLUMN unit_cost FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'vendor_id') THEN
        ALTER TABLE spares ADD COLUMN vendor_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'vendor_part_number') THEN
        ALTER TABLE spares ADD COLUMN vendor_part_number VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'lead_time_days') THEN
        ALTER TABLE spares ADD COLUMN lead_time_days INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'spares' AND column_name = 'bin_location') THEN
        ALTER TABLE spares ADD COLUMN bin_location VARCHAR(100);
    END IF;
END $$;

-- ============================================
-- Fix task_templates table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'id') THEN
        ALTER TABLE task_templates ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'created_at') THEN
        ALTER TABLE task_templates ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'updated_at') THEN
        ALTER TABLE task_templates ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'created_by') THEN
        ALTER TABLE task_templates ADD COLUMN created_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'updated_by') THEN
        ALTER TABLE task_templates ADD COLUMN updated_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'is_deleted') THEN
        ALTER TABLE task_templates ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'deleted_at') THEN
        ALTER TABLE task_templates ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'deleted_by') THEN
        ALTER TABLE task_templates ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'template_id') THEN
        ALTER TABLE task_templates ADD COLUMN template_id VARCHAR(50) UNIQUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'name') THEN
        ALTER TABLE task_templates ADD COLUMN name VARCHAR(200);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'description') THEN
        ALTER TABLE task_templates ADD COLUMN description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'instructions') THEN
        ALTER TABLE task_templates ADD COLUMN instructions TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'estimated_hours') THEN
        ALTER TABLE task_templates ADD COLUMN estimated_hours FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'skill_required') THEN
        ALTER TABLE task_templates ADD COLUMN skill_required VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'safety_requirements') THEN
        ALTER TABLE task_templates ADD COLUMN safety_requirements JSONB DEFAULT '[]';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'lockout_required') THEN
        ALTER TABLE task_templates ADD COLUMN lockout_required BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'tools_required') THEN
        ALTER TABLE task_templates ADD COLUMN tools_required JSONB DEFAULT '[]';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'task_templates' AND column_name = 'materials_required') THEN
        ALTER TABLE task_templates ADD COLUMN materials_required JSONB DEFAULT '[]';
    END IF;
END $$;

-- ============================================
-- Fix pm_schedules table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'id') THEN
        ALTER TABLE pm_schedules ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'created_at') THEN
        ALTER TABLE pm_schedules ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'updated_at') THEN
        ALTER TABLE pm_schedules ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'created_by') THEN
        ALTER TABLE pm_schedules ADD COLUMN created_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'updated_by') THEN
        ALTER TABLE pm_schedules ADD COLUMN updated_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'is_deleted') THEN
        ALTER TABLE pm_schedules ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'deleted_at') THEN
        ALTER TABLE pm_schedules ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'deleted_by') THEN
        ALTER TABLE pm_schedules ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'pm_id') THEN
        ALTER TABLE pm_schedules ADD COLUMN pm_id VARCHAR(50) UNIQUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'name') THEN
        ALTER TABLE pm_schedules ADD COLUMN name VARCHAR(200);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'description') THEN
        ALTER TABLE pm_schedules ADD COLUMN description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'asset_id') THEN
        ALTER TABLE pm_schedules ADD COLUMN asset_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'asset_class_id') THEN
        ALTER TABLE pm_schedules ADD COLUMN asset_class_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'is_active') THEN
        ALTER TABLE pm_schedules ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'trigger_type') THEN
        ALTER TABLE pm_schedules ADD COLUMN trigger_type VARCHAR(20) DEFAULT 'calendar';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'frequency_days') THEN
        ALTER TABLE pm_schedules ADD COLUMN frequency_days INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'day_of_week') THEN
        ALTER TABLE pm_schedules ADD COLUMN day_of_week INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'day_of_month') THEN
        ALTER TABLE pm_schedules ADD COLUMN day_of_month INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'month_of_year') THEN
        ALTER TABLE pm_schedules ADD COLUMN month_of_year INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'meter_id') THEN
        ALTER TABLE pm_schedules ADD COLUMN meter_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'meter_interval') THEN
        ALTER TABLE pm_schedules ADD COLUMN meter_interval FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'condition_tag_id') THEN
        ALTER TABLE pm_schedules ADD COLUMN condition_tag_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'condition_threshold') THEN
        ALTER TABLE pm_schedules ADD COLUMN condition_threshold FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'lead_time_days') THEN
        ALTER TABLE pm_schedules ADD COLUMN lead_time_days INTEGER DEFAULT 7;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'work_window_days') THEN
        ALTER TABLE pm_schedules ADD COLUMN work_window_days INTEGER DEFAULT 7;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'last_completed') THEN
        ALTER TABLE pm_schedules ADD COLUMN last_completed TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'last_meter_reading') THEN
        ALTER TABLE pm_schedules ADD COLUMN last_meter_reading FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'next_due_date') THEN
        ALTER TABLE pm_schedules ADD COLUMN next_due_date DATE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'next_due_meter') THEN
        ALTER TABLE pm_schedules ADD COLUMN next_due_meter FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'priority') THEN
        ALTER TABLE pm_schedules ADD COLUMN priority VARCHAR(20) DEFAULT 'medium';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'estimated_hours') THEN
        ALTER TABLE pm_schedules ADD COLUMN estimated_hours FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'estimated_cost') THEN
        ALTER TABLE pm_schedules ADD COLUMN estimated_cost FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'work_center_id') THEN
        ALTER TABLE pm_schedules ADD COLUMN work_center_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'task_template_id') THEN
        ALTER TABLE pm_schedules ADD COLUMN task_template_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'instructions') THEN
        ALTER TABLE pm_schedules ADD COLUMN instructions TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'checklist') THEN
        ALTER TABLE pm_schedules ADD COLUMN checklist JSONB DEFAULT '[]';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'pm_schedules' AND column_name = 'spares_required') THEN
        ALTER TABLE pm_schedules ADD COLUMN spares_required JSONB DEFAULT '[]';
    END IF;
END $$;

-- ============================================
-- Fix maintenance_work_orders table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'id') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN id UUID DEFAULT gen_random_uuid() PRIMARY KEY;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'created_at') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'updated_at') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'created_by') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN created_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'updated_by') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN updated_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'is_deleted') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE NOT NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'deleted_at') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'deleted_by') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN deleted_by VARCHAR(100);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'wo_number') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN wo_number VARCHAR(50) UNIQUE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'description') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'wo_type') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN wo_type VARCHAR(20) DEFAULT 'corrective';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'status') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN status VARCHAR(20) DEFAULT 'draft';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'priority') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN priority VARCHAR(20) DEFAULT 'medium';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'asset_id') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN asset_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'pm_schedule_id') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN pm_schedule_id UUID;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'problem_code') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN problem_code VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'problem_description') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN problem_description TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'failure_code') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN failure_code VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'reported_date') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN reported_date TIMESTAMP DEFAULT NOW();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'target_start') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN target_start TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'target_completion') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN target_completion TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'actual_start') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN actual_start TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'actual_completion') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN actual_completion TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'assigned_to') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN assigned_to VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'work_center_id') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN work_center_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'estimated_hours') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN estimated_hours FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'actual_hours') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN actual_hours FLOAT DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'estimated_cost') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN estimated_cost FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'actual_labor_cost') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN actual_labor_cost FLOAT DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'actual_material_cost') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN actual_material_cost FLOAT DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'downtime_start') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN downtime_start TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'downtime_end') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN downtime_end TIMESTAMP;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'downtime_hours') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN downtime_hours FLOAT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'instructions') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN instructions TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'completion_notes') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN completion_notes TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'root_cause') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN root_cause TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'corrective_action') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN corrective_action TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'requires_approval') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN requires_approval BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'approved_by') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN approved_by VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'maintenance_work_orders' AND column_name = 'approved_date') THEN
        ALTER TABLE maintenance_work_orders ADD COLUMN approved_date TIMESTAMP;
    END IF;
END $$;

-- ============================================
-- Fix lego_products table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'material_cost') THEN
        ALTER TABLE lego_products ADD COLUMN material_cost NUMERIC(10,4);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'labor_cost') THEN
        ALTER TABLE lego_products ADD COLUMN labor_cost NUMERIC(10,4);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'overhead_cost') THEN
        ALTER TABLE lego_products ADD COLUMN overhead_cost NUMERIC(10,4);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'total_cost') THEN
        ALTER TABLE lego_products ADD COLUMN total_cost NUMERIC(10,4);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'list_price') THEN
        ALTER TABLE lego_products ADD COLUMN list_price NUMERIC(10,2);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'lead_time_days') THEN
        ALTER TABLE lego_products ADD COLUMN lead_time_days INTEGER DEFAULT 1;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'min_order_qty') THEN
        ALTER TABLE lego_products ADD COLUMN min_order_qty INTEGER DEFAULT 1;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'gcode_file') THEN
        ALTER TABLE lego_products ADD COLUMN gcode_file VARCHAR(500);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'cam_file') THEN
        ALTER TABLE lego_products ADD COLUMN cam_file VARCHAR(500);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'erp_item_id') THEN
        ALTER TABLE lego_products ADD COLUMN erp_item_id UUID;
    END IF;
END $$;

-- ============================================
-- Fix lego_materials table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_materials' AND column_name = 'process_type') THEN
        ALTER TABLE lego_materials ADD COLUMN process_type VARCHAR(20);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_materials' AND column_name = 'default_machine_id') THEN
        ALTER TABLE lego_materials ADD COLUMN default_machine_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_materials' AND column_name = 'cost_per_gram') THEN
        ALTER TABLE lego_materials ADD COLUMN cost_per_gram NUMERIC(10,4);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_materials' AND column_name = 'process_params') THEN
        ALTER TABLE lego_materials ADD COLUMN process_params JSONB DEFAULT '{}';
    END IF;
END $$;

-- ============================================
-- Fix lego_colors table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_colors' AND column_name = 'hex_code') THEN
        ALTER TABLE lego_colors ADD COLUMN hex_code VARCHAR(7);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_colors' AND column_name = 'lego_id') THEN
        ALTER TABLE lego_colors ADD COLUMN lego_id INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_colors' AND column_name = 'is_metal_finish') THEN
        ALTER TABLE lego_colors ADD COLUMN is_metal_finish BOOLEAN DEFAULT FALSE;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_colors' AND column_name = 'finish_type') THEN
        ALTER TABLE lego_colors ADD COLUMN finish_type VARCHAR(30);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_colors' AND column_name = 'compatible_materials') THEN
        ALTER TABLE lego_colors ADD COLUMN compatible_materials JSONB DEFAULT '[]';
    END IF;
END $$;

-- ============================================
-- Fix lego_routings table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_routings' AND column_name = 'estimated_time_min') THEN
        ALTER TABLE lego_routings ADD COLUMN estimated_time_min INTEGER;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_routings' AND column_name = 'revision') THEN
        ALTER TABLE lego_routings ADD COLUMN revision VARCHAR(20) DEFAULT '1.0';
    END IF;
END $$;

-- ============================================
-- Fix lego_routing_operations table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_routing_operations' AND column_name = 'work_center_id') THEN
        ALTER TABLE lego_routing_operations ADD COLUMN work_center_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_routing_operations' AND column_name = 'machine_id') THEN
        ALTER TABLE lego_routing_operations ADD COLUMN machine_id VARCHAR(50);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_routing_operations' AND column_name = 'setup_time_min') THEN
        ALTER TABLE lego_routing_operations ADD COLUMN setup_time_min INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_routing_operations' AND column_name = 'run_time_min') THEN
        ALTER TABLE lego_routing_operations ADD COLUMN run_time_min INTEGER DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_routing_operations' AND column_name = 'gcode_template') THEN
        ALTER TABLE lego_routing_operations ADD COLUMN gcode_template VARCHAR(500);
    END IF;
END $$;

-- ============================================
-- Create tables if they don't exist
-- ============================================

-- Create operations table if missing
CREATE TABLE IF NOT EXISTS operations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(100),
    work_order_id UUID,
    operation_id VARCHAR(50),
    sequence INTEGER DEFAULT 10,
    operation_type VARCHAR(30),
    name VARCHAR(200),
    description TEXT,
    work_center_id VARCHAR(50),
    machine_id VARCHAR(50),
    setup_time FLOAT DEFAULT 0,
    run_time FLOAT DEFAULT 0,
    teardown_time FLOAT DEFAULT 0,
    actual_setup_time FLOAT,
    actual_run_time FLOAT,
    status VARCHAR(20) DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    parameters JSONB DEFAULT '{}'
);

-- Create asset_classes table if missing
CREATE TABLE IF NOT EXISTS asset_classes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(100),
    code VARCHAR(50) UNIQUE,
    name VARCHAR(200),
    description TEXT,
    parent_class_id UUID,
    default_pm_interval_days INTEGER,
    default_pm_interval_hours FLOAT,
    expected_lifespan_years FLOAT,
    spec_template JSONB DEFAULT '{}'
);

-- Create meters table if missing
CREATE TABLE IF NOT EXISTS meters (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(100),
    meter_id VARCHAR(50) UNIQUE,
    asset_id UUID,
    name VARCHAR(200),
    description TEXT,
    meter_type VARCHAR(20) DEFAULT 'continuous',
    unit_of_measure VARCHAR(50),
    last_reading FLOAT,
    last_reading_date TIMESTAMP,
    warning_threshold FLOAT,
    critical_threshold FLOAT,
    rollover_value FLOAT,
    average_daily_usage FLOAT
);

-- Create spares table if missing
CREATE TABLE IF NOT EXISTS spares (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(100),
    spare_id VARCHAR(50) UNIQUE,
    name VARCHAR(200),
    description TEXT,
    item_id VARCHAR(50),
    quantity_on_hand INTEGER DEFAULT 0,
    reorder_point INTEGER DEFAULT 0,
    reorder_quantity INTEGER DEFAULT 1,
    unit_cost FLOAT,
    vendor_id VARCHAR(50),
    vendor_part_number VARCHAR(100),
    lead_time_days INTEGER,
    bin_location VARCHAR(100)
);

-- Create task_templates table if missing
CREATE TABLE IF NOT EXISTS task_templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(100),
    template_id VARCHAR(50) UNIQUE,
    name VARCHAR(200),
    description TEXT,
    instructions TEXT,
    estimated_hours FLOAT,
    skill_required VARCHAR(100),
    safety_requirements JSONB DEFAULT '[]',
    lockout_required BOOLEAN DEFAULT FALSE,
    tools_required JSONB DEFAULT '[]',
    materials_required JSONB DEFAULT '[]'
);

-- Create pm_schedules table if missing
CREATE TABLE IF NOT EXISTS pm_schedules (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(100),
    pm_id VARCHAR(50) UNIQUE,
    name VARCHAR(200),
    description TEXT,
    asset_id UUID,
    asset_class_id UUID,
    is_active BOOLEAN DEFAULT TRUE,
    trigger_type VARCHAR(20) DEFAULT 'calendar',
    frequency_days INTEGER,
    day_of_week INTEGER,
    day_of_month INTEGER,
    month_of_year INTEGER,
    meter_id UUID,
    meter_interval FLOAT,
    condition_tag_id VARCHAR(50),
    condition_threshold FLOAT,
    lead_time_days INTEGER DEFAULT 7,
    work_window_days INTEGER DEFAULT 7,
    last_completed TIMESTAMP,
    last_meter_reading FLOAT,
    next_due_date DATE,
    next_due_meter FLOAT,
    priority VARCHAR(20) DEFAULT 'medium',
    estimated_hours FLOAT,
    estimated_cost FLOAT,
    work_center_id VARCHAR(50),
    task_template_id UUID,
    instructions TEXT,
    checklist JSONB DEFAULT '[]',
    spares_required JSONB DEFAULT '[]'
);

-- ============================================
-- Fix partners table - add ALL missing columns
-- ============================================
DO $$
BEGIN
    -- Add legal_name
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'legal_name') THEN
        ALTER TABLE partners ADD COLUMN legal_name VARCHAR(200);
    END IF;
    -- Add status
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'status') THEN
        ALTER TABLE partners ADD COLUMN status VARCHAR(20) DEFAULT 'active';
    END IF;
    -- Add fax
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'fax') THEN
        ALTER TABLE partners ADD COLUMN fax VARCHAR(50);
    END IF;
    -- Add tax_exempt
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'tax_exempt') THEN
        ALTER TABLE partners ADD COLUMN tax_exempt BOOLEAN DEFAULT FALSE;
    END IF;
    -- Add tax_exempt_certificate
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'tax_exempt_certificate') THEN
        ALTER TABLE partners ADD COLUMN tax_exempt_certificate VARCHAR(100);
    END IF;
    -- Add payment_terms_days
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'payment_terms_days') THEN
        ALTER TABLE partners ADD COLUMN payment_terms_days INTEGER;
    END IF;
    -- Add salesperson_id
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'salesperson_id') THEN
        ALTER TABLE partners ADD COLUMN salesperson_id VARCHAR(50);
    END IF;
    -- Add territory
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'territory') THEN
        ALTER TABLE partners ADD COLUMN territory VARCHAR(100);
    END IF;
    -- Add customer_category
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'customer_category') THEN
        ALTER TABLE partners ADD COLUMN customer_category VARCHAR(50);
    END IF;
    -- Add price_list_id
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'price_list_id') THEN
        ALTER TABLE partners ADD COLUMN price_list_id VARCHAR(50);
    END IF;
    -- Add vendor_category
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'vendor_category') THEN
        ALTER TABLE partners ADD COLUMN vendor_category VARCHAR(50);
    END IF;
    -- Add lead_time_days
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'lead_time_days') THEN
        ALTER TABLE partners ADD COLUMN lead_time_days INTEGER;
    END IF;
    -- Add min_order_amount
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'min_order_amount') THEN
        ALTER TABLE partners ADD COLUMN min_order_amount NUMERIC;
    END IF;
    -- Add bank_name
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'bank_name') THEN
        ALTER TABLE partners ADD COLUMN bank_name VARCHAR(200);
    END IF;
    -- Add bank_account
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'bank_account') THEN
        ALTER TABLE partners ADD COLUMN bank_account VARCHAR(100);
    END IF;
    -- Add bank_routing
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'bank_routing') THEN
        ALTER TABLE partners ADD COLUMN bank_routing VARCHAR(50);
    END IF;
    -- Add ar_account
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'ar_account') THEN
        ALTER TABLE partners ADD COLUMN ar_account VARCHAR(50);
    END IF;
    -- Add ap_account
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'ap_account') THEN
        ALTER TABLE partners ADD COLUMN ap_account VARCHAR(50);
    END IF;
    -- Add attributes
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'attributes') THEN
        ALTER TABLE partners ADD COLUMN attributes JSONB DEFAULT '{}';
    END IF;
    -- Add website
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'website') THEN
        ALTER TABLE partners ADD COLUMN website VARCHAR(200);
    END IF;
    -- Add is_customer
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'is_customer') THEN
        ALTER TABLE partners ADD COLUMN is_customer BOOLEAN DEFAULT FALSE;
    END IF;
    -- Add is_vendor
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partners' AND column_name = 'is_vendor') THEN
        ALTER TABLE partners ADD COLUMN is_vendor BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- ============================================
-- Fix assets table - make asset_number nullable
-- ============================================
DO $$
BEGIN
    -- Check if asset_number has NOT NULL constraint and remove it
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'assets'
        AND column_name = 'asset_number'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE assets ALTER COLUMN asset_number DROP NOT NULL;
    END IF;
END $$;

-- ============================================
-- Fix jobs.work_order_id type if VARCHAR instead of UUID
-- ============================================
DO $$
BEGIN
    -- Check if work_order_id is VARCHAR and needs to be UUID
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'jobs'
        AND column_name = 'work_order_id'
        AND data_type = 'character varying'
    ) THEN
        -- Drop the column and re-add as UUID
        ALTER TABLE jobs DROP COLUMN work_order_id;
        ALTER TABLE jobs ADD COLUMN work_order_id UUID REFERENCES work_orders(id);
    END IF;
END $$;

-- ============================================
-- Fix jobs.machine_id type if UUID instead of VARCHAR
-- The model defines machine_id as String(50), not UUID
-- ============================================
DO $$
BEGIN
    -- Check if machine_id is UUID but should be VARCHAR
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'jobs'
        AND column_name = 'machine_id'
        AND data_type = 'uuid'
    ) THEN
        -- Drop and recreate as VARCHAR
        ALTER TABLE jobs DROP COLUMN machine_id;
        ALTER TABLE jobs ADD COLUMN machine_id VARCHAR(50);
        CREATE INDEX IF NOT EXISTS ix_jobs_machine_id ON jobs(machine_id);
    END IF;
END $$;

-- ============================================
-- Fix jobs.operation_id - allow NULL values
-- Jobs can exist without a specific operation
-- ============================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'jobs'
        AND column_name = 'operation_id'
        AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE jobs ALTER COLUMN operation_id DROP NOT NULL;
    END IF;
END $$;

-- ============================================
-- Fix operations.machine_id type if UUID instead of VARCHAR
-- The model defines machine_id as String(50), not UUID
-- ============================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'operations'
        AND column_name = 'machine_id'
        AND data_type = 'uuid'
    ) THEN
        -- Drop and recreate as VARCHAR
        ALTER TABLE operations DROP COLUMN machine_id;
        ALTER TABLE operations ADD COLUMN machine_id VARCHAR(50);
        CREATE INDEX IF NOT EXISTS ix_operations_machine_id ON operations(machine_id);
    END IF;
END $$;

-- ============================================
-- Ensure lego_products has routing_id column
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'lego_products' AND column_name = 'routing_id') THEN
        ALTER TABLE lego_products ADD COLUMN routing_id VARCHAR(50);
    END IF;
END $$;

-- ============================================
-- Create partners table if it doesn't exist
-- ============================================
CREATE TABLE IF NOT EXISTS partners (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(100),
    partner_id VARCHAR(50) UNIQUE,
    name VARCHAR(200) NOT NULL,
    legal_name VARCHAR(200),
    partner_type VARCHAR(20),
    is_customer BOOLEAN DEFAULT FALSE,
    is_vendor BOOLEAN DEFAULT FALSE,
    tax_id VARCHAR(50),
    currency VARCHAR(3) DEFAULT 'USD',
    payment_terms VARCHAR(50),
    credit_limit NUMERIC(12,2),
    email VARCHAR(200),
    phone VARCHAR(50),
    website VARCHAR(200),
    address_line1 VARCHAR(200),
    address_line2 VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'US',
    notes TEXT,
    metadata JSONB DEFAULT '{}'
);

-- ============================================
-- Fix existing jobs with NULL scheduled times
-- ============================================
UPDATE jobs
SET scheduled_start = created_at,
    scheduled_end = created_at + INTERVAL '2 hours'
WHERE scheduled_start IS NULL AND status != 'completed';

-- ============================================
-- Create CRM Activities table
-- ============================================
CREATE TABLE IF NOT EXISTS crm_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id UUID REFERENCES partners(id),
    contact_id UUID,
    activity_type VARCHAR(50) NOT NULL,  -- 'call', 'email', 'meeting', 'note'
    subject VARCHAR(200),
    description TEXT,
    activity_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP,
    completed BOOLEAN DEFAULT false,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_crm_activities_partner ON crm_activities(partner_id);
CREATE INDEX IF NOT EXISTS ix_crm_activities_date ON crm_activities(activity_date);
CREATE INDEX IF NOT EXISTS ix_crm_activities_type ON crm_activities(activity_type);

-- ============================================
-- Create Contacts table for CRM
-- ============================================
CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_at TIMESTAMPTZ,
    deleted_by VARCHAR(100),
    contact_id VARCHAR(50) UNIQUE,
    partner_id UUID REFERENCES partners(id),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    title VARCHAR(100),
    department VARCHAR(100),
    email VARCHAR(200),
    phone VARCHAR(50),
    mobile VARCHAR(50),
    is_primary BOOLEAN DEFAULT FALSE,
    notes TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_contacts_partner ON contacts(partner_id);
CREATE INDEX IF NOT EXISTS ix_contacts_email ON contacts(email);

-- Confirm completion
SELECT 'Comprehensive schema fix completed successfully!' as status;
