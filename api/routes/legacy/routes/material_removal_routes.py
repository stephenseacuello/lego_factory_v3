"""
Material Removal API Routes
Provides REST API endpoints for material removal simulation data.
Part of Feature 1.1: Material Removal Simulation (MEDIUM PRIORITY)
"""

import logging
from flask import Blueprint, jsonify, request
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global service reference (set by init function)
material_removal_service = None


def init_material_removal_routes(app, service):
    """
    Initialize material removal routes with service dependency.

    Args:
        app: Flask application instance
        service: MaterialRemovalService instance
    """
    global material_removal_service
    material_removal_service = service

    bp = create_material_removal_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/material-removal')
    logger.info("[MaterialRemoval] Routes initialized")


def create_material_removal_blueprint() -> Blueprint:
    """Create and configure material removal blueprint"""
    bp = Blueprint('material_removal', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = material_removal_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'material_removal',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[MaterialRemoval] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/<machine_id>/event', methods=['POST'])
    def store_removal_event(machine_id: str):
        """
        Store a material removal event.

        Request Body:
        {
            "voxels_removed": 10,
            "volume_removed": 0.00001,
            "mass_removed": 0.000027,
            "tool_position": {
                "x": 0.05,
                "y": 0.03,
                "z": 0.02
            }
        }

        Returns:
            201: Event stored successfully
            400: Invalid request data
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'No data provided'}), 400

            # Validate required fields
            required_fields = ['voxels_removed', 'volume_removed', 'mass_removed']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400

            # Store event
            success = material_removal_service.store_removal_event(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Removal event stored',
                    'machine_id': machine_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to store event'
                }), 500

        except Exception as e:
            logger.error(f"[MaterialRemoval] Error storing event: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/history', methods=['GET'])
    def get_removal_history(machine_id: str):
        """
        Get material removal history for a machine.

        Query Parameters:
            start_time: Start time (RFC3339 or relative like '-1h')
            end_time: End time (RFC3339 or relative like 'now')
            limit: Maximum records to return (default: 1000)

        Returns:
            200: History data
            500: Server error
        """
        try:
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            limit = request.args.get('limit', 1000, type=int)

            history = material_removal_service.get_removal_history(
                machine_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            return jsonify({
                'machine_id': machine_id,
                'count': len(history),
                'events': history
            }), 200

        except Exception as e:
            logger.error(f"[MaterialRemoval] Error retrieving history: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/summary', methods=['GET'])
    def get_removal_summary(machine_id: str):
        """
        Get summary statistics for material removal.

        Query Parameters:
            time_range: Time range (e.g., '-1h', '-24h', '-7d', default: '-1h')

        Returns:
            200: Summary statistics
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-1h')

            summary = material_removal_service.get_removal_summary(
                machine_id,
                time_range=time_range
            )

            if 'error' in summary:
                return jsonify(summary), 500

            return jsonify({
                'success': True,
                'data': summary
            }), 200

        except Exception as e:
            logger.error(f"[MaterialRemoval] Error generating summary: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/rate', methods=['GET'])
    def get_removal_rate(machine_id: str):
        """
        Calculate material removal rate over time.

        Query Parameters:
            window: Aggregation window (e.g., '1m', '5m', '1h', default: '1m')

        Returns:
            200: Removal rate data
            500: Server error
        """
        try:
            window = request.args.get('window', '1m')

            rates = material_removal_service.get_removal_rate(
                machine_id,
                window=window
            )

            return jsonify({
                'machine_id': machine_id,
                'window': window,
                'count': len(rates),
                'data': rates
            }), 200

        except Exception as e:
            logger.error(f"[MaterialRemoval] Error calculating rate: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/history', methods=['DELETE'])
    def clear_removal_history(machine_id: str):
        """
        Clear removal history for a machine.

        Returns:
            200: History cleared
            500: Server error
        """
        try:
            success = material_removal_service.clear_history(machine_id)

            if success:
                return jsonify({
                    'success': True,
                    'message': f'History cleared for machine {machine_id}'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to clear history'
                }), 500

        except Exception as e:
            logger.error(f"[MaterialRemoval] Error clearing history: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_service_statistics():
        """
        Get material removal service statistics.

        Returns:
            200: Service statistics
        """
        try:
            stats = material_removal_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[MaterialRemoval] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Material Removal API',
    'version': '1.0.0',
    'description': 'REST API for material removal simulation data',
    'base_path': '/api/v1/material-removal',
    'endpoints': [
        {
            'path': '/health',
            'method': 'GET',
            'description': 'Health check endpoint',
            'response': {
                'status': 'healthy',
                'service': 'material_removal'
            }
        },
        {
            'path': '/<machine_id>/event',
            'method': 'POST',
            'description': 'Store material removal event',
            'request_body': {
                'voxels_removed': 'int',
                'volume_removed': 'float',
                'mass_removed': 'float',
                'tool_position': {'x': 'float', 'y': 'float', 'z': 'float'}
            }
        },
        {
            'path': '/<machine_id>/history',
            'method': 'GET',
            'description': 'Get removal history',
            'query_params': {
                'start_time': 'string (optional)',
                'end_time': 'string (optional)',
                'limit': 'int (optional)'
            }
        },
        {
            'path': '/<machine_id>/summary',
            'method': 'GET',
            'description': 'Get removal summary statistics',
            'query_params': {
                'time_range': 'string (optional)'
            }
        },
        {
            'path': '/<machine_id>/rate',
            'method': 'GET',
            'description': 'Get material removal rate',
            'query_params': {
                'window': 'string (optional)'
            }
        },
        {
            'path': '/<machine_id>/history',
            'method': 'DELETE',
            'description': 'Clear removal history'
        },
        {
            'path': '/statistics',
            'method': 'GET',
            'description': 'Get service statistics'
        }
    ]
}
