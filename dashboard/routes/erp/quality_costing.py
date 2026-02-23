"""
Quality Costing Routes - Cost of Quality API Endpoints

LegoMCP World-Class Manufacturing System v5.0
Phase 16: Quality Costing

Provides:
- Cost of Quality (COQ) recording and analysis
- Activity-Based Costing for quality activities
- Pareto analysis and improvement opportunities
- Quality ROI calculation
"""

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

quality_costing_bp = Blueprint('quality_costing', __name__, url_prefix='/quality-costing')

# Import services
try:
    from services.erp import (
        get_quality_cost_service,
        get_abc_service,
        CostElement,
        CostCategory,
        ActivityType,
        CostDriver,
    )
    QUALITY_COSTING_AVAILABLE = True
except ImportError:
    QUALITY_COSTING_AVAILABLE = False


def _parse_date(date_str: str) -> datetime:
    """Parse ISO date string."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        return datetime.strptime(date_str[:10], '%Y-%m-%d')


# ==================== Cost of Quality Endpoints ====================

@quality_costing_bp.route('/coq/record', methods=['POST'])
def record_quality_cost():
    """
    Record a quality cost.

    Request body:
    {
        "element": "scrap|rework|inspection|testing|training|...",
        "amount": 150.00,
        "description": "Scrap from print defect",
        "work_order_id": "WO-001",
        "part_id": "BRICK-2X4",
        "quantity": 10
    }

    Returns:
        JSON with created cost entry
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'error': 'Quality costing services not available',
            'available': False
        }), 400

    data = request.get_json() or {}

    element_str = data.get('element', 'scrap')
    try:
        element = CostElement(element_str.lower())
    except ValueError:
        return jsonify({
            'error': f"Invalid cost element: {element_str}",
            'valid_elements': [e.value for e in CostElement]
        }), 400

    service = get_quality_cost_service()

    entry = service.record_cost(
        element=element,
        amount=float(data.get('amount', 0)),
        description=data.get('description', ''),
        work_order_id=data.get('work_order_id'),
        part_id=data.get('part_id'),
        defect_id=data.get('defect_id'),
        quantity=float(data.get('quantity', 1)),
        recorded_by=data.get('recorded_by'),
        cost_center=data.get('cost_center'),
    )

    return jsonify({
        'success': True,
        'entry': {
            'entry_id': entry.entry_id,
            'category': entry.category.value,
            'element': entry.element.value,
            'amount': float(entry.amount),
            'description': entry.description,
            'timestamp': entry.timestamp.isoformat(),
        }
    }), 201


@quality_costing_bp.route('/coq/scrap', methods=['POST'])
def record_scrap():
    """
    Record scrap cost.

    Request body:
    {
        "work_order_id": "WO-001",
        "part_id": "BRICK-2X4",
        "quantity": 10,
        "unit_cost": 0.50,
        "reason": "Layer adhesion failure"
    }
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({'error': 'Service not available'}), 400

    data = request.get_json() or {}
    service = get_quality_cost_service()

    entry = service.record_scrap_cost(
        work_order_id=data.get('work_order_id', 'unknown'),
        part_id=data.get('part_id', 'unknown'),
        quantity=int(data.get('quantity', 1)),
        unit_cost=float(data.get('unit_cost', 0)),
        reason=data.get('reason', 'unspecified'),
        defect_id=data.get('defect_id'),
    )

    return jsonify({
        'success': True,
        'entry_id': entry.entry_id,
        'total_cost': float(entry.amount),
    }), 201


@quality_costing_bp.route('/coq/rework', methods=['POST'])
def record_rework():
    """
    Record rework cost.

    Request body:
    {
        "work_order_id": "WO-001",
        "part_id": "BRICK-2X4",
        "labor_hours": 2.5,
        "labor_rate": 25.00,
        "material_cost": 5.00,
        "reason": "Stud dimension correction"
    }
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({'error': 'Service not available'}), 400

    data = request.get_json() or {}
    service = get_quality_cost_service()

    entry = service.record_rework_cost(
        work_order_id=data.get('work_order_id', 'unknown'),
        part_id=data.get('part_id', 'unknown'),
        labor_hours=float(data.get('labor_hours', 0)),
        labor_rate=float(data.get('labor_rate', 25.0)),
        material_cost=float(data.get('material_cost', 0)),
        reason=data.get('reason', 'unspecified'),
    )

    return jsonify({
        'success': True,
        'entry_id': entry.entry_id,
        'total_cost': float(entry.amount),
    }), 201


