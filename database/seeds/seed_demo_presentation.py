"""
LEGO Factory v3 - Full Demo Presentation Seeder
=================================================
Creates a rich, realistic dataset for demo screenshots:
  - 30+ work orders across all statuses
  - 80+ scheduled jobs for a packed Gantt chart
  - Jobs spread across all machines with realistic timing
  - Mix of completed, running, queued, and upcoming work

Run inside Docker:
    docker compose exec app python -m database.seeds.seed_demo_presentation
"""

import os
import sys
import random
from datetime import datetime, timedelta
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from models.base import Base
from models.mes.work_orders import (
    WorkOrder, Operation, Job,
    WorkOrderStatus, JobStatus, OperationType,
)


def get_engine():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is required.")
    return create_engine(url)


# ---------------------------------------------------------------------------
# Products & routings
# ---------------------------------------------------------------------------
PRODUCTS = [
    {
        'id': 'brick_2x4_red', 'name': '2x4 Brick Red', 'recipe': 'RCP-001',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 110, 8, ['bambu-ps1', 'creality-cr30']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 12, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6', 'niryo-ned2']),
        ],
    },
    {
        'id': 'brick_2x4_blue', 'name': '2x4 Brick Blue', 'recipe': 'RCP-001',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'creality-cr30', 120, 10, ['creality-cr30', 'bambu-ps1']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 12, 3, ['niryo-ned2']),
            ('Pack & Label', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'brick_2x4_yellow', 'name': '2x4 Brick Yellow', 'recipe': 'RCP-001',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 115, 8, ['bambu-ps1', 'creality-cr30']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 12, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'brick_2x4_white', 'name': '2x4 Brick White', 'recipe': 'RCP-001',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'creality-cr30', 110, 8, ['creality-cr30', 'bambu-ps1']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 12, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 8, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'brick_2x2_red', 'name': '2x2 Brick Red', 'recipe': 'RCP-002',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 70, 6, ['bambu-ps1', 'creality-cr30']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 10, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 8, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'brick_2x2_blue', 'name': '2x2 Brick Blue', 'recipe': 'RCP-002',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'creality-cr30', 70, 6, ['creality-cr30', 'bambu-ps1']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 10, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 8, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'plate_1x4_white', 'name': '1x4 Plate White', 'recipe': 'RCP-003',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 55, 5, ['bambu-ps1', 'creality-cr30']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 8, 2, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 6, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'gear_8t_black', 'name': '8-Tooth Technic Gear', 'recipe': 'RCP-004',
        'routing': [
            ('SLA Print', OperationType.PRINTING_SLA, 'formlabs-3', 160, 15, ['formlabs-3']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 15, 5, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'gear_24t_grey', 'name': '24-Tooth Technic Gear', 'recipe': 'RCP-004',
        'routing': [
            ('SLA Print', OperationType.PRINTING_SLA, 'formlabs-3', 200, 15, ['formlabs-3']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 20, 5, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'baseplate_16x16_green', 'name': '16x16 Green Baseplate', 'recipe': 'RCP-005',
        'routing': [
            ('CNC Mill', OperationType.CNC_MILLING, 'bantam-explorer', 85, 12, ['bantam-explorer', 'coastrunner-cr1']),
            ('Deburr & Clean', OperationType.CUSTOM, 'coastrunner-cr1', 20, 5, ['coastrunner-cr1', 'labfab-runner']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 12, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'baseplate_32x32_grey', 'name': '32x32 Grey Baseplate', 'recipe': 'RCP-005',
        'routing': [
            ('CNC Mill', OperationType.CNC_MILLING, 'coastrunner-cr1', 140, 20, ['coastrunner-cr1', 'bantam-explorer']),
            ('Deburr', OperationType.CUSTOM, 'labfab-runner', 25, 5, ['labfab-runner']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 15, 5, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 12, 3, ['xarm-lite6']),
        ],
    },
    {
        'id': 'axle_4L_grey', 'name': 'Technic Axle 4L', 'recipe': 'RCP-006',
        'routing': [
            ('CNC Turn', OperationType.CNC_MILLING, 'rownd-lathe', 40, 8, ['rownd-lathe']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 8, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 6, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'axle_8L_grey', 'name': 'Technic Axle 8L', 'recipe': 'RCP-006',
        'routing': [
            ('CNC Turn', OperationType.CNC_MILLING, 'rownd-lathe', 55, 10, ['rownd-lathe']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 10, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 8, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'tile_1x2_white', 'name': '1x2 Smooth Tile', 'recipe': 'RCP-007',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 45, 5, ['bambu-ps1', 'creality-cr30']),
            ('Laser Engrave', OperationType.CUSTOM, 'longer-ray-laser', 12, 3, ['longer-ray-laser']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 8, 2, ['niryo-ned2']),
        ],
    },
    {
        'id': 'tile_2x2_printed', 'name': '2x2 Printed Tile', 'recipe': 'RCP-007',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'creality-cr30', 50, 5, ['creality-cr30', 'bambu-ps1']),
            ('Laser Print', OperationType.CUSTOM, 'longer-ray-laser', 18, 5, ['longer-ray-laser']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 8, 2, ['niryo-ned2']),
        ],
    },
    {
        'id': 'minifig_torso', 'name': 'Custom Minifig Torso', 'recipe': 'RCP-008',
        'routing': [
            ('SLA Print', OperationType.PRINTING_SLA, 'formlabs-3', 130, 12, ['formlabs-3']),
            ('Laser Detail', OperationType.CUSTOM, 'longer-ray-laser', 20, 5, ['longer-ray-laser']),
            ('Assembly', OperationType.ASSEMBLY, 'niryo-ned2', 15, 5, ['niryo-ned2', 'xarm-lite6']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 12, 3, ['niryo-ned2']),
        ],
    },
    {
        'id': 'pin_connector', 'name': 'Technic Pin Connector', 'recipe': 'RCP-009',
        'routing': [
            ('CNC Mill', OperationType.CNC_MILLING, 'labfab-runner', 35, 8, ['labfab-runner', 'bantam-explorer']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 8, 2, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 6, 2, ['xarm-lite6']),
        ],
    },
    {
        'id': 'slope_2x2_red', 'name': '2x2 Slope Brick Red', 'recipe': 'RCP-010',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 80, 8, ['bambu-ps1', 'creality-cr30']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 10, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 8, 2, ['xarm-lite6']),
        ],
    },
]

CUSTOMERS = ['CUST001', 'CUST002', 'CUST003']
WORKERS = ['EMP001', 'EMP002', 'EMP003', 'EMP004']
SALES_ORDERS = ['SO-2026-101', 'SO-2026-102', 'SO-2026-103', 'SO-2026-104', 'SO-2026-105']


def clear_demo_data(session):
    """Remove previously seeded demo WO/job data so we can re-run cleanly."""
    from models.qms.supplier_quality import InspectionRecord, InspectionMeasurement

    # Delete jobs, then operations, then work orders that start with our demo prefixes
    prefixes = ('WO-2026-C', 'WO-2026-P', 'WO-2026-R', 'WO-2026-F', 'WO-2026-D', 'WO-2026-U')
    for prefix in prefixes:
        wos = session.query(WorkOrder).filter(WorkOrder.work_order_id.like(f'{prefix}%')).all()
        for wo in wos:
            # Delete QMS records that reference this WO (child tables first)
            insp_records = session.query(InspectionRecord).filter(
                InspectionRecord.work_order_id == wo.id
            ).all()
            for ir in insp_records:
                session.query(InspectionMeasurement).filter(
                    InspectionMeasurement.record_id == ir.id
                ).delete()
            session.query(InspectionRecord).filter(
                InspectionRecord.work_order_id == wo.id
            ).delete()
            # Delete records that reference jobs in this WO
            from models.mes.oee import DowntimeEvent, ProductionCount
            from models.mes.labor import TimeEntry
            from models.mes.operations import ScrapEvent
            job_ids = [j.id for j in session.query(Job).filter(Job.work_order_id == wo.id).all()]
            if job_ids:
                session.query(ScrapEvent).filter(ScrapEvent.job_id.in_(job_ids)).delete(synchronize_session='fetch')
                session.query(DowntimeEvent).filter(DowntimeEvent.job_id.in_(job_ids)).delete(synchronize_session='fetch')
                session.query(ProductionCount).filter(ProductionCount.job_id.in_(job_ids)).delete(synchronize_session='fetch')
                session.query(TimeEntry).filter(TimeEntry.job_id.in_(job_ids)).delete(synchronize_session='fetch')
            # Now delete MES children
            session.query(Job).filter(Job.work_order_id == wo.id).delete()
            session.query(Operation).filter(Operation.work_order_id == wo.id).delete()
            session.delete(wo)
    session.commit()
    print("  Cleared previous demo data")


def create_work_order(session, wo_id, product, qty, status, priority, planned_start,
                      due_date, customer_id, qty_completed=0, actual_start=None, actual_end=None):
    """Create a work order with operations and jobs."""

    wo = WorkOrder(
        work_order_id=wo_id,
        description=f"Production: {product['name']}",
        product_id=product['id'],
        recipe_id=product['recipe'],
        quantity_ordered=qty,
        quantity_completed=qty_completed,
        status=status,
        priority=priority,
        planned_start=planned_start,
        planned_end=due_date,
        due_date=due_date,
        actual_start=actual_start,
        actual_end=actual_end,
        customer_id=customer_id,
        sales_order_id=random.choice(SALES_ORDERS),
    )
    session.add(wo)
    session.flush()
    return wo


def _get_material_type(op_type, op_name, product_id):
    """Derive material type from operation and product — maps to actual MaterialLot types."""
    if 'fdm' in op_type.value:
        return 'PLA'
    if 'sla' in op_type.value:
        return 'Resin'
    if op_type == OperationType.CNC_MILLING:
        # Baseplates use ABS sheet, axles/connectors use Nylon rod
        if 'baseplate' in product_id:
            return 'ABS'
        return 'Nylon'
    if op_type == OperationType.INSPECTION:
        return None  # Inspection doesn't consume material
    if op_type == OperationType.PACKAGING:
        return 'Packaging'
    if op_type == OperationType.ASSEMBLY:
        return None
    # Laser, custom ops — don't consume raw material directly
    return None


def create_ops_and_jobs(session, wo, product, status, time_anchor, job_counter,
                        machine_availability):
    """Create operations and corresponding jobs for a work order.

    ``machine_availability`` is a dict[str, datetime] tracking the next
    available time for each machine.  Each job is scheduled to start no
    earlier than the machine becomes free, guaranteeing no overlaps.
    """
    now = datetime.utcnow()
    cursor = time_anchor
    routing = product['routing']

    for seq_idx, (op_name, op_type, machine, run_mins, setup_mins, eligible) in enumerate(routing):
        seq = (seq_idx + 1) * 10

        # Determine operation/job status based on WO status and position in routing
        if status == WorkOrderStatus.COMPLETED:
            op_status = JobStatus.COMPLETED
        elif status == WorkOrderStatus.IN_PROGRESS:
            total_ops = len(routing)
            if seq_idx < total_ops // 2:
                op_status = JobStatus.COMPLETED
            elif seq_idx == total_ops // 2:
                op_status = JobStatus.RUNNING
            else:
                op_status = JobStatus.QUEUED
        elif status == WorkOrderStatus.RELEASED:
            op_status = JobStatus.QUEUED
        else:
            op_status = JobStatus.PENDING

        # --- Respect machine capacity: start no earlier than machine is free ---
        machine_free = machine_availability.get(machine, time_anchor)
        earliest = max(cursor, machine_free)

        op = Operation(
            work_order_id=wo.id,
            operation_id=f"{wo.work_order_id}-OP{seq}",
            sequence=seq,
            operation_type=op_type,
            name=op_name,
            machine_id=machine,
            eligible_machines=eligible,
            setup_time=setup_mins,
            run_time=run_mins,
            status=op_status,
            started_at=earliest if op_status in (JobStatus.RUNNING, JobStatus.COMPLETED) else None,
            completed_at=(earliest + timedelta(minutes=setup_mins + run_mins)) if op_status == JobStatus.COMPLETED else None,
        )
        session.add(op)
        session.flush()

        # Compute job timing — honour machine availability
        job_duration = setup_mins + run_mins + random.randint(0, 10)
        job_start = earliest + timedelta(minutes=random.randint(0, 5))
        job_end = job_start + timedelta(minutes=job_duration)

        if op_status == JobStatus.RUNNING:
            back = max(15, int(run_mins * 0.5))
            fwd = max(20, int(run_mins * 0.5))
            job_start = now - timedelta(minutes=random.randint(10, back))
            job_end = now + timedelta(minutes=random.randint(15, fwd))

        # Update machine availability to after this job finishes (+ small gap)
        gap = timedelta(minutes=random.randint(3, 10))
        machine_availability[machine] = job_end + gap

        job_counter[0] += 1

        if op_status == JobStatus.COMPLETED:
            j_qty_c = wo.quantity_ordered
            j_qty_r = random.randint(0, max(1, int(wo.quantity_ordered * 0.02)))
        elif op_status == JobStatus.RUNNING:
            j_qty_c = int(wo.quantity_ordered * random.uniform(0.25, 0.65))
            j_qty_r = random.randint(0, 3)
        else:
            j_qty_c = 0
            j_qty_r = 0

        job = Job(
            job_id=f"JOB-2026-{job_counter[0]:04d}",
            work_order_id=wo.id,
            operation_id=op.id,
            machine_id=machine,
            scheduled_start=job_start,
            scheduled_end=job_end,
            actual_start=job_start if op_status in (JobStatus.RUNNING, JobStatus.COMPLETED) else None,
            actual_end=job_end if op_status == JobStatus.COMPLETED else None,
            status=op_status,
            priority_score=float(10 - wo.priority),
            quantity_planned=wo.quantity_ordered,
            quantity_completed=j_qty_c,
            quantity_rejected=j_qty_r,
            assigned_worker_id=random.choice(WORKERS),
            runtime_data={
                'operation_name': op_name,
                'operation_type': op_type.value,
                'eligible_machines': eligible,
                'estimated_duration_mins': setup_mins + run_mins,
                'setup_time_mins': setup_mins,
                'material_type': _get_material_type(op_type, op_name, wo.product_id),
            },
        )
        session.add(job)

        # Advance the WO cursor so the next operation starts after this one
        cursor = job_end + timedelta(minutes=random.randint(5, 15))


def seed_presentation(session):
    """Create all demo data."""
    now = datetime.utcnow()
    job_counter = [0]
    # Track when each machine is next available — shared across ALL work orders
    machine_availability = {}

    clear_demo_data(session)

    # =========================================================================
    # COMPLETED — finished in the last 12-36 hours
    # =========================================================================
    completed_orders = [
        ('WO-2026-C001', PRODUCTS[0],  200,  3, -28, -4),   # 2x4 Red
        ('WO-2026-C002', PRODUCTS[1],  350,  4, -32, -8),   # 2x4 Blue
        ('WO-2026-C003', PRODUCTS[6],  500,  5, -24, -6),   # 1x4 Plate
        ('WO-2026-C004', PRODUCTS[11], 250,  3, -20, -3),   # Axle 4L
        ('WO-2026-C005', PRODUCTS[4],  400,  4, -26, -5),   # 2x2 Red
        ('WO-2026-C006', PRODUCTS[13], 600,  5, -30, -7),   # 1x2 Tile
        ('WO-2026-C007', PRODUCTS[9],   60,  2, -36, -10),  # 16x16 Baseplate
        ('WO-2026-C008', PRODUCTS[7],  150,  3, -22, -2),   # 8T Gear
    ]

    for wo_id, prod, qty, pri, start_h, end_h in completed_orders:
        start = now + timedelta(hours=start_h)
        end = now + timedelta(hours=end_h)
        wo = create_work_order(
            session, wo_id, prod, qty, WorkOrderStatus.COMPLETED, pri,
            planned_start=start, due_date=end, customer_id=random.choice(CUSTOMERS),
            qty_completed=qty, actual_start=start, actual_end=end
        )
        create_ops_and_jobs(session, wo, prod, WorkOrderStatus.COMPLETED, start, job_counter, machine_availability)
        print(f"  + {wo_id} COMPLETED  {prod['name']} x{qty}")

    # =========================================================================
    # IN PROGRESS — actively running right now
    # =========================================================================
    in_progress_orders = [
        ('WO-2026-P001', PRODUCTS[0],  300,  1, -6,  36),   # 2x4 Red - HIGH PRI
        ('WO-2026-P002', PRODUCTS[2],  250,  2, -8,  24),   # 2x4 Yellow
        ('WO-2026-P003', PRODUCTS[5],  400,  2, -5,  18),   # 2x2 Blue
        ('WO-2026-P004', PRODUCTS[7],  100,  1, -4,  12),   # 8T Gear - URGENT
        ('WO-2026-P005', PRODUCTS[9],   80,  3, -10, 30),   # 16x16 Baseplate
        ('WO-2026-P006', PRODUCTS[15], 60,   2, -3,  20),   # Minifig Torso
        ('WO-2026-P007', PRODUCTS[10],  40,  3, -12, 36),   # 32x32 Baseplate
        ('WO-2026-P008', PRODUCTS[12],  200, 2, -4,  16),   # Axle 8L
        ('WO-2026-P009', PRODUCTS[14], 350,  3, -7,  24),   # 2x2 Printed Tile
        ('WO-2026-P010', PRODUCTS[17], 500,  2, -6,  20),   # 2x2 Slope Red
    ]

    for wo_id, prod, qty, pri, start_h, due_h in in_progress_orders:
        start = now + timedelta(hours=start_h)
        due = now + timedelta(hours=due_h)
        pct = random.uniform(0.15, 0.65)
        wo = create_work_order(
            session, wo_id, prod, qty, WorkOrderStatus.IN_PROGRESS, pri,
            planned_start=start, due_date=due, customer_id=random.choice(CUSTOMERS),
            qty_completed=int(qty * pct), actual_start=start
        )
        create_ops_and_jobs(session, wo, prod, WorkOrderStatus.IN_PROGRESS, start, job_counter, machine_availability)
        print(f"  + {wo_id} IN_PROGRESS {prod['name']} x{qty}")

    # =========================================================================
    # RELEASED — scheduled, ready to start in the next hours
    # =========================================================================
    released_orders = [
        ('WO-2026-R001', PRODUCTS[3],  500,  3, 1,   48),   # 2x4 White
        ('WO-2026-R002', PRODUCTS[4],  600,  4, 2,   60),   # 2x2 Red
        ('WO-2026-R003', PRODUCTS[6],  800,  3, 3,   72),   # 1x4 Plate
        ('WO-2026-R004', PRODUCTS[8],  120,  2, 1,   36),   # 24T Gear
        ('WO-2026-R005', PRODUCTS[11], 300,  4, 4,   48),   # Axle 4L
        ('WO-2026-R006', PRODUCTS[13], 450,  3, 2,   40),   # 1x2 Tile
        ('WO-2026-R007', PRODUCTS[16], 200,  4, 5,   60),   # Pin Connector
        ('WO-2026-R008', PRODUCTS[1],  350,  3, 3,   54),   # 2x4 Blue
    ]

    for wo_id, prod, qty, pri, start_h, due_h in released_orders:
        start = now + timedelta(hours=start_h)
        due = now + timedelta(hours=due_h)
        wo = create_work_order(
            session, wo_id, prod, qty, WorkOrderStatus.RELEASED, pri,
            planned_start=start, due_date=due, customer_id=random.choice(CUSTOMERS)
        )
        create_ops_and_jobs(session, wo, prod, WorkOrderStatus.RELEASED, start, job_counter, machine_availability)
        print(f"  + {wo_id} RELEASED    {prod['name']} x{qty}")

    # =========================================================================
    # PLANNED — future work (next 2-5 days)
    # =========================================================================
    planned_orders = [
        ('WO-2026-F001', PRODUCTS[0],  1000, 5, 36, 120),   # 2x4 Red - big batch
        ('WO-2026-F002', PRODUCTS[2],   800, 4, 48, 144),   # 2x4 Yellow
        ('WO-2026-F003', PRODUCTS[7],   200, 3, 40,  96),   # 8T Gear
        ('WO-2026-F004', PRODUCTS[10],   50, 4, 60, 168),   # 32x32 Baseplate
        ('WO-2026-F005', PRODUCTS[15],  100, 3, 42, 120),   # Minifig Torso
        ('WO-2026-F006', PRODUCTS[5],   600, 5, 72, 168),   # 2x2 Blue
    ]

    for wo_id, prod, qty, pri, start_h, due_h in planned_orders:
        start = now + timedelta(hours=start_h)
        due = now + timedelta(hours=due_h)
        wo = create_work_order(
            session, wo_id, prod, qty, WorkOrderStatus.PLANNED, pri,
            planned_start=start, due_date=due, customer_id=random.choice(CUSTOMERS)
        )
        create_ops_and_jobs(session, wo, prod, WorkOrderStatus.PLANNED, start, job_counter, machine_availability)
        print(f"  + {wo_id} PLANNED     {prod['name']} x{qty}")

    # =========================================================================
    # URGENT / RUSH — released orders with very tight due dates
    # These create interesting optimizer trade-offs:
    #   - Makespan objective: parallelize across machines
    #   - Due Date objective: prioritize these first, potentially serializing
    #   - Setup Time objective: group by material type, risking missed deadlines
    # =========================================================================
    urgent_orders = [
        # --- FDM contention: 4 orders all need bambu-ps1 or creality-cr30 ---
        ('WO-2026-U001', PRODUCTS[0],  150, 1, 0.5, 4),    # 2x4 Red - RUSH due in 4h
        ('WO-2026-U002', PRODUCTS[2],  200, 1, 0.5, 5),    # 2x4 Yellow - RUSH due in 5h
        ('WO-2026-U003', PRODUCTS[4],  250, 1, 0.5, 3),    # 2x2 Red - RUSH due in 3h!
        ('WO-2026-U004', PRODUCTS[17], 300, 1, 0.5, 6),    # 2x2 Slope Red - RUSH due in 6h

        # --- SLA contention: 2 orders both need formlabs-3 (single machine!) ---
        ('WO-2026-U005', PRODUCTS[7],   80, 1, 0.5, 5),    # 8T Gear - RUSH, SLA only
        ('WO-2026-U006', PRODUCTS[15],  40, 1, 0.5, 6),    # Minifig Torso - RUSH, SLA only

        # --- CNC contention: 3 orders across lathe & mills ---
        ('WO-2026-U007', PRODUCTS[11], 200, 1, 0.5, 4),    # Axle 4L - RUSH, rownd-lathe only
        ('WO-2026-U008', PRODUCTS[12], 150, 1, 0.5, 5),    # Axle 8L - RUSH, rownd-lathe only
        ('WO-2026-U009', PRODUCTS[9],   30, 1, 0.5, 7),    # 16x16 Baseplate - RUSH, CNC

        # --- Mixed: these have longer routings, compete for inspection/packaging ---
        ('WO-2026-U010', PRODUCTS[13], 400, 1, 0.5, 4),    # 1x2 Tile + laser - RUSH
        ('WO-2026-U011', PRODUCTS[14], 350, 1, 0.5, 5),    # 2x2 Printed Tile + laser - RUSH
        ('WO-2026-U012', PRODUCTS[16], 250, 2, 0.5, 8),    # Pin Connector - medium priority
    ]

    for wo_id, prod, qty, pri, start_h, due_h in urgent_orders:
        start = now + timedelta(hours=start_h)
        due = now + timedelta(hours=due_h)
        wo = create_work_order(
            session, wo_id, prod, qty, WorkOrderStatus.RELEASED, pri,
            planned_start=start, due_date=due, customer_id=random.choice(CUSTOMERS)
        )
        wo.notes = "RUSH ORDER - Customer escalation" if pri == 1 else "Expedited"
        create_ops_and_jobs(session, wo, prod, WorkOrderStatus.RELEASED, start, job_counter, machine_availability)
        print(f"  + {wo_id} URGENT      {prod['name']} x{qty}  (due in {due_h}h)")

    # =========================================================================
    # DRAFT — a couple in draft state
    # =========================================================================
    draft_orders = [
        ('WO-2026-D001', PRODUCTS[8],  300, 6, 96, 240),    # 24T Gear
        ('WO-2026-D002', PRODUCTS[3],  1500, 7, 120, 336),  # 2x4 White - big order
    ]

    for wo_id, prod, qty, pri, start_h, due_h in draft_orders:
        start = now + timedelta(hours=start_h)
        due = now + timedelta(hours=due_h)
        wo = create_work_order(
            session, wo_id, prod, qty, WorkOrderStatus.DRAFT, pri,
            planned_start=start, due_date=due, customer_id=random.choice(CUSTOMERS)
        )
        # Drafts have operations but no jobs
        for seq_idx, (op_name, op_type, machine, run_mins, setup_mins, eligible) in enumerate(prod['routing']):
            op = Operation(
                work_order_id=wo.id,
                operation_id=f"{wo_id}-OP{(seq_idx+1)*10}",
                sequence=(seq_idx + 1) * 10,
                operation_type=op_type,
                name=op_name,
                machine_id=machine,
                eligible_machines=eligible,
                setup_time=setup_mins,
                run_time=run_mins,
                status=JobStatus.PENDING,
            )
            session.add(op)
        print(f"  + {wo_id} DRAFT       {prod['name']} x{qty}")

    # =========================================================================
    # ON HOLD — one order on hold
    # =========================================================================
    prod = PRODUCTS[14]
    wo = create_work_order(
        session, 'WO-2026-P011', prod, 200, WorkOrderStatus.ON_HOLD, 3,
        planned_start=now - timedelta(hours=8), due_date=now + timedelta(hours=36),
        customer_id='CUST002', qty_completed=45,
        actual_start=now - timedelta(hours=8)
    )
    wo.notes = "ON HOLD: Waiting for filament restock (PLA White)"
    create_ops_and_jobs(session, wo, prod, WorkOrderStatus.IN_PROGRESS, now - timedelta(hours=8), job_counter, machine_availability)
    print(f"  + WO-2026-P011 ON_HOLD     {prod['name']} x200")

    session.commit()
    return job_counter[0]


def seed_maintenance_windows(session):
    """Create demo maintenance windows visible on the Gantt chart."""
    try:
        from models.mes.scheduling import MachineAvailability, MachineAvailabilityType
    except ImportError:
        print("  (Skipping maintenance windows — model not available)")
        return

    # Clear old demo maintenance windows
    session.query(MachineAvailability).filter(
        MachineAvailability.availability_type.in_([
            MachineAvailabilityType.MAINTENANCE,
            MachineAvailabilityType.DOWNTIME,
        ])
    ).delete(synchronize_session='fetch')

    now = datetime.utcnow()

    windows = [
        {
            'machine_id': 'creality-cr30',
            'availability_type': MachineAvailabilityType.MAINTENANCE,
            'start_datetime': now + timedelta(hours=5),
            'end_datetime': now + timedelta(hours=7),
            'reason': 'PM - Belt tension & calibration',
            'is_active': True,
        },
        {
            'machine_id': 'rownd-lathe',
            'availability_type': MachineAvailabilityType.MAINTENANCE,
            'start_datetime': now + timedelta(hours=10),
            'end_datetime': now + timedelta(hours=11, minutes=30),
            'reason': 'Tool change & inspection',
            'is_active': True,
        },
        {
            'machine_id': 'bambu-ps1',
            'availability_type': MachineAvailabilityType.DOWNTIME,
            'start_datetime': now + timedelta(hours=18),
            'end_datetime': now + timedelta(hours=20),
            'reason': 'Nozzle replacement',
            'is_active': True,
        },
    ]

    for w in windows:
        session.add(MachineAvailability(**w))

    session.commit()
    print(f"  + {len(windows)} maintenance windows seeded")


def seed_resource_data(session):
    """Seed resource status, tool inventory, material lots, and data collection events.

    Cross-references running jobs from the already-seeded work orders so the
    Resource Allocation page reflects live production activity.
    """
    import json as _json

    from models.mes.resources import (
        ResourceStatus, MachineStatus,
        ToolInventory, ToolStatus,
        MaterialLot, MaterialStatus,
    )
    from models.mes.sensor_data import DataCollectionEvent

    now = datetime.utcnow()

    # --- Clear previous resource seed data ---
    from models.mes.resources import MaterialReservation as MatRes
    session.query(DataCollectionEvent).delete(synchronize_session='fetch')
    session.query(ToolInventory).delete(synchronize_session='fetch')
    session.query(MatRes).delete(synchronize_session='fetch')
    session.query(MaterialLot).delete(synchronize_session='fetch')
    session.query(ResourceStatus).delete(synchronize_session='fetch')
    session.commit()
    print("  Cleared previous resource data")

    # --- Load machine config ---
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'config', 'machines.json')
    with open(config_path) as f:
        machines_cfg = _json.load(f)['machines']

    physical = [m for m in machines_cfg if m.get('machine_type') != 'virtual']

    # --- Cross-reference running jobs ---
    running_jobs = session.query(Job).filter(Job.status == JobStatus.RUNNING).all()
    job_by_machine = {}
    for j in running_jobs:
        job_by_machine[j.machine_id] = j

    # Build WO id→wo_id map for all work orders (needed for reservations too)
    all_wos = session.query(WorkOrder).all()
    wo_map = {wo.id: wo.work_order_id for wo in all_wos}

    # --- Default status assignment for machines without running jobs ---
    # Most idle, a few in specific states for demo variety
    special_status = {
        'longer-ray-laser': (MachineStatus.SETUP, 'Loading new material for tile engraving'),
        'niryo-conveyor': (MachineStatus.IDLE, None),
        'labfab-runner': (MachineStatus.MAINTENANCE, 'Scheduled PM - spindle bearings'),
    }

    resource_count = 0
    for m in physical:
        mid = m['machine_id']
        mname = m.get('name', mid)
        mtype = m.get('machine_type', '')
        job = job_by_machine.get(mid)

        if job:
            status = MachineStatus.RUNNING
            rd = job.runtime_data or {}
            elapsed = (now - job.actual_start).total_seconds() / 60 if job.actual_start else 0
            total = rd.get('estimated_duration_mins', 60)
            progress = min(95.0, (elapsed / max(total, 1)) * 100)
            est_complete = job.scheduled_end

            rs = ResourceStatus(
                machine_id=mid, machine_name=mname,
                status=status,
                current_job_id=job.job_id,
                current_work_order_id=wo_map.get(job.work_order_id, ''),
                current_operation_name=rd.get('operation_name', 'Production'),
                current_material_type=rd.get('material_type', 'Mixed'),
                utilization_1hr=round(random.uniform(75, 98), 1),
                utilization_8hr=round(random.uniform(60, 90), 1),
                utilization_24hr=round(random.uniform(50, 85), 1),
                is_connected=True, last_heartbeat=now - timedelta(seconds=random.randint(1, 15)),
                job_progress_pct=round(progress, 1),
                estimated_completion=est_complete,
            )
            # Set machine-type specific data
            if 'printer_3d' in mtype:
                rs.extruder_temp = round(random.uniform(195, 215), 1)
                rs.bed_temp = round(random.uniform(55, 65), 1)
            elif 'cnc' in mtype:
                rs.spindle_rpm = round(random.uniform(8000, 18000), 0)
        elif mid in special_status:
            st, note = special_status[mid]
            rs = ResourceStatus(
                machine_id=mid, machine_name=mname,
                status=st,
                utilization_1hr=round(random.uniform(5, 25), 1) if st != MachineStatus.MAINTENANCE else 0,
                utilization_8hr=round(random.uniform(20, 50), 1),
                utilization_24hr=round(random.uniform(30, 55), 1),
                is_connected=True, last_heartbeat=now - timedelta(seconds=random.randint(1, 30)),
            )
            if note:
                rs.extra_data = {'note': note}
        else:
            rs = ResourceStatus(
                machine_id=mid, machine_name=mname,
                status=MachineStatus.IDLE,
                utilization_1hr=round(random.uniform(0, 15), 1),
                utilization_8hr=round(random.uniform(25, 55), 1),
                utilization_24hr=round(random.uniform(35, 65), 1),
                is_connected=True, last_heartbeat=now - timedelta(seconds=random.randint(1, 20)),
            )
            if 'printer_3d' in mtype:
                rs.extruder_temp = round(random.uniform(22, 28), 1)  # ambient
                rs.bed_temp = round(random.uniform(22, 26), 1)

        session.add(rs)
        resource_count += 1

    session.flush()
    print(f"  + {resource_count} resource status records")

    # =========================================================================
    # Tool Inventory
    # =========================================================================
    tools_data = [
        # CNC end mills & drills
        ('TOOL-EM-001', 'end_mill', '3.175mm Flat End Mill', 'bantam-explorer', 3.175, 38.1, ToolStatus.IN_USE, 45, 120),
        ('TOOL-EM-002', 'end_mill', '6mm Flat End Mill', 'bantam-explorer', 6.0, 50.0, ToolStatus.AVAILABLE, 12, 120),
        ('TOOL-EM-003', 'end_mill', '1.5mm Ball End Mill', 'bantam-explorer', 1.5, 30.0, ToolStatus.WORN, 88, 100),
        ('TOOL-DR-001', 'drill', '2mm PCB Drill', 'bantam-explorer', 2.0, 25.0, ToolStatus.AVAILABLE, 5, 60),
        ('TOOL-EM-004', 'end_mill', '6mm Flat End Mill', 'coastrunner-cr1', 6.0, 50.0, ToolStatus.IN_USE, 30, 120),
        ('TOOL-EM-005', 'end_mill', '3mm Flat End Mill', 'coastrunner-cr1', 3.0, 38.0, ToolStatus.AVAILABLE, 15, 120),
        ('TOOL-EM-006', 'end_mill', '8mm Roughing Mill', 'labfab-runner', 8.0, 60.0, ToolStatus.MAINTENANCE, 0, 150),
        ('TOOL-EM-007', 'end_mill', '4mm Ball End Mill', 'labfab-runner', 4.0, 45.0, ToolStatus.AVAILABLE, 22, 120),
        ('TOOL-LT-001', 'lathe_tool', 'Carbide Turning Insert', 'rownd-lathe', 0, 0, ToolStatus.IN_USE, 55, 200),
        ('TOOL-LT-002', 'lathe_tool', 'Parting Tool 2mm', 'rownd-lathe', 2.0, 0, ToolStatus.AVAILABLE, 10, 150),
        # 3D printer nozzles
        ('TOOL-NZ-001', 'nozzle', '0.4mm Hardened Steel Nozzle', 'bambu-ps1', 0.4, 0, ToolStatus.IN_USE, 60, 500),
        ('TOOL-NZ-002', 'nozzle', '0.4mm Brass Nozzle', 'creality-cr30', 0.4, 0, ToolStatus.IN_USE, 72, 400),
        ('TOOL-NZ-003', 'nozzle', '0.6mm Brass Nozzle', None, 0.6, 0, ToolStatus.AVAILABLE, 0, 400),
        # Robot grippers
        ('TOOL-GR-001', 'gripper', 'Vacuum Gripper Pad', 'niryo-ned2', 0, 0, ToolStatus.IN_USE, 20, 1000),
        ('TOOL-GR-002', 'gripper', 'Parallel Jaw Gripper', 'xarm-lite6', 0, 0, ToolStatus.IN_USE, 15, 1000),
        ('TOOL-GR-003', 'gripper', 'Soft Finger Gripper', None, 0, 0, ToolStatus.AVAILABLE, 0, 1000),
    ]

    tool_count = 0
    for tid, ttype, tname, machine, diam, length, status, wear, life in tools_data:
        tool = ToolInventory(
            tool_id=tid, tool_type=ttype, tool_name=tname,
            machine_id=machine, diameter_mm=diam if diam else None,
            length_mm=length if length else None,
            status=status, wear_percent=wear,
            remaining_life_mins=max(0, life - (life * wear / 100)),
            total_cutting_time_mins=round(life * wear / 100, 1),
            expected_life_mins=life,
            installed_at=now - timedelta(days=random.randint(1, 30)) if machine else None,
            last_used_at=now - timedelta(hours=random.randint(1, 48)) if wear > 0 else None,
            storage_location='Tool Crib A' if not machine else None,
        )
        session.add(tool)
        tool_count += 1

    session.flush()
    print(f"  + {tool_count} tool inventory records")

    # =========================================================================
    # Material Lots — derived from actual PRODUCTS routings
    #
    # Products use:
    #   FDM printers → PLA 1.75mm filament (Red, Blue, Yellow, White)
    #   SLA printer  → Resin (Grey)
    #   CNC mills    → ABS sheet (baseplates), Nylon rod (axles, connectors)
    #   Packaging    → Bags & labels
    # =========================================================================
    from models.mes.resources import MaterialReservation

    materials_data = [
        # PLA 1.75mm filament — 1kg spools, used by bambu-ps1 & creality-cr30
        # Products: 2x4 Brick Red, 2x2 Brick Red, 2x2 Slope Red
        ('MAT-PLA-R01', 'PLA', 'PolyMaker PolyLite PLA 1.75mm Red', 'filament',
         'Red', '#E03030', 1000, 620, 'g', 'Bin-A1', 'PolyMaker', 'PML-R-2026-041',
         1.75, 195, 220, 55, 65),
        ('MAT-PLA-R02', 'PLA', 'PolyMaker PolyLite PLA 1.75mm Red', 'filament',
         'Red', '#E03030', 1000, 980, 'g', 'Bin-A1', 'PolyMaker', 'PML-R-2026-055',
         1.75, 195, 220, 55, 65),
        # Products: 2x4 Brick Blue, 2x2 Brick Blue
        ('MAT-PLA-B01', 'PLA', 'Hatchbox PLA 1.75mm Blue', 'filament',
         'Blue', '#3050D0', 1000, 430, 'g', 'Bin-A2', 'Hatchbox', 'HB-BLU-2026-112',
         1.75, 190, 215, 50, 60),
        # Products: 2x4 Brick Yellow
        ('MAT-PLA-Y01', 'PLA', 'Hatchbox PLA 1.75mm Yellow', 'filament',
         'Yellow', '#F0D020', 1000, 780, 'g', 'Bin-A3', 'Hatchbox', 'HB-YEL-2026-089',
         1.75, 190, 215, 50, 60),
        # Products: 2x4 Brick White, 1x4 Plate, 1x2 Tile, 2x2 Tile
        ('MAT-PLA-W01', 'PLA', 'PolyMaker PolyLite PLA 1.75mm White', 'filament',
         'White', '#F5F5F5', 1000, 75, 'g', 'Bin-A4', 'PolyMaker', 'PML-W-2026-033',
         1.75, 195, 220, 55, 65),   # LOW STOCK — heavy use from 4 products
        ('MAT-PLA-W02', 'PLA', 'PolyMaker PolyLite PLA 1.75mm White', 'filament',
         'White', '#F5F5F5', 1000, 940, 'g', 'Bin-A5', 'PolyMaker', 'PML-W-2026-060',
         1.75, 195, 220, 55, 65),   # Fresh replacement spool

        # Resin — 1L bottles for Formlabs Form 3
        # Products: 8T Gear, 24T Gear, Minifig Torso
        ('MAT-RES-G01', 'Resin', 'Formlabs Grey V5 Standard Resin 1L', 'resin',
         'Grey', '#808080', 1000, 540, 'ml', 'Bin-B1', 'Formlabs', 'FL-GV5-2026-003',
         None, None, None, None, None),
        ('MAT-RES-G02', 'Resin', 'Formlabs Grey V5 Standard Resin 1L', 'resin',
         'Grey', '#808080', 1000, 990, 'ml', 'Bin-B2', 'Formlabs', 'FL-GV5-2026-007',
         None, None, None, None, None),

        # ABS sheet stock — for CNC milling baseplates
        # Products: 16x16 Green Baseplate
        ('MAT-ABS-G01', 'ABS', 'ABS Sheet 300x200x6mm Green', 'sheet',
         'Green', '#4CAF50', 25, 14, 'pcs', 'Rack-C1', 'Curbell Plastics', 'CP-ABS-G-2026-018',
         None, None, None, None, None),
        # Products: 32x32 Grey Baseplate
        ('MAT-ABS-GY1', 'ABS', 'ABS Sheet 400x400x8mm Grey', 'sheet',
         'Grey', '#9E9E9E', 15, 9, 'pcs', 'Rack-C2', 'Curbell Plastics', 'CP-ABS-GY-2026-011',
         None, None, None, None, None),

        # Nylon rod — for CNC turned axles and milled connectors
        # Products: Axle 4L, Axle 8L
        ('MAT-NYL-R12', 'Nylon', 'Nylon 6/6 Rod 12mm x 300mm', 'rod',
         'Black', '#2C2C2C', 50, 28, 'pcs', 'Rack-C3', 'McMaster-Carr', 'MC-NYL12-2026-004',
         None, None, None, None, None),
        # Products: Pin Connector
        ('MAT-NYL-R08', 'Nylon', 'Nylon 6/6 Rod 8mm x 200mm', 'rod',
         'Black', '#2C2C2C', 40, 32, 'pcs', 'Rack-C4', 'McMaster-Carr', 'MC-NYL08-2026-009',
         None, None, None, None, None),

        # Packaging supplies — used by all products
        ('MAT-PKG-001', 'Packaging', 'Anti-static Parts Bag 50x70mm', 'packaging',
         'Clear', '#FFFFFF', 5000, 3200, 'pcs', 'Shelf-D1', 'Uline', 'UL-S-1036-2026',
         None, None, None, None, None),
        ('MAT-PKG-002', 'Packaging', 'Product ID Label Roll (1000ct)', 'packaging',
         'White', '#FFFFFF', 2000, 1450, 'pcs', 'Shelf-D2', 'Uline', 'UL-S-3847-2026',
         None, None, None, None, None),
    ]

    # Build lots and a lookup for reservation linking
    lot_objects = {}   # material_type → list of MaterialLot objects
    mat_count = 0
    for (lot_num, mtype, mname, cat, color, hex_c,
         qty_recv, qty_avail, uom, loc, supplier, supplier_lot,
         fil_diam, temp_min, temp_max, bed_min, bed_max) in materials_data:
        lot = MaterialLot(
            lot_number=lot_num, material_type=mtype, material_name=mname,
            material_category=cat, color=color, color_hex=hex_c,
            quantity_received=qty_recv, quantity_available=qty_avail,
            quantity_reserved=0, quantity_consumed=qty_recv - qty_avail,
            unit_of_measure=uom, status=MaterialStatus.AVAILABLE, location=loc,
            supplier=supplier, supplier_lot=supplier_lot,
            received_date=now - timedelta(days=random.randint(5, 60)),
            filament_diameter_mm=fil_diam, print_temp_min=temp_min,
            print_temp_max=temp_max, bed_temp_min=bed_min, bed_temp_max=bed_max,
            expiry_date=now + timedelta(days=random.randint(90, 365)) if cat == 'resin' else None,
        )
        session.add(lot)
        lot_objects.setdefault(mtype, []).append(lot)
        mat_count += 1

    session.flush()
    print(f"  + {mat_count} material lot records")

    # =========================================================================
    # Material Reservations — link active jobs to their material lots
    # =========================================================================
    active_jobs = session.query(Job).filter(
        Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
    ).all()

    reservation_count = 0
    for j in active_jobs:
        rd = j.runtime_data or {}
        mat_type = rd.get('material_type')
        if not mat_type or mat_type not in lot_objects:
            continue

        # Pick the lot with the most available quantity for this type
        lots_for_type = sorted(lot_objects[mat_type],
                               key=lambda l: l.quantity_available, reverse=True)
        lot = lots_for_type[0]

        # Reserve a realistic amount based on job quantity
        qty = j.quantity_planned or 10
        # Rough material per piece: filament ~5g, resin ~15ml, ABS ~1pc/piece, nylon ~1pc/2pieces
        per_piece = {'PLA': 5.0, 'Resin': 15.0, 'ABS': 1.0, 'Nylon': 0.5, 'Packaging': 1.0}
        reserve_qty = min(qty * per_piece.get(mat_type, 1.0), lot.quantity_available * 0.3)
        if reserve_qty <= 0:
            continue

        res = MaterialReservation(
            lot_id=lot.id,
            job_id=j.job_id,
            work_order_id=wo_map.get(j.work_order_id, ''),
            quantity_reserved=round(reserve_qty, 1),
            unit_of_measure=lot.unit_of_measure,
            reserved_by='scheduler',
        )
        session.add(res)
        lot.quantity_reserved = round((lot.quantity_reserved or 0) + reserve_qty, 1)
        reservation_count += 1

    session.flush()
    print(f"  + {reservation_count} material reservations")

    # =========================================================================
    # Data Collection Events (last 24 hours of machine activity)
    # =========================================================================
    events = []

    # Generate status change events for machines with running jobs
    for mid, job in job_by_machine.items():
        rd = job.runtime_data or {}
        start = job.actual_start or (now - timedelta(hours=1))
        events.append(DataCollectionEvent(
            timestamp=start,
            machine_id=mid, event_type='state_change',
            description=f"Machine started: {rd.get('operation_name', 'Production')}",
            previous_state='idle', new_state='running',
            job_id=job.job_id, work_order_id=wo_map.get(job.work_order_id, ''),
            severity='info', source='system',
        ))
        events.append(DataCollectionEvent(
            timestamp=start - timedelta(minutes=random.randint(1, 5)),
            machine_id=mid, event_type='material_loaded',
            description=f"Material loaded: {rd.get('material_type', 'Mixed')}",
            job_id=job.job_id, severity='info', source='operator',
            operator_id=random.choice(WORKERS),
        ))

    # Generate completed job events for recently completed jobs
    completed_jobs = session.query(Job).filter(
        Job.status == JobStatus.COMPLETED,
        Job.actual_end >= now - timedelta(hours=12)
    ).limit(8).all()

    for j in completed_jobs:
        rd = j.runtime_data or {}
        if j.actual_end:
            events.append(DataCollectionEvent(
                timestamp=j.actual_end,
                machine_id=j.machine_id, event_type='job_completed',
                description=f"Job completed: {rd.get('operation_name', 'Production')}",
                previous_state='running', new_state='idle',
                job_id=j.job_id, work_order_id=wo_map.get(j.work_order_id, ''),
                severity='info', source='system',
            ))

    # Maintenance event for labfab-runner
    events.append(DataCollectionEvent(
        timestamp=now - timedelta(hours=1),
        machine_id='labfab-runner', event_type='maintenance_started',
        description='Scheduled PM - spindle bearing inspection',
        previous_state='idle', new_state='maintenance',
        severity='info', source='operator', operator_id='EMP003',
    ))

    # Setup event for longer-ray-laser
    events.append(DataCollectionEvent(
        timestamp=now - timedelta(minutes=15),
        machine_id='longer-ray-laser', event_type='state_change',
        description='Setup: Loading acrylic sheet for tile engraving run',
        previous_state='idle', new_state='setup',
        severity='info', source='operator', operator_id='EMP001',
    ))

    # A couple connection events
    events.append(DataCollectionEvent(
        timestamp=now - timedelta(hours=6),
        machine_id='niryo-conveyor', event_type='connection_lost',
        description='Network timeout - auto-reconnecting',
        severity='warning', source='system',
    ))
    events.append(DataCollectionEvent(
        timestamp=now - timedelta(hours=6) + timedelta(seconds=12),
        machine_id='niryo-conveyor', event_type='connection_restored',
        description='Connection restored via rosbridge',
        severity='info', source='system',
    ))

    # Tool wear warning
    events.append(DataCollectionEvent(
        timestamp=now - timedelta(hours=3),
        machine_id='bantam-explorer', event_type='system_event',
        event_code='TOOL_WEAR_HIGH',
        description='Tool TOOL-EM-003 wear at 88% - replacement recommended',
        severity='warning', source='system',
    ))

    for ev in events:
        session.add(ev)

    session.commit()
    print(f"  + {len(events)} data collection events")


def seed_qms_data(session):
    """Seed realistic QMS (Quality Management System) data for demo.

    Creates inspection plans, inspection records, SPC charts, NCRs, CAPAs,
    audits, training courses/records, and calibrated equipment.
    """
    from datetime import date
    from models.qms.quality import (
        Audit, AuditFinding, TrainingCourse, TrainingRecord,
        CalibratedEquipment, CalibrationRecord, SPCChart, SPCData,
        AuditType, AuditStatus, FindingSeverity,
        TrainingStatus, CalibrationStatus,
    )
    from models.qms.ncr_capa import (
        NonConformanceReport, CAPA, CAPAAction,
        NCRType, NCRStatus, DispositionType, Severity,
        CAPAType, CAPAStatus,
    )
    from models.qms.supplier_quality import (
        InspectionPlan, InspectionCharacteristic, InspectionRecord,
        InspectionMeasurement, InspectionType, InspectionResult,
        CharacteristicType,
    )
    from models.mes.work_orders import WorkOrder

    now = datetime.utcnow()
    today = date.today()

    # ------------------------------------------------------------------
    # Clear old QMS data (child tables first to respect FK constraints)
    # ------------------------------------------------------------------
    session.query(InspectionMeasurement).delete(synchronize_session='fetch')
    session.query(InspectionRecord).delete(synchronize_session='fetch')
    session.query(InspectionCharacteristic).delete(synchronize_session='fetch')
    session.query(InspectionPlan).delete(synchronize_session='fetch')
    session.query(SPCData).delete(synchronize_session='fetch')
    session.query(SPCChart).delete(synchronize_session='fetch')
    session.query(CAPAAction).delete(synchronize_session='fetch')
    session.query(CAPA).delete(synchronize_session='fetch')
    session.query(NonConformanceReport).delete(synchronize_session='fetch')
    session.query(AuditFinding).delete(synchronize_session='fetch')
    session.query(Audit).delete(synchronize_session='fetch')
    session.query(TrainingRecord).delete(synchronize_session='fetch')
    session.query(TrainingCourse).delete(synchronize_session='fetch')
    session.query(CalibrationRecord).delete(synchronize_session='fetch')
    session.query(CalibratedEquipment).delete(synchronize_session='fetch')
    session.commit()
    print("  Cleared previous QMS data")

    # Build a lookup of work order string IDs to UUID PKs
    wo_lookup = {}
    for wo in session.query(WorkOrder).all():
        wo_lookup[wo.work_order_id] = wo.id

    # =====================================================================
    # 1. Inspection Plans (4) with characteristics
    # =====================================================================
    plan_data = [
        {
            'plan_id': 'IP-FDM-BRICK-001',
            'name': 'FDM Brick Dimensional Inspection',
            'description': 'Dimensional and weight inspection for FDM-printed 2x4 LEGO bricks.',
            'inspection_type': InspectionType.IN_PROCESS,
            'sampling_type': 'aql',
            'sample_size': 13,
            'aql_level': 'II',
            'characteristics': [
                ('Length', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 31.8, 0.2, 0.2, 31.6, 32.0, True, 'CAL-DIG-001', 'DWG-BRICK-2x4-R01'),
                ('Width', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 15.8, 0.2, 0.2, 15.6, 16.0, True, 'CAL-DIG-001', 'DWG-BRICK-2x4-R01'),
                ('Height', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 11.4, 0.15, 0.15, 11.25, 11.55, True, 'CAL-DIG-001', 'DWG-BRICK-2x4-R01'),
                ('Stud Diameter', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 4.85, 0.1, 0.1, 4.75, 4.95, True, 'CAL-DIG-002', 'DWG-BRICK-2x4-R01'),
                ('Weight', CharacteristicType.MATERIAL, 'variable', 'g', 2.30, 0.15, 0.15, 2.15, 2.45, False, 'CAL-BAL-001', None),
            ],
        },
        {
            'plan_id': 'IP-SLA-GEAR-001',
            'name': 'SLA Gear Inspection',
            'description': 'Dimensional and surface quality inspection for SLA-printed Technic gears.',
            'inspection_type': InspectionType.IN_PROCESS,
            'sampling_type': 'fixed',
            'sample_size': 8,
            'aql_level': None,
            'characteristics': [
                ('Tooth Profile', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 0.50, 0.05, 0.05, 0.45, 0.55, True, 'CAL-OPT-001', 'DWG-GEAR-8T-R02'),
                ('Bore Diameter', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 4.85, 0.10, 0.10, 4.75, 4.95, True, 'CAL-DIG-002', 'DWG-GEAR-8T-R02'),
                ('Overall Diameter', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 10.0, 0.15, 0.15, 9.85, 10.15, True, 'CAL-DIG-001', 'DWG-GEAR-8T-R02'),
                ('Surface Finish', CharacteristicType.VISUAL, 'attribute', 'Ra um', 1.6, 0.8, 0.0, 0.8, 2.4, False, 'CAL-SRF-001', 'DWG-GEAR-8T-R02'),
            ],
        },
        {
            'plan_id': 'IP-CNC-BASE-001',
            'name': 'CNC Baseplate Inspection',
            'description': 'Flatness, thickness, and stud-spacing inspection for CNC-milled baseplates.',
            'inspection_type': InspectionType.IN_PROCESS,
            'sampling_type': 'fixed',
            'sample_size': 5,
            'aql_level': None,
            'characteristics': [
                ('Flatness', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 0.0, 0.10, 0.0, 0.0, 0.10, True, 'CAL-SRF-001', 'DWG-BASE-16-R01'),
                ('Thickness', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 6.0, 0.10, 0.10, 5.9, 6.1, True, 'CAL-MIC-001', 'DWG-BASE-16-R01'),
                ('Stud Spacing', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 8.0, 0.05, 0.05, 7.95, 8.05, True, 'CAL-DIG-001', 'DWG-BASE-16-R01'),
                ('Edge Quality', CharacteristicType.VISUAL, 'attribute', None, None, None, None, None, None, False, None, 'DWG-BASE-16-R01'),
            ],
        },
        {
            'plan_id': 'IP-CNC-AXLE-001',
            'name': 'CNC Axle Inspection',
            'description': 'Dimensional and straightness inspection for CNC-turned Technic axles.',
            'inspection_type': InspectionType.IN_PROCESS,
            'sampling_type': 'aql',
            'sample_size': 8,
            'aql_level': 'II',
            'characteristics': [
                ('Diameter', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 4.85, 0.05, 0.05, 4.80, 4.90, True, 'CAL-MIC-001', 'DWG-AXLE-4L-R01'),
                ('Length', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 32.0, 0.20, 0.20, 31.80, 32.20, True, 'CAL-DIG-001', 'DWG-AXLE-4L-R01'),
                ('Straightness', CharacteristicType.DIMENSIONAL, 'variable', 'mm', 0.0, 0.05, 0.0, 0.0, 0.05, True, 'CAL-HGT-001', 'DWG-AXLE-4L-R01'),
                ('Surface Finish', CharacteristicType.VISUAL, 'attribute', 'Ra um', 0.8, 0.4, 0.0, 0.4, 1.2, False, 'CAL-SRF-001', 'DWG-AXLE-4L-R01'),
            ],
        },
    ]

    plan_objects = {}
    char_objects = {}
    for pd in plan_data:
        plan = InspectionPlan(
            plan_id=pd['plan_id'],
            name=pd['name'],
            description=pd['description'],
            inspection_type=pd['inspection_type'],
            sampling_type=pd['sampling_type'],
            sample_size=pd['sample_size'],
            aql_level=pd['aql_level'],
            is_active=True,
            effective_date=today - timedelta(days=90),
        )
        session.add(plan)
        session.flush()
        plan_objects[pd['plan_id']] = plan

        chars_for_plan = []
        for seq, (cname, ctype, mtype, uom, nom, tol_p, tol_m, lsl, usl, critical, gauge, dwg) in enumerate(pd['characteristics'], start=1):
            char = InspectionCharacteristic(
                plan_id=plan.id,
                sequence=seq,
                name=cname,
                characteristic_type=ctype,
                measurement_type=mtype,
                unit_of_measure=uom,
                nominal_value=nom,
                tolerance_plus=tol_p,
                tolerance_minus=tol_m,
                lower_spec_limit=lsl,
                upper_spec_limit=usl,
                is_critical=critical,
                gauge_id=gauge,
                drawing_reference=dwg,
            )
            session.add(char)
            chars_for_plan.append(char)

        session.flush()
        char_objects[pd['plan_id']] = chars_for_plan

    print(f"  + {len(plan_objects)} inspection plans with characteristics")

    # =====================================================================
    # 2. Inspection Records (12) from completed work orders
    # =====================================================================
    inspection_records_data = [
        # (record_id, wo_string_id, plan_id, inspector, hours_ago, disposition, defects)
        ('IR-2026-001', 'WO-2026-C001', 'IP-FDM-BRICK-001', 'EMP001', 26, InspectionResult.ACCEPT, 0),
        ('IR-2026-002', 'WO-2026-C002', 'IP-FDM-BRICK-001', 'EMP002', 30, InspectionResult.ACCEPT, 0),
        ('IR-2026-003', 'WO-2026-C003', 'IP-FDM-BRICK-001', 'EMP001', 22, InspectionResult.ACCEPT, 1),
        ('IR-2026-004', 'WO-2026-C004', 'IP-CNC-AXLE-001', 'EMP003', 18, InspectionResult.ACCEPT, 0),
        ('IR-2026-005', 'WO-2026-C005', 'IP-FDM-BRICK-001', 'EMP002', 24, InspectionResult.REJECT, 3),
        ('IR-2026-006', 'WO-2026-C006', 'IP-FDM-BRICK-001', 'EMP001', 28, InspectionResult.ACCEPT, 0),
        ('IR-2026-007', 'WO-2026-C007', 'IP-CNC-BASE-001', 'EMP003', 34, InspectionResult.ACCEPT, 0),
        ('IR-2026-008', 'WO-2026-C008', 'IP-SLA-GEAR-001', 'EMP004', 20, InspectionResult.ACCEPT, 0),
        ('IR-2026-009', 'WO-2026-C001', 'IP-FDM-BRICK-001', 'EMP002', 16, InspectionResult.CONDITIONAL, 1),
        ('IR-2026-010', 'WO-2026-C002', 'IP-FDM-BRICK-001', 'EMP001', 12, InspectionResult.ACCEPT, 0),
        ('IR-2026-011', 'WO-2026-C008', 'IP-SLA-GEAR-001', 'EMP004', 8, InspectionResult.REJECT, 2),
        ('IR-2026-012', 'WO-2026-C007', 'IP-CNC-BASE-001', 'EMP003', 6, InspectionResult.ACCEPT, 0),
    ]

    ir_objects = {}
    ir_count = 0
    for (rec_id, wo_str, plan_key, inspector, hrs_ago, disp, total_def) in inspection_records_data:
        wo_uuid = wo_lookup.get(wo_str)
        plan_obj = plan_objects[plan_key]
        ir = InspectionRecord(
            record_id=rec_id,
            inspection_type=plan_obj.inspection_type,
            plan_id=plan_obj.id,
            work_order_id=wo_uuid,
            lot_qty=float(random.randint(50, 500)),
            sample_qty=float(plan_obj.sample_size or 10),
            disposition=disp,
            total_defects=total_def,
            major_defects=min(total_def, random.randint(0, total_def)),
            minor_defects=0,
            critical_defects=0,
            inspector_id=inspector,
            inspection_date=now - timedelta(hours=hrs_ago),
            inspection_location='QC Station',
            notes='Routine in-process inspection.' if disp == InspectionResult.ACCEPT else 'Deviations noted, see measurements.',
        )
        # Distribute defects across major/minor
        if total_def > 0:
            ir.major_defects = max(1, total_def // 2)
            ir.minor_defects = total_def - ir.major_defects
        session.add(ir)
        session.flush()
        ir_objects[rec_id] = ir
        ir_count += 1

        # Create measurements for each characteristic in the plan
        chars = char_objects[plan_key]
        for char in chars:
            if char.measurement_type == 'variable' and char.nominal_value is not None:
                nom = char.nominal_value
                tol = char.tolerance_plus or 0.1
                # Most measurements are conforming; introduce occasional deviation for rejected records
                if disp == InspectionResult.REJECT and random.random() < 0.3:
                    measured = nom + random.uniform(tol * 1.1, tol * 2.0) * random.choice([-1, 1])
                    conforming = False
                else:
                    measured = round(nom + random.uniform(-tol * 0.8, tol * 0.8), 3)
                    conforming = True

                meas = InspectionMeasurement(
                    record_id=ir.id,
                    characteristic_id=char.id,
                    sequence=char.sequence,
                    characteristic_name=char.name,
                    measurement_type='variable',
                    measured_value=round(measured, 3),
                    nominal_value=nom,
                    lower_limit=char.lower_spec_limit,
                    upper_limit=char.upper_spec_limit,
                    deviation=round(measured - nom, 4),
                    is_conforming=conforming,
                    gauge_used=char.gauge_id,
                    sample_number=1,
                )
                session.add(meas)
            elif char.measurement_type == 'attribute':
                attr_pass = not (disp == InspectionResult.REJECT and random.random() < 0.2)
                meas = InspectionMeasurement(
                    record_id=ir.id,
                    characteristic_id=char.id,
                    sequence=char.sequence,
                    characteristic_name=char.name,
                    measurement_type='attribute',
                    attribute_result='pass' if attr_pass else 'fail',
                    defects_found=0 if attr_pass else 1,
                    is_conforming=attr_pass,
                    gauge_used=char.gauge_id,
                    sample_number=1,
                )
                session.add(meas)

    session.flush()
    print(f"  + {ir_count} inspection records with measurements")

    # =====================================================================
    # 3. SPC Charts (3) with data points
    # =====================================================================
    spc_charts_data = [
        {
            'chart_id': 'SPC-FDM-LEN-001',
            'name': 'FDM 2x4 Brick Length (bambu-ps1)',
            'description': 'X-bar R chart for 2x4 brick length on Bambu P1S.',
            'characteristic': 'Length',
            'unit_of_measure': 'mm',
            'chart_type': 'xbar_r',
            'subgroup_size': 5,
            'target': 31.8,
            'usl': 32.0,
            'lsl': 31.6,
            'ucl': 31.95,
            'lcl': 31.65,
            'center_line': 31.8,
            'ucl_r': 0.45,
            'lcl_r': 0.0,
            'center_line_r': 0.21,
            'machine_id': 'bambu-ps1',
            'nominal': 31.8,
            'std': 0.06,
        },
        {
            'chart_id': 'SPC-SLA-BORE-001',
            'name': 'SLA Gear Bore Diameter (formlabs-3)',
            'description': 'X-bar R chart for gear bore diameter on Formlabs Form 3.',
            'characteristic': 'Bore Diameter',
            'unit_of_measure': 'mm',
            'chart_type': 'xbar_r',
            'subgroup_size': 5,
            'target': 4.85,
            'usl': 4.95,
            'lsl': 4.75,
            'ucl': 4.92,
            'lcl': 4.78,
            'center_line': 4.85,
            'ucl_r': 0.22,
            'lcl_r': 0.0,
            'center_line_r': 0.10,
            'machine_id': 'formlabs-3',
            'nominal': 4.85,
            'std': 0.03,
        },
        {
            'chart_id': 'SPC-CNC-THK-001',
            'name': 'CNC Baseplate Thickness',
            'description': 'X-bar R chart for baseplate thickness on CNC mills.',
            'characteristic': 'Thickness',
            'unit_of_measure': 'mm',
            'chart_type': 'xbar_r',
            'subgroup_size': 5,
            'target': 6.0,
            'usl': 6.1,
            'lsl': 5.9,
            'ucl': 6.06,
            'lcl': 5.94,
            'center_line': 6.0,
            'ucl_r': 0.16,
            'lcl_r': 0.0,
            'center_line_r': 0.07,
            'machine_id': 'bantam-explorer',
            'nominal': 6.0,
            'std': 0.025,
        },
    ]

    spc_chart_objects = {}
    for sc in spc_charts_data:
        chart = SPCChart(
            chart_id=sc['chart_id'],
            name=sc['name'],
            description=sc['description'],
            characteristic=sc['characteristic'],
            unit_of_measure=sc['unit_of_measure'],
            chart_type=sc['chart_type'],
            subgroup_size=sc['subgroup_size'],
            target=sc['target'],
            usl=sc['usl'],
            lsl=sc['lsl'],
            ucl=sc['ucl'],
            lcl=sc['lcl'],
            center_line=sc['center_line'],
            ucl_r=sc['ucl_r'],
            lcl_r=sc['lcl_r'],
            center_line_r=sc['center_line_r'],
            machine_id=sc['machine_id'],
            is_active=True,
        )
        session.add(chart)
        session.flush()
        spc_chart_objects[sc['chart_id']] = (chart, sc)

    # Generate 25 data points per chart
    spc_data_count = 0
    for chart_id, (chart_obj, sc) in spc_chart_objects.items():
        nominal = sc['nominal']
        std = sc['std']
        subgroup_size = sc['subgroup_size']
        ucl = sc['ucl']
        lcl = sc['lcl']

        for i in range(25):
            sample_time = now - timedelta(hours=(25 - i) * 2)
            # Generate subgroup values, mostly in-control
            if i == 8:
                # Out-of-control high point
                vals = [round(nominal + random.gauss(std * 2.5, std * 0.3), 3) for _ in range(subgroup_size)]
            elif i == 19:
                # Out-of-control low point
                vals = [round(nominal - random.gauss(std * 2.5, std * 0.3), 3) for _ in range(subgroup_size)]
            else:
                vals = [round(random.gauss(nominal, std), 3) for _ in range(subgroup_size)]

            mean_val = round(sum(vals) / len(vals), 4)
            range_val = round(max(vals) - min(vals), 4)
            std_val = round((sum((v - mean_val) ** 2 for v in vals) / max(len(vals) - 1, 1)) ** 0.5, 4)
            in_ctrl = lcl <= mean_val <= ucl
            violations = []
            if mean_val > ucl:
                violations.append('Rule 1: Point above UCL')
            elif mean_val < lcl:
                violations.append('Rule 1: Point below LCL')

            wo_choices = ['WO-2026-C001', 'WO-2026-C002', 'WO-2026-C003', 'WO-2026-C004',
                          'WO-2026-C005', 'WO-2026-C006', 'WO-2026-C007', 'WO-2026-C008']
            spc_pt = SPCData(
                chart_id=chart_obj.id,
                subgroup_number=i + 1,
                sample_time=sample_time,
                values=vals,
                mean=mean_val,
                range_value=range_val,
                std_dev=std_val,
                in_control=in_ctrl,
                rule_violations=violations,
                operator_id=random.choice(WORKERS),
                work_order_id=random.choice(wo_choices),
                lot_number=f"LOT-2026-{random.randint(100, 999)}",
            )
            session.add(spc_pt)
            spc_data_count += 1

    session.flush()
    print(f"  + {len(spc_chart_objects)} SPC charts with {spc_data_count} data points")

    # =====================================================================
    # 4. NCRs (5)
    # =====================================================================
    ncr1 = NonConformanceReport(
        ncr_number='NCR-2026-001',
        ncr_type=NCRType.PRODUCT,
        severity=Severity.MAJOR,
        status=NCRStatus.CLOSED,
        title='2x4 Brick Red - Stud diameter out of spec (undersized)',
        description='During in-process inspection of WO-2026-C001, 12 out of 200 bricks showed stud diameter below LSL of 4.75mm. Root cause: worn nozzle on bambu-ps1 causing under-extrusion.',
        detected_date=today - timedelta(days=18),
        detected_by='EMP001',
        detection_location='QC Station',
        detection_stage='in_process',
        item_id='brick_2x4_red',
        work_order_id='WO-2026-C001',
        quantity_affected=12,
        quantity_inspected=200,
        containment_action='Segregated affected batch. 100% inspection of remaining production from bambu-ps1.',
        containment_date=now - timedelta(days=18, hours=2),
        containment_by='EMP001',
        investigation_lead='EMP003',
        root_cause='Nozzle wear on bambu-ps1 causing under-extrusion of stud features. Nozzle had exceeded recommended 500-hour service life.',
        root_cause_category='5Why',
        disposition=DispositionType.SCRAP,
        disposition_reason='Studs cannot be reworked; affected bricks do not meet clutch-power requirements.',
        disposition_approved_by='EMP003',
        disposition_date=now - timedelta(days=16),
        estimated_cost=24.0,
        actual_cost=28.50,
        target_close_date=today - timedelta(days=10),
        actual_close_date=today - timedelta(days=11),
        capa_required=True,
    )

    ncr2 = NonConformanceReport(
        ncr_number='NCR-2026-002',
        ncr_type=NCRType.PROCESS,
        severity=Severity.MINOR,
        status=NCRStatus.CLOSED,
        title='SLA Gear surface finish exceeds Ra limit',
        description='Batch of 8-tooth gears from WO-2026-C008 exhibited rough surface finish (Ra 3.2um vs limit 2.4um). Resin tank clouding identified.',
        detected_date=today - timedelta(days=12),
        detected_by='EMP004',
        detection_location='QC Station',
        detection_stage='in_process',
        item_id='gear_8t_black',
        work_order_id='WO-2026-C008',
        quantity_affected=8,
        quantity_inspected=150,
        containment_action='Quarantined affected lot. Replaced resin tank on formlabs-3.',
        containment_date=now - timedelta(days=12, hours=1),
        containment_by='EMP004',
        investigation_lead='EMP002',
        root_cause='Resin tank film (PDMS layer) was clouded from extended use, causing light scattering during cure.',
        root_cause_category='Fishbone',
        disposition=DispositionType.REWORK,
        disposition_reason='Re-cure under UV to improve surface finish within acceptable limits.',
        disposition_approved_by='EMP002',
        disposition_date=now - timedelta(days=10),
        estimated_cost=15.0,
        actual_cost=12.75,
        target_close_date=today - timedelta(days=5),
        actual_close_date=today - timedelta(days=6),
        capa_required=False,
    )

    ncr3 = NonConformanceReport(
        ncr_number='NCR-2026-003',
        ncr_type=NCRType.PRODUCT,
        severity=Severity.MAJOR,
        status=NCRStatus.DISPOSITION_APPROVED,
        title='CNC Baseplate thickness variation on bantam-explorer',
        description='16x16 baseplates from WO-2026-C007 showed thickness readings between 5.82mm and 5.88mm, below LSL of 5.9mm. Spindle Z-axis backlash suspected.',
        detected_date=today - timedelta(days=5),
        detected_by='EMP003',
        detection_location='CNC Area',
        detection_stage='in_process',
        item_id='baseplate_16x16_green',
        work_order_id='WO-2026-C007',
        quantity_affected=6,
        quantity_inspected=60,
        containment_action='Halted baseplate production on bantam-explorer. Routed remaining orders to coastrunner-cr1.',
        containment_date=now - timedelta(days=5, hours=3),
        containment_by='EMP003',
        investigation_lead='EMP003',
        root_cause='Z-axis ball screw backlash exceeding 0.08mm after extended high-speed milling runs.',
        root_cause_category='5Why',
        disposition=DispositionType.REWORK,
        disposition_reason='Re-machine thickness on coastrunner-cr1 to bring within spec. Acceptable for internal use if within 5.85-5.90mm.',
        disposition_approved_by='EMP002',
        disposition_date=now - timedelta(days=3),
        estimated_cost=45.0,
        actual_cost=None,
        target_close_date=today + timedelta(days=5),
        capa_required=True,
    )

    ncr4 = NonConformanceReport(
        ncr_number='NCR-2026-004',
        ncr_type=NCRType.INTERNAL,
        severity=Severity.MINOR,
        status=NCRStatus.UNDER_INVESTIGATION,
        title='Axle 4L diameter trend toward USL',
        description='SPC chart SPC-CNC-THK-001 flagged upward trend for axle diameters on rownd-lathe. Last 7 subgroups show mean above center line, approaching UCL.',
        detected_date=today - timedelta(days=2),
        detected_by='EMP003',
        detection_location='CNC Area',
        detection_stage='in_process',
        item_id='axle_4L_grey',
        work_order_id='WO-2026-C004',
        quantity_affected=0,
        quantity_inspected=250,
        containment_action='Increased SPC sampling frequency to every 30 minutes. Monitoring ongoing.',
        containment_date=now - timedelta(days=2, hours=1),
        containment_by='EMP003',
        investigation_lead='EMP003',
        root_cause=None,
        target_close_date=today + timedelta(days=10),
        capa_required=False,
    )

    ncr5 = NonConformanceReport(
        ncr_number='NCR-2026-005',
        ncr_type=NCRType.SUPPLIER,
        severity=Severity.MINOR,
        status=NCRStatus.SUBMITTED,
        title='PLA filament color inconsistency - Red lot PML-R-2026-055',
        description='New spool of PolyMaker PLA Red (lot PML-R-2026-055) shows noticeable color shift compared to reference standard. Delta-E measured at 4.2 (limit 3.0).',
        detected_date=today,
        detected_by='EMP001',
        detection_location='Incoming Inspection',
        detection_stage='incoming',
        item_id='brick_2x4_red',
        lot_number='PML-R-2026-055',
        quantity_affected=1000,
        quantity_inspected=1000,
        target_close_date=today + timedelta(days=14),
        capa_required=False,
    )

    for ncr in [ncr1, ncr2, ncr3, ncr4, ncr5]:
        session.add(ncr)
    session.flush()
    print(f"  + 5 non-conformance reports")

    # =====================================================================
    # 5. CAPAs (3) with actions
    # =====================================================================
    capa1 = CAPA(
        capa_number='CAPA-2026-001',
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.CLOSED,
        priority='high',
        ncr_id=ncr1.id,
        source_type='ncr',
        source_reference='NCR-2026-001',
        title='Implement nozzle life tracking and replacement schedule for FDM printers',
        problem_statement='Worn nozzle on bambu-ps1 caused under-extrusion resulting in undersized studs on 2x4 bricks. No preventive nozzle replacement schedule was in place.',
        owner_id='EMP003',
        owner_department='Maintenance',
        root_cause_method='5Why',
        root_cause='No nozzle wear tracking system. Operators relied on visual inspection which is unreliable for detecting gradual wear.',
        contributing_factors=['No tool life tracking for printer nozzles', 'No defined replacement interval', 'Visual-only wear assessment'],
        risk_before=16,
        risk_after=4,
        initiation_date=today - timedelta(days=16),
        target_completion_date=today - timedelta(days=5),
        actual_completion_date=today - timedelta(days=6),
        estimated_cost=200.0,
        actual_cost=175.0,
        is_effective=True,
    )
    session.add(capa1)
    session.flush()

    capa1_actions = [
        CAPAAction(
            capa_id=capa1.id,
            action_number=1,
            action_type='immediate',
            description='Replace nozzles on all FDM printers (bambu-ps1, creality-cr30) with new hardened steel nozzles.',
            assigned_to='EMP002',
            target_date=today - timedelta(days=14),
            completed_date=today - timedelta(days=14),
            status='completed',
            completion_notes='Replaced both nozzles. Calibration prints verified within spec.',
        ),
        CAPAAction(
            capa_id=capa1.id,
            action_number=2,
            action_type='short_term',
            description='Add nozzle wear tracking to CMMS. Set 400-hour replacement interval for hardened steel nozzles.',
            assigned_to='EMP003',
            target_date=today - timedelta(days=10),
            completed_date=today - timedelta(days=9),
            status='completed',
            completion_notes='PM schedule created: PM-NZ-001 for bambu-ps1, PM-NZ-002 for creality-cr30. 400hr interval.',
        ),
        CAPAAction(
            capa_id=capa1.id,
            action_number=3,
            action_type='long_term',
            description='Implement SPC monitoring for stud diameter on all FDM brick production. Auto-alert when Cpk drops below 1.33.',
            assigned_to='EMP001',
            target_date=today - timedelta(days=6),
            completed_date=today - timedelta(days=7),
            status='completed',
            completion_notes='SPC chart SPC-FDM-LEN-001 extended with stud diameter. Alert threshold set in SCADA.',
        ),
    ]

    capa2 = CAPA(
        capa_number='CAPA-2026-002',
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.IN_IMPLEMENTATION,
        priority='high',
        ncr_id=ncr3.id,
        source_type='ncr',
        source_reference='NCR-2026-003',
        title='Address Z-axis backlash on bantam-explorer CNC mill',
        problem_statement='Z-axis ball screw backlash on bantam-explorer exceeding 0.08mm causing baseplate thickness variations below LSL.',
        owner_id='EMP003',
        owner_department='Maintenance',
        root_cause_method='5Why',
        root_cause='Ball screw nut wear from extended high-feed milling operations without scheduled backlash checks.',
        contributing_factors=['No periodic backlash measurement in PM routine', 'High feed rates for baseplate roughing', 'Ball screw nut approaching end of life'],
        risk_before=20,
        risk_after=None,
        initiation_date=today - timedelta(days=4),
        target_completion_date=today + timedelta(days=10),
        estimated_cost=800.0,
    )
    session.add(capa2)
    session.flush()

    capa2_actions = [
        CAPAAction(
            capa_id=capa2.id,
            action_number=1,
            action_type='immediate',
            description='Order replacement ball screw nut assembly for bantam-explorer Z-axis (P/N BSN-Z-12-400).',
            assigned_to='EMP003',
            target_date=today - timedelta(days=2),
            completed_date=today - timedelta(days=3),
            status='completed',
            completion_notes='Ordered from MSC Industrial. Expected delivery in 5 business days.',
        ),
        CAPAAction(
            capa_id=capa2.id,
            action_number=2,
            action_type='short_term',
            description='Install replacement ball screw nut and verify Z-axis backlash < 0.02mm using dial indicator.',
            assigned_to='EMP003',
            target_date=today + timedelta(days=5),
            status='open',
        ),
        CAPAAction(
            capa_id=capa2.id,
            action_number=3,
            action_type='long_term',
            description='Add quarterly Z-axis backlash measurement to PM routine for all CNC mills. Acceptance limit: 0.03mm.',
            assigned_to='EMP003',
            target_date=today + timedelta(days=10),
            status='open',
        ),
    ]

    capa3 = CAPA(
        capa_number='CAPA-2026-003',
        capa_type=CAPAType.PREVENTIVE,
        status=CAPAStatus.ROOT_CAUSE_ANALYSIS,
        priority='medium',
        source_type='management_review',
        source_reference='MR-2026-Q1',
        title='Reduce FDM first-pass yield variability across printer fleet',
        problem_statement='Management review identified that first-pass yield on creality-cr30 (92.1%) is significantly lower than bambu-ps1 (97.8%). Investigation needed to identify root cause and standardize.',
        owner_id='EMP001',
        owner_department='Quality',
        root_cause_method='Fishbone',
        root_cause=None,
        contributing_factors=['Different printer architectures', 'Belt-driven vs CoreXY kinematics', 'Different firmware calibration approaches'],
        risk_before=12,
        initiation_date=today - timedelta(days=7),
        target_completion_date=today + timedelta(days=30),
        estimated_cost=500.0,
    )
    session.add(capa3)
    session.flush()

    capa3_actions = [
        CAPAAction(
            capa_id=capa3.id,
            action_number=1,
            action_type='short_term',
            description='Collect 30-day SPC data comparison between bambu-ps1 and creality-cr30 for identical brick products.',
            assigned_to='EMP001',
            target_date=today + timedelta(days=14),
            status='in_progress',
        ),
        CAPAAction(
            capa_id=capa3.id,
            action_number=2,
            action_type='short_term',
            description='Perform capability study (Cp/Cpk) on both printers for critical dimensions: length, width, stud diameter.',
            assigned_to='EMP002',
            target_date=today + timedelta(days=21),
            status='open',
        ),
    ]

    for action in capa1_actions + capa2_actions + capa3_actions:
        session.add(action)
    session.flush()
    print(f"  + 3 CAPAs with {len(capa1_actions) + len(capa2_actions) + len(capa3_actions)} actions")

    # =====================================================================
    # 6. Audits (3) with findings
    # =====================================================================
    audit1 = Audit(
        audit_number='AUD-2026-001',
        audit_type=AuditType.PROCESS,
        status=AuditStatus.COMPLETED,
        title='Internal Process Audit - FDM Printing Operations',
        scope='FDM printing process from material loading through dimensional inspection, covering bambu-ps1 and creality-cr30.',
        objectives=['Verify compliance with SOP-FDM-001', 'Assess SPC implementation effectiveness', 'Review operator training records'],
        criteria=['SOP-FDM-001 Rev C', 'WI-INSP-003 Rev B', 'ISO 9001:2015 Clause 8.5'],
        department='Production',
        process='FDM Printing',
        lead_auditor='EMP002',
        audit_team=['EMP002', 'EMP004'],
        planned_start=today - timedelta(days=20),
        planned_end=today - timedelta(days=18),
        actual_start=today - timedelta(days=20),
        actual_end=today - timedelta(days=18),
        summary='Audit of FDM printing operations found the process generally well-controlled. Three findings identified: one minor related to SPC chart review frequency, one observation on material traceability labeling, and one minor on training record currency.',
        conclusion='Process is effective. Minor improvements recommended for SPC review discipline and material labeling consistency.',
        findings_count={'minor': 2, 'observation': 1},
        report_date=today - timedelta(days=17),
        follow_up_date=today + timedelta(days=30),
    )
    session.add(audit1)
    session.flush()

    findings1 = [
        AuditFinding(
            audit_id=audit1.id,
            finding_number='AUD-2026-001-F01',
            severity=FindingSeverity.MINOR,
            category='Process Control',
            reference='SOP-FDM-001, Section 7.2',
            description='SPC charts for brick dimensions are not being reviewed at the required 4-hour intervals. Evidence shows gaps of 6-8 hours between operator reviews during night shift.',
            objective_evidence='SPC chart review log for bambu-ps1 shows only 2 reviews during 12-hour night shift on Feb 10-11 (required: 3).',
            capa_required=False,
            is_closed=True,
            closure_date=today - timedelta(days=8),
            closed_by='EMP001',
        ),
        AuditFinding(
            audit_id=audit1.id,
            finding_number='AUD-2026-001-F02',
            severity=FindingSeverity.OBSERVATION,
            category='Material Traceability',
            reference='SOP-FDM-001, Section 5.1',
            description='PLA filament spools in use on creality-cr30 did not have lot number labels visible. Lot traceability was maintained in the system but physical identification was missing.',
            objective_evidence='Visual observation during audit walk-through. Spool in use had label tucked behind holder.',
            capa_required=False,
            is_closed=True,
            closure_date=today - timedelta(days=10),
            closed_by='EMP002',
        ),
        AuditFinding(
            audit_id=audit1.id,
            finding_number='AUD-2026-001-F03',
            severity=FindingSeverity.MINOR,
            category='Training',
            reference='SOP-TRN-001, Section 4.3',
            description='Operator EMP004 SPC Fundamentals training certificate expired 15 days prior to audit. Operator was performing SPC data collection.',
            objective_evidence='Training record for EMP004 shows SPC Fundamentals (TRN-SPC-001) expired on Jan 25, 2026.',
            capa_required=False,
            is_closed=False,
        ),
    ]
    for f in findings1:
        session.add(f)

    audit2 = Audit(
        audit_number='AUD-2026-002',
        audit_type=AuditType.EXTERNAL,
        status=AuditStatus.IN_PROGRESS,
        title='ISO 9001:2015 Surveillance Audit - Year 2',
        scope='Full QMS scope including production, quality control, CAPA management, and management review.',
        objectives=['Verify continued conformity to ISO 9001:2015', 'Review effectiveness of CAPA system', 'Assess management review outputs'],
        criteria=['ISO 9001:2015', 'LEGO Factory QMS Manual Rev D'],
        department='Quality',
        process='Quality Management System',
        lead_auditor='EXT-AUD-001',
        audit_team=['EXT-AUD-001', 'EXT-AUD-002'],
        planned_start=today,
        planned_end=today + timedelta(days=2),
        actual_start=today,
        summary=None,
    )
    session.add(audit2)

    audit3 = Audit(
        audit_number='AUD-2026-003',
        audit_type=AuditType.SUPPLIER,
        status=AuditStatus.PLANNED,
        title='Supplier Audit - PolyMaker PLA Filament',
        scope='Audit of PolyMaker incoming material quality and process controls for PLA 1.75mm filament production.',
        objectives=['Verify raw material controls', 'Review dimensional consistency process', 'Assess color matching capability'],
        criteria=['LEGO Factory SQR-001', 'ISO 9001:2015 Clause 8.4'],
        department='Quality',
        process='Supplier Quality',
        lead_auditor='EMP002',
        audit_team=['EMP002', 'EMP001'],
        planned_start=today + timedelta(days=21),
        planned_end=today + timedelta(days=22),
    )
    session.add(audit3)
    session.flush()
    print(f"  + 3 audits with {len(findings1)} findings")

    # =====================================================================
    # 7. Training Courses (5)
    # =====================================================================
    courses_data = [
        {
            'course_id': 'TRN-GMP-001',
            'title': 'GMP and Quality Basics for Manufacturing',
            'description': 'Foundational course covering Good Manufacturing Practices, quality principles, non-conformance reporting, and documentation requirements.',
            'category': 'Quality',
            'course_type': 'classroom',
            'duration_hours': 4.0,
            'assessment_required': True,
            'passing_score': 80.0,
            'prerequisites': [],
            'required_for_roles': ['Operator', 'Inspector', 'Technician', 'Engineer'],
            'validity_months': 24,
        },
        {
            'course_id': 'TRN-SPC-001',
            'title': 'SPC Fundamentals and Control Chart Interpretation',
            'description': 'Statistical Process Control principles, X-bar R chart construction, Western Electric rules, capability indices (Cp, Cpk), and reaction plans.',
            'category': 'Quality',
            'course_type': 'classroom',
            'duration_hours': 8.0,
            'assessment_required': True,
            'passing_score': 85.0,
            'prerequisites': ['TRN-GMP-001'],
            'required_for_roles': ['Inspector', 'Engineer'],
            'validity_months': 12,
        },
        {
            'course_id': 'TRN-CNC-001',
            'title': 'CNC Machine Operation and Safety',
            'description': 'CNC mill and lathe operation, tool setup, program loading, work holding, in-process measurement, and emergency procedures.',
            'category': 'Operations',
            'course_type': 'ojt',
            'duration_hours': 16.0,
            'assessment_required': True,
            'passing_score': 90.0,
            'prerequisites': ['TRN-GMP-001', 'TRN-SAF-001'],
            'required_for_roles': ['CNC Operator', 'Technician'],
            'validity_months': 24,
        },
        {
            'course_id': 'TRN-3DP-001',
            'title': '3D Printer Operation (FDM and SLA)',
            'description': 'FDM and SLA printer setup, material loading, print job management, post-processing, and quality verification for LEGO part production.',
            'category': 'Operations',
            'course_type': 'ojt',
            'duration_hours': 12.0,
            'assessment_required': True,
            'passing_score': 85.0,
            'prerequisites': ['TRN-GMP-001'],
            'required_for_roles': ['3D Print Operator', 'Technician'],
            'validity_months': 24,
        },
        {
            'course_id': 'TRN-SAF-001',
            'title': 'Workplace Safety and Lockout/Tagout (LOTO)',
            'description': 'General workplace safety, hazard identification, PPE requirements, LOTO procedures for CNC and industrial equipment, and emergency response.',
            'category': 'Safety',
            'course_type': 'classroom',
            'duration_hours': 4.0,
            'assessment_required': True,
            'passing_score': 100.0,
            'prerequisites': [],
            'required_for_roles': ['Operator', 'Inspector', 'Technician', 'Engineer', 'CNC Operator', '3D Print Operator'],
            'validity_months': 12,
        },
    ]

    course_objects = {}
    for cd in courses_data:
        course = TrainingCourse(
            course_id=cd['course_id'],
            title=cd['title'],
            description=cd['description'],
            category=cd['category'],
            course_type=cd['course_type'],
            duration_hours=cd['duration_hours'],
            assessment_required=cd['assessment_required'],
            passing_score=cd['passing_score'],
            prerequisites=cd['prerequisites'],
            required_for_roles=cd['required_for_roles'],
            validity_months=cd['validity_months'],
            is_active=True,
        )
        session.add(course)
        session.flush()
        course_objects[cd['course_id']] = course

    print(f"  + {len(course_objects)} training courses")

    # =====================================================================
    # 8. Training Records (18) - each worker gets 3-5 records
    # =====================================================================
    worker_names = {
        'EMP001': 'Alex Chen',
        'EMP002': 'Maria Santos',
        'EMP003': 'James Wilson',
        'EMP004': 'Priya Patel',
    }

    training_records_data = [
        # EMP001 - Senior operator, all training current
        ('EMP001', 'TRN-GMP-001', TrainingStatus.COMPLETED, -180, 24, 92.0, True, 'EMP003'),
        ('EMP001', 'TRN-SPC-001', TrainingStatus.COMPLETED, -120, 12, 88.0, True, 'EMP002'),
        ('EMP001', 'TRN-3DP-001', TrainingStatus.COMPLETED, -90, 24, 95.0, True, 'EMP003'),
        ('EMP001', 'TRN-SAF-001', TrainingStatus.COMPLETED, -60, 12, 100.0, True, 'EMP003'),

        # EMP002 - Quality lead, all current except one scheduled
        ('EMP002', 'TRN-GMP-001', TrainingStatus.COMPLETED, -200, 24, 96.0, True, 'EMP003'),
        ('EMP002', 'TRN-SPC-001', TrainingStatus.COMPLETED, -150, 12, 94.0, True, 'EMP003'),
        ('EMP002', 'TRN-SAF-001', TrainingStatus.COMPLETED, -45, 12, 100.0, True, 'EMP003'),
        ('EMP002', 'TRN-CNC-001', TrainingStatus.SCHEDULED, 14, 24, None, None, 'EMP003'),

        # EMP003 - Maintenance tech, some expired
        ('EMP003', 'TRN-GMP-001', TrainingStatus.COMPLETED, -400, 24, 85.0, True, 'EMP002'),
        ('EMP003', 'TRN-CNC-001', TrainingStatus.COMPLETED, -100, 24, 92.0, True, 'EMP002'),
        ('EMP003', 'TRN-SAF-001', TrainingStatus.EXPIRED, -380, 12, 100.0, True, 'EMP002'),
        ('EMP003', 'TRN-3DP-001', TrainingStatus.SCHEDULED, 7, 24, None, None, 'EMP001'),

        # EMP004 - Junior operator, some completed, one expired, one in progress
        ('EMP004', 'TRN-GMP-001', TrainingStatus.COMPLETED, -60, 24, 82.0, True, 'EMP002'),
        ('EMP004', 'TRN-SPC-001', TrainingStatus.EXPIRED, -390, 12, 86.0, True, 'EMP002'),
        ('EMP004', 'TRN-3DP-001', TrainingStatus.COMPLETED, -30, 24, 88.0, True, 'EMP001'),
        ('EMP004', 'TRN-SAF-001', TrainingStatus.COMPLETED, -50, 12, 100.0, True, 'EMP003'),
        ('EMP004', 'TRN-CNC-001', TrainingStatus.IN_PROGRESS, -3, 24, None, None, 'EMP003'),
        ('EMP004', 'TRN-SPC-001', TrainingStatus.SCHEDULED, 10, 12, None, None, 'EMP002'),
    ]

    tr_count = 0
    cert_counter = 1000
    for (emp_id, course_key, status, days_offset, validity_mo, score, passed, instructor) in training_records_data:
        course_obj = course_objects[course_key]
        if status == TrainingStatus.COMPLETED:
            comp_date = today + timedelta(days=days_offset)
            expiry = comp_date + timedelta(days=validity_mo * 30)
            sched_date = comp_date - timedelta(days=7)
        elif status == TrainingStatus.EXPIRED:
            comp_date = today + timedelta(days=days_offset)
            expiry = comp_date + timedelta(days=validity_mo * 30)
            sched_date = comp_date - timedelta(days=7)
            # Check if actually expired
            if expiry > today:
                expiry = today - timedelta(days=15)
        elif status == TrainingStatus.SCHEDULED:
            comp_date = None
            expiry = None
            sched_date = today + timedelta(days=days_offset)
        elif status == TrainingStatus.IN_PROGRESS:
            comp_date = None
            expiry = None
            sched_date = today + timedelta(days=days_offset)
        else:
            comp_date = None
            expiry = None
            sched_date = today

        cert_num = None
        if status == TrainingStatus.COMPLETED:
            cert_counter += 1
            cert_num = f"CERT-2026-{cert_counter}"

        tr = TrainingRecord(
            course_id=course_obj.id,
            trainee_id=emp_id,
            trainee_name=worker_names.get(emp_id, emp_id),
            status=status,
            scheduled_date=sched_date,
            completion_date=comp_date,
            expiry_date=expiry,
            instructor_id=instructor,
            instructor_name=worker_names.get(instructor, instructor),
            assessment_score=score,
            assessment_passed=passed,
            certificate_number=cert_num,
        )
        session.add(tr)
        tr_count += 1

    session.flush()
    print(f"  + {tr_count} training records")

    # =====================================================================
    # 9. Calibrated Equipment (7) with calibration records
    # =====================================================================
    equipment_data = [
        {
            'equipment_id': 'CAL-DIG-001',
            'name': 'Digital Caliper 150mm',
            'description': 'Mitutoyo 500-196-30 Digimatic Caliper, 0-150mm range.',
            'equipment_type': 'Caliper',
            'category': 'Dimensional',
            'manufacturer': 'Mitutoyo',
            'model': '500-196-30',
            'serial_number': 'MIT-DC-2024-0847',
            'location': 'QC Station',
            'custodian': 'EMP001',
            'calibration_procedure': 'CAL-PROC-001',
            'calibration_interval_days': 180,
            'range_min': 0.0,
            'range_max': 150.0,
            'resolution': 0.01,
            'accuracy': '+/- 0.02mm',
            'unit_of_measure': 'mm',
            'status': CalibrationStatus.CURRENT,
            'last_cal_days_ago': 45,
        },
        {
            'equipment_id': 'CAL-DIG-002',
            'name': 'Digital Caliper 200mm',
            'description': 'Mitutoyo 500-197-30 Digimatic Caliper, 0-200mm range.',
            'equipment_type': 'Caliper',
            'category': 'Dimensional',
            'manufacturer': 'Mitutoyo',
            'model': '500-197-30',
            'serial_number': 'MIT-DC-2024-1203',
            'location': 'CNC Area',
            'custodian': 'EMP003',
            'calibration_procedure': 'CAL-PROC-001',
            'calibration_interval_days': 180,
            'range_min': 0.0,
            'range_max': 200.0,
            'resolution': 0.01,
            'accuracy': '+/- 0.02mm',
            'unit_of_measure': 'mm',
            'status': CalibrationStatus.CURRENT,
            'last_cal_days_ago': 90,
        },
        {
            'equipment_id': 'CAL-MIC-001',
            'name': 'Outside Micrometer 0-25mm',
            'description': 'Mitutoyo 293-340-30 Digimatic Micrometer, 0-25mm.',
            'equipment_type': 'Micrometer',
            'category': 'Dimensional',
            'manufacturer': 'Mitutoyo',
            'model': '293-340-30',
            'serial_number': 'MIT-OM-2023-5521',
            'location': 'QC Station',
            'custodian': 'EMP001',
            'calibration_procedure': 'CAL-PROC-002',
            'calibration_interval_days': 365,
            'range_min': 0.0,
            'range_max': 25.0,
            'resolution': 0.001,
            'accuracy': '+/- 0.001mm',
            'unit_of_measure': 'mm',
            'status': CalibrationStatus.CURRENT,
            'last_cal_days_ago': 120,
        },
        {
            'equipment_id': 'CAL-HGT-001',
            'name': 'Digital Height Gauge 300mm',
            'description': 'Mitutoyo 570-244 Digimatic Height Gauge, 0-300mm.',
            'equipment_type': 'Height Gauge',
            'category': 'Dimensional',
            'manufacturer': 'Mitutoyo',
            'model': '570-244',
            'serial_number': 'MIT-HG-2024-0312',
            'location': 'QC Station',
            'custodian': 'EMP002',
            'calibration_procedure': 'CAL-PROC-003',
            'calibration_interval_days': 365,
            'range_min': 0.0,
            'range_max': 300.0,
            'resolution': 0.01,
            'accuracy': '+/- 0.03mm',
            'unit_of_measure': 'mm',
            'status': CalibrationStatus.CURRENT,
            'last_cal_days_ago': 200,
        },
        {
            'equipment_id': 'CAL-SRF-001',
            'name': 'Granite Surface Plate 450x300mm',
            'description': 'Grade B granite surface plate for flatness reference.',
            'equipment_type': 'Surface Plate',
            'category': 'Reference',
            'manufacturer': 'Starrett',
            'model': '81798',
            'serial_number': 'STR-SP-2022-0088',
            'location': 'QC Station',
            'custodian': 'EMP002',
            'calibration_procedure': 'CAL-PROC-004',
            'calibration_interval_days': 730,
            'range_min': None,
            'range_max': None,
            'resolution': None,
            'accuracy': 'Grade B per ASME B89.3.7',
            'unit_of_measure': None,
            'status': CalibrationStatus.CURRENT,
            'last_cal_days_ago': 300,
        },
        {
            'equipment_id': 'CAL-BAL-001',
            'name': 'Precision Balance 200g',
            'description': 'A&D HR-202i Analytical Balance, 200g capacity.',
            'equipment_type': 'Balance',
            'category': 'Mass',
            'manufacturer': 'A&D',
            'model': 'HR-202i',
            'serial_number': 'AD-BAL-2024-0156',
            'location': 'QC Station',
            'custodian': 'EMP001',
            'calibration_procedure': 'CAL-PROC-005',
            'calibration_interval_days': 365,
            'range_min': 0.0,
            'range_max': 200.0,
            'resolution': 0.01,
            'accuracy': '+/- 0.02g',
            'unit_of_measure': 'g',
            'status': CalibrationStatus.DUE,
            'last_cal_days_ago': 355,
        },
        {
            'equipment_id': 'CAL-OPT-001',
            'name': 'USB Digital Microscope 200x',
            'description': 'Dino-Lite AM4113T USB microscope for tooth profile and surface inspection.',
            'equipment_type': 'Microscope',
            'category': 'Optical',
            'manufacturer': 'Dino-Lite',
            'model': 'AM4113T',
            'serial_number': 'DL-USB-2024-0741',
            'location': 'QC Station',
            'custodian': 'EMP004',
            'calibration_procedure': 'CAL-PROC-006',
            'calibration_interval_days': 365,
            'range_min': None,
            'range_max': None,
            'resolution': None,
            'accuracy': '+/- 1% at 200x',
            'unit_of_measure': None,
            'status': CalibrationStatus.CURRENT,
            'last_cal_days_ago': 60,
        },
    ]

    equip_objects = {}
    cal_record_count = 0
    for ed in equipment_data:
        last_cal_date = today - timedelta(days=ed['last_cal_days_ago'])
        next_due = last_cal_date + timedelta(days=ed['calibration_interval_days'])

        equip = CalibratedEquipment(
            equipment_id=ed['equipment_id'],
            name=ed['name'],
            description=ed['description'],
            equipment_type=ed['equipment_type'],
            category=ed['category'],
            manufacturer=ed['manufacturer'],
            model=ed['model'],
            serial_number=ed['serial_number'],
            location=ed['location'],
            custodian=ed['custodian'],
            calibration_procedure=ed['calibration_procedure'],
            calibration_interval_days=ed['calibration_interval_days'],
            last_calibration_date=last_cal_date,
            next_calibration_due=next_due,
            status=ed['status'],
            range_min=ed['range_min'],
            range_max=ed['range_max'],
            resolution=ed['resolution'],
            accuracy=ed['accuracy'],
            unit_of_measure=ed['unit_of_measure'],
            is_active=True,
        )
        session.add(equip)
        session.flush()
        equip_objects[ed['equipment_id']] = equip

        # Create calibration record for most recent calibration
        cal_num = f"CR-{ed['equipment_id'].replace('CAL-', '')}-{last_cal_date.strftime('%Y%m%d')}"

        as_found = {}
        as_left = {}
        if ed['range_min'] is not None and ed['range_max'] is not None:
            # Generate realistic as-found/as-left data
            points = [ed['range_min'], ed['range_max'] * 0.25, ed['range_max'] * 0.5, ed['range_max'] * 0.75, ed['range_max']]
            for pt in points:
                key = f"{pt:.2f}"
                as_found[key] = round(pt + random.uniform(-0.005, 0.005), 4)
                as_left[key] = round(pt + random.uniform(-0.002, 0.002), 4)

        cal_rec = CalibrationRecord(
            equipment_id=equip.id,
            calibration_number=cal_num,
            calibration_date=last_cal_date,
            next_due_date=next_due,
            performed_by='EMP002' if ed['category'] != 'Reference' else 'EXT-CAL-001',
            result='pass',
            as_found_data=as_found,
            as_left_data=as_left,
            temperature=round(random.uniform(20.0, 22.0), 1),
            humidity=round(random.uniform(40.0, 55.0), 1),
        )
        session.add(cal_rec)
        cal_record_count += 1

    session.flush()
    print(f"  + {len(equip_objects)} calibrated equipment with {cal_record_count} calibration records")

    session.commit()
    print("  QMS data seeding complete")


def seed_cmms_data(session):
    """Seed realistic CMMS (maintenance) data for the LEGO factory.

    Creates asset classes, assets, meters, meter readings, spare parts,
    PM schedules, maintenance work orders (with tasks, labor, materials),
    and failure codes.
    """
    from datetime import date
    from models.cmms.assets import (
        AssetClass, Asset, Meter, MeterReading, Spare, AssetSpare,
        AssetStatus, AssetCriticality, MeterType,
    )
    from models.cmms.maintenance import (
        PMSchedule, MaintenanceWorkOrder, WorkOrderTask,
        WorkOrderLabor, WorkOrderMaterial,
        WorkOrderType, WorkOrderStatus, WorkOrderPriority, PMTriggerType,
    )
    from models.cmms.failure import (
        FailureCode, FailureType, FailureSeverity,
    )

    now = datetime.utcnow()
    today = date.today()

    # -----------------------------------------------------------------------
    # Clear previous CMMS data (order matters for FK constraints)
    # -----------------------------------------------------------------------
    session.query(WorkOrderMaterial).delete(synchronize_session='fetch')
    session.query(WorkOrderLabor).delete(synchronize_session='fetch')
    session.query(WorkOrderTask).delete(synchronize_session='fetch')
    session.query(MaintenanceWorkOrder).delete(synchronize_session='fetch')
    session.query(PMSchedule).delete(synchronize_session='fetch')
    session.query(MeterReading).delete(synchronize_session='fetch')
    session.query(Meter).delete(synchronize_session='fetch')
    session.query(AssetSpare).delete(synchronize_session='fetch')
    session.query(Spare).delete(synchronize_session='fetch')
    session.query(Asset).delete(synchronize_session='fetch')
    session.query(AssetClass).delete(synchronize_session='fetch')
    session.query(FailureCode).delete(synchronize_session='fetch')
    session.commit()
    print("  Cleared previous CMMS data")

    # -----------------------------------------------------------------------
    # 1. Asset Classes (7)
    # -----------------------------------------------------------------------
    asset_classes_data = [
        {
            'code': 'FDM-3DP', 'name': 'FDM 3D Printer',
            'description': 'Fused Deposition Modeling 3D printers for thermoplastic parts',
            'default_pm_interval_days': 30, 'default_pm_interval_hours': 500.0,
            'expected_lifespan_years': 5.0,
            'spec_template': {'nozzle_diameter_mm': 0.4, 'max_temp_c': 300, 'build_volume_mm': '256x256x256'},
        },
        {
            'code': 'SLA-3DP', 'name': 'SLA 3D Printer',
            'description': 'Stereolithography resin printers for high-detail parts',
            'default_pm_interval_days': 14, 'default_pm_interval_hours': 300.0,
            'expected_lifespan_years': 5.0,
            'spec_template': {'resin_type': 'standard', 'laser_wavelength_nm': 405, 'build_volume_mm': '145x145x185'},
        },
        {
            'code': 'CNC-MILL', 'name': 'CNC Mill',
            'description': 'Computer Numerical Control milling machines',
            'default_pm_interval_days': 60, 'default_pm_interval_hours': 1000.0,
            'expected_lifespan_years': 10.0,
            'spec_template': {'max_rpm': 24000, 'axes': 3, 'work_area_mm': '305x228x89'},
        },
        {
            'code': 'CNC-LATHE', 'name': 'CNC Lathe',
            'description': 'Computer Numerical Control turning lathes',
            'default_pm_interval_days': 60, 'default_pm_interval_hours': 1000.0,
            'expected_lifespan_years': 10.0,
            'spec_template': {'max_rpm': 5000, 'max_turning_diameter_mm': 50, 'max_turning_length_mm': 150},
        },
        {
            'code': 'ROBOT-ARM', 'name': 'Robot Arm',
            'description': 'Articulated robot arms for pick-and-place and assembly',
            'default_pm_interval_days': 90, 'default_pm_interval_hours': 2000.0,
            'expected_lifespan_years': 8.0,
            'spec_template': {'dof': 6, 'payload_kg': 1.0, 'reach_mm': 440},
        },
        {
            'code': 'LASER-ENG', 'name': 'Laser Engraver',
            'description': 'Laser engraving and cutting machines',
            'default_pm_interval_days': 45, 'default_pm_interval_hours': 800.0,
            'expected_lifespan_years': 7.0,
            'spec_template': {'laser_power_w': 10, 'work_area_mm': '400x400', 'laser_type': 'diode'},
        },
        {
            'code': 'CONVEYOR', 'name': 'Conveyor System',
            'description': 'Belt conveyor systems for material transport',
            'default_pm_interval_days': 120, 'default_pm_interval_hours': 5000.0,
            'expected_lifespan_years': 15.0,
            'spec_template': {'belt_width_mm': 100, 'max_speed_mm_s': 200, 'max_load_kg': 5},
        },
    ]

    ac_map = {}  # code -> AssetClass object
    for acd in asset_classes_data:
        ac = AssetClass(**acd)
        session.add(ac)
        ac_map[acd['code']] = ac

    session.flush()
    print(f"  + {len(asset_classes_data)} asset classes")

    # -----------------------------------------------------------------------
    # 2. Assets (11 - one per physical machine)
    # -----------------------------------------------------------------------
    assets_data = [
        {
            'asset_id': 'AST-BAMBU-PS1', 'name': 'Bambu Lab P1S #1',
            'description': 'Primary FDM 3D printer for high-speed brick production',
            'asset_class_code': 'FDM-3DP', 'machine_id': 'bambu-ps1',
            'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.CRITICAL,
            'location_id': 'ZONE-A', 'location_description': 'Print Farm - Station A1',
            'work_center_id': 'WC-PRINT', 'serial_number': 'BBL-P1S-2023-04821',
            'model_number': 'P1S', 'manufacturer': 'Bambu Lab',
            'purchase_date': today - timedelta(days=548),
            'installation_date': today - timedelta(days=540),
            'warranty_expiry': today + timedelta(days=182),
            'purchase_cost': 699.00, 'replacement_cost': 749.00,
            'specifications': {'nozzle_diameter_mm': 0.4, 'max_temp_c': 300, 'build_volume_mm': '256x256x256'},
        },
        {
            'asset_id': 'AST-CR30', 'name': 'Creality 3DPrintMill CR-30',
            'description': 'Belt 3D printer for continuous production runs',
            'asset_class_code': 'FDM-3DP', 'machine_id': 'creality-cr30',
            'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.ESSENTIAL,
            'location_id': 'ZONE-A', 'location_description': 'Print Farm - Station A2',
            'work_center_id': 'WC-PRINT', 'serial_number': 'CR30-2023-11287',
            'model_number': 'CR-30', 'manufacturer': 'Creality',
            'purchase_date': today - timedelta(days=730),
            'installation_date': today - timedelta(days=720),
            'warranty_expiry': today - timedelta(days=5),
            'purchase_cost': 999.00, 'replacement_cost': 1049.00,
            'specifications': {'nozzle_diameter_mm': 0.4, 'max_temp_c': 260, 'belt_type': 'continuous'},
        },
        {
            'asset_id': 'AST-FORM3', 'name': 'Formlabs Form 3',
            'description': 'SLA resin printer for high-detail minifigure accessories',
            'asset_class_code': 'SLA-3DP', 'machine_id': 'formlabs-3',
            'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.ESSENTIAL,
            'location_id': 'ZONE-A', 'location_description': 'Print Farm - Station A3 (ventilated)',
            'work_center_id': 'WC-PRINT', 'serial_number': 'F3-2023-K9247',
            'model_number': 'Form 3', 'manufacturer': 'Formlabs',
            'purchase_date': today - timedelta(days=455),
            'installation_date': today - timedelta(days=448),
            'warranty_expiry': today + timedelta(days=275),
            'purchase_cost': 3499.00, 'replacement_cost': 3749.00,
            'specifications': {'laser_wavelength_nm': 405, 'layer_resolution_um': 25, 'build_volume_mm': '145x145x185'},
        },
        {
            'asset_id': 'AST-BANTAM', 'name': 'Bantam Tools Desktop CNC',
            'description': 'Desktop CNC mill for mold inserts and fixtures',
            'asset_class_code': 'CNC-MILL', 'machine_id': 'bantam-explorer',
            'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.CRITICAL,
            'location_id': 'ZONE-B', 'location_description': 'CNC Bay - Station B1',
            'work_center_id': 'WC-CNC', 'serial_number': 'BT-EXP-2022-03481',
            'model_number': 'Desktop CNC', 'manufacturer': 'Bantam Tools',
            'purchase_date': today - timedelta(days=912),
            'installation_date': today - timedelta(days=900),
            'warranty_expiry': today - timedelta(days=170),
            'purchase_cost': 4599.00, 'replacement_cost': 4899.00,
            'specifications': {'max_rpm': 24000, 'axes': 3, 'work_area_mm': '140x114x44'},
        },
        {
            'asset_id': 'AST-CR1', 'name': 'CoastRunner CR1 CNC',
            'description': 'CNC router for larger mold plates and enclosures',
            'asset_class_code': 'CNC-MILL', 'machine_id': 'coastrunner-cr1',
            'status': AssetStatus.DEGRADED, 'criticality': AssetCriticality.IMPORTANT,
            'location_id': 'ZONE-B', 'location_description': 'CNC Bay - Station B2',
            'work_center_id': 'WC-CNC', 'serial_number': 'CR1-2023-00892',
            'model_number': 'CR1', 'manufacturer': 'CoastRunner',
            'purchase_date': today - timedelta(days=640),
            'installation_date': today - timedelta(days=630),
            'warranty_expiry': today + timedelta(days=90),
            'purchase_cost': 3299.00, 'replacement_cost': 3499.00,
            'specifications': {'max_rpm': 12000, 'axes': 3, 'work_area_mm': '305x228x89'},
        },
        {
            'asset_id': 'AST-LABFAB', 'name': 'Labfab CNC Runner',
            'description': 'CNC mill for precision brick mold inserts',
            'asset_class_code': 'CNC-MILL', 'machine_id': 'labfab-runner',
            'status': AssetStatus.MAINTENANCE, 'criticality': AssetCriticality.IMPORTANT,
            'location_id': 'ZONE-B', 'location_description': 'CNC Bay - Station B3',
            'work_center_id': 'WC-CNC', 'serial_number': 'LF-RUN-2023-05614',
            'model_number': 'Runner', 'manufacturer': 'Labfab',
            'purchase_date': today - timedelta(days=500),
            'installation_date': today - timedelta(days=490),
            'warranty_expiry': today + timedelta(days=230),
            'purchase_cost': 2899.00, 'replacement_cost': 3099.00,
            'specifications': {'max_rpm': 18000, 'axes': 3, 'work_area_mm': '200x150x60'},
        },
        {
            'asset_id': 'AST-ROWND', 'name': 'Rownd CNC Lathe',
            'description': 'CNC lathe for cylindrical brick and axle components',
            'asset_class_code': 'CNC-LATHE', 'machine_id': 'rownd-lathe',
            'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.IMPORTANT,
            'location_id': 'ZONE-B', 'location_description': 'CNC Bay - Station B4',
            'work_center_id': 'WC-CNC', 'serial_number': 'RWND-2023-LT-1247',
            'model_number': 'Rownd Lathe', 'manufacturer': 'Rownd',
            'purchase_date': today - timedelta(days=410),
            'installation_date': today - timedelta(days=400),
            'warranty_expiry': today + timedelta(days=320),
            'purchase_cost': 5999.00, 'replacement_cost': 6299.00,
            'specifications': {'max_rpm': 5000, 'max_turning_diameter_mm': 50, 'max_turning_length_mm': 150},
        },
        {
            'asset_id': 'AST-NIRYO', 'name': 'Niryo Ned2 Robot Arm',
            'description': '6-axis collaborative robot for QC pick-and-place',
            'asset_class_code': 'ROBOT-ARM', 'machine_id': 'niryo-ned2',
            'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.CRITICAL,
            'location_id': 'ZONE-C', 'location_description': 'Assembly Cell - Station C1',
            'work_center_id': 'WC-ASSEMBLY', 'serial_number': 'NED2-2023-FR-4129',
            'model_number': 'Ned2', 'manufacturer': 'Niryo',
            'purchase_date': today - timedelta(days=365),
            'installation_date': today - timedelta(days=358),
            'warranty_expiry': today + timedelta(days=365),
            'purchase_cost': 5990.00, 'replacement_cost': 6290.00,
            'specifications': {'dof': 6, 'payload_kg': 0.3, 'reach_mm': 440, 'repeatability_mm': 0.5},
        },
        {
            'asset_id': 'AST-XARM', 'name': 'xArm Lite 6 Robot Arm',
            'description': '6-axis robot arm for packaging and palletizing',
            'asset_class_code': 'ROBOT-ARM', 'machine_id': 'xarm-lite6',
            'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.ESSENTIAL,
            'location_id': 'ZONE-C', 'location_description': 'Packaging Cell - Station C2',
            'work_center_id': 'WC-PACK', 'serial_number': 'XARM-L6-2023-08217',
            'model_number': 'Lite 6', 'manufacturer': 'UFACTORY',
            'purchase_date': today - timedelta(days=320),
            'installation_date': today - timedelta(days=312),
            'warranty_expiry': today + timedelta(days=410),
            'purchase_cost': 4999.00, 'replacement_cost': 5299.00,
            'specifications': {'dof': 6, 'payload_kg': 1.0, 'reach_mm': 500, 'repeatability_mm': 0.1},
        },
        {
            'asset_id': 'AST-LASER', 'name': 'Longer Ray5 Laser Engraver',
            'description': 'Diode laser engraver for brick logos and serial markings',
            'asset_class_code': 'LASER-ENG', 'machine_id': 'longer-ray-laser',
            'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.STANDARD,
            'location_id': 'ZONE-D', 'location_description': 'Finishing Area - Station D1',
            'work_center_id': 'WC-FINISH', 'serial_number': 'LR5-2024-EN-00493',
            'model_number': 'Ray5 10W', 'manufacturer': 'Longer',
            'purchase_date': today - timedelta(days=280),
            'installation_date': today - timedelta(days=273),
            'warranty_expiry': today + timedelta(days=450),
            'purchase_cost': 499.00, 'replacement_cost': 549.00,
            'specifications': {'laser_power_w': 10, 'work_area_mm': '400x400', 'laser_type': 'diode'},
        },
        {
            'asset_id': 'AST-CONV', 'name': 'Niryo Conveyor Belt',
            'description': 'Motorized conveyor belt linking assembly and packaging cells',
            'asset_class_code': 'CONVEYOR', 'machine_id': 'niryo-conveyor',
            'status': AssetStatus.OPERATIONAL, 'criticality': AssetCriticality.STANDARD,
            'location_id': 'ZONE-C', 'location_description': 'Assembly-to-Pack Transfer Line',
            'work_center_id': 'WC-ASSEMBLY', 'serial_number': 'NCONV-2023-BLT-0071',
            'model_number': 'Conveyor Belt', 'manufacturer': 'Niryo',
            'purchase_date': today - timedelta(days=365),
            'installation_date': today - timedelta(days=358),
            'warranty_expiry': today + timedelta(days=365),
            'purchase_cost': 399.00, 'replacement_cost': 449.00,
            'specifications': {'belt_width_mm': 100, 'max_speed_mm_s': 200, 'length_mm': 700},
        },
    ]

    asset_map = {}  # asset_id string -> Asset ORM object
    for ad in assets_data:
        ac_code = ad.pop('asset_class_code')
        ad['asset_class_id'] = ac_map[ac_code].id
        asset = Asset(**ad)
        session.add(asset)
        asset_map[ad['asset_id']] = asset

    session.flush()
    print(f"  + {len(assets_data)} assets")

    # -----------------------------------------------------------------------
    # 3. Meters (~28 total, 2-3 per asset)
    # -----------------------------------------------------------------------
    meters_data = []
    meter_counter = 0

    def add_meter(asset_id_str, name, meter_type, unit, last_val, warn, crit,
                  avg_daily, rollover=None):
        nonlocal meter_counter
        meter_counter += 1
        m_id = f"MTR-{meter_counter:03d}"
        meters_data.append({
            'meter_id': m_id,
            'asset_id': asset_map[asset_id_str].id,
            'name': name,
            'description': f'{name} for {asset_id_str}',
            'meter_type': meter_type,
            'unit_of_measure': unit,
            'last_reading': last_val,
            'last_reading_date': now - timedelta(hours=random.randint(1, 8)),
            'warning_threshold': warn,
            'critical_threshold': crit,
            'rollover_value': rollover,
            'average_daily_usage': avg_daily,
        })
        return m_id

    # Bambu P1S
    add_meter('AST-BAMBU-PS1', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 1847.0, 2000, 4000, 12.5)
    add_meter('AST-BAMBU-PS1', 'Print Cycle Count', MeterType.CONTINUOUS, 'cycles', 4230.0, 8000, 15000, 28.0)
    add_meter('AST-BAMBU-PS1', 'Nozzle Temperature', MeterType.GAUGE, 'deg_C', 210.0, 250, 280, None)

    # Creality CR-30
    add_meter('AST-CR30', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 2410.0, 2000, 4000, 10.0)
    add_meter('AST-CR30', 'Print Cycle Count', MeterType.CONTINUOUS, 'cycles', 5812.0, 8000, 15000, 22.0)
    add_meter('AST-CR30', 'Bed Temperature', MeterType.GAUGE, 'deg_C', 60.0, 80, 100, None)

    # Formlabs Form 3
    add_meter('AST-FORM3', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 982.0, 2000, 4000, 6.5)
    add_meter('AST-FORM3', 'Print Cycle Count', MeterType.CONTINUOUS, 'cycles', 1467.0, 5000, 10000, 9.0)
    add_meter('AST-FORM3', 'Resin Tank Level', MeterType.GAUGE, 'percent', 42.0, 20, 10, None)

    # Bantam CNC
    add_meter('AST-BANTAM', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 2180.0, 2000, 4000, 8.0)
    add_meter('AST-BANTAM', 'Spindle Hours', MeterType.CONTINUOUS, 'hours', 1890.0, 2000, 4000, 7.0)
    add_meter('AST-BANTAM', 'Vibration Level', MeterType.CHARACTERISTIC, 'mm/s', 2.8, 4.0, 6.0, 0.0)

    # CoastRunner CR1
    add_meter('AST-CR1', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 1520.0, 2000, 4000, 7.5)
    add_meter('AST-CR1', 'Spindle Hours', MeterType.CONTINUOUS, 'hours', 1340.0, 2000, 4000, 6.5)
    add_meter('AST-CR1', 'Vibration Level', MeterType.CHARACTERISTIC, 'mm/s', 4.2, 4.0, 6.0, 0.0)

    # Labfab Runner
    add_meter('AST-LABFAB', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 1050.0, 2000, 4000, 6.0)
    add_meter('AST-LABFAB', 'Spindle Hours', MeterType.CONTINUOUS, 'hours', 920.0, 2000, 4000, 5.5)
    add_meter('AST-LABFAB', 'Vibration Level', MeterType.CHARACTERISTIC, 'mm/s', 1.9, 4.0, 6.0, 0.0)

    # Rownd Lathe
    add_meter('AST-ROWND', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 870.0, 2000, 4000, 5.0)
    add_meter('AST-ROWND', 'Spindle Hours', MeterType.CONTINUOUS, 'hours', 780.0, 2000, 4000, 4.5)
    add_meter('AST-ROWND', 'Vibration Level', MeterType.CHARACTERISTIC, 'mm/s', 1.5, 4.0, 6.0, 0.0)

    # Niryo Ned2
    add_meter('AST-NIRYO', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 1620.0, 2000, 4000, 14.0)
    add_meter('AST-NIRYO', 'Joint Cycle Count', MeterType.CONTINUOUS, 'cycles', 184200.0, 300000, 500000, 1200.0)

    # xArm Lite 6
    add_meter('AST-XARM', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 1380.0, 2000, 4000, 12.0)
    add_meter('AST-XARM', 'Joint Cycle Count', MeterType.CONTINUOUS, 'cycles', 156800.0, 300000, 500000, 1050.0)

    # Longer Ray5 Laser
    add_meter('AST-LASER', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 620.0, 2000, 4000, 4.0)
    add_meter('AST-LASER', 'Engrave Cycle Count', MeterType.CONTINUOUS, 'cycles', 12840.0, 30000, 60000, 85.0)

    # Niryo Conveyor
    add_meter('AST-CONV', 'Runtime Hours', MeterType.CONTINUOUS, 'hours', 2950.0, 5000, 8000, 16.0)
    add_meter('AST-CONV', 'Belt Cycle Count', MeterType.CONTINUOUS, 'cycles', 98200.0, 200000, 400000, 550.0)

    meter_map = {}  # meter_id string -> Meter ORM object
    for md in meters_data:
        meter = Meter(**md)
        session.add(meter)
        meter_map[md['meter_id']] = meter

    session.flush()
    print(f"  + {len(meters_data)} meters")

    # -----------------------------------------------------------------------
    # 4. Meter Readings (7-10 per meter over the last 30 days)
    # -----------------------------------------------------------------------
    reading_count = 0
    workers = ['EMP001', 'EMP002', 'EMP003', 'EMP004']

    for md in meters_data:
        meter_obj = meter_map[md['meter_id']]
        m_type = md['meter_type']
        last_val = md['last_reading']
        avg_daily = md['average_daily_usage']
        num_readings = random.randint(7, 10)

        for i in range(num_readings, 0, -1):
            days_ago = i * (30.0 / num_readings)
            reading_dt = now - timedelta(days=days_ago)

            if m_type == MeterType.CONTINUOUS and avg_daily:
                val = last_val - (avg_daily * days_ago)
                val = max(0, round(val, 1))
                delta = round(avg_daily * (30.0 / num_readings) * random.uniform(0.8, 1.2), 1)
            elif m_type == MeterType.GAUGE:
                val = round(last_val + random.uniform(-5, 5), 1)
                delta = None
            else:  # CHARACTERISTIC
                val = round(last_val + random.uniform(-0.5, 0.5), 2)
                delta = None

            reading = MeterReading(
                meter_id=meter_obj.id,
                reading_date=reading_dt,
                reading_value=val,
                delta=delta,
                source=random.choice(['automatic', 'automatic', 'manual']),
                recorded_by=random.choice(workers) if random.random() < 0.3 else None,
            )
            session.add(reading)
            reading_count += 1

    session.flush()
    print(f"  + {reading_count} meter readings")

    # -----------------------------------------------------------------------
    # 5. Spare Parts (18)
    # -----------------------------------------------------------------------
    spares_data = [
        {
            'spare_id': 'SPR-001', 'name': '0.4mm Hardened Steel Nozzle',
            'description': 'Hardened steel nozzle for FDM printers, 0.4mm bore',
            'item_id': 'INV-NOZZLE-04', 'quantity_on_hand': 12, 'reorder_point': 5,
            'reorder_quantity': 20, 'unit_cost': 18.50,
            'vendor_id': 'VND-BAMBU', 'vendor_part_number': 'BBL-NZ-04HS',
            'lead_time_days': 7, 'bin_location': 'BIN-A01',
        },
        {
            'spare_id': 'SPR-002', 'name': 'FDM Print Bed PEI Sheet',
            'description': 'PEI spring steel print bed sheet 256x256mm',
            'item_id': 'INV-BED-PEI', 'quantity_on_hand': 3, 'reorder_point': 2,
            'reorder_quantity': 5, 'unit_cost': 35.00,
            'vendor_id': 'VND-BAMBU', 'vendor_part_number': 'BBL-BED-PEI256',
            'lead_time_days': 10, 'bin_location': 'BIN-A02',
        },
        {
            'spare_id': 'SPR-003', 'name': 'GT2 Timing Belt 6mm',
            'description': 'GT2 timing belt, 6mm width, sold per meter',
            'item_id': 'INV-BELT-GT2', 'quantity_on_hand': 8, 'reorder_point': 3,
            'reorder_quantity': 10, 'unit_cost': 4.50,
            'vendor_id': 'VND-MOTION', 'vendor_part_number': 'GT2-6-1M',
            'lead_time_days': 5, 'bin_location': 'BIN-A03',
        },
        {
            'spare_id': 'SPR-004', 'name': 'CR-30 Belt Surface',
            'description': 'Replacement belt surface for Creality CR-30 belt printer',
            'item_id': 'INV-CR30-BELT', 'quantity_on_hand': 1, 'reorder_point': 2,
            'reorder_quantity': 3, 'unit_cost': 89.00,
            'vendor_id': 'VND-CRTY', 'vendor_part_number': 'CR30-BELT-01',
            'lead_time_days': 14, 'bin_location': 'BIN-A04',
        },
        {
            'spare_id': 'SPR-005', 'name': 'Formlabs Resin Tank V2.1',
            'description': 'Replacement resin tank for Form 3 printer',
            'item_id': 'INV-TANK-F3', 'quantity_on_hand': 2, 'reorder_point': 2,
            'reorder_quantity': 4, 'unit_cost': 149.00,
            'vendor_id': 'VND-FORMLABS', 'vendor_part_number': 'FL-TANK-V21',
            'lead_time_days': 7, 'bin_location': 'BIN-A05',
        },
        {
            'spare_id': 'SPR-006', 'name': 'Standard Grey Resin 1L',
            'description': 'Formlabs Standard Grey V4 resin, 1 liter',
            'item_id': 'INV-RESIN-GRY', 'quantity_on_hand': 4, 'reorder_point': 3,
            'reorder_quantity': 6, 'unit_cost': 149.00,
            'vendor_id': 'VND-FORMLABS', 'vendor_part_number': 'FL-RESIN-GRY-V4',
            'lead_time_days': 5, 'bin_location': 'BIN-A06',
        },
        {
            'spare_id': 'SPR-007', 'name': '1/8" Flat End Mill 2-Flute',
            'description': 'Carbide flat end mill, 1/8" shank, 2-flute',
            'item_id': 'INV-EM-125-2F', 'quantity_on_hand': 15, 'reorder_point': 5,
            'reorder_quantity': 25, 'unit_cost': 12.00,
            'vendor_id': 'VND-BANTAM', 'vendor_part_number': 'BT-EM-125-2FL',
            'lead_time_days': 5, 'bin_location': 'BIN-B01',
        },
        {
            'spare_id': 'SPR-008', 'name': '1/16" Ball End Mill 2-Flute',
            'description': 'Carbide ball end mill, 1/16" shank, 2-flute for detail work',
            'item_id': 'INV-BEM-0625', 'quantity_on_hand': 8, 'reorder_point': 4,
            'reorder_quantity': 15, 'unit_cost': 15.50,
            'vendor_id': 'VND-BANTAM', 'vendor_part_number': 'BT-BEM-0625-2FL',
            'lead_time_days': 5, 'bin_location': 'BIN-B02',
        },
        {
            'spare_id': 'SPR-009', 'name': 'CNC Spindle Bearing Set',
            'description': 'Replacement angular contact bearing set for CNC spindles',
            'item_id': 'INV-BEAR-SPNDL', 'quantity_on_hand': 2, 'reorder_point': 2,
            'reorder_quantity': 4, 'unit_cost': 85.00,
            'vendor_id': 'VND-BEARINGS', 'vendor_part_number': 'ACB-7001-SET',
            'lead_time_days': 14, 'bin_location': 'BIN-B03',
        },
        {
            'spare_id': 'SPR-010', 'name': 'CNC Way Lubricant 500ml',
            'description': 'Slideway lubricant oil ISO 68 for CNC linear guides',
            'item_id': 'INV-LUBE-WAY', 'quantity_on_hand': 6, 'reorder_point': 3,
            'reorder_quantity': 12, 'unit_cost': 22.00,
            'vendor_id': 'VND-LUBES', 'vendor_part_number': 'SWO-ISO68-500',
            'lead_time_days': 3, 'bin_location': 'BIN-B04',
        },
        {
            'spare_id': 'SPR-011', 'name': 'Niryo Ned2 Gripper Pads',
            'description': 'Replacement soft gripper pads for Niryo Ned2',
            'item_id': 'INV-GRIP-NED2', 'quantity_on_hand': 4, 'reorder_point': 3,
            'reorder_quantity': 8, 'unit_cost': 29.00,
            'vendor_id': 'VND-NIRYO', 'vendor_part_number': 'NED2-GRIP-SOFT',
            'lead_time_days': 10, 'bin_location': 'BIN-C01',
        },
        {
            'spare_id': 'SPR-012', 'name': 'xArm Vacuum Gripper Cup',
            'description': 'Replacement vacuum suction cup for xArm pick-and-place',
            'item_id': 'INV-VAC-XARM', 'quantity_on_hand': 10, 'reorder_point': 4,
            'reorder_quantity': 12, 'unit_cost': 8.50,
            'vendor_id': 'VND-UFACTORY', 'vendor_part_number': 'XA-VAC-CUP-25',
            'lead_time_days': 12, 'bin_location': 'BIN-C02',
        },
        {
            'spare_id': 'SPR-013', 'name': 'Robot Joint Grease Cartridge',
            'description': 'High-performance grease cartridge for robot arm joints',
            'item_id': 'INV-GREASE-RBT', 'quantity_on_hand': 5, 'reorder_point': 2,
            'reorder_quantity': 6, 'unit_cost': 45.00,
            'vendor_id': 'VND-LUBES', 'vendor_part_number': 'RBG-EP2-CART',
            'lead_time_days': 5, 'bin_location': 'BIN-C03',
        },
        {
            'spare_id': 'SPR-014', 'name': 'Laser Focus Lens',
            'description': 'Replacement focus lens for Longer Ray5 laser module',
            'item_id': 'INV-LENS-LR5', 'quantity_on_hand': 3, 'reorder_point': 2,
            'reorder_quantity': 5, 'unit_cost': 25.00,
            'vendor_id': 'VND-LONGER', 'vendor_part_number': 'LR5-LENS-FOC',
            'lead_time_days': 10, 'bin_location': 'BIN-D01',
        },
        {
            'spare_id': 'SPR-015', 'name': 'Laser Air Assist Nozzle',
            'description': 'Air assist nozzle assembly for laser engraver',
            'item_id': 'INV-AIRNOZ-LR5', 'quantity_on_hand': 2, 'reorder_point': 1,
            'reorder_quantity': 3, 'unit_cost': 18.00,
            'vendor_id': 'VND-LONGER', 'vendor_part_number': 'LR5-AIRNOZ',
            'lead_time_days': 10, 'bin_location': 'BIN-D02',
        },
        {
            'spare_id': 'SPR-016', 'name': 'Conveyor Belt Segment',
            'description': 'Replacement belt segment for Niryo conveyor, 700mm',
            'item_id': 'INV-CBELT-700', 'quantity_on_hand': 1, 'reorder_point': 1,
            'reorder_quantity': 2, 'unit_cost': 65.00,
            'vendor_id': 'VND-NIRYO', 'vendor_part_number': 'NCONV-BELT-700',
            'lead_time_days': 14, 'bin_location': 'BIN-C04',
        },
        {
            'spare_id': 'SPR-017', 'name': 'HEPA Filter Cartridge',
            'description': 'HEPA filter for printer enclosure air filtration',
            'item_id': 'INV-HEPA-ENC', 'quantity_on_hand': 0, 'reorder_point': 2,
            'reorder_quantity': 6, 'unit_cost': 32.00,
            'vendor_id': 'VND-FILTERS', 'vendor_part_number': 'HEPA-13-ENC',
            'lead_time_days': 7, 'bin_location': 'BIN-A07',
        },
        {
            'spare_id': 'SPR-018', 'name': 'Stepper Motor NEMA 17',
            'description': 'Replacement NEMA 17 stepper motor for 3D printers and CNC',
            'item_id': 'INV-MOTOR-N17', 'quantity_on_hand': 3, 'reorder_point': 2,
            'reorder_quantity': 5, 'unit_cost': 14.00,
            'vendor_id': 'VND-MOTION', 'vendor_part_number': 'N17-48-20',
            'lead_time_days': 7, 'bin_location': 'BIN-A08',
        },
    ]

    spare_map = {}  # spare_id string -> Spare ORM object
    for sd in spares_data:
        spare = Spare(**sd)
        session.add(spare)
        spare_map[sd['spare_id']] = spare

    session.flush()
    print(f"  + {len(spares_data)} spare parts")

    # -- Asset-Spare associations --
    asset_spare_links = [
        ('AST-BAMBU-PS1', 'SPR-001', 2, 'Nozzle replacement'),
        ('AST-BAMBU-PS1', 'SPR-002', 1, 'Bed sheet replacement'),
        ('AST-BAMBU-PS1', 'SPR-003', 2, 'X/Y axis belts'),
        ('AST-BAMBU-PS1', 'SPR-017', 1, 'Enclosure filter'),
        ('AST-CR30', 'SPR-001', 1, 'Nozzle replacement'),
        ('AST-CR30', 'SPR-004', 1, 'Belt surface replacement'),
        ('AST-CR30', 'SPR-003', 2, 'Drive belts'),
        ('AST-FORM3', 'SPR-005', 1, 'Resin tank replacement'),
        ('AST-FORM3', 'SPR-006', 1, 'Resin supply'),
        ('AST-BANTAM', 'SPR-007', 5, 'Flat end mills'),
        ('AST-BANTAM', 'SPR-008', 3, 'Ball end mills'),
        ('AST-BANTAM', 'SPR-009', 1, 'Spindle bearings'),
        ('AST-CR1', 'SPR-007', 5, 'Flat end mills'),
        ('AST-CR1', 'SPR-009', 1, 'Spindle bearings'),
        ('AST-CR1', 'SPR-010', 1, 'Way lubricant'),
        ('AST-LABFAB', 'SPR-007', 5, 'Flat end mills'),
        ('AST-LABFAB', 'SPR-008', 3, 'Ball end mills'),
        ('AST-LABFAB', 'SPR-010', 1, 'Way lubricant'),
        ('AST-ROWND', 'SPR-009', 1, 'Spindle bearings'),
        ('AST-ROWND', 'SPR-010', 1, 'Way lubricant'),
        ('AST-NIRYO', 'SPR-011', 2, 'Gripper pads'),
        ('AST-NIRYO', 'SPR-013', 1, 'Joint grease'),
        ('AST-XARM', 'SPR-012', 4, 'Vacuum cups'),
        ('AST-XARM', 'SPR-013', 1, 'Joint grease'),
        ('AST-LASER', 'SPR-014', 1, 'Focus lens'),
        ('AST-LASER', 'SPR-015', 1, 'Air assist nozzle'),
        ('AST-CONV', 'SPR-016', 1, 'Belt segment'),
    ]

    for a_id, s_id, qty, note in asset_spare_links:
        link = AssetSpare(
            asset_id=asset_map[a_id].id,
            spare_id=spare_map[s_id].id,
            quantity_required=qty,
            notes=note,
        )
        session.add(link)

    session.flush()
    print(f"  + {len(asset_spare_links)} asset-spare associations")

    # -----------------------------------------------------------------------
    # 6. PM Schedules (10)
    # -----------------------------------------------------------------------
    # Helper to find a meter object by asset_id string and name substring
    def find_meter(asset_id_str, name_sub):
        for md in meters_data:
            if md['asset_id'] == asset_map[asset_id_str].id and name_sub.lower() in md['name'].lower():
                return meter_map[md['meter_id']]
        return None

    pm_schedules_data = [
        {
            'pm_id': 'PM-001', 'name': 'FDM Nozzle Inspection - Bambu P1S',
            'description': 'Inspect nozzle for wear, clogs, and drool. Replace if bore exceeds 0.45mm.',
            'asset_id_str': 'AST-BAMBU-PS1', 'is_active': True,
            'trigger_type': PMTriggerType.CALENDAR, 'frequency_days': 30,
            'lead_time_days': 5, 'work_window_days': 7,
            'last_completed': now - timedelta(days=25),
            'next_due_date': today + timedelta(days=5),
            'priority': WorkOrderPriority.MEDIUM, 'estimated_hours': 0.5,
            'estimated_cost': 25.00, 'work_center_id': 'WC-PRINT',
            'instructions': '1. Heat nozzle to 220C\n2. Remove filament\n3. Cold pull with nylon\n4. Inspect bore with magnifier\n5. Replace if worn',
            'checklist': [
                {'step': 1, 'task': 'Heat nozzle to 220C', 'type': 'action'},
                {'step': 2, 'task': 'Cold pull cleaning', 'type': 'action'},
                {'step': 3, 'task': 'Inspect bore diameter', 'type': 'inspection'},
                {'step': 4, 'task': 'Check for nozzle drool', 'type': 'inspection'},
            ],
            'spares_required': [{'spare_id': 'SPR-001', 'quantity': 1, 'condition': 'if_worn'}],
        },
        {
            'pm_id': 'PM-002', 'name': 'FDM Belt Tension Check - Bambu P1S',
            'description': 'Check and adjust X/Y axis belt tension. Prevent layer shifting.',
            'asset_id_str': 'AST-BAMBU-PS1', 'is_active': True,
            'trigger_type': PMTriggerType.CALENDAR, 'frequency_days': 90,
            'lead_time_days': 7, 'work_window_days': 14,
            'last_completed': now - timedelta(days=85),
            'next_due_date': today + timedelta(days=5),
            'priority': WorkOrderPriority.LOW, 'estimated_hours': 0.75,
            'estimated_cost': 10.00, 'work_center_id': 'WC-PRINT',
            'instructions': '1. Power off printer\n2. Check X-axis belt tension (should twang at ~80Hz)\n3. Check Y-axis belt tension\n4. Adjust tensioners if needed\n5. Run calibration print',
            'checklist': [
                {'step': 1, 'task': 'Power off and LOTO', 'type': 'safety'},
                {'step': 2, 'task': 'X-axis belt tension check', 'type': 'inspection'},
                {'step': 3, 'task': 'Y-axis belt tension check', 'type': 'inspection'},
                {'step': 4, 'task': 'Run calibration cube', 'type': 'verification'},
            ],
            'spares_required': [{'spare_id': 'SPR-003', 'quantity': 1, 'condition': 'if_stretched'}],
        },
        {
            'pm_id': 'PM-003', 'name': 'SLA Resin Tank Replacement - Form 3',
            'description': 'Replace resin tank when clouding is observed or every 2 weeks of active use.',
            'asset_id_str': 'AST-FORM3', 'is_active': True,
            'trigger_type': PMTriggerType.CALENDAR, 'frequency_days': 14,
            'lead_time_days': 3, 'work_window_days': 3,
            'last_completed': now - timedelta(days=18),
            'next_due_date': today - timedelta(days=4),  # OVERDUE
            'priority': WorkOrderPriority.HIGH, 'estimated_hours': 0.5,
            'estimated_cost': 160.00, 'work_center_id': 'WC-PRINT',
            'instructions': '1. Pause/cancel any active prints\n2. Pour remaining resin back into bottle\n3. Remove old tank carefully\n4. Install new tank V2.1\n5. Fill with resin to max line\n6. Run test print',
            'checklist': [
                {'step': 1, 'task': 'Drain resin from old tank', 'type': 'action'},
                {'step': 2, 'task': 'Inspect old tank film', 'type': 'inspection'},
                {'step': 3, 'task': 'Install new tank', 'type': 'action'},
                {'step': 4, 'task': 'Fill resin to max line', 'type': 'action'},
                {'step': 5, 'task': 'Test print validation', 'type': 'verification'},
            ],
            'spares_required': [{'spare_id': 'SPR-005', 'quantity': 1, 'condition': 'always'}],
        },
        {
            'pm_id': 'PM-004', 'name': 'SLA Optics Cleaning - Form 3',
            'description': 'Clean optical window and LPU glass for consistent laser accuracy.',
            'asset_id_str': 'AST-FORM3', 'is_active': True,
            'trigger_type': PMTriggerType.CALENDAR, 'frequency_days': 30,
            'lead_time_days': 5, 'work_window_days': 7,
            'last_completed': now - timedelta(days=22),
            'next_due_date': today + timedelta(days=8),
            'priority': WorkOrderPriority.MEDIUM, 'estimated_hours': 0.75,
            'estimated_cost': 5.00, 'work_center_id': 'WC-PRINT',
            'instructions': '1. Power off printer\n2. Remove resin tank\n3. Clean optical window with PEC pads and IPA\n4. Inspect for scratches\n5. Clean LPU glass with supplied tool\n6. Reassemble and test',
            'checklist': [
                {'step': 1, 'task': 'Power off printer', 'type': 'safety'},
                {'step': 2, 'task': 'Clean optical window', 'type': 'action'},
                {'step': 3, 'task': 'Inspect for scratches', 'type': 'inspection'},
                {'step': 4, 'task': 'Clean LPU glass', 'type': 'action'},
            ],
            'spares_required': [],
        },
        {
            'pm_id': 'PM-005', 'name': 'CNC Spindle Lubrication - Bantam',
            'description': 'Lubricate spindle bearings based on runtime hours meter.',
            'asset_id_str': 'AST-BANTAM', 'is_active': True,
            'trigger_type': PMTriggerType.METER, 'frequency_days': None,
            'meter_asset': 'AST-BANTAM', 'meter_name': 'Spindle Hours',
            'meter_interval': 500.0,
            'lead_time_days': 7, 'work_window_days': 7,
            'last_completed': now - timedelta(days=40),
            'next_due_date': today + timedelta(days=15),
            'priority': WorkOrderPriority.HIGH, 'estimated_hours': 1.5,
            'estimated_cost': 45.00, 'work_center_id': 'WC-CNC',
            'instructions': '1. Power off and LOTO machine\n2. Remove spindle housing cover\n3. Clean old grease from bearings\n4. Apply recommended grease (2ml per bearing)\n5. Reassemble and run spindle warm-up cycle\n6. Check for noise or vibration',
            'checklist': [
                {'step': 1, 'task': 'LOTO machine', 'type': 'safety'},
                {'step': 2, 'task': 'Remove spindle cover', 'type': 'action'},
                {'step': 3, 'task': 'Clean old grease', 'type': 'action'},
                {'step': 4, 'task': 'Apply new grease', 'type': 'action'},
                {'step': 5, 'task': 'Reassemble', 'type': 'action'},
                {'step': 6, 'task': 'Warm-up cycle and vibration check', 'type': 'verification'},
            ],
            'spares_required': [{'spare_id': 'SPR-010', 'quantity': 1, 'condition': 'always'}],
        },
        {
            'pm_id': 'PM-006', 'name': 'CNC Way Cover Inspection',
            'description': 'Inspect way covers and linear guide lubrication on all CNC mills.',
            'asset_id_str': 'AST-CR1', 'is_active': True,
            'trigger_type': PMTriggerType.CALENDAR, 'frequency_days': 60,
            'lead_time_days': 7, 'work_window_days': 14,
            'last_completed': now - timedelta(days=62),
            'next_due_date': today - timedelta(days=2),  # OVERDUE
            'priority': WorkOrderPriority.MEDIUM, 'estimated_hours': 1.0,
            'estimated_cost': 30.00, 'work_center_id': 'WC-CNC',
            'instructions': '1. Power off machine\n2. Inspect way covers for tears or debris\n3. Lubricate linear guides\n4. Check for backlash on each axis\n5. Clean chip tray',
            'checklist': [
                {'step': 1, 'task': 'Inspect way covers', 'type': 'inspection'},
                {'step': 2, 'task': 'Lubricate linear guides', 'type': 'action'},
                {'step': 3, 'task': 'Check backlash', 'type': 'inspection'},
                {'step': 4, 'task': 'Clean chip tray', 'type': 'action'},
            ],
            'spares_required': [{'spare_id': 'SPR-010', 'quantity': 1, 'condition': 'always'}],
        },
        {
            'pm_id': 'PM-007', 'name': 'Robot Joint Calibration - Niryo Ned2',
            'description': 'Full joint calibration and accuracy verification for Niryo Ned2.',
            'asset_id_str': 'AST-NIRYO', 'is_active': True,
            'trigger_type': PMTriggerType.CALENDAR, 'frequency_days': 90,
            'lead_time_days': 7, 'work_window_days': 14,
            'last_completed': now - timedelta(days=70),
            'next_due_date': today + timedelta(days=20),
            'priority': WorkOrderPriority.MEDIUM, 'estimated_hours': 2.0,
            'estimated_cost': 50.00, 'work_center_id': 'WC-ASSEMBLY',
            'instructions': '1. Run auto-calibration sequence via Niryo Studio\n2. Verify each joint zero position\n3. Run pick-and-place accuracy test\n4. Grease joints if needed\n5. Update calibration log',
            'checklist': [
                {'step': 1, 'task': 'Run auto-calibration', 'type': 'action'},
                {'step': 2, 'task': 'Verify joint zero positions', 'type': 'inspection'},
                {'step': 3, 'task': 'Accuracy test with gauge block', 'type': 'verification'},
                {'step': 4, 'task': 'Grease joints if necessary', 'type': 'action'},
            ],
            'spares_required': [{'spare_id': 'SPR-013', 'quantity': 1, 'condition': 'if_needed'}],
        },
        {
            'pm_id': 'PM-008', 'name': 'Laser Lens Cleaning - Longer Ray5',
            'description': 'Clean focus lens and check beam alignment on laser engraver.',
            'asset_id_str': 'AST-LASER', 'is_active': True,
            'trigger_type': PMTriggerType.CALENDAR, 'frequency_days': 45,
            'lead_time_days': 5, 'work_window_days': 7,
            'last_completed': now - timedelta(days=40),
            'next_due_date': today + timedelta(days=5),
            'priority': WorkOrderPriority.MEDIUM, 'estimated_hours': 0.5,
            'estimated_cost': 10.00, 'work_center_id': 'WC-FINISH',
            'instructions': '1. Power off laser\n2. Remove lens assembly\n3. Clean lens with lens paper and IPA\n4. Inspect for pitting or coating damage\n5. Reassemble and run focus test pattern',
            'checklist': [
                {'step': 1, 'task': 'Power off laser', 'type': 'safety'},
                {'step': 2, 'task': 'Remove lens assembly', 'type': 'action'},
                {'step': 3, 'task': 'Clean and inspect lens', 'type': 'inspection'},
                {'step': 4, 'task': 'Focus test pattern', 'type': 'verification'},
            ],
            'spares_required': [{'spare_id': 'SPR-014', 'quantity': 1, 'condition': 'if_damaged'}],
        },
        {
            'pm_id': 'PM-009', 'name': 'Conveyor Belt Tension & Alignment',
            'description': 'Check belt tension, alignment, and motor drive on conveyor.',
            'asset_id_str': 'AST-CONV', 'is_active': True,
            'trigger_type': PMTriggerType.CALENDAR, 'frequency_days': 120,
            'lead_time_days': 14, 'work_window_days': 14,
            'last_completed': now - timedelta(days=60),
            'next_due_date': today + timedelta(days=60),
            'priority': WorkOrderPriority.LOW, 'estimated_hours': 1.0,
            'estimated_cost': 15.00, 'work_center_id': 'WC-ASSEMBLY',
            'instructions': '1. Stop conveyor and LOTO\n2. Check belt tension with spring gauge\n3. Inspect belt surface for wear\n4. Check roller alignment\n5. Lubricate drive motor bearings\n6. Run test cycle',
            'checklist': [
                {'step': 1, 'task': 'LOTO conveyor', 'type': 'safety'},
                {'step': 2, 'task': 'Belt tension check', 'type': 'inspection'},
                {'step': 3, 'task': 'Belt surface inspection', 'type': 'inspection'},
                {'step': 4, 'task': 'Roller alignment', 'type': 'inspection'},
                {'step': 5, 'task': 'Lubricate motor bearings', 'type': 'action'},
            ],
            'spares_required': [],
        },
        {
            'pm_id': 'PM-010', 'name': 'CR-30 Belt Surface Inspection',
            'description': 'Inspect and replace belt surface on Creality CR-30 belt printer.',
            'asset_id_str': 'AST-CR30', 'is_active': True,
            'trigger_type': PMTriggerType.METER, 'frequency_days': None,
            'meter_asset': 'AST-CR30', 'meter_name': 'Runtime Hours',
            'meter_interval': 500.0,
            'lead_time_days': 7, 'work_window_days': 7,
            'last_completed': now - timedelta(days=50),
            'next_due_date': today - timedelta(days=1),  # OVERDUE
            'priority': WorkOrderPriority.HIGH, 'estimated_hours': 1.0,
            'estimated_cost': 95.00, 'work_center_id': 'WC-PRINT',
            'instructions': '1. Power off printer\n2. Remove belt from drive rollers\n3. Inspect surface for delamination and gouges\n4. Replace belt if wear exceeds threshold\n5. Re-tension and level',
            'checklist': [
                {'step': 1, 'task': 'Power off printer', 'type': 'safety'},
                {'step': 2, 'task': 'Remove belt', 'type': 'action'},
                {'step': 3, 'task': 'Inspect belt surface', 'type': 'inspection'},
                {'step': 4, 'task': 'Replace if needed', 'type': 'action'},
                {'step': 5, 'task': 'Tension and level', 'type': 'verification'},
            ],
            'spares_required': [{'spare_id': 'SPR-004', 'quantity': 1, 'condition': 'if_worn'}],
        },
    ]

    pm_map = {}  # pm_id string -> PMSchedule ORM object
    for pmd in pm_schedules_data:
        asset_id_str = pmd.pop('asset_id_str')
        pmd['asset_id'] = asset_map[asset_id_str].id

        # Handle meter-based triggers
        meter_asset = pmd.pop('meter_asset', None)
        meter_name = pmd.pop('meter_name', None)
        if meter_asset and meter_name:
            m_obj = find_meter(meter_asset, meter_name)
            if m_obj:
                pmd['meter_id'] = m_obj.id

        pm = PMSchedule(**pmd)
        session.add(pm)
        pm_map[pmd['pm_id']] = pm

    session.flush()
    print(f"  + {len(pm_schedules_data)} PM schedules")

    # -----------------------------------------------------------------------
    # 7. Failure Codes (10)
    # -----------------------------------------------------------------------
    failure_codes_data = [
        {
            'code': 'FC-MECH-001', 'name': 'Bearing Failure',
            'description': 'Bearing seized, worn, or producing excessive noise/vibration',
            'failure_type': FailureType.MECHANICAL, 'category': 'Rotating Equipment',
            'subcategory': 'Bearings',
            'default_severity': FailureSeverity.MAJOR,
            'applies_to': ['CNC-MILL', 'CNC-LATHE', 'CONVEYOR'],
            'common_causes': ['Insufficient lubrication', 'Contamination', 'Overload', 'Misalignment'],
            'recommended_actions': ['Replace bearing set', 'Check alignment', 'Verify lubrication schedule'],
            'estimated_repair_hours': 3.0, 'is_active': True,
        },
        {
            'code': 'FC-MECH-002', 'name': 'Belt Wear/Breakage',
            'description': 'Drive belt stretched, cracked, or broken causing loss of motion',
            'failure_type': FailureType.MECHANICAL, 'category': 'Drive Systems',
            'subcategory': 'Belts',
            'default_severity': FailureSeverity.MINOR,
            'applies_to': ['FDM-3DP', 'CONVEYOR'],
            'common_causes': ['Normal wear', 'Over-tension', 'Misalignment', 'Debris contamination'],
            'recommended_actions': ['Replace belt', 'Check tensioner', 'Verify alignment'],
            'estimated_repair_hours': 1.0, 'is_active': True,
        },
        {
            'code': 'FC-MECH-003', 'name': 'Nozzle Clog/Wear',
            'description': 'Print nozzle clogged or bore worn beyond tolerance',
            'failure_type': FailureType.MECHANICAL, 'category': 'Extrusion',
            'subcategory': 'Nozzle',
            'default_severity': FailureSeverity.MINOR,
            'applies_to': ['FDM-3DP'],
            'common_causes': ['Filament contamination', 'Heat creep', 'Material carbon buildup'],
            'recommended_actions': ['Cold pull', 'Replace nozzle', 'Check PTFE tube'],
            'estimated_repair_hours': 0.5, 'is_active': True,
        },
        {
            'code': 'FC-ELEC-001', 'name': 'Heater Cartridge Failure',
            'description': 'Heater cartridge open circuit or intermittent heating',
            'failure_type': FailureType.ELECTRICAL, 'category': 'Thermal',
            'subcategory': 'Heaters',
            'default_severity': FailureSeverity.MAJOR,
            'applies_to': ['FDM-3DP'],
            'common_causes': ['Thermal fatigue', 'Loose connection', 'Wire damage'],
            'recommended_actions': ['Replace heater cartridge', 'Check wiring', 'PID re-tune'],
            'estimated_repair_hours': 1.5, 'is_active': True,
        },
        {
            'code': 'FC-ELEC-002', 'name': 'Stepper Motor Failure',
            'description': 'Stepper motor skipping steps, overheating, or no response',
            'failure_type': FailureType.ELECTRICAL, 'category': 'Motion',
            'subcategory': 'Motors',
            'default_severity': FailureSeverity.MAJOR,
            'applies_to': ['FDM-3DP', 'CNC-MILL', 'CNC-LATHE'],
            'common_causes': ['Driver overheating', 'Wiring fault', 'Mechanical binding', 'Motor burnout'],
            'recommended_actions': ['Check driver current', 'Replace motor', 'Check mechanical load'],
            'estimated_repair_hours': 2.0, 'is_active': True,
        },
        {
            'code': 'FC-SOFT-001', 'name': 'Firmware Crash',
            'description': 'Machine controller firmware crash or watchdog reset',
            'failure_type': FailureType.SOFTWARE, 'category': 'Controller',
            'subcategory': 'Firmware',
            'default_severity': FailureSeverity.MINOR,
            'applies_to': ['FDM-3DP', 'SLA-3DP', 'CNC-MILL', 'CNC-LATHE', 'ROBOT-ARM'],
            'common_causes': ['Firmware bug', 'Memory overflow', 'Corrupt G-code', 'EMI interference'],
            'recommended_actions': ['Power cycle', 'Update firmware', 'Check G-code', 'Add EMI shielding'],
            'estimated_repair_hours': 0.5, 'is_active': True,
        },
        {
            'code': 'FC-PROC-001', 'name': 'Print Adhesion Failure',
            'description': 'Part detached from print bed during printing',
            'failure_type': FailureType.PROCESS, 'category': 'Printing',
            'subcategory': 'Adhesion',
            'default_severity': FailureSeverity.MINOR,
            'applies_to': ['FDM-3DP', 'SLA-3DP'],
            'common_causes': ['Bed not level', 'Bed temp too low', 'Contaminated surface', 'Insufficient supports'],
            'recommended_actions': ['Re-level bed', 'Clean surface', 'Adjust first layer', 'Add supports'],
            'estimated_repair_hours': 0.25, 'is_active': True,
        },
        {
            'code': 'FC-MECH-004', 'name': 'Spindle Runout Excessive',
            'description': 'CNC spindle runout exceeds tolerance causing poor surface finish',
            'failure_type': FailureType.MECHANICAL, 'category': 'Rotating Equipment',
            'subcategory': 'Spindle',
            'default_severity': FailureSeverity.MAJOR,
            'applies_to': ['CNC-MILL', 'CNC-LATHE'],
            'common_causes': ['Worn bearings', 'Collet contamination', 'Spindle damage', 'Thermal expansion'],
            'recommended_actions': ['Measure runout with DTI', 'Replace bearings', 'Clean collet', 'Warm up spindle'],
            'estimated_repair_hours': 4.0, 'is_active': True,
        },
        {
            'code': 'FC-MECH-005', 'name': 'Robot Gripper Malfunction',
            'description': 'Robot gripper fails to open, close, or drops parts',
            'failure_type': FailureType.MECHANICAL, 'category': 'End Effector',
            'subcategory': 'Gripper',
            'default_severity': FailureSeverity.MINOR,
            'applies_to': ['ROBOT-ARM'],
            'common_causes': ['Worn gripper pads', 'Pneumatic leak', 'Sensor fault', 'Contamination'],
            'recommended_actions': ['Replace gripper pads', 'Check pneumatic lines', 'Calibrate sensor'],
            'estimated_repair_hours': 0.75, 'is_active': True,
        },
        {
            'code': 'FC-MAT-001', 'name': 'Material Contamination',
            'description': 'Raw material (filament, resin, stock) contaminated or defective',
            'failure_type': FailureType.MATERIAL, 'category': 'Raw Material',
            'subcategory': 'Contamination',
            'default_severity': FailureSeverity.MINOR,
            'applies_to': ['FDM-3DP', 'SLA-3DP', 'CNC-MILL'],
            'common_causes': ['Moisture absorption', 'Expired resin', 'Wrong material loaded', 'Storage issue'],
            'recommended_actions': ['Dry filament', 'Replace resin', 'Verify material lot', 'Improve storage'],
            'estimated_repair_hours': 0.5, 'is_active': True,
        },
    ]

    for fcd in failure_codes_data:
        fc = FailureCode(**fcd)
        session.add(fc)

    session.flush()
    print(f"  + {len(failure_codes_data)} failure codes")

    # -----------------------------------------------------------------------
    # 8. Maintenance Work Orders (15)
    # -----------------------------------------------------------------------
    wo_list = []

    def make_wo(wo_data, tasks_data, labor_data=None, material_data=None):
        """Create a work order with associated tasks, labor, and materials."""
        asset_id_str = wo_data.pop('asset_id_str')
        wo_data['asset_id'] = asset_map[asset_id_str].id

        pm_id_str = wo_data.pop('pm_id_str', None)
        if pm_id_str and pm_id_str in pm_map:
            wo_data['pm_schedule_id'] = pm_map[pm_id_str].id

        wo = MaintenanceWorkOrder(**wo_data)
        session.add(wo)
        session.flush()

        for td in tasks_data:
            td['work_order_id'] = wo.id
            task = WorkOrderTask(**td)
            session.add(task)

        if labor_data:
            for ld in labor_data:
                ld['work_order_id'] = wo.id
                lab = WorkOrderLabor(**ld)
                session.add(lab)

        if material_data:
            for mtd in material_data:
                spare_id_str = mtd.pop('spare_id_str', None)
                if spare_id_str and spare_id_str in spare_map:
                    mtd['spare_id'] = spare_map[spare_id_str].id
                mtd['work_order_id'] = wo.id
                mat = WorkOrderMaterial(**mtd)
                session.add(mat)

        session.flush()
        wo_list.append(wo)
        return wo

    # --- COMPLETED Work Orders (5) ---

    # MWO-001: Completed PM - Nozzle replacement on Bambu P1S (4 days ago)
    make_wo(
        wo_data={
            'wo_number': 'MWO-001', 'description': 'PM: Nozzle inspection and replacement - Bambu P1S',
            'wo_type': WorkOrderType.PREVENTIVE, 'status': WorkOrderStatus.COMPLETED,
            'priority': WorkOrderPriority.MEDIUM, 'asset_id_str': 'AST-BAMBU-PS1',
            'pm_id_str': 'PM-001',
            'reported_date': now - timedelta(days=8),
            'target_start': now - timedelta(days=5),
            'target_completion': now - timedelta(days=4),
            'actual_start': now - timedelta(days=4, hours=9),
            'actual_completion': now - timedelta(days=4, hours=9, minutes=35),
            'assigned_to': 'EMP001', 'work_center_id': 'WC-PRINT',
            'estimated_hours': 0.5, 'actual_hours': 0.6,
            'estimated_cost': 25.00, 'actual_labor_cost': 30.00, 'actual_material_cost': 18.50,
            'instructions': 'Standard nozzle PM per PM-001 checklist.',
            'completion_notes': 'Nozzle bore measured 0.43mm - replaced with new hardened steel nozzle. Cold pull showed minor carbon buildup.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Heat nozzle to 220C', 'instructions': 'Wait for stable temperature',
             'is_completed': True, 'completed_by': 'EMP001', 'completed_date': now - timedelta(days=4, hours=9),
             'estimated_minutes': 5, 'actual_minutes': 5, 'lockout_required': False},
            {'sequence': 20, 'name': 'Perform cold pull', 'instructions': 'Use nylon filament for cold pull',
             'is_completed': True, 'completed_by': 'EMP001', 'completed_date': now - timedelta(days=4, hours=8, minutes=50),
             'estimated_minutes': 10, 'actual_minutes': 12, 'lockout_required': False},
            {'sequence': 30, 'name': 'Inspect and replace nozzle', 'instructions': 'Measure bore with pin gauge',
             'is_completed': True, 'completed_by': 'EMP001', 'completed_date': now - timedelta(days=4, hours=8, minutes=35),
             'estimated_minutes': 15, 'actual_minutes': 18, 'lockout_required': False},
        ],
        labor_data=[
            {'worker_id': 'EMP001', 'craft': 'Technician',
             'start_time': now - timedelta(days=4, hours=9),
             'end_time': now - timedelta(days=4, hours=8, minutes=24),
             'regular_hours': 0.6, 'overtime_hours': 0.0, 'hourly_rate': 50.00, 'total_cost': 30.00},
        ],
        material_data=[
            {'spare_id_str': 'SPR-001', 'item_id': 'INV-NOZZLE-04',
             'description': '0.4mm Hardened Steel Nozzle',
             'quantity_required': 1, 'quantity_used': 1, 'unit_cost': 18.50, 'total_cost': 18.50},
        ],
    )

    # MWO-002: Completed corrective - CR-30 belt replacement (1 day ago)
    make_wo(
        wo_data={
            'wo_number': 'MWO-002', 'description': 'Corrective: CR-30 belt surface showing delamination',
            'wo_type': WorkOrderType.CORRECTIVE, 'status': WorkOrderStatus.COMPLETED,
            'priority': WorkOrderPriority.HIGH, 'asset_id_str': 'AST-CR30',
            'problem_code': 'FC-MECH-002', 'problem_description': 'Belt surface showing delamination at edges, causing print adhesion issues on continuous runs.',
            'failure_code': 'FC-MECH-002',
            'reported_date': now - timedelta(days=3),
            'target_start': now - timedelta(days=2),
            'target_completion': now - timedelta(days=1),
            'actual_start': now - timedelta(days=1, hours=10),
            'actual_completion': now - timedelta(days=1, hours=8, minutes=45),
            'assigned_to': 'EMP002', 'work_center_id': 'WC-PRINT',
            'estimated_hours': 1.0, 'actual_hours': 1.25,
            'estimated_cost': 100.00, 'actual_labor_cost': 62.50, 'actual_material_cost': 89.00,
            'downtime_start': now - timedelta(days=1, hours=10),
            'downtime_end': now - timedelta(days=1, hours=8, minutes=45),
            'downtime_hours': 1.25,
            'instructions': 'Replace belt surface on CR-30. Refer to manufacturer replacement guide.',
            'completion_notes': 'Belt replaced successfully. New belt tensioned to spec. Test print passed QC.',
            'root_cause': 'Belt surface exceeded expected life due to high-temp ABS usage.',
            'corrective_action': 'Reduced max bed temp for ABS to 95C to extend belt life. Updated PM interval.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Power off and remove filament', 'instructions': 'Retract filament fully',
             'is_completed': True, 'completed_by': 'EMP002', 'completed_date': now - timedelta(days=1, hours=9, minutes=50),
             'estimated_minutes': 10, 'actual_minutes': 8, 'lockout_required': True},
            {'sequence': 20, 'name': 'Remove old belt surface', 'instructions': 'Loosen tension rollers first',
             'is_completed': True, 'completed_by': 'EMP002', 'completed_date': now - timedelta(days=1, hours=9, minutes=25),
             'estimated_minutes': 20, 'actual_minutes': 25, 'lockout_required': False},
            {'sequence': 30, 'name': 'Install new belt and tension', 'instructions': 'Tension to 2.5N per spec',
             'is_completed': True, 'completed_by': 'EMP002', 'completed_date': now - timedelta(days=1, hours=9),
             'estimated_minutes': 20, 'actual_minutes': 22, 'lockout_required': False},
            {'sequence': 40, 'name': 'Calibration and test print', 'instructions': 'Run standard test print',
             'is_completed': True, 'completed_by': 'EMP002', 'completed_date': now - timedelta(days=1, hours=8, minutes=45),
             'estimated_minutes': 15, 'actual_minutes': 20, 'lockout_required': False},
        ],
        labor_data=[
            {'worker_id': 'EMP002', 'craft': 'Technician',
             'start_time': now - timedelta(days=1, hours=10),
             'end_time': now - timedelta(days=1, hours=8, minutes=45),
             'regular_hours': 1.25, 'overtime_hours': 0.0, 'hourly_rate': 50.00, 'total_cost': 62.50},
        ],
        material_data=[
            {'spare_id_str': 'SPR-004', 'item_id': 'INV-CR30-BELT',
             'description': 'CR-30 Belt Surface',
             'quantity_required': 1, 'quantity_used': 1, 'unit_cost': 89.00, 'total_cost': 89.00},
        ],
    )

    # MWO-003: Completed PM - Robot joint calibration (7 days ago)
    make_wo(
        wo_data={
            'wo_number': 'MWO-003', 'description': 'PM: Niryo Ned2 joint calibration and accuracy check',
            'wo_type': WorkOrderType.PREVENTIVE, 'status': WorkOrderStatus.COMPLETED,
            'priority': WorkOrderPriority.MEDIUM, 'asset_id_str': 'AST-NIRYO',
            'pm_id_str': 'PM-007',
            'reported_date': now - timedelta(days=10),
            'target_start': now - timedelta(days=8),
            'target_completion': now - timedelta(days=6),
            'actual_start': now - timedelta(days=7, hours=8),
            'actual_completion': now - timedelta(days=7, hours=6),
            'assigned_to': 'EMP003', 'work_center_id': 'WC-ASSEMBLY',
            'estimated_hours': 2.0, 'actual_hours': 2.0,
            'estimated_cost': 50.00, 'actual_labor_cost': 100.00, 'actual_material_cost': 0.0,
            'instructions': 'Full joint calibration per PM-007.',
            'completion_notes': 'All joints calibrated within spec. Joint 3 required minor adjustment. Accuracy test passed at 0.4mm repeatability.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Run auto-calibration', 'instructions': 'Via Niryo Studio software',
             'is_completed': True, 'completed_by': 'EMP003', 'completed_date': now - timedelta(days=7, hours=7, minutes=30),
             'estimated_minutes': 30, 'actual_minutes': 35, 'lockout_required': False},
            {'sequence': 20, 'name': 'Verify joint zero positions', 'instructions': 'Check each joint against reference',
             'is_completed': True, 'completed_by': 'EMP003', 'completed_date': now - timedelta(days=7, hours=7),
             'estimated_minutes': 30, 'actual_minutes': 30, 'lockout_required': False},
            {'sequence': 30, 'name': 'Accuracy test', 'instructions': 'Pick-and-place 10 parts, measure deviation',
             'is_completed': True, 'completed_by': 'EMP003', 'completed_date': now - timedelta(days=7, hours=6, minutes=20),
             'estimated_minutes': 40, 'actual_minutes': 45, 'lockout_required': False},
        ],
        labor_data=[
            {'worker_id': 'EMP003', 'craft': 'Robotics Technician',
             'start_time': now - timedelta(days=7, hours=8),
             'end_time': now - timedelta(days=7, hours=6),
             'regular_hours': 2.0, 'overtime_hours': 0.0, 'hourly_rate': 50.00, 'total_cost': 100.00},
        ],
    )

    # MWO-004: Completed inspection - Laser engraver optics (10 days ago)
    make_wo(
        wo_data={
            'wo_number': 'MWO-004', 'description': 'Inspection: Laser engraver optics and beam alignment',
            'wo_type': WorkOrderType.INSPECTION, 'status': WorkOrderStatus.COMPLETED,
            'priority': WorkOrderPriority.LOW, 'asset_id_str': 'AST-LASER',
            'reported_date': now - timedelta(days=12),
            'target_start': now - timedelta(days=11),
            'target_completion': now - timedelta(days=9),
            'actual_start': now - timedelta(days=10, hours=14),
            'actual_completion': now - timedelta(days=10, hours=13, minutes=30),
            'assigned_to': 'EMP004', 'work_center_id': 'WC-FINISH',
            'estimated_hours': 0.5, 'actual_hours': 0.5,
            'estimated_cost': 10.00, 'actual_labor_cost': 25.00, 'actual_material_cost': 0.0,
            'instructions': 'Inspect laser optics per PM-008 checklist.',
            'completion_notes': 'Lens clean, no pitting observed. Beam alignment within spec. No replacement needed.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Clean focus lens', 'instructions': 'Use lens paper and IPA',
             'is_completed': True, 'completed_by': 'EMP004', 'completed_date': now - timedelta(days=10, hours=13, minutes=45),
             'estimated_minutes': 15, 'actual_minutes': 15, 'lockout_required': False},
            {'sequence': 20, 'name': 'Beam alignment test', 'instructions': 'Run alignment test pattern',
             'is_completed': True, 'completed_by': 'EMP004', 'completed_date': now - timedelta(days=10, hours=13, minutes=30),
             'estimated_minutes': 15, 'actual_minutes': 15, 'lockout_required': False},
        ],
        labor_data=[
            {'worker_id': 'EMP004', 'craft': 'Technician',
             'start_time': now - timedelta(days=10, hours=14),
             'end_time': now - timedelta(days=10, hours=13, minutes=30),
             'regular_hours': 0.5, 'overtime_hours': 0.0, 'hourly_rate': 50.00, 'total_cost': 25.00},
        ],
    )

    # MWO-005: Completed corrective - Gripper pad replacement on xArm (14 days ago)
    make_wo(
        wo_data={
            'wo_number': 'MWO-005', 'description': 'Corrective: xArm vacuum cup worn - dropping parts intermittently',
            'wo_type': WorkOrderType.CORRECTIVE, 'status': WorkOrderStatus.COMPLETED,
            'priority': WorkOrderPriority.HIGH, 'asset_id_str': 'AST-XARM',
            'problem_code': 'FC-MECH-005', 'problem_description': 'xArm dropping bricks during palletizing. Vacuum cups visibly worn.',
            'failure_code': 'FC-MECH-005',
            'reported_date': now - timedelta(days=15),
            'target_start': now - timedelta(days=14),
            'target_completion': now - timedelta(days=13),
            'actual_start': now - timedelta(days=14, hours=7),
            'actual_completion': now - timedelta(days=14, hours=6, minutes=15),
            'assigned_to': 'EMP001', 'work_center_id': 'WC-PACK',
            'estimated_hours': 0.75, 'actual_hours': 0.75,
            'estimated_cost': 40.00, 'actual_labor_cost': 37.50, 'actual_material_cost': 25.50,
            'downtime_start': now - timedelta(days=14, hours=8),
            'downtime_end': now - timedelta(days=14, hours=6, minutes=15),
            'downtime_hours': 1.75,
            'instructions': 'Replace vacuum suction cups on xArm end effector.',
            'completion_notes': 'Replaced 3 worn vacuum cups. Suction test passed. Zero drops in 50-cycle test.',
            'root_cause': 'Vacuum cups degraded from repeated ABS contact at elevated temperatures.',
            'corrective_action': 'Ordered silicone cups rated for higher temps. Updated replacement interval to 90 days.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Power off robot', 'instructions': 'Emergency stop and LOTO',
             'is_completed': True, 'completed_by': 'EMP001', 'completed_date': now - timedelta(days=14, hours=6, minutes=55),
             'estimated_minutes': 5, 'actual_minutes': 5, 'lockout_required': True},
            {'sequence': 20, 'name': 'Replace vacuum cups', 'instructions': 'Replace all 3 cups, check seals',
             'is_completed': True, 'completed_by': 'EMP001', 'completed_date': now - timedelta(days=14, hours=6, minutes=30),
             'estimated_minutes': 25, 'actual_minutes': 25, 'lockout_required': False},
            {'sequence': 30, 'name': 'Suction and cycle test', 'instructions': 'Run 50 pick-and-place cycles',
             'is_completed': True, 'completed_by': 'EMP001', 'completed_date': now - timedelta(days=14, hours=6, minutes=15),
             'estimated_minutes': 15, 'actual_minutes': 15, 'lockout_required': False},
        ],
        labor_data=[
            {'worker_id': 'EMP001', 'craft': 'Robotics Technician',
             'start_time': now - timedelta(days=14, hours=7),
             'end_time': now - timedelta(days=14, hours=6, minutes=15),
             'regular_hours': 0.75, 'overtime_hours': 0.0, 'hourly_rate': 50.00, 'total_cost': 37.50},
        ],
        material_data=[
            {'spare_id_str': 'SPR-012', 'item_id': 'INV-VAC-XARM',
             'description': 'xArm Vacuum Gripper Cup',
             'quantity_required': 3, 'quantity_used': 3, 'unit_cost': 8.50, 'total_cost': 25.50},
        ],
    )

    # --- IN_PROGRESS Work Orders (4) ---

    # MWO-006: In-progress emergency - CNC spindle vibration high on CoastRunner
    make_wo(
        wo_data={
            'wo_number': 'MWO-006', 'description': 'Emergency: CoastRunner CR1 excessive spindle vibration',
            'wo_type': WorkOrderType.EMERGENCY, 'status': WorkOrderStatus.IN_PROGRESS,
            'priority': WorkOrderPriority.EMERGENCY, 'asset_id_str': 'AST-CR1',
            'problem_code': 'FC-MECH-004', 'problem_description': 'Vibration meter reading 4.2 mm/s exceeds warning threshold. Surface finish degraded on last 3 parts.',
            'failure_code': 'FC-MECH-004',
            'reported_date': now - timedelta(hours=4),
            'target_start': now - timedelta(hours=3),
            'target_completion': now + timedelta(hours=4),
            'actual_start': now - timedelta(hours=3),
            'assigned_to': 'EMP002', 'work_center_id': 'WC-CNC',
            'estimated_hours': 4.0, 'actual_hours': 3.0,
            'estimated_cost': 250.00,
            'downtime_start': now - timedelta(hours=4),
            'downtime_hours': 4.0,
            'instructions': 'Diagnose and repair excessive spindle vibration. Check bearings, collet, and balance.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Vibration analysis', 'instructions': 'Measure vibration spectrum at spindle',
             'is_completed': True, 'completed_by': 'EMP002', 'completed_date': now - timedelta(hours=2, minutes=30),
             'estimated_minutes': 30, 'actual_minutes': 30, 'lockout_required': False},
            {'sequence': 20, 'name': 'Inspect collet and toolholder', 'instructions': 'Check for contamination or damage',
             'is_completed': True, 'completed_by': 'EMP002', 'completed_date': now - timedelta(hours=2),
             'estimated_minutes': 20, 'actual_minutes': 25, 'lockout_required': True},
            {'sequence': 30, 'name': 'Replace spindle bearings', 'instructions': 'Install new bearing set ACB-7001',
             'is_completed': False,
             'estimated_minutes': 90, 'lockout_required': True},
            {'sequence': 40, 'name': 'Test cut and vibration recheck', 'instructions': 'Run test program and verify vibration < 2.0 mm/s',
             'is_completed': False,
             'estimated_minutes': 30, 'lockout_required': False},
        ],
        labor_data=[
            {'worker_id': 'EMP002', 'craft': 'CNC Technician',
             'start_time': now - timedelta(hours=3),
             'regular_hours': 3.0, 'overtime_hours': 0.0, 'hourly_rate': 55.00, 'total_cost': 165.00,
             'notes': 'Still in progress'},
        ],
        material_data=[
            {'spare_id_str': 'SPR-009', 'item_id': 'INV-BEAR-SPNDL',
             'description': 'CNC Spindle Bearing Set',
             'quantity_required': 1, 'quantity_used': 0, 'unit_cost': 85.00, 'total_cost': 0.0},
        ],
    )

    # MWO-007: In-progress PM - Labfab CNC spindle lubrication
    make_wo(
        wo_data={
            'wo_number': 'MWO-007', 'description': 'PM: Labfab Runner spindle lubrication and way cover check',
            'wo_type': WorkOrderType.PREVENTIVE, 'status': WorkOrderStatus.IN_PROGRESS,
            'priority': WorkOrderPriority.MEDIUM, 'asset_id_str': 'AST-LABFAB',
            'pm_id_str': 'PM-006',
            'reported_date': now - timedelta(days=2),
            'target_start': now - timedelta(hours=2),
            'target_completion': now + timedelta(hours=2),
            'actual_start': now - timedelta(hours=2),
            'assigned_to': 'EMP003', 'work_center_id': 'WC-CNC',
            'estimated_hours': 1.5, 'actual_hours': 1.0,
            'estimated_cost': 45.00,
            'downtime_start': now - timedelta(hours=2),
            'instructions': 'PM per schedule PM-006. Lubricate spindle and inspect way covers.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'LOTO machine', 'instructions': 'Follow lockout procedure',
             'is_completed': True, 'completed_by': 'EMP003', 'completed_date': now - timedelta(hours=1, minutes=50),
             'estimated_minutes': 10, 'actual_minutes': 10, 'lockout_required': True},
            {'sequence': 20, 'name': 'Inspect way covers', 'instructions': 'Check for tears, debris, and proper seating',
             'is_completed': True, 'completed_by': 'EMP003', 'completed_date': now - timedelta(hours=1, minutes=30),
             'estimated_minutes': 20, 'actual_minutes': 20, 'lockout_required': False},
            {'sequence': 30, 'name': 'Lubricate spindle and guides', 'instructions': 'Apply ISO 68 way oil per spec',
             'is_completed': False,
             'estimated_minutes': 30, 'lockout_required': False},
            {'sequence': 40, 'name': 'Run warm-up and test', 'instructions': 'Run spindle warm-up cycle',
             'is_completed': False,
             'estimated_minutes': 20, 'lockout_required': False},
        ],
        labor_data=[
            {'worker_id': 'EMP003', 'craft': 'CNC Technician',
             'start_time': now - timedelta(hours=2),
             'regular_hours': 1.0, 'overtime_hours': 0.0, 'hourly_rate': 50.00, 'total_cost': 50.00,
             'notes': 'In progress - lubrication step next'},
        ],
        material_data=[
            {'spare_id_str': 'SPR-010', 'item_id': 'INV-LUBE-WAY',
             'description': 'CNC Way Lubricant 500ml',
             'quantity_required': 1, 'quantity_used': 0, 'unit_cost': 22.00, 'total_cost': 0.0},
        ],
    )

    # MWO-008: In-progress predictive - Bambu P1S filament sensor warnings
    make_wo(
        wo_data={
            'wo_number': 'MWO-008', 'description': 'Predictive: Bambu P1S filament sensor intermittent false triggers',
            'wo_type': WorkOrderType.PREDICTIVE, 'status': WorkOrderStatus.IN_PROGRESS,
            'priority': WorkOrderPriority.HIGH, 'asset_id_str': 'AST-BAMBU-PS1',
            'problem_code': 'FC-SOFT-001', 'problem_description': 'Filament runout sensor triggering false positives. May indicate sensor or cable degradation.',
            'reported_date': now - timedelta(hours=6),
            'target_start': now - timedelta(hours=1),
            'target_completion': now + timedelta(hours=3),
            'actual_start': now - timedelta(hours=1),
            'assigned_to': 'EMP001', 'work_center_id': 'WC-PRINT',
            'estimated_hours': 1.5, 'actual_hours': 0.5,
            'estimated_cost': 20.00,
            'instructions': 'Diagnose filament sensor false triggers. Check cable, connector, and sensor element.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Check sensor cable routing', 'instructions': 'Look for pinched or frayed cables',
             'is_completed': True, 'completed_by': 'EMP001', 'completed_date': now - timedelta(minutes=40),
             'estimated_minutes': 15, 'actual_minutes': 15, 'lockout_required': False},
            {'sequence': 20, 'name': 'Test sensor with multimeter', 'instructions': 'Verify continuity and signal levels',
             'is_completed': False,
             'estimated_minutes': 20, 'lockout_required': False},
            {'sequence': 30, 'name': 'Clean or replace sensor', 'instructions': 'Clean contacts. Replace if faulty.',
             'is_completed': False,
             'estimated_minutes': 30, 'lockout_required': False},
        ],
        labor_data=[
            {'worker_id': 'EMP001', 'craft': 'Technician',
             'start_time': now - timedelta(hours=1),
             'regular_hours': 0.5, 'overtime_hours': 0.0, 'hourly_rate': 50.00, 'total_cost': 25.00,
             'notes': 'In progress - cable routing looks OK, testing sensor next'},
        ],
    )

    # MWO-009: In-progress calibration - Rownd Lathe
    make_wo(
        wo_data={
            'wo_number': 'MWO-009', 'description': 'Calibration: Rownd Lathe axis calibration and backlash compensation',
            'wo_type': WorkOrderType.CALIBRATION, 'status': WorkOrderStatus.IN_PROGRESS,
            'priority': WorkOrderPriority.MEDIUM, 'asset_id_str': 'AST-ROWND',
            'reported_date': now - timedelta(days=1),
            'target_start': now - timedelta(hours=3),
            'target_completion': now + timedelta(hours=1),
            'actual_start': now - timedelta(hours=3),
            'assigned_to': 'EMP004', 'work_center_id': 'WC-CNC',
            'estimated_hours': 3.0, 'actual_hours': 2.5,
            'estimated_cost': 30.00,
            'instructions': 'Perform full axis calibration with DTI. Adjust backlash compensation in controller.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Mount DTI on carriage', 'instructions': 'Use magnetic base',
             'is_completed': True, 'completed_by': 'EMP004', 'completed_date': now - timedelta(hours=2, minutes=45),
             'estimated_minutes': 15, 'actual_minutes': 15, 'lockout_required': False},
            {'sequence': 20, 'name': 'Measure X-axis backlash', 'instructions': 'Record at 3 positions',
             'is_completed': True, 'completed_by': 'EMP004', 'completed_date': now - timedelta(hours=2),
             'estimated_minutes': 30, 'actual_minutes': 35, 'lockout_required': False},
            {'sequence': 30, 'name': 'Measure Z-axis backlash', 'instructions': 'Record at 3 positions',
             'is_completed': True, 'completed_by': 'EMP004', 'completed_date': now - timedelta(hours=1, minutes=15),
             'estimated_minutes': 30, 'actual_minutes': 40, 'lockout_required': False},
            {'sequence': 40, 'name': 'Update compensation and verify', 'instructions': 'Enter values in controller, test cut',
             'is_completed': False,
             'estimated_minutes': 45, 'lockout_required': False},
        ],
        labor_data=[
            {'worker_id': 'EMP004', 'craft': 'CNC Technician',
             'start_time': now - timedelta(hours=3),
             'regular_hours': 2.5, 'overtime_hours': 0.0, 'hourly_rate': 50.00, 'total_cost': 125.00,
             'notes': 'Measuring complete, entering compensation values'},
        ],
    )

    # --- SCHEDULED Work Orders (3) ---

    # MWO-010: Scheduled PM - Form 3 resin tank replacement (overdue PM)
    make_wo(
        wo_data={
            'wo_number': 'MWO-010', 'description': 'PM: Form 3 resin tank replacement (OVERDUE)',
            'wo_type': WorkOrderType.PREVENTIVE, 'status': WorkOrderStatus.SCHEDULED,
            'priority': WorkOrderPriority.HIGH, 'asset_id_str': 'AST-FORM3',
            'pm_id_str': 'PM-003',
            'reported_date': now - timedelta(days=5),
            'target_start': now + timedelta(hours=4),
            'target_completion': now + timedelta(hours=8),
            'assigned_to': 'EMP001', 'work_center_id': 'WC-PRINT',
            'estimated_hours': 0.5, 'estimated_cost': 160.00,
            'instructions': 'Replace resin tank per PM-003. Tank overdue by 4 days.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Drain resin from current tank', 'instructions': 'Pour back into resin bottle',
             'is_completed': False, 'estimated_minutes': 10, 'lockout_required': False},
            {'sequence': 20, 'name': 'Replace tank', 'instructions': 'Install new Tank V2.1',
             'is_completed': False, 'estimated_minutes': 10, 'lockout_required': False},
            {'sequence': 30, 'name': 'Fill and test', 'instructions': 'Fill to max line, run test print',
             'is_completed': False, 'estimated_minutes': 20, 'lockout_required': False},
        ],
    )

    # MWO-011: Scheduled PM - Bambu P1S belt tension check
    make_wo(
        wo_data={
            'wo_number': 'MWO-011', 'description': 'PM: Bambu P1S belt tension check',
            'wo_type': WorkOrderType.PREVENTIVE, 'status': WorkOrderStatus.SCHEDULED,
            'priority': WorkOrderPriority.LOW, 'asset_id_str': 'AST-BAMBU-PS1',
            'pm_id_str': 'PM-002',
            'reported_date': now - timedelta(days=1),
            'target_start': now + timedelta(days=3),
            'target_completion': now + timedelta(days=4),
            'assigned_to': 'EMP002', 'work_center_id': 'WC-PRINT',
            'estimated_hours': 0.75, 'estimated_cost': 10.00,
            'instructions': 'Check and adjust X/Y belt tension per PM-002.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Power off and LOTO', 'instructions': 'Follow LOTO procedure',
             'is_completed': False, 'estimated_minutes': 5, 'lockout_required': True},
            {'sequence': 20, 'name': 'Check X/Y belt tension', 'instructions': 'Use frequency method (~80Hz)',
             'is_completed': False, 'estimated_minutes': 20, 'lockout_required': False},
            {'sequence': 30, 'name': 'Run calibration print', 'instructions': 'Print calibration cube',
             'is_completed': False, 'estimated_minutes': 30, 'lockout_required': False},
        ],
    )

    # MWO-012: Scheduled PM - Laser lens cleaning
    make_wo(
        wo_data={
            'wo_number': 'MWO-012', 'description': 'PM: Longer Ray5 laser lens cleaning',
            'wo_type': WorkOrderType.PREVENTIVE, 'status': WorkOrderStatus.SCHEDULED,
            'priority': WorkOrderPriority.MEDIUM, 'asset_id_str': 'AST-LASER',
            'pm_id_str': 'PM-008',
            'reported_date': now - timedelta(days=1),
            'target_start': now + timedelta(days=5),
            'target_completion': now + timedelta(days=6),
            'assigned_to': 'EMP004', 'work_center_id': 'WC-FINISH',
            'estimated_hours': 0.5, 'estimated_cost': 10.00,
            'instructions': 'Clean laser lens per PM-008.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Power off laser', 'instructions': 'Wait 5 min for cooldown',
             'is_completed': False, 'estimated_minutes': 5, 'lockout_required': True},
            {'sequence': 20, 'name': 'Clean and inspect lens', 'instructions': 'Lens paper + IPA',
             'is_completed': False, 'estimated_minutes': 15, 'lockout_required': False},
            {'sequence': 30, 'name': 'Focus test pattern', 'instructions': 'Engrave test grid',
             'is_completed': False, 'estimated_minutes': 10, 'lockout_required': False},
        ],
    )

    # --- WAITING_PARTS Work Orders (2) ---

    # MWO-013: Waiting for HEPA filters (out of stock)
    make_wo(
        wo_data={
            'wo_number': 'MWO-013', 'description': 'PM: Replace HEPA filters on print enclosures',
            'wo_type': WorkOrderType.PREVENTIVE, 'status': WorkOrderStatus.WAITING_PARTS,
            'priority': WorkOrderPriority.MEDIUM, 'asset_id_str': 'AST-BAMBU-PS1',
            'reported_date': now - timedelta(days=5),
            'target_start': now - timedelta(days=2),
            'target_completion': now + timedelta(days=5),
            'assigned_to': 'EMP003', 'work_center_id': 'WC-PRINT',
            'estimated_hours': 0.5, 'estimated_cost': 35.00,
            'instructions': 'Replace HEPA filter cartridge in printer enclosure. Filters on backorder.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Remove old filter', 'instructions': 'Unclip filter housing',
             'is_completed': False, 'estimated_minutes': 5, 'lockout_required': False},
            {'sequence': 20, 'name': 'Install new HEPA filter', 'instructions': 'Ensure proper seal',
             'is_completed': False, 'estimated_minutes': 10, 'lockout_required': False},
        ],
        material_data=[
            {'spare_id_str': 'SPR-017', 'item_id': 'INV-HEPA-ENC',
             'description': 'HEPA Filter Cartridge',
             'quantity_required': 1, 'quantity_used': 0, 'unit_cost': 32.00, 'total_cost': 0.0},
        ],
    )

    # MWO-014: Waiting for CR-30 belt (low stock)
    make_wo(
        wo_data={
            'wo_number': 'MWO-014', 'description': 'Corrective: CR-30 belt tension mechanism sticking',
            'wo_type': WorkOrderType.CORRECTIVE, 'status': WorkOrderStatus.WAITING_PARTS,
            'priority': WorkOrderPriority.HIGH, 'asset_id_str': 'AST-CR30',
            'problem_code': 'FC-MECH-002',
            'problem_description': 'Belt tensioner mechanism binding intermittently. May need new belt and tensioner spring.',
            'reported_date': now - timedelta(days=3),
            'target_start': now + timedelta(days=7),
            'target_completion': now + timedelta(days=10),
            'assigned_to': 'EMP002', 'work_center_id': 'WC-PRINT',
            'estimated_hours': 1.5, 'estimated_cost': 100.00,
            'instructions': 'Replace belt tension mechanism. Belt on order (lead time 14 days from Creality).',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Remove tension mechanism', 'instructions': 'Disassemble belt path',
             'is_completed': False, 'estimated_minutes': 30, 'lockout_required': True},
            {'sequence': 20, 'name': 'Replace belt and tensioner', 'instructions': 'Install new parts',
             'is_completed': False, 'estimated_minutes': 30, 'lockout_required': False},
            {'sequence': 30, 'name': 'Re-tension and calibrate', 'instructions': 'Tension to 2.5N, level bed',
             'is_completed': False, 'estimated_minutes': 30, 'lockout_required': False},
        ],
    )

    # --- DRAFT Work Order (1) ---

    # MWO-015: Draft - Conveyor motor noise reported
    make_wo(
        wo_data={
            'wo_number': 'MWO-015', 'description': 'Reported: Niryo Conveyor motor making unusual grinding noise',
            'wo_type': WorkOrderType.CORRECTIVE, 'status': WorkOrderStatus.DRAFT,
            'priority': WorkOrderPriority.MEDIUM, 'asset_id_str': 'AST-CONV',
            'problem_code': 'FC-MECH-001',
            'problem_description': 'Operator EMP004 reported grinding noise from conveyor drive motor during shift. Not yet assessed.',
            'reported_date': now - timedelta(hours=2),
            'work_center_id': 'WC-ASSEMBLY',
            'estimated_hours': 2.0,
            'instructions': 'Investigate grinding noise from conveyor drive motor. Assess bearing condition.',
        },
        tasks_data=[
            {'sequence': 10, 'name': 'Inspect motor and drive', 'instructions': 'Listen, feel for vibration, check temperature',
             'is_completed': False, 'estimated_minutes': 20, 'lockout_required': False},
            {'sequence': 20, 'name': 'Assess repair needed', 'instructions': 'Determine if bearing replacement required',
             'is_completed': False, 'estimated_minutes': 10, 'lockout_required': False},
        ],
    )

    session.commit()
    print(f"  + {len(wo_list)} maintenance work orders (with tasks, labor, materials)")
    print(f"    CMMS seed complete: {len(asset_classes_data)} classes, {len(assets_data)} assets, "
          f"{len(meters_data)} meters, {reading_count} readings, {len(spares_data)} spares, "
          f"{len(pm_schedules_data)} PM schedules, {len(failure_codes_data)} failure codes, "
          f"{len(wo_list)} work orders")


