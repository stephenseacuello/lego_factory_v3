"""
Historical Playback API Routes
==============================
REST API endpoints for recording and replaying factory operations.

Endpoints:
- POST /api/playback/record/start - Start recording
- POST /api/playback/record/stop - Stop recording
- GET /api/playback/recordings - List recordings
- GET /api/playback/recordings/<id> - Get recording details
- DELETE /api/playback/recordings/<id> - Delete recording
- POST /api/playback/play - Start playback
- POST /api/playback/pause - Pause playback
- POST /api/playback/stop - Stop playback
- POST /api/playback/seek - Seek to timestamp
- GET /api/playback/status - Get playback status
"""

import asyncio
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from typing import Optional

logger = logging.getLogger(__name__)

# Blueprint for historical playback routes
bp = Blueprint('historical_playback', __name__, url_prefix='/api/playback')

# Lazy service initialization
_playback_service = None


def get_playback_service():
    """Get or create the historical playback service instance."""
    global _playback_service
    if _playback_service is None:
        try:
            from services.historical_playback_service import HistoricalPlaybackService
            _playback_service = HistoricalPlaybackService()
            logger.info("Historical playback service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize playback service: {e}")
            return None
    return _playback_service


# =============================================================================
# Recording Endpoints
# =============================================================================

