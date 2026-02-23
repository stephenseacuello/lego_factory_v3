"""
LEGO Factory v3 - Demo Gantt Chart & Work Order Seeder
======================================================
Populates work orders, operations, and scheduled jobs
for a rich Gantt chart demonstration.

Run inside Docker:
    docker compose exec app python -m database.seeds.seed_demo_gantt

Or locally (with DATABASE_URL set):
    DATABASE_URL=postgresql://lego:LegoFactory2024!@localhost:5434/lego_factory \
        python -m database.seeds.seed_demo_gantt
"""

import os
import sys
import random
from datetime import datetime, timedelta
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import create_engine
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
# Product catalogue – each product has a routing (list of operations)
# ---------------------------------------------------------------------------
PRODUCTS = [
    {
        'product_id': 'brick_2x4_red',
        'name': '2x4 Brick Red',
        'recipe_id': 'RCP-001',
        'routing': [
            ('Design Review', OperationType.DESIGN, 'software', 20, 0, ['software']),
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 120, 10, ['bambu-ps1', 'creality-cr30']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 15, 5, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6', 'niryo-ned2']),
        ],
    },
    {
        'product_id': 'brick_2x4_blue',
        'name': '2x4 Brick Blue',
        'recipe_id': 'RCP-001',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'creality-cr30', 135, 10, ['creality-cr30', 'bambu-ps1']),
            ('Quality Inspection', OperationType.INSPECTION, 'niryo-ned2', 15, 5, ['niryo-ned2']),
            ('Pack & Label', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6']),
        ],
    },
    {
        'product_id': 'brick_2x2_red',
        'name': '2x2 Brick Red',
        'recipe_id': 'RCP-002',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 90, 8, ['bambu-ps1', 'creality-cr30']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 10, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 8, 2, ['xarm-lite6']),
        ],
    },
    {
        'product_id': 'brick_2x4_yellow',
        'name': '2x4 Brick Yellow',
        'recipe_id': 'RCP-001',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 120, 10, ['bambu-ps1', 'creality-cr30']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 15, 5, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6']),
        ],
    },
    {
        'product_id': 'plate_1x4_white',
        'name': '1x4 Plate White',
        'recipe_id': 'RCP-003',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'creality-cr30', 60, 5, ['creality-cr30', 'bambu-ps1']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 10, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 8, 2, ['xarm-lite6']),
        ],
    },
    {
        'product_id': 'gear_8t_black',
        'name': '8-Tooth Technic Gear',
        'recipe_id': 'RCP-004',
        'routing': [
            ('SLA Print', OperationType.PRINTING_SLA, 'formlabs-3', 180, 15, ['formlabs-3']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 20, 5, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6']),
        ],
    },
    {
        'product_id': 'baseplate_16x16_green',
        'name': '16x16 Green Baseplate',
        'recipe_id': 'RCP-005',
        'routing': [
            ('CNC Mill', OperationType.CNC_MILLING, 'bantam-explorer', 90, 15, ['bantam-explorer', 'coastrunner-cr1']),
            ('Deburr & Clean', OperationType.CUSTOM, 'labfab-runner', 20, 5, ['labfab-runner']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 15, 5, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 10, 2, ['xarm-lite6']),
        ],
    },
    {
        'product_id': 'axle_4L_grey',
        'name': 'Technic Axle 4L',
        'recipe_id': 'RCP-006',
        'routing': [
            ('CNC Turn', OperationType.CNC_MILLING, 'rownd-lathe', 45, 10, ['rownd-lathe']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 10, 3, ['niryo-ned2']),
            ('Packaging', OperationType.PACKAGING, 'xarm-lite6', 8, 2, ['xarm-lite6']),
        ],
    },
    {
        'product_id': 'tile_1x2_white',
        'name': '1x2 Smooth Tile White',
        'recipe_id': 'RCP-007',
        'routing': [
            ('FDM Print', OperationType.PRINTING_FDM, 'bambu-ps1', 50, 5, ['bambu-ps1', 'creality-cr30']),
            ('Laser Engrave', OperationType.CUSTOM, 'longer-ray-laser', 15, 3, ['longer-ray-laser']),
            ('Inspect', OperationType.INSPECTION, 'niryo-ned2', 10, 3, ['niryo-ned2']),
        ],
    },
    {
        'product_id': 'minifig_torso_custom',
        'name': 'Custom Minifig Torso',
        'recipe_id': 'RCP-008',
        'routing': [
            ('SLA Print', OperationType.PRINTING_SLA, 'formlabs-3', 150, 15, ['formlabs-3']),
            ('Laser Detail', OperationType.CUSTOM, 'longer-ray-laser', 25, 5, ['longer-ray-laser']),
            ('Assembly', OperationType.ASSEMBLY, 'niryo-ned2', 20, 5, ['niryo-ned2', 'xarm-lite6']),
            ('Quality Check', OperationType.INSPECTION, 'niryo-ned2', 15, 5, ['niryo-ned2']),
        ],
    },
]

