-- LEGO MCP Manufacturing Database Schema
-- ISA-95 Compliant Manufacturing Operations Management
-- Version: 2.0.0

-- Enable UUID extension for primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- PART MASTER (EBOM/MBOM Source)
-- ============================================
CREATE TABLE IF NOT EXISTS parts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_number VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    part_type VARCHAR(50) NOT NULL DEFAULT 'standard',
    category VARCHAR(100),
    studs_x INTEGER,
    studs_y INTEGER,
    height_plates REAL,
    volume_mm3 REAL,
    weight_grams REAL,
    standard_cost DECIMAL(10,4) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    specifications JSONB,
    cad_file_path VARCHAR(500),
    thumbnail_path VARCHAR(500)
);

CREATE INDEX idx_parts_part_number ON parts(part_number);
CREATE INDEX idx_parts_type ON parts(part_type);
CREATE INDEX idx_parts_category ON parts(category);

-- ============================================
-- BILL OF MATERIALS
-- ============================================
CREATE TABLE IF NOT EXISTS bom (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    parent_part_id UUID NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    child_part_id UUID NOT NULL REFERENCES parts(id) ON DELETE RESTRICT,
    quantity REAL NOT NULL DEFAULT 1,
    unit VARCHAR(10) DEFAULT 'EA',
    bom_type VARCHAR(20) DEFAULT 'MBOM',
    sequence INTEGER,
    notes TEXT,
    effective_date DATE,
    obsolete_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(parent_part_id, child_part_id, bom_type)
);

CREATE INDEX idx_bom_parent ON bom(parent_part_id);
CREATE INDEX idx_bom_child ON bom(child_part_id);

-- ============================================
-- WORK CENTERS (Machines/Resources)
-- ============================================
CREATE TABLE IF NOT EXISTS work_centers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL,
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    serial_number VARCHAR(100),
    capabilities JSONB,
    status VARCHAR(50) DEFAULT 'AVAILABLE',
    location VARCHAR(255),
    capacity_per_hour REAL,
    hourly_rate DECIMAL(10,2) DEFAULT 0,
    efficiency_percent REAL DEFAULT 85.0,
    maintenance_interval_hours REAL,
    last_maintenance TIMESTAMP WITH TIME ZONE,
    total_runtime_hours REAL DEFAULT 0,
    connection_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_work_centers_type ON work_centers(type);
CREATE INDEX idx_work_centers_status ON work_centers(status);

-- ============================================
-- MANUFACTURING ROUTINGS
-- ============================================
CREATE TABLE IF NOT EXISTS routings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_id UUID NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    operation_sequence INTEGER NOT NULL,
    operation_code VARCHAR(50) NOT NULL,
    work_center_id UUID REFERENCES work_centers(id),
    description TEXT,
    setup_time_min REAL DEFAULT 0,
    run_time_min REAL DEFAULT 0,
    machine_time_min REAL DEFAULT 0,
    labor_time_min REAL DEFAULT 0,
    standard_cost DECIMAL(10,4) DEFAULT 0,
    instructions TEXT,
    tooling_required JSONB,
    parameters JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(part_id, operation_sequence)
);

CREATE INDEX idx_routings_part ON routings(part_id);
CREATE INDEX idx_routings_work_center ON routings(work_center_id);

-- ============================================
-- CUSTOMERS
-- ============================================
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_number VARCHAR(50) UNIQUE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    address JSONB,
    default_priority INTEGER DEFAULT 5,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- WORK ORDERS
-- ============================================
CREATE TABLE IF NOT EXISTS work_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_number VARCHAR(50) UNIQUE NOT NULL,
    part_id UUID NOT NULL REFERENCES parts(id),
    quantity_ordered INTEGER NOT NULL,
    quantity_completed INTEGER DEFAULT 0,
    quantity_scrapped INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'PLANNED',
    priority INTEGER DEFAULT 5,
    scheduled_start TIMESTAMP WITH TIME ZONE,
    scheduled_end TIMESTAMP WITH TIME ZONE,
    actual_start TIMESTAMP WITH TIME ZONE,
    actual_end TIMESTAMP WITH TIME ZONE,
    parent_order_id UUID REFERENCES work_orders(id),
    sales_order_ref VARCHAR(100),
    customer_id UUID REFERENCES customers(id),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE INDEX idx_work_orders_status ON work_orders(status);
