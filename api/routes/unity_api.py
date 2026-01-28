"""
LEGO Factory v3 - Unity Digital Twin API
=========================================
REST and WebSocket API endpoints for Unity Digital Twin integration.

Provides endpoints for:
- Scene state synchronization
- Entity management
- Real-time updates
- Historical playback
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

logger = logging.getLogger(__name__)

unity_api_bp = Blueprint('unity_api', __name__, url_prefix='/api/unity')


def get_unity_service():
    """Get Unity state service."""
    try:
        from services.unity.unity_state_service import get_unity_service
        return get_unity_service()
    except Exception as e:
        logger.warning(f"Unity service not available: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Scene Management
# ─────────────────────────────────────────────────────────────────────────────

@unity_api_bp.route('/scene', methods=['GET'])
@jwt_required()
def get_scene_state():
    """Get complete scene state for Unity."""
    service = get_unity_service()
    if not service:
        return _demo_scene_state()

    scene_id = request.args.get('scene_id')
    state = service.get_scene_state(scene_id)

    if not state:
        return jsonify({'error': 'Scene not found'}), 404

    return jsonify(state)


@unity_api_bp.route('/scenes', methods=['GET'])
@jwt_required()
def list_scenes():
    """List available scenes."""
    service = get_unity_service()
    if not service:
        return jsonify({
            'scenes': [
                {'scene_id': 'factory_floor', 'name': 'LEGO Factory Floor', 'active': True},
            ],
            'count': 1,
        })

    scenes = [{
        'scene_id': s.scene_id,
        'name': s.name,
        'active': s.scene_id == service.active_scene,
        'entity_count': len(s.entities),
    } for s in service.scenes.values()]

    return jsonify({'scenes': scenes, 'count': len(scenes)})


@unity_api_bp.route('/scenes/<scene_id>/activate', methods=['POST'])
@jwt_required()
def activate_scene(scene_id: str):
    """Activate a scene."""
    service = get_unity_service()
    if not service:
        return jsonify({'error': 'Unity service not available'}), 503

    if scene_id not in service.scenes:
        return jsonify({'error': 'Scene not found'}), 404

    service.active_scene = scene_id
    return jsonify({'status': 'activated', 'scene_id': scene_id})


# ─────────────────────────────────────────────────────────────────────────────
# Entity Management
# ─────────────────────────────────────────────────────────────────────────────

@unity_api_bp.route('/entities', methods=['GET'])
@jwt_required()
def list_entities():
    """
    List entities in the scene.

    Query params:
    - type: Filter by entity type (machine, robot, conveyor, etc.)
    - scene_id: Specific scene
    """
    service = get_unity_service()
    if not service:
        return _demo_entities()

    entity_type = request.args.get('type')

    if entity_type:
        entities = service.get_entities_by_type(entity_type)
    else:
        entities = [e.to_dict() for e in service.entities.values()]

    return jsonify({
        'entities': entities,
        'count': len(entities),
    })


@unity_api_bp.route('/entities', methods=['POST'])
@jwt_required()
def create_entity():
    """Create a new entity in the scene."""
    service = get_unity_service()
    if not service:
        return jsonify({'error': 'Unity service not available'}), 503

    data = request.get_json()
    if not data or 'entity_id' not in data:
        return jsonify({'error': 'entity_id required'}), 400

    entity = service.create_entity(data)
    return jsonify(entity), 201


@unity_api_bp.route('/entities/<entity_id>', methods=['GET'])
@jwt_required()
def get_entity(entity_id: str):
    """Get entity state."""
    service = get_unity_service()
    if not service:
        return _demo_entity(entity_id)

    entity = service.get_entity(entity_id)
    if not entity:
        return jsonify({'error': 'Entity not found'}), 404

    return jsonify(entity)


@unity_api_bp.route('/entities/<entity_id>', methods=['PUT'])
@jwt_required()
def update_entity(entity_id: str):
    """
    Update entity state or transform.

    JSON body:
    - state: State updates (dict)
    - transform: Transform updates (position, rotation, scale)
    """
    service = get_unity_service()
    if not service:
        return jsonify({'error': 'Unity service not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    success = service.update_entity(
        entity_id,
        state=data.get('state'),
        transform=data.get('transform'),
    )

    if not success:
        return jsonify({'error': 'Entity not found'}), 404

    return jsonify({'status': 'updated', 'entity_id': entity_id})


@unity_api_bp.route('/entities/<entity_id>', methods=['DELETE'])
@jwt_required()
def delete_entity(entity_id: str):
    """Delete an entity from the scene."""
    service = get_unity_service()
    if not service:
        return jsonify({'error': 'Unity service not available'}), 503

    if service.delete_entity(entity_id):
        return jsonify({'status': 'deleted', 'entity_id': entity_id})

    return jsonify({'error': 'Entity not found'}), 404


# ─────────────────────────────────────────────────────────────────────────────
# Batch Updates
# ─────────────────────────────────────────────────────────────────────────────

@unity_api_bp.route('/batch-update', methods=['POST'])
@jwt_required()
def batch_update():
    """
    Apply batch updates to multiple entities.

    JSON body:
    - updates: List of {entity_id, state?, transform?}
    """
    service = get_unity_service()
    if not service:
        return jsonify({'error': 'Unity service not available'}), 503

    data = request.get_json()
    if not data or 'updates' not in data:
        return jsonify({'error': 'updates required'}), 400

    results = []
    for update in data['updates']:
        entity_id = update.get('entity_id')
        if entity_id:
            success = service.update_entity(
                entity_id,
                state=update.get('state'),
                transform=update.get('transform'),
            )
            results.append({'entity_id': entity_id, 'updated': success})

    return jsonify({'results': results, 'count': len(results)})


# ─────────────────────────────────────────────────────────────────────────────
# Real-time Control
# ─────────────────────────────────────────────────────────────────────────────

@unity_api_bp.route('/service/start', methods=['POST'])
@jwt_required()
def start_service():
    """Start the Unity state service update loop."""
    service = get_unity_service()
    if not service:
        return jsonify({'error': 'Unity service not available'}), 503

    service.start()
    return jsonify({'status': 'started'})


@unity_api_bp.route('/service/stop', methods=['POST'])
@jwt_required()
def stop_service():
    """Stop the Unity state service update loop."""
    service = get_unity_service()
    if not service:
        return jsonify({'error': 'Unity service not available'}), 503

    service.stop()
    return jsonify({'status': 'stopped'})


@unity_api_bp.route('/service/status', methods=['GET'])
@jwt_required()
def service_status():
    """Get Unity service status."""
    service = get_unity_service()

    return jsonify({
        'available': service is not None,
        'running': service._running if service else False,
        'active_scene': service.active_scene if service else None,
        'entity_count': len(service.entities) if service else 0,
        'connected_clients': len(service._unity_clients) if service else 0,
        'update_interval': service.update_interval if service else None,
    })


@unity_api_bp.route('/service/config', methods=['PUT'])
@jwt_required()
def update_config():
    """Update service configuration."""
    service = get_unity_service()
    if not service:
        return jsonify({'error': 'Unity service not available'}), 503

    data = request.get_json() or {}

    if 'update_interval' in data:
        service.update_interval = float(data['update_interval'])

    return jsonify({
        'update_interval': service.update_interval,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Historical Playback
# ─────────────────────────────────────────────────────────────────────────────

def get_playback_service():
    """Get Historical Playback service."""
    try:
        from services.unity.historical_playback_service import get_playback_service
        return get_playback_service()
    except Exception as e:
        logger.warning(f"Playback service not available: {e}")
        return None


@unity_api_bp.route('/playback/states', methods=['GET'])
@jwt_required()
def get_historical_states():
    """
    Get historical states for playback.

    Query params:
    - start_time: Start time (ISO format)
    - end_time: End time (ISO format)
    - entity_id: Optional entity filter
    - interval: Sampling interval in seconds
    """
    service = get_playback_service()
    if not service:
        return jsonify({
            'playback_available': False,
            'message': 'Historical playback service not available',
        }), 503

    start_time_str = request.args.get('start_time')
    end_time_str = request.args.get('end_time')

    if not start_time_str or not end_time_str:
        return jsonify({'error': 'start_time and end_time required'}), 400

    try:
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
    except ValueError as e:
        return jsonify({'error': f'Invalid datetime format: {e}'}), 400

    # Get state at the start time
    state = service.get_state_at_time(start_time)

    return jsonify({
        'playback_available': True,
        'state': state,
        'query': {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
        },
    })


@unity_api_bp.route('/playback/session', methods=['POST'])
@jwt_required()
def create_playback_session():
    """
    Create a new playback session.

    JSON body:
    - start_time: Start time (ISO format, required)
    - end_time: End time (ISO format, required)
    - speed: Playback speed (optional, default 1.0, range 0.1-10.0)
    - preload: Whether to preload data (optional, default true)

    Returns:
    - session: Session details including session_id
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    # Parse required fields
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')

    if not start_time_str or not end_time_str:
        return jsonify({'error': 'start_time and end_time are required'}), 400

    try:
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
    except ValueError as e:
        return jsonify({'error': f'Invalid datetime format: {e}'}), 400

    # Parse optional fields
    speed = data.get('speed', 1.0)
    preload = data.get('preload', True)

    try:
        speed = float(speed)
    except (TypeError, ValueError):
        speed = 1.0

    try:
        session = service.create_playback_session(
            start_time=start_time,
            end_time=end_time,
            speed=speed,
            preload=preload
        )
        return jsonify({
            'status': 'created',
            'session': session.to_dict(),
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating playback session: {e}")
        return jsonify({'error': 'Failed to create playback session'}), 500


@unity_api_bp.route('/playback/sessions', methods=['GET'])
@jwt_required()
def list_playback_sessions():
    """
    List all playback sessions.

    Returns:
    - sessions: List of session details
    - count: Number of sessions
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    sessions = service.list_sessions()
    return jsonify({
        'sessions': sessions,
        'count': len(sessions),
    })


@unity_api_bp.route('/playback/<session_id>/start', methods=['POST'])
@jwt_required()
def start_playback(session_id: str):
    """
    Start playback for a session.

    Returns:
    - status: 'started'
    - session: Updated session details
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    try:
        service.start_playback(session_id)
        status = service.get_session_status(session_id)
        return jsonify({
            'status': 'started',
            'session': status,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error starting playback: {e}")
        return jsonify({'error': 'Failed to start playback'}), 500


@unity_api_bp.route('/playback/<session_id>/pause', methods=['POST'])
@jwt_required()
def pause_playback(session_id: str):
    """
    Pause playback for a session.

    Returns:
    - status: 'paused'
    - session: Updated session details
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    try:
        service.pause_playback(session_id)
        status = service.get_session_status(session_id)
        return jsonify({
            'status': 'paused',
            'session': status,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error pausing playback: {e}")
        return jsonify({'error': 'Failed to pause playback'}), 500


@unity_api_bp.route('/playback/<session_id>/resume', methods=['POST'])
@jwt_required()
def resume_playback(session_id: str):
    """
    Resume paused playback for a session.

    Returns:
    - status: 'resumed'
    - session: Updated session details
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    try:
        service.resume_playback(session_id)
        status = service.get_session_status(session_id)
        return jsonify({
            'status': 'resumed',
            'session': status,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error resuming playback: {e}")
        return jsonify({'error': 'Failed to resume playback'}), 500


@unity_api_bp.route('/playback/<session_id>/stop', methods=['POST'])
@jwt_required()
def stop_playback(session_id: str):
    """
    Stop playback and reset to start.

    Returns:
    - status: 'stopped'
    - session: Updated session details
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    try:
        service.stop_playback(session_id)
        status = service.get_session_status(session_id)
        return jsonify({
            'status': 'stopped',
            'session': status,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error stopping playback: {e}")
        return jsonify({'error': 'Failed to stop playback'}), 500


@unity_api_bp.route('/playback/<session_id>/seek', methods=['POST'])
@jwt_required()
def seek_playback(session_id: str):
    """
    Seek to a specific time in the playback.

    JSON body:
    - target_time: Target timestamp (ISO format, required)

    Returns:
    - status: 'seeked'
    - session: Updated session details
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    data = request.get_json()
    if not data or 'target_time' not in data:
        return jsonify({'error': 'target_time required'}), 400

    try:
        target_time = datetime.fromisoformat(
            data['target_time'].replace('Z', '+00:00')
        )
    except ValueError as e:
        return jsonify({'error': f'Invalid datetime format: {e}'}), 400

    try:
        service.seek_to_time(session_id, target_time)
        status = service.get_session_status(session_id)
        return jsonify({
            'status': 'seeked',
            'session': status,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error seeking playback: {e}")
        return jsonify({'error': 'Failed to seek playback'}), 500


@unity_api_bp.route('/playback/<session_id>/speed', methods=['POST'])
@jwt_required()
def set_playback_speed(session_id: str):
    """
    Set playback speed.

    JSON body:
    - speed: Playback speed (0.1 to 10.0, required)

    Returns:
    - status: 'speed_changed'
    - speed: Actual speed set (clamped to valid range)
    - session: Updated session details
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    data = request.get_json()
    if not data or 'speed' not in data:
        return jsonify({'error': 'speed required'}), 400

    try:
        speed = float(data['speed'])
    except (TypeError, ValueError):
        return jsonify({'error': 'speed must be a number'}), 400

    try:
        actual_speed = service.set_playback_speed(session_id, speed)
        status = service.get_session_status(session_id)
        return jsonify({
            'status': 'speed_changed',
            'speed': actual_speed,
            'session': status,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error setting playback speed: {e}")
        return jsonify({'error': 'Failed to set playback speed'}), 500


@unity_api_bp.route('/playback/<session_id>/status', methods=['GET'])
@jwt_required()
def get_playback_status(session_id: str):
    """
    Get current playback session status.

    Returns:
    - session: Session details including state, progress, etc.
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    try:
        status = service.get_session_status(session_id)
        return jsonify({
            'session': status,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error getting playback status: {e}")
        return jsonify({'error': 'Failed to get playback status'}), 500


@unity_api_bp.route('/playback/<session_id>', methods=['DELETE'])
@jwt_required()
def delete_playback_session(session_id: str):
    """
    Delete a playback session and clean up resources.

    Returns:
    - status: 'deleted'
    - session_id: Deleted session ID
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    try:
        success = service.delete_session(session_id)
        if success:
            return jsonify({
                'status': 'deleted',
                'session_id': session_id,
            })
        else:
            return jsonify({'error': 'Failed to delete session'}), 500

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error deleting playback session: {e}")
        return jsonify({'error': 'Failed to delete playback session'}), 500


@unity_api_bp.route('/playback/<session_id>/state', methods=['GET'])
@jwt_required()
def get_state_at_playback_time(session_id: str):
    """
    Get the factory state at the current playback time.

    Query params:
    - timestamp: Optional specific timestamp (ISO format)
                 If not provided, uses current playback position

    Returns:
    - state: Factory state at the specified time
    - session: Current session status
    """
    service = get_playback_service()
    if not service:
        return jsonify({'error': 'Playback service not available'}), 503

    try:
        status = service.get_session_status(session_id)

        # Check for specific timestamp in query params
        timestamp_str = request.args.get('timestamp')
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(
                    timestamp_str.replace('Z', '+00:00')
                )
            except ValueError as e:
                return jsonify({'error': f'Invalid datetime format: {e}'}), 400
        else:
            timestamp = datetime.fromisoformat(status['current_time'])

        state = service.get_state_at_time(timestamp)

        return jsonify({
            'state': state,
            'session': status,
        })

    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error getting state at playback time: {e}")
        return jsonify({'error': 'Failed to get state'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ML Anomaly Overlay
# ─────────────────────────────────────────────────────────────────────────────

@unity_api_bp.route('/overlays/anomalies', methods=['GET'])
@jwt_required()
def get_anomaly_overlays():
    """Get ML anomaly data for visualization overlay."""
    return jsonify({
        'anomalies': [
            {
                'entity_id': 'printer_2',
                'anomaly_type': 'temperature_drift',
                'confidence': 0.87,
                'detected_at': (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
                'details': 'Extruder temperature 3°C above expected',
            },
        ],
        'count': 1,
    })


@unity_api_bp.route('/overlays/maintenance', methods=['GET'])
@jwt_required()
def get_maintenance_overlays():
    """Get maintenance status for visualization overlay."""
    return jsonify({
        'maintenance_items': [
            {
                'entity_id': 'printer_1',
                'item': 'Nozzle replacement',
                'due_in_hours': 24,
                'priority': 'medium',
            },
            {
                'entity_id': 'niryo_ned2',
                'item': 'Gripper calibration',
                'due_in_hours': 8,
                'priority': 'low',
            },
        ],
        'count': 2,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Demo Data
# ─────────────────────────────────────────────────────────────────────────────

def _demo_scene_state():
    """Return demo scene state."""
    return jsonify({
        'scene_id': 'factory_floor',
        'name': 'LEGO Factory Floor',
        'timestamp': datetime.utcnow().isoformat(),
        'entities': {
            'printer_1': {
                'entity_id': 'printer_1',
                'entity_type': 'machine',
                'name': 'Prusa MK4 #1',
                'transform': {
                    'position': {'x': 0, 'y': 0, 'z': 0},
                    'rotation': {'x': 0, 'y': 0, 'z': 0, 'w': 1},
                    'scale': {'x': 1, 'y': 1, 'z': 1},
                },
                'state': {
                    'status': 'running',
                    'temperature': 205,
                    'bed_temperature': 60,
                    'progress': 0.67,
                    'job_id': 'JOB-20240115-001',
                },
                'visible': True,
            },
            'printer_2': {
                'entity_id': 'printer_2',
                'entity_type': 'machine',
                'name': 'Prusa MK4 #2',
                'transform': {
                    'position': {'x': 1.5, 'y': 0, 'z': 0},
                    'rotation': {'x': 0, 'y': 0, 'z': 0, 'w': 1},
                    'scale': {'x': 1, 'y': 1, 'z': 1},
                },
                'state': {
                    'status': 'running',
                    'temperature': 208,
                    'bed_temperature': 60,
                    'progress': 0.23,
                    'job_id': 'JOB-20240115-002',
                },
                'visible': True,
            },
            'bambu_x1c': {
                'entity_id': 'bambu_x1c',
                'entity_type': 'machine',
                'name': 'Bambu X1C',
                'transform': {
                    'position': {'x': 3, 'y': 0, 'z': 0},
                    'rotation': {'x': 0, 'y': 0, 'z': 0, 'w': 1},
                    'scale': {'x': 1, 'y': 1, 'z': 1},
                },
                'state': {
                    'status': 'idle',
                    'temperature': 25,
                    'bed_temperature': 25,
                    'progress': 0,
                },
                'visible': True,
            },
            'niryo_ned2': {
                'entity_id': 'niryo_ned2',
                'entity_type': 'robot',
                'name': 'Niryo Ned2',
                'transform': {
                    'position': {'x': -1, 'y': 0, 'z': 1},
                    'rotation': {'x': 0, 'y': 0, 'z': 0, 'w': 1},
                    'scale': {'x': 1, 'y': 1, 'z': 1},
                },
                'state': {
                    'status': 'running',
                    'joint_positions': [0.0, 0.3, -0.5, 0.0, 0.2, 0.0],
                    'gripper_closed': False,
                    'task': 'pick_place',
                },
                'visible': True,
            },
            'xarm_lite6': {
                'entity_id': 'xarm_lite6',
                'entity_type': 'robot',
                'name': 'xArm Lite 6',
                'transform': {
                    'position': {'x': 4, 'y': 0, 'z': 1},
                    'rotation': {'x': 0, 'y': 0, 'z': 0, 'w': 1},
                    'scale': {'x': 1, 'y': 1, 'z': 1},
                },
                'state': {
                    'status': 'idle',
                    'joint_positions': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                    'gripper_closed': True,
                },
                'visible': True,
            },
        },
        'global_state': {
            'active_alarms': 2,
            'alarm_summary': {'critical': 0, 'high': 1, 'medium': 1, 'low': 0},
            'oee': 0.852,
            'work_orders_active': 3,
        },
    })


def _demo_entities():
    """Return demo entities list."""
    scene = _demo_scene_state().get_json()
    return jsonify({
        'entities': list(scene['entities'].values()),
        'count': len(scene['entities']),
    })


def _demo_entity(entity_id: str):
    """Return demo entity."""
    scene = _demo_scene_state().get_json()
    if entity_id in scene['entities']:
        return jsonify(scene['entities'][entity_id])
    return jsonify({'error': 'Entity not found'}), 404
