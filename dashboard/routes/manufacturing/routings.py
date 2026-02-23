"""
Alternative Routing Routes - Routing Selection API

LegoMCP World-Class Manufacturing System v5.0
Phase 9: Alternative Routings & Enhanced BOM

ISA-95 Level 3 Manufacturing Routing Operations:
- Multi-criteria routing selection
- Alternative routing comparison
- Context-aware optimization (rush, cost, quality, green)
- Routing templates management
"""

from datetime import date
from flask import Blueprint, jsonify, request

routings_bp = Blueprint('routings', __name__, url_prefix='/routings')

# Try to import routing services
try:
    from services.manufacturing.routing_selector import (
        RoutingSelector,
        SelectionRequest,
        SelectionContext,
    )
    from services.manufacturing.routing_service import (
        RoutingService,
        ROUTING_TEMPLATES,
    )
    ROUTING_SERVICES_AVAILABLE = True
except ImportError:
    ROUTING_SERVICES_AVAILABLE = False
    ROUTING_TEMPLATES = {}

# Global selector instance
_routing_selector = None


def _get_selector():
    """Get or create routing selector."""
    global _routing_selector
    if _routing_selector is None and ROUTING_SERVICES_AVAILABLE:
        _routing_selector = RoutingSelector()
        # Initialize with demo routing data
        _initialize_demo_routings()
    return _routing_selector


def _initialize_demo_routings():
    """Initialize demo routing data for selection."""
    global _routing_selector
    if not _routing_selector:
        return

    # Add demo routings for BRICK-2X4
    demo_routings = [
        {
            'routing_id': 'RT-2X4-FDM-STD',
            'part_id': 'BRICK-2X4',
            'name': 'FDM Standard',
            'cost_per_unit': 0.45,
            'time_per_unit_min': 45,
            'risk_score': 10,
            'energy_kwh': 0.15,
            'yield_percent': 98.5,
            'work_centers': ['WC-PRINT-01', 'WC-PRINT-02'],
        },
        {
            'routing_id': 'RT-2X4-FDM-FAST',
            'part_id': 'BRICK-2X4',
            'name': 'FDM Fast (Lower Quality)',
            'cost_per_unit': 0.35,
            'time_per_unit_min': 25,
            'risk_score': 25,
            'energy_kwh': 0.12,
            'yield_percent': 96.0,
            'work_centers': ['WC-PRINT-01', 'WC-PRINT-02'],
        },
        {
            'routing_id': 'RT-2X4-FDM-HQ',
            'part_id': 'BRICK-2X4',
            'name': 'FDM High Quality',
            'cost_per_unit': 0.65,
            'time_per_unit_min': 75,
            'risk_score': 5,
            'energy_kwh': 0.22,
            'yield_percent': 99.5,
            'work_centers': ['WC-PRINT-01'],
        },
        {
            'routing_id': 'RT-2X4-SLA',
            'part_id': 'BRICK-2X4',
            'name': 'SLA Resin (Premium)',
            'cost_per_unit': 1.25,
            'time_per_unit_min': 60,
            'risk_score': 3,
            'energy_kwh': 0.18,
            'yield_percent': 99.8,
            'work_centers': ['WC-SLA-01'],
        },
    ]

    for r in demo_routings:
        _routing_selector.add_routing(
            routing_id=r['routing_id'],
            part_id=r['part_id'],
            name=r['name'],
            cost_per_unit=r['cost_per_unit'],
            time_per_unit_min=r['time_per_unit_min'],
            risk_score=r['risk_score'],
            energy_kwh=r['energy_kwh'],
            yield_percent=r['yield_percent'],
            work_centers=r['work_centers'],
        )

    # Add routings for other parts
    for part_id in ['BRICK-2X2', 'PLATE-4X8', 'TECHNIC-BEAM']:
        for variant in ['STD', 'FAST', 'HQ']:
            modifier = {'STD': 1.0, 'FAST': 0.8, 'HQ': 1.5}[variant]
            _routing_selector.add_routing(
                routing_id=f'RT-{part_id}-{variant}',
                part_id=part_id,
                name=f'{part_id} {variant}',
                cost_per_unit=0.40 * modifier,
                time_per_unit_min=40 * modifier,
                risk_score=10 if variant == 'STD' else (25 if variant == 'FAST' else 5),
                energy_kwh=0.15 * modifier,
                yield_percent=98.5 if variant == 'STD' else (96.0 if variant == 'FAST' else 99.5),
                work_centers=['WC-PRINT-01', 'WC-PRINT-02'],
            )


@routings_bp.route('/<part_id>', methods=['GET'])
def get_routings(part_id: str):
    """
    Get all available routings for a part.

    Returns:
        JSON with list of alternative routings
    """
    if not ROUTING_SERVICES_AVAILABLE:
        return jsonify({
            'part_id': part_id,
            'routings': [],
            'count': 0,
            'message': 'Routing services not available',
        })

    selector = _get_selector()
    candidates = selector._get_candidates(part_id)

    return jsonify({
        'part_id': part_id,
        'routings': candidates,
        'count': len(candidates),
    })


