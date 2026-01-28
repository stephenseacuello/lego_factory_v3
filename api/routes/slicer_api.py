"""
LEGO Factory v3 - Slicer API
=============================
REST API endpoints for 3D model slicing service.
"""

import logging
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
import io

logger = logging.getLogger(__name__)

slicer_api_bp = Blueprint('slicer_api', __name__, url_prefix='/api/slicer')


def get_client():
    """Get slicer client (lazy import to avoid circular deps)."""
    try:
        from services.lego.slicer_client import get_slicer_client
        return get_slicer_client()
    except Exception as e:
        logger.error(f"Failed to get slicer client: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Health & Status
# ─────────────────────────────────────────────────────────────────────────────

@slicer_api_bp.route('/health', methods=['GET'])
@jwt_required()
def health_check():
    """Check slicer service health."""
    client = get_client()
    if not client:
        return jsonify({
            'status': 'unavailable',
            'error': 'Slicer client not initialized',
        }), 503

    try:
        health = client.health_check()
        return jsonify(health)
    except Exception as e:
        return jsonify({
            'status': 'unavailable',
            'error': str(e),
        }), 503


@slicer_api_bp.route('/status', methods=['GET'])
@jwt_required()
def service_status():
    """Get slicer service status."""
    client = get_client()
    if not client:
        return jsonify({'available': False})

    return jsonify({
        'available': client.is_available(),
        'base_url': client.base_url,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Profile Management
# ─────────────────────────────────────────────────────────────────────────────

@slicer_api_bp.route('/profiles', methods=['GET'])
@jwt_required()
def list_profiles():
    """List available slicer profiles."""
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    try:
        profiles = client.list_profiles()
        return jsonify({
            'profiles': profiles,
            'count': len(profiles),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@slicer_api_bp.route('/profiles/<name>', methods=['GET'])
@jwt_required()
def get_profile(name: str):
    """Get a specific slicer profile."""
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    try:
        profile = client.get_profile(name)
        if profile:
            return jsonify(profile)
        return jsonify({'error': 'Profile not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@slicer_api_bp.route('/profiles/<name>', methods=['PUT'])
@jwt_required()
def save_profile(name: str):
    """Save or update a slicer profile."""
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No profile data provided'}), 400

    try:
        if client.save_profile(name, data):
            return jsonify({'status': 'saved', 'name': name})
        return jsonify({'error': 'Failed to save profile'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Model Analysis
# ─────────────────────────────────────────────────────────────────────────────

@slicer_api_bp.route('/analyze', methods=['POST'])
@jwt_required()
def analyze_model():
    """
    Analyze a 3D model file.

    Accepts multipart/form-data with 'file' field containing STL/3MF/OBJ.

    Returns geometry information including:
    - Volume, surface area
    - Dimensions and bounds
    - Vertex/face counts
    - Mesh validity
    """
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        file_content = file.read()
        analysis = client.analyze_model(
            file_content=file_content,
            filename=file.filename,
        )

        return jsonify({
            'valid': analysis.valid,
            'volume_mm3': analysis.volume_mm3,
            'surface_area_mm2': analysis.surface_area_mm2,
            'dimensions_mm': analysis.dimensions_mm,
            'bounds_mm': analysis.bounds_mm,
            'vertex_count': analysis.vertex_count,
            'face_count': analysis.face_count,
            'is_watertight': analysis.is_watertight,
            'euler_number': analysis.euler_number,
            'error': analysis.error,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@slicer_api_bp.route('/estimate', methods=['POST'])
@jwt_required()
def estimate_print():
    """
    Estimate print time and material usage.

    Accepts multipart/form-data with:
    - file: STL/3MF/OBJ file
    - profile: (optional) Profile name for estimation

    Returns rough estimates without full slicing.
    """
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    profile = request.form.get('profile', 'lego_pla_quality')

    try:
        file_content = file.read()
        estimate = client.estimate_print_time(
            file_content=file_content,
            filename=file.filename,
            profile=profile,
        )
        return jsonify(estimate)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Slicing Jobs
# ─────────────────────────────────────────────────────────────────────────────

@slicer_api_bp.route('/slice', methods=['POST'])
@jwt_required()
def submit_slice_job():
    """
    Submit a model for slicing.

    Accepts multipart/form-data with:
    - file: STL/3MF/OBJ file (required)
    - profile: Profile name (default: lego_pla_quality)
    - engine: Slicer engine (auto, prusaslicer, curaengine)
    - metadata: JSON string with additional metadata

    Returns job information with ID for tracking.
    """
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    profile = request.form.get('profile', 'lego_pla_quality')
    engine = request.form.get('engine', 'auto')

    # Parse metadata
    metadata = {}
    if request.form.get('metadata'):
        import json
        try:
            metadata = json.loads(request.form['metadata'])
        except json.JSONDecodeError:
            pass

    try:
        from services.lego.slicer_client import SlicerEngine as SE
        file_content = file.read()

        job = client.submit_slice_job(
            file_content=file_content,
            filename=file.filename,
            profile=profile,
            engine=SE(engine),
            metadata=metadata,
        )

        return jsonify({
            'job_id': job.job_id,
            'status': job.status.value,
            'profile': job.profile_name,
            'engine': job.engine.value,
            'created_at': job.created_at.isoformat(),
        }), 202

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@slicer_api_bp.route('/jobs', methods=['GET'])
@jwt_required()
def list_jobs():
    """List slicing jobs with optional status filter."""
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    status_str = request.args.get('status')
    limit = int(request.args.get('limit', 100))

    try:
        from services.lego.slicer_client import JobStatus
        status = JobStatus(status_str) if status_str else None

        jobs = client.list_jobs(status=status, limit=limit)

        return jsonify({
            'jobs': [{
                'job_id': j.job_id,
                'status': j.status.value,
                'profile': j.profile_name,
                'progress': j.progress,
                'created_at': j.created_at.isoformat(),
                'completed_at': j.completed_at.isoformat() if j.completed_at else None,
                'error': j.error,
            } for j in jobs],
            'count': len(jobs),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@slicer_api_bp.route('/jobs/<job_id>', methods=['GET'])
@jwt_required()
def get_job(job_id: str):
    """Get job status and details."""
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    try:
        job = client.get_job(job_id)

        return jsonify({
            'job_id': job.job_id,
            'status': job.status.value,
            'engine': job.engine.value,
            'profile': job.profile_name,
            'progress': job.progress,
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'error': job.error,
            'metadata': job.metadata,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@slicer_api_bp.route('/jobs/<job_id>', methods=['DELETE'])
@jwt_required()
def cancel_job(job_id: str):
    """Cancel a pending slicing job."""
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    try:
        if client.cancel_job(job_id):
            return jsonify({'status': 'cancelled', 'job_id': job_id})
        return jsonify({'error': 'Cannot cancel job'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@slicer_api_bp.route('/jobs/<job_id>/gcode', methods=['GET'])
@jwt_required()
def download_gcode(job_id: str):
    """Download generated G-code for a completed job."""
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    try:
        gcode = client.download_gcode(job_id)

        return send_file(
            io.BytesIO(gcode),
            mimetype='text/plain',
            as_attachment=True,
            download_name=f"{job_id}.gcode",
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# LEGO Brick Slicing
# ─────────────────────────────────────────────────────────────────────────────

@slicer_api_bp.route('/brick/slice', methods=['POST'])
@jwt_required()
def slice_brick():
    """
    Slice a LEGO brick model with material-specific settings.

    Accepts multipart/form-data with:
    - file: STL file of the brick
    - brick_id: Brick identifier (e.g., 'brick_2x4')
    - material: Material type (PLA, ABS, PETG)
    - quality: Quality level (draft, standard, quality)

    Returns slicing job information.
    """
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    brick_id = request.form.get('brick_id', 'custom_brick')
    material = request.form.get('material', 'PLA').upper()
    quality = request.form.get('quality', 'quality')

    # Map material to profile
    profile_map = {
        'PLA': 'lego_pla_quality',
        'ABS': 'lego_abs_functional',
        'PETG': 'lego_petg_durable',
    }
    profile = profile_map.get(material, 'lego_pla_quality')

    try:
        from services.lego.slicer_client import SlicerEngine as SE
        file_content = file.read()

        job = client.submit_slice_job(
            file_content=file_content,
            filename=f"{brick_id}.stl",
            profile=profile,
            engine=SE.AUTO,
            metadata={
                'brick_id': brick_id,
                'material': material,
                'quality': quality,
                'type': 'lego_brick',
            },
        )

        return jsonify({
            'job_id': job.job_id,
            'status': job.status.value,
            'brick_id': brick_id,
            'material': material,
            'quality': quality,
            'profile': profile,
            'created_at': job.created_at.isoformat(),
        }), 202

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@slicer_api_bp.route('/brick/batch', methods=['POST'])
@jwt_required()
def slice_brick_batch():
    """
    Submit multiple brick models for slicing.

    Accepts JSON with:
    - bricks: List of {brick_id, stl_url or stl_base64}
    - material: Material for all bricks
    - quality: Quality level

    Returns list of job IDs.
    """
    client = get_client()
    if not client:
        return jsonify({'error': 'Slicer service unavailable'}), 503

    data = request.get_json()
    if not data or 'bricks' not in data:
        return jsonify({'error': 'No bricks provided'}), 400

    bricks = data['bricks']
    material = data.get('material', 'PLA').upper()
    quality = data.get('quality', 'quality')

    profile_map = {
        'PLA': 'lego_pla_quality',
        'ABS': 'lego_abs_functional',
        'PETG': 'lego_petg_durable',
    }
    profile = profile_map.get(material, 'lego_pla_quality')

    jobs = []

    for brick in bricks:
        brick_id = brick.get('brick_id', 'unknown')

        # Get STL content (either from base64 or fetch from URL)
        stl_content = None
        if 'stl_base64' in brick:
            import base64
            stl_content = base64.b64decode(brick['stl_base64'])
        elif 'stl_url' in brick:
            # Would fetch from URL in production
            continue

        if not stl_content:
            continue

        try:
            from services.lego.slicer_client import SlicerEngine as SE

            job = client.submit_slice_job(
                file_content=stl_content,
                filename=f"{brick_id}.stl",
                profile=profile,
                engine=SE.AUTO,
                metadata={
                    'brick_id': brick_id,
                    'material': material,
                    'quality': quality,
                    'type': 'lego_brick_batch',
                },
            )

            jobs.append({
                'brick_id': brick_id,
                'job_id': job.job_id,
                'status': job.status.value,
            })

        except Exception as e:
            jobs.append({
                'brick_id': brick_id,
                'error': str(e),
            })

    return jsonify({
        'jobs': jobs,
        'total': len(jobs),
        'material': material,
        'quality': quality,
    }), 202
