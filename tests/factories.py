"""
LEGO Factory v3 - Test Factories
================================
Factory Boy factories for generating test data.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import factory
from factory import Faker, LazyAttribute, SubFactory, Sequence

# We'll mock the models for unit testing
# These factories create dictionaries that mimic model instances


class DictFactory(factory.Factory):
    """Base factory that creates dictionaries instead of model instances."""

    class Meta:
        model = dict

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        return kwargs

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        return kwargs


class UserFactory(DictFactory):
    """Factory for user data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    username = Sequence(lambda n: f"user_{n}")
    email = Faker('email')
    password_hash = "hashed_password_placeholder"
    is_active = True
    is_admin = False
    created_at = factory.LazyFunction(datetime.utcnow)
    updated_at = factory.LazyFunction(datetime.utcnow)


class TagFactory(DictFactory):
    """Factory for SCADA tag data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    tag_id = Sequence(lambda n: f"TAG-{n:04d}")
    name = Faker('word')
    description = Faker('sentence')
    data_type = "float32"
    category = "analog_input"
    area = "production"
    equipment = Sequence(lambda n: f"Machine-{n}")
    eng_units = "C"
    eng_low = 0.0
    eng_high = 100.0
    raw_low = 0.0
    raw_high = 4095.0
    current_value = 25.0
    current_quality = 192
    current_timestamp = factory.LazyFunction(datetime.utcnow)
    historize = True
    scan_rate_ms = 1000
    deadband = 0.5
    is_deleted = False


class AlarmDefinitionFactory(DictFactory):
    """Factory for alarm definition data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    alarm_id = Sequence(lambda n: f"ALM-{n:04d}")
    name = Faker('sentence', nb_words=3)
    description = Faker('sentence')
    priority = 2  # HIGH
    alarm_class = "process"
    alarm_type = "high"
    tag_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    setpoint = 50.0
    high_limit = 80.0
    high_high_limit = 90.0
    low_limit = 20.0
    low_low_limit = 10.0
    deadband = 1.0
    on_delay_seconds = 0
    off_delay_seconds = 0
    enabled = True
    is_active = False
    is_acknowledged = True
    consequence = "Temperature too high - risk of damage"
    corrective_action = "Check cooling system"


class MachineFactory(DictFactory):
    """Factory for machine data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    machine_id = Sequence(lambda n: f"MCH-{n:04d}")
    name = Faker('word')
    description = Faker('sentence')
    machine_type = "printer_3d"
    controller_type = "simulation"
    connection_type = "simulation"
    connection_config = {}
    current_state = "idle"
    enabled = True
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)


class WorkOrderFactory(DictFactory):
    """Factory for work order data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    work_order_id = Sequence(lambda n: f"WO-{datetime.utcnow().strftime('%Y%m%d')}-{n:04d}")
    description = Faker('sentence')
    product_id = Sequence(lambda n: f"PROD-{n:03d}")
    recipe_id = Sequence(lambda n: f"RCP-{n:03d}")
    quantity_ordered = 100
    quantity_completed = 0
    status = "draft"
    priority = 5
    planned_start = factory.LazyFunction(datetime.utcnow)
    planned_end = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(hours=8))
    actual_start = None
    actual_end = None
    due_date = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(days=7))
    customer_id = Sequence(lambda n: f"CUST-{n:03d}")
    sales_order_id = None
    notes = None
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


class JobFactory(DictFactory):
    """Factory for job data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    job_id = Sequence(lambda n: f"JOB-{datetime.utcnow().strftime('%Y%m%d')}-{n:04d}")
    work_order_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    operation_id = None
    machine_id = Sequence(lambda n: f"MCH-{n:04d}")
    scheduled_start = factory.LazyFunction(datetime.utcnow)
    scheduled_end = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(hours=2))
    actual_start = None
    actual_end = None
    status = "pending"
    priority_score = 0.5
    quantity_planned = 10
    quantity_completed = 0
    quantity_rejected = 0
    assigned_worker_id = None
    gcode_file = None
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


class OperationFactory(DictFactory):
    """Factory for operation data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    work_order_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    operation_id = Sequence(lambda n: f"OP-{n:04d}")
    sequence = 10
    operation_type = "printing_fdm"
    name = Faker('word')
    description = Faker('sentence')
    work_center_id = Sequence(lambda n: f"WC-{n:02d}")
    machine_id = Sequence(lambda n: f"MCH-{n:04d}")
    setup_time = 15.0
    run_time = 60.0
    teardown_time = 5.0
    status = "pending"
    is_deleted = False


