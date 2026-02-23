"""
Operator Routes - HMI API Endpoints

LegoMCP World-Class Manufacturing System v5.0
Phase 20: HMI & AR Work Instructions

Provides:
- Work instruction delivery
- Step-by-step guidance
- Media attachments
- AR marker data
- Voice command interface
"""

from datetime import datetime
from flask import Blueprint, jsonify, request
import uuid

operator_bp = Blueprint('operator', __name__, url_prefix='/operator')

# Try to import HMI services
try:
    from services.hmi.work_instructions import WorkInstructionService
    HMI_AVAILABLE = True
except ImportError:
    HMI_AVAILABLE = False

# In-memory storage
_work_instructions = {}
_operator_sessions = {}


@operator_bp.route('/status', methods=['GET'])
def get_hmi_status():
    """Get HMI system status."""
    return jsonify({
        'available': True,
        'capabilities': {
            'work_instructions': True,
            'step_by_step': True,
            'media_support': ['image', 'video', '3d_model'],
            'ar_support': True,
            'voice_interface': True,
            'multi_language': True,
        },
        'active_sessions': len(_operator_sessions),
    })


@operator_bp.route('/instructions/<part_id>', methods=['GET'])
def get_work_instructions(part_id: str):
    """
    Get work instructions for a part.

    Query params:
        operation: Specific operation code
        language: Language code (en, es, zh, etc.)
        format: detailed|summary

    Returns:
        JSON with work instructions
    """
    operation = request.args.get('operation')
    language = request.args.get('language', 'en')

    # Demo work instructions
    instructions = {
        'part_id': part_id,
        'part_name': 'Standard 2x4 Brick',
        'revision': 'REV-A',
        'language': language,
        'operations': [
            {
                'operation_code': 'PRINT',
                'operation_name': 'FDM 3D Printing',
                'work_center': 'WC-PRINT-01',
                'standard_time_min': 45,
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Load Filament',
                        'description': 'Ensure PLA filament is properly loaded and fed through extruder',
                        'media': {'type': 'image', 'url': '/static/instructions/load_filament.jpg'},
                        'safety_notes': ['Wear heat-resistant gloves'],
                        'quality_checks': [],
                    },
                    {
                        'step_number': 2,
                        'title': 'Start Print Job',
                        'description': 'Select job from queue and verify settings',
                        'media': {'type': 'video', 'url': '/static/instructions/start_print.mp4'},
                        'safety_notes': [],
                        'quality_checks': ['Verify bed level indicator is green'],
                    },
                    {
                        'step_number': 3,
                        'title': 'Monitor First Layer',
                        'description': 'Observe first layer adhesion for 2 minutes',
                        'media': {'type': 'image', 'url': '/static/instructions/first_layer.jpg'},
                        'safety_notes': [],
                        'quality_checks': ['First layer adhesion OK', 'No warping'],
                    },
                ],
            },
            {
                'operation_code': 'INSPECT',
                'operation_name': 'Quality Inspection',
                'work_center': 'WC-QC',
                'standard_time_min': 5,
                'steps': [
                    {
                        'step_number': 1,
                        'title': 'Visual Inspection',
                        'description': 'Check for surface defects, stringing, and layer issues',
                        'media': {'type': 'image', 'url': '/static/instructions/visual_inspect.jpg'},
                        'safety_notes': [],
                        'quality_checks': ['No visible defects', 'Surface quality grade 3+'],
                    },
                    {
                        'step_number': 2,
                        'title': 'Dimensional Check',
                        'description': 'Measure stud diameter with calipers',
                        'media': {'type': 'video', 'url': '/static/instructions/measure_studs.mp4'},
                        'safety_notes': [],
                        'quality_checks': ['Stud diameter 4.80 +/- 0.02mm'],
                    },
                    {
                        'step_number': 3,
                        'title': 'Clutch Power Test',
                        'description': 'Test LEGO brick compatibility',
                        'media': {'type': '3d_model', 'url': '/static/instructions/clutch_test.glb'},
                        'safety_notes': [],
                        'quality_checks': ['Clutch power 1.5-3.0 N'],
                    },
                ],
            },
        ],
    }

    if operation:
        instructions['operations'] = [
            op for op in instructions['operations']
            if op['operation_code'] == operation
        ]

    return jsonify(instructions)


@operator_bp.route('/session/start', methods=['POST'])
def start_operator_session():
    """
    Start an operator session.

    Request body:
    {
        "operator_id": "OP-001",
        "work_order_id": "WO-001",
        "work_center_id": "WC-PRINT-01"
    }

    Returns:
        JSON with session info
    """
    data = request.get_json() or {}

    session_id = str(uuid.uuid4())[:8]

    session = {
        'session_id': session_id,
        'operator_id': data.get('operator_id'),
        'work_order_id': data.get('work_order_id'),
        'work_center_id': data.get('work_center_id'),
        'started_at': datetime.utcnow().isoformat(),
        'current_operation': None,
        'current_step': 0,
        'status': 'active',
        'completions': [],
    }

    _operator_sessions[session_id] = session

    return jsonify({
        'success': True,
        'session': session,
    }), 201


