# =============================================================================
# Material Flow Tracking API Routes
# =============================================================================
#
# REST endpoints for material flow tracking in the factory cell.
# Provides part tracking, location updates, and production metrics.
#
# Endpoints:
#   GET  /api/material/parts              - List all active parts
#   GET  /api/material/parts/<part_id>    - Get specific part
#   POST /api/material/parts              - Create new part
#   PUT  /api/material/parts/<part_id>/location  - Update part location
#   PUT  /api/material/parts/<part_id>/status    - Update part status
#   GET  /api/material/metrics            - Get flow metrics
#   GET  /api/material/history/<part_id>  - Get part event history
#   GET  /api/material/locations          - Get parts by location
# =============================================================================

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime

logger = logging.getLogger(__name__)

# Blueprint for material flow routes
bp = Blueprint('material_flow', __name__, url_prefix='/api/material')

# Service will be imported at runtime to avoid circular imports
_service = None


def get_service():
    """Lazy load the material flow service."""
    global _service
    if _service is None:
        try:
            from services.material_flow_service import get_material_flow_service
            _service = get_material_flow_service()
        except ImportError as e:
            logger.error(f"Failed to import material flow service: {e}")
            return None
    return _service


# -----------------------------------------------------------------------------
# Part Management Endpoints
# -----------------------------------------------------------------------------

