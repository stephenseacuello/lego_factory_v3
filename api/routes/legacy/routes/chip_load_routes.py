"""
Chip Load API Routes
REST API endpoints for chip load monitoring and analysis.
Part of Feature 2.2: Chip Load Heatmaps (Phase 2)
"""

import logging
from flask import Blueprint, jsonify, request
from typing import Dict

logger = logging.getLogger(__name__)

# Global service reference
chip_load_service = None


def init_chip_load_routes(app, service):
    """
    Initialize chip load routes with service dependency.

    Args:
        app: Flask application instance
        service: ChipLoadService instance
    """
    global chip_load_service
    chip_load_service = service

    bp = create_chip_load_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/chip-load')
    logger.info("[ChipLoad] Routes initialized")


def create_chip_load_blueprint() -> Blueprint:
    """Create and configure chip load blueprint"""
    bp = Blueprint('chip_load', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = chip_load_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'chip_load',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[ChipLoad] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/<machine_id>/data', methods=['POST'])
    def store_chip_load_data(machine_id: str):
        """
        Store chip load data.

        Request Body:
        {
            "chip_load": 0.08,
            "feed_rate": 1000.0,
            "spindle_speed": 12000.0,
            "number_of_flutes": 4,
            "chip_thickness": 0.08,
            "material_removal_rate": 50.0,
            "tool_diameter": 6.0,
            "material_type": "aluminum",
            "is_optimal": true
        }

        Returns:
            201: Data stored successfully
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'No data provided'}), 400

            # Validate required fields
            required_fields = ['chip_load', 'feed_rate', 'spindle_speed', 'number_of_flutes']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400

            success = chip_load_service.store_chip_load_data(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Chip load data stored',
                    'machine_id': machine_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to store chip load data'
                }), 500

        except Exception as e:
            logger.error(f"[ChipLoad] Error storing chip load data: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/flutes', methods=['POST'])
    def store_flute_data(machine_id: str):
        """
        Store per-flute chip load data.

        Request Body:
        {
            "flute_loads": [0.078, 0.082, 0.080, 0.079]
        }

        Returns:
            201: Data stored successfully
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'flute_loads' not in data:
                return jsonify({'error': 'flute_loads required'}), 400

            success = chip_load_service.store_flute_chip_loads(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Flute chip loads stored',
                    'machine_id': machine_id,
                    'flute_count': len(data['flute_loads'])
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to store flute data'
                }), 500

        except Exception as e:
            logger.error(f"[ChipLoad] Error storing flute data: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/history', methods=['GET'])
    def get_chip_load_history(machine_id: str):
        """
        Get chip load history for a machine.

        Query Parameters:
            start_time: Start time (RFC3339 or relative like '-1h')
            end_time: End time (RFC3339 or relative like 'now()')
            limit: Maximum records to return (default: 1000)

        Returns:
            200: History data
            500: Server error
        """
        try:
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            limit = request.args.get('limit', 1000, type=int)

            history = chip_load_service.get_chip_load_history(
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
            logger.error(f"[ChipLoad] Error retrieving history: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/flutes/history', methods=['GET'])
    def get_flute_history(machine_id: str):
        """
        Get per-flute chip load history.

        Query Parameters:
            start_time: Start time
            end_time: End time
            limit: Maximum records to return (default: 1000)

        Returns:
            200: Flute history data
            500: Server error
        """
        try:
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            limit = request.args.get('limit', 1000, type=int)

            history = chip_load_service.get_flute_history(
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
            logger.error(f"[ChipLoad] Error retrieving flute history: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/statistics', methods=['GET'])
    def get_chip_load_statistics(machine_id: str):
        """
        Get chip load statistics for a machine.

        Query Parameters:
            time_range: Time range (e.g., '-1h', '-24h', default: '-1h')
            material_type: Material type for optimal range comparison

        Returns:
            200: Statistics data
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-1h')
            material_type = request.args.get('material_type')

            stats = chip_load_service.analyze_chip_load_statistics(
                machine_id,
                time_range=time_range,
                material_type=material_type
            )

            if 'error' in stats:
                return jsonify(stats), 500

            return jsonify({
                'success': True,
                'data': stats
            }), 200

        except Exception as e:
            logger.error(f"[ChipLoad] Error analyzing statistics: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/flutes/distribution', methods=['GET'])
    def get_flute_distribution(machine_id: str):
        """
        Analyze chip load distribution across flutes.

        Query Parameters:
            time_range: Time range (default: '-1h')

        Returns:
            200: Distribution analysis
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-1h')

            analysis = chip_load_service.analyze_flute_distribution(
                machine_id,
                time_range=time_range
            )

            if 'error' in analysis:
                return jsonify(analysis), 500

            return jsonify({
                'success': True,
                'data': analysis
            }), 200

        except Exception as e:
            logger.error(f"[ChipLoad] Error analyzing distribution: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/warnings', methods=['GET'])
    def detect_warnings(machine_id: str):
        """
        Detect chip load warnings.

        Query Parameters:
            material_type: Material being machined (required)
            time_range: Time range to analyze (default: '-5m')

        Returns:
            200: Warning information
            400: Missing required parameter
            500: Server error
        """
        try:
            material_type = request.args.get('material_type')
            time_range = request.args.get('time_range', '-5m')

            if not material_type:
                return jsonify({'error': 'material_type parameter required'}), 400

            warnings = chip_load_service.detect_chip_load_warnings(
                machine_id,
                material_type=material_type,
                time_range=time_range
            )

            if 'error' in warnings:
                return jsonify(warnings), 500

            return jsonify({
                'success': True,
                'data': warnings
            }), 200

        except Exception as e:
            logger.error(f"[ChipLoad] Error detecting warnings: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/calculate/feed-rate', methods=['POST'])
    def calculate_feed_rate():
        """
        Calculate recommended feed rate for target chip load.

        Request Body:
        {
            "target_chip_load": 0.08,
            "spindle_speed": 12000,
            "number_of_flutes": 4
        }

        Returns:
            200: Recommended parameters
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'No data provided'}), 400

            required_fields = ['target_chip_load', 'spindle_speed', 'number_of_flutes']
            for field in required_fields:
                if field not in data:
                    return jsonify({'error': f'Missing required field: {field}'}), 400

            result = chip_load_service.calculate_recommended_parameters(
                target_chip_load=float(data['target_chip_load']),
                spindle_speed=float(data['spindle_speed']),
                number_of_flutes=int(data['number_of_flutes'])
            )

            if 'error' in result:
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'data': result
            }), 200

        except Exception as e:
            logger.error(f"[ChipLoad] Error calculating feed rate: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_service_statistics():
        """
        Get chip load service statistics.

        Returns:
            200: Service statistics
        """
        try:
            stats = chip_load_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[ChipLoad] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Chip Load Monitoring API',
    'version': '1.0.0',
    'description': 'REST API for chip load monitoring and heatmap visualization',
    'base_path': '/api/v1/chip-load',
    'endpoints': [
        {
            'path': '/health',
            'method': 'GET',
            'description': 'Health check endpoint'
        },
        {
            'path': '/<machine_id>/data',
            'method': 'POST',
            'description': 'Store chip load data',
            'request_body': {
                'chip_load': 'float (required)',
                'feed_rate': 'float (required)',
                'spindle_speed': 'float (required)',
                'number_of_flutes': 'int (required)',
                'chip_thickness': 'float (optional)',
                'material_removal_rate': 'float (optional)',
                'tool_diameter': 'float (optional)',
                'material_type': 'string (optional)',
                'is_optimal': 'boolean (optional)'
            }
        },
        {
            'path': '/<machine_id>/flutes',
            'method': 'POST',
            'description': 'Store per-flute chip load data',
            'request_body': {
                'flute_loads': 'array of float (required)'
            }
        },
        {
            'path': '/<machine_id>/history',
            'method': 'GET',
            'description': 'Get chip load history'
        },
        {
            'path': '/<machine_id>/flutes/history',
            'method': 'GET',
            'description': 'Get per-flute history'
        },
        {
            'path': '/<machine_id>/statistics',
            'method': 'GET',
            'description': 'Get chip load statistics'
        },
        {
            'path': '/<machine_id>/flutes/distribution',
            'method': 'GET',
            'description': 'Analyze flute distribution'
        },
        {
            'path': '/<machine_id>/warnings',
            'method': 'GET',
            'description': 'Detect chip load warnings'
        },
        {
            'path': '/calculate/feed-rate',
            'method': 'POST',
            'description': 'Calculate recommended feed rate'
        },
        {
            'path': '/statistics',
            'method': 'GET',
            'description': 'Get service statistics'
        }
    ]
}