@operator_bp.route('/session/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """Get operator session status."""
    session = _operator_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    return jsonify(session)


@operator_bp.route('/session/<session_id>/step', methods=['POST'])
def complete_step(session_id: str):
    """
    Complete a step in the current operation.

    Request body:
    {
        "operation_code": "PRINT",
        "step_number": 1,
        "quality_checks": {"first_layer_ok": true},
        "notes": "Optional notes"
    }
    """
    session = _operator_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    data = request.get_json() or {}

    completion = {
        'operation_code': data.get('operation_code'),
        'step_number': data.get('step_number'),
        'completed_at': datetime.utcnow().isoformat(),
        'quality_checks': data.get('quality_checks', {}),
        'notes': data.get('notes'),
    }

    session['completions'].append(completion)
    session['current_step'] = data.get('step_number', 0) + 1
    session['current_operation'] = data.get('operation_code')

    return jsonify({
        'success': True,
        'completion': completion,
        'next_step': session['current_step'],
    })


@operator_bp.route('/session/<session_id>/end', methods=['POST'])
def end_session(session_id: str):
    """End an operator session."""
    session = _operator_sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    session['ended_at'] = datetime.utcnow().isoformat()
    session['status'] = 'completed'

    return jsonify({
        'success': True,
        'session': session,
    })


@operator_bp.route('/ar/markers/<part_id>', methods=['GET'])
def get_ar_markers(part_id: str):
    """
    Get AR markers and overlay data for a part.

    Returns:
        JSON with AR marker positions and overlays
    """
    markers = {
        'part_id': part_id,
        'markers': [
            {
                'marker_id': 'stud_measure',
                'type': 'measurement',
                'position': {'x': 0, 'y': 0, 'z': 9.6},
                'overlay': {
                    'type': 'dimension',
                    'label': 'Stud Height',
                    'value': '1.8mm',
                    'tolerance': '+/- 0.02mm',
                },
            },
            {
                'marker_id': 'qc_zone',
                'type': 'inspection_zone',
                'position': {'x': 0, 'y': 0, 'z': 0},
                'overlay': {
                    'type': 'highlight',
                    'color': '#00ff00',
                    'label': 'Quality Check Zone',
                },
            },
        ],
        '3d_model_url': '/static/models/brick_2x4.glb',
        'scale': 1.0,
    }

    return jsonify(markers)


@operator_bp.route('/voice/command', methods=['POST'])
def process_voice_command():
    """
    Process a voice command.

    Request body:
    {
        "session_id": "abc123",
        "command_text": "next step",
        "language": "en"
    }

    Returns:
        JSON with command response
    """
    data = request.get_json() or {}

    command = data.get('command_text', '').lower()
    session_id = data.get('session_id')

    # Parse command
    if 'next' in command or 'forward' in command:
        action = 'next_step'
        response_text = 'Moving to next step'
    elif 'previous' in command or 'back' in command:
        action = 'previous_step'
        response_text = 'Going back to previous step'
    elif 'complete' in command or 'done' in command:
        action = 'complete_step'
        response_text = 'Step marked as complete'
    elif 'repeat' in command:
        action = 'repeat_instruction'
        response_text = 'Repeating current instruction'
    elif 'help' in command:
        action = 'show_help'
        response_text = 'Showing help information'
    elif 'quality' in command or 'check' in command:
        action = 'show_quality_checks'
        response_text = 'Displaying quality checks for this step'
    else:
        action = 'unknown'
        response_text = 'Command not recognized. Say "help" for available commands.'

    return jsonify({
        'command': command,
        'action': action,
        'response_text': response_text,
        'speak': True,
    })


@operator_bp.route('/alerts', methods=['GET'])
def get_operator_alerts():
    """Get active operator alerts."""
    work_center = request.args.get('work_center')

    alerts = [
        {
            'alert_id': 'ALT-001',
            'type': 'quality',
            'severity': 'warning',
            'message': 'SPC control limit approaching on stud diameter',
            'work_center': 'WC-PRINT-01',
            'created_at': datetime.utcnow().isoformat(),
            'action_required': 'Check and adjust nozzle temperature',
        },
        {
            'alert_id': 'ALT-002',
            'type': 'material',
            'severity': 'info',
            'message': 'PLA-RED filament at 20% remaining',
            'work_center': 'WC-PRINT-01',
            'created_at': datetime.utcnow().isoformat(),
            'action_required': 'Prepare replacement spool',
        },
    ]

    if work_center:
        alerts = [a for a in alerts if a['work_center'] == work_center]

    return jsonify({
        'alerts': alerts,
        'count': len(alerts),
    })


@operator_bp.route('/training/<operator_id>', methods=['GET'])
def get_training_status(operator_id: str):
    """Get operator training status."""
    return jsonify({
        'operator_id': operator_id,
        'certifications': [
            {
                'skill': '3D Printing',
                'level': 'certified',
                'certified_date': '2024-01-15',
                'expires': '2025-01-15',
                'status': 'active',
            },
            {
                'skill': 'Quality Inspection',
                'level': 'certified',
                'certified_date': '2024-02-01',
                'expires': '2025-02-01',
                'status': 'active',
            },
        ],
        'required_training': [
            {
                'skill': 'SPC Fundamentals',
                'due_date': '2024-06-30',
                'status': 'pending',
            },
        ],
        'training_hours_ytd': 24,
        'compliance': True,
    })
