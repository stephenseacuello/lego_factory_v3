"""
Force and Vibration API Routes
REST API endpoints for force and vibration monitoring data.
Part of Feature 2.1: Force/Vibration Visualization (Phase 2)
"""

import logging
from flask import Blueprint, jsonify, request
from typing import Dict

logger = logging.getLogger(__name__)

# Global service reference
force_vibration_service = None


def init_force_vibration_routes(app, service):
    """
    Initialize force/vibration routes with service dependency.

    Args:
        app: Flask application instance
        service: ForceVibrationService instance
    """
    global force_vibration_service
    force_vibration_service = service

    bp = create_force_vibration_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/force-vibration')
    logger.info("[ForceVibration] Routes initialized")


def create_force_vibration_blueprint() -> Blueprint:
    """Create and configure force/vibration blueprint"""
    bp = Blueprint('force_vibration', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = force_vibration_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'force_vibration',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[ForceVibration] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/<machine_id>/force', methods=['POST'])
    def store_force_data(machine_id: str):
        """
        Store cutting force data.

        Request Body:
        {
            "tangential": 150.5,
            "radial": 75.2,
            "axial": 50.1,
            "resultant": 175.3,
            "power": 1250.0
        }

        Returns:
            201: Force data stored
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'No data provided'}), 400

            # Validate required fields
            required_fields = ['tangential', 'radial', 'axial']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400

            success = force_vibration_service.store_force_data(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Force data stored',
                    'machine_id': machine_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to store force data'
                }), 500

        except Exception as e:
            logger.error(f"[ForceVibration] Error storing force data: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/vibration', methods=['POST'])
    def store_vibration_data(machine_id: str):
        """
        Store vibration data.

        Request Body:
        {
            "x": 0.005,
            "y": 0.003,
            "z": 0.004,
            "magnitude": 0.007,
            "frequency": 120.5
        }

        Returns:
            201: Vibration data stored
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'No data provided'}), 400

            # Validate required fields
            required_fields = ['x', 'y', 'z']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400

            success = force_vibration_service.store_vibration_data(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Vibration data stored',
                    'machine_id': machine_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to store vibration data'
                }), 500

        except Exception as e:
            logger.error(f"[ForceVibration] Error storing vibration data: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/force/history', methods=['GET'])
    def get_force_history(machine_id: str):
        """
        Get force history for a machine.

        Query Parameters:
            start_time: Start time (RFC3339 or relative like '-1h')
            end_time: End time (RFC3339 or relative like 'now()')
            limit: Maximum records to return (default: 1000)

        Returns:
            200: Force history data
            500: Server error
        """
        try:
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            limit = request.args.get('limit', 1000, type=int)

            history = force_vibration_service.get_force_history(
                machine_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            return jsonify({
                'machine_id': machine_id,
                'count': len(history),
                'records': history
            }), 200

        except Exception as e:
            logger.error(f"[ForceVibration] Error retrieving force history: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/vibration/history', methods=['GET'])
    def get_vibration_history(machine_id: str):
        """
        Get vibration history for a machine.

        Query Parameters:
            start_time: Start time (RFC3339 or relative like '-1h')
            end_time: End time (RFC3339 or relative like 'now()')
            limit: Maximum records to return (default: 1000)

        Returns:
            200: Vibration history data
            500: Server error
        """
        try:
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            limit = request.args.get('limit', 1000, type=int)

            history = force_vibration_service.get_vibration_history(
                machine_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            return jsonify({
                'machine_id': machine_id,
                'count': len(history),
                'records': history
            }), 200

        except Exception as e:
            logger.error(f"[ForceVibration] Error retrieving vibration history: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/force/statistics', methods=['GET'])
    def get_force_statistics(machine_id: str):
        """
        Get force statistics for a machine.

        Query Parameters:
            time_range: Time range (e.g., '-1h', '-24h', default: '-1h')

        Returns:
            200: Force statistics
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-1h')

            stats = force_vibration_service.analyze_force_statistics(
                machine_id,
                time_range=time_range
            )

            if 'error' in stats:
                return jsonify(stats), 500

            return jsonify({
                'success': True,
                'data': stats
            }), 200

        except Exception as e:
            logger.error(f"[ForceVibration] Error analyzing force statistics: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/vibration/statistics', methods=['GET'])
    def get_vibration_statistics(machine_id: str):
        """
        Get vibration statistics for a machine.

        Query Parameters:
            time_range: Time range (e.g., '-1h', '-24h', default: '-1h')

        Returns:
            200: Vibration statistics
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-1h')

            stats = force_vibration_service.analyze_vibration_statistics(
                machine_id,
                time_range=time_range
            )

            if 'error' in stats:
                return jsonify(stats), 500

            return jsonify({
                'success': True,
                'data': stats
            }), 200

        except Exception as e:
            logger.error(f"[ForceVibration] Error analyzing vibration statistics: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/anomalies', methods=['GET'])
    def detect_anomalies(machine_id: str):
        """
        Detect anomalies in force/vibration data.

        Query Parameters:
            threshold_multiplier: Threshold as multiple of std dev (default: 3.0)

        Returns:
            200: Anomaly detection results
            500: Server error
        """
        try:
            threshold_multiplier = request.args.get('threshold_multiplier', 3.0, type=float)

            anomalies = force_vibration_service.detect_anomalies(
                machine_id,
                threshold_multiplier=threshold_multiplier
            )

            if 'error' in anomalies:
                return jsonify(anomalies), 500

            return jsonify({
                'success': True,
                'data': anomalies
            }), 200

        except Exception as e:
            logger.error(f"[ForceVibration] Error detecting anomalies: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_service_statistics():
        """
        Get force/vibration service statistics.

        Returns:
            200: Service statistics
        """
        try:
            stats = force_vibration_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[ForceVibration] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Force and Vibration Monitoring API',
    'version': '1.0.0',
    'description': 'REST API for cutting force and vibration monitoring',
    'base_path': '/api/v1/force-vibration',
    'endpoints': [
        {
            'path': '/health',
            'method': 'GET',
            'description': 'Health check endpoint'
        },
        {
            'path': '/<machine_id>/force',
            'method': 'POST',
            'description': 'Store cutting force data',
            'request_body': {
                'tangential': 'float',
                'radial': 'float',
                'axial': 'float',
                'resultant': 'float (optional)',
                'power': 'float (optional)'
            }
        },
        {
            'path': '/<machine_id>/vibration',
            'method': 'POST',
            'description': 'Store vibration data',
            'request_body': {
                'x': 'float',
                'y': 'float',
                'z': 'float',
                'magnitude': 'float (optional)',
                'frequency': 'float (optional)'
            }
        },
        {
            'path': '/<machine_id>/force/history',
            'method': 'GET',
            'description': 'Get force history'
        },
        {
            'path': '/<machine_id>/vibration/history',
            'method': 'GET',
            'description': 'Get vibration history'
        },
        {
            'path': '/<machine_id>/force/statistics',
            'method': 'GET',
            'description': 'Get force statistics'
        },
        {
            'path': '/<machine_id>/vibration/statistics',
            'method': 'GET',
            'description': 'Get vibration statistics'
        },
        {
            'path': '/<machine_id>/anomalies',
            'method': 'GET',
            'description': 'Detect force/vibration anomalies'
        },
        {
            'path': '/statistics',
            'method': 'GET',
            'description': 'Get service statistics'
        }
    ]
}