@routings_bp.route('/select', methods=['POST'])
def select_routing():
    """
    Select optimal routing based on criteria.

    Request body:
    {
        "part_id": "BRICK-2X4",
        "quantity": 100,
        "context": "normal" | "rush" | "high_quality" | "low_cost" | "green",
        "due_date": "2024-03-15",
        "priority": "A" | "B" | "C",
        "quality_level": "standard" | "premium" | "certified",
        "max_cost": 100.0,
        "max_time_hours": 8.0,
        "weights": {
            "cost": 0.3,
            "time": 0.25,
            "quality": 0.25,
            "energy": 0.1,
            "capacity": 0.1
        }
    }

    Returns:
        JSON with selected routing and alternatives
    """
    data = request.get_json() or {}

    if not ROUTING_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Routing services not available',
            'available': False,
        }), 503

    selector = _get_selector()

    # Parse due date
    due_date = None
    if data.get('due_date'):
        try:
            due_date = date.fromisoformat(data['due_date'])
        except ValueError:
            pass

    # Parse context
    context_str = data.get('context', 'normal').upper()
    try:
        context = SelectionContext[context_str]
    except KeyError:
        context = SelectionContext.NORMAL

    # Build request
    selection_request = SelectionRequest(
        part_id=data.get('part_id', ''),
        quantity=int(data.get('quantity', 1)),
        due_date=due_date,
        context=context,
        priority=data.get('priority', 'B'),
        quality_level=data.get('quality_level', 'standard'),
        weights=data.get('weights', {}),
        max_cost=data.get('max_cost'),
        max_time_hours=data.get('max_time_hours'),
        required_work_centers=data.get('required_work_centers', []),
        excluded_work_centers=data.get('excluded_work_centers', []),
    )

    result = selector.select_routing(selection_request)

    return jsonify({
        'selection': result.to_dict(),
        'request': {
            'part_id': selection_request.part_id,
            'quantity': selection_request.quantity,
            'context': selection_request.context.value,
        },
    })


@routings_bp.route('/compare', methods=['POST'])
def compare_routings():
    """
    Compare all available routings for a part.

    Request body:
    {
        "part_id": "BRICK-2X4",
        "quantity": 100
    }

    Returns:
        JSON with side-by-side comparison of all routings
    """
    data = request.get_json() or {}

    if not ROUTING_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Routing services not available',
        }), 503

    selector = _get_selector()

    part_id = data.get('part_id', '')
    quantity = int(data.get('quantity', 1))

    comparison = selector.compare_routings(part_id, quantity)

    return jsonify(comparison)


@routings_bp.route('/contexts', methods=['GET'])
def get_selection_contexts():
    """
    Get available selection contexts and their weight profiles.

    Returns:
        JSON with context options and default weights
    """
    if not ROUTING_SERVICES_AVAILABLE:
        contexts = {
            'normal': {'description': 'Balanced optimization'},
            'rush': {'description': 'Prioritize speed'},
            'high_quality': {'description': 'Prioritize quality'},
            'low_cost': {'description': 'Prioritize cost savings'},
            'green': {'description': 'Prioritize energy efficiency'},
        }
        return jsonify({
            'contexts': contexts,
            'weights': {},
        })

    selector = _get_selector()

    contexts = {}
    for ctx in SelectionContext:
        contexts[ctx.value] = {
            'description': {
                'normal': 'Balanced optimization across all criteria',
                'rush': 'Prioritize fastest production time',
                'high_quality': 'Prioritize quality and low defect risk',
                'low_cost': 'Prioritize lowest production cost',
                'green': 'Prioritize energy efficiency and sustainability',
            }.get(ctx.value, ctx.value),
            'weights': selector.CONTEXT_WEIGHTS.get(ctx, {}),
        }

    return jsonify({
        'contexts': contexts,
        'criteria': ['cost', 'time', 'quality', 'energy', 'capacity'],
    })


@routings_bp.route('/templates', methods=['GET'])
def get_routing_templates():
    """
    Get available routing templates by part type.

    Returns:
        JSON with routing templates for each part type
    """
    templates_summary = {}

    for part_type, operations in ROUTING_TEMPLATES.items():
        total_setup = sum(op.get('setup_time_min', 0) for op in operations)
        total_run = sum(op.get('run_time_min', 0) for op in operations)

        templates_summary[part_type] = {
            'operation_count': len(operations),
            'operations': [op['operation_code'] for op in operations],
            'total_setup_min': total_setup,
            'total_run_min': total_run,
            'work_center_types': list(set(
                op.get('work_center_type', '') for op in operations
            )),
        }

    return jsonify({
        'templates': templates_summary,
        'part_types': list(ROUTING_TEMPLATES.keys()),
    })


