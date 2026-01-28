"""
Sensor Routes Module
====================
API routes for Arduino sensor recorder operations and sensor dashboard.

Authentication:
- GET /status: optional_auth (public read)
- POST operations: require_auth with appropriate permissions

Endpoints:
- /status: Sensor recorder status
- /start, /stop, /pause, /resume: Recorder control
- /registry: Sensor registry (list all registered sensors)
- /registry/<id>: Single sensor details
- /registry/<id>/approve: Admin approve sensor
- /registry/<id>/disable: Disable sensor
- /current: Current readings for all approved sensors
- /categories: List sensor categories
- /health: Sensor health summary
- /history/sessions: List recorded sessions
- /history/session/<session_id>: Get session data
- /history/compare: Compare multiple sessions
- /history/analytics: Statistical analysis

Author: Flask CNC SCADA System
"""

import os
import glob
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Blueprint, jsonify, request, render_template

from config import get_config

from core.controllers.sensor_controller import SensorRecorder
from services.influxdb_service import InfluxDBService
from services.sensor_registry_service import get_sensor_registry_service
from services.auth_service import (
    require_auth,
    require_permission,
    optional_auth
)

# Create blueprint
bp = Blueprint('sensor', __name__)

# Load configuration
config = get_config()

# Global recorder instance
sensor_recorder = SensorRecorder()
influx_service = InfluxDBService()


# =============================================================================
# Historical Data Helper Functions
# =============================================================================

def _get_session_files():
    """Get all sensor session CSV files from logs directory."""
    log_dir = config.LOG_DIR
    sessions = []

    # Find all sensor data files
    patterns = [
        os.path.join(log_dir, '*_sensor.csv'),
        os.path.join(log_dir, '*_sensor_data_*.csv'),
        os.path.join(log_dir, 'demo_sensor_data_*.csv'),
    ]

    seen = set()
    for pattern in patterns:
        for filepath in glob.glob(pattern):
            if filepath in seen:
                continue
            seen.add(filepath)

            filename = os.path.basename(filepath)
            stat = os.stat(filepath)

            # Parse session info from filename
            session_id = filename.replace('.csv', '')

            # Try to extract experiment name and trial
            parts = session_id.split('_')
            experiment = parts[0] if len(parts) > 1 else 'unknown'

            sessions.append({
                'id': session_id,
                'filename': filename,
                'filepath': filepath,
                'experiment': experiment,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })

    # Also check for aligned files (multi-sensor)
    aligned_pattern = os.path.join(log_dir, '*_aligned.csv')
    for filepath in glob.glob(aligned_pattern):
        if filepath in seen:
            continue
        seen.add(filepath)

        filename = os.path.basename(filepath)
        stat = os.stat(filepath)
        session_id = filename.replace('.csv', '')

        sessions.append({
            'id': session_id,
            'filename': filename,
            'filepath': filepath,
            'experiment': session_id.split('_')[0],
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'aligned': True,
        })

    # Sort by modified time, newest first
    sessions.sort(key=lambda x: x['modified'], reverse=True)
    return sessions


def _load_session_data(filepath: str, start_idx: int = 0, limit: int = 1000,
                       sensors: list = None, modalities: list = None):
    """
    Load sensor session data from CSV with optional filtering.

    Args:
        filepath: Path to CSV file
        start_idx: Starting row index for pagination
        limit: Maximum rows to return
        sensors: Filter to specific sensor IDs
        modalities: Filter to specific modalities (Ax, Ay, Temperature, etc.)

    Returns:
        Dict with data, metadata, and pagination info
    """
    try:
        # Read CSV header first to get column info
        df_header = pd.read_csv(filepath, nrows=0)
        all_columns = df_header.columns.tolist()

        # Determine file type and parse sensors
        detected_sensors = set()
        is_aligned = '_aligned' in filepath or any('.' in col for col in all_columns)

        if is_aligned:
            # Multi-sensor aligned file: columns like "xa_motor.Ax", "frame_r1.Temperature"
            for col in all_columns:
                if '.' in col:
                    sensor_id = col.split('.')[0]
                    detected_sensors.add(sensor_id)
        else:
            # Single-sensor or raw file with 'id' column
            pass

        # Build column filter
        columns_to_read = None
        if sensors or modalities:
            columns_to_read = []
            # Always include timestamp column
            if 'ts_ms' in all_columns:
                columns_to_read.append('ts_ms')
            if 't_host' in all_columns:
                columns_to_read.append('t_host')
            if 'id' in all_columns:
                columns_to_read.append('id')
            if 'port' in all_columns:
                columns_to_read.append('port')

            for col in all_columns:
                if '.' in col:
                    sensor_id, modality = col.split('.', 1)
                    if sensors and sensor_id not in sensors:
                        continue
                    if modalities and modality not in modalities:
                        continue
                    columns_to_read.append(col)
                elif modalities and col in modalities:
                    columns_to_read.append(col)

        # Read data with pagination
        df = pd.read_csv(
            filepath,
            usecols=columns_to_read,
            skiprows=range(1, start_idx + 1) if start_idx > 0 else None,
            nrows=limit
        )

        # Get total row count (approximate for large files)
        total_rows = sum(1 for _ in open(filepath)) - 1  # -1 for header

        # Convert to records
        records = df.to_dict(orient='records')

        # Clean NaN values
        for record in records:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None

        return {
            'data': records,
            'columns': df.columns.tolist(),
            'sensors': list(detected_sensors),
            'total_rows': total_rows,
            'start_idx': start_idx,
            'limit': limit,
            'has_more': start_idx + limit < total_rows,
        }

    except Exception as e:
        return {
            'error': str(e),
            'data': [],
            'columns': [],
            'sensors': [],
            'total_rows': 0,
        }


