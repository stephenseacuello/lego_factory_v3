"""
Root Cause Analysis API Routes
REST API endpoints for automated root cause analysis.
Part of Feature 3.2: Root Cause Analysis (Phase 3)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Global service reference
root_cause_service = None


def init_root_cause_routes(app, service):
    """Initialize root cause analysis routes"""
    global root_cause_service
    root_cause_service = service

    bp = create_root_cause_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/root-cause')
    logger.info("[RootCause] Routes initialized")


def create_root_cause_blueprint() -> Blueprint:
    """Create and configure root cause blueprint"""
    bp = Blueprint('root_cause', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = root_cause_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'root_cause_analysis',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[RootCause] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/<machine_id>/events', methods=['POST'])
    def record_event(machine_id: str):
        """
        Record a manufacturing event.

        Request Body:
        {
            "event_id": "EVT-001",
            "event_type": "tool_age_high",
            "description": "Tool approaching end of life",
            "parameters": {
                "tool_life_percentage": 85,
                "operations_completed": 450
            }
        }

        Returns:
            201: Event recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'event_type' not in data:
                return jsonify({'error': 'event_type required'}), 400

            success = root_cause_service.record_event(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Event recorded',
                    'machine_id': machine_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record event'
                }), 500

        except Exception as e:
            logger.error(f"[RootCause] Error recording event: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/quality-issues', methods=['POST'])
    def record_quality_issue(machine_id: str):
        """
        Record a quality issue.

        Request Body:
        {
            "issue_id": "QI-001",
            "issue_type": "dimensional_deviation",
            "description": "Part dimension out of tolerance",
            "severity": 0.8,
            "measurements": {
                "actual_dimension": 10.05,
                "target_dimension": 10.0,
                "tolerance": 0.02
            }
        }

        Returns:
            201: Quality issue recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'issue_type' not in data:
                return jsonify({'error': 'issue_type required'}), 400

            success = root_cause_service.record_quality_issue(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Quality issue recorded',
                    'machine_id': machine_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record quality issue'
                }), 500

        except Exception as e:
            logger.error(f"[RootCause] Error recording quality issue: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/analyze/<issue_type>', methods=['POST'])
    def analyze_issue(machine_id: str, issue_type: str):
        """
        Perform root cause analysis.

        Query Parameters:
            time_window: Time window for historical data (default: -1h)

        Returns:
            200: Analysis completed
            500: Server error
        """
        try:
            time_window = request.args.get('time_window', '-1h')

            analysis = root_cause_service.analyze_issue(machine_id, issue_type, time_window)

            if 'error' in analysis:
                return jsonify(analysis), 500

            return jsonify({
                'success': True,
                'data': analysis
            }), 200

        except Exception as e:
            logger.error(f"[RootCause] Error analyzing issue: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/analyses', methods=['GET'])
    def get_analyses():
        """
        Get analysis history.

        Query Parameters:
            machine_id: Filter by machine (optional)
            issue_type: Filter by issue type (optional)
            time_range: Time range (default: -7d)
            limit: Maximum results (default: 100)

        Returns:
            200: Analysis history
            500: Server error
        """
        try:
            machine_id = request.args.get('machine_id')
            issue_type = request.args.get('issue_type')
            time_range = request.args.get('time_range', '-7d')
            limit = request.args.get('limit', 100, type=int)

            analyses = root_cause_service.get_analysis_history(
                machine_id=machine_id,
                issue_type=issue_type,
                time_range=time_range,
                limit=limit
            )

            return jsonify({
                'count': len(analyses),
                'analyses': analyses
            }), 200

        except Exception as e:
            logger.error(f"[RootCause] Error getting analyses: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/patterns/statistics', methods=['GET'])
    def get_pattern_statistics():
        """
        Get pattern detection statistics.

        Query Parameters:
            time_range: Time range for statistics (default: -30d)

        Returns:
            200: Pattern statistics
            500: Server error
        """
        try:
            time_range = request.args.get('time_range', '-30d')

            stats = root_cause_service.get_pattern_statistics(time_range)

            if 'error' in stats:
                return jsonify(stats), 500

            return jsonify({
                'success': True,
                'data': stats
            }), 200

        except Exception as e:
            logger.error(f"[RootCause] Error getting pattern statistics: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_statistics():
        """
        Get service statistics.

        Returns:
            200: Service statistics
        """
        try:
            stats = root_cause_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[RootCause] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Root Cause Analysis API',
    'version': '1.0.0',
    'description': 'REST API for automated root cause analysis of manufacturing issues',
    'base_path': '/api/v1/root-cause',
    'endpoints': [
        {'path': '/health', 'method': 'GET', 'description': 'Health check'},
        {'path': '/<machine_id>/events', 'method': 'POST', 'description': 'Record manufacturing event'},
        {'path': '/<machine_id>/quality-issues', 'method': 'POST', 'description': 'Record quality issue'},
        {'path': '/<machine_id>/analyze/<issue_type>', 'method': 'POST', 'description': 'Perform root cause analysis'},
        {'path': '/analyses', 'method': 'GET', 'description': 'Get analysis history'},
        {'path': '/patterns/statistics', 'method': 'GET', 'description': 'Get pattern statistics'},
        {'path': '/statistics', 'method': 'GET', 'description': 'Get service statistics'}
    ]
}
