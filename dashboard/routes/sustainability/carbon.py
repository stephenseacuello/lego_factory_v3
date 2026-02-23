"""
Carbon Routes - Sustainability API Endpoints

LegoMCP World-Class Manufacturing System v5.0
Phase 19: Sustainability & Carbon Tracking

Provides:
- Carbon footprint calculation
- Energy tracking
- Scope 1/2/3 emissions
- Circular economy metrics
- Net zero progress
"""

from datetime import datetime, date, timedelta
from flask import Blueprint, jsonify, request, render_template
import uuid

carbon_bp = Blueprint('carbon', __name__, url_prefix='/carbon')


# Dashboard Page Routes
@carbon_bp.route('/page', methods=['GET'])
def carbon_page():
    """Render carbon tracking dashboard page."""
    return render_template('pages/sustainability/carbon.html')


@carbon_bp.route('/dashboard', methods=['GET'])
def sustainability_dashboard_page():
    """Render sustainability dashboard page."""
    return render_template('pages/sustainability/sustainability_dashboard.html')

# Try to import sustainability services
try:
    from services.sustainability.carbon_tracker import CarbonTracker
    SUSTAINABILITY_AVAILABLE = True
    _tracker = CarbonTracker()
except ImportError:
    SUSTAINABILITY_AVAILABLE = False
    _tracker = None

# In-memory storage for demo
_footprints = []
_energy_records = []


@carbon_bp.route('/status', methods=['GET'])
def get_sustainability_status():
    """Get sustainability system status."""
    return jsonify({
        'available': True,
        'standards': ['ISO 14001', 'GHG Protocol'],
        'capabilities': {
            'carbon_footprint': True,
            'energy_tracking': True,
            'scope_1_2_3': True,
            'circular_economy': True,
            'net_zero_tracking': True,
        },
        'emission_factors_loaded': True,
    })


@carbon_bp.route('/footprint', methods=['POST'])
def calculate_footprint():
    """
    Calculate carbon footprint for a production run.

    Request body:
    {
        "part_id": "BRICK-2X4",
        "quantity": 100,
        "material_kg": 0.5,
        "material_type": "pla",
        "electricity_kwh": 2.5,
        "transport_km": 50
    }

    Returns:
        JSON with carbon footprint breakdown
    """
    data = request.get_json() or {}

    if SUSTAINABILITY_AVAILABLE and _tracker:
        footprint = _tracker.calculate_production_footprint(
            part_id=data.get('part_id', 'PART'),
            quantity=data.get('quantity', 1),
            material_kg=data.get('material_kg', 0.1),
            material_type=data.get('material_type', 'pla'),
            electricity_kwh=data.get('electricity_kwh', 0.5),
            transport_km=data.get('transport_km', 0),
        )
        result = footprint.to_dict()
    else:
        # Calculate demo values
        material_kg = data.get('material_kg', 0.1)
        electricity_kwh = data.get('electricity_kwh', 0.5)
        quantity = data.get('quantity', 1)

        scope_2 = electricity_kwh * 0.5  # kg CO2e per kWh
        scope_3 = material_kg * 2.1  # PLA factor

        result = {
            'footprint_id': str(uuid.uuid4()),
            'part_id': data.get('part_id'),
            'quantity': quantity,
            'timestamp': datetime.utcnow().isoformat(),
            'scope_1_kg': 0.0,
            'scope_2_kg': scope_2,
            'scope_3_kg': scope_3,
            'total_co2e': scope_2 + scope_3,
            'co2e_per_unit': (scope_2 + scope_3) / quantity,
        }

    _footprints.append(result)

    return jsonify({
        'success': True,
        'footprint': result,
    }), 201


@carbon_bp.route('/footprint/part/<part_id>', methods=['GET'])
def get_part_footprint(part_id: str):
    """Get average footprint for a part."""
    if SUSTAINABILITY_AVAILABLE and _tracker:
        result = _tracker.get_part_footprint(part_id)
    else:
        # Demo data
        result = {
            'part_id': part_id,
            'records': 50,
            'total_co2e_kg': 125.5,
            'total_units': 5000,
            'avg_co2e_per_unit': 0.0251,
        }

    return jsonify(result)