def _compute_session_analytics(filepath: str, sensors: list = None):
    """
    Compute statistical analytics for a session.

    Args:
        filepath: Path to CSV file
        sensors: Filter to specific sensors

    Returns:
        Dict with statistical analysis per sensor/modality
    """
    try:
        df = pd.read_csv(filepath)
        analytics = {
            'summary': {},
            'sensors': {},
            'anomalies': [],
            'trends': {},
        }

        # Get numeric columns only
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

        # Overall summary
        analytics['summary'] = {
            'total_samples': len(df),
            'duration_ms': None,
            'sample_rate_hz': None,
        }

        # Calculate duration if timestamp available
        if 'ts_ms' in df.columns:
            ts_col = 'ts_ms'
            analytics['summary']['duration_ms'] = float(df[ts_col].max() - df[ts_col].min())
            if analytics['summary']['duration_ms'] > 0:
                analytics['summary']['sample_rate_hz'] = round(
                    len(df) / (analytics['summary']['duration_ms'] / 1000), 2
                )

        # Per-column statistics
        for col in numeric_cols:
            if col in ['ts_ms', 't_host']:
                continue

            # Parse sensor.modality format
            if '.' in col:
                sensor_id, modality = col.split('.', 1)
            else:
                sensor_id = 'default'
                modality = col

            if sensors and sensor_id not in sensors:
                continue

            if sensor_id not in analytics['sensors']:
                analytics['sensors'][sensor_id] = {}

            series = df[col].dropna()
            if len(series) == 0:
                continue

            analytics['sensors'][sensor_id][modality] = {
                'min': float(series.min()),
                'max': float(series.max()),
                'mean': float(series.mean()),
                'std': float(series.std()),
                'median': float(series.median()),
                'q25': float(series.quantile(0.25)),
                'q75': float(series.quantile(0.75)),
                'count': int(len(series)),
            }

            # Detect anomalies (values > 3 std from mean)
            mean = series.mean()
            std = series.std()
            if std > 0:
                anomaly_mask = (series - mean).abs() > 3 * std
                anomaly_count = anomaly_mask.sum()
                if anomaly_count > 0:
                    analytics['anomalies'].append({
                        'sensor': sensor_id,
                        'modality': modality,
                        'count': int(anomaly_count),
                        'percent': round(100 * anomaly_count / len(series), 2),
                    })

            # Simple trend detection (linear regression slope)
            if len(series) > 10:
                x = np.arange(len(series))
                slope = np.polyfit(x, series.values, 1)[0]
                if sensor_id not in analytics['trends']:
                    analytics['trends'][sensor_id] = {}
                analytics['trends'][sensor_id][modality] = {
                    'slope': float(slope),
                    'direction': 'increasing' if slope > 0.001 else 'decreasing' if slope < -0.001 else 'stable',
                }

        return analytics

    except Exception as e:
        return {'error': str(e)}


@bp.route('/status')
@optional_auth
def get_status():
    """
    Get sensor recorder status.

    Auth: Optional

    Returns:
        JSON with recorder status
    """
    status = sensor_recorder.status()
    return jsonify({
        "success": True,
        "status": status
    })