@routings_bp.route('/templates/<part_type>', methods=['GET'])
def get_template_details(part_type: str):
    """
    Get detailed routing template for a part type.

    Returns:
        JSON with full operation sequence
    """
    template = ROUTING_TEMPLATES.get(part_type)

    if not template:
        return jsonify({
            'error': f'Template not found for part type: {part_type}',
            'available_types': list(ROUTING_TEMPLATES.keys()),
        }), 404

    return jsonify({
        'part_type': part_type,
        'operations': template,
        'total_operations': len(template),
    })


@routings_bp.route('/optimize', methods=['POST'])
def optimize_routing_selection():
    """
    Run multi-scenario routing optimization.

    Compares selection results across all contexts
    for decision support.

    Request body:
    {
        "part_id": "BRICK-2X4",
        "quantity": 100,
        "due_date": "2024-03-15"
    }

    Returns:
        JSON with optimization results for all contexts
    """
    data = request.get_json() or {}

    if not ROUTING_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Routing services not available',
        }), 503

    selector = _get_selector()

    part_id = data.get('part_id', '')
    quantity = int(data.get('quantity', 1))

    due_date = None
    if data.get('due_date'):
        try:
            due_date = date.fromisoformat(data['due_date'])
        except ValueError:
            pass

    # Run selection for each context
    scenarios = []
    for context in SelectionContext:
        selection_request = SelectionRequest(
            part_id=part_id,
            quantity=quantity,
            due_date=due_date,
            context=context,
        )
        result = selector.select_routing(selection_request)

        scenarios.append({
            'context': context.value,
            'selected_routing': result.selected_routing_name,
            'routing_id': result.selected_routing_id,
            'estimated_cost': result.estimated_cost,
            'estimated_time_hours': result.estimated_time_hours,
            'confidence': result.confidence,
            'reason': result.selection_reason,
        })

    # Find Pareto-optimal solutions
    pareto_front = _identify_pareto_front(scenarios)

    return jsonify({
        'part_id': part_id,
        'quantity': quantity,
        'scenarios': scenarios,
        'pareto_front': pareto_front,
        'recommendation': scenarios[0] if scenarios else None,
    })


def _identify_pareto_front(scenarios):
    """Identify Pareto-optimal scenarios."""
    pareto = []
    for i, s1 in enumerate(scenarios):
        dominated = False
        for j, s2 in enumerate(scenarios):
            if i == j:
                continue
            # s2 dominates s1 if better in at least one dimension, no worse in others
            better_cost = s2['estimated_cost'] < s1['estimated_cost']
            better_time = s2['estimated_time_hours'] < s1['estimated_time_hours']
            not_worse_cost = s2['estimated_cost'] <= s1['estimated_cost']
            not_worse_time = s2['estimated_time_hours'] <= s1['estimated_time_hours']

            if (better_cost or better_time) and not_worse_cost and not_worse_time:
                dominated = True
                break

        if not dominated:
            pareto.append(s1['context'])

    return pareto


@routings_bp.route('/what-if', methods=['POST'])
def what_if_analysis():
    """
    Run what-if analysis for routing selection.

    Analyze impact of different quantities, constraints, or priorities.

    Request body:
    {
        "part_id": "BRICK-2X4",
        "base_quantity": 100,
        "scenarios": [
            {"quantity": 50, "context": "normal"},
            {"quantity": 100, "context": "rush"},
            {"quantity": 200, "context": "low_cost"},
            {"quantity": 100, "max_cost": 40.0}
        ]
    }

    Returns:
        JSON with analysis results for each scenario
    """
    data = request.get_json() or {}

    if not ROUTING_SERVICES_AVAILABLE:
        return jsonify({
            'error': 'Routing services not available',
        }), 503

    selector = _get_selector()
    part_id = data.get('part_id', '')
    scenarios_input = data.get('scenarios', [])

    results = []
    for scenario in scenarios_input:
        quantity = int(scenario.get('quantity', data.get('base_quantity', 1)))

        context_str = scenario.get('context', 'normal').upper()
        try:
            context = SelectionContext[context_str]
        except KeyError:
            context = SelectionContext.NORMAL

        selection_request = SelectionRequest(
            part_id=part_id,
            quantity=quantity,
            context=context,
            max_cost=scenario.get('max_cost'),
            max_time_hours=scenario.get('max_time_hours'),
        )

        result = selector.select_routing(selection_request)

        results.append({
            'scenario': scenario,
            'selected_routing': result.selected_routing_name,
            'routing_id': result.selected_routing_id,
            'estimated_cost': result.estimated_cost,
            'estimated_time_hours': result.estimated_time_hours,
            'confidence': result.confidence,
            'alternatives': result.alternative_routing_ids,
        })

    return jsonify({
        'part_id': part_id,
        'what_if_results': results,
        'scenario_count': len(results),
    })


@routings_bp.route('/summary', methods=['GET'])
def get_routing_summary():
    """
    Get routing selection system summary.

    Returns:
        JSON with system statistics
    """
    if not ROUTING_SERVICES_AVAILABLE:
        return jsonify({
            'available': False,
            'message': 'Routing services not available',
        })

    selector = _get_selector()
    summary = selector.get_selection_summary()
    summary['available'] = True

    return jsonify(summary)
