"""
LEGO Factory v3 - Simulation Seed Data
=======================================
Comprehensive seed data for MESA-11 MES demonstration.

Run with: python -m database.seeds.seed_simulation

Creates:
- Work orders in various states
- Shift definitions
- Workers with varied skill profiles
- PM schedules for each machine
- Material lots
- SPC charts with baseline readings
- Inspection records
- Historical OEE data
- Genealogy records
- Sample documents
"""

import os
import sys
import random
from datetime import datetime, date, timedelta
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def seed_shifts():
    """Create shift definitions."""
    shifts = [
        {
            'id': 'shift-day',
            'name': 'Day Shift',
            'start_time': '06:00',
            'end_time': '14:00',
            'hours': 8,
            'days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
        },
        {
            'id': 'shift-evening',
            'name': 'Evening Shift',
            'start_time': '14:00',
            'end_time': '22:00',
            'hours': 8,
            'days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
        },
        {
            'id': 'shift-night',
            'name': 'Night Shift',
            'start_time': '22:00',
            'end_time': '06:00',
            'hours': 8,
            'days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
        },
    ]
    print(f"Created {len(shifts)} shift definitions")
    return shifts


def seed_workers():
    """Create workers with varied skill profiles and certifications."""
    workers = [
        {
            'id': 'W001',
            'name': 'John Smith',
            'department': 'Production',
            'role': 'Operator',
            'hire_date': '2022-01-15',
            'shift': 'day',
            'skills': {
                'fdm_printing': {'level': 'expert', 'certified_date': '2022-03-01', 'expiry_date': '2025-03-01'},
                'sla_printing': {'level': 'advanced', 'certified_date': '2022-06-15', 'expiry_date': '2025-06-15'},
                'cnc_milling': {'level': 'basic', 'certified_date': '2023-01-10', 'expiry_date': '2026-01-10'},
                'quality_inspection': {'level': 'intermediate', 'certified_date': '2022-09-01', 'expiry_date': '2025-09-01'},
            },
        },
        {
            'id': 'W002',
            'name': 'Sarah Johnson',
            'department': 'Production',
            'role': 'Senior Operator',
            'hire_date': '2020-05-20',
            'shift': 'day',
            'skills': {
                'fdm_printing': {'level': 'expert', 'certified_date': '2020-08-01', 'expiry_date': '2025-08-01'},
                'sla_printing': {'level': 'expert', 'certified_date': '2020-10-15', 'expiry_date': '2025-10-15'},
                'cnc_milling': {'level': 'advanced', 'certified_date': '2021-03-01', 'expiry_date': '2024-03-01'},
                'laser_cutting': {'level': 'intermediate', 'certified_date': '2022-01-15', 'expiry_date': '2025-01-15'},
                'assembly': {'level': 'expert', 'certified_date': '2020-07-01', 'expiry_date': '2025-07-01'},
            },
        },
        {
            'id': 'W003',
            'name': 'Mike Chen',
            'department': 'Production',
            'role': 'Operator',
            'hire_date': '2023-03-10',
            'shift': 'evening',
            'skills': {
                'fdm_printing': {'level': 'intermediate', 'certified_date': '2023-06-01', 'expiry_date': '2026-06-01'},
                'assembly': {'level': 'basic', 'certified_date': '2023-04-15', 'expiry_date': '2026-04-15'},
            },
        },
        {
            'id': 'W004',
            'name': 'Emily Davis',
            'department': 'Quality',
            'role': 'Quality Inspector',
            'hire_date': '2021-08-01',
            'shift': 'day',
            'skills': {
                'quality_inspection': {'level': 'expert', 'certified_date': '2021-11-01', 'expiry_date': '2024-11-01'},
                'spc_analysis': {'level': 'advanced', 'certified_date': '2022-02-01', 'expiry_date': '2025-02-01'},
                'metrology': {'level': 'expert', 'certified_date': '2021-12-01', 'expiry_date': '2024-12-01'},
            },
        },
        {
            'id': 'W005',
            'name': 'Tom Wilson',
            'department': 'Maintenance',
            'role': 'Maintenance Technician',
            'hire_date': '2019-11-15',
            'shift': 'day',
            'skills': {
                'machine_maintenance': {'level': 'expert', 'certified_date': '2020-02-01', 'expiry_date': '2025-02-01'},
                'electrical_systems': {'level': 'advanced', 'certified_date': '2020-04-01', 'expiry_date': '2025-04-01'},
                'calibration': {'level': 'intermediate', 'certified_date': '2021-01-15', 'expiry_date': '2024-01-15'},
            },
        },
        {
            'id': 'W006',
            'name': 'Lisa Brown',
            'department': 'Production',
            'role': 'Operator',
            'hire_date': '2022-09-01',
            'shift': 'evening',
            'skills': {
                'fdm_printing': {'level': 'basic', 'certified_date': '2022-12-01', 'expiry_date': '2025-12-01'},
                'laser_cutting': {'level': 'trainee', 'certified_date': '2023-06-01', 'expiry_date': '2026-06-01'},
            },
        },
        {
            'id': 'W007',
            'name': 'James Lee',
            'department': 'Production',
            'role': 'CNC Specialist',
            'hire_date': '2018-06-01',
            'shift': 'night',
            'skills': {
                'cnc_milling': {'level': 'expert', 'certified_date': '2018-09-01', 'expiry_date': '2025-09-01'},
                'cnc_programming': {'level': 'expert', 'certified_date': '2019-01-01', 'expiry_date': '2025-01-01'},
                'quality_inspection': {'level': 'intermediate', 'certified_date': '2020-03-01', 'expiry_date': '2025-03-01'},
            },
        },
        {
            'id': 'W008',
            'name': 'Anna Martinez',
            'department': 'Production',
            'role': 'Shift Supervisor',
            'hire_date': '2017-02-15',
            'shift': 'day',
            'skills': {
                'fdm_printing': {'level': 'expert', 'certified_date': '2017-05-01', 'expiry_date': '2025-05-01'},
                'sla_printing': {'level': 'advanced', 'certified_date': '2018-01-01', 'expiry_date': '2025-01-01'},
                'cnc_milling': {'level': 'intermediate', 'certified_date': '2019-06-01', 'expiry_date': '2025-06-01'},
                'supervision': {'level': 'expert', 'certified_date': '2019-01-01'},
            },
        },
    ]
    print(f"Created {len(workers)} workers with skill profiles")
    return workers


