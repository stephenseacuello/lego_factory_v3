"""
G-Code API Routes for Flask CNC SCADA
======================================
REST API for G-code file upload, job management, and Fusion 360 integration.

Endpoints:
    POST   /api/gcode/upload     - Upload G-code file
    GET    /api/gcode/jobs       - List all jobs
    GET    /api/gcode/jobs/<id>  - Get job details
    DELETE /api/gcode/jobs/<id>  - Delete job
    POST   /api/gcode/jobs/<id>/cancel - Cancel job
    GET    /api/gcode/queue      - Get queue status
    POST   /api/gcode/send       - One-click send from Fusion 360
"""

import os
import logging
from flask import Blueprint, request, jsonify, current_app

from services.gcode_service import (
    get_gcode_service,
    JobStatus,
    JobPriority
)
from services.auth_service import require_auth, require_role, get_current_user
from api.utils.validation import safe_path_join, validate_in_directory

logger = logging.getLogger(__name__)

bp = Blueprint('gcode', __name__, url_prefix='/api/gcode')


@bp.route('/upload', methods=['POST'])
@require_auth
def upload_gcode():
    """
    Upload a G-code file.

    Request:
        - multipart/form-data with 'file' field
        - Optional 'priority' field (low, normal, high, urgent)

    Response:
        - 201: Job created with job details
        - 400: Bad request (no file, invalid file)
        - 500: Server error
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    # Get priority
    priority_str = request.form.get('priority', 'normal').lower()
    priority_map = {
        'low': JobPriority.LOW,
        'normal': JobPriority.NORMAL,
        'high': JobPriority.HIGH,
        'urgent': JobPriority.URGENT
    }
    priority = priority_map.get(priority_str, JobPriority.NORMAL)

    # Get operator ID from auth
    user = get_current_user()
    operator_id = user.username if user else None

    # Upload file
    service = get_gcode_service()
    job, error = service.upload_file(
        file_content=file.read(),
        filename=file.filename,
        priority=priority,
        operator_id=operator_id
    )

    if error:
        return jsonify({'error': error}), 400

    logger.info(f"G-code uploaded: {job.filename} by {operator_id}")

    return jsonify({
        'message': 'File uploaded successfully',
        'job': job.to_dict()
    }), 201


@bp.route('/send', methods=['POST'])
@require_auth
def send_from_fusion():
    """
    One-click send from Fusion 360.

    This endpoint is designed for the Fusion 360 add-in to send
    G-code directly after post-processing.

    Request JSON:
        {
            "filename": "part_op1.nc",
            "gcode": "G0 X0 Y0\\nG1 Z-1 F100\\n...",
            "priority": "normal",
            "metadata": {
                "operation": "Adaptive Clearing",
                "tool": "T1 - 6mm Flat",
                "material": "Aluminum 6061",
                "estimated_time": "00:05:30"
            }
        }

    Response:
        - 201: Job created
        - 400: Bad request
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    filename = data.get('filename')
    gcode = data.get('gcode')

    if not filename or not gcode:
        return jsonify({'error': 'filename and gcode are required'}), 400

    # Get priority
    priority_str = data.get('priority', 'normal').lower()
    priority_map = {
        'low': JobPriority.LOW,
        'normal': JobPriority.NORMAL,
        'high': JobPriority.HIGH,
        'urgent': JobPriority.URGENT
    }
    priority = priority_map.get(priority_str, JobPriority.NORMAL)

    # Get operator
    user = get_current_user()
    operator_id = user.username if user else None

    # Convert G-code string to bytes
    gcode_bytes = gcode.encode('utf-8')

    # Upload
    service = get_gcode_service()
    job, error = service.upload_file(
        file_content=gcode_bytes,
        filename=filename,
        priority=priority,
        operator_id=operator_id
    )

    if error:
        return jsonify({'error': error}), 400

    # Log Fusion 360 metadata if provided
    fusion_meta = data.get('metadata', {})
    if fusion_meta:
        logger.info(f"Fusion 360 metadata: {fusion_meta}")

    return jsonify({
        'message': 'G-code sent successfully',
        'job': job.to_dict(),
        'fusion_metadata': fusion_meta
    }), 201