class ItemFactory(DictFactory):
    """Factory for inventory item data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    item_id = Sequence(lambda n: f"ITEM-{n:06d}")
    name = Faker('word')
    description = Faker('sentence')
    item_type = "component"
    status = "active"
    base_uom = "EA"
    standard_cost = 10.0
    average_cost = 10.0
    list_price = 15.0
    lead_time_days = 3
    safety_stock = 100.0
    reorder_point = 50.0
    reorder_quantity = 200.0
    is_purchasable = True
    is_salable = True
    is_manufactured = False
    is_lot_controlled = False
    track_inventory = True
    is_deleted = False


class LocationFactory(DictFactory):
    """Factory for inventory location data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    location_id = Sequence(lambda n: f"LOC-{n:04d}")
    name = Faker('word')
    description = Faker('sentence')
    location_type = "warehouse"
    is_active = True
    allows_negative = False
    is_deleted = False


class InventoryBalanceFactory(DictFactory):
    """Factory for inventory balance data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    item_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    location_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    lot_id = None
    quantity_on_hand = 100.0
    quantity_allocated = 0.0
    quantity_available = 100.0
    quantity_on_order = 0.0
    unit_cost = 10.0
    total_value = 1000.0


class InventoryTransactionFactory(DictFactory):
    """Factory for inventory transaction data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    transaction_id = Sequence(lambda n: f"TXN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{n:04d}")
    transaction_type = "receipt"
    transaction_date = factory.LazyFunction(datetime.utcnow)
    item_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    from_location_id = None
    to_location_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    quantity = 100.0
    uom = "EA"
    unit_cost = 10.0
    total_cost = 1000.0
    reference_type = None
    reference_id = None
    notes = None
    created_by = "system"


class LotFactory(DictFactory):
    """Factory for lot/batch data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    lot_number = Sequence(lambda n: f"LOT-{datetime.utcnow().strftime('%Y%m%d')}-{n:04d}")
    item_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    status = "available"
    manufacture_date = factory.LazyFunction(lambda: datetime.utcnow().date())
    expiration_date = factory.LazyFunction(lambda: (datetime.utcnow() + timedelta(days=365)).date())
    receipt_date = factory.LazyFunction(lambda: datetime.utcnow().date())
    vendor_id = None
    vendor_lot = None


# =============================================================================
# CMMS Factories (Asset Management & Maintenance)
# =============================================================================

class AssetFactory(DictFactory):
    """Factory for asset data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    asset_id = Sequence(lambda n: f"AST-{n:08d}")
    name = Faker('word')
    description = Faker('sentence')
    asset_class_id = None
    status = "operational"
    criticality = "standard"
    location_id = None
    location_description = Faker('address')
    work_center_id = None
    serial_number = Sequence(lambda n: f"SN-{n:010d}")
    model_number = Sequence(lambda n: f"MDL-{n:05d}")
    manufacturer = Faker('company')
    vendor_id = None
    purchase_date = factory.LazyFunction(lambda: (datetime.utcnow() - timedelta(days=365)).date())
    installation_date = factory.LazyFunction(lambda: (datetime.utcnow() - timedelta(days=300)).date())
    warranty_expiry = factory.LazyFunction(lambda: (datetime.utcnow() + timedelta(days=365)).date())
    purchase_cost = 10000.0
    replacement_cost = 12000.0
    machine_id = None
    parent_asset_id = None
    specifications = {}
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