@quality_costing_bp.route('/coq/inspection', methods=['POST'])
def record_inspection():
    """
    Record inspection cost.

    Request body:
    {
        "work_order_id": "WO-001",
        "inspector_hours": 1.0,
        "inspector_rate": 30.00,
        "equipment_cost": 5.00,
        "inspection_type": "final"
    }
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({'error': 'Service not available'}), 400

    data = request.get_json() or {}
    service = get_quality_cost_service()

    entry = service.record_inspection_cost(
        work_order_id=data.get('work_order_id'),
        inspector_hours=float(data.get('inspector_hours', 0)),
        inspector_rate=float(data.get('inspector_rate', 30.0)),
        equipment_cost=float(data.get('equipment_cost', 0)),
        inspection_type=data.get('inspection_type', 'standard'),
    )

    return jsonify({
        'success': True,
        'entry_id': entry.entry_id,
        'total_cost': float(entry.amount),
    }), 201


@quality_costing_bp.route('/coq/summary', methods=['GET'])
def get_coq_summary():
    """
    Get Cost of Quality summary.

    Query params:
        start_date: Period start (ISO date)
        end_date: Period end (ISO date)
        revenue: Revenue for COQ % calculation

    Returns:
        JSON with COQ summary by category
    """
    if not QUALITY_COSTING_AVAILABLE:
        # Return demo data
        return jsonify({
            'summary': {
                'prevention_costs': 5000.00,
                'appraisal_costs': 8000.00,
                'internal_failure_costs': 12000.00,
                'external_failure_costs': 3000.00,
                'total_coq': 28000.00,
                'coq_percentage': 5.6,
                'conformance_cost': 13000.00,
                'nonconformance_cost': 15000.00,
                'ratio': 0.87,
            },
            'demo': True
        })

    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    revenue = request.args.get('revenue', type=float)

    # Default to last 30 days
    end_date = _parse_date(end_str) if end_str else datetime.utcnow()
    start_date = _parse_date(start_str) if start_str else (end_date - timedelta(days=30))

    service = get_quality_cost_service()
    summary = service.get_period_summary(start_date, end_date, revenue)

    return jsonify({
        'summary': {
            'period_start': summary.period_start.isoformat(),
            'period_end': summary.period_end.isoformat(),
            'prevention_costs': float(summary.prevention_costs),
            'appraisal_costs': float(summary.appraisal_costs),
            'internal_failure_costs': float(summary.internal_failure_costs),
            'external_failure_costs': float(summary.external_failure_costs),
            'total_coq': float(summary.total_coq),
            'revenue': float(summary.revenue),
            'coq_percentage': summary.coq_percentage,
            'conformance_cost': float(summary.conformance_cost),
            'nonconformance_cost': float(summary.nonconformance_cost),
            'ratio': summary.ratio if summary.ratio != float('inf') else None,
        }
    })


@quality_costing_bp.route('/coq/breakdown', methods=['GET'])
def get_coq_breakdown():
    """
    Get detailed COQ breakdown by element.

    Query params:
        start_date: Period start
        end_date: Period end

    Returns:
        JSON with cost breakdown by element
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'breakdown': {
                'scrap': {'category': 'internal_failure', 'count': 45, 'total_cost': 6750.00},
                'rework': {'category': 'internal_failure', 'count': 23, 'total_cost': 4600.00},
                'inspection': {'category': 'appraisal', 'count': 120, 'total_cost': 6000.00},
                'testing': {'category': 'appraisal', 'count': 80, 'total_cost': 2000.00},
                'training': {'category': 'prevention', 'count': 5, 'total_cost': 3000.00},
            },
            'demo': True
        })

    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    end_date = _parse_date(end_str) if end_str else datetime.utcnow()
    start_date = _parse_date(start_str) if start_str else (end_date - timedelta(days=30))

    service = get_quality_cost_service()
    breakdown = service.get_element_breakdown(start_date, end_date)

    return jsonify({'breakdown': breakdown})