@bp.route('/parts', methods=['GET'])
def list_parts():
    """
    List all active parts in the system.

    Query Parameters:
        job_id (str): Filter by job ID
        status (str): Filter by status
        location (str): Filter by location
        limit (int): Maximum number of parts to return

    Returns:
        JSON with list of parts
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        # Get filter parameters
        job_id = request.args.get('job_id')
        status = request.args.get('status')
        location = request.args.get('location')
        limit = request.args.get('limit', 100, type=int)

        # Get parts
        if job_id:
            parts = service.get_parts_by_job(job_id)
        elif status:
            from services.material_flow_service import PartStatus
            try:
                status_enum = PartStatus(status)
                parts = service.get_parts_by_status(status_enum)
            except ValueError:
                return jsonify({"success": False, "error": f"Invalid status: {status}"}), 400
        elif location:
            from services.material_flow_service import PartLocation
            try:
                location_enum = PartLocation(location)
                parts = service.get_parts_at_location(location_enum)
            except ValueError:
                return jsonify({"success": False, "error": f"Invalid location: {location}"}), 400
        else:
            parts = service.get_all_active_parts()

        # Apply limit
        parts = parts[:limit]

        # Convert to dict
        parts_data = []
        for part in parts:
            parts_data.append({
                "part_id": part.part_id,
                "job_id": part.job_id,
                "serial_number": part.serial_number,
                "material_type": part.material_type.value,
                "location": part.location.value,
                "status": part.status.value,
                "slot_number": part.slot_number,
                "created_at": part.created_at.isoformat(),
                "updated_at": part.updated_at.isoformat()
            })

        return jsonify({
            "success": True,
            "count": len(parts_data),
            "parts": parts_data
        })

    except Exception as e:
        logger.error(f"Error listing parts: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/parts/<part_id>', methods=['GET'])
def get_part(part_id: str):
    """
    Get details for a specific part.

    Args:
        part_id: Part identifier

    Returns:
        JSON with part details
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        part = service.get_part(part_id)
        if not part:
            return jsonify({"success": False, "error": f"Part not found: {part_id}"}), 404

        return jsonify({
            "success": True,
            "part": {
                "part_id": part.part_id,
                "job_id": part.job_id,
                "serial_number": part.serial_number,
                "material_type": part.material_type.value,
                "batch_id": part.batch_id,
                "location": part.location.value,
                "status": part.status.value,
                "slot_number": part.slot_number,
                "created_at": part.created_at.isoformat(),
                "updated_at": part.updated_at.isoformat(),
                "started_machining_at": part.started_machining_at.isoformat() if part.started_machining_at else None,
                "finished_machining_at": part.finished_machining_at.isoformat() if part.finished_machining_at else None,
                "inspection_completed_at": part.inspection_completed_at.isoformat() if part.inspection_completed_at else None,
                "inspection_result": part.inspection_result,
                "inspection_report_id": part.inspection_report_id,
                "quality_score": part.quality_score,
                "max_vibration": part.max_vibration,
                "max_spindle_temp": part.max_spindle_temp,
                "avg_feed_rate": part.avg_feed_rate,
                "event_count": len(part.events),
                "metadata": part.metadata
            }
        })

    except Exception as e:
        logger.error(f"Error getting part {part_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/parts', methods=['POST'])
async def create_part():
    """
    Create a new part record.

    Request Body:
        job_id (str): Required - Job identifier
        material_type (str): Optional - Material type (default: aluminum_6061)
        slot_number (int): Optional - Input pallet slot
        batch_id (str): Optional - Batch identifier
        metadata (dict): Optional - Additional metadata

    Returns:
        JSON with created part details
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        job_id = data.get('job_id')
        if not job_id:
            return jsonify({"success": False, "error": "job_id is required"}), 400

        # Parse material type
        from services.material_flow_service import MaterialType
        material_str = data.get('material_type', 'aluminum_6061')
        try:
            material_type = MaterialType(material_str)
        except ValueError:
            material_type = MaterialType.ALUMINUM_6061

        part = await service.create_part(
            job_id=job_id,
            material_type=material_type,
            slot_number=data.get('slot_number'),
            batch_id=data.get('batch_id'),
            metadata=data.get('metadata')
        )

        return jsonify({
            "success": True,
            "part_id": part.part_id,
            "serial_number": part.serial_number
        }), 201

    except Exception as e:
        logger.error(f"Error creating part: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/parts/<part_id>/location', methods=['PUT'])
async def update_part_location(part_id: str):
    """
    Update part location.

    Request Body:
        location (str): Required - New location
        slot_number (int): Optional - Slot number for pallet locations
        metadata (dict): Optional - Additional event metadata

    Returns:
        JSON with updated part details
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        location_str = data.get('location')
        if not location_str:
            return jsonify({"success": False, "error": "location is required"}), 400

        from services.material_flow_service import PartLocation
        try:
            location = PartLocation(location_str)
        except ValueError:
            return jsonify({"success": False, "error": f"Invalid location: {location_str}"}), 400

        part = await service.update_location(
            part_id=part_id,
            new_location=location,
            slot_number=data.get('slot_number'),
            metadata=data.get('metadata')
        )

        if not part:
            return jsonify({"success": False, "error": f"Part not found: {part_id}"}), 404

        return jsonify({
            "success": True,
            "part_id": part.part_id,
            "location": part.location.value,
            "status": part.status.value
        })

    except Exception as e:
        logger.error(f"Error updating part location: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/parts/<part_id>/status', methods=['PUT'])
async def update_part_status(part_id: str):
    """
    Update part status.

    Request Body:
        status (str): Required - New status
        metadata (dict): Optional - Additional event metadata

    Returns:
        JSON with updated part details
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        status_str = data.get('status')
        if not status_str:
            return jsonify({"success": False, "error": "status is required"}), 400

        from services.material_flow_service import PartStatus
        try:
            status = PartStatus(status_str)
        except ValueError:
            return jsonify({"success": False, "error": f"Invalid status: {status_str}"}), 400

        part = await service.update_status(
            part_id=part_id,
            new_status=status,
            metadata=data.get('metadata')
        )

        if not part:
            return jsonify({"success": False, "error": f"Part not found: {part_id}"}), 404

        return jsonify({
            "success": True,
            "part_id": part.part_id,
            "status": part.status.value,
            "location": part.location.value
        })

    except Exception as e:
        logger.error(f"Error updating part status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/parts/<part_id>/machining-data', methods=['PUT'])
async def record_machining_data(part_id: str):
    """
    Record machining sensor data for a part.

    Request Body:
        max_vibration (float): Maximum vibration (g)
        max_spindle_temp (float): Maximum spindle temp (°C)
        avg_feed_rate (float): Average feed rate (mm/min)

    Returns:
        JSON with updated part details
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        part = await service.record_machining_data(
            part_id=part_id,
            max_vibration=data.get('max_vibration'),
            max_spindle_temp=data.get('max_spindle_temp'),
            avg_feed_rate=data.get('avg_feed_rate')
        )

        if not part:
            return jsonify({"success": False, "error": f"Part not found: {part_id}"}), 404

        return jsonify({
            "success": True,
            "part_id": part.part_id,
            "max_vibration": part.max_vibration,
            "max_spindle_temp": part.max_spindle_temp,
            "avg_feed_rate": part.avg_feed_rate
        })

    except Exception as e:
        logger.error(f"Error recording machining data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/parts/<part_id>/inspection', methods=['PUT'])
async def record_inspection(part_id: str):
    """
    Record inspection results for a part.

    Request Body:
        result (str): Required - "PASS", "FAIL", or "CONDITIONAL"
        report_id (str): Required - Inspection report ID
        quality_score (float): Optional - Quality confidence (0-1)
        metadata (dict): Optional - Additional inspection data

    Returns:
        JSON with updated part details
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        result = data.get('result')
        report_id = data.get('report_id')

        if not result or not report_id:
            return jsonify({"success": False, "error": "result and report_id are required"}), 400

        if result not in ("PASS", "FAIL", "CONDITIONAL"):
            return jsonify({"success": False, "error": "result must be PASS, FAIL, or CONDITIONAL"}), 400

        part = await service.record_inspection_result(
            part_id=part_id,
            result=result,
            report_id=report_id,
            quality_score=data.get('quality_score'),
            metadata=data.get('metadata')
        )

        if not part:
            return jsonify({"success": False, "error": f"Part not found: {part_id}"}), 404

        return jsonify({
            "success": True,
            "part_id": part.part_id,
            "inspection_result": part.inspection_result,
            "status": part.status.value
        })

    except Exception as e:
        logger.error(f"Error recording inspection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# Query Endpoints
# -----------------------------------------------------------------------------

@bp.route('/history/<part_id>', methods=['GET'])
def get_part_history(part_id: str):
    """
    Get event history for a part.

    Args:
        part_id: Part identifier

    Returns:
        JSON with list of events
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        events = service.get_part_history(part_id)

        events_data = []
        for event in events:
            events_data.append({
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "old_value": event.old_value,
                "new_value": event.new_value,
                "location": event.location.value,
                "metadata": event.metadata
            })

        return jsonify({
            "success": True,
            "part_id": part_id,
            "event_count": len(events_data),
            "events": events_data
        })

    except Exception as e:
        logger.error(f"Error getting part history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/locations', methods=['GET'])
def get_parts_by_location():
    """
    Get parts grouped by location.

    Returns:
        JSON with parts organized by location
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        from services.material_flow_service import PartLocation

        locations = {}
        for loc in PartLocation:
            parts = service.get_parts_at_location(loc)
            locations[loc.value] = {
                "count": len(parts),
                "parts": [
                    {
                        "part_id": p.part_id,
                        "job_id": p.job_id,
                        "status": p.status.value,
                        "slot_number": p.slot_number
                    }
                    for p in parts
                ]
            }

        return jsonify({
            "success": True,
            "locations": locations
        })

    except Exception as e:
        logger.error(f"Error getting parts by location: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/completed', methods=['GET'])
def get_completed_parts():
    """
    Get recently completed parts.

    Query Parameters:
        limit (int): Maximum number of parts (default: 100)

    Returns:
        JSON with list of completed parts
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        limit = request.args.get('limit', 100, type=int)
        parts = service.get_completed_parts(limit)

        parts_data = []
        for part in parts:
            parts_data.append({
                "part_id": part.part_id,
                "job_id": part.job_id,
                "serial_number": part.serial_number,
                "location": part.location.value,
                "status": part.status.value,
                "inspection_result": part.inspection_result,
                "quality_score": part.quality_score,
                "created_at": part.created_at.isoformat(),
                "inspection_completed_at": part.inspection_completed_at.isoformat() if part.inspection_completed_at else None
            })

        return jsonify({
            "success": True,
            "count": len(parts_data),
            "parts": parts_data
        })

    except Exception as e:
        logger.error(f"Error getting completed parts: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# -----------------------------------------------------------------------------
# Metrics Endpoint
# -----------------------------------------------------------------------------

@bp.route('/metrics', methods=['GET'])
def get_metrics():
    """
    Get material flow metrics.

    Returns:
        JSON with production metrics
    """
    service = get_service()
    if not service:
        return jsonify({"success": False, "error": "Service not available"}), 503

    try:
        metrics = service.get_metrics_dict()
        return jsonify({
            "success": True,
            "metrics": metrics
        })

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