@bp.route('/record/start', methods=['POST'])
def start_recording():
    """
    Start recording factory operations.

    Request Body:
        name: str - Recording name
        description: str - Optional description
        tags: list - Optional tags for filtering

    Returns:
        Recording session info
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    data = request.get_json() or {}
    name = data.get('name')

    if not name:
        return jsonify({"error": "name is required"}), 400

    description = data.get('description')
    tags = data.get('tags', [])

    try:
        recording = service.start_recording(
            name=name,
            description=description,
            tags=tags
        )

        return jsonify({
            "success": True,
            "message": "Recording started",
            "recording": {
                "id": recording.id,
                "name": recording.name,
                "description": recording.description,
                "start_time": recording.start_time.isoformat(),
                "tags": recording.tags
            }
        })

    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/record/stop', methods=['POST'])
def stop_recording():
    """
    Stop current recording.

    Request Body:
        save: bool - Whether to save the recording (default true)

    Returns:
        Final recording info
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    data = request.get_json() or {}
    save = data.get('save', True)

    try:
        recording = service.stop_recording(save=save)

        if not recording:
            return jsonify({"error": "No active recording"}), 400

        return jsonify({
            "success": True,
            "message": "Recording stopped" + (" and saved" if save else " (discarded)"),
            "recording": service._recording_to_dict(recording)
        })

    except Exception as e:
        logger.error(f"Failed to stop recording: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/record/event', methods=['POST'])
def record_event():
    """
    Manually record an event during active recording.

    Request Body:
        event_type: str - Type of event
        source_id: str - Source identifier
        data: dict - Event data

    Returns:
        Confirmation
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    from services.historical_playback_service import RecordingState

    if service.recording_state != RecordingState.RECORDING:
        return jsonify({"error": "No active recording"}), 400

    data = request.get_json() or {}
    event_type_str = data.get('event_type')
    source_id = data.get('source_id')
    event_data = data.get('data', {})

    if not event_type_str or not source_id:
        return jsonify({"error": "event_type and source_id are required"}), 400

    try:
        from services.historical_playback_service import EventType

        # Map string to enum
        type_map = {
            'machine_state': EventType.MACHINE_STATE,
            'robot_position': EventType.ROBOT_POSITION,
            'sensor_data': EventType.SENSOR_DATA,
            'workflow_event': EventType.WORKFLOW_EVENT,
            'alarm': EventType.ALARM,
            'operator_action': EventType.OPERATOR_ACTION,
            'quality_event': EventType.QUALITY_EVENT,
            'material_event': EventType.MATERIAL_EVENT
        }

        event_type = type_map.get(event_type_str.lower())
        if not event_type:
            return jsonify({"error": f"Unknown event type: {event_type_str}"}), 400

        service.record_event(event_type, source_id, event_data)

        return jsonify({
            "success": True,
            "message": "Event recorded",
            "event_count": len(service.current_recording.events) if service.current_recording else 0
        })

    except Exception as e:
        logger.error(f"Failed to record event: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/recordings', methods=['GET'])
def list_recordings():
    """
    List available recordings.

    Query Parameters:
        tag: str - Filter by tag
        limit: int - Max results (default 50)

    Returns:
        List of recordings
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    tag_filter = request.args.get('tag')
    limit = int(request.args.get('limit', 50))

    try:
        recordings = list(service.saved_recordings.values())

        if tag_filter:
            recordings = [r for r in recordings if tag_filter in r.tags]

        # Sort by start time descending
        recordings = sorted(recordings, key=lambda r: r.start_time, reverse=True)[:limit]

        return jsonify({
            "count": len(recordings),
            "recordings": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "start_time": r.start_time.isoformat(),
                    "end_time": r.end_time.isoformat() if r.end_time else None,
                    "duration_seconds": r.duration_seconds,
                    "event_count": len(r.events),
                    "tags": r.tags,
                    "size_bytes": r.compressed_size_bytes
                }
                for r in recordings
            ]
        })

    except Exception as e:
        logger.error(f"Failed to list recordings: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/recordings/<recording_id>', methods=['GET'])
def get_recording(recording_id: str):
    """
    Get details of a specific recording.

    Args:
        recording_id: Recording identifier

    Returns:
        Full recording details
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    recording = service.saved_recordings.get(recording_id)

    if not recording:
        return jsonify({"error": "Recording not found"}), 404

    return jsonify(service._recording_to_dict(recording))


@bp.route('/recordings/<recording_id>', methods=['DELETE'])
def delete_recording(recording_id: str):
    """
    Delete a recording.

    Args:
        recording_id: Recording identifier

    Returns:
        Confirmation
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    if recording_id not in service.saved_recordings:
        return jsonify({"error": "Recording not found"}), 404

    try:
        del service.saved_recordings[recording_id]
        logger.info(f"Recording deleted: {recording_id}")

        return jsonify({
            "success": True,
            "message": f"Recording {recording_id} deleted"
        })

    except Exception as e:
        logger.error(f"Failed to delete recording: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Playback Endpoints
# =============================================================================

@bp.route('/play', methods=['POST'])
def start_playback():
    """
    Start playback of a recording.

    Request Body:
        recording_id: str - Recording to play
        speed: float - Playback speed (0.1 to 10.0, default 1.0)
        start_time: float - Start from this timestamp offset (default 0)
        loop: bool - Loop playback (default false)

    Returns:
        Playback status
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    data = request.get_json() or {}
    recording_id = data.get('recording_id')

    if not recording_id:
        return jsonify({"error": "recording_id is required"}), 400

    speed = data.get('speed', 1.0)
    start_time = data.get('start_time', 0.0)
    loop = data.get('loop', False)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                service.start_playback(
                    recording_id=recording_id,
                    speed=speed,
                    start_time=start_time
                )
            )
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "message": "Playback started",
            "status": service.get_playback_status()
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to start playback: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/pause', methods=['POST'])
def pause_playback():
    """
    Pause or resume playback.

    Returns:
        Updated playback status
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    try:
        service.pause_playback()

        return jsonify({
            "success": True,
            "message": "Playback paused/resumed",
            "status": service.get_playback_status()
        })

    except Exception as e:
        logger.error(f"Failed to pause playback: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/stop', methods=['POST'])
def stop_playback():
    """
    Stop playback.

    Returns:
        Confirmation
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    try:
        service.stop_playback()

        return jsonify({
            "success": True,
            "message": "Playback stopped"
        })

    except Exception as e:
        logger.error(f"Failed to stop playback: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/seek', methods=['POST'])
def seek_playback():
    """
    Seek to a specific timestamp in playback.

    Request Body:
        timestamp: float - Timestamp offset in seconds

    Returns:
        Updated playback status
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    data = request.get_json() or {}
    timestamp = data.get('timestamp')

    if timestamp is None:
        return jsonify({"error": "timestamp is required"}), 400

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(service.seek_to(float(timestamp)))
        finally:
            loop.close()

        return jsonify({
            "success": True,
            "message": f"Seeked to {timestamp}s",
            "status": service.get_playback_status()
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to seek: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/speed', methods=['POST'])
def set_playback_speed():
    """
    Set playback speed.

    Request Body:
        speed: float - Playback speed (0.1 to 10.0)

    Returns:
        Updated playback status
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    data = request.get_json() or {}
    speed = data.get('speed')

    if speed is None:
        return jsonify({"error": "speed is required"}), 400

    try:
        service.set_playback_speed(float(speed))

        return jsonify({
            "success": True,
            "message": f"Playback speed set to {speed}x",
            "status": service.get_playback_status()
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to set speed: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/status', methods=['GET'])
def get_playback_status():
    """
    Get current playback and recording status.

    Returns:
        Current status of playback/recording
    """
    service = get_playback_service()
    if not service:
        return jsonify({"error": "Playback service not available"}), 503

    from services.historical_playback_service import RecordingState

    status = {
        "recording": {
            "state": service.recording_state.value,
            "active": service.recording_state == RecordingState.RECORDING,
            "current_recording": None
        },
        "playback": service.get_playback_status()
    }

    if service.current_recording:
        status["recording"]["current_recording"] = {
            "id": service.current_recording.id,
            "name": service.current_recording.name,
            "event_count": len(service.current_recording.events),
            "start_time": service.current_recording.start_time.isoformat()
        }

    return jsonify(status)


@bp.route('/health', methods=['GET'])
def health_check():
    """
    Check playback service health.

    Returns:
        Health status
    """
    service = get_playback_service()

    return jsonify({
        "service": "ok" if service else "unavailable",
        "recording_count": len(service.saved_recordings) if service else 0,
        "storage_path": str(service.storage_path) if service else None
    })