@quality_costing_bp.route('/coq/trend', methods=['GET'])
def get_coq_trend():
    """
    Get monthly COQ trend.

    Query params:
        months: Number of months (default 12)

    Returns:
        JSON with monthly COQ trend data
    """
    if not QUALITY_COSTING_AVAILABLE:
        # Return demo trend
        return jsonify({
            'trend': [
                {'period': '2024-07', 'total_coq': 25000, 'coq_percentage': 5.0},
                {'period': '2024-08', 'total_coq': 27000, 'coq_percentage': 5.4},
                {'period': '2024-09', 'total_coq': 24000, 'coq_percentage': 4.8},
                {'period': '2024-10', 'total_coq': 28000, 'coq_percentage': 5.6},
            ],
            'demo': True
        })

    months = request.args.get('months', 12, type=int)
    service = get_quality_cost_service()
    trend = service.get_trend(months)

    return jsonify({'trend': trend})


@quality_costing_bp.route('/coq/pareto', methods=['GET'])
def get_coq_pareto():
    """
    Get Pareto analysis of quality costs.

    Query params:
        start_date: Period start
        end_date: Period end
        by: Group by 'element', 'part_id', or 'defect_id'

    Returns:
        JSON with Pareto analysis
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'pareto': {
                'items': [
                    {'name': 'scrap', 'cost': 6750, 'percentage': 24.1, 'cumulative_percentage': 24.1},
                    {'name': 'inspection', 'cost': 6000, 'percentage': 21.4, 'cumulative_percentage': 45.5},
                    {'name': 'rework', 'cost': 4600, 'percentage': 16.4, 'cumulative_percentage': 61.9},
                ],
                'vital_few': ['scrap', 'inspection', 'rework'],
            },
            'demo': True
        })

    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    by = request.args.get('by', 'element')

    end_date = _parse_date(end_str) if end_str else datetime.utcnow()
    start_date = _parse_date(start_str) if start_str else (end_date - timedelta(days=90))

    service = get_quality_cost_service()
    pareto = service.get_pareto_analysis(start_date, end_date, by)

    return jsonify({'pareto': pareto})


@quality_costing_bp.route('/coq/opportunities', methods=['GET'])
def get_improvement_opportunities():
    """
    Get quality improvement opportunities.

    Returns:
        JSON with prioritized improvement opportunities
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'opportunities': [
                {
                    'priority': 'high',
                    'area': 'Prevention Investment',
                    'finding': 'Prevention costs are only 18% of total COQ',
                    'recommendation': 'Increase investment in training and FMEA',
                    'potential_savings': 3000.00,
                },
                {
                    'priority': 'medium',
                    'area': 'Scrap Reduction',
                    'finding': 'High scrap costs: $6750/month',
                    'recommendation': 'Implement root cause analysis program',
                    'potential_savings': 2000.00,
                }
            ],
            'demo': True
        })

    service = get_quality_cost_service()
    opportunities = service.get_improvement_opportunities()

    return jsonify({'opportunities': opportunities})


@quality_costing_bp.route('/coq/roi', methods=['POST'])
def calculate_quality_roi():
    """
    Calculate ROI for quality improvement investment.

    Request body:
    {
        "prevention_investment": 10000,
        "expected_failure_reduction": 0.25
    }

    Returns:
        JSON with ROI analysis
    """
    if not QUALITY_COSTING_AVAILABLE:
        data = request.get_json() or {}
        investment = float(data.get('prevention_investment', 10000))
        return jsonify({
            'roi_analysis': {
                'investment': investment,
                'expected_annual_savings': investment * 1.5,
                'roi_percentage': 50.0,
                'payback_months': 8,
                'recommendation': 'Invest',
            },
            'demo': True
        })

    data = request.get_json() or {}
    service = get_quality_cost_service()

    roi = service.calculate_quality_roi(
        prevention_investment=float(data.get('prevention_investment', 0)),
        expected_failure_reduction=float(data.get('expected_failure_reduction', 0.20)),
    )

    return jsonify({'roi_analysis': roi})


# ==================== Activity-Based Costing Endpoints ====================

