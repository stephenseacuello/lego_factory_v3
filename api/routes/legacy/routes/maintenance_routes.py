"""
AR Maintenance API Routes
REST API endpoints for AR-guided maintenance procedures.
Part of Feature 4.4: AR Maintenance Overlay (Phase 4)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Global service reference
maintenance_service = None


def init_maintenance_routes(app, service):
    """Initialize maintenance routes"""
    global maintenance_service
    maintenance_service = service

    bp = create_maintenance_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/maintenance')
    logger.info("[Maintenance] Routes initialized")


def create_maintenance_blueprint() -> Blueprint:
    """Create and configure maintenance blueprint"""
    bp = Blueprint('maintenance', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """
        Health check endpoint.

        Returns:
            200: Service healthy
            500: Service unhealthy
        """
        try:
            stats = maintenance_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'ar_maintenance',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[Maintenance] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/procedures', methods=['POST'])
    def start_procedure():
        """
        Start AR maintenance procedure.

        Request Body:
        {
            "procedure_id": "MAINT-001",
            "machine_id": "CNC-001",
            "technician_id": "TECH-001",
            "procedure_type": "preventive",
            "priority": "normal",
            "estimated_duration": 1800.0,
            "step_count": 5,
            "ar_enabled": true
        }

        Returns:
            201: Procedure started
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or not all(k in data for k in ['procedure_id', 'machine_id', 'technician_id']):
                return jsonify({
                    'error': 'Required fields: procedure_id, machine_id, technician_id'
                }), 400

            result = maintenance_service.start_procedure(data)

            if 'error' in result:
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'message': 'Maintenance procedure started',
                'data': result
            }), 201

        except Exception as e:
            logger.error(f"[Maintenance] Error starting procedure: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/procedures/<procedure_id>/steps', methods=['POST'])
    def complete_step(procedure_id: str):
        """
        Record completion of maintenance step.

        Request Body:
        {
            "step_id": "step-001",
            "step_index": 0,
            "completion_time": 300.0,
            "success": true,
            "issues_found": ["Issue 1", "Issue 2"],
            "ar_assisted": true
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

            success = maintenance_service.record_step_completion(procedure_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Step completion recorded',
                    'procedure_id': procedure_id,
                    'step_id': data['step_id']
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record step completion'
                }), 500

        except Exception as e:
            logger.error(f"[Maintenance] Error recording step: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/procedures/<procedure_id>/complete', methods=['POST'])
    def complete_procedure(procedure_id: str):
        """
        Complete AR maintenance procedure.

        Request Body:
        {
            "machine_id": "CNC-001",
            "technician_id": "TECH-001",
            "duration": 1650.0,
            "steps_completed": 5,
            "total_steps": 5,
            "success": true,
            "parts_replaced": [
                {
                    "part_number": "PART-001",
                    "part_type": "bearing",
                    "quantity": 2,
                    "cost": 150.00
                }
            ],
            "notes": "Maintenance completed successfully"
        }

        Returns:
            200: Procedure completed
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or not all(k in data for k in ['machine_id', 'technician_id']):
                return jsonify({
                    'error': 'Required fields: machine_id, technician_id'
                }), 400

            result = maintenance_service.complete_procedure(procedure_id, data)

            if 'error' in result:
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'message': 'Maintenance procedure completed',
                'data': result
            }), 200

        except Exception as e:
            logger.error(f"[Maintenance] Error completing procedure: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/procedures/<procedure_id>', methods=['GET'])
    def get_procedure_details(procedure_id: str):
        """
        Get detailed information about a procedure.

        Returns:
            200: Procedure details
            404: Procedure not found
            500: Server error
        """
        try:
            details = maintenance_service.get_procedure_details(procedure_id)

            if 'error' in details:
                if details['error'] == 'Procedure not found':
                    return jsonify(details), 404
                return jsonify(details), 500

            return jsonify({
                'success': True,
                'data': details
            }), 200

        except Exception as e:
            logger.error(f"[Maintenance] Error getting procedure details: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/machines/<machine_id>/history', methods=['GET'])
    def get_machine_history(machine_id: str):
        """
        Get maintenance history for a machine.

        Query Parameters:
        - days: Number of days to look back (default: 30)

        Returns:
            200: Maintenance history
            500: Server error
        """
        try:
            days = request.args.get('days', 30, type=int)

            history = maintenance_service.get_machine_maintenance_history(machine_id, days)

            if 'error' in history:
                return jsonify(history), 500

            return jsonify({
                'success': True,
                'data': history
            }), 200

        except Exception as e:
            logger.error(f"[Maintenance] Error getting machine history: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/annotations', methods=['POST'])
    def add_annotation():
        """
        Record AR annotation from remote expert.

        Request Body:
        {
            "procedure_id": "MAINT-001",
            "annotation_type": "arrow",
            "position": {
                "x": 1.0,
                "y": 2.0,
                "z": 3.0
            },
            "content": "Check this connection",
            "expert_id": "EXPERT-001"
        }

        Returns:
            201: Annotation recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'procedure_id' not in data:
                return jsonify({'error': 'procedure_id required'}), 400

            success = maintenance_service.record_ar_annotation(data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'AR annotation recorded'
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record annotation'
                }), 500

        except Exception as e:
            logger.error(f"[Maintenance] Error recording annotation: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_statistics():
        """
        Get maintenance service statistics.

        Returns:
            200: Maintenance statistics
            500: Server error
        """
        try:
            stats = maintenance_service.get_statistics()

            if 'error' in stats:
                return jsonify(stats), 500

            return jsonify(stats), 200

        except Exception as e:
            logger.error(f"[Maintenance] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'AR Maintenance API',
    'version': '1.0.0',
    'description': 'REST API for AR-guided maintenance procedures and tracking',
    'base_path': '/api/v1/maintenance',
    'endpoints': [
        {'path': '/health', 'method': 'GET', 'description': 'Health check'},
        {'path': '/procedures', 'method': 'POST', 'description': 'Start maintenance procedure'},
        {'path': '/procedures/<procedure_id>/steps', 'method': 'POST', 'description': 'Record step completion'},
        {'path': '/procedures/<procedure_id>/complete', 'method': 'POST', 'description': 'Complete maintenance procedure'},
        {'path': '/procedures/<procedure_id>', 'method': 'GET', 'description': 'Get procedure details'},
        {'path': '/machines/<machine_id>/history', 'method': 'GET', 'description': 'Get machine maintenance history'},
        {'path': '/annotations', 'method': 'POST', 'description': 'Add AR annotation'},
        {'path': '/statistics', 'method': 'GET', 'description': 'Get maintenance statistics'}
    ]
}
