"""
Vision Inspection API Routes
============================
REST API endpoints for vision-based quality inspection.

Endpoints:
- POST /api/inspection/inspect - Run inspection on a part
- GET /api/inspection/reports - List inspection reports
- GET /api/inspection/reports/<id> - Get specific report
- GET /api/inspection/stats - Get inspection statistics
- POST /api/inspection/calibrate - Run calibration routine
- GET /api/inspection/defect-types - Get defect type catalog
"""

import asyncio
import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from typing import Optional

logger = logging.getLogger(__name__)

# Blueprint for vision inspection routes
bp = Blueprint('vision_inspection', __name__, url_prefix='/api/inspection')

# Lazy service initialization
_inspection_service = None


def get_inspection_service():
    """Get or create the vision inspection service instance."""
    global _inspection_service
    if _inspection_service is None:
        try:
            from services.vision_inspection_service import VisionInspectionService
            _inspection_service = VisionInspectionService()
            logger.info("Vision inspection service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize vision inspection service: {e}")
            return None
    return _inspection_service


# =============================================================================
# Inspection Endpoints
# =============================================================================

@bp.route('/inspect', methods=['POST'])
def run_inspection():
    """
    Run inspection on a part.

    Request Body:
        part_id: str - Part identifier
        job_id: str - Job identifier
        inspection_type: str - Type of inspection (full, visual, dimensional, surface)
        expected_dimensions: list - Optional list of expected dimensions
        machining_data: dict - Optional machining parameters

    Returns:
        Inspection report with results
    """
    service = get_inspection_service()
    if not service:
        return jsonify({"error": "Vision inspection service not available"}), 503

    data = request.get_json() or {}

    part_id = data.get('part_id')
    job_id = data.get('job_id')

    if not part_id or not job_id:
        return jsonify({"error": "part_id and job_id are required"}), 400

    inspection_type_str = data.get('inspection_type', 'full')
    expected_dimensions = data.get('expected_dimensions')
    machining_data = data.get('machining_data')

    try:
        from services.vision_inspection_service import InspectionType

        # Map string to enum
        type_map = {
            'full': InspectionType.FULL,
            'visual': InspectionType.VISUAL,
            'dimensional': InspectionType.DIMENSIONAL,
            'surface': InspectionType.SURFACE
        }
        inspection_type = type_map.get(inspection_type_str.lower(), InspectionType.FULL)

        # Run inspection async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(
                service.inspect_part(
                    part_id=part_id,
                    job_id=job_id,
                    inspection_type=inspection_type,
                    expected_dimensions=expected_dimensions,
                    machining_data=machining_data
                )
            )
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "report": service._report_to_dict(report)
        })

    except Exception as e:
        logger.error(f"Inspection failed: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/reports', methods=['GET'])
def list_reports():
    """
    List inspection reports with optional filtering.

    Query Parameters:
        job_id: str - Filter by job
        part_id: str - Filter by part
        result: str - Filter by result (pass, fail, warning)
        since: str - ISO datetime for start of range
        limit: int - Max results (default 50)

    Returns:
        List of inspection reports
    """
    service = get_inspection_service()
    if not service:
        return jsonify({"error": "Vision inspection service not available"}), 503

    job_id = request.args.get('job_id')
    part_id = request.args.get('part_id')
    result_filter = request.args.get('result')
    since_str = request.args.get('since')
    limit = int(request.args.get('limit', 50))

    try:
        # Get all reports from service
        reports = list(service.inspection_history.values())

        # Apply filters
        if job_id:
            reports = [r for r in reports if r.job_id == job_id]

        if part_id:
            reports = [r for r in reports if r.part_id == part_id]

        if result_filter:
            from services.vision_inspection_service import InspectionResult
            result_enum = InspectionResult(result_filter.lower())
            reports = [r for r in reports if r.result == result_enum]

        if since_str:
            since_dt = datetime.fromisoformat(since_str.replace('Z', '+00:00'))
            reports = [r for r in reports if r.timestamp >= since_dt]

        # Sort by timestamp descending and limit
        reports = sorted(reports, key=lambda r: r.timestamp, reverse=True)[:limit]

        return jsonify({
            "count": len(reports),
            "reports": [service._report_to_dict(r) for r in reports]
        })

    except Exception as e:
        logger.error(f"Failed to list reports: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/reports/<report_id>', methods=['GET'])
def get_report(report_id: str):
    """
    Get a specific inspection report.

    Args:
        report_id: Report identifier

    Returns:
        Full inspection report
    """
    service = get_inspection_service()
    if not service:
        return jsonify({"error": "Vision inspection service not available"}), 503

    report = service.inspection_history.get(report_id)

    if not report:
        return jsonify({"error": "Report not found"}), 404

    return jsonify(service._report_to_dict(report))


@bp.route('/stats', methods=['GET'])
def get_inspection_stats():
    """
    Get inspection statistics.

    Query Parameters:
        hours: int - Hours to look back (default 24)
        job_id: str - Filter by job

    Returns:
        Inspection statistics including pass rate, defect counts
    """
    service = get_inspection_service()
    if not service:
        return jsonify({"error": "Vision inspection service not available"}), 503

    hours = int(request.args.get('hours', 24))
    job_id = request.args.get('job_id')

    try:
        cutoff = datetime.now() - timedelta(hours=hours)

        # Filter reports
        reports = [r for r in service.inspection_history.values()
                   if r.timestamp >= cutoff]

        if job_id:
            reports = [r for r in reports if r.job_id == job_id]

        if not reports:
            return jsonify({
                "period_hours": hours,
                "total_inspections": 0,
                "pass_count": 0,
                "fail_count": 0,
                "warning_count": 0,
                "pass_rate": 0.0,
                "defect_summary": {},
                "avg_inspection_time_ms": 0
            })

        from services.vision_inspection_service import InspectionResult

        pass_count = sum(1 for r in reports if r.result == InspectionResult.PASS)
        fail_count = sum(1 for r in reports if r.result == InspectionResult.FAIL)
        warning_count = sum(1 for r in reports if r.result == InspectionResult.WARNING)

        # Aggregate defects by type
        defect_summary = {}
        for report in reports:
            for defect in report.defects:
                defect_type = defect.defect_type
                if defect_type not in defect_summary:
                    defect_summary[defect_type] = 0
                defect_summary[defect_type] += 1

        # Average inspection time
        total_time = sum(r.inspection_duration_ms for r in reports)
        avg_time = total_time / len(reports) if reports else 0

        return jsonify({
            "period_hours": hours,
            "total_inspections": len(reports),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "warning_count": warning_count,
            "pass_rate": pass_count / len(reports) * 100 if reports else 0.0,
            "defect_summary": defect_summary,
            "avg_inspection_time_ms": avg_time
        })

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/calibrate', methods=['POST'])
def run_calibration():
    """
    Run calibration routine for the vision system.

    Request Body:
        calibration_type: str - Type of calibration (camera, lighting, dimensional)
        reference_id: str - Reference artifact ID

    Returns:
        Calibration result
    """
    service = get_inspection_service()
    if not service:
        return jsonify({"error": "Vision inspection service not available"}), 503

    data = request.get_json() or {}
    calibration_type = data.get('calibration_type', 'full')
    reference_id = data.get('reference_id')

    try:
        # Simulated calibration (in production, this would trigger actual calibration)
        calibration_result = {
            "timestamp": datetime.now().isoformat(),
            "calibration_type": calibration_type,
            "reference_id": reference_id,
            "status": "completed",
            "results": {
                "camera_focus": {"status": "ok", "value": 0.98},
                "lighting_uniformity": {"status": "ok", "value": 0.95},
                "dimensional_accuracy": {"status": "ok", "error_mm": 0.012}
            },
            "next_calibration_due": (datetime.now() + timedelta(hours=24)).isoformat()
        }

        logger.info(f"Calibration completed: {calibration_type}")

        return jsonify({
            "success": True,
            "calibration": calibration_result
        })

    except Exception as e:
        logger.error(f"Calibration failed: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/defect-types', methods=['GET'])
def get_defect_types():
    """
    Get catalog of known defect types.

    Returns:
        List of defect types with descriptions and severity levels
    """
    defect_catalog = {
        "defect_types": [
            {
                "type": "scratch",
                "description": "Surface scratch or abrasion",
                "severity_range": ["minor", "major"],
                "detection_method": "visual"
            },
            {
                "type": "burr",
                "description": "Machining burr or raised edge",
                "severity_range": ["minor", "major", "critical"],
                "detection_method": "visual"
            },
            {
                "type": "chip",
                "description": "Material chip or breakout",
                "severity_range": ["major", "critical"],
                "detection_method": "visual"
            },
            {
                "type": "dimension_error",
                "description": "Dimensional deviation from specification",
                "severity_range": ["minor", "major", "critical"],
                "detection_method": "dimensional"
            },
            {
                "type": "surface_roughness",
                "description": "Surface finish out of specification",
                "severity_range": ["minor", "major"],
                "detection_method": "surface"
            },
            {
                "type": "tool_mark",
                "description": "Visible tool marks or machining patterns",
                "severity_range": ["minor", "major"],
                "detection_method": "visual"
            },
            {
                "type": "contamination",
                "description": "Foreign material or debris",
                "severity_range": ["minor", "major"],
                "detection_method": "visual"
            },
            {
                "type": "crack",
                "description": "Surface or subsurface crack",
                "severity_range": ["critical"],
                "detection_method": "visual"
            }
        ],
        "severity_definitions": {
            "minor": "Cosmetic defect, does not affect function",
            "major": "Significant defect, may affect function or assembly",
            "critical": "Critical defect, part is non-conforming"
        }
    }

    return jsonify(defect_catalog)


@bp.route('/health', methods=['GET'])
def health_check():
    """
    Check vision inspection system health.

    Returns:
        Health status of vision inspection components
    """
    service = get_inspection_service()

    status = {
        "service": "ok" if service else "unavailable",
        "camera": "simulated",  # Would check actual camera in production
        "lighting": "ok",
        "calibration_status": "valid",
        "last_inspection": None,
        "inspections_today": 0
    }

    if service and service.inspection_history:
        today = datetime.now().date()
        today_reports = [r for r in service.inspection_history.values()
                        if r.timestamp.date() == today]

        status["inspections_today"] = len(today_reports)

        if today_reports:
            latest = max(today_reports, key=lambda r: r.timestamp)
            status["last_inspection"] = latest.timestamp.isoformat()

    return jsonify(status)