class AssetClassFactory(DictFactory):
    """Factory for asset class data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    code = Sequence(lambda n: f"CLS-{n:03d}")
    name = Faker('word')
    description = Faker('sentence')
    parent_class_id = None
    default_pm_interval_days = 90
    default_pm_interval_hours = 500
    expected_lifespan_years = 10
    spec_template = {}
    is_deleted = False


class MeterFactory(DictFactory):
    """Factory for meter data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    meter_id = Sequence(lambda n: f"MTR-{n:08d}")
    asset_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = Faker('word')
    description = Faker('sentence')
    meter_type = "continuous"
    unit_of_measure = "hours"
    last_reading = 1000.0
    last_reading_date = factory.LazyFunction(datetime.utcnow)
    warning_threshold = 4500.0
    critical_threshold = 5000.0
    rollover_value = 10000.0
    is_deleted = False


class MeterReadingFactory(DictFactory):
    """Factory for meter reading data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    meter_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    reading_date = factory.LazyFunction(datetime.utcnow)
    reading_value = 1050.0
    delta = 50.0
    source = "manual"
    recorded_by = "operator"


class MaintenanceWorkOrderFactory(DictFactory):
    """Factory for maintenance work order data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    wo_number = Sequence(lambda n: f"MWO-{datetime.utcnow().strftime('%Y%m%d')}-{n:06d}")
    description = Faker('sentence')
    wo_type = "corrective"
    status = "draft"
    priority = "medium"
    asset_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    pm_schedule_id = None
    problem_code = None
    problem_description = Faker('paragraph')
    target_start = factory.LazyFunction(datetime.utcnow)
    target_completion = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(days=3))
    actual_start = None
    actual_completion = None
    assigned_to = Sequence(lambda n: f"tech_{n}")
    work_center_id = None
    estimated_hours = 4.0
    actual_hours = None
    estimated_cost = 500.0
    actual_labor_cost = None
    actual_material_cost = None
    instructions = Faker('paragraph')
    completion_notes = None
    requires_approval = False
    downtime_start = None
    downtime_end = None
    downtime_hours = None
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


class WorkOrderTaskFactory(DictFactory):
    """Factory for work order task data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    work_order_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    sequence = Sequence(lambda n: n * 10)
    name = Faker('sentence', nb_words=4)
    description = Faker('sentence')
    instructions = Faker('paragraph')
    estimated_minutes = 30
    actual_minutes = None
    is_completed = False
    completed_by = None
    completed_date = None
    lockout_required = False


class WorkOrderLaborFactory(DictFactory):
    """Factory for work order labor data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    work_order_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    worker_id = Sequence(lambda n: f"worker_{n}")
    craft = "mechanic"
    start_time = factory.LazyFunction(datetime.utcnow)
    end_time = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(hours=2))
    regular_hours = 2.0
    overtime_hours = 0.0
    hourly_rate = 50.0
    total_cost = 100.0
    notes = None


class WorkOrderMaterialFactory(DictFactory):
    """Factory for work order material data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    work_order_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    spare_id = None
    item_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    description = Faker('word')
    quantity_required = 2.0
    quantity_used = 2.0
    unit_cost = 25.0
    total_cost = 50.0


class PMScheduleFactory(DictFactory):
    """Factory for PM schedule data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    pm_id = Sequence(lambda n: f"PM-{n:08d}")
    name = Faker('sentence', nb_words=4)
    description = Faker('sentence')
    asset_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    is_active = True
    trigger_type = "calendar"
    frequency_days = 30
    day_of_week = None
    day_of_month = None
    meter_id = None
    meter_interval = None
    lead_time_days = 7
    work_window_days = 7
    last_completed = None
    next_due_date = factory.LazyFunction(lambda: (datetime.utcnow() + timedelta(days=30)).date())
    priority = "medium"
    estimated_hours = 2.0
    estimated_cost = 200.0
    work_center_id = None
    instructions = Faker('paragraph')
    checklist = []
    spares_required = []
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


