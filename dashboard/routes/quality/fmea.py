"""
FMEA Routes - Failure Mode and Effects Analysis API

LegoMCP World-Class Manufacturing System v5.0
Phase 10: FMEA Engine (Dynamic)

Provides:
- FMEA record management
- Failure mode tracking with dynamic RPN
- Risk actions and triggered responses
- LEGO-specific failure mode templates
"""

from flask import Blueprint, jsonify, request, render_template

fmea_bp = Blueprint('fmea', __name__, url_prefix='/fmea')


# Dashboard Page Route
@fmea_bp.route('/page', methods=['GET'])
def fmea_page():
    """Render FMEA dashboard page."""
    return render_template('pages/quality/fmea_dashboard.html')

# Try to import FMEA service
try:
    from services.quality.fmea_service import FMEAService, DynamicFactors
    fmea_service = FMEAService()
    FMEA_AVAILABLE = True
except ImportError:
    FMEA_AVAILABLE = False
    fmea_service = None


def _get_service():
    """Get or create FMEA service."""
    global fmea_service
    if fmea_service is None:
        from services.quality.fmea_service import FMEAService
        fmea_service = FMEAService()
    return fmea_service


@fmea_bp.route('', methods=['GET'])
def list_fmeas():
    """
    List all FMEA records.

    Query params:
    - part_id: Filter by part ID
    - status: Filter by status (draft, active, archived)
    - high_risk: Filter to high-risk only (true/false)

    Returns:
        JSON list of FMEA records
    """
    service = _get_service()

    part_id = request.args.get('part_id')
    status = request.args.get('status')
    high_risk = request.args.get('high_risk', '').lower() == 'true'

    if part_id:
        fmeas = service.get_fmeas_by_part(part_id)
    elif high_risk:
        fmeas = service.get_high_risk_parts()
    else:
        fmeas = list(service._fmeas.values())

    if status:
        fmeas = [f for f in fmeas if f.get('status') == status]

    return jsonify({
        'fmeas': fmeas,
        'count': len(fmeas),
        'summary': service.get_summary()
    })


@fmea_bp.route('', methods=['POST'])
def create_fmea():
    """
    Create a new FMEA record.

    Request body:
    {
        "part_id": "PART-001",
        "part_name": "2x4 Brick",
        "fmea_type": "process",  // "design", "process", "material", "human"
        "use_lego_template": true  // Auto-add LEGO failure modes
    }

    Returns:
        JSON with created FMEA
    """
    service = _get_service()
    data = request.get_json() or {}

    part_id = data.get('part_id', 'UNKNOWN')
    part_name = data.get('part_name', 'Unknown Part')
    fmea_type = data.get('fmea_type', 'process')
    use_lego_template = data.get('use_lego_template', False)

    if use_lego_template:
        fmea = service.create_lego_pfmea(part_id, part_name)
    else:
        fmea = service.create_fmea(part_id, part_name, fmea_type)

    return jsonify({
        'success': True,
        'fmea': fmea,
        'summary': service.get_risk_summary(fmea['fmea_id'])
    }), 201


@fmea_bp.route('/<fmea_id>', methods=['GET'])
def get_fmea(fmea_id: str):
    """
    Get FMEA by ID with dynamic RPN.

    Returns:
        JSON with FMEA details and risk summary
    """
    service = _get_service()

    fmea = service.get_fmea(fmea_id)
    if not fmea:
        return jsonify({'error': 'FMEA not found'}), 404

    return jsonify({
        'fmea': fmea,
        'summary': service.get_risk_summary(fmea_id),
        'triggered_actions': service.check_triggered_actions(fmea_id)
    })


@fmea_bp.route('/<fmea_id>/failure-modes', methods=['GET'])
def get_failure_modes(fmea_id: str):
    """Get failure modes for an FMEA."""
    service = _get_service()

    fmea = service.get_fmea(fmea_id)
    if not fmea:
        return jsonify({'error': 'FMEA not found'}), 404

    # Sort by dynamic RPN descending
    failure_modes = sorted(
        fmea['failure_modes'],
        key=lambda x: x.get('dynamic_rpn', 0),
        reverse=True
    )

    return jsonify({
        'fmea_id': fmea_id,
        'failure_modes': failure_modes,
        'count': len(failure_modes)
    })


@fmea_bp.route('/<fmea_id>/failure-modes', methods=['POST'])
def add_failure_mode(fmea_id: str):
    """
    Add a failure mode to an FMEA.

    Request body:
    {
        "description": "Stud diameter undersized",
        "severity": 7,
        "occurrence": 4,
        "detection": 5,
        "effect": "Poor clutch power",
        "cause": "Under-extrusion",
        "controls": "Dimensional inspection"
    }

    OR for LEGO template:
    {
        "mode_key": "stud_undersized"  // Use predefined LEGO mode
    }

    Returns:
        JSON with created failure mode
    """
    service = _get_service()
    data = request.get_json() or {}

    fmea = service.get_fmea(fmea_id)
    if not fmea:
        return jsonify({'error': 'FMEA not found'}), 404

    # Check for LEGO template mode
    mode_key = data.get('mode_key')
    if mode_key:
        fm = service.add_lego_failure_mode(fmea_id, mode_key)
        if not fm:
            return jsonify({
                'error': 'Invalid mode key',
                'available_modes': list(service.LEGO_FAILURE_MODES.keys())
            }), 400
    else:
        # Custom failure mode
        fm = service.add_failure_mode(
            fmea_id=fmea_id,
            description=data.get('description', ''),
            severity=int(data.get('severity', 5)),
            occurrence=int(data.get('occurrence', 5)),
            detection=int(data.get('detection', 5)),
            effect=data.get('effect', ''),
            cause=data.get('cause', ''),
            controls=data.get('controls', ''),
            is_safety_critical=data.get('is_safety_critical', False)
        )

    return jsonify({
        'success': True,
        'failure_mode': fm,
        'fmea_summary': service.get_risk_summary(fmea_id)
    }), 201


