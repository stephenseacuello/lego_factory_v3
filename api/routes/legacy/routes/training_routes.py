"""
Operator Training API Routes
REST API endpoints for operator training and skill development.
Part of Feature 4.3: Operator Training Mode (Phase 4)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Global service reference
training_service = None


def init_training_routes(app, service):
    """Initialize training routes"""
    global training_service
    training_service = service

    bp = create_training_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/training')
    logger.info("[Training] Routes initialized")


def create_training_blueprint() -> Blueprint:
    """Create and configure training blueprint"""
    bp = Blueprint('training', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """
        Health check endpoint.

        Returns:
            200: Service healthy
            500: Service unhealthy
        """
        try:
            stats = training_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'operator_training',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[Training] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/sessions', methods=['POST'])
    def start_session():
        """
        Start a new training session.

        Request Body:
        {
            "session_id": "SESSION-001",
            "operator_id": "OP-001",
            "scenario_id": "machine_setup",
            "difficulty": "beginner",
            "guided_mode": true,
            "attempt_number": 1
        }

        Returns:
            201: Session started
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or not all(k in data for k in ['session_id', 'operator_id', 'scenario_id']):
                return jsonify({
                    'error': 'Required fields: session_id, operator_id, scenario_id'
                }), 400

            result = training_service.start_session(data)

            if 'error' in result:
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'message': 'Training session started',
                'data': result
            }), 201

        except Exception as e:
            logger.error(f"[Training] Error starting session: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/sessions/<session_id>/steps', methods=['POST'])
    def record_step():
        """
        Record step performance for a training session.

        Request Body:
        {
            "step_id": "power_on",
            "step_index": 0,
            "action_taken": "power_on",
            "is_correct": true,
            "timed_out": false,
            "completion_time": 45.5,
            "time_limit": 60.0,
            "points_earned": 9.5,
            "max_points": 10.0,
            "accuracy": 0.95
        }

        Returns:
            200: Step recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'step_id' not in data:
                return jsonify({'error': 'step_id required'}), 400

            success = training_service.record_step_performance(session_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Step performance recorded',
                    'session_id': session_id,
                    'step_id': data['step_id']
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record step performance'
                }), 500

        except Exception as e:
            logger.error(f"[Training] Error recording step: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/sessions/<session_id>/complete', methods=['POST'])
    def complete_session(session_id: str):
        """
        Complete a training session.

        Request Body:
        {
            "operator_id": "OP-001",
            "scenario_id": "machine_setup",
            "duration": 600.0,
            "steps_completed": 4,
            "total_steps": 4,
            "final_score": 0.85,
            "accuracy": 0.90,
            "avg_step_time": 150.0,
            "passed": true,
            "rating": "good",
            "certification_earned": false
        }

        Returns:
            200: Session completed
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or not all(k in data for k in ['operator_id', 'scenario_id']):
                return jsonify({
                    'error': 'Required fields: operator_id, scenario_id'
                }), 400

            result = training_service.complete_session(session_id, data)

            if 'error' in result:
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'message': 'Training session completed',
                'data': result
            }), 200

        except Exception as e:
            logger.error(f"[Training] Error completing session: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/sessions/<session_id>/performance', methods=['GET'])
    def get_session_performance(session_id: str):
        """
        Get detailed performance metrics for a session.

        Returns:
            200: Session performance data
            404: Session not found
            500: Server error
        """
        try:
            performance = training_service.get_session_performance(session_id)

            if 'error' in performance:
                if performance['error'] == 'Session not found':
                    return jsonify(performance), 404
                return jsonify(performance), 500

            return jsonify({
                'success': True,
                'data': performance
            }), 200

        except Exception as e:
            logger.error(f"[Training] Error getting session performance: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/operators/<operator_id>/progress', methods=['GET'])
    def get_operator_progress(operator_id: str):
        """
        Get training progress for an operator.

        Query Parameters:
        - days: Number of days to look back (default: 30)

        Returns:
            200: Operator progress data
            500: Server error
        """
        try:
            days = request.args.get('days', 30, type=int)

            progress = training_service.get_operator_progress(operator_id, days)

            if 'error' in progress:
                return jsonify(progress), 500

            return jsonify({
                'success': True,
                'data': progress
            }), 200

        except Exception as e:
            logger.error(f"[Training] Error getting operator progress: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_statistics():
        """
        Get training service statistics.

        Returns:
            200: Training statistics
            500: Server error
        """
        try:
            stats = training_service.get_statistics()

            if 'error' in stats:
                return jsonify(stats), 500

            return jsonify(stats), 200

        except Exception as e:
            logger.error(f"[Training] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Operator Training API',
    'version': '1.0.0',
    'description': 'REST API for operator training, skill development, and certification tracking',
    'base_path': '/api/v1/training',
    'endpoints': [
        {'path': '/health', 'method': 'GET', 'description': 'Health check'},
        {'path': '/sessions', 'method': 'POST', 'description': 'Start training session'},
        {'path': '/sessions/<session_id>/steps', 'method': 'POST', 'description': 'Record step performance'},
        {'path': '/sessions/<session_id>/complete', 'method': 'POST', 'description': 'Complete training session'},
        {'path': '/sessions/<session_id>/performance', 'method': 'GET', 'description': 'Get session performance'},
        {'path': '/operators/<operator_id>/progress', 'method': 'GET', 'description': 'Get operator progress'},
        {'path': '/statistics', 'method': 'GET', 'description': 'Get training statistics'}
    ]
}