@quality_costing_bp.route('/abc/activities', methods=['GET'])
def list_activities():
    """
    List all defined activities.

    Returns:
        JSON with activity list
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'activities': [
                {'activity_id': 'ACT-PRINT', 'name': '3D Printing', 'rate': 25.00},
                {'activity_id': 'ACT-INSPECT', 'name': 'Quality Inspection', 'rate': 4.00},
            ],
            'demo': True
        })

    service = get_abc_service()
    activities = service.get_all_activities()

    return jsonify({
        'activities': [
            {
                'activity_id': a.activity_id,
                'name': a.name,
                'type': a.activity_type.value,
                'cost_driver': a.cost_driver.value,
                'cost_pool': float(a.cost_pool),
                'driver_quantity': a.driver_quantity,
                'rate': float(a.rate),
                'is_quality_activity': a.is_quality_activity,
            }
            for a in activities
        ]
    })


@quality_costing_bp.route('/abc/activities', methods=['POST'])
def define_activity():
    """
    Define a new activity.

    Request body:
    {
        "name": "CMM Measurement",
        "activity_type": "inspection",
        "cost_driver": "inspections",
        "cost_pool": 2000,
        "driver_quantity": 100,
        "is_quality_activity": true
    }
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({'error': 'Service not available'}), 400

    data = request.get_json() or {}

    try:
        activity_type = ActivityType(data.get('activity_type', 'inspection'))
        cost_driver = CostDriver(data.get('cost_driver', 'inspections'))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    service = get_abc_service()

    activity = service.define_activity(
        name=data.get('name', 'New Activity'),
        activity_type=activity_type,
        cost_driver=cost_driver,
        cost_pool=float(data.get('cost_pool', 0)),
        driver_quantity=float(data.get('driver_quantity', 1)),
        description=data.get('description', ''),
        is_quality_activity=data.get('is_quality_activity', False),
    )

    return jsonify({
        'success': True,
        'activity': {
            'activity_id': activity.activity_id,
            'name': activity.name,
            'rate': float(activity.rate),
        }
    }), 201


@quality_costing_bp.route('/abc/consumption', methods=['POST'])
def record_activity_consumption():
    """
    Record activity consumption.

    Request body:
    {
        "activity_id": "ACT-INSPECT",
        "driver_quantity": 5,
        "part_id": "BRICK-2X4",
        "work_order_id": "WO-001"
    }
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({'error': 'Service not available'}), 400

    data = request.get_json() or {}
    service = get_abc_service()

    try:
        consumption = service.record_consumption(
            activity_id=data.get('activity_id'),
            driver_quantity=float(data.get('driver_quantity', 1)),
            part_id=data.get('part_id'),
            work_order_id=data.get('work_order_id'),
        )

        return jsonify({
            'success': True,
            'consumption': {
                'consumption_id': consumption.consumption_id,
                'activity_id': consumption.activity_id,
                'driver_quantity': consumption.driver_quantity,
                'calculated_cost': float(consumption.calculated_cost),
            }
        }), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@quality_costing_bp.route('/abc/part-cost/<part_id>', methods=['GET'])
def get_part_abc_cost(part_id: str):
    """
    Get ABC-calculated part cost.

    Query params:
        direct_materials: Direct material cost
        direct_labor: Direct labor cost

    Returns:
        JSON with full product cost breakdown
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'part_id': part_id,
            'direct_materials': 0.25,
            'direct_labor': 0.10,
            'activity_costs': {'ACT-PRINT': 0.50, 'ACT-INSPECT': 0.08},
            'total_cost': 0.93,
            'demo': True
        })

    direct_materials = request.args.get('direct_materials', 0, type=float)
    direct_labor = request.args.get('direct_labor', 0, type=float)

    service = get_abc_service()
    cost = service.calculate_part_cost(
        part_id=part_id,
        direct_materials=direct_materials,
        direct_labor=direct_labor,
    )

    return jsonify({
        'part_id': cost.part_id,
        'direct_materials': float(cost.direct_materials),
        'direct_labor': float(cost.direct_labor),
        'activity_costs': {k: float(v) for k, v in cost.activity_costs.items()},
        'total_cost': float(cost.total_cost),
        'breakdown': cost.cost_breakdown,
    })


