"""
Dynamic Production Scheduler API Routes
REST API endpoints for real-time schedule optimization.
Part of Feature 4.1: Dynamic Scheduling (Phase 4)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Global service reference
dynamic_scheduler_service = None


def init_dynamic_scheduler_routes(app, service):
    """Initialize dynamic scheduler routes"""
    global dynamic_scheduler_service
    dynamic_scheduler_service = service

    bp = create_dynamic_scheduler_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/scheduler')
    logger.info("[DynamicScheduler] Routes initialized")


def create_dynamic_scheduler_blueprint() -> Blueprint:
    """Create and configure dynamic scheduler blueprint"""
    bp = Blueprint('dynamic_scheduler', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """
        Health check endpoint.

        Returns:
            200: Service healthy
            500: Service unhealthy
        """
        try:
            stats = dynamic_scheduler_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'dynamic_scheduling',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[DynamicScheduler] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/jobs', methods=['POST'])
    def create_job():
        """
        Create a new production job.

        Request Body:
        {
            "job_id": "JOB-001",
            "part_number": "PN-12345",
            "quantity": 100,
            "estimated_cycle_time": 45.5,
            "priority": "high",
            "due_date": "2025-01-20T00:00:00Z",
            "required_capabilities": ["3-axis", "coolant"]
        }

        Returns:
            201: Job created
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or not all(k in data for k in ['job_id', 'part_number', 'quantity', 'estimated_cycle_time', 'due_date']):
                return jsonify({'error': 'Required fields: job_id, part_number, quantity, estimated_cycle_time, due_date'}), 400

            success = dynamic_scheduler_service.create_job(data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Job created successfully',
                    'job_id': data['job_id']
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create job'
                }), 500

        except Exception as e:
            logger.error(f"[DynamicScheduler] Error creating job: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/jobs/<job_id>/status', methods=['PUT'])
    def update_job_status(job_id: str):
        """
        Update job status.

        Request Body:
        {
            "status": "in_progress"
        }

        Returns:
            200: Status updated
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'status' not in data:
                return jsonify({'error': 'status required'}), 400

            success = dynamic_scheduler_service.update_job_status(job_id, data['status'])

            if success:
                return jsonify({
                    'success': True,
                    'job_id': job_id,
                    'status': data['status']
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update job status'
                }), 500

        except Exception as e:
            logger.error(f"[DynamicScheduler] Error updating job status: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/machines/<machine_id>/status', methods=['PUT'])
    def update_machine_status(machine_id: str):
        """
        Update machine status for scheduling.

        Request Body:
        {
            "available": true,
            "current_utilization": 0.75,
            "capabilities": ["3-axis", "4-axis", "coolant"]
        }

        Returns:
            200: Status updated
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'Request body required'}), 400

            success = dynamic_scheduler_service.update_machine_status(machine_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'machine_id': machine_id
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update machine status'
                }), 500

        except Exception as e:
            logger.error(f"[DynamicScheduler] Error updating machine status: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/optimize', methods=['POST'])
    def optimize_schedule():
        """
        Optimize production schedule.

        Request Body:
        {
            "strategy": "minimize_makespan"
        }

        Available strategies:
        - fifo: First In First Out
        - edd: Earliest Due Date
        - spt: Shortest Processing Time
        - priority: Highest Priority First
        - minimize_makespan: Critical Ratio (default)

        Returns:
            200: Schedule optimized
            500: Server error
        """
        try:
            data = request.get_json() or {}
            strategy = data.get('strategy', 'minimize_makespan')

            schedule = dynamic_scheduler_service.optimize_schedule(strategy)

            if 'error' in schedule:
                return jsonify(schedule), 500

            return jsonify({
                'success': True,
                'schedule': schedule
            }), 200

        except Exception as e:
            logger.error(f"[DynamicScheduler] Error optimizing schedule: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/schedule/current', methods=['GET'])
    def get_current_schedule():
        """
        Get current production schedule.

        Returns:
            200: Current schedule
            404: No schedule found
            500: Server error
        """
        try:
            schedule = dynamic_scheduler_service.get_current_schedule()

            if schedule:
                return jsonify({
                    'success': True,
                    'schedule': schedule
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'No current schedule found'
                }), 404

        except Exception as e:
            logger.error(f"[DynamicScheduler] Error getting current schedule: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_statistics():
        """
        Get scheduler statistics.

        Returns:
            200: Scheduler statistics
            500: Server error
        """
        try:
            stats = dynamic_scheduler_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[DynamicScheduler] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Dynamic Production Scheduler API',
    'version': '1.0.0',
    'description': 'REST API for real-time production schedule optimization',
    'base_path': '/api/v1/scheduler',
    'endpoints': [
        {'path': '/health', 'method': 'GET', 'description': 'Health check'},
        {'path': '/jobs', 'method': 'POST', 'description': 'Create production job'},
        {'path': '/jobs/<job_id>/status', 'method': 'PUT', 'description': 'Update job status'},
        {'path': '/machines/<machine_id>/status', 'method': 'PUT', 'description': 'Update machine status'},
        {'path': '/optimize', 'method': 'POST', 'description': 'Optimize production schedule'},
        {'path': '/schedule/current', 'method': 'GET', 'description': 'Get current schedule'},
        {'path': '/statistics', 'method': 'GET', 'description': 'Get scheduler statistics'}
    ]
}