CREATE INDEX idx_work_orders_scheduled ON work_orders(scheduled_start);
CREATE INDEX idx_work_orders_part ON work_orders(part_id);

-- ============================================
-- WORK ORDER OPERATIONS
-- ============================================
CREATE TABLE IF NOT EXISTS work_order_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    routing_id UUID REFERENCES routings(id),
    operation_sequence INTEGER NOT NULL,
    operation_code VARCHAR(50) NOT NULL,
    work_center_id UUID REFERENCES work_centers(id),
    status VARCHAR(50) DEFAULT 'PENDING',
    quantity_completed INTEGER DEFAULT 0,
    quantity_scrapped INTEGER DEFAULT 0,
    scheduled_start TIMESTAMP WITH TIME ZONE,
    scheduled_end TIMESTAMP WITH TIME ZONE,
    actual_start TIMESTAMP WITH TIME ZONE,
    actual_end TIMESTAMP WITH TIME ZONE,
    setup_time_actual_min REAL,
    run_time_actual_min REAL,
    operator_id VARCHAR(100),
    machine_program TEXT,
    parameters_used JSONB,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_wo_ops_work_order ON work_order_operations(work_order_id);
CREATE INDEX idx_wo_ops_status ON work_order_operations(status);
CREATE INDEX idx_wo_ops_work_center ON work_order_operations(work_center_id);

-- ============================================
-- INVENTORY LOCATIONS
-- ============================================
CREATE TABLE IF NOT EXISTS inventory_locations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    location_type VARCHAR(50) DEFAULT 'SHELF',
    parent_location_id UUID REFERENCES inventory_locations(id),
    zone VARCHAR(50),
    aisle VARCHAR(50),
    rack VARCHAR(50),
    shelf VARCHAR(50),
    bin VARCHAR(50),
    capacity INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_inv_locations_type ON inventory_locations(location_type);

-- ============================================
-- INVENTORY TRANSACTIONS
-- ============================================
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_type VARCHAR(50) NOT NULL,
    part_id UUID NOT NULL REFERENCES parts(id),
    quantity REAL NOT NULL,
    uom VARCHAR(10) DEFAULT 'EA',
    from_location_id UUID REFERENCES inventory_locations(id),
    to_location_id UUID REFERENCES inventory_locations(id),
    work_order_id UUID REFERENCES work_orders(id),
    lot_number VARCHAR(100),
    serial_number VARCHAR(100),
    unit_cost DECIMAL(10,4),
    total_cost DECIMAL(12,4),
    reason_code VARCHAR(50),
    reference_doc VARCHAR(100),
    transacted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    transacted_by VARCHAR(100)
);

CREATE INDEX idx_inv_trans_part ON inventory_transactions(part_id);
CREATE INDEX idx_inv_trans_type ON inventory_transactions(transaction_type);
CREATE INDEX idx_inv_trans_date ON inventory_transactions(transacted_at);

-- ============================================
-- INVENTORY BALANCES (Materialized View)
-- ============================================
CREATE TABLE IF NOT EXISTS inventory_balances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_id UUID NOT NULL REFERENCES parts(id),
    location_id UUID NOT NULL REFERENCES inventory_locations(id),
    quantity_on_hand REAL DEFAULT 0,
    quantity_allocated REAL DEFAULT 0,
    quantity_available REAL GENERATED ALWAYS AS (quantity_on_hand - quantity_allocated) STORED,
    last_count_date TIMESTAMP WITH TIME ZONE,
    average_cost DECIMAL(10,4),
    last_receipt_date TIMESTAMP WITH TIME ZONE,
    last_issue_date TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(part_id, location_id)
);

CREATE INDEX idx_inv_balance_part ON inventory_balances(part_id);
CREATE INDEX idx_inv_balance_location ON inventory_balances(location_id);