@quality_costing_bp.route('/abc/work-order-cost/<work_order_id>', methods=['GET'])
def get_work_order_abc_cost(work_order_id: str):
    """
    Get ABC-calculated work order cost.

    Query params:
        direct_materials: Direct material cost
        direct_labor: Direct labor cost

    Returns:
        JSON with work order cost breakdown
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'work_order_id': work_order_id,
            'total_cost': 125.50,
            'quality_activity_cost': 15.00,
            'quality_cost_percentage': 12.0,
            'demo': True
        })

    direct_materials = request.args.get('direct_materials', 0, type=float)
    direct_labor = request.args.get('direct_labor', 0, type=float)

    service = get_abc_service()
    cost = service.calculate_work_order_cost(
        work_order_id=work_order_id,
        direct_materials=direct_materials,
        direct_labor=direct_labor,
    )

    return jsonify(cost)


@quality_costing_bp.route('/abc/summary', methods=['GET'])
def get_abc_summary():
    """
    Get activity consumption summary.

    Query params:
        start_date: Period start
        end_date: Period end

    Returns:
        JSON with activity summary
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'summary': {
                'total_cost': 15000.00,
                'quality_cost': 3500.00,
                'activities': {}
            },
            'demo': True
        })

    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    end_date = _parse_date(end_str) if end_str else datetime.utcnow()
    start_date = _parse_date(start_str) if start_str else (end_date - timedelta(days=30))

    service = get_abc_service()
    summary = service.get_activity_summary(start_date, end_date)

    return jsonify({'summary': summary})


@quality_costing_bp.route('/abc/opportunities', methods=['GET'])
def get_abc_opportunities():
    """
    Get cost reduction opportunities from activity analysis.

    Returns:
        JSON with prioritized opportunities
    """
    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'opportunities': [
                {
                    'priority': 'medium',
                    'activity': 'Machine Setup',
                    'finding': 'High setup costs: $750/month',
                    'recommendation': 'Consider batch consolidation or SMED',
                    'potential_savings': 150.00,
                }
            ],
            'demo': True
        })

    service = get_abc_service()
    opportunities = service.identify_cost_reduction_opportunities()

    return jsonify({'opportunities': opportunities})


@quality_costing_bp.route('/abc/pricing/<part_id>', methods=['GET'])
def get_pricing_data(part_id: str):
    """
    Get activity-based pricing data for a part.

    Query params:
        quantity: Order quantity

    Returns:
        JSON with pricing data
    """
    if not QUALITY_COSTING_AVAILABLE:
        quantity = request.args.get('quantity', 1, type=int)
        return jsonify({
            'part_id': part_id,
            'unit_activity_cost': 0.65,
            'quantity': quantity,
            'total_activity_cost': 0.65 * quantity,
            'demo': True
        })

    quantity = request.args.get('quantity', 1, type=int)

    service = get_abc_service()
    pricing = service.calculate_activity_rates_for_pricing(part_id, quantity)

    return jsonify(pricing)


# ==================== Combined Endpoints ====================

@quality_costing_bp.route('/dashboard', methods=['GET'])
def get_costing_dashboard():
    """
    Get combined quality costing dashboard data.

    Returns:
        JSON with COQ summary, ABC highlights, and recommendations
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    if not QUALITY_COSTING_AVAILABLE:
        return jsonify({
            'coq': {
                'total': 28000,
                'percentage': 5.6,
                'conformance_ratio': 0.87,
            },
            'abc': {
                'total_overhead': 15000,
                'quality_percentage': 23.3,
            },
            'top_opportunities': [
                {'area': 'Prevention Investment', 'savings': 3000},
                {'area': 'Scrap Reduction', 'savings': 2000},
            ],
            'demo': True
        })

    coq_service = get_quality_cost_service()
    abc_service = get_abc_service()

    coq_summary = coq_service.get_period_summary(start_date, end_date)
    abc_summary = abc_service.get_activity_summary(start_date, end_date)
    opportunities = coq_service.get_improvement_opportunities()[:3]

    return jsonify({
        'coq': {
            'total': float(coq_summary.total_coq),
            'percentage': coq_summary.coq_percentage,
            'conformance_ratio': coq_summary.ratio if coq_summary.ratio != float('inf') else None,
            'prevention': float(coq_summary.prevention_costs),
            'appraisal': float(coq_summary.appraisal_costs),
            'internal_failure': float(coq_summary.internal_failure_costs),
            'external_failure': float(coq_summary.external_failure_costs),
        },
        'abc': {
            'total_overhead': abc_summary.get('total_cost', 0),
            'quality_cost': abc_summary.get('quality_cost', 0),
            'quality_percentage': (
                abc_summary.get('quality_cost', 0) / abc_summary.get('total_cost', 1) * 100
                if abc_summary.get('total_cost') else 0
            ),
        },
        'top_opportunities': [
            {'area': o['area'], 'savings': o['potential_savings']}
            for o in opportunities
        ],
    })