# =============================================================================
# QMS Factories (Quality Management)
# =============================================================================

class DocumentFactory(DictFactory):
    """Factory for controlled document data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    document_number = Sequence(lambda n: f"DOC-{datetime.utcnow().strftime('%Y%m%d')}-{n:04d}")
    title = Faker('sentence', nb_words=5)
    description = Faker('paragraph')
    document_type = "procedure"
    category_id = None
    status = "draft"
    revision = "A"
    revision_date = None
    effective_date = None
    previous_version_id = None
    author_id = None
    owner_id = None
    department = "engineering"
    confidentiality = "internal"
    requires_training = False
    keywords = []
    metadata = {}
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


class DocumentApprovalFactory(DictFactory):
    """Factory for document approval data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    document_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    approval_type = "review"
    sequence = 1
    approver_id = Sequence(lambda n: f"approver_{n}")
    status = "pending"
    due_date = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(days=7))
    completed_date = None
    signature_meaning = None
    signature_timestamp = None
    signature_hash = None
    ip_address = None
    comments = None
    rejection_reason = None


class NCRFactory(DictFactory):
    """Factory for non-conformance report data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    ncr_number = Sequence(lambda n: f"NCR-{datetime.utcnow().strftime('%Y%m%d')}-{n:04d}")
    ncr_type = "product"
    severity = "minor"
    status = "draft"
    title = Faker('sentence', nb_words=6)
    description = Faker('paragraph')
    detected_date = factory.LazyFunction(lambda: datetime.utcnow().date())
    detected_by = Sequence(lambda n: f"inspector_{n}")
    detection_location = "incoming_inspection"
    detection_stage = "receiving"
    item_id = None
    lot_number = None
    work_order_id = None
    quantity_affected = 10.0
    vendor_id = None
    customer_id = None
    disposition = None
    disposition_reason = None
    disposition_approved_by = None
    disposition_date = None
    target_close_date = factory.LazyFunction(lambda: (datetime.utcnow() + timedelta(days=14)).date())
    actual_close_date = None
    estimated_cost = 500.0
    actual_cost = None
    capa_required = False
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


class CAPAFactory(DictFactory):
    """Factory for CAPA (Corrective and Preventive Action) data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    capa_number = Sequence(lambda n: f"CAPA-{datetime.utcnow().strftime('%Y%m%d')}-{n:04d}")
    capa_type = "corrective"
    status = "draft"
    priority = "medium"
    ncr_id = None
    source_type = "ncr"
    source_reference = None
    title = Faker('sentence', nb_words=6)
    problem_statement = Faker('paragraph')
    scope = Faker('sentence')
    root_cause = None
    root_cause_method = None
    owner_id = Sequence(lambda n: f"owner_{n}")
    owner_department = "quality"
    target_completion_date = factory.LazyFunction(lambda: (datetime.utcnow() + timedelta(days=30)).date())
    actual_completion_date = None
    is_effective = None
    effectiveness_result = None
    effectiveness_reviewed_by = None
    effectiveness_review_date = None
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


class CAPAActionFactory(DictFactory):
    """Factory for CAPA action data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    capa_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    action_number = Sequence(lambda n: n + 1)
    action_type = "short_term"
    description = Faker('sentence')
    assigned_to = Sequence(lambda n: f"assignee_{n}")
    assigned_department = "engineering"
    target_date = factory.LazyFunction(lambda: (datetime.utcnow() + timedelta(days=14)).date())
    completed_date = None
    status = "pending"
    completion_notes = None
    evidence = []
    verification_required = True
    verified_by = None
    verification_date = None


# =============================================================================
# OEE Factories (Overall Equipment Effectiveness)
# =============================================================================

class DowntimeEventFactory(DictFactory):
    """Factory for downtime event data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    machine_id = Sequence(lambda n: f"MCH-{n:04d}")
    start_time = factory.LazyFunction(datetime.utcnow)
    end_time = factory.LazyFunction(lambda: datetime.utcnow() + timedelta(minutes=30))
    duration_minutes = 30.0
    reason = "mechanical_failure"
    planned = False
    description = Faker('sentence')
    reported_by = "operator"