-- ============================================
-- QUALITY INSPECTIONS
-- ============================================
CREATE TABLE IF NOT EXISTS quality_inspections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id UUID REFERENCES work_orders(id),
    operation_id UUID REFERENCES work_order_operations(id),
    part_id UUID NOT NULL REFERENCES parts(id),
    inspection_type VARCHAR(50) NOT NULL,
    sample_size INTEGER DEFAULT 1,
    inspector_id VARCHAR(100),
    inspected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    result VARCHAR(50) NOT NULL,
    disposition VARCHAR(50),
    measurements JSONB,
    defects_found JSONB,
    notes TEXT,
    images JSONB
);

CREATE INDEX idx_quality_insp_wo ON quality_inspections(work_order_id);
CREATE INDEX idx_quality_insp_result ON quality_inspections(result);
CREATE INDEX idx_quality_insp_date ON quality_inspections(inspected_at);

-- ============================================
-- QUALITY METRICS (Dimensional Data)
-- ============================================
CREATE TABLE IF NOT EXISTS quality_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    inspection_id UUID NOT NULL REFERENCES quality_inspections(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    target_value REAL,
    actual_value REAL,
    tolerance_plus REAL,
    tolerance_minus REAL,
    unit VARCHAR(20),
    is_within_spec BOOLEAN,
    measurement_tool VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quality_metrics_inspection ON quality_metrics(inspection_id);
CREATE INDEX idx_quality_metrics_name ON quality_metrics(metric_name);

-- ============================================
-- OEE EVENTS (Availability, Performance, Quality)
-- ============================================
CREATE TABLE IF NOT EXISTS oee_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_center_id UUID NOT NULL REFERENCES work_centers(id),
    event_type VARCHAR(50) NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_minutes REAL,
    reason_code VARCHAR(50),
    parts_produced INTEGER DEFAULT 0,
    parts_defective INTEGER DEFAULT 0,
    ideal_cycle_time_sec REAL,
    actual_cycle_time_sec REAL,
    work_order_id UUID REFERENCES work_orders(id),
    operator_id VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_oee_events_wc ON oee_events(work_center_id);
CREATE INDEX idx_oee_events_time ON oee_events(start_time);
CREATE INDEX idx_oee_events_type ON oee_events(event_type);
CREATE INDEX idx_oee_events_wc_time ON oee_events(work_center_id, start_time);

-- ============================================
-- MAINTENANCE RECORDS
-- ============================================
CREATE TABLE IF NOT EXISTS maintenance_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_center_id UUID NOT NULL REFERENCES work_centers(id),
    maintenance_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'SCHEDULED',
    scheduled_date TIMESTAMP WITH TIME ZONE,
    completed_date TIMESTAMP WITH TIME ZONE,
    technician_id VARCHAR(100),
    description TEXT,
    parts_used JSONB,
    labor_hours REAL,
    cost DECIMAL(10,2),
    next_maintenance_date TIMESTAMP WITH TIME ZONE,
    runtime_at_maintenance REAL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_maintenance_wc ON maintenance_records(work_center_id);
CREATE INDEX idx_maintenance_status ON maintenance_records(status);
CREATE INDEX idx_maintenance_scheduled ON maintenance_records(scheduled_date);

-- ============================================
-- COST LEDGER
-- ============================================
CREATE TABLE IF NOT EXISTS cost_ledger (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_date DATE NOT NULL,
    cost_type VARCHAR(50) NOT NULL,
    work_order_id UUID REFERENCES work_orders(id),
    operation_id UUID REFERENCES work_order_operations(id),
    part_id UUID REFERENCES parts(id),
    work_center_id UUID REFERENCES work_centers(id),
    standard_cost DECIMAL(12,4) DEFAULT 0,
    actual_cost DECIMAL(12,4) DEFAULT 0,
    variance DECIMAL(12,4) GENERATED ALWAYS AS (actual_cost - standard_cost) STORED,
    quantity REAL DEFAULT 1,
    uom VARCHAR(10),
    gl_account VARCHAR(50),
    reference_doc VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cost_ledger_date ON cost_ledger(transaction_date);
CREATE INDEX idx_cost_ledger_wo ON cost_ledger(work_order_id);
CREATE INDEX idx_cost_ledger_type ON cost_ledger(cost_type);

-- ============================================
-- DIGITAL TWIN STATE
-- ============================================
CREATE TABLE IF NOT EXISTS digital_twin_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_center_id UUID NOT NULL REFERENCES work_centers(id),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    state_type VARCHAR(50) NOT NULL,
    state_data JSONB NOT NULL,
    is_current BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_twin_state_wc ON digital_twin_state(work_center_id);
CREATE INDEX idx_twin_state_time ON digital_twin_state(timestamp);
CREATE INDEX idx_twin_state_current ON digital_twin_state(work_center_id, is_current) WHERE is_current = TRUE;

-- ============================================
-- USERS (Multi-user Support)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    role VARCHAR(50) DEFAULT 'OPERATOR',
    permissions JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);

-- ============================================
-- AUDIT LOG
-- ============================================
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100) NOT NULL,
    record_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(50),
    user_agent TEXT
);