@bp.route('/start', methods=['POST'])
@require_auth
@require_permission('view_sensors')
def start_recording():
    """
    Start sensor recording.

    Auth: Requires 'view_sensors' permission (operator+)

    Request JSON:
        {
            "ports": ["/dev/ttyACM0", "/dev/ttyACM1"],
            "baud": 115200,          # optional
            "experiment_name": "test", # optional
            "trial_number": 1         # optional
        }

    Returns:
        JSON with start result
    """
    data = request.get_json() or {}
    ports = data.get('ports', [])
    baud = data.get('baud')
    experiment_name = data.get('experiment_name', '')
    trial_number = data.get('trial_number')

    if not ports:
        return jsonify({
            "success": False,
            "error": "At least one port is required"
        }), 400

    # Set session tags for InfluxDB
    if influx_service.is_available():
        influx_service.set_session_tags(experiment_name, trial_number)

    success, message = sensor_recorder.start(
        ports=ports,
        baud=baud,
        experiment_name=experiment_name,
        trial_number=trial_number
    )

    return jsonify({
        "success": success,
        "message": message
    })


@bp.route('/stop', methods=['POST'])
@require_auth
@require_permission('view_sensors')
def stop_recording():
    """
    Stop sensor recording.

    Auth: Requires 'view_sensors' permission (operator+)

    Returns:
        JSON with stop result
    """
    success, message = sensor_recorder.stop()

    return jsonify({
        "success": success,
        "message": message
    })


@bp.route('/pause', methods=['POST'])
@require_auth
@require_permission('view_sensors')
def pause_recording():
    """
    Pause sensor recording.

    Auth: Requires 'view_sensors' permission (operator+)

    Returns:
        JSON with pause result
    """
    success, message = sensor_recorder.pause()

    return jsonify({
        "success": success,
        "message": message
    })


@bp.route('/resume', methods=['POST'])
@require_auth
@require_permission('view_sensors')
def resume_recording():
    """
    Resume sensor recording after pause.

    Auth: Requires 'view_sensors' permission (operator+)

    Returns:
        JSON with resume result
    """
    success, message = sensor_recorder.resume()

    return jsonify({
        "success": success,
        "message": message
    })


# =============================================================================
# Sensor Registry Endpoints
# =============================================================================

@bp.route('/registry')
@optional_auth
def get_registry():
    """
    Get all registered sensors.

    Query params:
        status: Filter by status (pending_approval, approved, disabled)

    Returns:
        JSON with list of registered sensors
    """
    registry_service = get_sensor_registry_service()
    status = request.args.get('status')

    sensors = registry_service.get_registry(status=status)

    return jsonify({
        "success": True,
        "sensors": sensors,
        "count": len(sensors)
    })


@bp.route('/registry/<sensor_id>')
@optional_auth
def get_sensor_details(sensor_id: str):
    """
    Get details for a single sensor.

    Args:
        sensor_id: Sensor identifier

    Returns:
        JSON with sensor details
    """
    registry_service = get_sensor_registry_service()
    sensor = registry_service.get_sensor(sensor_id)

    if not sensor:
        return jsonify({
            "success": False,
            "error": f"Sensor {sensor_id} not found"
        }), 404

    return jsonify({
        "success": True,
        "sensor": sensor
    })


@bp.route('/registry/<sensor_id>/approve', methods=['POST'])
@require_auth
@require_permission('manage_sensors')
def approve_sensor(sensor_id: str):
    """
    Approve a pending sensor.

    Auth: Requires 'manage_sensors' permission (admin)

    Args:
        sensor_id: Sensor identifier

    Returns:
        JSON with approval result
    """
    registry_service = get_sensor_registry_service()

    # Get approver from auth context
    approved_by = request.headers.get('X-User-ID', 'admin')

    success, message = registry_service.approve_sensor(sensor_id, approved_by)

    if not success:
        return jsonify({
            "success": False,
            "error": message
        }), 400

    return jsonify({
        "success": True,
        "message": message
    })


@bp.route('/registry/<sensor_id>/disable', methods=['POST'])
@require_auth
@require_permission('manage_sensors')
def disable_sensor(sensor_id: str):
    """
    Disable a sensor.

    Auth: Requires 'manage_sensors' permission (admin)

    Args:
        sensor_id: Sensor identifier

    Returns:
        JSON with disable result
    """
    registry_service = get_sensor_registry_service()
    success, message = registry_service.disable_sensor(sensor_id)

    if not success:
        return jsonify({
            "success": False,
            "error": message
        }), 400

    return jsonify({
        "success": True,
        "message": message
    })