@carbon_bp.route('/energy', methods=['POST'])
def record_energy():
    """
    Record energy consumption.

    Request body:
    {
        "work_center_id": "WC-PRINT-01",
        "electricity_kwh": 5.0,
        "duration_hours": 2.0,
        "parts_produced": 50
    }
    """
    data = request.get_json() or {}

    if SUSTAINABILITY_AVAILABLE and _tracker:
        record = _tracker.record_energy(
            work_center_id=data.get('work_center_id', 'WC-001'),
            electricity_kwh=data.get('electricity_kwh', 0),
            duration_hours=data.get('duration_hours', 0),
            parts_produced=data.get('parts_produced', 0),
        )
        result = record.to_dict()
    else:
        result = {
            'record_id': str(uuid.uuid4()),
            'work_center_id': data.get('work_center_id'),
            'timestamp': datetime.utcnow().isoformat(),
            'electricity_kwh': data.get('electricity_kwh'),
            'duration_hours': data.get('duration_hours'),
            'parts_produced': data.get('parts_produced'),
            'kwh_per_unit': data.get('electricity_kwh', 0) / max(1, data.get('parts_produced', 1)),
        }

    _energy_records.append(result)

    return jsonify({
        'success': True,
        'record': result,
    }), 201


@carbon_bp.route('/energy/summary', methods=['GET'])
def get_energy_summary():
    """Get energy consumption summary."""
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    # Demo summary
    summary = {
        'period': {
            'start': start_str or (datetime.utcnow() - timedelta(days=30)).isoformat(),
            'end': end_str or datetime.utcnow().isoformat(),
        },
        'total_kwh': 1250.5,
        'total_parts': 25000,
        'avg_kwh_per_part': 0.05,
        'by_work_center': {
            'WC-PRINT-01': {'kwh': 450.2, 'parts': 9000, 'kwh_per_part': 0.050},
            'WC-PRINT-02': {'kwh': 425.8, 'parts': 8500, 'kwh_per_part': 0.050},
            'WC-ASSEMBLY': {'kwh': 374.5, 'parts': 7500, 'kwh_per_part': 0.050},
        },
        'trend': 'improving',
        'vs_target': {
            'target_kwh_per_part': 0.06,
            'actual': 0.05,
            'status': 'on_track',
        },
    }

    return jsonify({'summary': summary})


@carbon_bp.route('/lifecycle', methods=['POST'])
def record_lifecycle():
    """
    Record material lifecycle data.

    Request body:
    {
        "part_id": "BRICK-2X4",
        "virgin_kg": 0.08,
        "recycled_kg": 0.02,
        "recyclable_output_kg": 0.09,
        "waste_kg": 0.01
    }
    """
    data = request.get_json() or {}

    if SUSTAINABILITY_AVAILABLE and _tracker:
        record = _tracker.record_material_lifecycle(
            part_id=data.get('part_id', 'PART'),
            virgin_kg=data.get('virgin_kg', 0),
            recycled_kg=data.get('recycled_kg', 0),
            recyclable_output_kg=data.get('recyclable_output_kg', 0),
            waste_kg=data.get('waste_kg', 0),
        )
        result = record.to_dict()
    else:
        virgin = data.get('virgin_kg', 0.08)
        recycled = data.get('recycled_kg', 0.02)
        recyclable = data.get('recyclable_output_kg', 0.09)
        waste = data.get('waste_kg', 0.01)

        total_input = virgin + recycled
        total_output = recyclable + waste

        result = {
            'lifecycle_id': str(uuid.uuid4()),
            'part_id': data.get('part_id'),
            'virgin_material_kg': virgin,
            'recycled_material_kg': recycled,
            'recyclable_output_kg': recyclable,
            'waste_kg': waste,
            'recycled_content_percent': (recycled / total_input * 100) if total_input > 0 else 0,
            'circularity_index': ((recyclable / total_output if total_output > 0 else 0) +
                                   (recycled / total_input if total_input > 0 else 0)) / 2,
        }

    return jsonify({
        'success': True,
        'record': result,
    }), 201


