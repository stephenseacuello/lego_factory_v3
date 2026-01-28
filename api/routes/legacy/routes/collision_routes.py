"""
Collision Detection API Routes
REST API for collision detection and safety validation.
Part of Feature 1.2: Collision Detection (HIGH PRIORITY)
"""

from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

# Services will be injected during initialization
collision_prediction_service = None
kinematic_limits_service = None


def init_collision_routes(app, collision_svc, kinematic_svc):
    """
    Initialize collision detection routes with service dependencies.

    Args:
        app: Flask application
        collision_svc: CollisionPredictionService instance
        kinematic_svc: KinematicLimitsService instance
    """
    global collision_prediction_service, kinematic_limits_service
    collision_prediction_service = collision_svc
    kinematic_limits_service = kinematic_svc

    # Create blueprint
    collision_bp = Blueprint('collision', __name__, url_prefix='/api/v1/collision')

    @collision_bp.route('/check-segment', methods=['POST'])
    def check_segment():
        """
        Check a path segment for collisions.

        Request JSON:
        {
            "start": [x, y, z],
            "end": [x, y, z]
        }

        Response JSON:
        {
            "collision": bool,
            "collision_type": str (optional),
            "collision_point": [x, y, z] (optional),
            "distance": float,
            "safe": bool
        }
        """
        try:
            data = request.get_json()

            if not data or 'start' not in data or 'end' not in data:
                return jsonify({'error': 'Missing start or end position'}), 400

            start = data['start']
            end = data['end']

            # Validate input
            if len(start) != 3 or len(end) != 3:
                return jsonify({'error': 'Start and end must be 3D positions'}), 400

            result = collision_prediction_service.check_path_segment(start, end)

            return jsonify(result), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error checking segment: {e}")
            return jsonify({'error': str(e)}), 500

    @collision_bp.route('/check-toolpath', methods=['POST'])
    def check_toolpath():
        """
        Check an entire toolpath for collisions.

        Request JSON:
        {
            "path": [[x, y, z], [x, y, z], ...]
        }

        Response JSON:
        {
            "safe": bool,
            "collisions": [...],
            "total_segments": int,
            "collision_count": int,
            "collision_percentage": float
        }
        """
        try:
            data = request.get_json()

            if not data or 'path' not in data:
                return jsonify({'error': 'Missing path data'}), 400

            path = data['path']

            if not isinstance(path, list) or len(path) < 2:
                return jsonify({'error': 'Path must be a list of at least 2 points'}), 400

            result = collision_prediction_service.check_toolpath(path)

            return jsonify(result), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error checking toolpath: {e}")
            return jsonify({'error': str(e)}), 500

    @collision_bp.route('/validate-position', methods=['POST'])
    def validate_position():
        """
        Validate a position against kinematic limits.

        Request JSON:
        {
            "position": {"X": 100, "Y": 200, "Z": 50, ...}
        }

        Response JSON:
        {
            "valid": bool,
            "in_soft_limit": bool,
            "violations": [...],
            "warnings": [...]
        }
        """
        try:
            data = request.get_json()

            if not data or 'position' not in data:
                return jsonify({'error': 'Missing position data'}), 400

            position = data['position']

            result = kinematic_limits_service.validate_position(position)

            return jsonify(result), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error validating position: {e}")
            return jsonify({'error': str(e)}), 500

    @collision_bp.route('/safe-feedrate', methods=['POST'])
    def get_safe_feedrate():
        """
        Calculate safe feedrate based on proximity to obstacles.

        Request JSON:
        {
            "position": [x, y, z],
            "direction": [dx, dy, dz]
        }

        Response JSON:
        {
            "safe_feedrate_multiplier": float (0.0 to 1.0)
        }
        """
        try:
            data = request.get_json()

            if not data or 'position' not in data or 'direction' not in data:
                return jsonify({'error': 'Missing position or direction'}), 400

            position = data['position']
            direction = data['direction']

            multiplier = collision_prediction_service.get_safe_feedrate(position, direction)

            return jsonify({
                'safe_feedrate_multiplier': multiplier
            }), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error calculating safe feedrate: {e}")
            return jsonify({'error': str(e)}), 500

    @collision_bp.route('/config/tool', methods=['POST'])
    def configure_tool():
        """
        Configure tool dimensions for collision detection.

        Request JSON:
        {
            "radius": float,  # meters
            "length": float   # meters
        }

        Response JSON:
        {
            "success": bool,
            "message": str
        }
        """
        try:
            data = request.get_json()

            if not data or 'radius' not in data or 'length' not in data:
                return jsonify({'error': 'Missing radius or length'}), 400

            radius = float(data['radius'])
            length = float(data['length'])

            if radius <= 0 or length <= 0:
                return jsonify({'error': 'Radius and length must be positive'}), 400

            collision_prediction_service.set_tool_dimensions(radius, length)

            return jsonify({
                'success': True,
                'message': f'Tool dimensions set: R={radius}m, L={length}m'
            }), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error configuring tool: {e}")
            return jsonify({'error': str(e)}), 500

    @collision_bp.route('/config/workpiece', methods=['POST'])
    def configure_workpiece():
        """
        Configure workpiece bounding box.

        Request JSON:
        {
            "min": [x, y, z],
            "max": [x, y, z]
        }

        Response JSON:
        {
            "success": bool,
            "message": str
        }
        """
        try:
            data = request.get_json()

            if not data or 'min' not in data or 'max' not in data:
                return jsonify({'error': 'Missing min or max bounds'}), 400

            collision_prediction_service.set_workpiece_bounds(data)

            return jsonify({
                'success': True,
                'message': 'Workpiece bounds configured'
            }), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error configuring workpiece: {e}")
            return jsonify({'error': str(e)}), 500

    @collision_bp.route('/config/fixture', methods=['POST'])
    def add_fixture():
        """
        Add a fixture to collision geometry.

        Request JSON:
        {
            "position": [x, y, z],
            "size": [width, height, depth],
            "rotation": float (optional)
        }

        Response JSON:
        {
            "success": bool,
            "message": str
        }
        """
        try:
            data = request.get_json()

            if not data or 'position' not in data or 'size' not in data:
                return jsonify({'error': 'Missing position or size'}), 400

            collision_prediction_service.add_fixture(data)

            return jsonify({
                'success': True,
                'message': 'Fixture added'
            }), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error adding fixture: {e}")
            return jsonify({'error': str(e)}), 500

    @collision_bp.route('/config/fixture', methods=['DELETE'])
    def clear_fixtures():
        """
        Clear all fixtures from collision geometry.

        Response JSON:
        {
            "success": bool,
            "message": str
        }
        """
        try:
            collision_prediction_service.clear_fixtures()

            return jsonify({
                'success': True,
                'message': 'All fixtures cleared'
            }), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error clearing fixtures: {e}")
            return jsonify({'error': str(e)}), 500

    @collision_bp.route('/limits/joint', methods=['POST'])
    def set_joint_limits():
        """
        Set joint limits for an axis.

        Request JSON:
        {
            "axis": str,
            "min": float,
            "max": float,
            "unit": str (optional)
        }

        Response JSON:
        {
            "success": bool,
            "message": str
        }
        """
        try:
            data = request.get_json()

            if not data or 'axis' not in data or 'min' not in data or 'max' not in data:
                return jsonify({'error': 'Missing axis, min, or max'}), 400

            axis = data['axis']
            min_val = float(data['min'])
            max_val = float(data['max'])
            unit = data.get('unit', 'mm')

            kinematic_limits_service.set_joint_limits(axis, min_val, max_val, unit)

            return jsonify({
                'success': True,
                'message': f'{axis} limits set: [{min_val}, {max_val}] {unit}'
            }), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error setting joint limits: {e}")
            return jsonify({'error': str(e)}), 500

    @collision_bp.route('/statistics', methods=['GET'])
    def get_statistics():
        """
        Get collision detection and kinematic limits statistics.

        Response JSON:
        {
            "collision": {...},
            "kinematic": {...}
        }
        """
        try:
            collision_stats = collision_prediction_service.get_statistics()
            kinematic_stats = kinematic_limits_service.get_statistics()

            return jsonify({
                'collision': collision_stats,
                'kinematic': kinematic_stats
            }), 200

        except Exception as e:
            logger.error(f"[CollisionRoutes] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    # Register blueprint with app
    app.register_blueprint(collision_bp)
    logger.info("[CollisionRoutes] Collision detection routes registered")