@bp.route('/current')
@optional_auth
def get_current_readings():
    """
    Get current readings for all approved sensors.

    Query params:
        all: If 'true', include non-approved sensors

    Returns:
        JSON with current sensor readings
    """
    registry_service = get_sensor_registry_service()
    approved_only = request.args.get('all', 'false').lower() != 'true'

    readings = registry_service.get_current_readings(approved_only=approved_only)

    return jsonify({
        "success": True,
        "readings": readings,
        "count": len(readings)
    })


@bp.route('/categories')
@optional_auth
def get_categories():
    """
    Get sensor categories with counts.

    Returns:
        JSON with list of categories
    """
    registry_service = get_sensor_registry_service()
    categories = registry_service.get_categories()

    return jsonify({
        "success": True,
        "categories": categories
    })


@bp.route('/health')
@optional_auth
def get_health():
    """
    Get sensor health summary.

    Returns:
        JSON with health counts (online, offline, pending)
    """
    registry_service = get_sensor_registry_service()
    health = registry_service.get_health_summary()

    return jsonify({
        "success": True,
        **health
    })


# =============================================================================
# Historical Data Endpoints
# =============================================================================

@bp.route('/history/sessions')
@optional_auth
def get_history_sessions():
    """
    List all recorded sensor sessions.

    Query params:
        experiment: Filter by experiment name
        limit: Max number of sessions to return (default: 50)

    Returns:
        JSON with list of available sessions
    """
    experiment = request.args.get('experiment')
    limit = int(request.args.get('limit', 50))

    sessions = _get_session_files()

    # Filter by experiment if specified
    if experiment:
        sessions = [s for s in sessions if s.get('experiment', '').startswith(experiment)]

    # Apply limit
    sessions = sessions[:limit]

    return jsonify({
        "success": True,
        "sessions": sessions,
        "count": len(sessions)
    })


@bp.route('/history/session/<session_id>')
@optional_auth
def get_history_session_data(session_id: str):
    """
    Get data from a specific recorded session.

    Args:
        session_id: Session identifier (filename without .csv)

    Query params:
        start: Start row index for pagination (default: 0)
        limit: Max rows to return (default: 1000, max: 10000)
        sensors: Comma-separated sensor IDs to include
        modalities: Comma-separated modalities to include (Ax, Temperature, etc.)
        downsample: Downsample factor (e.g., 10 = every 10th sample)

    Returns:
        JSON with session data and metadata
    """
    # Find session file
    sessions = _get_session_files()
    session = next((s for s in sessions if s['id'] == session_id), None)

    if not session:
        return jsonify({
            "success": False,
            "error": f"Session {session_id} not found"
        }), 404

    # Parse query params
    start_idx = int(request.args.get('start', 0))
    limit = min(int(request.args.get('limit', 1000)), 10000)
    sensors = request.args.get('sensors', '').split(',') if request.args.get('sensors') else None
    modalities = request.args.get('modalities', '').split(',') if request.args.get('modalities') else None
    downsample = int(request.args.get('downsample', 1))

    # Load data
    result = _load_session_data(
        session['filepath'],
        start_idx=start_idx,
        limit=limit * downsample,  # Read more if downsampling
        sensors=sensors,
        modalities=modalities
    )

    # Apply downsampling
    if downsample > 1 and result.get('data'):
        result['data'] = result['data'][::downsample]
        result['downsampled'] = True
        result['downsample_factor'] = downsample

    # Add session metadata
    result['session'] = session

    return jsonify({
        "success": True,
        **result
    })


@bp.route('/history/session/<session_id>/analytics')
@optional_auth
def get_session_analytics(session_id: str):
    """
    Get statistical analytics for a session.

    Args:
        session_id: Session identifier

    Query params:
        sensors: Comma-separated sensor IDs to analyze

    Returns:
        JSON with statistical analysis (min, max, mean, std, anomalies, trends)
    """
    # Find session file
    sessions = _get_session_files()
    session = next((s for s in sessions if s['id'] == session_id), None)

    if not session:
        return jsonify({
            "success": False,
            "error": f"Session {session_id} not found"
        }), 404

    sensors = request.args.get('sensors', '').split(',') if request.args.get('sensors') else None

    analytics = _compute_session_analytics(session['filepath'], sensors=sensors)

    return jsonify({
        "success": True,
        "session_id": session_id,
        **analytics
    })


