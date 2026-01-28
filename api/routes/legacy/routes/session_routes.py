"""
Session Routes Module
=====================
API routes for session management and data alignment.

These routes provide a RESTful interface for:
- Creating and managing recording sessions
- Starting/stopping data collection
- Running data alignment
- Downloading aligned datasets

Authentication:
- Public: GET /api/sessions (list only)
- Operator+: Create, start, stop sessions
- Maintenance+: Delete sessions, alignment operations

Author: Flask CNC SCADA System
"""

import os
from pathlib import Path
from flask import Blueprint, jsonify, request, send_file

from config import get_config
from services.session_manager import (
    get_session_manager,
    SessionState,
    AlignmentConfig
)
from services.data_alignment_service import get_alignment_service
from services.gcode_line_tracker import get_line_tracker
from services.auth_service import require_auth, require_role, optional_auth

config = get_config()
bp = Blueprint('session', __name__, url_prefix='/api/session')


@bp.route('', methods=['GET'])
@optional_auth
def list_sessions():
    """
    List all sessions.

    Query params:
        state: Filter by state (created, recording, stopped, completed, error)
        limit: Max sessions to return (default 50)

    Returns:
        JSON list of sessions
    """
    try:
        manager = get_session_manager()

        # Parse query params
        state_filter = request.args.get('state')
        limit = int(request.args.get('limit', 50))

        state = None
        if state_filter:
            try:
                state = SessionState(state_filter)
            except ValueError:
                return jsonify({
                    "success": False,
                    "error": f"Invalid state: {state_filter}. Valid: {[s.value for s in SessionState]}"
                }), 400

        sessions = manager.list_sessions(state=state, limit=limit)

        return jsonify({
            "success": True,
            "sessions": [s.to_dict() for s in sessions],
            "count": len(sessions)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('', methods=['POST'])
@require_auth
@require_role('operator')
def create_session():
    """
    Create a new recording session.

    Request body:
        name: Session name (required)
        gcode_file: G-code file path (optional)
        sources: List of sources to record (optional, default: all)
        metadata: Additional metadata (optional)

    Returns:
        JSON with created session
    """
    try:
        data = request.get_json() or {}

        name = data.get('name')
        if not name:
            return jsonify({
                "success": False,
                "error": "Session name is required"
            }), 400

        gcode_file = data.get('gcode_file')
        sources = data.get('sources')
        metadata = data.get('metadata', {})

        # Validate gcode file if provided
        if gcode_file:
            gcode_path = Path(config.GCODE_DIR) / gcode_file
            if not gcode_path.exists():
                return jsonify({
                    "success": False,
                    "error": f"G-code file not found: {gcode_file}"
                }), 404

        manager = get_session_manager()
        session = manager.create_session(
            name=name,
            gcode_file=str(gcode_path) if gcode_file else None,
            sources=sources,
            metadata=metadata
        )

        # Load G-code into line tracker if provided
        if gcode_file:
            tracker = get_line_tracker()
            tracker.load_program(str(gcode_path))

        return jsonify({
            "success": True,
            "session": session.to_dict()
        }), 201

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<session_id>', methods=['GET'])
@optional_auth
def get_session(session_id: str):
    """
    Get session details.

    Returns:
        JSON with session details
    """
    try:
        manager = get_session_manager()
        session = manager.get_session(session_id)

        return jsonify({
            "success": True,
            "session": session.to_dict()
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<session_id>', methods=['DELETE'])
@require_auth
@require_role('maintenance')
def delete_session(session_id: str):
    """
    Delete a session.

    Query params:
        delete_files: If 'true', also delete associated data files

    Returns:
        JSON success response
    """
    try:
        delete_files = request.args.get('delete_files', 'false').lower() == 'true'

        manager = get_session_manager()
        manager.delete_session(session_id, delete_files=delete_files)

        return jsonify({
            "success": True,
            "message": f"Session {session_id} deleted"
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<session_id>/start', methods=['POST'])
@require_auth
@require_role('operator')
def start_session(session_id: str):
    """
    Start recording for a session.

    Returns:
        JSON with updated session
    """
    try:
        manager = get_session_manager()
        session = manager.start_session(session_id)

        # Start line tracker if G-code loaded
        if session.gcode_file:
            tracker = get_line_tracker()
            tracker.start_session(session_id)

        return jsonify({
            "success": True,
            "session": session.to_dict(),
            "message": f"Recording started with sources: {session.sources}"
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<session_id>/stop', methods=['POST'])
@require_auth
@require_role('operator')
def stop_session(session_id: str):
    """
    Stop recording for a session.

    Returns:
        JSON with updated session and file info
    """
    try:
        manager = get_session_manager()
        session = manager.stop_session(session_id)

        # Stop line tracker
        tracker = get_line_tracker()
        line_events = tracker.stop_session()

        # Export line events to CSV
        if line_events:
            events_path = os.path.join(config.LOG_DIR, f"{session_id}_gcode_lines.csv")
            tracker.export_events_csv(events_path)

        return jsonify({
            "success": True,
            "session": session.to_dict(),
            "line_events_count": len(line_events),
            "message": "Recording stopped"
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<session_id>/align', methods=['POST'])
@require_auth
@require_role('operator')
def align_session(session_id: str):
    """
    Run data alignment for a session.

    Request body (optional):
        master_source: Source for master timeline (default: tinyg)
        interpolation_method: linear, nearest, cubic (default: linear)
        resample_rate_hz: Target sample rate (optional)
        include_gcode_lines: Include G-code line mapping (default: true)

    Returns:
        JSON with alignment result
    """
    try:
        data = request.get_json() or {}

        # Build alignment config
        alignment_config = AlignmentConfig(
            master_source=data.get('master_source', 'tinyg'),
            interpolation_method=data.get('interpolation_method', 'linear'),
            resample_rate_hz=data.get('resample_rate_hz'),
            include_gcode_lines=data.get('include_gcode_lines', True)
        )

        manager = get_session_manager()
        aligned_path = manager.align_session_data(session_id, alignment_config)

        # Get alignment stats
        aligner = get_alignment_service()
        import pandas as pd
        aligned_df = pd.read_csv(aligned_path)
        stats = aligner.get_alignment_stats(aligned_df)

        return jsonify({
            "success": True,
            "aligned_file": aligned_path,
            "stats": stats,
            "message": "Data alignment completed"
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<session_id>/download', methods=['GET'])
@require_auth
@require_role('operator')
def download_aligned(session_id: str):
    """
    Download the aligned CSV for a session.

    Returns:
        File download response
    """
    try:
        manager = get_session_manager()
        session = manager.get_session(session_id)

        if not session.aligned_file:
            return jsonify({
                "success": False,
                "error": "No aligned file available. Run alignment first."
            }), 404

        if not os.path.exists(session.aligned_file):
            return jsonify({
                "success": False,
                "error": "Aligned file not found on disk"
            }), 404

        return send_file(
            session.aligned_file,
            as_attachment=True,
            download_name=f"{session_id}_aligned.csv"
        )

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/<session_id>/files', methods=['GET'])
@optional_auth
def list_session_files(session_id: str):
    """
    List all files associated with a session.

    Returns:
        JSON with file info
    """
    try:
        manager = get_session_manager()
        session = manager.get_session(session_id)

        files = []
        for source, file_info in session.files.items():
            file_data = {
                'source': source,
                'filename': file_info.filename,
                'filepath': file_info.filepath,
                'exists': os.path.exists(file_info.filepath),
                'row_count': file_info.row_count
            }
            if os.path.exists(file_info.filepath):
                file_data['size_bytes'] = os.path.getsize(file_info.filepath)
            files.append(file_data)

        # Add aligned file if exists
        if session.aligned_file:
            aligned_exists = os.path.exists(session.aligned_file)
            files.append({
                'source': 'aligned',
                'filename': os.path.basename(session.aligned_file),
                'filepath': session.aligned_file,
                'exists': aligned_exists,
                'size_bytes': os.path.getsize(session.aligned_file) if aligned_exists else 0
            })

        return jsonify({
            "success": True,
            "session_id": session_id,
            "files": files
        })

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/active', methods=['GET'])
@optional_auth
def get_active_session():
    """
    Get the currently active recording session.

    Returns:
        JSON with active session or null
    """
    try:
        manager = get_session_manager()
        session = manager.get_active_session()

        return jsonify({
            "success": True,
            "session": session.to_dict() if session else None,
            "is_recording": session is not None
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/sources', methods=['GET'])
@optional_auth
def list_available_sources():
    """
    List available data sources for recording.

    Returns:
        JSON with available sources
    """
    try:
        manager = get_session_manager()
        sources = manager.get_registered_sources()

        return jsonify({
            "success": True,
            "sources": sources
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Data Alignment Utility Routes ---

@bp.route('/align', methods=['POST'])
@require_auth
@require_role('operator')
def quick_align():
    """
    Quick alignment of uploaded or existing files.

    Request body:
        tinyg_file: Path to TinyG CSV (optional)
        sensor_file: Path to sensor CSV (optional)
        mcc_file: Path to MCC CSV (optional)
        master_source: Master timeline source (default: tinyg)
        interpolation_method: linear, nearest, cubic (default: linear)

    Returns:
        JSON with alignment result
    """
    try:
        data = request.get_json() or {}

        tinyg_file = data.get('tinyg_file')
        sensor_file = data.get('sensor_file')
        mcc_file = data.get('mcc_file')

        if not any([tinyg_file, sensor_file, mcc_file]):
            return jsonify({
                "success": False,
                "error": "At least one input file is required"
            }), 400

        # Build file paths dict
        file_paths = {}
        for source, filepath in [('tinyg', tinyg_file), ('sensors', sensor_file), ('mcc', mcc_file)]:
            if filepath:
                # Handle relative paths
                if not os.path.isabs(filepath):
                    filepath = os.path.join(config.LOG_DIR, filepath)
                if os.path.exists(filepath):
                    file_paths[source] = filepath
                else:
                    return jsonify({
                        "success": False,
                        "error": f"File not found: {filepath}"
                    }), 404

        # Generate output path
        output_filename = f"aligned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output_path = os.path.join(config.LOG_DIR, output_filename)

        # Run alignment
        aligner = get_alignment_service()
        aligned_df = aligner.align_files(
            file_paths=file_paths,
            output_path=output_path,
            master_source=data.get('master_source', 'tinyg'),
            interpolation_method=data.get('interpolation_method', 'linear')
        )

        stats = aligner.get_alignment_stats(aligned_df)

        return jsonify({
            "success": True,
            "aligned_file": output_path,
            "filename": output_filename,
            "stats": stats
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Standalone Alignment (Sensor + MCC without TinyG) ---

@bp.route('/align/standalone', methods=['POST'])
@require_auth
@require_role('operator')
def standalone_align():
    """
    Standalone alignment of sensor and MCC data (without TinyG).

    Useful for environmental monitoring, calibration runs, or testing.

    Request body:
        sensor_file: Path to sensor CSV (required)
        mcc_file: Path to MCC CSV (optional)
        interpolation_method: linear, nearest (default: linear)

    Returns:
        JSON with alignment result
    """
    try:
        data = request.get_json() or {}

        sensor_file = data.get('sensor_file')
        if not sensor_file:
            return jsonify({
                "success": False,
                "error": "sensor_file is required"
            }), 400

        # Handle relative paths
        if not os.path.isabs(sensor_file):
            sensor_file = os.path.join(config.LOG_DIR, sensor_file)
        if not os.path.exists(sensor_file):
            return jsonify({
                "success": False,
                "error": f"Sensor file not found: {sensor_file}"
            }), 404

        mcc_file = data.get('mcc_file')
        if mcc_file and not os.path.isabs(mcc_file):
            mcc_file = os.path.join(config.LOG_DIR, mcc_file)

        # Generate output path
        output_filename = f"standalone_aligned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output_path = os.path.join(config.LOG_DIR, output_filename)

        # Run standalone alignment
        aligner = get_alignment_service()
        success, message = aligner.align_standalone(
            sensor_file=sensor_file,
            output_file=output_path,
            mcc_file=mcc_file,
            interpolation_method=data.get('interpolation_method', 'linear')
        )

        if not success:
            return jsonify({
                "success": False,
                "error": message
            }), 400

        # Get stats
        import pandas as pd
        aligned_df = pd.read_csv(output_path)
        stats = aligner.get_alignment_stats(aligned_df)

        return jsonify({
            "success": True,
            "aligned_file": output_path,
            "filename": output_filename,
            "stats": stats,
            "message": message
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/align/full', methods=['POST'])
@require_auth
@require_role('operator')
def full_align():
    """
    Full alignment with G-code position-based line matching.

    Matches the old flask_cnc_controller.py DataAligner.align_data() method.
    Uses Euclidean distance to match TinyG positions to G-code lines.

    Request body:
        sensor_file: Path to sensor CSV (required)
        tinyg_file: Path to TinyG status CSV (required)
        gcode_file: Path to G-code file (required)
        mcc_file: Path to MCC CSV (optional)

    Returns:
        JSON with alignment result
    """
    try:
        data = request.get_json() or {}

        sensor_file = data.get('sensor_file')
        tinyg_file = data.get('tinyg_file')
        gcode_file = data.get('gcode_file')
        mcc_file = data.get('mcc_file')

        # Validate required fields
        if not sensor_file:
            return jsonify({"success": False, "error": "sensor_file is required"}), 400
        if not tinyg_file:
            return jsonify({"success": False, "error": "tinyg_file is required"}), 400
        if not gcode_file:
            return jsonify({"success": False, "error": "gcode_file is required"}), 400

        # Resolve paths
        def resolve_path(filepath, base_dir):
            if not filepath:
                return None
            if not os.path.isabs(filepath):
                filepath = os.path.join(base_dir, filepath)
            return filepath

        sensor_file = resolve_path(sensor_file, config.LOG_DIR)
        tinyg_file = resolve_path(tinyg_file, config.LOG_DIR)
        gcode_file = resolve_path(gcode_file, getattr(config, 'GCODE_DIR', config.LOG_DIR))
        mcc_file = resolve_path(mcc_file, config.LOG_DIR) if mcc_file else None

        # Validate files exist
        if not os.path.exists(sensor_file):
            return jsonify({"success": False, "error": f"Sensor file not found: {sensor_file}"}), 404
        if not os.path.exists(tinyg_file):
            return jsonify({"success": False, "error": f"TinyG file not found: {tinyg_file}"}), 404
        if not os.path.exists(gcode_file):
            return jsonify({"success": False, "error": f"G-code file not found: {gcode_file}"}), 404

        # Generate output path
        output_filename = f"full_aligned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        output_path = os.path.join(config.LOG_DIR, output_filename)

        # Run full alignment
        aligner = get_alignment_service()
        success, message = aligner.align_data_full(
            sensor_csv=sensor_file,
            tinyg_csv=tinyg_file,
            gcode_file=gcode_file,
            output_csv=output_path,
            mcc_csv=mcc_file
        )

        if not success:
            return jsonify({
                "success": False,
                "error": message
            }), 400

        # Get stats
        import pandas as pd
        aligned_df = pd.read_csv(output_path)
        stats = aligner.get_alignment_stats(aligned_df)

        return jsonify({
            "success": True,
            "aligned_file": output_path,
            "filename": output_filename,
            "stats": stats,
            "message": message
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Line Tracker Routes ---

@bp.route('/tracker/status', methods=['GET'])
@optional_auth
def tracker_status():
    """
    Get G-code line tracker status.

    Returns:
        JSON with tracker statistics
    """
    try:
        tracker = get_line_tracker()

        return jsonify({
            "success": True,
            "stats": tracker.get_tracking_stats(),
            "program": tracker.get_program_info(),
            "current_line": tracker.get_current_line()
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route('/tracker/events', methods=['GET'])
@optional_auth
def tracker_events():
    """
    Get line tracker events.

    Query params:
        start_line: Start of line range
        end_line: End of line range
        session_only: Only return session events (default: true)

    Returns:
        JSON with line events
    """
    try:
        tracker = get_line_tracker()

        start_line = request.args.get('start_line', type=int)
        end_line = request.args.get('end_line', type=int)
        session_only = request.args.get('session_only', 'true').lower() == 'true'

        if session_only:
            events = tracker.get_session_events()
        else:
            events = tracker.get_line_events(start_line, end_line)

        return jsonify({
            "success": True,
            "events": events,
            "count": len(events)
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Import datetime for quick_align timestamp
from datetime import datetime