def seed_work_orders():
    """Create work orders in various states."""
    today = date.today()

    work_orders = [
        {
            'wo_number': 'WO-2024-001',
            'product_id': 'BRICK-2x4-RED',
            'product_name': '2x4 Red Brick',
            'quantity': 500,
            'status': 'in_progress',
            'priority': 'high',
            'release_date': (today - timedelta(days=2)).isoformat(),
            'due_date': (today + timedelta(days=3)).isoformat(),
            'routing': ['fdm_print', 'quality_check', 'packaging'],
            'completed_qty': 350,
        },
        {
            'wo_number': 'WO-2024-002',
            'product_id': 'BRICK-2x2-BLUE',
            'product_name': '2x2 Blue Brick',
            'quantity': 1000,
            'status': 'released',
            'priority': 'medium',
            'release_date': (today - timedelta(days=1)).isoformat(),
            'due_date': (today + timedelta(days=5)).isoformat(),
            'routing': ['fdm_print', 'quality_check', 'packaging'],
            'completed_qty': 0,
        },
        {
            'wo_number': 'WO-2024-003',
            'product_id': 'PLATE-1x4-YELLOW',
            'product_name': '1x4 Yellow Plate',
            'quantity': 750,
            'status': 'in_progress',
            'priority': 'medium',
            'release_date': (today - timedelta(days=3)).isoformat(),
            'due_date': (today + timedelta(days=2)).isoformat(),
            'routing': ['fdm_print', 'quality_check', 'packaging'],
            'completed_qty': 500,
        },
        {
            'wo_number': 'WO-2024-004',
            'product_id': 'GEAR-8T-BLACK',
            'product_name': '8-Tooth Gear',
            'quantity': 200,
            'status': 'released',
            'priority': 'high',
            'release_date': today.isoformat(),
            'due_date': (today + timedelta(days=2)).isoformat(),
            'routing': ['sla_print', 'curing', 'quality_check', 'packaging'],
            'completed_qty': 0,
        },
        {
            'wo_number': 'WO-2024-005',
            'product_id': 'BASEPLATE-32x32',
            'product_name': '32x32 Baseplate',
            'quantity': 50,
            'status': 'completed',
            'priority': 'low',
            'release_date': (today - timedelta(days=7)).isoformat(),
            'due_date': (today - timedelta(days=2)).isoformat(),
            'routing': ['cnc_mill', 'quality_check', 'packaging'],
            'completed_qty': 50,
        },
    ]
    print(f"Created {len(work_orders)} work orders")
    return work_orders