def seed_erp_data(session):
    """Seed ERP data: Partners, Items, Sales/Purchase Orders, Inventory."""
    from models.erp.partners import Partner, PartnerType, PartnerStatus, PaymentTerms
    from models.erp.items import Item, ItemType, ItemStatus, ItemCategory
    from models.erp.sales import SalesOrder, SalesOrderStatus, SalesOrderLine
    from models.erp.purchasing import PurchaseOrder, PurchaseOrderStatus, PurchaseOrderLine
    from models.erp.inventory import Location, LocationType, InventoryBalance
    from datetime import date

    print("\n[ERP] Seeding partners, items, orders, inventory...")

    # --- Clear previous ERP seed data (including dependent financial tables) ---
    from models.erp.financial import JournalLine, JournalEntry, GLAccount
    from models.erp.inventory import InventoryTransaction
    from models.qms.supplier_quality import SupplierQualityRating

    # Child/dependent tables first (FK order)
    for model in [
        JournalLine, JournalEntry,          # JournalEntry.partner_id → partners
        InventoryTransaction,                # references items, locations
        SupplierQualityRating,               # vendor_id → partners
        SalesOrderLine, SalesOrder,          # customer_id → partners
        PurchaseOrderLine, PurchaseOrder,    # vendor_id → partners
        InventoryBalance,                    # references items, locations
        Item, ItemCategory, Location,
        GLAccount,                           # referenced by JournalLine (already deleted)
        Partner,
    ]:
        session.query(model).delete(synchronize_session='fetch')
    session.commit()

    # --- Partners (Customers) ---
    customers_data = [
        {'partner_id': 'CUST001', 'name': 'Brick Builders Inc', 'email': 'orders@brickbuilders.com',
         'phone': '(555) 100-2001', 'city': 'Portland', 'state': 'OR', 'country': 'US',
         'credit_limit': 50000, 'payment_terms': PaymentTerms.NET_30},
        {'partner_id': 'CUST002', 'name': 'LEGO World Shop', 'email': 'purchasing@legoworldshop.com',
         'phone': '(555) 200-3002', 'city': 'Seattle', 'state': 'WA', 'country': 'US',
         'credit_limit': 75000, 'payment_terms': PaymentTerms.NET_30},
        {'partner_id': 'CUST003', 'name': 'Creative Toy Distributors', 'email': 'buy@creativetoys.com',
         'phone': '(555) 300-4003', 'city': 'San Francisco', 'state': 'CA', 'country': 'US',
         'credit_limit': 100000, 'payment_terms': PaymentTerms.NET_60},
        {'partner_id': 'CUST004', 'name': 'MiniWorld Hobby Store', 'email': 'info@miniworld.com',
         'phone': '(555) 400-5004', 'city': 'Denver', 'state': 'CO', 'country': 'US',
         'credit_limit': 25000, 'payment_terms': PaymentTerms.NET_30},
    ]

    customer_objs = {}
    for c in customers_data:
        partner = Partner(
            partner_id=c['partner_id'], name=c['name'],
            partner_type=PartnerType.CUSTOMER, status=PartnerStatus.ACTIVE,
            email=c['email'], phone=c['phone'],
            city=c['city'], state=c['state'], country=c['country'],
            credit_limit=c['credit_limit'], payment_terms=c['payment_terms'],
            currency='USD',
        )
        session.add(partner)
        customer_objs[c['partner_id']] = partner

    # --- Partners (Vendors) — match vendor IDs used in CMMS spare parts ---
    vendors_data = [
        {'partner_id': 'VEND001', 'name': 'Filament Supply Co', 'email': 'sales@filamentsupply.com',
         'phone': '(555) 500-1001', 'city': 'Austin', 'state': 'TX', 'country': 'US',
         'lead_time_days': 5, 'payment_terms': PaymentTerms.NET_30},
        {'partner_id': 'VEND002', 'name': 'Precision Resin Labs', 'email': 'orders@precisionresin.com',
         'phone': '(555) 600-2002', 'city': 'Boston', 'state': 'MA', 'country': 'US',
         'lead_time_days': 7, 'payment_terms': PaymentTerms.NET_30},
        {'partner_id': 'VEND003', 'name': 'Industrial Plastics Corp', 'email': 'sales@indplastics.com',
         'phone': '(555) 700-3003', 'city': 'Chicago', 'state': 'IL', 'country': 'US',
         'lead_time_days': 10, 'payment_terms': PaymentTerms.NET_60},
        {'partner_id': 'VEND004', 'name': 'Packaging Direct', 'email': 'orders@packdirect.com',
         'phone': '(555) 800-4004', 'city': 'Nashville', 'state': 'TN', 'country': 'US',
         'lead_time_days': 3, 'payment_terms': PaymentTerms.DUE_ON_RECEIPT},
    ]

    vendor_objs = {}
    for v in vendors_data:
        partner = Partner(
            partner_id=v['partner_id'], name=v['name'],
            partner_type=PartnerType.VENDOR, status=PartnerStatus.ACTIVE,
            email=v['email'], phone=v['phone'],
            city=v['city'], state=v['state'], country=v['country'],
            lead_time_days=v.get('lead_time_days'), payment_terms=v['payment_terms'],
            currency='USD',
        )
        session.add(partner)
        vendor_objs[v['partner_id']] = partner

    session.flush()

    # --- Item Categories ---
    cat_fg = ItemCategory(code='FG', name='Finished Goods', description='Completed LEGO bricks and parts')
    cat_rm = ItemCategory(code='RM', name='Raw Materials', description='Filaments, resins, and stock')
    cat_pkg = ItemCategory(code='PKG', name='Packaging', description='Bags, labels, boxes')
    session.add_all([cat_fg, cat_rm, cat_pkg])
    session.flush()

    # --- Items (Raw Materials + Finished Goods matching PRODUCTS) ---
    items_data = [
        # Raw materials
        {'item_id': 'PLA-RED-1KG', 'name': 'PLA Filament 1.75mm Red 1kg', 'type': ItemType.RAW_MATERIAL,
         'uom': 'KG', 'cost': 22.00, 'category': cat_rm, 'purchasable': True, 'salable': False,
         'safety_stock': 5, 'reorder_point': 3, 'reorder_qty': 10},
        {'item_id': 'PLA-BLU-1KG', 'name': 'PLA Filament 1.75mm Blue 1kg', 'type': ItemType.RAW_MATERIAL,
         'uom': 'KG', 'cost': 22.00, 'category': cat_rm, 'purchasable': True, 'salable': False,
         'safety_stock': 5, 'reorder_point': 3, 'reorder_qty': 10},
        {'item_id': 'PLA-YLW-1KG', 'name': 'PLA Filament 1.75mm Yellow 1kg', 'type': ItemType.RAW_MATERIAL,
         'uom': 'KG', 'cost': 22.00, 'category': cat_rm, 'purchasable': True, 'salable': False,
         'safety_stock': 3, 'reorder_point': 2, 'reorder_qty': 8},
        {'item_id': 'PLA-WHT-1KG', 'name': 'PLA Filament 1.75mm White 1kg', 'type': ItemType.RAW_MATERIAL,
         'uom': 'KG', 'cost': 22.00, 'category': cat_rm, 'purchasable': True, 'salable': False,
         'safety_stock': 5, 'reorder_point': 3, 'reorder_qty': 10},
        {'item_id': 'RESIN-GRY-1L', 'name': 'Grey Standard Resin 1L', 'type': ItemType.RAW_MATERIAL,
         'uom': 'L', 'cost': 45.00, 'category': cat_rm, 'purchasable': True, 'salable': False,
         'safety_stock': 3, 'reorder_point': 2, 'reorder_qty': 6},
        {'item_id': 'ABS-GRN-SHT', 'name': 'ABS Sheet 300x300x3mm Green', 'type': ItemType.RAW_MATERIAL,
         'uom': 'EA', 'cost': 8.50, 'category': cat_rm, 'purchasable': True, 'salable': False,
         'safety_stock': 20, 'reorder_point': 10, 'reorder_qty': 50},
        {'item_id': 'ABS-GRY-SHT', 'name': 'ABS Sheet 300x300x3mm Grey', 'type': ItemType.RAW_MATERIAL,
         'uom': 'EA', 'cost': 8.50, 'category': cat_rm, 'purchasable': True, 'salable': False,
         'safety_stock': 15, 'reorder_point': 8, 'reorder_qty': 40},
        {'item_id': 'NYL-ROD-12', 'name': 'Nylon Rod 12mm x 300mm', 'type': ItemType.RAW_MATERIAL,
         'uom': 'EA', 'cost': 3.20, 'category': cat_rm, 'purchasable': True, 'salable': False,
         'safety_stock': 30, 'reorder_point': 15, 'reorder_qty': 100},
        {'item_id': 'NYL-ROD-8', 'name': 'Nylon Rod 8mm x 300mm', 'type': ItemType.RAW_MATERIAL,
         'uom': 'EA', 'cost': 2.10, 'category': cat_rm, 'purchasable': True, 'salable': False,
         'safety_stock': 30, 'reorder_point': 15, 'reorder_qty': 100},
        {'item_id': 'PKG-BAG-SM', 'name': 'Resealable Bag Small (100pk)', 'type': ItemType.CONSUMABLE,
         'uom': 'PK', 'cost': 12.00, 'category': cat_pkg, 'purchasable': True, 'salable': False,
         'safety_stock': 5, 'reorder_point': 3, 'reorder_qty': 10},
        # Finished goods (matching PRODUCTS)
        {'item_id': 'brick_2x4_red', 'name': '2x4 Brick Red', 'type': ItemType.FINISHED_GOOD,
         'uom': 'EA', 'cost': 0.15, 'price': 0.35, 'category': cat_fg,
         'purchasable': False, 'salable': True, 'manufactured': True},
        {'item_id': 'brick_2x4_blue', 'name': '2x4 Brick Blue', 'type': ItemType.FINISHED_GOOD,
         'uom': 'EA', 'cost': 0.15, 'price': 0.35, 'category': cat_fg,
         'purchasable': False, 'salable': True, 'manufactured': True},
        {'item_id': 'brick_2x4_yellow', 'name': '2x4 Brick Yellow', 'type': ItemType.FINISHED_GOOD,
         'uom': 'EA', 'cost': 0.15, 'price': 0.35, 'category': cat_fg,
         'purchasable': False, 'salable': True, 'manufactured': True},
        {'item_id': 'brick_2x4_white', 'name': '2x4 Brick White', 'type': ItemType.FINISHED_GOOD,
         'uom': 'EA', 'cost': 0.15, 'price': 0.35, 'category': cat_fg,
         'purchasable': False, 'salable': True, 'manufactured': True},
        {'item_id': 'brick_2x2_red', 'name': '2x2 Brick Red', 'type': ItemType.FINISHED_GOOD,
         'uom': 'EA', 'cost': 0.10, 'price': 0.25, 'category': cat_fg,
         'purchasable': False, 'salable': True, 'manufactured': True},
        {'item_id': 'gear_8t', 'name': '8-Tooth Technic Gear', 'type': ItemType.FINISHED_GOOD,
         'uom': 'EA', 'cost': 0.45, 'price': 0.95, 'category': cat_fg,
         'purchasable': False, 'salable': True, 'manufactured': True},
        {'item_id': 'gear_24t', 'name': '24-Tooth Technic Gear', 'type': ItemType.FINISHED_GOOD,
         'uom': 'EA', 'cost': 0.55, 'price': 1.10, 'category': cat_fg,
         'purchasable': False, 'salable': True, 'manufactured': True},
        {'item_id': 'baseplate_16x16', 'name': '16x16 Baseplate Green', 'type': ItemType.FINISHED_GOOD,
         'uom': 'EA', 'cost': 2.80, 'price': 5.99, 'category': cat_fg,
         'purchasable': False, 'salable': True, 'manufactured': True},
        {'item_id': 'axle_4l', 'name': 'Technic Axle 4L', 'type': ItemType.FINISHED_GOOD,
         'uom': 'EA', 'cost': 0.20, 'price': 0.45, 'category': cat_fg,
         'purchasable': False, 'salable': True, 'manufactured': True},
    ]

    item_objs = {}
    for it in items_data:
        item = Item(
            item_id=it['item_id'], name=it['name'],
            item_type=it['type'], status=ItemStatus.ACTIVE,
            category_id=it['category'].id,
            base_uom=it['uom'], standard_cost=it['cost'],
            list_price=it.get('price'), average_cost=it['cost'],
            is_purchasable=it.get('purchasable', False),
            is_salable=it.get('salable', False),
            is_manufactured=it.get('manufactured', False),
            safety_stock=it.get('safety_stock'),
            reorder_point=it.get('reorder_point'),
            reorder_quantity=it.get('reorder_qty'),
            lead_time_days=it.get('lead_time_days', 7),
        )
        session.add(item)
        item_objs[it['item_id']] = item

    session.flush()

    # --- Locations ---
    locations_data = [
        {'location_id': 'WH-MAIN', 'name': 'Main Warehouse', 'type': LocationType.WAREHOUSE},
        {'location_id': 'WH-RAW', 'name': 'Raw Material Storage', 'type': LocationType.WAREHOUSE},
        {'location_id': 'PROD-FDM', 'name': 'FDM Production Floor', 'type': LocationType.PRODUCTION},
        {'location_id': 'PROD-SLA', 'name': 'SLA Production Floor', 'type': LocationType.PRODUCTION},
        {'location_id': 'PROD-CNC', 'name': 'CNC Production Floor', 'type': LocationType.PRODUCTION},
        {'location_id': 'STG-SHIP', 'name': 'Shipping Staging', 'type': LocationType.SHIPPING},
        {'location_id': 'QC-HOLD', 'name': 'QC Hold Area', 'type': LocationType.QUALITY},
    ]

    loc_objs = {}
    for loc in locations_data:
        location = Location(
            location_id=loc['location_id'], name=loc['name'],
            location_type=loc['type'], is_active=True,
        )
        session.add(location)
        loc_objs[loc['location_id']] = location

    session.flush()

    # --- Inventory Balances ---
    today = date.today()
    balances_data = [
        ('PLA-RED-1KG', 'WH-RAW', 8, 2, 22.00),
        ('PLA-BLU-1KG', 'WH-RAW', 6, 1, 22.00),
        ('PLA-YLW-1KG', 'WH-RAW', 4, 1, 22.00),
        ('PLA-WHT-1KG', 'WH-RAW', 10, 3, 22.00),
        ('RESIN-GRY-1L', 'WH-RAW', 5, 1, 45.00),
        ('ABS-GRN-SHT', 'WH-RAW', 25, 5, 8.50),
        ('ABS-GRY-SHT', 'WH-RAW', 12, 3, 8.50),
        ('NYL-ROD-12', 'WH-RAW', 45, 10, 3.20),
        ('NYL-ROD-8', 'WH-RAW', 35, 8, 2.10),
        ('PKG-BAG-SM', 'WH-MAIN', 8, 0, 12.00),
        # Finished goods in main warehouse
        ('brick_2x4_red', 'WH-MAIN', 520, 100, 0.15),
        ('brick_2x4_blue', 'WH-MAIN', 380, 50, 0.15),
        ('brick_2x4_yellow', 'WH-MAIN', 150, 30, 0.15),
        ('brick_2x4_white', 'WH-MAIN', 620, 120, 0.15),
        ('brick_2x2_red', 'WH-MAIN', 410, 80, 0.10),
        ('gear_8t', 'WH-MAIN', 95, 20, 0.45),
        ('gear_24t', 'WH-MAIN', 72, 15, 0.55),
        ('baseplate_16x16', 'WH-MAIN', 45, 10, 2.80),
        ('axle_4l', 'WH-MAIN', 180, 40, 0.20),
    ]

    for item_id, loc_id, on_hand, allocated, cost in balances_data:
        bal = InventoryBalance(
            item_id=item_objs[item_id].id,
            location_id=loc_objs[loc_id].id,
            quantity_on_hand=on_hand,
            quantity_allocated=allocated,
            quantity_available=on_hand - allocated,
            unit_cost=cost,
            total_value=on_hand * cost,
            last_receipt_date=datetime.now() - timedelta(days=random.randint(1, 15)),
        )
        session.add(bal)

    # --- Sales Orders ---
    so_data = [
        {'num': 'SO-2026-101', 'cust': 'CUST001', 'status': SalesOrderStatus.RELEASED,
         'days_ago': 8, 'due_in': 7, 'subtotal': 175.00, 'tax': 14.00, 'shipped': 0},
        {'num': 'SO-2026-102', 'cust': 'CUST002', 'status': SalesOrderStatus.PARTIALLY_SHIPPED,
         'days_ago': 15, 'due_in': -2, 'subtotal': 450.00, 'tax': 36.00, 'shipped': 300},
        {'num': 'SO-2026-103', 'cust': 'CUST003', 'status': SalesOrderStatus.APPROVED,
         'days_ago': 3, 'due_in': 14, 'subtotal': 1250.00, 'tax': 100.00, 'shipped': 0},
        {'num': 'SO-2026-104', 'cust': 'CUST001', 'status': SalesOrderStatus.COMPLETED,
         'days_ago': 30, 'due_in': -15, 'subtotal': 89.50, 'tax': 7.16, 'shipped': 500},
        {'num': 'SO-2026-105', 'cust': 'CUST004', 'status': SalesOrderStatus.DRAFT,
         'days_ago': 1, 'due_in': 21, 'subtotal': 620.00, 'tax': 49.60, 'shipped': 0},
        {'num': 'SO-2026-106', 'cust': 'CUST002', 'status': SalesOrderStatus.SHIPPED,
         'days_ago': 20, 'due_in': -5, 'subtotal': 325.00, 'tax': 26.00, 'shipped': 1000},
    ]

    for so in so_data:
        order = SalesOrder(
            order_number=so['num'],
            customer_id=customer_objs[so['cust']].id,
            status=so['status'],
            order_date=today - timedelta(days=so['days_ago']),
            requested_date=today + timedelta(days=so['due_in']),
            subtotal=so['subtotal'],
            tax_amount=so['tax'],
            total=so['subtotal'] + so['tax'],
            quantity_shipped=so['shipped'],
            payment_terms='Net 30',
        )
        session.add(order)

    # --- Purchase Orders ---
    po_data = [
        {'num': 'PO-2026-001', 'vend': 'VEND001', 'status': PurchaseOrderStatus.SENT,
         'days_ago': 5, 'due_in': 10, 'subtotal': 440.00, 'tax': 0, 'received': 0},
        {'num': 'PO-2026-002', 'vend': 'VEND002', 'status': PurchaseOrderStatus.PARTIALLY_RECEIVED,
         'days_ago': 18, 'due_in': -3, 'subtotal': 270.00, 'tax': 0, 'received': 3},
        {'num': 'PO-2026-003', 'vend': 'VEND003', 'status': PurchaseOrderStatus.RECEIVED,
         'days_ago': 25, 'due_in': -10, 'subtotal': 850.00, 'tax': 0, 'received': 100},
        {'num': 'PO-2026-004', 'vend': 'VEND001', 'status': PurchaseOrderStatus.DRAFT,
         'days_ago': 0, 'due_in': 14, 'subtotal': 660.00, 'tax': 0, 'received': 0},
        {'num': 'PO-2026-005', 'vend': 'VEND004', 'status': PurchaseOrderStatus.APPROVED,
         'days_ago': 2, 'due_in': 5, 'subtotal': 120.00, 'tax': 0, 'received': 0},
    ]

    for po in po_data:
        order = PurchaseOrder(
            po_number=po['num'],
            vendor_id=vendor_objs[po['vend']].id,
            status=po['status'],
            order_date=today - timedelta(days=po['days_ago']),
            required_date=today + timedelta(days=po['due_in']),
            subtotal=po['subtotal'],
            tax_amount=po['tax'],
            total=po['subtotal'] + po['tax'],
            quantity_received=po['received'],
            payment_terms='Net 30',
        )
        session.add(order)

    session.commit()

    print(f"  + {len(customers_data)} customers, {len(vendors_data)} vendors")
    print(f"  + {len(items_data)} items ({sum(1 for i in items_data if i['type'] == ItemType.RAW_MATERIAL)} raw, "
          f"{sum(1 for i in items_data if i['type'] == ItemType.FINISHED_GOOD)} finished)")
    print(f"  + {len(locations_data)} locations, {len(balances_data)} inventory balances")
    print(f"  + {len(so_data)} sales orders, {len(po_data)} purchase orders")