CREATE INDEX idx_audit_table_record ON audit_log(table_name, record_id);
CREATE INDEX idx_audit_changed_at ON audit_log(changed_at);

-- ============================================
-- DEFAULT DATA: Work Center Types
-- ============================================
INSERT INTO work_centers (name, code, type, status, capabilities)
VALUES
    ('Design Workstation', 'WC-DESIGN-01', 'DESIGN_WORKSTATION', 'AVAILABLE',
     '{"operations": ["CAD_DESIGN"], "software": ["Fusion 360"]}'),
    ('FDM Printer 1', 'WC-FDM-01', 'FDM_PRINTER', 'AVAILABLE',
     '{"operations": ["3D_PRINT_FDM"], "build_volume": {"x": 256, "y": 256, "z": 256}, "materials": ["PLA", "PETG", "ABS"]}'),
    ('CNC Mill 1', 'WC-CNC-01', 'CNC_MILL', 'AVAILABLE',
     '{"operations": ["CNC_MILL"], "work_envelope": {"x": 300, "y": 200, "z": 100}, "spindle_rpm": 24000}'),
    ('Laser Engraver 1', 'WC-LASER-01', 'LASER_ENGRAVER', 'AVAILABLE',
     '{"operations": ["LASER_ENGRAVE"], "work_area": {"x": 400, "y": 400}, "power_watts": 40}'),
    ('Inspection Station', 'WC-QC-01', 'INSPECTION_STATION', 'AVAILABLE',
     '{"operations": ["QC_INSPECT", "QC_FIT_TEST"], "equipment": ["calipers", "go_no_go_gauges"]}')
ON CONFLICT (code) DO NOTHING;

-- ============================================
-- DEFAULT DATA: Inventory Locations
-- ============================================
INSERT INTO inventory_locations (location_code, name, location_type)
VALUES
    ('RAW', 'Raw Materials', 'SHELF'),
    ('WIP', 'Work In Progress', 'WIP'),
    ('FG', 'Finished Goods', 'FINISHED_GOODS'),
    ('SCRAP', 'Scrap/Reject', 'FLOOR'),
    ('QC-HOLD', 'QC Hold Area', 'FLOOR')
ON CONFLICT (location_code) DO NOTHING;

-- ============================================
-- DEFAULT DATA: Admin User
-- ============================================
INSERT INTO users (username, email, role, permissions, is_active)
VALUES
    ('admin', 'admin@lego-mcp.local', 'ADMIN',
     '{"all": true}', TRUE),
    ('operator', 'operator@lego-mcp.local', 'OPERATOR',
     '{"work_orders": ["view", "start", "complete"], "inventory": ["view", "issue"]}', TRUE)
ON CONFLICT (username) DO NOTHING;

-- ============================================
-- FUNCTIONS: Update Timestamp Trigger
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables with updated_at
CREATE TRIGGER update_parts_updated_at
    BEFORE UPDATE ON parts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_work_centers_updated_at
    BEFORE UPDATE ON work_centers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_inventory_balances_updated_at
    BEFORE UPDATE ON inventory_balances
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- FUNCTIONS: OEE Calculation
-- ============================================
CREATE OR REPLACE FUNCTION calculate_oee(
    p_work_center_id UUID,
    p_start_time TIMESTAMP WITH TIME ZONE,
    p_end_time TIMESTAMP WITH TIME ZONE
)
RETURNS TABLE (
    availability REAL,
    performance REAL,
    quality REAL,
    oee REAL,
    planned_time_min REAL,
    run_time_min REAL,
    total_count INTEGER,
    good_count INTEGER
) AS $$
DECLARE
    v_planned_time REAL;
    v_run_time REAL;
    v_downtime REAL;
    v_total_count INTEGER;
    v_defect_count INTEGER;
    v_good_count INTEGER;
    v_ideal_cycle_time REAL;
    v_availability REAL;
    v_performance REAL;
    v_quality REAL;