def seed_pm_schedules():
    """Create PM schedules for each machine."""
    machines = [
        ('bambu-ps1', 'weekly', 168),
        ('bambu-ps2', 'weekly', 168),
        ('prusa-mk4-1', 'weekly', 168),
        ('prusa-mk4-2', 'weekly', 168),
        ('formlabs-3l', 'bi-weekly', 336),
        ('bantam-explorer', 'monthly', 720),
        ('nomad-883', 'monthly', 720),
        ('k40-laser', 'bi-weekly', 336),
        ('emblaser-2', 'bi-weekly', 336),
        ('assembly-1', 'quarterly', 2160),
        ('inspection-1', 'monthly', 720),
    ]

    today = date.today()
    pm_schedules = []

    for machine_id, frequency, hours in machines:
        pm_schedules.append({
            'id': f'PM-{machine_id.upper()}',
            'machine_id': machine_id,
            'name': f'{frequency.title()} PM - {machine_id}',
            'frequency': frequency,
            'interval_hours': hours,
            'last_completed': (today - timedelta(days=random.randint(1, 14))).isoformat(),
            'next_due': (today + timedelta(days=random.randint(1, 14))).isoformat(),
            'tasks': [
                'Clean and inspect',
                'Lubricate moving parts',
                'Check belt tension',
                'Verify calibration',
                'Run diagnostics',
            ],
        })

    print(f"Created {len(pm_schedules)} PM schedules")
    return pm_schedules


def seed_material_lots():
    """Create material lots (PLA, ABS, PETG spools; aluminum stock; resin cartridges)."""
    materials = [
        ('PLA-RED-001', 'PLA Filament - Red', 'PLA', 10, 'kg', 'LOC-A1', 25.00),
        ('PLA-RED-002', 'PLA Filament - Red', 'PLA', 8, 'kg', 'LOC-A1', 25.00),
        ('PLA-BLUE-001', 'PLA Filament - Blue', 'PLA', 12, 'kg', 'LOC-A2', 25.00),
        ('PLA-YELLOW-001', 'PLA Filament - Yellow', 'PLA', 6, 'kg', 'LOC-A2', 25.00),
        ('PLA-BLACK-001', 'PLA Filament - Black', 'PLA', 15, 'kg', 'LOC-A3', 25.00),
        ('ABS-WHITE-001', 'ABS Filament - White', 'ABS', 5, 'kg', 'LOC-B1', 30.00),
        ('PETG-CLEAR-001', 'PETG Filament - Clear', 'PETG', 4, 'kg', 'LOC-B2', 35.00),
        ('RESIN-STD-001', 'Standard Resin - Grey', 'Resin', 2, 'L', 'LOC-C1', 45.00),
        ('RESIN-STD-002', 'Standard Resin - Grey', 'Resin', 1.5, 'L', 'LOC-C1', 45.00),
        ('RESIN-TOUGH-001', 'Tough Resin - Black', 'Resin', 1, 'L', 'LOC-C2', 65.00),
        ('ALU-6061-001', 'Aluminum 6061 Stock', 'Aluminum', 20, 'pcs', 'LOC-D1', 15.00),
        ('ALU-6061-002', 'Aluminum 6061 Stock', 'Aluminum', 15, 'pcs', 'LOC-D1', 15.00),
    ]

    today = date.today()
    lots = []

    for lot_num, name, material_type, qty, unit, location, cost in materials:
        lots.append({
            'lot_number': lot_num,
            'name': name,
            'material_type': material_type,
            'quantity_available': qty,
            'quantity_reserved': random.randint(0, int(qty * 0.3)),
            'unit': unit,
            'location': location,
            'cost_per_unit': cost,
            'received_date': (today - timedelta(days=random.randint(7, 60))).isoformat(),
            'expiry_date': (today + timedelta(days=random.randint(180, 365))).isoformat(),
            'status': 'available',
            'supplier': f'Supplier-{random.choice(["A", "B", "C"])}',
        })

    print(f"Created {len(lots)} material lots")
    return lots