def seed_operational_data(session):
    """Seed operational data: downtime, OEE, production counts, workers, time entries, machine events."""
    import random as _rand
    from datetime import datetime, date, timedelta

    from models.mes.oee import DowntimeEvent, DowntimeReason, ProductionCount, OEERecord
    from models.mes.labor import Worker, WorkerStatus, TimeEntry
    from models.scada.machines import Machine, MachineEvent
    from models.mes.work_orders import Job, JobStatus, WorkOrder

    _rand.seed(42)
    now = datetime.utcnow()
    today = date.today()

    # ── Cleanup ────────────────────────────────────────────────────────────
    session.query(TimeEntry).delete(synchronize_session='fetch')
    session.query(Worker).filter(Worker.is_deleted == False).delete(synchronize_session='fetch')
    session.query(DowntimeEvent).delete(synchronize_session='fetch')
    session.query(ProductionCount).delete(synchronize_session='fetch')
    session.query(OEERecord).delete(synchronize_session='fetch')
    session.query(MachineEvent).delete(synchronize_session='fetch')
    session.commit()
    print("  Cleared previous operational data")

    # ── Lookup helpers ─────────────────────────────────────────────────────
    machines_by_str = {m.machine_id: m for m in session.query(Machine).all()}
    linkable_jobs = (
        session.query(Job)
        .filter(Job.status.in_([JobStatus.COMPLETED, JobStatus.RUNNING]))
        .all()
    )
    job_ids = [j.id for j in linkable_jobs] if linkable_jobs else []

    PRODUCTION_MACHINES = [
        'bambu-ps1', 'creality-cr30', 'formlabs-3',
        'bantam-explorer', 'coastrunner-cr1', 'rownd-lathe',
        'labfab-runner', 'longer-ray-laser',
    ]
    ALL_MACHINES = PRODUCTION_MACHINES + ['niryo-ned2', 'xarm-lite6']

    MACHINE_PROFILES = {
        'bambu-ps1':       {'type': 'fdm',   'parts_lo': 20, 'parts_hi': 40, 'quality_lo': 0.95, 'quality_hi': 0.99, 'cycle_s': 180, 'shifts': 1},
        'creality-cr30':   {'type': 'fdm',   'parts_lo': 20, 'parts_hi': 40, 'quality_lo': 0.95, 'quality_hi': 0.99, 'cycle_s': 200, 'shifts': 1},
        'formlabs-3':      {'type': 'sla',   'parts_lo':  8, 'parts_hi': 15, 'quality_lo': 0.96, 'quality_hi': 0.99, 'cycle_s': 420, 'shifts': 1},
        'bantam-explorer': {'type': 'cnc',   'parts_lo': 15, 'parts_hi': 30, 'quality_lo': 0.97, 'quality_hi': 0.99, 'cycle_s': 240, 'shifts': 2},
        'coastrunner-cr1': {'type': 'cnc',   'parts_lo': 15, 'parts_hi': 30, 'quality_lo': 0.97, 'quality_hi': 0.99, 'cycle_s': 260, 'shifts': 1},
        'rownd-lathe':     {'type': 'lathe', 'parts_lo': 12, 'parts_hi': 25, 'quality_lo': 0.97, 'quality_hi': 0.99, 'cycle_s': 300, 'shifts': 1},
        'labfab-runner':   {'type': 'cnc',   'parts_lo': 15, 'parts_hi': 30, 'quality_lo': 0.97, 'quality_hi': 0.99, 'cycle_s': 250, 'shifts': 1},
        'longer-ray-laser':{'type': 'laser', 'parts_lo': 25, 'parts_hi': 45, 'quality_lo': 0.97, 'quality_hi': 0.99, 'cycle_s': 150, 'shifts': 1},
        'niryo-ned2':      {'type': 'robot', 'parts_lo': 30, 'parts_hi': 60, 'quality_lo': 0.99, 'quality_hi': 1.00, 'cycle_s':  90, 'shifts': 2},
        'xarm-lite6':      {'type': 'robot', 'parts_lo': 30, 'parts_hi': 60, 'quality_lo': 0.99, 'quality_hi': 1.00, 'cycle_s':  80, 'shifts': 2},
    }

    # ══════════════════════════════════════════════════════════════════════
    # 1. DOWNTIME EVENTS  (~30 records over past 7 days)
    # ══════════════════════════════════════════════════════════════════════
    DOWNTIME_POOL = [
        (DowntimeReason.CHANGEOVER,            True,  15, 45, "Changeover for {product} on {machine}", "Scheduled product changeover", "Standard changeover SOP followed"),
        (DowntimeReason.CHANGEOVER,            True,  20, 40, "Tool swap for next batch on {machine}", "Different tooling required", "Pre-staged tooling for next run"),
        (DowntimeReason.SETUP,                 True,  15, 45, "Initial setup for morning run on {machine}", "First-run calibration", "Completed setup checklist"),
        (DowntimeReason.SETUP,                 True,  20, 35, "Fixture alignment on {machine}", "New fixture required", "Fixture aligned and verified"),
        (DowntimeReason.FILAMENT_CHANGE,       True,  10, 25, "Filament spool change on {machine}", "Spool depleted", "New spool loaded and purged"),
        (DowntimeReason.MATERIAL,              True,  10, 20, "Resin refill on {machine}", "Resin tank low", "Resin topped up and leveled"),
        (DowntimeReason.MATERIAL,              False, 15, 25, "Waiting for material delivery to {machine}", "Material not staged on time", "Updated staging schedule with warehouse"),
        (DowntimeReason.MAINTENANCE_PLANNED,   True,  30, 60, "Scheduled PM on {machine}", "Weekly maintenance window", "PM checklist completed"),
        (DowntimeReason.MAINTENANCE_UNPLANNED, False, 45,120, "Unexpected bearing noise on {machine}", "Worn linear bearing", "Bearing replaced; ordered spare set"),
        (DowntimeReason.MAINTENANCE_UNPLANNED, False, 30, 90, "Hydraulic leak detected on {machine}", "Worn seal on cylinder", "Seal replaced, fluid topped off"),
        (DowntimeReason.QUALITY_ISSUE,         False,  5, 30, "Dimensional out-of-spec on {machine}", "Tool wear beyond tolerance", "Tool replaced, first-article re-inspected"),
        (DowntimeReason.BED_ADHESION,          False,  5, 20, "Print lifting from bed on {machine}", "Bed surface contamination", "Bed cleaned with IPA, re-leveled"),
        (DowntimeReason.NOZZLE_CLOG,           False, 10, 30, "Nozzle clog during print on {machine}", "Contaminated filament batch", "Cold pull performed, nozzle cleared"),
        (DowntimeReason.CALIBRATION,           True,  15, 40, "Probe calibration on {machine}", "Scheduled monthly calibration", "Calibration cert updated"),
        (DowntimeReason.SOFTWARE,              False, 10, 30, "Slicer crash required restart on {machine}", "Memory overflow in slicer", "Slicer updated to latest patch"),
        (DowntimeReason.OTHER,                 False, 10, 25, "Operator training exercise on {machine}", "New hire shadowing", "Training log signed off"),
    ]
    DOWNTIME_WEIGHTS = [8, 7, 5, 4, 5, 4, 3, 3, 2, 2, 2, 2, 1, 2, 1, 2]

    products = ['2x4 Brick Red', '2x2 Brick Blue', 'Technic Axle', 'Minifig Torso', 'Baseplate 16x16']
    reporters = ['EMP001', 'EMP002', 'EMP003', 'EMP004']
    downtime_records = []

    for _ in range(30):
        template = _rand.choices(DOWNTIME_POOL, weights=DOWNTIME_WEIGHTS, k=1)[0]
        reason, planned, dur_lo, dur_hi, desc_tpl, root, corrective = template
        machine_id = _rand.choice(PRODUCTION_MACHINES)
        duration = round(_rand.uniform(dur_lo, dur_hi), 1)
        days_ago = _rand.randint(0, 6)
        hour = _rand.randint(6, 20)
        minute = _rand.randint(0, 59)
        start = datetime(today.year, today.month, today.day, hour, minute) - timedelta(days=days_ago)
        end = start + timedelta(minutes=duration)

        evt = DowntimeEvent(
            machine_id=machine_id,
            job_id=_rand.choice(job_ids) if job_ids and _rand.random() < 0.4 else None,
            start_time=start,
            end_time=end,
            duration_minutes=duration,
            reason=reason,
            planned=planned,
            description=desc_tpl.format(machine=machine_id, product=_rand.choice(products)),
            root_cause=root,
            corrective_action=corrective,
            reported_by=_rand.choice(reporters),
            created_by='seeder',
        )
        session.add(evt)
        downtime_records.append(evt)

    session.flush()
    downtime_count = len(downtime_records)

    # ══════════════════════════════════════════════════════════════════════
    # 2. PRODUCTION COUNTS  (1 per machine per day, past 7 days)
    # ══════════════════════════════════════════════════════════════════════
    prod_count_records = []

    for mid, profile in MACHINE_PROFILES.items():
        for days_ago in range(7):
            d = today - timedelta(days=days_ago)
            total = _rand.randint(profile['parts_lo'], profile['parts_hi'])
            quality_rate = _rand.uniform(profile['quality_lo'], profile['quality_hi'])
            good = int(total * quality_rate)
            reject = _rand.randint(0, total - good)
            rework = total - good - reject
            cycle_s = profile['cycle_s'] + _rand.randint(-20, 20)

            shift_start = datetime(d.year, d.month, d.day, 6, 0)
            run_minutes = round((total * cycle_s) / 60, 1)
            shift_end = shift_start + timedelta(minutes=run_minutes + 30)

            pc = ProductionCount(
                machine_id=mid,
                job_id=_rand.choice(job_ids) if job_ids and _rand.random() < 0.3 else None,
                shift_date=d,
                shift='A',
                total_count=total,
                good_count=good,
                reject_count=reject,
                rework_count=rework,
                start_time=shift_start,
                end_time=shift_end,
                run_time_minutes=run_minutes,
                ideal_cycle_time_seconds=float(cycle_s),
                created_by='seeder',
            )
            session.add(pc)
            prod_count_records.append(pc)

    session.flush()
    prod_count = len(prod_count_records)

    # ══════════════════════════════════════════════════════════════════════
    # 3. OEE RECORDS  (1 per machine per day, past 7 days)
    # ══════════════════════════════════════════════════════════════════════
    oee_records = []
    pc_index = {(pc.machine_id, pc.shift_date): pc for pc in prod_count_records}

    for mid, profile in MACHINE_PROFILES.items():
        scheduled_base = 480.0 if profile['shifts'] == 1 else 960.0

        for days_ago in range(7):
            d = today - timedelta(days=days_ago)
            planned_dt = round(_rand.uniform(30, 60), 1)
            unplanned_dt = round(_rand.uniform(0, 60) * _rand.choice([0, 0.3, 0.5, 0.7, 1.0]), 1)
            changeover_t = round(_rand.uniform(0, 30), 1)
            operating = scheduled_base - planned_dt - unplanned_dt

            pc_ref = pc_index.get((mid, d))
            total_c = pc_ref.total_count if pc_ref else _rand.randint(profile['parts_lo'], profile['parts_hi'])
            good_c = pc_ref.good_count if pc_ref else int(total_c * _rand.uniform(profile['quality_lo'], profile['quality_hi']))
            cycle_t = pc_ref.ideal_cycle_time_seconds if pc_ref else float(profile['cycle_s'])

            net_op = operating - changeover_t

            rec = OEERecord(
                machine_id=mid,
                record_date=d,
                shift='A',
                scheduled_time=scheduled_base,
                operating_time=round(operating, 1),
                net_operating_time=round(max(net_op, 0), 1),
                planned_downtime=planned_dt,
                unplanned_downtime=unplanned_dt,
                changeover_time=changeover_t,
                total_count=total_c,
                good_count=good_c,
                ideal_cycle_time=cycle_t,
                mtbf_minutes=round(_rand.uniform(120, 400), 1),
                mttr_minutes=round(_rand.uniform(15, 60), 1),
                created_by='seeder',
            )
            rec.calculate_oee()
            session.add(rec)
            oee_records.append(rec)

    session.flush()
    oee_count = len(oee_records)

    # ══════════════════════════════════════════════════════════════════════
    # 4. WORKERS  (8 factory workers)
    # ══════════════════════════════════════════════════════════════════════
    WORKERS_DATA = [
        {'employee_id': 'EMP001', 'first': 'Alex', 'last': 'Chen',
         'email': 'alex.chen@legofactory.local', 'phone': '555-0101',
         'dept': 'CNC Operations', 'role': 'CNC Operator',
         'shift': 'Shift A', 'rate': 28.00, 'supervisor': None,
         'certs': [{'name': 'CNC Mill Operation', 'issued': '2024-03-15', 'expires': '2026-03-15'},
                   {'name': 'GD&T Fundamentals', 'issued': '2024-06-01', 'expires': '2027-06-01'}]},
        {'employee_id': 'EMP002', 'first': 'Maria', 'last': 'Santos',
         'email': 'maria.santos@legofactory.local', 'phone': '555-0102',
         'dept': 'Additive Manufacturing', 'role': 'FDM Technician',
         'shift': 'Shift A', 'rate': 26.00, 'supervisor': 'EMP008',
         'certs': [{'name': 'FDM Printer Operation', 'issued': '2024-01-10', 'expires': '2026-01-10'},
                   {'name': 'Material Handling - PLA/ABS', 'issued': '2024-04-20', 'expires': '2026-04-20'}]},
        {'employee_id': 'EMP003', 'first': 'James', 'last': 'Wilson',
         'email': 'james.wilson@legofactory.local', 'phone': '555-0103',
         'dept': 'Additive Manufacturing', 'role': 'SLA / Robot Operator',
         'shift': 'Shift A', 'rate': 27.00, 'supervisor': 'EMP008',
         'certs': [{'name': 'SLA Printer Operation', 'issued': '2024-02-28', 'expires': '2026-02-28'},
                   {'name': 'Robot Arm Safety', 'issued': '2024-05-15', 'expires': '2026-05-15'},
                   {'name': 'Resin Handling', 'issued': '2024-02-28', 'expires': '2026-02-28'}]},
        {'employee_id': 'EMP004', 'first': 'Sarah', 'last': 'Kim',
         'email': 'sarah.kim@legofactory.local', 'phone': '555-0104',
         'dept': 'Quality', 'role': 'Quality Inspector',
         'shift': 'Shift A', 'rate': 29.00, 'supervisor': 'EMP008',
         'certs': [{'name': 'CMM Operation', 'issued': '2024-01-05', 'expires': '2026-01-05'},
                   {'name': 'SPC / Control Charts', 'issued': '2024-07-12', 'expires': '2027-07-12'},
                   {'name': 'ISO 9001 Internal Auditor', 'issued': '2025-01-20', 'expires': '2028-01-20'}]},
        {'employee_id': 'EMP005', 'first': 'David', 'last': 'Nguyen',
         'email': 'david.nguyen@legofactory.local', 'phone': '555-0105',
         'dept': 'CNC Operations', 'role': 'CNC Operator',
         'shift': 'Shift B', 'rate': 28.00, 'supervisor': 'EMP008',
         'certs': [{'name': 'CNC Mill Operation', 'issued': '2024-08-01', 'expires': '2026-08-01'},
                   {'name': 'CNC Lathe Operation', 'issued': '2024-09-15', 'expires': '2026-09-15'}]},
        {'employee_id': 'EMP006', 'first': 'Lisa', 'last': 'Park',
         'email': 'lisa.park@legofactory.local', 'phone': '555-0106',
         'dept': 'Additive Manufacturing', 'role': 'FDM Technician',
         'shift': 'Shift B', 'rate': 26.00, 'supervisor': 'EMP008',
         'certs': [{'name': 'FDM Printer Operation', 'issued': '2024-05-10', 'expires': '2026-05-10'},
                   {'name': 'Filament QC', 'issued': '2024-11-01', 'expires': '2026-11-01'}]},
        {'employee_id': 'EMP007', 'first': 'Michael', 'last': 'Brown',
         'email': 'michael.brown@legofactory.local', 'phone': '555-0107',
         'dept': 'Maintenance', 'role': 'Maintenance Technician',
         'shift': 'Shift B', 'rate': 30.00, 'supervisor': 'EMP008',
         'certs': [{'name': 'Electrical Safety', 'issued': '2024-03-01', 'expires': '2026-03-01'},
                   {'name': 'Lockout/Tagout', 'issued': '2024-03-01', 'expires': '2026-03-01'},
                   {'name': 'PLC Troubleshooting', 'issued': '2024-06-20', 'expires': '2027-06-20'},
                   {'name': 'Hydraulic Systems', 'issued': '2024-09-10', 'expires': '2026-09-10'}]},
        {'employee_id': 'EMP008', 'first': 'Jennifer', 'last': 'Lee',
         'email': 'jennifer.lee@legofactory.local', 'phone': '555-0108',
         'dept': 'Production', 'role': 'Team Lead',
         'shift': 'Shift A', 'rate': 32.00, 'supervisor': None,
         'certs': [{'name': 'Lean Manufacturing', 'issued': '2023-11-15', 'expires': '2026-11-15'},
                   {'name': 'Six Sigma Green Belt', 'issued': '2024-02-01', 'expires': '2027-02-01'},
                   {'name': 'First Aid / CPR', 'issued': '2025-01-10', 'expires': '2027-01-10'}]},
    ]

    worker_objs = {}
    for w in WORKERS_DATA:
        worker = Worker(
            employee_id=w['employee_id'],
            first_name=w['first'],
            last_name=w['last'],
            email=w['email'],
            phone=w['phone'],
            department=w['dept'],
            role=w['role'],
            supervisor_id=w['supervisor'],
            status=WorkerStatus.ACTIVE,
            hire_date=today - timedelta(days=_rand.randint(365, 1200)),
            default_shift=w['shift'],
            hourly_rate=w['rate'],
            certifications=w['certs'],
            is_deleted=False,
            created_by='seeder',
        )
        session.add(worker)
        worker_objs[w['employee_id']] = worker

    session.flush()
    worker_count = len(worker_objs)

    # ══════════════════════════════════════════════════════════════════════
    # 5. TIME ENTRIES  (~40 records over past 7 days)
    # ══════════════════════════════════════════════════════════════════════
    SHIFT_A_START, SHIFT_A_END = 6, 14
    SHIFT_B_START, SHIFT_B_END = 14, 22
    ENTRY_TYPES = ['direct', 'direct', 'direct', 'setup', 'indirect']
    time_entries = []

    def _te_note(entry_type):
        notes_map = {
            'direct': ["Production run on assigned machines", "Standard production shift",
                       "Batch processing - normal operations", "Running priority work orders"],
            'setup':  ["Machine setup and first-article inspection", "Fixture changeover and alignment",
                       "New job setup, tooling verification"],
            'indirect': ["5S area cleanup and tool organization", "Team meeting and shift briefing",
                         "Training on updated SOP", "Inventory count assistance"],
        }
        return _rand.choice(notes_map.get(entry_type, notes_map['direct']))

    for days_ago in range(7):
        d = today - timedelta(days=days_ago)
        is_past = days_ago > 0

        for emp_id, worker in worker_objs.items():
            if _rand.random() > 0.70:
                continue

            if worker.default_shift == 'Shift A':
                ci_hour, co_hour, co_min = SHIFT_A_START, SHIFT_A_END, 30
            else:
                ci_hour, co_hour, co_min = SHIFT_B_START, SHIFT_B_END, 30

            jitter = _rand.randint(-10, 10)
            clock_in = datetime(d.year, d.month, d.day, ci_hour, max(0, min(59, 0 + jitter)))
            clock_out = datetime(d.year, d.month, d.day, co_hour, co_min) + timedelta(minutes=_rand.randint(-5, 15))

            total_hours = (clock_out - clock_in).total_seconds() / 3600
            break_min = 30
            worked = total_hours - (break_min / 60)
            regular = min(worked, 8.0)
            overtime = max(0, worked - 8.0)

            entry_type = _rand.choice(ENTRY_TYPES)
            linked_job = _rand.choice(job_ids) if job_ids and entry_type == 'direct' and _rand.random() < 0.5 else None

            te = TimeEntry(
                worker_id=worker.id,
                job_id=linked_job,
                clock_in=clock_in,
                clock_out=clock_out if is_past else None,
                break_minutes=break_min,
                regular_hours=round(regular, 2),
                overtime_hours=round(overtime, 2),
                entry_type=entry_type,
                notes=_te_note(entry_type),
                approved=is_past,
                approved_by='EMP008' if is_past else None,
                approved_at=datetime(d.year, d.month, d.day, 23, 0) if is_past else None,
                created_by='seeder',
            )
            session.add(te)
            time_entries.append(te)

    session.flush()
    time_entry_count = len(time_entries)

    # ══════════════════════════════════════════════════════════════════════
    # 6. MACHINE EVENTS  (~50 records over past 7 days)
    # ══════════════════════════════════════════════════════════════════════
    def _running_details(mid):
        if 'bambu' in mid or 'creality' in mid:
            return {'action': 'print_started', 'nozzle_temp_c': _rand.randint(195, 220),
                    'bed_temp_c': _rand.randint(55, 65), 'layer_height_mm': _rand.choice([0.16, 0.20, 0.28]),
                    'estimated_min': _rand.randint(60, 180)}
        elif 'formlabs' in mid:
            return {'action': 'print_started', 'resin_type': _rand.choice(['Standard Grey', 'Tough 2000', 'Durable']),
                    'layer_height_um': _rand.choice([25, 50, 100]), 'estimated_min': _rand.randint(120, 360)}
        elif 'bantam' in mid or 'coastrunner' in mid or 'labfab' in mid:
            return {'action': 'program_started', 'spindle_rpm': _rand.randint(8000, 24000),
                    'feed_rate_mmpm': _rand.randint(500, 2000), 'tool_number': _rand.randint(1, 6)}
        elif 'rownd' in mid:
            return {'action': 'program_started', 'spindle_rpm': _rand.randint(1000, 4000),
                    'feed_rate_mmpm': _rand.randint(200, 800), 'material': _rand.choice(['ABS rod', 'Nylon rod'])}
        elif 'laser' in mid:
            return {'action': 'cut_started', 'power_pct': _rand.randint(40, 100),
                    'speed_mmps': _rand.randint(10, 80), 'material': _rand.choice(['3mm acrylic', '1.5mm ABS'])}
        else:
            return {'action': 'cycle_started', 'program': _rand.choice(['inspect_2x4', 'pack_box_12']),
                    'speed_pct': _rand.randint(60, 100)}

    def _alarm_details(mid):
        if 'bambu' in mid or 'creality' in mid:
            alarm = _rand.choice([
                {'code': 'THERMAL_RUNAWAY', 'message': 'Hotend temperature exceeded safety limit', 'severity': 'critical'},
                {'code': 'FILAMENT_OUT', 'message': 'Filament runout sensor triggered', 'severity': 'warning'}])
        elif 'formlabs' in mid:
            alarm = _rand.choice([
                {'code': 'RESIN_LOW', 'message': 'Resin level below minimum', 'severity': 'warning'},
                {'code': 'LASER_FAULT', 'message': 'Galvo mirror calibration drift', 'severity': 'critical'}])
        elif any(x in mid for x in ['bantam', 'coastrunner', 'labfab', 'rownd']):
            alarm = _rand.choice([
                {'code': 'SPINDLE_OVERLOAD', 'message': 'Spindle load exceeded 95%', 'severity': 'critical'},
                {'code': 'TOOL_BREAKAGE', 'message': 'Tool breakage detected', 'severity': 'critical'}])
        elif 'laser' in mid:
            alarm = _rand.choice([
                {'code': 'ENCLOSURE_OPEN', 'message': 'Safety interlock triggered', 'severity': 'critical'},
                {'code': 'EXHAUST_FAIL', 'message': 'Fume extraction below threshold', 'severity': 'warning'}])
        else:
            alarm = _rand.choice([
                {'code': 'COLLISION_DETECT', 'message': 'Unexpected force on end effector', 'severity': 'critical'},
                {'code': 'SERVO_FAULT', 'message': 'Joint 3 servo timeout', 'severity': 'warning'}])
        alarm['action'] = 'alarm_raised'
        return alarm

    TRANSITION_PATTERNS = [
        ('startup',     'disconnected', 'idle',    lambda m: {'action': 'power_on', 'firmware': '2.1.4'}),
        ('connect',     'disconnected', 'idle',    lambda m: {'action': 'network_connect', 'ip': f'10.0.1.{_rand.randint(10,99)}'}),
        ('start',       'idle',         'running', _running_details),
        ('stop',        'running',      'idle',    lambda m: {'action': 'job_complete', 'parts_produced': _rand.randint(5, 30)}),
        ('pause',       'running',      'paused',  lambda m: {'action': 'operator_pause', 'reason': 'material check'}),
        ('resume',      'paused',       'running', lambda m: {'action': 'operator_resume'}),
        ('alarm',       'running',      'alarm',   _alarm_details),
        ('alarm_clear', 'alarm',        'idle',    lambda m: {'action': 'alarm_acknowledged', 'cleared_by': _rand.choice(reporters)}),
        ('disconnect',  'idle',         'disconnected', lambda m: {'action': 'planned_shutdown'}),
        ('maintenance', 'idle',         'maintenance',  lambda m: {'action': 'pm_started', 'wo': f'WO-PM-{_rand.randint(100,999)}'}),
        ('maintenance_end', 'maintenance', 'idle', lambda m: {'action': 'pm_completed', 'duration_min': _rand.randint(20, 60)}),
    ]

    machine_events = []
    operators = ['Alex Chen', 'Maria Santos', 'James Wilson', 'David Nguyen', 'Lisa Park', 'Michael Brown']

    for mid in ALL_MACHINES:
        machine_obj = machines_by_str.get(mid)
        if not machine_obj:
            continue

        n_events = _rand.randint(4, 6)
        state = 'disconnected'

        for i in range(n_events):
            days_ago = _rand.uniform(0, 6.5)
            evt_time = now - timedelta(days=days_ago)

            valid = [t for t in TRANSITION_PATTERNS if t[1] == state]
            if not valid:
                state = 'idle'
                valid = [t for t in TRANSITION_PATTERNS if t[1] == state]
            if not valid:
                continue

            transition = _rand.choice(valid)
            event_type, prev_state, new_state, detail_fn = transition

            me = MachineEvent(
                machine_id=machine_obj.id,
                event_type=event_type,
                previous_state=prev_state,
                new_state=new_state,
                details=detail_fn(mid),
                operator=_rand.choice(operators),
            )
            session.add(me)
            machine_events.append(me)
            state = new_state

    session.flush()
    event_count = len(machine_events)

    session.commit()
    print(f"  + {downtime_count} downtime events")
    print(f"  + {prod_count} production count records")
    print(f"  + {oee_count} OEE records")
    print(f"  + {worker_count} workers")
    print(f"  + {time_entry_count} time entries")
    print(f"  + {event_count} machine events")


