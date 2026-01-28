"""
Trail Visualization API Routes
REST and WebSocket endpoints for machine trail visualization.
Part of Feature 1.3: Machine Trail Visualization

Author: Claude (Anthropic)
Created: 2026-01-14
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Create Blueprint
trail_bp = Blueprint('trail', __name__, url_prefix='/api/v1/trails')

# Services will be injected
path_history_service = None
trail_optimizer_service = None


def init_trail_routes(app, path_history_svc, trail_optimizer_svc):
    """
    Initialize trail routes with service dependencies.

    Args:
        app: Flask application
        path_history_svc: PathHistoryService instance
        trail_optimizer_svc: TrailOptimizerService instance
    """
    global path_history_service, trail_optimizer_service
    path_history_service = path_history_svc
    trail_optimizer_service = trail_optimizer_svc

    app.register_blueprint(trail_bp)
    logger.info("[TrailRoutes] Routes initialized")


@trail_bp.route('/<machine_id>', methods=['GET'])
def get_trail_history(machine_id):
    """
    Get trail history for a machine.

    Query Parameters:
        start_time (str, optional): Start time ISO format
        end_time (str, optional): End time ISO format
        limit (int, optional): Max points (default: 10000)
        optimize (bool, optional): Apply optimization (default: false)
        epsilon (float, optional): Optimization tolerance (default: 0.001)

    Returns:
        JSON response with trail data
    """
    try:
        # Parse query parameters
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        limit = int(request.args.get('limit', 10000))
        optimize = request.args.get('optimize', 'false').lower() == 'true'
        epsilon = float(request.args.get('epsilon', 0.001))

        # Parse dates
        start_time = None
        end_time = None

        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        if end_time_str:
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))

        # Get trail history
        trail_data = path_history_service.get_trail_history(
            machine_id=machine_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )

        # Optimize if requested
        if optimize and trail_data['points']:
            optimized_points = trail_optimizer_service.optimize_trail(
                points=trail_data['points'],
                epsilon=epsilon,
                max_points=limit
            )

            # Update trail data with optimized points
            original_count = len(trail_data['points'])
            trail_data['points'] = optimized_points
            trail_data['optimized'] = True
            trail_data['original_count'] = original_count

        return jsonify({
            'success': True,
            'machine_id': machine_id,
            'data': trail_data
        }), 200

    except Exception as e:
        logger.error(f"[TrailRoutes] Error getting trail history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trail_bp.route('/<machine_id>', methods=['POST'])
def store_trail_points(machine_id):
    """
    Store trail points for a machine.

    Request Body:
        {
            "points": [{"x": 0, "y": 0, "z": 0}],
            "speeds": [0],
            "timestamp": "2026-01-14T12:00:00Z" (optional)
        }

    Returns:
        JSON response with success status
    """
    try:
        data = request.get_json()

        if not data or 'points' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing points data'
            }), 400

        points = data['points']
        speeds = data.get('speeds', [0] * len(points))
        timestamp = data.get('timestamp')

        # Prepare points for storage
        storage_points = []
        for i, point in enumerate(points):
            storage_point = {
                'x': point.get('x', 0),
                'y': point.get('y', 0),
                'z': point.get('z', 0),
                'speed': speeds[i] if i < len(speeds) else 0
            }

            if timestamp:
                storage_point['timestamp'] = timestamp

            storage_points.append(storage_point)

        # Store points
        success = path_history_service.store_trail_points(machine_id, storage_points)

        if success:
            return jsonify({
                'success': True,
                'machine_id': machine_id,
                'points_stored': len(storage_points)
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to store trail points'
            }), 500

    except Exception as e:
        logger.error(f"[TrailRoutes] Error storing trail points: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trail_bp.route('/<machine_id>', methods=['DELETE'])
def clear_trail_history(machine_id):
    """
    Clear trail history for a machine.

    Query Parameters:
        hours (int, optional): Only clear last N hours. If not specified, clears all.

    Returns:
        JSON response with success status
    """
    try:
        hours = request.args.get('hours', type=int)

        success = path_history_service.clear_trail_history(machine_id, hours)

        if success:
            return jsonify({
                'success': True,
                'machine_id': machine_id,
                'message': f'Trail history cleared{" for last " + str(hours) + " hours" if hours else ""}'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to clear trail history'
            }), 500

    except Exception as e:
        logger.error(f"[TrailRoutes] Error clearing trail history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trail_bp.route('/<machine_id>/summary', methods=['GET'])
def get_trail_summary(machine_id):
    """
    Get trail summary statistics.

    Query Parameters:
        hours (int, optional): Number of hours to look back (default: 1)

    Returns:
        JSON response with trail summary
    """
    try:
        hours = int(request.args.get('hours', 1))

        summary = path_history_service.get_trail_summary(machine_id, hours)

        return jsonify({
            'success': True,
            'machine_id': machine_id,
            'hours': hours,
            'summary': summary
        }), 200

    except Exception as e:
        logger.error(f"[TrailRoutes] Error getting trail summary: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trail_bp.route('/<machine_id>/distance', methods=['GET'])
def get_total_distance(machine_id):
    """
    Get total distance traveled by machine.

    Query Parameters:
        start_time (str, optional): Start time ISO format
        end_time (str, optional): End time ISO format

    Returns:
        JSON response with total distance
    """
    try:
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')

        start_time = None
        end_time = None

        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        if end_time_str:
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))

        distance = path_history_service.calculate_total_distance(
            machine_id=machine_id,
            start_time=start_time,
            end_time=end_time
        )

        return jsonify({
            'success': True,
            'machine_id': machine_id,
            'total_distance_meters': distance,
            'total_distance_mm': distance * 1000
        }), 200

    except Exception as e:
        logger.error(f"[TrailRoutes] Error calculating distance: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trail_bp.route('/active', methods=['GET'])
def get_active_machines():
    """
    Get list of machines with recent trail activity.

    Query Parameters:
        minutes (int, optional): Time window in minutes (default: 10)

    Returns:
        JSON response with active machine list
    """
    try:
        minutes = int(request.args.get('minutes', 10))

        machines = path_history_service.get_active_machines(minutes)

        return jsonify({
            'success': True,
            'minutes': minutes,
            'active_machines': machines,
            'count': len(machines)
        }), 200

    except Exception as e:
        logger.error(f"[TrailRoutes] Error getting active machines: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trail_bp.route('/<machine_id>/optimize', methods=['POST'])
def optimize_trail(machine_id):
    """
    Optimize stored trail data.

    Request Body:
        {
            "epsilon": 0.001,
            "max_points": 1000
        }

    Returns:
        JSON response with optimized trail
    """
    try:
        data = request.get_json() or {}
        epsilon = data.get('epsilon', 0.001)
        max_points = data.get('max_points', 1000)

        # Get current trail
        trail_data = path_history_service.get_trail_history(machine_id)

        if not trail_data['points']:
            return jsonify({
                'success': False,
                'error': 'No trail data found'
            }), 404

        # Optimize
        optimized_points = trail_optimizer_service.optimize_trail(
            points=trail_data['points'],
            epsilon=epsilon,
            max_points=max_points
        )

        # Calculate statistics
        original_stats = trail_optimizer_service.calculate_path_statistics(trail_data['points'])
        optimized_stats = trail_optimizer_service.calculate_path_statistics(optimized_points)

        return jsonify({
            'success': True,
            'machine_id': machine_id,
            'original_count': len(trail_data['points']),
            'optimized_count': len(optimized_points),
            'reduction_percent': (1 - len(optimized_points) / len(trail_data['points'])) * 100,
            'original_stats': original_stats,
            'optimized_stats': optimized_stats
        }), 200

    except Exception as e:
        logger.error(f"[TrailRoutes] Error optimizing trail: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