def seed_spc_charts():
    """Create SPC charts with 50 baseline readings per chart."""
    machines = ['bambu-ps1', 'prusa-mk4-1', 'formlabs-3l', 'bantam-explorer']

    charts = []
    readings = []

    for machine_id in machines:
        # Height chart
        chart_id = f'SPC-{machine_id.upper()}-HEIGHT'
        nominal = 9.6
        sigma = 0.05

        chart = {
            'chart_id': chart_id,
            'name': f'Part Height - {machine_id}',
            'characteristic': 'Height',
            'chart_type': 'xbar_r',
            'subgroup_size': 5,
            'machine_id': machine_id,
            'ucl': nominal + 3 * sigma,
            'lcl': nominal - 3 * sigma,
            'center_line': nominal,
            'usl': nominal + 0.2,
            'lsl': nominal - 0.2,
            'is_active': True,
        }
        charts.append(chart)

        # Generate 50 readings
        for i in range(50):
            values = [nominal + random.gauss(0, sigma) for _ in range(5)]
            mean = sum(values) / len(values)
            range_val = max(values) - min(values)

            readings.append({
                'chart_id': chart_id,
                'sample_time': (datetime.now() - timedelta(hours=50 - i)).isoformat(),
                'subgroup_number': i + 1,
                'values': values,
                'mean': mean,
                'range_value': range_val,
                'in_control': chart['lcl'] <= mean <= chart['ucl'],
                'rule_violations': [],
            })

    print(f"Created {len(charts)} SPC charts with {len(readings)} readings")
    return charts, readings