def seed_mes_operational_data(session):
    """Seed MES operational data: rework orders, scrap events, shift handovers,
    kanban cards, WIP snapshots, and cycle time records."""
    import random as _rand
    from datetime import datetime, date, timedelta

    from models.mes.operations import (
        ReworkOrder, ReworkStatus, ScrapEvent,
        ShiftHandover, HandoverStatus,
        KanbanCardModel, WIPSnapshot, CycleTimeRecord,
    )
    from models.mes.work_orders import Job, JobStatus, WorkOrder

    _rand.seed(99)
    now = datetime.utcnow()
    today = date.today()

    print("\n[MES-Ops] Seeding rework, scrap, handovers, kanban, WIP snapshots, cycle times...")

    # ── Cleanup ─────────────────────────────────────────────────────────
    for model in [ScrapEvent, ReworkOrder, ShiftHandover,
                  KanbanCardModel, WIPSnapshot, CycleTimeRecord]:
        session.query(model).delete(synchronize_session='fetch')
    session.commit()

    # ── Rework Orders (8) ───────────────────────────────────────────────
    REWORK_REASONS = [
        'Dimensional out of tolerance', 'Surface finish defect',
        'Layer adhesion failure', 'Color mismatch',
        'Warping beyond spec', 'Post-cure incomplete',
        'Stud fitment loose', 'Thread damage',
    ]
    completed_wos = session.query(WorkOrder).filter(
        WorkOrder.work_order_id.like('WO-2026-C%')
    ).all()
    wo_ids = [wo.work_order_id for wo in completed_wos]

    rework_count = 0
    for i in range(8):
        rw = ReworkOrder(
            rework_id=f'RW-{i + 1:04d}',
            original_wo_id=_rand.choice(wo_ids) if wo_ids else f'WO-2026-C00{i + 1}',
            ncr_id=f'NCR-2026-{_rand.randint(1, 5):03d}' if _rand.random() > 0.3 else None,
            reason=_rand.choice(REWORK_REASONS),
            rework_operations=['re-print', 'inspect'] if i % 3 == 0 else ['re-machine', 'deburr', 'inspect'],
            quantity=_rand.randint(5, 50),
            cost=round(_rand.uniform(15, 200), 2),
            status=_rand.choice([ReworkStatus.OPEN, ReworkStatus.IN_PROGRESS,
                                 ReworkStatus.COMPLETED, ReworkStatus.COMPLETED]),
            completed_at=now - timedelta(days=_rand.randint(1, 14))
            if i < 5 else None,
        )
        session.add(rw)
        rework_count += 1

    # ── Scrap Events (15) ──────────────────────────────────────────────
    SCRAP_REASONS = [
        'dimensional_fail', 'surface_defect', 'layer_separation',
        'warping', 'color_out_of_spec', 'material_contamination',
        'tooling_damage', 'operator_error',
    ]
    MACHINES = [
        'bambu-ps1', 'creality-cr30', 'formlabs-3',
        'bantam-explorer', 'coastrunner-cr1', 'rownd-lathe',
    ]
    jobs = session.query(Job).filter(
        Job.status.in_([JobStatus.COMPLETED, JobStatus.RUNNING])
    ).limit(30).all()

    scrap_count = 0
    for i in range(15):
        unit_cost = round(_rand.uniform(0.05, 2.50), 2)
        qty = _rand.randint(1, 20)
        se = ScrapEvent(
            job_id=_rand.choice(jobs).id if jobs else None,
            machine_id=_rand.choice(MACHINES),
            quantity=qty,
            reason=_rand.choice(SCRAP_REASONS),
            unit_cost=unit_cost,
            total_cost=round(qty * unit_cost, 2),
            dispositioned_by=_rand.choice(['EMP001', 'EMP002', 'EMP003', 'EMP004']),
        )
        session.add(se)
        scrap_count += 1

    # ── Shift Handovers (14 — last 7 days × 2 shifts) ──────────────────
    OPERATORS = ['Alice Chen', 'Bob Martinez', 'Carol Kim', 'Dan Osei',
                 'Erin Tanaka', 'Frank Weber', 'Grace Li', 'Hiro Sato']
    handover_count = 0
    for day_offset in range(7):
        d = today - timedelta(days=day_offset)
        for shift_idx, shift_type in enumerate(['day', 'night']):
            outgoing = OPERATORS[(day_offset * 2 + shift_idx) % len(OPERATORS)]
            incoming = OPERATORS[(day_offset * 2 + shift_idx + 1) % len(OPERATORS)]
            items = [
                {'category': 'SAFETY', 'description': 'Safety walkthrough completed',
                 'status': 'OK', 'notes': ''},
                {'category': 'PRODUCTION', 'description': 'Production targets reviewed',
                 'status': 'OK', 'notes': f'{_rand.randint(80, 100)}% of shift target met'},
                {'category': 'QUALITY', 'description': 'Quality issues reviewed',
                 'status': _rand.choice(['OK', 'OK', 'ATTENTION']),
                 'notes': '' if day_offset > 2 else 'Minor surface finish issue on FDM line'},
            ]
            if _rand.random() > 0.7:
                items.append({
                    'category': 'MAINTENANCE',
                    'description': f'Machine {_rand.choice(MACHINES)} needs attention',
                    'status': 'ATTENTION',
                    'notes': _rand.choice(['Belt tension low', 'Nozzle wear detected',
                                           'Coolant level low', 'Vibration alarm triggered']),
                })
            ho = ShiftHandover(
                handover_id=f'HO-{handover_count + 1:04d}',
                shift_date=d,
                shift_type=shift_type,
                outgoing_worker=outgoing,
                incoming_worker=incoming,
                status=HandoverStatus.COMPLETED,
                items=items,
                completed_at=datetime.combine(d, datetime.min.time())
                + timedelta(hours=6 if shift_type == 'day' else 18),
            )
            session.add(ho)
            handover_count += 1

    # ── Kanban Cards (6 — one per product/work-center combo) ────────────
    KANBAN_CONFIGS = [
        ('brick_2x4_red', 'fdm-line', 100, 30),
        ('brick_2x4_blue', 'fdm-line', 100, 30),
        ('gear_8t_black', 'sla-line', 50, 15),
        ('axle_4l_grey', 'cnc-line', 80, 25),
        ('baseplate_16x16_green', 'cnc-line', 30, 10),
        ('brick_2x2_red', 'fdm-line', 120, 40),
    ]
    kanban_count = 0
    for product_id, work_center, target, reorder in KANBAN_CONFIGS:
        qty = _rand.randint(reorder - 5, target)
        status = 'full' if qty >= target else ('empty' if qty <= reorder else 'in_transit')
        signal = 'none' if qty >= target else ('replenish' if qty <= reorder else 'none')
        card = KanbanCardModel(
            card_id=f'KB-{kanban_count + 1:04d}',
            product_id=product_id,
            work_center_id=work_center,
            quantity=qty,
            target_qty=target,
            reorder_point=reorder,
            status=status,
            signal=signal,
            last_replenish_at=now - timedelta(hours=_rand.randint(1, 48)),
        )
        session.add(card)
        kanban_count += 1

    # ── WIP Snapshots (48 — last 7 days, every ~3.5h) ──────────────────
    wip_count = 0
    for i in range(48):
        ts = now - timedelta(hours=i * 3.5)
        total = _rand.randint(8, 25)
        snap = WIPSnapshot(
            total_wip=total,
            by_machine={m: _rand.randint(0, 4) for m in MACHINES[:4]},
        )
        snap.created_at = ts
        session.add(snap)
        wip_count += 1

    # ── Cycle Time Records (120 — recent cycle times across work centers) ─
    WORK_CENTERS = ['fdm-line', 'sla-line', 'cnc-line', 'lathe-cell', 'laser-cell']
    TAKT_TARGETS = {
        'fdm-line': 180, 'sla-line': 420, 'cnc-line': 240,
        'lathe-cell': 300, 'laser-cell': 150,
    }
    cycle_count = 0
    for wc_id in WORK_CENTERS:
        takt = TAKT_TARGETS[wc_id]
        for i in range(24):
            ts = now - timedelta(minutes=i * 30 + _rand.randint(0, 10))
            # Realistic cycle times: mostly near takt, occasional outliers
            if _rand.random() > 0.85:
                cycle = takt * _rand.uniform(1.1, 1.35)  # over takt
            else:
                cycle = takt * _rand.uniform(0.85, 1.05)  # near/under takt
            deviation = cycle - takt
            rec = CycleTimeRecord(
                work_center_id=wc_id,
                cycle_seconds=round(cycle, 1),
                takt_target_seconds=takt,
                deviation_seconds=round(deviation, 1),
                on_takt=cycle <= takt * 1.05,
                job_id=str(_rand.choice(jobs).id) if jobs else None,
                operator_id=_rand.choice(['EMP001', 'EMP002', 'EMP003', 'EMP004']),
            )
            rec.created_at = ts
            session.add(rec)
            cycle_count += 1

    session.commit()
    print(f"  + {rework_count} rework orders")
    print(f"  + {scrap_count} scrap events")
    print(f"  + {handover_count} shift handovers")
    print(f"  + {kanban_count} kanban cards")
    print(f"  + {wip_count} WIP snapshots")
    print(f"  + {cycle_count} cycle time records")