class ProductionCountFactory(DictFactory):
    """Factory for production count data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    machine_id = Sequence(lambda n: f"MCH-{n:04d}")
    shift_date = factory.LazyFunction(lambda: datetime.utcnow().date())
    shift = "day"
    total_count = 1000
    good_count = 950
    reject_count = 30
    rework_count = 20
    run_time_minutes = 420.0
    ideal_cycle_time_seconds = 30.0


class OEERecordFactory(DictFactory):
    """Factory for OEE record data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    machine_id = Sequence(lambda n: f"MCH-{n:04d}")
    record_date = factory.LazyFunction(lambda: datetime.utcnow().date())
    shift = None
    scheduled_time = 480.0
    operating_time = 420.0
    net_operating_time = 400.0
    planned_downtime = 30.0
    unplanned_downtime = 30.0
    changeover_time = 20.0
    total_count = 1000
    good_count = 950
    ideal_cycle_time = 30.0
    availability = 0.875
    performance = 0.95
    quality = 0.95
    oee = 0.79


# =============================================================================
# ERP Factories (Extended)
# =============================================================================

class SalesOrderFactory(DictFactory):
    """Factory for sales order data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    order_number = Sequence(lambda n: f"SO-{datetime.utcnow().strftime('%Y%m%d')}-{n:04d}")
    customer_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    status = "draft"
    order_date = factory.LazyFunction(lambda: datetime.utcnow().date())
    requested_date = factory.LazyFunction(lambda: (datetime.utcnow() + timedelta(days=14)).date())
    promised_date = None
    currency = "USD"
    subtotal = 1000.0
    tax_amount = 80.0
    discount_amount = 0.0
    total = 1080.0
    shipping_method = "ground"
    payment_terms = "net_30"
    notes = None
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


class SalesOrderLineFactory(DictFactory):
    """Factory for sales order line data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    order_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    line_number = Sequence(lambda n: n + 1)
    item_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    description = Faker('word')
    quantity_ordered = 10.0
    quantity_shipped = 0.0
    uom = "EA"
    unit_price = 100.0
    discount_percent = 0.0
    line_total = 1000.0


class PurchaseOrderFactory(DictFactory):
    """Factory for purchase order data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    po_number = Sequence(lambda n: f"PO-{datetime.utcnow().strftime('%Y%m%d')}-{n:04d}")
    vendor_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    status = "draft"
    order_date = factory.LazyFunction(lambda: datetime.utcnow().date())
    required_date = factory.LazyFunction(lambda: (datetime.utcnow() + timedelta(days=14)).date())
    currency = "USD"
    subtotal = 5000.0
    tax_amount = 400.0
    discount_amount = 0.0
    freight_amount = 100.0
    total = 5500.0
    shipping_method = "freight"
    payment_terms = "net_30"
    buyer_id = None
    notes = None
    approved_by = None
    approved_date = None
    quantity_received = 0.0
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
    created_by = "system"


class PurchaseOrderLineFactory(DictFactory):
    """Factory for purchase order line data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    order_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    line_number = Sequence(lambda n: n + 1)
    item_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    vendor_part_number = None
    description = Faker('word')
    quantity_ordered = 100.0
    quantity_received = 0.0
    quantity_rejected = 0.0
    uom = "EA"
    unit_price = 50.0
    discount_percent = 0.0
    line_total = 5000.0
    required_date = None
    notes = None


class PartnerFactory(DictFactory):
    """Factory for partner (customer/vendor) data."""

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    partner_id = Sequence(lambda n: f"PTR-{n:06d}")
    name = Faker('company')
    partner_type = "both"
    status = "active"
    tax_id = Sequence(lambda n: f"TAX-{n:09d}")
    currency = "USD"
    payment_terms = "net_30"
    credit_limit = 50000.0
    is_deleted = False
    created_at = factory.LazyFunction(datetime.utcnow)