def seed_inspections():
    """Create completed inspections (2 pass, 1 fail with NCR)."""
    today = date.today()

    inspections = [
        {
            'inspection_number': 'INS-20260125-001',
            'job_id': 'WO-2024-001',
            'serial_number': 'SN-001',
            'plan_name': 'Brick Dimension Check',
            'inspector_id': 'W004',
            'status': 'passed',
            'completed_at': (datetime.now() - timedelta(days=3)).isoformat(),
            'measurements': [
                {'dimension': 'Height', 'nominal': 9.6, 'actual': 9.58, 'result': 'pass'},
                {'dimension': 'Width', 'nominal': 15.8, 'actual': 15.82, 'result': 'pass'},
                {'dimension': 'Length', 'nominal': 31.8, 'actual': 31.75, 'result': 'pass'},
            ],
        },
        {
            'inspection_number': 'INS-20260126-001',
            'job_id': 'WO-2024-003',
            'serial_number': 'SN-002',
            'plan_name': 'Plate Dimension Check',
            'inspector_id': 'W004',
            'status': 'passed',
            'completed_at': (datetime.now() - timedelta(days=2)).isoformat(),
            'measurements': [
                {'dimension': 'Height', 'nominal': 3.2, 'actual': 3.18, 'result': 'pass'},
                {'dimension': 'Width', 'nominal': 7.8, 'actual': 7.82, 'result': 'pass'},
            ],
        },
        {
            'inspection_number': 'INS-20260126-002',
            'job_id': 'WO-2024-002',
            'serial_number': 'SN-003',
            'plan_name': 'Brick Dimension Check',
            'inspector_id': 'W004',
            'status': 'failed',
            'completed_at': (datetime.now() - timedelta(days=2)).isoformat(),
            'measurements': [
                {'dimension': 'Height', 'nominal': 9.6, 'actual': 9.58, 'result': 'pass'},
                {'dimension': 'Width', 'nominal': 15.8, 'actual': 16.05, 'result': 'fail'},  # Out of tolerance
                {'dimension': 'Stud Diameter', 'nominal': 4.85, 'actual': 4.92, 'result': 'fail'},  # Out of tolerance
            ],
            'ncr_number': 'NCR-20260126-001',
        },
    ]

    print(f"Created {len(inspections)} inspection records")
    return inspections


def seed_oee_history():
    """Create 30 days of historical OEE data per machine."""
    machines = [
        'bambu-ps1', 'bambu-ps2', 'prusa-mk4-1', 'prusa-mk4-2',
        'formlabs-3l', 'bantam-explorer', 'nomad-883',
        'k40-laser', 'emblaser-2', 'assembly-1', 'inspection-1'
    ]

    today = date.today()
    oee_records = []

    for machine_id in machines:
        for day_offset in range(30):
            record_date = today - timedelta(days=day_offset)

            # Generate realistic OEE components
            availability = 0.85 + random.gauss(0, 0.05)
            performance = 0.90 + random.gauss(0, 0.04)
            quality = 0.97 + random.gauss(0, 0.02)

            # Clamp values
            availability = max(0.5, min(1.0, availability))
            performance = max(0.6, min(1.0, performance))
            quality = max(0.85, min(1.0, quality))

            oee = availability * performance * quality

            # Production counts
            planned_qty = random.randint(80, 150)
            good_qty = int(planned_qty * oee)
            scrap_qty = planned_qty - good_qty

            # Downtime
            planned_downtime = random.randint(15, 45)
            unplanned_downtime = random.randint(0, 30)

            oee_records.append({
                'machine_id': machine_id,
                'date': record_date.isoformat(),
                'availability': round(availability, 4),
                'performance': round(performance, 4),
                'quality': round(quality, 4),
                'oee': round(oee, 4),
                'planned_qty': planned_qty,
                'good_qty': good_qty,
                'scrap_qty': scrap_qty,
                'planned_downtime_mins': planned_downtime,
                'unplanned_downtime_mins': unplanned_downtime,
            })

    print(f"Created {len(oee_records)} OEE history records")
    return oee_records


def seed_genealogy():
    """Create genealogy records for completed WOs."""
    genealogy_records = [
        {
            'serial_number': 'SN-2024-001-0001',
            'work_order_id': 'WO-2024-005',
            'product_id': 'BASEPLATE-32x32',
            'status': 'completed',
            'created_at': (datetime.now() - timedelta(days=5)).isoformat(),
            'completed_at': (datetime.now() - timedelta(days=3)).isoformat(),
            'process_steps': [
                {
                    'operation': 'cnc_mill',
                    'machine_id': 'bantam-explorer',
                    'worker_id': 'W007',
                    'start_time': (datetime.now() - timedelta(days=4, hours=2)).isoformat(),
                    'end_time': (datetime.now() - timedelta(days=4)).isoformat(),
                    'parameters': {'feed_rate': 500, 'spindle_speed': 12000},
                    'quality_result': 'pass',
                },
                {
                    'operation': 'quality_check',
                    'machine_id': 'inspection-1',
                    'worker_id': 'W004',
                    'start_time': (datetime.now() - timedelta(days=3, hours=6)).isoformat(),
                    'end_time': (datetime.now() - timedelta(days=3, hours=5)).isoformat(),
                    'quality_result': 'pass',
                },
                {
                    'operation': 'packaging',
                    'machine_id': 'assembly-1',
                    'worker_id': 'W002',
                    'start_time': (datetime.now() - timedelta(days=3, hours=4)).isoformat(),
                    'end_time': (datetime.now() - timedelta(days=3, hours=3)).isoformat(),
                    'quality_result': 'pass',
                },
            ],
            'input_materials': [
                {'lot_number': 'ALU-6061-001', 'quantity_consumed': 1},
            ],
        },
    ]

    print(f"Created {len(genealogy_records)} genealogy records")
    return genealogy_records