def seed_phase5_data(session):
    """
    Seed data for Phase 5 services: setup events, setup procedures, benchmarks,
    recipe runs, recipe audit entries, and first article inspections.
    """
    import random
    from datetime import datetime, timedelta, date
    from models.mes.setup import SetupEvent, SetupProcedure, SetupBenchmark, SMEDProject
    from models.mes.recipe_run import RecipeRun, RecipeAuditEntry
    from models.qms.first_article import FirstArticleInspection

    print("\n[Phase5] Seeding setup events, recipe runs, FAIs...")

    # Clear existing
    for model in [SMEDProject, SetupBenchmark, SetupProcedure, SetupEvent,
                   RecipeRun, RecipeAuditEntry, FirstArticleInspection]:
        session.query(model).delete(synchronize_session='fetch')
    session.commit()

    machines = [
        'prusa-mk4-1', 'prusa-mk4-2', 'bambu-x1c-1',
        'elegoo-mars-1', 'bantam-explorer', 'coastrunner-cr1',
    ]
    products = [
        'brick_2x4_red', 'brick_2x4_blue', 'gear_16t_yellow',
        'axle_3L_black', 'baseplate_16x16_green', 'minifig_head_yellow',
        'wheel_24mm_black', 'technic_beam_5_grey', 'slope_2x1_white',
    ]
    operators = ['OP-001', 'OP-002', 'OP-003', 'OP-004', 'OP-005', 'OP-006', 'OP-007', 'OP-008']

    # ── Setup Events (40 events over past 3 months) ──
    setup_count = 0
    now = datetime.utcnow()
    for i in range(40):
        machine = random.choice(machines)
        from_prod = random.choice(products)
        to_prod = random.choice([p for p in products if p != from_prod])
        duration = round(random.uniform(5, 45), 1)
        days_ago = random.randint(0, 90)
        completed = now - timedelta(days=days_ago, hours=random.randint(0, 23))

        event = SetupEvent(
            setup_id=f"SETUP-{i+1:04d}",
            machine_id=machine,
            job_id=f"JOB-SETUP-{i+1:03d}",
            from_product=from_prod,
            to_product=to_prod,
            operator_id=random.choice(operators),
            setup_type=random.choice(['internal', 'internal', 'internal', 'external']),
            duration_minutes=duration,
            total_duration_minutes=round(duration + random.uniform(0, 5), 1),
            pause_minutes=round(random.uniform(0, 5), 1),
            step_times={'preparation': round(duration * 0.2, 1), 'removal': round(duration * 0.15, 1),
                        'installation': round(duration * 0.35, 1), 'adjustment': round(duration * 0.2, 1),
                        'trial_run': round(duration * 0.1, 1)},
            completed_at=completed,
        )
        session.add(event)
        setup_count += 1
    session.flush()

    # ── Setup Procedures (6 standard procedures) ──
    proc_count = 0
    procedure_defs = [
        ('FDM Filament Change', 'prusa-mk4-1', [
            {'description': 'Unload current filament', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 2},
            {'description': 'Clean extruder', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 3},
            {'description': 'Load new filament', 'setup_type': 'internal', 'phase': 'installation', 'estimated_minutes': 2},
            {'description': 'Prime and purge', 'setup_type': 'internal', 'phase': 'adjustment', 'estimated_minutes': 1},
            {'description': 'First layer test', 'setup_type': 'internal', 'phase': 'trial_run', 'estimated_minutes': 3},
        ]),
        ('SLA Resin Change', 'elegoo-mars-1', [
            {'description': 'Drain current resin', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 5},
            {'description': 'Clean vat and FEP', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 10},
            {'description': 'Pour new resin', 'setup_type': 'internal', 'phase': 'installation', 'estimated_minutes': 3},
            {'description': 'Level check', 'setup_type': 'internal', 'phase': 'adjustment', 'estimated_minutes': 2},
            {'description': 'Exposure calibration print', 'setup_type': 'internal', 'phase': 'trial_run', 'estimated_minutes': 5},
        ]),
        ('CNC Tool Change', 'bantam-explorer', [
            {'description': 'Prepare new tooling (external)', 'setup_type': 'external', 'phase': 'preparation', 'estimated_minutes': 5},
            {'description': 'Remove current tool', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 2},
            {'description': 'Install new tool', 'setup_type': 'internal', 'phase': 'installation', 'estimated_minutes': 3},
            {'description': 'Set tool offset', 'setup_type': 'internal', 'phase': 'adjustment', 'estimated_minutes': 5},
            {'description': 'Air cut verification', 'setup_type': 'internal', 'phase': 'trial_run', 'estimated_minutes': 3},
        ]),
        ('CNC Material Change', 'coastrunner-cr1', [
            {'description': 'Remove finished part', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 2},
            {'description': 'Clean work area', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 3},
            {'description': 'Mount new stock', 'setup_type': 'internal', 'phase': 'installation', 'estimated_minutes': 5},
            {'description': 'Probe workpiece zero', 'setup_type': 'internal', 'phase': 'adjustment', 'estimated_minutes': 8},
            {'description': 'Test cut', 'setup_type': 'internal', 'phase': 'trial_run', 'estimated_minutes': 4},
        ]),
        ('Bambu Plate Swap', 'bambu-x1c-1', [
            {'description': 'Cool down build plate', 'setup_type': 'internal', 'phase': 'preparation', 'estimated_minutes': 3},
            {'description': 'Remove plate and parts', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 1},
            {'description': 'Install clean plate', 'setup_type': 'internal', 'phase': 'installation', 'estimated_minutes': 1},
            {'description': 'Calibration', 'setup_type': 'internal', 'phase': 'adjustment', 'estimated_minutes': 2},
        ]),
        ('FDM Color Change', 'prusa-mk4-2', [
            {'description': 'Heat nozzle to purge temp', 'setup_type': 'internal', 'phase': 'preparation', 'estimated_minutes': 2},
            {'description': 'Unload filament', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 1},
            {'description': 'Cold pull (clean nozzle)', 'setup_type': 'internal', 'phase': 'removal', 'estimated_minutes': 3},
            {'description': 'Load new color', 'setup_type': 'internal', 'phase': 'installation', 'estimated_minutes': 2},
            {'description': 'Purge until clean', 'setup_type': 'internal', 'phase': 'adjustment', 'estimated_minutes': 2},
        ]),
    ]

    for idx, (name, machine, steps) in enumerate(procedure_defs):
        total_est = sum(s['estimated_minutes'] for s in steps)
        proc = SetupProcedure(
            procedure_id=f"PROC-{idx+1:04d}",
            name=name,
            machine_id=machine,
            steps=steps,
            total_estimated_minutes=total_est,
            version=1,
        )
        session.add(proc)
        proc_count += 1
    session.flush()

    # ── Setup Benchmarks (computed from events) ──
    bench_count = 0
    from collections import defaultdict
    import statistics as stats
    event_data = defaultdict(list)
    for evt in session.query(SetupEvent).all():
        key = (evt.machine_id, f"{evt.from_product or '?'} -> {evt.to_product or '?'}")
        event_data[key].append(evt.duration_minutes)

    for (machine, transition), durations in event_data.items():
        bench = SetupBenchmark(
            machine_id=machine,
            product_transition=transition,
            best_time_minutes=round(min(durations), 1),
            avg_time_minutes=round(stats.mean(durations), 1),
            worst_time_minutes=round(max(durations), 1),
            std_dev_minutes=round(stats.stdev(durations), 1) if len(durations) > 1 else 0,
            sample_count=len(durations),
        )
        session.add(bench)
        bench_count += 1
    session.flush()

    # ── SMED Projects (2 active) ──
    smed_count = 0
    for i, (machine, transition, baseline, target) in enumerate([
        ('bantam-explorer', 'gear_16t_yellow -> axle_3L_black', 28.5, 15.0),
        ('prusa-mk4-1', 'brick_2x4_red -> brick_2x4_blue', 12.0, 5.0),
    ]):
        proj = SMEDProject(
            project_id=f"SMED-{i+1:04d}",
            machine_id=machine,
            product_transition=transition,
            baseline_minutes=baseline,
            current_minutes=round(baseline * 0.75, 1),
            target_minutes=target,
            improvement_pct=25.0,
            internal_converted_to_external=['Prepare tooling offline', 'Pre-stage materials'],
            streamlined_steps=['Combined removal+install step'],
            status='active',
        )
        session.add(proj)
        smed_count += 1
    session.flush()

    # ── Recipe Runs (20 lot-recipe linkages) ──
    run_count = 0
    recipe_ids = ['RCP-FDM-001', 'RCP-FDM-002', 'RCP-SLA-001', 'RCP-CNC-001', 'RCP-CNC-002']
    for i in range(20):
        recipe_id = random.choice(recipe_ids)
        version = random.randint(1, 3)
        good_qty = random.randint(40, 100)
        reject_qty = random.randint(0, 5)

        run = RecipeRun(
            lot_id=f"LOT-{i+1:04d}",
            recipe_id=recipe_id,
            version_number=version,
            version_id=f"{recipe_id}-V{version:03d}",
            job_id=f"JOB-RUN-{i+1:03d}",
            quantity=good_qty + reject_qty,
            parameters_snapshot={
                'temperature': random.randint(190, 230),
                'speed': random.randint(40, 80),
                'layer_height': random.choice([0.1, 0.15, 0.2]),
            },
            good_quantity=good_qty,
            reject_quantity=reject_qty,
            cycle_time=round(random.uniform(30, 120), 1),
            quality_score=round(random.uniform(85, 99), 1),
        )
        session.add(run)
        run_count += 1
    session.flush()

    # ── Recipe Audit Entries (30 entries) ──
    audit_count = 0
    actions = ['created', 'version_created', 'submitted_for_approval', 'approved',
               'activated', 'locked', 'unlocked', 'lot_linked']
    actors = ['process_engineer', 'quality_manager', 'system', 'production_lead']
    for i in range(30):
        recipe_id = random.choice(recipe_ids)
        entry = RecipeAuditEntry(
            recipe_id=recipe_id,
            version_number=random.randint(1, 3),
            action=random.choice(actions),
            actor=random.choice(actors),
            details={'note': f'Audit event {i+1}'},
            lot_id=f"LOT-{random.randint(1,20):04d}" if random.random() > 0.5 else None,
            job_id=f"JOB-RUN-{random.randint(1,20):03d}" if random.random() > 0.5 else None,
        )
        session.add(entry)
        audit_count += 1
    session.flush()

    # ── First Article Inspections (6 FAIs at various stages) ──
    fai_count = 0
    fai_defs = [
        ('brick_2x4_red', 'Standard 2x4 Brick Red', 'A', 'approved', 'pass'),
        ('gear_16t_yellow', '16-Tooth Gear Yellow', 'B', 'approved', 'pass'),
        ('axle_3L_black', '3L Technic Axle Black', 'A', 'pending_approval', 'pass'),
        ('minifig_head_yellow', 'Minifig Head Yellow', 'A', 'pending_review', 'deviation'),
        ('baseplate_16x16_green', '16x16 Baseplate Green', 'C', 'in_progress', 'not_inspected'),
        ('wheel_24mm_black', '24mm Wheel Black', 'A', 'draft', 'not_inspected'),
    ]

    for idx, (part_no, part_name, rev, status, overall) in enumerate(fai_defs):
        chars = []
        num_chars = random.randint(8, 15)
        for c in range(num_chars):
            nominal = round(random.uniform(1, 50), 2)
            tol = round(nominal * 0.02, 3)
            measured = round(nominal + random.uniform(-tol * 1.5, tol * 1.5), 3) if status != 'draft' else None

            if measured is not None:
                if abs(measured - nominal) <= tol:
                    result = 'pass'
                elif abs(measured - nominal) <= tol * 2:
                    result = 'deviation' if random.random() > 0.7 else 'fail'
                else:
                    result = 'fail'
            else:
                result = 'not_inspected'

            chars.append({
                'char_id': f"FAI-{idx+1:03d}-{c+1:03d}",
                'char_number': c + 1,
                'description': f"Dimension {c+1}: {'Length' if c % 3 == 0 else 'Width' if c % 3 == 1 else 'Height'}",
                'char_type': 'dimensional',
                'specification': f"{nominal} +/- {tol} mm",
                'nominal': nominal,
                'upper_limit': round(nominal + tol, 3),
                'lower_limit': round(nominal - tol, 3),
                'unit_of_measure': 'mm',
                'is_critical': c < 3,
                'is_safety': False,
                'measured_value': measured,
                'measurement_method': 'CMM' if c < 3 else 'Caliper',
                'measurement_equipment': 'CMM-001' if c < 3 else 'CAL-007',
                'result': result,
                'notes': '',
            })

        fail_ct = len([c for c in chars if c['result'] == 'fail'])
        dev_ct = len([c for c in chars if c['result'] == 'deviation'])

        fai = FirstArticleInspection(
            fai_number=f"FAI-2026-{idx+1:04d}",
            part_number=part_no,
            part_name=part_name,
            revision=rev,
            drawing_number=part_no,
            drawing_revision=rev,
            work_order_id=f"WO-FAI-{idx+1:03d}",
            machine_id=random.choice(machines),
            operator_id=random.choice(operators),
            production_date=now - timedelta(days=random.randint(1, 30)),
            quantity_inspected=1,
            characteristics=chars,
            status=status,
            overall_result=overall if status not in ('draft', 'in_progress') else 'not_inspected',
            deviation_count=dev_ct,
            fail_count=fail_ct,
            inspector_id='QC-001' if status not in ('draft',) else '',
            inspection_date=now - timedelta(days=5) if status not in ('draft', 'in_progress') else None,
            reviewer_id='QE-001' if status in ('pending_approval', 'approved') else '',
            review_date=now - timedelta(days=3) if status in ('pending_approval', 'approved') else None,
            approver_id='QM-001' if status == 'approved' else '',
            approval_date=now - timedelta(days=1) if status == 'approved' else None,
        )
        session.add(fai)
        fai_count += 1

    session.commit()

    print(f"  + {setup_count} setup events")
    print(f"  + {proc_count} setup procedures")
    print(f"  + {bench_count} setup benchmarks")
    print(f"  + {smed_count} SMED projects")
    print(f"  + {run_count} recipe runs")
    print(f"  + {audit_count} recipe audit entries")
    print(f"  + {fai_count} first article inspections")