CUSTOMERS = ['CUST001', 'CUST002', 'CUST003']
WORKERS = ['EMP001', 'EMP002', 'EMP003', 'EMP004']

# ---------------------------------------------------------------------------
# Work order definitions — a mix of statuses to make the Gantt interesting
# ---------------------------------------------------------------------------

def build_work_orders():
    """Build a list of work order dicts relative to 'now'."""
    now = datetime.utcnow()

    orders = []

    # ---- COMPLETED work orders (finished in the past 24h) ----
    for i, (prod_idx, qty) in enumerate([
        (0, 200), (4, 500), (7, 300),
    ], start=1):
        prod = PRODUCTS[prod_idx]
        start = now - timedelta(hours=random.randint(18, 30))
        orders.append({
            'wo_number': f'WO-2026-C{i:03d}',
            'product': prod,
            'quantity': qty,
            'status': WorkOrderStatus.COMPLETED,
            'priority': random.randint(2, 5),
            'planned_start': start,
            'due_date': now - timedelta(hours=random.randint(1, 6)),
            'customer_id': random.choice(CUSTOMERS),
            'job_status': JobStatus.COMPLETED,
            'time_anchor': start,
        })

    # ---- IN_PROGRESS work orders (started, some jobs running now) ----
    for i, (prod_idx, qty) in enumerate([
        (0, 300), (1, 250), (5, 100), (6, 80), (8, 400), (9, 60),
    ], start=1):
        prod = PRODUCTS[prod_idx]
        start = now - timedelta(hours=random.randint(4, 12))
        orders.append({
            'wo_number': f'WO-2026-P{i:03d}',
            'product': prod,
            'quantity': qty,
            'status': WorkOrderStatus.IN_PROGRESS,
            'priority': random.randint(1, 4),
            'planned_start': start,
            'due_date': now + timedelta(hours=random.randint(12, 72)),
            'customer_id': random.choice(CUSTOMERS),
            'job_status': None,  # mixed
            'time_anchor': start,
        })

    # ---- RELEASED work orders (scheduled but not started) ----
    for i, (prod_idx, qty) in enumerate([
        (2, 600), (3, 350), (4, 800), (7, 150), (1, 500),
    ], start=1):
        prod = PRODUCTS[prod_idx]
        start = now + timedelta(hours=random.randint(2, 24))
        orders.append({
            'wo_number': f'WO-2026-R{i:03d}',
            'product': prod,
            'quantity': qty,
            'status': WorkOrderStatus.RELEASED,
            'priority': random.randint(2, 6),
            'planned_start': start,
            'due_date': now + timedelta(hours=random.randint(48, 120)),
            'customer_id': random.choice(CUSTOMERS),
            'job_status': JobStatus.QUEUED,
            'time_anchor': start,
        })

    # ---- PLANNED work orders (further out) ----
    for i, (prod_idx, qty) in enumerate([
        (0, 1000), (5, 200), (6, 120), (9, 80),
    ], start=1):
        prod = PRODUCTS[prod_idx]
        start = now + timedelta(hours=random.randint(30, 72))
        orders.append({
            'wo_number': f'WO-2026-F{i:03d}',
            'product': prod,
            'quantity': qty,
            'status': WorkOrderStatus.PLANNED,
            'priority': random.randint(3, 7),
            'planned_start': start,
            'due_date': now + timedelta(hours=random.randint(96, 168)),
            'customer_id': random.choice(CUSTOMERS),
            'job_status': JobStatus.PENDING,
            'time_anchor': start,
        })

    return orders


