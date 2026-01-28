"""
Fusion 360 Integration API Routes
=================================
REST API endpoints for Fusion 360 CAD/CAM integration.

Features:
- Project management and synchronization
- NC program provenance and approval workflow
- Bidirectional parameter bridge
- Tool library synchronization
- Setup/fixture validation
- Adaptive feedback backchannel
- Change-impact alerts
- Variant/configurator support

Endpoints:
    /api/fusion360/projects             - Project management
    /api/fusion360/nc-programs          - NC program provenance
    /api/fusion360/approval             - Approval workflow
    /api/fusion360/parameters           - Parameter bridge
    /api/fusion360/tools/sync           - Tool library sync
    /api/fusion360/validation           - Setup validation
    /api/fusion360/feedback             - Adaptive feedback
    /api/fusion360/alerts               - Change alerts
    /api/fusion360/variants             - Variant configurator
    /api/fusion360/digital-twin         - Digital twin data
"""

import logging
from flask import Blueprint, request, jsonify
from functools import wraps
from typing import Optional

from config import get_config
from services.fusion360_service import (
    get_fusion360_service,
    ApprovalStatus,
    SyncStatus,
    ValidationResult
)

logger = logging.getLogger(__name__)
config = get_config()

bp = Blueprint('fusion360', __name__, url_prefix='/api/fusion360')


# =============================================================================
# Authentication Decorator
# =============================================================================

