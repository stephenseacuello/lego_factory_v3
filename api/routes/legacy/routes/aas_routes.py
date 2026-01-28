"""
Asset Administration Shell (AAS) API Routes
=============================================
REST API for AAS access per IDTA specifications.

Endpoints:
- GET  /api/aas/shells              - List all AAS
- GET  /api/aas/shells/<id>         - Get specific AAS
- POST /api/aas/shells              - Create new AAS
- DELETE /api/aas/shells/<id>       - Delete AAS
- GET  /api/aas/shells/<id>/submodels - List submodels
- GET  /api/aas/submodels/<id>      - Get specific submodel
- PUT  /api/aas/shells/<id>/operational - Update operational data

Author: Flask CNC SCADA System
"""

import logging
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint('aas', __name__, url_prefix='/api/aas')


def _get_aas_service():
    """Get AAS service (lazy import)."""
    from services.aas_service import get_aas_service
    return get_aas_service()


# =============================================================================
# Shell Endpoints
# =============================================================================

@bp.route('/shells', methods=['GET'])
def list_shells():
    """
    List all Asset Administration Shells.

    Query params:
        - asset_type: Filter by asset type

    Response:
        {
            "shells": [
                {
                    "id": "urn:scada:aas:mill-01",
                    "idShort": "mill-01",
                    "assetInformation": {...}
                }
            ],
            "count": 1
        }
    """
    aas_service = _get_aas_service()
    shells = aas_service.get_all_shells()

    # Filter by asset type if specified
    asset_type = request.args.get('asset_type')
    if asset_type:
        shells = [
            s for s in shells
            if s.asset_information.asset_type and asset_type in s.asset_information.asset_type
        ]

    return jsonify({
        "shells": [s.to_dict() for s in shells],
        "count": len(shells)
    })


@bp.route('/shells/<path:aas_id>', methods=['GET'])
def get_shell(aas_id: str):
    """
    Get a specific Asset Administration Shell.

    Response:
        {
            "assetAdministrationShells": [...],
            "submodels": [...],
            "conceptDescriptions": []
        }
    """
    aas_service = _get_aas_service()

    # Handle URL-encoded IDs
    if not aas_id.startswith('urn:'):
        aas_id = f"urn:scada:aas:{aas_id}"

    result = aas_service.export_shell(aas_id)
    if not result:
        return jsonify({
            "error": "Not Found",
            "message": f"AAS not found: {aas_id}"
        }), 404

    return jsonify(result)


@bp.route('/shells', methods=['POST'])
def create_shell():
    """
    Create a new Asset Administration Shell for a machine.

    Request body:
        {
            "machine_id": "mill-01",
            "machine_type": "tinyg",
            "manufacturer": "Synthetos",
            "model": "TinyG v8",
            "serial_number": "TG-001234",
            "capabilities": {
                "axes": ["X", "Y", "Z"],
                "max_feed_rate": 5000,
                "max_spindle_speed": 24000
            }
        }

    Response:
        {"id": "urn:scada:aas:mill-01", ...}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Bad Request", "message": "JSON body required"}), 400

    machine_id = data.get('machine_id')
    if not machine_id:
        return jsonify({"error": "Bad Request", "message": "machine_id required"}), 400

    aas_service = _get_aas_service()

    try:
        shell = aas_service.create_shell_for_machine(
            machine_id=machine_id,
            machine_type=data.get('machine_type', 'unknown'),
            manufacturer=data.get('manufacturer', 'Unknown'),
            model=data.get('model', 'Unknown'),
            serial_number=data.get('serial_number', ''),
            capabilities=data.get('capabilities')
        )

        return jsonify(shell.to_dict()), 201

    except Exception as e:
        logger.error(f"Failed to create AAS: {e}")
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e)
        }), 500


@bp.route('/shells/<path:aas_id>', methods=['DELETE'])
def delete_shell(aas_id: str):
    """
    Delete an Asset Administration Shell.

    Response:
        {"message": "AAS deleted successfully"}
    """
    aas_service = _get_aas_service()

    if not aas_id.startswith('urn:'):
        aas_id = f"urn:scada:aas:{aas_id}"

    if aas_service.delete_shell(aas_id):
        return jsonify({"message": "AAS deleted successfully"})
    else:
        return jsonify({
            "error": "Not Found",
            "message": f"AAS not found: {aas_id}"
        }), 404


# =============================================================================
# Submodel Endpoints
# =============================================================================

@bp.route('/shells/<path:aas_id>/submodels', methods=['GET'])
def list_submodels(aas_id: str):
    """
    List submodels for an AAS.

    Response:
        {
            "submodels": [...],
            "count": 3
        }
    """
    aas_service = _get_aas_service()

    if not aas_id.startswith('urn:'):
        aas_id = f"urn:scada:aas:{aas_id}"

    submodels = aas_service.get_submodels_for_shell(aas_id)

    return jsonify({
        "submodels": [sm.to_dict() for sm in submodels],
        "count": len(submodels)
    })


@bp.route('/submodels/<path:submodel_id>', methods=['GET'])
def get_submodel(submodel_id: str):
    """
    Get a specific submodel.

    Response:
        {
            "modelType": "Submodel",
            "id": "...",
            "idShort": "...",
            "submodelElements": [...]
        }
    """
    aas_service = _get_aas_service()

    submodel = aas_service.get_submodel(submodel_id)
    if not submodel:
        return jsonify({
            "error": "Not Found",
            "message": f"Submodel not found: {submodel_id}"
        }), 404

    return jsonify(submodel.to_dict())


@bp.route('/shells/<path:aas_id>/submodels/<id_short>', methods=['GET'])
def get_submodel_by_short_id(aas_id: str, id_short: str):
    """
    Get submodel by idShort for an AAS.

    Response:
        {
            "modelType": "Submodel",
            ...
        }
    """
    aas_service = _get_aas_service()

    if not aas_id.startswith('urn:'):
        aas_id = f"urn:scada:aas:{aas_id}"

    shell = aas_service.get_shell(aas_id)
    if not shell:
        return jsonify({
            "error": "Not Found",
            "message": f"AAS not found: {aas_id}"
        }), 404

    submodel = shell.get_submodel(id_short)
    if not submodel:
        return jsonify({
            "error": "Not Found",
            "message": f"Submodel not found: {id_short}"
        }), 404

    return jsonify(submodel.to_dict())


# =============================================================================
# Operational Data Update
# =============================================================================

@bp.route('/shells/<machine_id>/operational', methods=['PUT'])
def update_operational_data(machine_id: str):
    """
    Update operational data submodel with real-time status.

    Request body:
        {
            "state": "RUNNING",
            "wx": 100.5,
            "wy": 50.2,
            "wz": -10.0,
            "feed": 1500,
            "sps": 12000,
            "line": 42
        }

    Response:
        {"message": "Operational data updated"}
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Bad Request", "message": "JSON body required"}), 400

    aas_service = _get_aas_service()

    if aas_service.update_operational_data(machine_id, data):
        return jsonify({"message": "Operational data updated"})
    else:
        return jsonify({
            "error": "Not Found",
            "message": f"AAS not found for machine: {machine_id}"
        }), 404


# =============================================================================
# Export
# =============================================================================

@bp.route('/export', methods=['GET'])
def export_all():
    """
    Export all AAS as AASX-compatible JSON.

    Response:
        {
            "assetAdministrationShells": [...],
            "submodels": [...],
            "conceptDescriptions": []
        }
    """
    aas_service = _get_aas_service()
    return jsonify(aas_service.export_all())