def seed_erp_financial_data(session):
    """
    Seed ERP financial data: GL Chart of Accounts, inventory transactions
    and journal entries for already-completed work orders (MES→ERP integration).
    """
    from models.erp.financial import (
        GLAccount, AccountType, AccountCategory,
        JournalEntry, JournalLine, JournalStatus,
    )
    from models.erp.inventory import (
        InventoryTransaction, InventoryBalance, TransactionType, Location,
    )
    from models.erp.items import Item
    from models.mes.work_orders import WorkOrder, WorkOrderStatus
    from datetime import date
    from decimal import Decimal

    print("\n[ERP-Financial] Seeding chart of accounts, production transactions, GL entries...")

    # --- Clear previous financial seed data (may already be empty from seed_erp_data) ---
    for model in [JournalLine, JournalEntry, InventoryTransaction, GLAccount]:
        session.query(model).delete(synchronize_session='fetch')
    session.commit()

    # --- Chart of Accounts (manufacturing-oriented) ---
    accounts = [
        # Assets
        ('1000', 'Cash — Operating', AccountType.ASSET, AccountCategory.CASH, 'debit'),
        ('1100', 'Accounts Receivable', AccountType.ASSET, AccountCategory.RECEIVABLE, 'debit'),
        ('1200', 'Raw Materials Inventory', AccountType.ASSET, AccountCategory.INVENTORY, 'debit'),
        ('1300', 'Finished Goods Inventory', AccountType.ASSET, AccountCategory.INVENTORY, 'debit'),
        ('1310', 'Work-in-Process Inventory', AccountType.ASSET, AccountCategory.INVENTORY, 'debit'),
        ('1400', 'Fixed Assets', AccountType.ASSET, AccountCategory.FIXED_ASSET, 'debit'),
        ('1410', 'Accumulated Depreciation', AccountType.ASSET, AccountCategory.FIXED_ASSET, 'credit'),
        # Liabilities
        ('2000', 'Accounts Payable', AccountType.LIABILITY, AccountCategory.PAYABLE, 'credit'),
        ('2100', 'Accrued Liabilities', AccountType.LIABILITY, AccountCategory.ACCRUED, 'credit'),
        ('2200', 'Sales Tax Payable', AccountType.LIABILITY, AccountCategory.ACCRUED, 'credit'),
        # Equity
        ('3000', 'Retained Earnings', AccountType.EQUITY, AccountCategory.EQUITY, 'credit'),
        # Revenue
        ('4000', 'Product Sales Revenue', AccountType.REVENUE, AccountCategory.SALES, 'credit'),
        ('4100', 'Shipping Revenue', AccountType.REVENUE, AccountCategory.OTHER_INCOME, 'credit'),
        # COGS / Manufacturing expense
        ('5000', 'Cost of Goods Sold', AccountType.EXPENSE, AccountCategory.COGS, 'debit'),
        ('5100', 'Direct Labor', AccountType.EXPENSE, AccountCategory.COGS, 'debit'),
        ('5200', 'Manufacturing Overhead', AccountType.EXPENSE, AccountCategory.COGS, 'debit'),
        ('5300', 'Scrap & Rework', AccountType.EXPENSE, AccountCategory.COGS, 'debit'),
        # Operating expenses
        ('6000', 'Salaries & Wages', AccountType.EXPENSE, AccountCategory.OPERATING_EXPENSE, 'debit'),
        ('6100', 'Utilities', AccountType.EXPENSE, AccountCategory.OPERATING_EXPENSE, 'debit'),
        ('6200', 'Maintenance & Repairs', AccountType.EXPENSE, AccountCategory.OPERATING_EXPENSE, 'debit'),
        ('6300', 'Depreciation Expense', AccountType.EXPENSE, AccountCategory.OPERATING_EXPENSE, 'debit'),
    ]

    acct_objs = {}
    for num, name, atype, cat, normal in accounts:
        acct = GLAccount(
            account_number=num,
            name=name,
            account_type=atype,
            account_category=cat,
            normal_balance=normal,
            is_active=True,
            is_posting=True,
            currency='USD',
            created_by='seed',
        )
        session.add(acct)
        acct_objs[num] = acct

    session.flush()
    print(f"  + {len(accounts)} GL accounts")

    # --- Production receipts + GL journals for completed WOs ---
    # Product-to-ERP-item mapping (same as WorkOrderService.PRODUCT_TO_ERP_ITEM)
    product_to_item = {
        'brick_2x4_red': 'brick_2x4_red',
        'brick_2x4_blue': 'brick_2x4_blue',
        'brick_2x4_yellow': 'brick_2x4_yellow',
        'brick_2x4_white': 'brick_2x4_white',
        'brick_2x2_red': 'brick_2x2_red',
        'gear_8t_black': 'gear_8t',
        'gear_24t_grey': 'gear_24t',
        'baseplate_16x16_green': 'baseplate_16x16',
        'axle_4L_grey': 'axle_4l',
    }

    completed_wos = session.query(WorkOrder).filter(
        WorkOrder.status == WorkOrderStatus.COMPLETED
    ).all()

    fg_acct = acct_objs['1300']
    wip_acct = acct_objs['1310']
    wh_main = session.query(Location).filter(Location.location_id == 'WH-MAIN').first()

    txn_count = 0
    je_count = 0

    for wo in completed_wos:
        erp_item_id = product_to_item.get(wo.product_id)
        if not erp_item_id:
            continue

        item = session.query(Item).filter(Item.item_id == erp_item_id).first()
        if not item:
            continue

        qty = wo.quantity_completed or wo.quantity_ordered or 0
        if qty <= 0:
            continue

        unit_cost = float(item.standard_cost or 0)
        total_cost = unit_cost * qty
        completion_date = wo.actual_end or datetime.utcnow()

        # --- Inventory transaction: production receipt ---
        txn = InventoryTransaction(
            transaction_id=f"TXN-PROD-{wo.work_order_id}",
            transaction_type=TransactionType.PRODUCTION_RECEIPT,
            transaction_date=completion_date,
            item_id=item.id,
            to_location_id=wh_main.id if wh_main else None,
            quantity=qty,
            uom=item.base_uom,
            unit_cost=unit_cost,
            total_cost=total_cost,
            reference_type='work_order',
            reference_id=wo.work_order_id,
            notes=f"Production receipt from WO {wo.work_order_id}",
            created_by='seed',
        )
        session.add(txn)
        txn_count += 1

        if total_cost <= 0:
            continue

        # --- Journal entry: WIP → FG ---
        je = JournalEntry(
            journal_number=f"JE-PROD-{wo.work_order_id}",
            status=JournalStatus.POSTED,
            journal_date=completion_date.date() if hasattr(completion_date, 'date') else date.today(),
            posting_date=completion_date.date() if hasattr(completion_date, 'date') else date.today(),
            description=f"WIP→FG transfer: WO {wo.work_order_id} — {erp_item_id} x{qty}",
            source_type='work_order',
            source_id=wo.work_order_id,
            total_debit=Decimal(str(total_cost)),
            total_credit=Decimal(str(total_cost)),
            created_by='seed',
        )
        session.add(je)
        session.flush()

        # Debit FG Inventory
        session.add(JournalLine(
            journal_id=je.id,
            line_number=1,
            account_id=fg_acct.id,
            debit_amount=Decimal(str(total_cost)),
            credit_amount=Decimal('0'),
            description=f"FG receipt: {erp_item_id} x{qty}",
            cost_center='PRODUCTION',
            created_by='seed',
        ))
        # Credit WIP Inventory
        session.add(JournalLine(
            journal_id=je.id,
            line_number=2,
            account_id=wip_acct.id,
            debit_amount=Decimal('0'),
            credit_amount=Decimal(str(total_cost)),
            description=f"WIP relief: WO {wo.work_order_id}",
            cost_center='PRODUCTION',
            created_by='seed',
        ))
        je_count += 1

    # ── Labor Cost Journal Entries (from TimeEntries) ──────────────────
    from models.mes.labor import TimeEntry as TimeEntryModel, Worker as WorkerModel

    labor_acct = acct_objs.get('5100')  # Direct Labor
    accrued_acct = acct_objs.get('2100')  # Accrued Liabilities
    labor_je_count = 0

    if labor_acct and accrued_acct:
        time_entries = session.query(TimeEntryModel).join(
            WorkerModel, TimeEntryModel.worker_id == WorkerModel.id
        ).filter(
            TimeEntryModel.clock_out != None,
        ).all()

        # Batch: one JE per day for all labor
        from collections import defaultdict as _dd
        daily_labor = _dd(lambda: Decimal('0'))
        for te in time_entries:
            worker = session.query(WorkerModel).filter(WorkerModel.id == te.worker_id).first()
            rate = Decimal(str(worker.hourly_rate)) if worker and worker.hourly_rate else Decimal('25.0')
            cost = Decimal(str(te.regular_hours or 0)) * rate + Decimal(str(te.overtime_hours or 0)) * rate * Decimal('1.5')
            if te.clock_in:
                day = te.clock_in.date()
                daily_labor[day] += cost

        for day, total_cost in sorted(daily_labor.items()):
            if total_cost <= 0:
                continue
            je = JournalEntry(
                journal_number=f"JE-LABOR-{day.isoformat()}",
                status=JournalStatus.POSTED,
                journal_date=day,
                posting_date=day,
                description=f"Daily labor cost: {day.isoformat()}",
                source_type='time_clock',
                source_id=f"daily-{day.isoformat()}",
                total_debit=total_cost,
                total_credit=total_cost,
                created_by='seed',
            )
            session.add(je)
            session.flush()

            session.add(JournalLine(
                journal_id=je.id, line_number=1,
                account_id=labor_acct.id,
                debit_amount=total_cost, credit_amount=Decimal('0'),
                description=f"Direct labor: {day.isoformat()}",
                cost_center='PRODUCTION', created_by='seed',
            ))
            session.add(JournalLine(
                journal_id=je.id, line_number=2,
                account_id=accrued_acct.id,
                debit_amount=Decimal('0'), credit_amount=total_cost,
                description=f"Payroll accrual: {day.isoformat()}",
                created_by='seed',
            ))
            labor_je_count += 1

    session.commit()
    print(f"  + {txn_count} production receipt transactions")
    print(f"  + {je_count} GL journal entries (WIP→FG)")
    print(f"  + {labor_je_count} GL journal entries (labor cost)")