def require_auth(f):
    """Require authentication for endpoint."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # In dev mode, skip auth
        if config.DEV_MODE or not config.JWT_ENABLED:
            return f(*args, **kwargs)

        # Check for bearer token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing authorization token"}), 401

        # Token validation would go here
        # For now, just check it exists
        token = auth_header[7:]
        if not token:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated


def get_current_user() -> str:
    """Get current user from request (placeholder)."""
    # In real implementation, extract from JWT
    return request.headers.get('X-User-ID', 'anonymous')


# =============================================================================
# Project Management
# =============================================================================

@bp.route('/projects', methods=['GET'])
@require_auth
def list_projects():
    """
    List all registered Fusion 360 projects.

    Returns:
        JSON list of projects
    """
    service = get_fusion360_service()
    projects = service.list_projects()

    return jsonify({
        "projects": projects,
        "count": len(projects)
    })


@bp.route('/projects', methods=['POST'])
@require_auth
def register_project():
    """
    Register a new Fusion 360 project for synchronization.

    Request body:
        project_id: Fusion 360 project ID
        name: Project name
        hub_id: Autodesk hub ID (optional)
        watch_folder: Local folder to watch for NC files (optional)

    Returns:
        Registered project details
    """
    data = request.get_json()

    if not data or not data.get('project_id') or not data.get('name'):
        return jsonify({"error": "project_id and name are required"}), 400

    service = get_fusion360_service()
    project = service.register_project(
        project_id=data['project_id'],
        name=data['name'],
        hub_id=data.get('hub_id', ''),
        watch_folder=data.get('watch_folder', '')
    )

    return jsonify({
        "message": "Project registered",
        "project": project.to_dict()
    }), 201


@bp.route('/projects/<project_id>', methods=['GET'])
@require_auth
def get_project(project_id: str):
    """Get project details."""
    service = get_fusion360_service()
    project = service.get_project(project_id)

    if not project:
        return jsonify({"error": "Project not found"}), 404

    return jsonify({"project": project.to_dict()})


@bp.route('/projects/<project_id>/sync', methods=['POST'])
@require_auth
def sync_project(project_id: str):
    """
    Synchronize project with Fusion 360 API.

    Fetches latest version and detects changes.
    """
    service = get_fusion360_service()
    success, message = service.sync_project(project_id)

    if success:
        return jsonify({"message": message})
    else:
        return jsonify({"error": message}), 400


# =============================================================================
# NC Program Provenance
# =============================================================================

@bp.route('/nc-programs', methods=['POST'])
@require_auth
def register_nc_program():
    """
    Register an NC program with full provenance tracking.

    Request body:
        filename: NC program filename
        content: G-code content
        fusion_document_id: Source Fusion document ID
        fusion_document_version: Document version
        fusion_setup_id: CAM setup ID
        fusion_setup_name: CAM setup name
        post_processor_version: Post processor version (optional)

    Returns:
        Registered NC program with provenance info
    """
    data = request.get_json()

    required_fields = ['filename', 'content', 'fusion_document_id', 'fusion_document_version']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    service = get_fusion360_service()
    program = service.register_nc_program(
        filename=data['filename'],
        content=data['content'],
        fusion_document_id=data['fusion_document_id'],
        fusion_document_version=data['fusion_document_version'],
        fusion_setup_id=data.get('fusion_setup_id', ''),
        fusion_setup_name=data.get('fusion_setup_name', ''),
        post_processor_version=data.get('post_processor_version', ''),
        uploaded_by=get_current_user()
    )

    return jsonify({
        "message": "NC program registered with provenance",
        "program_id": program.program_id,
        "provenance": {
            "fusion_document_id": program.fusion_document_id,
            "fusion_document_version": program.fusion_document_version,
            "content_hash": program.content_hash
        }
    }), 201


@bp.route('/nc-programs/<program_id>/provenance', methods=['GET'])
@require_auth
def get_nc_provenance(program_id: str):
    """
    Get full provenance for an NC program.

    Used for QA traceability - traces part back to exact CAD/CAM state.
    """
    service = get_fusion360_service()
    provenance = service.get_nc_program_provenance(program_id)

    if not provenance:
        return jsonify({"error": "NC program not found"}), 404

    return jsonify(provenance)


# =============================================================================
# Approval Workflow
# =============================================================================

@bp.route('/approval/<program_id>/submit', methods=['POST'])
@require_auth
def submit_for_approval(program_id: str):
    """
    Submit NC program for review/approval.

    Request body:
        simulation_pdf_url: URL to simulation PDF (optional)
        simulation_video_url: URL to simulation video (optional)
    """
    data = request.get_json() or {}

    service = get_fusion360_service()
    success, message = service.submit_for_approval(
        program_id=program_id,
        simulation_pdf_url=data.get('simulation_pdf_url', ''),
        simulation_video_url=data.get('simulation_video_url', '')
    )

    if success:
        return jsonify({"message": message})
    else:
        return jsonify({"error": message}), 400


@bp.route('/approval/<program_id>/approve', methods=['POST'])
@require_auth
def approve_program(program_id: str):
    """
    Approve NC program for execution.

    Request body:
        notes: Approval notes (optional)
    """
    data = request.get_json() or {}

    service = get_fusion360_service()
    success, message = service.approve_nc_program(
        program_id=program_id,
        approved_by=get_current_user(),
        notes=data.get('notes', '')
    )

    if success:
        return jsonify({"message": message})
    else:
        return jsonify({"error": message}), 400


@bp.route('/approval/<program_id>/reject', methods=['POST'])
@require_auth
def reject_program(program_id: str):
    """
    Reject NC program.

    Request body:
        reason: Rejection reason (required)
    """
    data = request.get_json() or {}

    if not data.get('reason'):
        return jsonify({"error": "Rejection reason is required"}), 400

    service = get_fusion360_service()
    success, message = service.reject_nc_program(
        program_id=program_id,
        rejected_by=get_current_user(),
        reason=data['reason']
    )

    if success:
        return jsonify({"message": message})
    else:
        return jsonify({"error": message}), 400


@bp.route('/approval/<program_id>/status', methods=['GET'])
@require_auth
def get_approval_status(program_id: str):
    """Get approval status for an NC program."""
    service = get_fusion360_service()
    provenance = service.get_nc_program_provenance(program_id)

    if not provenance:
        return jsonify({"error": "NC program not found"}), 404

    return jsonify({
        "program_id": program_id,
        "approval": provenance.get("approval", {}),
        "is_approved": service.is_program_approved(program_id)
    })


# =============================================================================
# Parameter Bridge
# =============================================================================

@bp.route('/parameters', methods=['GET'])
@require_auth
def get_parameters():
    """Get status of all synchronized parameters."""
    service = get_fusion360_service()
    parameters = service.get_parameter_status()

    return jsonify({
        "parameters": parameters,
        "count": len(parameters)
    })


@bp.route('/parameters', methods=['POST'])
@require_auth
def register_parameter():
    """
    Register a new parameter for bidirectional sync.

    Request body:
        name: Parameter name
        sync_direction: bidirectional, machine_to_fusion, fusion_to_machine
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
    """
    data = request.get_json()

    if not data or not data.get('name'):
        return jsonify({"error": "Parameter name is required"}), 400

    service = get_fusion360_service()
    parameter = service.register_parameter(
        name=data['name'],
        sync_direction=data.get('sync_direction', 'bidirectional'),
        min_value=data.get('min_value'),
        max_value=data.get('max_value')
    )

    return jsonify({
        "message": "Parameter registered",
        "parameter": parameter.to_dict()
    }), 201


@bp.route('/parameters/<name>/machine', methods=['PUT'])
@require_auth
def update_machine_parameter(name: str):
    """
    Update parameter from machine side.

    Request body:
        value: New value
    """
    data = request.get_json()

    if data is None or 'value' not in data:
        return jsonify({"error": "Value is required"}), 400

    service = get_fusion360_service()
    success, sync_status = service.update_machine_parameter(name, data['value'])

    if success:
        return jsonify({
            "message": "Parameter updated",
            "sync_status": sync_status.value
        })
    else:
        return jsonify({"error": "Failed to update parameter"}), 400


@bp.route('/parameters/<name>/fusion', methods=['PUT'])
@require_auth
def update_fusion_parameter(name: str):
    """
    Update parameter from Fusion side.

    Request body:
        value: New value
    """
    data = request.get_json()

    if data is None or 'value' not in data:
        return jsonify({"error": "Value is required"}), 400

    service = get_fusion360_service()
    success, sync_status = service.update_fusion_parameter(name, data['value'])

    if success:
        return jsonify({
            "message": "Parameter updated",
            "sync_status": sync_status.value
        })
    else:
        return jsonify({"error": "Failed to update parameter"}), 400


@bp.route('/parameters/sync', methods=['POST'])
@require_auth
def sync_all_parameters():
    """Synchronize all parameters."""
    service = get_fusion360_service()
    results = service.sync_parameters()

    return jsonify({
        "message": "Parameters synchronized",
        "results": {k: v.value for k, v in results.items()}
    })


# =============================================================================
# Tool Library Sync
# =============================================================================

@bp.route('/tools/sync', methods=['POST'])
@require_auth
def sync_tool_library():
    """
    Synchronize tool library with Fusion 360.

    Request body:
        tools: List of machine tools with their current values
            - number: Tool number
            - description: Tool description
            - diameter: Tool diameter
            - length_offset: Current length offset

    Returns:
        Sync results with any discrepancies found
    """
    data = request.get_json()

    if not data or not data.get('tools'):
        return jsonify({"error": "Tool list is required"}), 400

    service = get_fusion360_service()
    result = service.sync_tool_library(data['tools'])

    return jsonify(result)


# =============================================================================
# Setup Validation
# =============================================================================

@bp.route('/validation', methods=['POST'])
@require_auth
def validate_setup():
    """
    Validate setup against Fusion data before allowing machine start.

    Request body:
        setup_id: Fusion setup ID to validate
        probed_wcs: Probed work coordinate positions {x, y, z}
        tool_measurements: Optional list of tool measurements

    Returns:
        Validation result with gate status
    """
    data = request.get_json()

    if not data or not data.get('setup_id') or not data.get('probed_wcs'):
        return jsonify({"error": "setup_id and probed_wcs are required"}), 400

    service = get_fusion360_service()
    validation = service.validate_setup(
        setup_id=data['setup_id'],
        probed_wcs=data['probed_wcs'],
        tool_measurements=data.get('tool_measurements'),
        validated_by=get_current_user()
    )

    return jsonify({
        "validation": validation.to_dict(),
        "machine_start_allowed": validation.machine_start_allowed
    })


@bp.route('/validation/<validation_id>/override', methods=['POST'])
@require_auth
def override_validation(validation_id: str):
    """
    Override a failed validation gate.

    Request body:
        reason: Override reason (required)

    Note: This creates an audit trail.
    """
    data = request.get_json() or {}

    if not data.get('reason'):
        return jsonify({"error": "Override reason is required"}), 400

    service = get_fusion360_service()
    success, message = service.override_validation_gate(
        validation_id=validation_id,
        override_by=get_current_user(),
        reason=data['reason']
    )

    if success:
        return jsonify({"message": message, "warning": "Gate override recorded in audit trail"})
    else:
        return jsonify({"error": message}), 400


# =============================================================================
# Adaptive Feedback
# =============================================================================

@bp.route('/feedback', methods=['POST'])
@require_auth
def record_feedback():
    """
    Record sensor feedback for adaptive CAM parameter optimization.

    Request body:
        nc_program_id: NC program that was executed
        operation_name: Name of the operation
        sensor_metrics: Aggregated sensor data
            - avg_vibration_rms, max_vibration_rms
            - avg_spindle_load, max_spindle_load
            - avg_temperature, max_temperature
            - avg_motor_current
        cutting_parameters: Actual cutting parameters used
            - feed_rate, spindle_rpm, depth_of_cut

    Returns:
        Feedback record with recommendations
    """
    data = request.get_json()

    required_fields = ['nc_program_id', 'operation_name', 'sensor_metrics', 'cutting_parameters']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    service = get_fusion360_service()
    feedback = service.record_adaptive_feedback(
        nc_program_id=data['nc_program_id'],
        operation_name=data['operation_name'],
        sensor_metrics=data['sensor_metrics'],
        cutting_parameters=data['cutting_parameters']
    )

    return jsonify({
        "message": "Feedback recorded",
        "feedback_id": feedback.feedback_id,
        "recommendations": {
            "feed_adjustment_percent": feedback.recommended_feed_adjustment,
            "rpm_adjustment_percent": feedback.recommended_rpm_adjustment,
            "confidence": feedback.confidence_score
        }
    }), 201


@bp.route('/feedback/recommendations', methods=['GET'])
@require_auth
def get_recommendations():
    """
    Get feed/speed recommendations based on historical data.

    Query parameters:
        operation_type: Type of operation (optional)
        material: Workpiece material (optional)
        tool_diameter: Tool diameter in mm (optional)
    """
    operation_type = request.args.get('operation_type', '')
    material = request.args.get('material', '')
    tool_diameter = float(request.args.get('tool_diameter', 0))

    service = get_fusion360_service()
    recommendations = service.get_feed_speed_recommendations(
        operation_type=operation_type,
        material=material,
        tool_diameter=tool_diameter
    )

    return jsonify(recommendations)


# =============================================================================
# Change Alerts
# =============================================================================

@bp.route('/alerts', methods=['GET'])
@require_auth
def get_alerts():
    """Get unacknowledged change impact alerts."""
    service = get_fusion360_service()
    alerts = service.get_pending_alerts()

    return jsonify({
        "alerts": alerts,
        "count": len(alerts)
    })


@bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
@require_auth
def acknowledge_alert(alert_id: str):
    """Acknowledge a change impact alert."""
    service = get_fusion360_service()
    success = service.acknowledge_alert(
        alert_id=alert_id,
        acknowledged_by=get_current_user()
    )

    if success:
        return jsonify({"message": "Alert acknowledged"})
    else:
        return jsonify({"error": "Alert not found"}), 404


# =============================================================================
# Variant/Configurator
# =============================================================================

@bp.route('/variants', methods=['GET'])
@require_auth
def list_variants():
    """List all product variants."""
    project_id = request.args.get('project_id')

    service = get_fusion360_service()
    variants = service.list_variants(project_id)

    return jsonify({
        "variants": variants,
        "count": len(variants)
    })


@bp.route('/variants', methods=['POST'])
@require_auth
def create_variant():
    """
    Create a product variant with parameter overrides.

    Request body:
        base_project_id: Base Fusion project ID
        variant_name: Name for this variant
        parameter_overrides: Dict of parameter overrides
    """
    data = request.get_json()

    required_fields = ['base_project_id', 'variant_name', 'parameter_overrides']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    service = get_fusion360_service()
    variant = service.create_variant(
        base_project_id=data['base_project_id'],
        variant_name=data['variant_name'],
        parameter_overrides=data['parameter_overrides'],
        created_by=get_current_user()
    )

    return jsonify({
        "message": "Variant created",
        "variant": variant.to_dict()
    }), 201


@bp.route('/variants/<variant_id>/generate-nc', methods=['POST'])
@require_auth
def generate_variant_nc(variant_id: str):
    """
    Request NC program generation for a variant.

    This triggers Fusion 360 to regenerate toolpath with variant parameters.
    """
    service = get_fusion360_service()
    program_id, message = service.generate_variant_nc(variant_id)

    if program_id:
        return jsonify({
            "message": message,
            "nc_program_id": program_id
        })
    else:
        return jsonify({
            "message": message,
            "status": "queued"
        })


# =============================================================================
# Digital Twin Integration
# =============================================================================

@bp.route('/digital-twin/<setup_id>/toolpath', methods=['GET'])
@require_auth
def get_toolpath_data(setup_id: str):
    """
    Get toolpath data for digital twin enrichment.

    Returns toolpath geometry and metadata for simulation.
    """
    service = get_fusion360_service()
    data = service.get_toolpath_for_digital_twin(setup_id)

    if "error" in data:
        return jsonify(data), 404

    return jsonify(data)


@bp.route('/digital-twin/<project_id>/mesh', methods=['GET'])
@require_auth
def get_3d_mesh(project_id: str):
    """
    Get 3D mesh for visualization.

    Returns OBJ/STL mesh data for rendering in UI.
    """
    service = get_fusion360_service()
    mesh_data = service.get_3d_preview_mesh(project_id)

    if not mesh_data:
        return jsonify({
            "error": "Mesh not available",
            "message": "Requires Fusion 360 API connection"
        }), 404

    # Return mesh as binary
    from flask import Response
    return Response(
        mesh_data,
        mimetype='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename={project_id}.obj'}
    )


# =============================================================================
# Health Check
# =============================================================================

@bp.route('/health', methods=['GET'])
def health_check():
    """Health check for Fusion 360 integration."""
    service = get_fusion360_service()

    return jsonify({
        "status": "healthy",
        "service": "fusion360",
        "projects_registered": len(service._projects),
        "nc_programs_tracked": len(service._nc_programs),
        "parameters_bridged": len(service._parameters),
        "pending_alerts": len([a for a in service._alerts if not a.acknowledged])
    })


# =============================================================================
# Webhook for Fusion 360 Events (Future)
# =============================================================================

@bp.route('/webhook', methods=['POST'])
def fusion_webhook():
    """
    Webhook endpoint for Fusion 360 events.

    This would be called by Autodesk when project changes occur.
    """
    data = request.get_json()

    # Validate webhook signature (if implemented)
    # signature = request.headers.get('X-Fusion-Signature')

    logger.info(f"Received Fusion 360 webhook: {data}")

    # Process the event
    event_type = data.get('type')

    if event_type == 'model.modified':
        # Handle model modification
        service = get_fusion360_service()
        # Create change alert
        pass

    elif event_type == 'toolpath.generated':
        # Handle new toolpath
        pass

    return jsonify({"status": "received"})
