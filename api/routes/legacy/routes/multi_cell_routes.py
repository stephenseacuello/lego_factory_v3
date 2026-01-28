"""
Multi-Cell Factory API Routes
=============================
REST API endpoints for enterprise multi-cell factory management.

Endpoints:
- POST /api/factory/cells - Register a cell
- GET /api/factory/cells - List all cells
- GET /api/factory/cells/<id> - Get cell details
- PUT /api/factory/cells/<id>/status - Update cell status
- POST /api/factory/jobs - Submit a job
- GET /api/factory/jobs - List jobs
- GET /api/factory/jobs/<id> - Get job details
- POST /api/factory/jobs/<id>/cancel - Cancel a job
- GET /api/factory/alarms - List alarms
- POST /api/factory/alarms/<id>/acknowledge - Acknowledge alarm
- GET /api/factory/status - Get factory status overview
- GET /api/factory/metrics - Get factory-wide metrics
"""

import asyncio
import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from typing import Optional

logger = logging.getLogger(__name__)

# Blueprint for multi-cell factory routes
bp = Blueprint('multi_cell_factory', __name__, url_prefix='/api/factory')

# Lazy service initialization
_factory_service = None


def get_factory_service():
    """Get or create the multi-cell factory service instance."""
    global _factory_service
    if _factory_service is None:
        try:
            from services.multi_cell_factory_service import MultiCellFactoryService
            _factory_service = MultiCellFactoryService()
            logger.info("Multi-cell factory service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize factory service: {e}")
            return None
    return _factory_service


# =============================================================================
# Cell Management Endpoints
# =============================================================================

