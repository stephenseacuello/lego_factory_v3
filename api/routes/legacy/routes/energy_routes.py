"""
Energy Monitoring API Routes
REST API endpoints for energy consumption monitoring and analysis.
Part of Feature 3.3: Energy Dashboard (Phase 3)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Global service reference
energy_service = None


def init_energy_routes(app, service):
    """Initialize energy monitoring routes"""
    global energy_service
    energy_service = service

    bp = create_energy_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/energy')
    logger.info("[Energy] Routes initialized")


def create_energy_blueprint() -> Blueprint:
    """Create and configure energy monitoring blueprint"""
    bp = Blueprint('energy', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = energy_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'energy_monitoring',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[Energy] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/<machine_id>/power', methods=['POST'])
    def record_power_sample(machine_id: str):
        """
        Record a power consumption sample.

        Request Body:
        {
            "power": 2500.0,
            "energy": 0.69,
            "cost": 0.083,
            "operation_state": "cutting",
            "spindle_speed": 12000,
            "feed_rate": 1000
        }

        Returns:
            201: Sample recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'power' not in data:
                return jsonify({'error': 'power field required'}), 400

            success = energy_service.record_power_sample(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Power sample recorded',
                    'machine_id': machine_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record sample'
                }), 500

        except Exception as e:
            logger.error(f"[Energy] Error recording power sample: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/alerts', methods=['POST'])
    def record_alert(machine_id: str):
        """
        Record an energy alert.

        Request Body:
        {
            "alert_type": "high_power_consumption",
            "severity": "warning",
            "message": "Power consumption exceeds threshold",
            "power": 4500.0
        }

        Returns:
            201: Alert recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'alert_type' not in data:
                return jsonify({'error': 'alert_type required'}), 400

            success = energy_service.record_energy_alert(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Alert recorded',
                    'machine_id': machine_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record alert'
                }), 500

        except Exception as e:
            logger.error(f"[Energy] Error recording alert: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/statistics', methods=['GET'])
    def get_statistics(machine_id: str):
        """
        Get energy statistics.

        Query Parameters:
            time_range: Time range (default: -1h)

        Returns:
            200: Statistics data
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-1h')

            stats = energy_service.get_current_statistics(machine_id, time_range)

            if 'error' in stats:
                return jsonify(stats), 500

            return jsonify({
                'success': True,
                'data': stats
            }), 200

        except Exception as e:
            logger.error(f"[Energy] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/power-by-state', methods=['GET'])
    def get_power_by_state(machine_id: str):
        """
        Get power consumption by operation state.

        Query Parameters:
            time_range: Time range (default: -1h)

        Returns:
            200: Power by state
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-1h')

            power_by_state = energy_service.get_power_by_state(machine_id, time_range)

            if 'error' in power_by_state:
                return jsonify(power_by_state), 500

            return jsonify({
                'success': True,
                'data': power_by_state
            }), 200

        except Exception as e:
            logger.error(f"[Energy] Error getting power by state: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/trend', methods=['GET'])
    def get_energy_trend(machine_id: str):
        """
        Get energy consumption trend.

        Query Parameters:
            time_range: Time range (default: -24h)
            interval: Aggregation interval (default: 1h)

        Returns:
            200: Trend data
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-24h')
            interval = request.args.get('interval', '1h')

            trend = energy_service.get_energy_trend(machine_id, time_range, interval)

            return jsonify({
                'success': True,
                'count': len(trend),
                'data': trend
            }), 200

        except Exception as e:
            logger.error(f"[Energy] Error getting trend: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/recommendations', methods=['GET'])
    def get_recommendations(machine_id: str):
        """
        Get energy optimization recommendations.

        Query Parameters:
            time_range: Time range for analysis (default: -24h)

        Returns:
            200: Recommendations
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-24h')

            recommendations = energy_service.get_optimization_recommendations(machine_id, time_range)

            return jsonify({
                'success': True,
                'count': len(recommendations),
                'recommendations': recommendations
            }), 200

        except Exception as e:
            logger.error(f"[Energy] Error getting recommendations: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/projected-cost', methods=['GET'])
    def get_projected_cost(machine_id: str):
        """
        Calculate projected energy cost.

        Query Parameters:
            hours: Hours to project (required)
            time_range: Reference time range (default: -1h)

        Returns:
            200: Projected cost
            400: Invalid request
            500: Server error
        """
        try:
            hours = request.args.get('hours', type=float)
            if hours is None:
                return jsonify({'error': 'hours parameter required'}), 400

            time_range = request.args.get('time_range', '-1h')

            projection = energy_service.calculate_projected_cost(machine_id, hours, time_range)

            if 'error' in projection:
                return jsonify(projection), 500

            return jsonify({
                'success': True,
                'data': projection
            }), 200

        except Exception as e:
            logger.error(f"[Energy] Error calculating projected cost: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/alerts', methods=['GET'])
    def get_alerts():
        """
        Get energy alerts.

        Query Parameters:
            machine_id: Filter by machine (optional)
            time_range: Time range (default: -24h)
            limit: Maximum alerts (default: 100)

        Returns:
            200: Alerts
            500: Server error
        """
        try:
            machine_id = request.args.get('machine_id')
            time_range = request.args.get('time_range', '-24h')
            limit = request.args.get('limit', 100, type=int)

            alerts = energy_service.get_alerts(machine_id, time_range, limit)

            return jsonify({
                'count': len(alerts),
                'alerts': alerts
            }), 200

        except Exception as e:
            logger.error(f"[Energy] Error getting alerts: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_service_statistics():
        """
        Get service statistics.

        Returns:
            200: Service statistics
        """
        try:
            stats = energy_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[Energy] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Energy Monitoring API',
    'version': '1.0.0',
    'description': 'REST API for energy consumption monitoring and optimization',
    'base_path': '/api/v1/energy',
    'endpoints': [
        {'path': '/health', 'method': 'GET', 'description': 'Health check'},
        {'path': '/<machine_id>/power', 'method': 'POST', 'description': 'Record power sample'},
        {'path': '/<machine_id>/alerts', 'method': 'POST', 'description': 'Record energy alert'},
        {'path': '/<machine_id>/statistics', 'method': 'GET', 'description': 'Get energy statistics'},
        {'path': '/<machine_id>/power-by-state', 'method': 'GET', 'description': 'Get power by state'},
        {'path': '/<machine_id>/trend', 'method': 'GET', 'description': 'Get energy trend'},
        {'path': '/<machine_id>/recommendations', 'method': 'GET', 'description': 'Get optimization recommendations'},
        {'path': '/<machine_id>/projected-cost', 'method': 'GET', 'description': 'Calculate projected cost'},
        {'path': '/alerts', 'method': 'GET', 'description': 'Get energy alerts'},
        {'path': '/statistics', 'method': 'GET', 'description': 'Get service statistics'}
    ]
}