def seed_demo(session):
    """Insert demo work orders, operations, and jobs."""
    now = datetime.utcnow()
    orders = build_work_orders()
    job_counter = 0

    for wo_def in orders:
        prod = wo_def['product']

        # Skip if already exists
        if session.query(WorkOrder).filter_by(work_order_id=wo_def['wo_number']).first():
            print(f"  Skipping existing {wo_def['wo_number']}")
            continue

        # Determine actual_start / actual_end based on status
        actual_start = wo_def['planned_start'] if wo_def['status'] in (
            WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED
        ) else None
        actual_end = (wo_def['due_date'] - timedelta(hours=1)) if wo_def['status'] == WorkOrderStatus.COMPLETED else None

        qty_completed = wo_def['quantity'] if wo_def['status'] == WorkOrderStatus.COMPLETED else (
            int(wo_def['quantity'] * random.uniform(0.1, 0.7)) if wo_def['status'] == WorkOrderStatus.IN_PROGRESS else 0
        )

        wo = WorkOrder(
            work_order_id=wo_def['wo_number'],
            description=f"Production run: {prod['name']}",
            product_id=prod['product_id'],
            recipe_id=prod['recipe_id'],
            quantity_ordered=wo_def['quantity'],
            quantity_completed=qty_completed,
            status=wo_def['status'],
            priority=wo_def['priority'],
            planned_start=wo_def['planned_start'],
            due_date=wo_def['due_date'],
            actual_start=actual_start,
            actual_end=actual_end,
            customer_id=wo_def['customer_id'],
            sales_order_id=f"SO-2026-{random.randint(100,999)}",
        )
        session.add(wo)
        session.flush()  # get wo.id

        # --- Build operations & jobs along the routing ---
        cursor = wo_def['time_anchor']  # rolling time cursor for sequential scheduling
        routing = prod['routing']

        for seq_idx, (op_name, op_type, default_machine, run_mins, setup_mins, eligible) in enumerate(routing):
            seq = (seq_idx + 1) * 10

            # Determine operation status
            if wo_def['status'] == WorkOrderStatus.COMPLETED:
                op_status = JobStatus.COMPLETED
            elif wo_def['status'] == WorkOrderStatus.IN_PROGRESS:
                if seq_idx == 0:
                    op_status = JobStatus.COMPLETED
                elif seq_idx == 1:
                    op_status = JobStatus.RUNNING
                else:
                    op_status = JobStatus.QUEUED
            elif wo_def['status'] == WorkOrderStatus.RELEASED:
                op_status = JobStatus.QUEUED
            else:
                op_status = JobStatus.PENDING

            op = Operation(
                work_order_id=wo.id,
                operation_id=f"{wo_def['wo_number']}-OP{seq}",
                sequence=seq,
                operation_type=op_type,
                name=op_name,
                machine_id=default_machine,
                eligible_machines=eligible,
                setup_time=setup_mins,
                run_time=run_mins,
                status=op_status,
                started_at=cursor if op_status in (JobStatus.RUNNING, JobStatus.COMPLETED) else None,
                completed_at=(cursor + timedelta(minutes=setup_mins + run_mins)) if op_status == JobStatus.COMPLETED else None,
            )
            session.add(op)
            session.flush()

            # --- Only create jobs for physical machines (skip 'software') ---
            if default_machine == 'software':
                cursor += timedelta(minutes=setup_mins + run_mins)
                continue

            # Add a small random variation to make the Gantt look natural
            jitter = random.randint(-5, 10)
            job_start = cursor + timedelta(minutes=jitter)
            job_end = job_start + timedelta(minutes=setup_mins + run_mins + random.randint(0, 15))

            # For running jobs, make them straddle 'now'
            if op_status == JobStatus.RUNNING:
                back = max(15, int(run_mins * 0.6))
                fwd = max(20, int(run_mins * 0.6))
                job_start = now - timedelta(minutes=random.randint(10, back))
                job_end = now + timedelta(minutes=random.randint(15, fwd))

            job_counter += 1

            # Determine quantities for this job
            if op_status == JobStatus.COMPLETED:
                j_qty_completed = wo_def['quantity']
                j_qty_rejected = random.randint(0, max(1, int(wo_def['quantity'] * 0.02)))
            elif op_status == JobStatus.RUNNING:
                j_qty_completed = int(wo_def['quantity'] * random.uniform(0.2, 0.6))
                j_qty_rejected = random.randint(0, 3)
            else:
                j_qty_completed = 0
                j_qty_rejected = 0

            job = Job(
                job_id=f"JOB-2026-{job_counter:04d}",
                work_order_id=wo.id,
                operation_id=op.id,
                machine_id=default_machine,
                scheduled_start=job_start,
                scheduled_end=job_end,
                actual_start=job_start if op_status in (JobStatus.RUNNING, JobStatus.COMPLETED) else None,
                actual_end=job_end if op_status == JobStatus.COMPLETED else None,
                status=op_status,
                priority_score=float(10 - wo_def['priority']),
                quantity_planned=wo_def['quantity'],
                quantity_completed=j_qty_completed,
                quantity_rejected=j_qty_rejected,
                assigned_worker_id=random.choice(WORKERS),
                runtime_data={
                    'operation_name': op_name,
                    'operation_type': op_type.value,
                    'eligible_machines': eligible,
                    'estimated_duration_mins': setup_mins + run_mins,
                    'setup_time_mins': setup_mins,
                    'material_type': 'PLA' if 'fdm' in op_type.value.lower() else (
                        'Resin' if 'sla' in op_type.value.lower() else 'Mixed'
                    ),
                },
            )
            session.add(job)

            # Advance cursor for next operation
            cursor = job_end + timedelta(minutes=random.randint(5, 20))

        print(f"  Created {wo_def['wo_number']} ({wo_def['status'].value}) "
              f"- {prod['name']} x{wo_def['quantity']}")

    session.commit()
    return len(orders), job_counter


def main():
    print("\n" + "=" * 60)
    print("LEGO Factory v3 - Demo Gantt Chart Seeder")
    print("=" * 60 + "\n")

    engine = get_engine()
    Base.metadata.create_all(engine, checkfirst=True)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        wo_count, job_count = seed_demo(session)
        print(f"\nDone! Created {wo_count} work orders with {job_count} scheduled jobs.")
        print("Visit http://localhost:5000/mes/scheduling to see the Gantt chart.")
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
