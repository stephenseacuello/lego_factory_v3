"""
Time-Lapse Replay API Routes
REST API endpoints for recording and playing back machining operations.
Part of Feature 2.3: Time-Lapse Replay (Phase 2)
"""

import logging
from flask import Blueprint, jsonify, request, send_file
from typing import Dict
import io

logger = logging.getLogger(__name__)

# Global service reference
time_lapse_service = None


def init_time_lapse_routes(app, service):
    """
    Initialize time-lapse routes with service dependency.

    Args:
        app: Flask application instance
        service: TimeLapseService instance
    """
    global time_lapse_service
    time_lapse_service = service

    bp = create_time_lapse_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/time-lapse')
    logger.info("[TimeLapse] Routes initialized")


def create_time_lapse_blueprint() -> Blueprint:
    """Create and configure time-lapse blueprint"""
    bp = Blueprint('time_lapse', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = time_lapse_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'time_lapse',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[TimeLapse] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/<recording_id>/snapshots', methods=['POST'])
    def store_snapshot(recording_id: str):
        """
        Store a time-lapse snapshot.

        Request Body:
        {
            "machine_id": "CNC-001",
            "snapshot_index": 0,
            "time_offset": 0.0,
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0},
            "forces": {"tangential": 0.0, "radial": 0.0, "axial": 0.0},
            "vibration": {"x": 0.0, "y": 0.0, "z": 0.0, "magnitude": 0.0},
            "chip_load": {"chip_load": 0.0, "feed_rate": 0.0, "spindle_speed": 0.0}
        }

        Returns:
            201: Snapshot stored
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'machine_id' not in data:
                return jsonify({'error': 'machine_id required'}), 400

            machine_id = data.pop('machine_id')

            success = time_lapse_service.store_snapshot(recording_id, machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Snapshot stored',
                    'recording_id': recording_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to store snapshot'
                }), 500

        except Exception as e:
            logger.error(f"[TimeLapse] Error storing snapshot: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<recording_id>/metadata', methods=['POST'])
    def store_metadata(recording_id: str):
        """
        Store recording metadata.

        Request Body:
        {
            "machine_id": "CNC-001",
            "machine_name": "Bantam CNC",
            "operator_name": "John Doe",
            "program_name": "Part_001.nc",
            "duration": 120.5,
            "snapshot_count": 1205,
            "capture_interval": 0.1,
            "total_bytes": 500000
        }

        Returns:
            201: Metadata stored
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'machine_id' not in data:
                return jsonify({'error': 'machine_id required'}), 400

            machine_id = data.pop('machine_id')

            success = time_lapse_service.store_recording_metadata(
                recording_id, machine_id, data
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Metadata stored',
                    'recording_id': recording_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to store metadata'
                }), 500

        except Exception as e:
            logger.error(f"[TimeLapse] Error storing metadata: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<recording_id>/snapshots', methods=['GET'])
    def get_snapshots(recording_id: str):
        """
        Get snapshots for a recording.

        Query Parameters:
            start_time: Start time
            end_time: End time
            limit: Maximum snapshots (default: 10000)

        Returns:
            200: Snapshot data
            500: Server error
        """
        try:
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            limit = request.args.get('limit', 10000, type=int)

            snapshots = time_lapse_service.get_recording_snapshots(
                recording_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            return jsonify({
                'recording_id': recording_id,
                'count': len(snapshots),
                'snapshots': snapshots
            }), 200

        except Exception as e:
            logger.error(f"[TimeLapse] Error retrieving snapshots: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<recording_id>/metadata', methods=['GET'])
    def get_metadata(recording_id: str):
        """
        Get recording metadata.

        Returns:
            200: Metadata
            404: Recording not found
            500: Server error
        """
        try:
            metadata = time_lapse_service.get_recording_metadata(recording_id)

            if metadata:
                return jsonify({
                    'success': True,
                    'recording_id': recording_id,
                    'metadata': metadata
                }), 200
            else:
                return jsonify({
                    'error': f'Recording not found: {recording_id}'
                }), 404

        except Exception as e:
            logger.error(f"[TimeLapse] Error retrieving metadata: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/recordings', methods=['GET'])
    def list_recordings():
        """
        List available recordings.

        Query Parameters:
            machine_id: Filter by machine (optional)
            start_time: Start time (optional)
            end_time: End time (optional)
            limit: Maximum recordings (default: 100)

        Returns:
            200: List of recordings
            500: Server error
        """
        try:
            machine_id = request.args.get('machine_id')
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            limit = request.args.get('limit', 100, type=int)

            recordings = time_lapse_service.list_recordings(
                machine_id=machine_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            return jsonify({
                'count': len(recordings),
                'recordings': recordings
            }), 200

        except Exception as e:
            logger.error(f"[TimeLapse] Error listing recordings: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<recording_id>/statistics', methods=['GET'])
    def get_recording_statistics(recording_id: str):
        """
        Get statistics for a recording.

        Returns:
            200: Statistics data
            404: Recording not found
            500: Server error
        """
        try:
            stats = time_lapse_service.get_recording_statistics(recording_id)

            if 'error' in stats:
                return jsonify(stats), 404 if stats['error'] == 'Recording not found' else 500

            return jsonify({
                'success': True,
                'data': stats
            }), 200

        except Exception as e:
            logger.error(f"[TimeLapse] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<recording_id>', methods=['DELETE'])
    def delete_recording(recording_id: str):
        """
        Delete a recording.

        Returns:
            200: Recording deleted
            500: Server error
        """
        try:
            success = time_lapse_service.delete_recording(recording_id)

            if success:
                return jsonify({
                    'success': True,
                    'message': f'Recording deleted: {recording_id}'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to delete recording'
                }), 500

        except Exception as e:
            logger.error(f"[TimeLapse] Error deleting recording: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<recording_id>/export', methods=['GET'])
    def export_recording(recording_id: str):
        """
        Export recording as JSON file.

        Returns:
            200: JSON file
            404: Recording not found
            500: Server error
        """
        try:
            json_data = time_lapse_service.export_recording_json(recording_id)

            if json_data:
                # Create in-memory file
                file_obj = io.BytesIO(json_data.encode('utf-8'))
                file_obj.seek(0)

                return send_file(
                    file_obj,
                    mimetype='application/json',
                    as_attachment=True,
                    download_name=f'{recording_id}.json'
                )
            else:
                return jsonify({
                    'error': f'Recording not found: {recording_id}'
                }), 404

        except Exception as e:
            logger.error(f"[TimeLapse] Error exporting recording: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_service_statistics():
        """
        Get time-lapse service statistics.

        Returns:
            200: Service statistics
        """
        try:
            stats = time_lapse_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[TimeLapse] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Time-Lapse Replay API',
    'version': '1.0.0',
    'description': 'REST API for recording and replaying machining operations',
    'base_path': '/api/v1/time-lapse',
    'endpoints': [
        {
            'path': '/health',
            'method': 'GET',
            'description': 'Health check endpoint'
        },
        {
            'path': '/<recording_id>/snapshots',
            'method': 'POST',
            'description': 'Store time-lapse snapshot'
        },
        {
            'path': '/<recording_id>/metadata',
            'method': 'POST',
            'description': 'Store recording metadata'
        },
        {
            'path': '/<recording_id>/snapshots',
            'method': 'GET',
            'description': 'Get recording snapshots'
        },
        {
            'path': '/<recording_id>/metadata',
            'method': 'GET',
            'description': 'Get recording metadata'
        },
        {
            'path': '/recordings',
            'method': 'GET',
            'description': 'List available recordings'
        },
        {
            'path': '/<recording_id>/statistics',
            'method': 'GET',
            'description': 'Get recording statistics'
        },
        {
            'path': '/<recording_id>',
            'method': 'DELETE',
            'description': 'Delete recording'
        },
        {
            'path': '/<recording_id>/export',
            'method': 'GET',
            'description': 'Export recording as JSON'
        },
        {
            'path': '/statistics',
            'method': 'GET',
            'description': 'Get service statistics'
        }
    ]
}