def main():
    print("\n" + "=" * 60)
    print("LEGO Factory v3 - Demo Presentation Seeder")
    print("=" * 60 + "\n")

    engine = get_engine()
    Base.metadata.create_all(engine, checkfirst=True)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        job_count = seed_presentation(session)

        # Seed maintenance windows for demo
        seed_maintenance_windows(session)

        # Seed resource status, tools, materials, events
        seed_resource_data(session)

        # Seed CMMS data (assets, meters, spares, PM schedules, work orders, failure codes)
        seed_cmms_data(session)

        # Seed QMS data (inspections, SPC, NCRs, CAPAs, audits, training, calibration)
        seed_qms_data(session)

        # Seed ERP data (partners, items, orders, inventory)
        seed_erp_data(session)

        # Seed operational data (downtime, OEE, production counts, workers, time entries, machine events)
        seed_operational_data(session)

        # Seed MES operational data (rework, scrap, handovers, kanban, WIP, cycle times)
        seed_mes_operational_data(session)

        # Seed Phase 5 data (setup events, recipe runs, FAIs)
        seed_phase5_data(session)

        # Seed ERP financial data (GL accounts, production receipts, journal entries)
        seed_erp_financial_data(session)

        # Count totals
        wo_count = session.query(WorkOrder).count()
        total_jobs = session.query(Job).count()

        print(f"\n{'=' * 60}")
        print(f"Done! Database now has:")
        print(f"  Work Orders:  {wo_count}")
        print(f"  Scheduled Jobs: {total_jobs}")
        print(f"{'=' * 60}")
        print(f"\nPages to screenshot:")
        print(f"  Gantt Chart:   http://localhost:5000/mes/scheduling")
        print(f"  Work Orders:   http://localhost:5000/mes/work-orders")
        print(f"  Resources:     http://localhost:5000/mes/resources")
        print(f"  Dashboard:     http://localhost:5000/")
        print()

    except Exception as e:
        session.rollback()
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        session.close()


if __name__ == '__main__':
    main()