@bp.route('/jobs', methods=['GET'])
@require_auth
def list_jobs():
    """
    List all jobs.

    Query Parameters:
        - status: Filter by status (queued, running, completed, etc.)
        - limit: Maximum number of jobs to return (default 50)

    Response:
        - 200: List of jobs
    """
    status_filter = request.args.get('status')
    limit = int(request.args.get('limit', 50))

    service = get_gcode_service()

    if status_filter:
        try:
            status = JobStatus(status_filter)
            jobs = service.get_all_jobs(status=status)
        except ValueError:
            return jsonify({'error': f'Invalid status: {status_filter}'}), 400
    else:
        jobs = service.get_all_jobs()

    # Sort by created_at descending and limit
    jobs = sorted(jobs, key=lambda j: j.created_at, reverse=True)[:limit]

    return jsonify({
        'jobs': [job.to_dict() for job in jobs],
        'total': len(jobs)
    })


@bp.route('/jobs/<job_id>', methods=['GET'])
@require_auth
def get_job(job_id: str):
    """
    Get job details by ID.

    Response:
        - 200: Job details
        - 404: Job not found
    """
    service = get_gcode_service()
    job = service.get_job(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    # Include time accuracy if completed
    response = {'job': job.to_dict()}

    if job.status == JobStatus.COMPLETED:
        accuracy = service.get_time_accuracy(job_id)
        if accuracy:
            response['time_accuracy'] = accuracy

    return jsonify(response)


@bp.route('/jobs/<job_id>', methods=['DELETE'])
@require_auth
@require_role('maintenance')
def delete_job(job_id: str):
    """
    Delete a job.

    Response:
        - 200: Job deleted
        - 400: Cannot delete running job
        - 404: Job not found
    """
    service = get_gcode_service()
    job = service.get_job(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job.status == JobStatus.RUNNING:
        return jsonify({'error': 'Cannot delete running job'}), 400

    if service.delete_job(job_id):
        return jsonify({'message': 'Job deleted'})
    else:
        return jsonify({'error': 'Failed to delete job'}), 500


@bp.route('/jobs/<job_id>/cancel', methods=['POST'])
@require_auth
def cancel_job(job_id: str):
    """
    Cancel a queued or running job.

    Response:
        - 200: Job cancelled
        - 400: Cannot cancel (wrong status)
        - 404: Job not found
    """
    service = get_gcode_service()
    job = service.get_job(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PAUSED):
        return jsonify({'error': f'Cannot cancel job in {job.status.value} status'}), 400

    if service.cancel_job(job_id):
        return jsonify({
            'message': 'Job cancelled',
            'job': service.get_job(job_id).to_dict()
        })
    else:
        return jsonify({'error': 'Failed to cancel job'}), 500


@bp.route('/queue', methods=['GET'])
@require_auth
def get_queue_status():
    """
    Get current queue status.

    Response:
        - 200: Queue statistics
    """
    service = get_gcode_service()
    status = service.get_queue_status()

    return jsonify(status)


@bp.route('/next', methods=['GET'])
@require_auth
@require_role('operator')
def get_next_job():
    """
    Get the next job in queue (highest priority).

    This does not remove the job from queue - use /jobs/<id>/start for that.

    Response:
        - 200: Next job details
        - 204: No jobs in queue
    """
    service = get_gcode_service()

    # Peek at queue without removing
    jobs = service.get_all_jobs(status=JobStatus.QUEUED)
    if not jobs:
        return '', 204

    # Sort by priority
    next_job = min(jobs, key=lambda j: j.priority.value)

    return jsonify({'next_job': next_job.to_dict()})


@bp.route('/jobs/<job_id>/start', methods=['POST'])
@require_auth
@require_role('operator')
def start_job(job_id: str):
    """
    Start running a job.

    Request JSON (optional):
        {
            "machine_id": "cnc-01"
        }

    Response:
        - 200: Job started
        - 400: Cannot start (wrong status)
        - 404: Job not found
    """
    service = get_gcode_service()
    job = service.get_job(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job.status != JobStatus.QUEUED:
        return jsonify({'error': f'Cannot start job in {job.status.value} status'}), 400

    # Get machine ID from request
    data = request.get_json() or {}
    machine_id = data.get('machine_id')
    if machine_id:
        job.machine_id = machine_id

    if service.update_job_status(job_id, JobStatus.RUNNING):
        return jsonify({
            'message': 'Job started',
            'job': service.get_job(job_id).to_dict()
        })
    else:
        return jsonify({'error': 'Failed to start job'}), 500


@bp.route('/jobs/<job_id>/complete', methods=['POST'])
@require_auth
@require_role('operator')
def complete_job(job_id: str):
    """
    Mark a job as completed.

    Response:
        - 200: Job completed with time accuracy
        - 400: Cannot complete (wrong status)
        - 404: Job not found
    """
    service = get_gcode_service()
    job = service.get_job(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if job.status != JobStatus.RUNNING:
        return jsonify({'error': f'Cannot complete job in {job.status.value} status'}), 400

    if service.update_job_status(job_id, JobStatus.COMPLETED):
        job = service.get_job(job_id)
        accuracy = service.get_time_accuracy(job_id)

        return jsonify({
            'message': 'Job completed',
            'job': job.to_dict(),
            'time_accuracy': accuracy
        })
    else:
        return jsonify({'error': 'Failed to complete job'}), 500


@bp.route('/jobs/<job_id>/progress', methods=['POST'])
@require_auth
def update_progress(job_id: str):
    """
    Update job progress (current line number).

    Request JSON:
        {
            "current_line": 150
        }

    Response:
        - 200: Progress updated
        - 404: Job not found
    """
    service = get_gcode_service()
    job = service.get_job(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    data = request.get_json() or {}
    current_line = data.get('current_line', 0)

    service.update_job_progress(job_id, current_line)
    job = service.get_job(job_id)

    return jsonify({
        'progress': {
            'current_line': job.current_line,
            'total_lines': job.total_lines,
            'percent': job.progress_percent
        }
    })


# =============================================================================
# Toolpath Visualization Endpoints
# =============================================================================

@bp.route('/visualize', methods=['POST'])
@require_auth
def visualize_gcode():
    """
    Generate 3D toolpath visualization from G-code.

    Request JSON:
        {
            "gcode": "G0 X0 Y0\\nG1 X10 F100\\n...",
            "current_position": {"x": 0, "y": 0, "z": 0},
            "soft_limits": {...},
            "wcs_offset": {"x": 0, "y": 0, "z": 0},
            "executed_line": 0
        }

    Response:
        - 200: Plotly data and layout
        - 400: Bad request
    """
    from services.toolpath_visualizer import get_toolpath_visualizer

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    gcode = data.get('gcode')
    if not gcode:
        return jsonify({'error': 'gcode is required'}), 400

    visualizer = get_toolpath_visualizer()

    try:
        plot_data = visualizer.generate_plot(
            gcode_content=gcode,
            current_position=data.get('current_position'),
            soft_limits=data.get('soft_limits'),
            wcs_offset=data.get('wcs_offset'),
            executed_line=data.get('executed_line')
        )

        stats = visualizer.get_statistics()

        return jsonify({
            'plot': plot_data,
            'statistics': stats
        })

    except Exception as e:
        logger.error(f"Visualization error: {e}")
        return jsonify({'error': str(e)}), 400


@bp.route('/visualize/file/<job_id>', methods=['GET'])
@require_auth
def visualize_job(job_id: str):
    """
    Generate 3D visualization for a job's G-code file.

    Query Parameters:
        - current_position: JSON string of position
        - executed_line: Current line being executed

    Response:
        - 200: Plotly data
        - 404: Job not found
    """
    from services.toolpath_visualizer import get_toolpath_visualizer

    service = get_gcode_service()
    job = service.get_job(job_id)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    # Read G-code file (with path traversal protection)
    from config import config

    filepath = safe_path_join(config.GCODE_DIR, job.filename)
    if not filepath:
        logger.warning(f"Path traversal attempt in visualization: {job.filename}")
        return jsonify({'error': 'Invalid file path'}), 400

    if not os.path.exists(filepath):
        return jsonify({'error': 'G-code file not found'}), 404

    # Double-check path is within allowed directory
    if not validate_in_directory(filepath, config.GCODE_DIR):
        logger.warning(f"Path validation failed: {filepath}")
        return jsonify({'error': 'Access denied'}), 403

    with open(filepath, 'r') as f:
        gcode = f.read()

    # Get optional parameters
    import json
    current_pos = request.args.get('current_position')
    if current_pos:
        try:
            current_pos = json.loads(current_pos)
        except json.JSONDecodeError:
            current_pos = None

    executed_line = request.args.get('executed_line', type=int)

    visualizer = get_toolpath_visualizer()

    try:
        plot_data = visualizer.generate_plot(
            gcode_content=gcode,
            current_position=current_pos,
            executed_line=executed_line
        )

        stats = visualizer.get_statistics()

        return jsonify({
            'job_id': job_id,
            'filename': job.filename,
            'plot': plot_data,
            'statistics': stats
        })

    except Exception as e:
        logger.error(f"Visualization error for job {job_id}: {e}")
        return jsonify({'error': str(e)}), 400


@bp.route('/parse', methods=['POST'])
@require_auth
def parse_gcode():
    """
    Parse G-code and return structured segment data.

    Request JSON:
        {
            "gcode": "G0 X0 Y0\\nG1 X10 F100\\n..."
        }

    Response:
        - 200: Parsed segments and statistics
        - 400: Bad request
    """
    from services.gcode_parser_service import GCodeParser

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    gcode = data.get('gcode')
    if not gcode:
        return jsonify({'error': 'gcode is required'}), 400

    parser = GCodeParser()

    try:
        parser.parse(gcode)

        # Convert segments to dict format
        segments = []
        for seg in parser.segments:
            segments.append({
                'line_number': seg.line_number,
                'gcode': seg.gcode,
                'move_type': seg.move_type,
                'feedrate': seg.feedrate,
                'point_count': len(seg.points),
                'start': {'x': seg.points[0].x, 'y': seg.points[0].y, 'z': seg.points[0].z},
                'end': {'x': seg.points[-1].x, 'y': seg.points[-1].y, 'z': seg.points[-1].z}
            })

        return jsonify({
            'segments': segments,
            'total_segments': len(segments),
            'bounds': parser.get_bounds()
        })

    except Exception as e:
        logger.error(f"Parse error: {e}")
        return jsonify({'error': str(e)}), 400


@bp.route('/backplot/load', methods=['POST'])
@require_auth
def load_backplot():
    """
    Load G-code into backplot manager for real-time tracking.

    Request JSON:
        {
            "gcode": "G0 X0 Y0\\n..."
        }

    Response:
        - 200: Backplot loaded
    """
    from services.toolpath_visualizer import get_backplot_manager

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    gcode = data.get('gcode')
    if not gcode:
        return jsonify({'error': 'gcode is required'}), 400

    manager = get_backplot_manager()
    manager.load_gcode(gcode)

    return jsonify({
        'success': True,
        'message': 'Backplot loaded'
    })


@bp.route('/backplot/update', methods=['POST'])
@require_auth
def update_backplot():
    """
    Update backplot with current position and line number.

    Request JSON:
        {
            "position": {"x": 0, "y": 0, "z": 0},
            "line_number": 10
        }

    Response:
        - 200: Updated plot data
    """
    from services.toolpath_visualizer import get_backplot_manager
    from services.soft_limits_service import get_soft_limits_service

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400

    position = data.get('position', {})
    line_number = data.get('line_number')

    manager = get_backplot_manager()
    manager.update_position(position, line_number)

    # Get soft limits for overlay
    soft_limits = get_soft_limits_service().get_config()

    plot_data = manager.get_current_plot(soft_limits=soft_limits)

    # Add actual path trace
    actual_trace = manager.get_actual_path_trace()
    if actual_trace:
        plot_data['data'].append(actual_trace)

    return jsonify({
        'plot': plot_data
    })


@bp.route('/backplot/reset', methods=['POST'])
@require_auth
def reset_backplot():
    """Reset backplot state."""
    from services.toolpath_visualizer import get_backplot_manager

    manager = get_backplot_manager()
    manager.reset()

    return jsonify({
        'success': True,
        'message': 'Backplot reset'
    })