@bp.route('/history/compare')
@optional_auth
def compare_sessions():
    """
    Compare analytics across multiple sessions.

    Query params:
        sessions: Comma-separated session IDs to compare (required)
        sensors: Comma-separated sensor IDs to include
        modalities: Comma-separated modalities to compare

    Returns:
        JSON with comparative analytics per session
    """
    session_ids = request.args.get('sessions', '').split(',')
    if not session_ids or not session_ids[0]:
        return jsonify({
            "success": False,
            "error": "At least one session ID required"
        }), 400

    sensors = request.args.get('sensors', '').split(',') if request.args.get('sensors') else None
    modalities = request.args.get('modalities', '').split(',') if request.args.get('modalities') else None

    all_sessions = _get_session_files()
    comparison = {
        'sessions': {},
        'summary': {
            'modalities': {},
        }
    }

    for session_id in session_ids:
        session = next((s for s in all_sessions if s['id'] == session_id), None)
        if not session:
            continue

        analytics = _compute_session_analytics(session['filepath'], sensors=sensors)
        comparison['sessions'][session_id] = {
            'metadata': session,
            'analytics': analytics
        }

        # Aggregate modality stats across sessions for comparison
        for sensor_id, sensor_data in analytics.get('sensors', {}).items():
            for modality, stats in sensor_data.items():
                if modalities and modality not in modalities:
                    continue

                key = f"{sensor_id}.{modality}"
                if key not in comparison['summary']['modalities']:
                    comparison['summary']['modalities'][key] = []

                comparison['summary']['modalities'][key].append({
                    'session': session_id,
                    **stats
                })

    return jsonify({
        "success": True,
        **comparison
    })


@bp.route('/history/playback/<session_id>')
@optional_auth
def get_playback_data(session_id: str):
    """
    Get session data optimized for playback visualization.

    Returns downsampled data for the full session timeline,
    suitable for chart rendering and scrubbing.

    Args:
        session_id: Session identifier

    Query params:
        points: Target number of data points (default: 500)
        sensors: Comma-separated sensor IDs
        modalities: Comma-separated modalities

    Returns:
        JSON with timeline data for playback
    """
    # Find session file
    sessions = _get_session_files()
    session = next((s for s in sessions if s['id'] == session_id), None)

    if not session:
        return jsonify({
            "success": False,
            "error": f"Session {session_id} not found"
        }), 404

    target_points = int(request.args.get('points', 500))
    sensors = request.args.get('sensors', '').split(',') if request.args.get('sensors') else None
    modalities = request.args.get('modalities', '').split(',') if request.args.get('modalities') else None

    try:
        # Load full session for playback
        df = pd.read_csv(session['filepath'])
        total_rows = len(df)

        # Calculate downsample factor
        downsample = max(1, total_rows // target_points)

        # Downsample
        if downsample > 1:
            df = df.iloc[::downsample]

        # Filter columns if specified
        columns_to_keep = []
        if 'ts_ms' in df.columns:
            columns_to_keep.append('ts_ms')

        for col in df.columns:
            if col == 'ts_ms':
                continue
            if '.' in col:
                sensor_id, modality = col.split('.', 1)
                if sensors and sensor_id not in sensors:
                    continue
                if modalities and modality not in modalities:
                    continue
            elif modalities and col not in modalities:
                continue
            columns_to_keep.append(col)

        if columns_to_keep:
            df = df[columns_to_keep]

        # Convert to records
        records = df.to_dict(orient='records')

        # Clean NaN values
        for record in records:
            for key, value in list(record.items()):
                if pd.isna(value):
                    record[key] = None

        return jsonify({
            "success": True,
            "session": session,
            "data": records,
            "total_rows": total_rows,
            "displayed_rows": len(records),
            "downsample_factor": downsample,
            "columns": df.columns.tolist(),
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@bp.route('/history/session/<session_id>/download')
@optional_auth
def download_session(session_id):
    """
    Download a sensor session CSV file.

    Args:
        session_id: Session identifier (filename without extension)

    Returns:
        CSV file download
    """
    sessions = _get_session_files()
    session = next((s for s in sessions if s['id'] == session_id), None)

    if not session:
        return jsonify({
            "success": False,
            "error": f"Session {session_id} not found"
        }), 404

    try:
        from flask import send_file
        return send_file(
            session['filepath'],
            mimetype='text/csv',
            as_attachment=True,
            download_name=session['filename']
        )
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# Sensor Dashboard Page
# =============================================================================

@bp.route('/dashboard')
@optional_auth
def sensors_dashboard():
    """
    Render the sensor dashboard page.

    Returns:
        HTML sensor dashboard page
    """
    return render_template('sensors.html')