@fmea_bp.route('/<fmea_id>/actions', methods=['GET'])
def get_actions(fmea_id: str):
    """Get risk actions for an FMEA."""
    service = _get_service()

    fmea = service.get_fmea(fmea_id)
    if not fmea:
        return jsonify({'error': 'FMEA not found'}), 404

    return jsonify({
        'fmea_id': fmea_id,
        'actions': fmea['actions'],
        'count': len(fmea['actions']),
        'triggered': service.check_triggered_actions(fmea_id)
    })


@fmea_bp.route('/<fmea_id>/actions', methods=['POST'])
def add_action(fmea_id: str):
    """
    Add a risk action to a failure mode.

    Request body:
    {
        "failure_mode_id": "fm-123",
        "action_type": "inspection",  // inspection, slow_routing, human_intervention, price_adjustment
        "description": "Add 100% inspection for stud diameter",
        "trigger_threshold": 100,
        "auto_execute": true
    }

    Returns:
        JSON with created action
    """
    service = _get_service()
    data = request.get_json() or {}

    fmea = service.get_fmea(fmea_id)
    if not fmea:
        return jsonify({'error': 'FMEA not found'}), 404

    failure_mode_id = data.get('failure_mode_id')
    if not failure_mode_id:
        return jsonify({'error': 'failure_mode_id required'}), 400

    action = service.add_risk_action(
        failure_mode_id=failure_mode_id,
        action_type=data.get('action_type', 'inspection'),
        description=data.get('description', ''),
        trigger_threshold=float(data.get('trigger_threshold', 100)),
        auto_execute=data.get('auto_execute', False)
    )

    if not action:
        return jsonify({'error': 'Failure mode not found'}), 404

    return jsonify({
        'success': True,
        'action': action
    }), 201


@fmea_bp.route('/<fmea_id>/dynamic-factors', methods=['PUT'])
def update_dynamic_factors(fmea_id: str):
    """
    Update dynamic factors affecting RPN calculation.

    Request body:
    {
        "work_center_id": "WC-001",
        "machine_health": 1.2,  // 1.0 = normal, >1 = degraded
        "operator_skill": 1.0,
        "material_quality": 1.0,
        "spc_trend": 1.5,  // 1.0 = stable, >1 = trending OOC
        "environmental": 1.0
    }

    Returns:
        JSON with updated FMEA and new dynamic RPNs
    """
    service = _get_service()
    data = request.get_json() or {}

    fmea = service.get_fmea(fmea_id)
    if not fmea:
        return jsonify({'error': 'FMEA not found'}), 404

    factors = DynamicFactors(
        machine_health=float(data.get('machine_health', 1.0)),
        operator_skill=float(data.get('operator_skill', 1.0)),
        material_quality=float(data.get('material_quality', 1.0)),
        spc_trend=float(data.get('spc_trend', 1.0)),
        environmental=float(data.get('environmental', 1.0))
    )

    work_center_id = data.get('work_center_id', 'default')
    service.update_dynamic_factors(work_center_id, factors)

    return jsonify({
        'success': True,
        'fmea': service.get_fmea(fmea_id),
        'summary': service.get_risk_summary(fmea_id),
        'triggered_actions': service.check_triggered_actions(fmea_id)
    })


@fmea_bp.route('/<fmea_id>/trend/<failure_mode_id>', methods=['GET'])
def get_trend(fmea_id: str, failure_mode_id: str):
    """Get RPN trend analysis for a failure mode."""
    service = _get_service()

    fmea = service.get_fmea(fmea_id)
    if not fmea:
        return jsonify({'error': 'FMEA not found'}), 404

    trend = service.analyze_trend(fmea_id, failure_mode_id)

    return jsonify(trend)


@fmea_bp.route('/templates/lego', methods=['GET'])
def get_lego_templates():
    """
    Get LEGO-specific failure mode templates.

    Returns:
        JSON list of predefined LEGO failure modes
    """
    service = _get_service()

    templates = []
    for key, data in service.LEGO_FAILURE_MODES.items():
        templates.append({
            'mode_key': key,
            'description': data['description'],
            'effect': data['effect'],
            'cause': data['cause'],
            'severity': data['severity'],
            'occurrence': data['occurrence'],
            'detection': data['detection'],
            'rpn': data['severity'] * data['occurrence'] * data['detection']
        })

    # Sort by RPN descending
    templates.sort(key=lambda x: x['rpn'], reverse=True)

    return jsonify({
        'templates': templates,
        'count': len(templates)
    })


@fmea_bp.route('/high-risk', methods=['GET'])
def get_high_risk():
    """
    Get all high-risk parts based on FMEA.

    Query params:
    - threshold: RPN threshold (default: 100)

    Returns:
        JSON list of high-risk parts
    """
    service = _get_service()

    threshold = float(request.args.get('threshold', 100))
    high_risk = service.get_high_risk_parts(threshold)

    return jsonify({
        'high_risk_parts': high_risk,
        'count': len(high_risk),
        'threshold': threshold
    })


@fmea_bp.route('/summary', methods=['GET'])
def get_summary():
    """
    Get overall FMEA summary.

    Returns:
        JSON with FMEA statistics
    """
    service = _get_service()

    return jsonify(service.get_summary())