BEGIN
    -- Calculate planned production time (in minutes)
    v_planned_time := EXTRACT(EPOCH FROM (p_end_time - p_start_time)) / 60.0;

    -- Get production events
    SELECT
        COALESCE(SUM(CASE WHEN event_type = 'PRODUCTION' THEN duration_minutes ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN event_type = 'DOWNTIME' THEN duration_minutes ELSE 0 END), 0),
        COALESCE(SUM(parts_produced), 0),
        COALESCE(SUM(parts_defective), 0),
        COALESCE(AVG(ideal_cycle_time_sec), 60)
    INTO v_run_time, v_downtime, v_total_count, v_defect_count, v_ideal_cycle_time
    FROM oee_events
    WHERE work_center_id = p_work_center_id
      AND start_time >= p_start_time
      AND start_time < p_end_time;

    v_good_count := v_total_count - v_defect_count;

    -- Calculate OEE components
    IF v_planned_time > 0 THEN
        v_availability := (v_run_time / v_planned_time) * 100;
    ELSE
        v_availability := 0;
    END IF;

    IF v_run_time > 0 AND v_ideal_cycle_time > 0 THEN
        v_performance := ((v_ideal_cycle_time * v_total_count) / (v_run_time * 60)) * 100;
    ELSE
        v_performance := 0;
    END IF;

    IF v_total_count > 0 THEN
        v_quality := (v_good_count::REAL / v_total_count::REAL) * 100;
    ELSE
        v_quality := 100;  -- No production = no quality issues
    END IF;

    -- Clamp values to 0-100 range
    v_availability := LEAST(GREATEST(v_availability, 0), 100);
    v_performance := LEAST(GREATEST(v_performance, 0), 100);
    v_quality := LEAST(GREATEST(v_quality, 0), 100);

    RETURN QUERY SELECT
        ROUND(v_availability::NUMERIC, 1)::REAL,
        ROUND(v_performance::NUMERIC, 1)::REAL,
        ROUND(v_quality::NUMERIC, 1)::REAL,
        ROUND((v_availability * v_performance * v_quality / 10000)::NUMERIC, 1)::REAL,
        v_planned_time,
        v_run_time,
        v_total_count,
        v_good_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VIEWS: Work Order Summary
-- ============================================
CREATE OR REPLACE VIEW v_work_order_summary AS
SELECT
    wo.id,
    wo.work_order_number,
    wo.status,
    wo.priority,
    p.part_number,
    p.name AS part_name,
    wo.quantity_ordered,
    wo.quantity_completed,
    wo.quantity_scrapped,
    wo.scheduled_start,
    wo.scheduled_end,
    wo.actual_start,
    wo.actual_end,
    c.name AS customer_name,
    COUNT(woo.id) AS operation_count,
    COUNT(CASE WHEN woo.status = 'COMPLETE' THEN 1 END) AS operations_completed
FROM work_orders wo
JOIN parts p ON wo.part_id = p.id
LEFT JOIN customers c ON wo.customer_id = c.id
LEFT JOIN work_order_operations woo ON wo.id = woo.work_order_id
GROUP BY wo.id, p.part_number, p.name, c.name;

-- ============================================
-- VIEWS: Inventory Summary
-- ============================================
CREATE OR REPLACE VIEW v_inventory_summary AS
SELECT
    p.id AS part_id,
    p.part_number,
    p.name AS part_name,
    p.category,
    il.location_code,
    il.name AS location_name,
    ib.quantity_on_hand,
    ib.quantity_allocated,
    ib.quantity_available,
    ib.average_cost,
    (ib.quantity_on_hand * COALESCE(ib.average_cost, p.standard_cost)) AS total_value
FROM inventory_balances ib
JOIN parts p ON ib.part_id = p.id
JOIN inventory_locations il ON ib.location_id = il.id;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO lego_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO lego_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO lego_admin;