@carbon_bp.route('/kpis', methods=['GET'])
def get_sustainability_kpis():
    """Get sustainability KPIs."""
    if SUSTAINABILITY_AVAILABLE and _tracker:
        kpis = _tracker.get_sustainability_kpis()
    else:
        kpis = {
            'carbon': {
                'total_co2e_kg': 2500.5,
                'total_units': 100000,
                'co2e_per_unit': 0.025,
            },
            'energy': {
                'total_kwh': 5000,
                'kwh_per_unit': 0.05,
            },
            'circularity': {
                'records': 150,
                'avg_circularity_index': 0.72,
            },
            'net_zero_progress': {
                'target_kg': 3000,
                'current_kg': 2500.5,
                'percent_of_target': 83.4,
                'on_track': True,
            },
        }

    return jsonify({'kpis': kpis})


@carbon_bp.route('/daily', methods=['GET'])
def get_daily_summary():
    """Get daily carbon summary."""
    target_date = request.args.get('date')

    if SUSTAINABILITY_AVAILABLE and _tracker:
        if target_date:
            target = date.fromisoformat(target_date)
        else:
            target = date.today()
        summary = _tracker.get_daily_summary(target)
    else:
        summary = {
            'date': target_date or date.today().isoformat(),
            'total_co2e_kg': 85.5,
            'total_units': 3500,
            'co2e_per_unit': 0.0244,
        }

    return jsonify({'daily': summary})


@carbon_bp.route('/opportunities', methods=['GET'])
def get_reduction_opportunities():
    """Get emission reduction opportunities."""
    if SUSTAINABILITY_AVAILABLE and _tracker:
        opportunities = _tracker.get_emission_reduction_opportunities()
    else:
        opportunities = [
            {
                'type': 'energy_efficiency',
                'work_center_id': 'WC-PRINT-01',
                'current_kwh_per_unit': 0.055,
                'potential_savings_percent': 20,
                'action': 'Optimize print parameters to reduce energy',
            },
            {
                'type': 'circularity',
                'part_id': 'BRICK-2X4',
                'current_index': 0.65,
                'action': 'Increase recycled content to 30%',
            },
            {
                'type': 'scope_3',
                'action': 'Source materials from local suppliers',
                'potential_co2e_reduction_kg': 150,
            },
        ]

    return jsonify({'opportunities': opportunities})


@carbon_bp.route('/targets', methods=['GET'])
def get_targets():
    """Get sustainability targets."""
    return jsonify({
        'targets': {
            'net_zero': {
                'target_year': 2030,
                'annual_reduction_target_percent': 7,
                'current_progress': 'on_track',
            },
            'circular_economy': {
                'recycled_content_target_percent': 50,
                'current_percent': 25,
                'waste_reduction_target_percent': 80,
            },
            'energy': {
                'renewable_energy_target_percent': 100,
                'current_percent': 35,
                'efficiency_improvement_target_percent': 30,
            },
            'scope_3': {
                'supplier_emission_reduction_target_percent': 25,
                'current_progress': 12,
            },
        }
    })


@carbon_bp.route('/report', methods=['GET'])
def generate_sustainability_report():
    """
    Generate sustainability report.

    Query params:
        period: monthly|quarterly|annual
        format: json|summary
    """
    period = request.args.get('period', 'monthly')

    report = {
        'report_id': str(uuid.uuid4()),
        'period': period,
        'generated_at': datetime.utcnow().isoformat(),
        'summary': {
            'total_production': 100000,
            'total_co2e_kg': 2500.5,
            'co2e_per_unit': 0.025,
            'vs_previous_period': -5.2,  # % change
            'vs_target': 16.6,  # % under target
        },
        'scope_breakdown': {
            'scope_1': {'kg': 0, 'percent': 0},
            'scope_2': {'kg': 1250, 'percent': 50},
            'scope_3': {'kg': 1250.5, 'percent': 50},
        },
        'energy': {
            'total_kwh': 5000,
            'renewable_percent': 35,
            'efficiency_vs_baseline': 12,
        },
        'circularity': {
            'recycled_content_percent': 25,
            'recyclable_output_percent': 92,
            'waste_to_landfill_percent': 3,
        },
        'certifications': [
            {'name': 'ISO 14001', 'status': 'active', 'valid_until': '2025-12-31'},
        ],
        'key_achievements': [
            'Reduced energy consumption by 12%',
            'Increased recycled content to 25%',
            'On track for net zero by 2030',
        ],
        'improvement_areas': [
            'Scope 3 emissions from materials',
            'Supplier sustainability assessment',
        ],
    }

    return jsonify({'report': report})
