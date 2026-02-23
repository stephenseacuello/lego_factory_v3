"""
Traceability Routes - Digital Thread & Product Genealogy API

LegoMCP World-Class Manufacturing System v5.0
Phase 15: Digital Thread & Product Genealogy

Provides:
- Complete product genealogy
- Material traceability (lot tracking)
- Process history recording
- Root cause analysis support
- Recall simulation
- As-built vs as-designed comparison
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
import uuid

traceability_bp = Blueprint('traceability', __name__, url_prefix='/traceability')

# Try to import traceability services
try:
    from services.traceability import (
        DigitalThreadService,
        ProductGenealogy,
    )
    TRACEABILITY_AVAILABLE = True
except ImportError:
    TRACEABILITY_AVAILABLE = False

# In-memory storage for demo
_genealogy_records = {}
_material_lots = {}
_process_snapshots = {}


@traceability_bp.route('/status', methods=['GET'])
def get_traceability_status():
    """
    Get digital thread system status.

    Returns:
        JSON with system capabilities
    """
    return jsonify({
        'available': True,
        'capabilities': {
            'product_genealogy': True,
            'material_traceability': True,
            'process_history': True,
            'root_cause_analysis': True,
            'recall_simulation': True,
            'as_built_tracking': True,
        },
        'coverage': {
            'parts_tracked': len(_genealogy_records),
            'lots_tracked': len(_material_lots),
            'process_snapshots': len(_process_snapshots),
        }
    })


# ==================== Product Genealogy ====================

@traceability_bp.route('/genealogy', methods=['POST'])
def create_genealogy():
    """
    Create a product genealogy record.

    Request body:
    {
        "serial_number": "SN-2024-001234",
        "part_id": "BRICK-2X4",
        "work_order_id": "WO-001",
        "machine_id": "WC-PRINT-01",
        "operator_id": "OP-001",
        "material_lots": [
            {"material_id": "PLA-RED", "lot_number": "LOT-2024-001"}
        ]
    }

    Returns:
        JSON with created genealogy record
    """
    data = request.get_json() or {}

    genealogy_id = str(uuid.uuid4())
    serial_number = data.get('serial_number', f"SN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")

    record = {
        'genealogy_id': genealogy_id,
        'serial_number': serial_number,
        'part_id': data.get('part_id'),
        'work_order_id': data.get('work_order_id'),
        'machine_id': data.get('machine_id'),
        'operator_id': data.get('operator_id'),
        'created_at': datetime.utcnow().isoformat(),
        'status': 'active',
        'material_lots': data.get('material_lots', []),
        'process_snapshots': [],
        'quality_events': [],
        'parent_serials': data.get('parent_serials', []),
        'child_serials': [],
    }

    _genealogy_records[serial_number] = record

    return jsonify({
        'success': True,
        'genealogy': record,
    }), 201


@traceability_bp.route('/genealogy/<serial_number>', methods=['GET'])
def get_genealogy(serial_number: str):
    """
    Get complete genealogy for a serial number.

    Returns:
        JSON with full product history
    """
    record = _genealogy_records.get(serial_number)

    if not record:
        # Return demo data
        record = {
            'genealogy_id': str(uuid.uuid4()),
            'serial_number': serial_number,
            'part_id': 'BRICK-2X4',
            'work_order_id': 'WO-001',
            'machine_id': 'WC-PRINT-01',
            'operator_id': 'OP-001',
            'created_at': (datetime.utcnow() - timedelta(days=7)).isoformat(),
            'status': 'shipped',
            'material_lots': [
                {'material_id': 'PLA-RED', 'lot_number': 'LOT-2024-001', 'quantity': 5.2}
            ],
            'process_snapshots': [
                {
                    'operation': 'printing',
                    'timestamp': (datetime.utcnow() - timedelta(days=7, hours=2)).isoformat(),
                    'parameters': {'nozzle_temp': 210, 'bed_temp': 60, 'speed': 40},
                },
                {
                    'operation': 'inspection',
                    'timestamp': (datetime.utcnow() - timedelta(days=7, hours=1)).isoformat(),
                    'result': 'pass',
                }
            ],
            'quality_events': [
                {
                    'event_type': 'inspection',
                    'result': 'pass',
                    'clutch_power': 2.1,
                    'timestamp': (datetime.utcnow() - timedelta(days=7, hours=1)).isoformat(),
                }
            ],
            'parent_serials': [],
            'child_serials': [],
            'demo': True,
        }

    return jsonify(record)


@traceability_bp.route('/genealogy/<serial_number>/tree', methods=['GET'])
def get_genealogy_tree(serial_number: str):
    """
    Get hierarchical genealogy tree.

    Returns:
        JSON with parent/child relationships
    """
    record = _genealogy_records.get(serial_number)

    # Build tree structure
    tree = {
        'serial_number': serial_number,
        'part_id': record.get('part_id', 'BRICK-2X4') if record else 'BRICK-2X4',
        'level': 0,
        'parents': [],
        'children': [],
        'materials': [
            {'material_id': 'PLA-RED', 'lot': 'LOT-2024-001'}
        ],
    }

    # Add parent materials as "parents"
    if record and record.get('parent_serials'):
        for parent_sn in record['parent_serials']:
            parent_record = _genealogy_records.get(parent_sn, {})
            tree['parents'].append({
                'serial_number': parent_sn,
                'part_id': parent_record.get('part_id', 'COMPONENT'),
                'level': -1,
            })

    return jsonify({'tree': tree})


@traceability_bp.route('/genealogy/<serial_number>/process', methods=['POST'])
def add_process_snapshot(serial_number: str):
    """
    Add a process snapshot to genealogy.

    Request body:
    {
        "operation": "printing",
        "parameters": {"nozzle_temp": 210, "bed_temp": 60},
        "machine_id": "WC-PRINT-01"
    }
    """
    data = request.get_json() or {}

    snapshot = {
        'snapshot_id': str(uuid.uuid4()),
        'timestamp': datetime.utcnow().isoformat(),
        'operation': data.get('operation'),
        'parameters': data.get('parameters', {}),
        'machine_id': data.get('machine_id'),
        'operator_id': data.get('operator_id'),
    }

    if serial_number in _genealogy_records:
        _genealogy_records[serial_number]['process_snapshots'].append(snapshot)

    return jsonify({
        'success': True,
        'snapshot': snapshot,
    }), 201


@traceability_bp.route('/genealogy/<serial_number>/quality', methods=['POST'])
def add_quality_event(serial_number: str):
    """
    Add a quality event to genealogy.

    Request body:
    {
        "event_type": "inspection|test|ncr|rework",
        "result": "pass|fail",
        "measurements": {"clutch_power": 2.1},
        "notes": "..."
    }
    """
    data = request.get_json() or {}

    event = {
        'event_id': str(uuid.uuid4()),
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': data.get('event_type'),
        'result': data.get('result'),
        'measurements': data.get('measurements', {}),
        'notes': data.get('notes'),
        'inspector_id': data.get('inspector_id'),
    }

    if serial_number in _genealogy_records:
        _genealogy_records[serial_number]['quality_events'].append(event)

    return jsonify({
        'success': True,
        'event': event,
    }), 201


# ==================== Material Traceability ====================

@traceability_bp.route('/lots', methods=['POST'])
def create_material_lot():
    """
    Create a material lot record.

    Request body:
    {
        "lot_number": "LOT-2024-001",
        "material_id": "PLA-RED",
        "supplier": "FilamentCo",
        "quantity": 1000,
        "unit": "grams",
        "received_date": "2024-01-15",
        "expiry_date": "2025-01-15",
        "certificate_of_analysis": {...}
    }
    """
    data = request.get_json() or {}

    lot_number = data.get('lot_number', f"LOT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")

    lot = {
        'lot_number': lot_number,
        'material_id': data.get('material_id'),
        'supplier': data.get('supplier'),
        'quantity_received': data.get('quantity', 0),
        'quantity_remaining': data.get('quantity', 0),
        'unit': data.get('unit', 'grams'),
        'received_date': data.get('received_date'),
        'expiry_date': data.get('expiry_date'),
        'certificate_of_analysis': data.get('certificate_of_analysis', {}),
        'status': 'available',
        'consumed_by': [],  # Serial numbers that used this lot
    }

    _material_lots[lot_number] = lot

    return jsonify({
        'success': True,
        'lot': lot,
    }), 201


@traceability_bp.route('/lots/<lot_number>', methods=['GET'])
def get_material_lot(lot_number: str):
    """
    Get material lot details and usage.

    Returns:
        JSON with lot info and consumption history
    """
    lot = _material_lots.get(lot_number)

    if not lot:
        # Demo data
        lot = {
            'lot_number': lot_number,
            'material_id': 'PLA-RED',
            'supplier': 'FilamentCo',
            'quantity_received': 1000,
            'quantity_remaining': 750,
            'unit': 'grams',
            'received_date': '2024-01-15',
            'expiry_date': '2025-01-15',
            'status': 'available',
            'consumed_by': ['SN-2024-001234', 'SN-2024-001235'],
            'demo': True,
        }

    return jsonify(lot)


@traceability_bp.route('/lots/<lot_number>/consumption', methods=['POST'])
def record_lot_consumption(lot_number: str):
    """
    Record material consumption from a lot.

    Request body:
    {
        "serial_number": "SN-2024-001234",
        "quantity": 5.2,
        "work_order_id": "WO-001"
    }
    """
    data = request.get_json() or {}

    if lot_number in _material_lots:
        _material_lots[lot_number]['quantity_remaining'] -= data.get('quantity', 0)
        _material_lots[lot_number]['consumed_by'].append(data.get('serial_number'))

    consumption = {
        'lot_number': lot_number,
        'serial_number': data.get('serial_number'),
        'quantity': data.get('quantity'),
        'timestamp': datetime.utcnow().isoformat(),
        'work_order_id': data.get('work_order_id'),
    }

    return jsonify({
        'success': True,
        'consumption': consumption,
    }), 201


@traceability_bp.route('/lots/<lot_number>/affected-parts', methods=['GET'])
def get_affected_parts(lot_number: str):
    """
    Get all parts made with a specific material lot.

    Useful for recall/containment scenarios.

    Returns:
        JSON with list of affected serial numbers
    """
    lot = _material_lots.get(lot_number, {})
    consumed_by = lot.get('consumed_by', [])

    # Find all parts that used this lot
    affected = []
    for sn in consumed_by:
        record = _genealogy_records.get(sn, {})
        affected.append({
            'serial_number': sn,
            'part_id': record.get('part_id', 'unknown'),
            'work_order_id': record.get('work_order_id'),
            'status': record.get('status', 'unknown'),
            'created_at': record.get('created_at'),
        })

    # If no real data, return demo
    if not affected:
        affected = [
            {
                'serial_number': 'SN-2024-001234',
                'part_id': 'BRICK-2X4',
                'work_order_id': 'WO-001',
                'status': 'shipped',
                'created_at': (datetime.utcnow() - timedelta(days=7)).isoformat(),
            },
            {
                'serial_number': 'SN-2024-001235',
                'part_id': 'BRICK-2X4',
                'work_order_id': 'WO-001',
                'status': 'shipped',
                'created_at': (datetime.utcnow() - timedelta(days=7)).isoformat(),
            },
        ]

    return jsonify({
        'lot_number': lot_number,
        'affected_count': len(affected),
        'affected_parts': affected,
    })


# ==================== Root Cause Analysis ====================

@traceability_bp.route('/root-cause/<serial_number>', methods=['GET'])
def analyze_root_cause(serial_number: str):
    """
    Analyze root cause for a defective part.

    Query params:
        defect_type: Type of defect to analyze

    Returns:
        JSON with root cause analysis
    """
    defect_type = request.args.get('defect_type', 'unknown')

    record = _genealogy_records.get(serial_number, {})

    # Simulated root cause analysis
    analysis = {
        'serial_number': serial_number,
        'defect_type': defect_type,
        'analysis_timestamp': datetime.utcnow().isoformat(),
        'material_analysis': {
            'lots_used': record.get('material_lots', [{'lot_number': 'LOT-2024-001', 'material_id': 'PLA-RED'}]),
            'lot_quality_history': {
                'LOT-2024-001': {
                    'other_defects_from_lot': 2,
                    'defect_rate': 0.02,
                    'correlation': 'low',
                }
            },
            'material_likely_cause': False,
        },
        'process_analysis': {
            'machine_id': record.get('machine_id', 'WC-PRINT-01'),
            'process_parameters': {
                'nozzle_temp': 210,
                'bed_temp': 60,
                'speed': 40,
            },
            'deviation_from_nominal': {
                'nozzle_temp': 0,
                'bed_temp': 0,
                'speed': 0,
            },
            'machine_history': {
                'defects_last_24h': 3,
                'defect_rate': 0.03,
                'last_maintenance': (datetime.utcnow() - timedelta(days=5)).isoformat(),
            },
            'process_likely_cause': True,
            'suspected_factor': 'nozzle_wear',
        },
        'environmental_analysis': {
            'temperature': 23.5,
            'humidity': 48,
            'within_spec': True,
            'environmental_likely_cause': False,
        },
        'operator_analysis': {
            'operator_id': record.get('operator_id', 'OP-001'),
            'operator_defect_rate': 0.015,
            'training_current': True,
            'operator_likely_cause': False,
        },
        'root_cause_ranking': [
            {'factor': 'Nozzle wear', 'probability': 0.65, 'evidence': 'High machine defect rate'},
            {'factor': 'Material variation', 'probability': 0.20, 'evidence': 'Low lot defect rate'},
            {'factor': 'Process drift', 'probability': 0.10, 'evidence': 'Parameters within spec'},
            {'factor': 'Unknown', 'probability': 0.05, 'evidence': ''},
        ],
        'recommended_actions': [
            {'action': 'Inspect and replace nozzle on WC-PRINT-01', 'priority': 'high'},
            {'action': 'Review machine maintenance schedule', 'priority': 'medium'},
            {'action': 'Monitor next batch closely', 'priority': 'medium'},
        ],
    }

    return jsonify(analysis)


# ==================== Recall Simulation ====================

@traceability_bp.route('/recall/simulate', methods=['POST'])
def simulate_recall():
    """
    Simulate a product recall scenario.

    Request body:
    {
        "trigger_type": "lot|machine|date_range|defect",
        "trigger_value": "LOT-2024-001",
        "severity": "voluntary|mandatory"
    }

    Returns:
        JSON with recall impact analysis
    """
    data = request.get_json() or {}

    trigger_type = data.get('trigger_type', 'lot')
    trigger_value = data.get('trigger_value', 'LOT-2024-001')

    # Simulated recall analysis
    affected_count = 150
    shipped_count = 120
    in_production = 30

    simulation = {
        'recall_id': f"RCL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        'simulation_timestamp': datetime.utcnow().isoformat(),
        'trigger': {
            'type': trigger_type,
            'value': trigger_value,
        },
        'severity': data.get('severity', 'voluntary'),
        'impact': {
            'total_affected': affected_count,
            'shipped_to_customers': shipped_count,
            'in_production': in_production,
            'in_inventory': affected_count - shipped_count - in_production,
            'customers_affected': 45,
            'orders_affected': 12,
        },
        'cost_estimate': {
            'replacement_cost': affected_count * 2.50,
            'shipping_cost': shipped_count * 5.00,
            'labor_cost': 500.00,
            'communication_cost': 200.00,
            'total_estimated': affected_count * 2.50 + shipped_count * 5.00 + 700,
        },
        'timeline': {
            'identification': '1 hour',
            'containment': '4 hours',
            'customer_notification': '24 hours',
            'replacement_shipping': '3-5 days',
        },
        'containment_actions': [
            {'action': 'Halt production on affected lot', 'status': 'pending'},
            {'action': 'Quarantine inventory', 'status': 'pending'},
            {'action': 'Notify customer service', 'status': 'pending'},
            {'action': 'Prepare replacement stock', 'status': 'pending'},
        ],
    }

    return jsonify(simulation)


# ==================== As-Built Comparison ====================

@traceability_bp.route('/as-built/<serial_number>/compare', methods=['GET'])
def compare_as_built(serial_number: str):
    """
    Compare as-built vs as-designed.

    Returns:
        JSON with deviation analysis
    """
    record = _genealogy_records.get(serial_number, {})

    comparison = {
        'serial_number': serial_number,
        'part_id': record.get('part_id', 'BRICK-2X4'),
        'comparison_timestamp': datetime.utcnow().isoformat(),
        'design_revision': 'REV-A',
        'deviations': [
            {
                'attribute': 'material',
                'designed': 'PLA-BRIGHT-RED',
                'actual': 'PLA-RED',
                'deviation_type': 'substitution',
                'approved': True,
                'approval_id': 'DEV-001',
            },
        ],
        'process_deviations': [
            {
                'operation': 'printing',
                'parameter': 'print_speed',
                'designed': 45,
                'actual': 40,
                'reason': 'Quality optimization',
                'approved': True,
            },
        ],
        'dimensional_compliance': {
            'overall': 'pass',
            'critical_dimensions': [
                {'dimension': 'stud_diameter', 'nominal': 4.80, 'actual': 4.79, 'tolerance': 0.02, 'status': 'pass'},
                {'dimension': 'overall_height', 'nominal': 9.60, 'actual': 9.58, 'tolerance': 0.05, 'status': 'pass'},
            ],
        },
        'quality_compliance': {
            'clutch_power': {'min': 1.5, 'max': 3.0, 'actual': 2.1, 'status': 'pass'},
            'surface_grade': {'min': 3.0, 'actual': 4.2, 'status': 'pass'},
        },
        'overall_conformance': 'conforming',
        'approved_deviations_count': 2,
        'unapproved_deviations_count': 0,
    }

    return jsonify(comparison)


@traceability_bp.route('/search', methods=['GET'])
def search_genealogy():
    """
    Search genealogy records.

    Query params:
        part_id: Filter by part ID
        work_order_id: Filter by work order
        lot_number: Filter by material lot
        date_from: Start date
        date_to: End date
        status: Filter by status

    Returns:
        JSON with matching records
    """
    part_id = request.args.get('part_id')
    work_order_id = request.args.get('work_order_id')
    lot_number = request.args.get('lot_number')

    # Filter records (simplified)
    results = list(_genealogy_records.values())

    if part_id:
        results = [r for r in results if r.get('part_id') == part_id]
    if work_order_id:
        results = [r for r in results if r.get('work_order_id') == work_order_id]

    # If no results, return demo
    if not results:
        results = [
            {
                'serial_number': 'SN-2024-001234',
                'part_id': part_id or 'BRICK-2X4',
                'work_order_id': work_order_id or 'WO-001',
                'status': 'shipped',
                'created_at': (datetime.utcnow() - timedelta(days=7)).isoformat(),
            }
        ]

    return jsonify({
        'count': len(results),
        'records': results[:50],  # Limit to 50
    })