def seed_documents():
    """Create sample documents (SOPs, work instructions)."""
    documents = [
        {
            'doc_number': 'SOP-001',
            'title': 'FDM Printing Procedure',
            'type': 'SOP',
            'revision': 'A',
            'effective_date': '2024-01-01',
            'operations': ['fdm_print'],
        },
        {
            'doc_number': 'SOP-002',
            'title': 'CNC Milling Procedure',
            'type': 'SOP',
            'revision': 'B',
            'effective_date': '2024-02-15',
            'operations': ['cnc_mill'],
        },
        {
            'doc_number': 'SOP-003',
            'title': 'SLA Printing Procedure',
            'type': 'SOP',
            'revision': 'A',
            'effective_date': '2024-01-15',
            'operations': ['sla_print'],
        },
        {
            'doc_number': 'WI-001',
            'title': 'Inspection Procedure - Brick Dimensions',
            'type': 'Work Instruction',
            'revision': 'C',
            'effective_date': '2024-03-01',
            'operations': ['quality_check'],
        },
        {
            'doc_number': 'WI-002',
            'title': 'Bambu Printer Operation Guide',
            'type': 'Work Instruction',
            'revision': 'A',
            'effective_date': '2024-01-01',
            'operations': ['fdm_print'],
            'machines': ['bambu-ps1', 'bambu-ps2'],
        },
        {
            'doc_number': 'QCP-001',
            'title': 'Quality Control Plan - LEGO Bricks',
            'type': 'Quality Control Plan',
            'revision': 'B',
            'effective_date': '2024-02-01',
            'operations': ['quality_check'],
        },
    ]

    print(f"Created {len(documents)} document records")
    return documents


def seed_all():
    """Seed all simulation data."""
    print("=" * 60)
    print("LEGO Factory v3 - Seeding Simulation Data")
    print("=" * 60)
    print()

    data = {
        'shifts': seed_shifts(),
        'workers': seed_workers(),
        'work_orders': seed_work_orders(),
        'pm_schedules': seed_pm_schedules(),
        'material_lots': seed_material_lots(),
        'spc_charts': seed_spc_charts()[0],
        'spc_readings': seed_spc_charts()[1],
        'inspections': seed_inspections(),
        'oee_history': seed_oee_history(),
        'genealogy': seed_genealogy(),
        'documents': seed_documents(),
    }

    print()
    print("=" * 60)
    print("Seed data created successfully!")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"  - Shifts: {len(data['shifts'])}")
    print(f"  - Workers: {len(data['workers'])}")
    print(f"  - Work Orders: {len(data['work_orders'])}")
    print(f"  - PM Schedules: {len(data['pm_schedules'])}")
    print(f"  - Material Lots: {len(data['material_lots'])}")
    print(f"  - SPC Charts: {len(data['spc_charts'])}")
    print(f"  - Inspections: {len(data['inspections'])}")
    print(f"  - OEE Records: {len(data['oee_history'])}")
    print(f"  - Genealogy Records: {len(data['genealogy'])}")
    print(f"  - Documents: {len(data['documents'])}")

    return data


if __name__ == '__main__':
    seed_all()