@bp.route('/cells', methods=['POST'])
def register_cell():
    """
    Register a new manufacturing cell.

    Request Body:
        cell_id: str - Unique cell identifier
        cell_name: str - Human-readable name
        location: str - Physical location
        capabilities: list - List of capability strings
        max_concurrent_jobs: int - Max simultaneous jobs (default 1)
        metadata: dict - Optional additional metadata

    Returns:
        Registered cell info
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    data = request.get_json() or {}

    cell_id = data.get('cell_id')
    cell_name = data.get('cell_name')
    location = data.get('location')
    capabilities = data.get('capabilities', [])

    if not cell_id or not cell_name or not location:
        return jsonify({"error": "cell_id, cell_name, and location are required"}), 400

    max_jobs = data.get('max_concurrent_jobs', 1)
    metadata = data.get('metadata', {})

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            cell = loop.run_until_complete(
                service.register_cell(
                    cell_id=cell_id,
                    cell_name=cell_name,
                    location=location,
                    capabilities=capabilities,
                    max_concurrent_jobs=max_jobs,
                    metadata=metadata
                )
            )
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "message": f"Cell {cell_id} registered",
            "cell": service._cell_to_dict(cell)
        }), 201

    except Exception as e:
        logger.error(f"Failed to register cell: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/cells', methods=['GET'])
def list_cells():
    """
    List all registered cells.

    Query Parameters:
        status: str - Filter by status (online, offline, busy, maintenance, error)
        location: str - Filter by location
        capability: str - Filter by capability

    Returns:
        List of cells
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    status_filter = request.args.get('status')
    location_filter = request.args.get('location')
    capability_filter = request.args.get('capability')

    try:
        cells = list(service.cells.values())

        if status_filter:
            from services.multi_cell_factory_service import CellStatus
            status_enum = CellStatus(status_filter.lower())
            cells = [c for c in cells if c.status == status_enum]

        if location_filter:
            cells = [c for c in cells if location_filter.lower() in c.location.lower()]

        if capability_filter:
            cells = [c for c in cells if capability_filter in c.capabilities]

        return jsonify({
            "count": len(cells),
            "cells": [service._cell_to_dict(c) for c in cells]
        })

    except Exception as e:
        logger.error(f"Failed to list cells: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/cells/<cell_id>', methods=['GET'])
def get_cell(cell_id: str):
    """
    Get details of a specific cell.

    Args:
        cell_id: Cell identifier

    Returns:
        Cell details including current jobs and metrics
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    cell = service.cells.get(cell_id)

    if not cell:
        return jsonify({"error": "Cell not found"}), 404

    # Get jobs for this cell
    cell_jobs = [j for j in service.jobs.values() if j.assigned_cell == cell_id]

    return jsonify({
        **service._cell_to_dict(cell),
        "active_jobs": [service._job_to_dict(j) for j in cell_jobs
                       if j.status in ['pending', 'running']]
    })


@bp.route('/cells/<cell_id>/status', methods=['PUT'])
def update_cell_status(cell_id: str):
    """
    Update cell status.

    Args:
        cell_id: Cell identifier

    Request Body:
        status: str - New status (online, offline, maintenance, error)
        reason: str - Optional reason for status change

    Returns:
        Updated cell info
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    cell = service.cells.get(cell_id)
    if not cell:
        return jsonify({"error": "Cell not found"}), 404

    data = request.get_json() or {}
    status_str = data.get('status')
    reason = data.get('reason')

    if not status_str:
        return jsonify({"error": "status is required"}), 400

    try:
        from services.multi_cell_factory_service import CellStatus

        new_status = CellStatus(status_str.lower())
        cell.status = new_status
        cell.last_heartbeat = datetime.now()

        logger.info(f"Cell {cell_id} status updated to {new_status.value}: {reason}")

        return jsonify({
            "success": True,
            "message": f"Cell status updated to {new_status.value}",
            "cell": service._cell_to_dict(cell)
        })

    except ValueError:
        return jsonify({"error": f"Invalid status: {status_str}"}), 400
    except Exception as e:
        logger.error(f"Failed to update cell status: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/cells/<cell_id>/heartbeat', methods=['POST'])
def cell_heartbeat(cell_id: str):
    """
    Send heartbeat from a cell.

    Args:
        cell_id: Cell identifier

    Request Body:
        metrics: dict - Optional performance metrics

    Returns:
        Acknowledgment
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    cell = service.cells.get(cell_id)
    if not cell:
        return jsonify({"error": "Cell not found"}), 404

    data = request.get_json() or {}
    metrics = data.get('metrics', {})

    try:
        cell.last_heartbeat = datetime.now()

        # Update metrics if provided
        if 'oee' in metrics:
            cell.current_oee = metrics['oee']
        if 'utilization' in metrics:
            cell.utilization_percent = metrics['utilization']

        return jsonify({
            "success": True,
            "message": "Heartbeat received",
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Failed to process heartbeat: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Job Management Endpoints
# =============================================================================

@bp.route('/jobs', methods=['POST'])
def submit_job():
    """
    Submit a manufacturing job for routing.

    Request Body:
        job_name: str - Job name
        part_count: int - Number of parts to produce
        nc_program: str - NC program file or reference
        required_capabilities: list - Required cell capabilities
        priority: int - Job priority (1-10, default 5)
        due_date: str - Optional ISO datetime due date
        metadata: dict - Optional additional metadata

    Returns:
        Submitted job info with routing decision
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    data = request.get_json() or {}

    job_name = data.get('job_name')
    part_count = data.get('part_count')
    nc_program = data.get('nc_program')
    required_capabilities = data.get('required_capabilities', [])

    if not job_name or not part_count or not nc_program:
        return jsonify({"error": "job_name, part_count, and nc_program are required"}), 400

    priority = data.get('priority', 5)
    due_date_str = data.get('due_date')
    metadata = data.get('metadata', {})

    due_date = None
    if due_date_str:
        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            job = loop.run_until_complete(
                service.submit_job(
                    job_name=job_name,
                    part_count=part_count,
                    nc_program=nc_program,
                    required_capabilities=required_capabilities,
                    priority=priority,
                    due_date=due_date,
                    metadata=metadata
                )
            )
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "message": f"Job {job.id} submitted",
            "job": service._job_to_dict(job)
        }), 201

    except Exception as e:
        logger.error(f"Failed to submit job: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/jobs', methods=['GET'])
def list_jobs():
    """
    List jobs.

    Query Parameters:
        status: str - Filter by status (pending, running, completed, failed, cancelled)
        cell_id: str - Filter by assigned cell
        limit: int - Max results (default 50)

    Returns:
        List of jobs
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    status_filter = request.args.get('status')
    cell_filter = request.args.get('cell_id')
    limit = int(request.args.get('limit', 50))

    try:
        jobs = list(service.jobs.values())

        if status_filter:
            jobs = [j for j in jobs if j.status == status_filter.lower()]

        if cell_filter:
            jobs = [j for j in jobs if j.assigned_cell == cell_filter]

        # Sort by submit time descending
        jobs = sorted(jobs, key=lambda j: j.submit_time, reverse=True)[:limit]

        return jsonify({
            "count": len(jobs),
            "jobs": [service._job_to_dict(j) for j in jobs]
        })

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/jobs/<job_id>', methods=['GET'])
def get_job(job_id: str):
    """
    Get details of a specific job.

    Args:
        job_id: Job identifier

    Returns:
        Full job details
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    job = service.jobs.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(service._job_to_dict(job))


@bp.route('/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id: str):
    """
    Cancel a job.

    Args:
        job_id: Job identifier

    Request Body:
        reason: str - Optional cancellation reason

    Returns:
        Confirmation
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    job = service.jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status in ['completed', 'failed', 'cancelled']:
        return jsonify({"error": f"Cannot cancel job with status: {job.status}"}), 400

    data = request.get_json() or {}
    reason = data.get('reason', 'User requested cancellation')

    try:
        job.status = 'cancelled'
        job.error_message = reason

        # Update cell if job was assigned
        if job.assigned_cell:
            cell = service.cells.get(job.assigned_cell)
            if cell and job_id in cell.current_jobs:
                cell.current_jobs.remove(job_id)

        logger.info(f"Job {job_id} cancelled: {reason}")

        return jsonify({
            "success": True,
            "message": f"Job {job_id} cancelled",
            "job": service._job_to_dict(job)
        })

    except Exception as e:
        logger.error(f"Failed to cancel job: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/jobs/<job_id>/complete', methods=['POST'])
def complete_job(job_id: str):
    """
    Mark a job as completed.

    Args:
        job_id: Job identifier

    Request Body:
        completed_count: int - Number of parts completed
        scrap_count: int - Number of scrapped parts (default 0)

    Returns:
        Updated job info
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    job = service.jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status != 'running':
        return jsonify({"error": f"Cannot complete job with status: {job.status}"}), 400

    data = request.get_json() or {}
    completed_count = data.get('completed_count', job.part_count)
    scrap_count = data.get('scrap_count', 0)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                service.complete_job(job_id, completed_count, scrap_count)
            )
        finally:
            loop.close()

        job = service.jobs.get(job_id)

        return jsonify({
            "success": True,
            "message": f"Job {job_id} completed",
            "job": service._job_to_dict(job)
        })

    except Exception as e:
        logger.error(f"Failed to complete job: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Alarm Management Endpoints
# =============================================================================

@bp.route('/alarms', methods=['GET'])
def list_alarms():
    """
    List factory alarms.

    Query Parameters:
        active: bool - Only show active alarms (default true)
        cell_id: str - Filter by cell
        severity: str - Filter by severity

    Returns:
        List of alarms
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    active_only = request.args.get('active', 'true').lower() == 'true'
    cell_filter = request.args.get('cell_id')
    severity_filter = request.args.get('severity')

    try:
        alarms = list(service.alarms.values())

        if active_only:
            alarms = [a for a in alarms if a.active]

        if cell_filter:
            alarms = [a for a in alarms if a.cell_id == cell_filter]

        if severity_filter:
            alarms = [a for a in alarms if a.severity == severity_filter.lower()]

        # Sort by timestamp descending
        alarms = sorted(alarms, key=lambda a: a.timestamp, reverse=True)

        return jsonify({
            "count": len(alarms),
            "alarms": [service._alarm_to_dict(a) for a in alarms]
        })

    except Exception as e:
        logger.error(f"Failed to list alarms: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/alarms/<alarm_id>/acknowledge', methods=['POST'])
def acknowledge_alarm(alarm_id: str):
    """
    Acknowledge an alarm.

    Args:
        alarm_id: Alarm identifier

    Request Body:
        acknowledged_by: str - User acknowledging the alarm
        notes: str - Optional notes

    Returns:
        Updated alarm info
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    alarm = service.alarms.get(alarm_id)
    if not alarm:
        return jsonify({"error": "Alarm not found"}), 404

    data = request.get_json() or {}
    acknowledged_by = data.get('acknowledged_by', 'operator')
    notes = data.get('notes')

    try:
        alarm.acknowledged = True
        alarm.acknowledged_by = acknowledged_by
        alarm.acknowledged_at = datetime.now()

        logger.info(f"Alarm {alarm_id} acknowledged by {acknowledged_by}")

        return jsonify({
            "success": True,
            "message": f"Alarm acknowledged by {acknowledged_by}",
            "alarm": service._alarm_to_dict(alarm)
        })

    except Exception as e:
        logger.error(f"Failed to acknowledge alarm: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/alarms/<alarm_id>/clear', methods=['POST'])
def clear_alarm(alarm_id: str):
    """
    Clear/resolve an alarm.

    Args:
        alarm_id: Alarm identifier

    Request Body:
        cleared_by: str - User clearing the alarm
        resolution: str - Resolution description

    Returns:
        Updated alarm info
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    alarm = service.alarms.get(alarm_id)
    if not alarm:
        return jsonify({"error": "Alarm not found"}), 404

    data = request.get_json() or {}
    cleared_by = data.get('cleared_by', 'operator')
    resolution = data.get('resolution', 'Resolved')

    try:
        alarm.active = False
        alarm.cleared_at = datetime.now()

        logger.info(f"Alarm {alarm_id} cleared by {cleared_by}: {resolution}")

        return jsonify({
            "success": True,
            "message": f"Alarm cleared: {resolution}",
            "alarm": service._alarm_to_dict(alarm)
        })

    except Exception as e:
        logger.error(f"Failed to clear alarm: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Factory Status Endpoints
# =============================================================================

@bp.route('/status', methods=['GET'])
def get_factory_status():
    """
    Get overall factory status.

    Returns:
        Factory-wide status overview
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    return jsonify(service.get_factory_status())


@bp.route('/metrics', methods=['GET'])
def get_factory_metrics():
    """
    Get factory-wide performance metrics.

    Query Parameters:
        hours: int - Hours to look back (default 24)

    Returns:
        Factory metrics
    """
    service = get_factory_service()
    if not service:
        return jsonify({"error": "Factory service not available"}), 503

    hours = int(request.args.get('hours', 24))

    try:
        cutoff = datetime.now() - timedelta(hours=hours)

        # Jobs in time range
        recent_jobs = [j for j in service.jobs.values()
                      if j.submit_time >= cutoff]

        completed_jobs = [j for j in recent_jobs if j.status == 'completed']
        failed_jobs = [j for j in recent_jobs if j.status == 'failed']

        # Calculate metrics
        total_parts = sum(j.part_count for j in completed_jobs)
        total_scrap = sum(j.scrap_count for j in completed_jobs)
        total_cycle_time = sum(
            (j.end_time - j.start_time).total_seconds()
            for j in completed_jobs if j.start_time and j.end_time
        )

        # Cell utilization
        online_cells = [c for c in service.cells.values()
                       if c.status.value == 'online']
        avg_utilization = (
            sum(c.utilization_percent for c in online_cells) / len(online_cells)
            if online_cells else 0
        )

        return jsonify({
            "period_hours": hours,
            "jobs": {
                "submitted": len(recent_jobs),
                "completed": len(completed_jobs),
                "failed": len(failed_jobs),
                "pending": len([j for j in recent_jobs if j.status == 'pending']),
                "running": len([j for j in recent_jobs if j.status == 'running'])
            },
            "production": {
                "total_parts": total_parts,
                "total_scrap": total_scrap,
                "yield_percent": ((total_parts - total_scrap) / total_parts * 100)
                                if total_parts > 0 else 100.0,
                "avg_cycle_time_seconds": total_cycle_time / len(completed_jobs)
                                          if completed_jobs else 0
            },
            "cells": {
                "total": len(service.cells),
                "online": len(online_cells),
                "avg_utilization_percent": avg_utilization
            },
            "alarms": {
                "active": len([a for a in service.alarms.values() if a.active]),
                "total_period": len([a for a in service.alarms.values()
                                    if a.timestamp >= cutoff])
            }
        })

    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/health', methods=['GET'])
def health_check():
    """
    Check factory service health.

    Returns:
        Health status
    """
    service = get_factory_service()

    return jsonify({
        "service": "ok" if service else "unavailable",
        "cells_registered": len(service.cells) if service else 0,
        "active_jobs": len([j for j in service.jobs.values()
                          if j.status in ['pending', 'running']]) if service else 0,
        "active_alarms": len([a for a in service.alarms.values()
                             if a.active]) if service else 0
    })
