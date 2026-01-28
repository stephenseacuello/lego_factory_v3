"""
Digital Thread API Routes
REST API endpoints for product genealogy and traceability.
Part of Feature 3.1: Digital Thread Tracing (Phase 3)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Global service reference
digital_thread_service = None


def init_digital_thread_routes(app, service):
    """Initialize digital thread routes"""
    global digital_thread_service
    digital_thread_service = service

    bp = create_digital_thread_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/digital-thread')
    logger.info("[DigitalThread] Routes initialized")


def create_digital_thread_blueprint() -> Blueprint:
    """Create and configure digital thread blueprint"""
    bp = Blueprint('digital_thread', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = digital_thread_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'digital_thread',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[DigitalThread] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/threads', methods=['POST'])
    def create_thread():
        """
        Create a new digital thread.

        Request Body:
        {
            "thread_id": "DT-20260114-1234",
            "part_number": "PN-12345",
            "serial_number": "SN-67890",
            "material_data": {
                "material_type": "Aluminum 6061",
                "lot_number": "LOT-2024-001",
                "supplier": "Acme Materials",
                "certification_number": "CERT-12345",
                "traceability_code": "TC-ABC123"
            }
        }

        Returns:
            201: Thread created
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'thread_id' not in data:
                return jsonify({'error': 'thread_id required'}), 400

            thread_id = data['thread_id']
            part_number = data.get('part_number', '')
            serial_number = data.get('serial_number', '')
            material_data = data.get('material_data')

            success = digital_thread_service.create_thread(
                thread_id, part_number, serial_number, material_data
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Thread created',
                    'thread_id': thread_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to create thread'
                }), 500

        except Exception as e:
            logger.error(f"[DigitalThread] Error creating thread: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/threads/<thread_id>/operations', methods=['POST'])
    def record_operation(thread_id: str):
        """
        Record a manufacturing operation.

        Request Body:
        {
            "operation_id": "OP-001",
            "operation_name": "Roughing",
            "machine_id": "CNC-001",
            "status": "in_progress",
            "start_time": "2026-01-14T10:00:00Z",
            "parameters": {
                "feed_rate": 1000,
                "spindle_speed": 12000,
                "depth_of_cut": 2.5
            }
        }

        Returns:
            201: Operation recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'Operation data required'}), 400

            success = digital_thread_service.record_operation(thread_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Operation recorded',
                    'thread_id': thread_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record operation'
                }), 500

        except Exception as e:
            logger.error(f"[DigitalThread] Error recording operation: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/threads/<thread_id>/quality', methods=['POST'])
    def record_quality_check(thread_id: str):
        """
        Record a quality check.

        Request Body:
        {
            "check_id": "QC-001",
            "check_type": "Dimensional",
            "inspector_id": "INSP-123",
            "result": "pass",
            "measurements": {
                "length": 50.0,
                "width": 25.0,
                "thickness": 10.0
            },
            "notes": "Within tolerance"
        }

        Returns:
            201: Quality check recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'Quality check data required'}), 400

            success = digital_thread_service.record_quality_check(thread_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Quality check recorded',
                    'thread_id': thread_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record quality check'
                }), 500

        except Exception as e:
            logger.error(f"[DigitalThread] Error recording quality check: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/threads/<thread_id>/tool-changes', methods=['POST'])
    def record_tool_change(thread_id: str):
        """
        Record a tool change event.

        Request Body:
        {
            "change_id": "TC-001",
            "old_tool_id": "TOOL-100",
            "new_tool_id": "TOOL-101",
            "reason": "Tool wear",
            "tool_life_remaining": 5
        }

        Returns:
            201: Tool change recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'Tool change data required'}), 400

            success = digital_thread_service.record_tool_change(thread_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Tool change recorded',
                    'thread_id': thread_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record tool change'
                }), 500

        except Exception as e:
            logger.error(f"[DigitalThread] Error recording tool change: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/threads/<thread_id>/environment', methods=['POST'])
    def record_environment(thread_id: str):
        """
        Record environmental conditions.

        Request Body:
        {
            "operation_id": "OP-001",
            "temperature": 22.5,
            "humidity": 45.0,
            "ambient_vibration": 0.5
        }

        Returns:
            201: Environment recorded
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or 'operation_id' not in data:
                return jsonify({'error': 'operation_id and conditions required'}), 400

            operation_id = data.pop('operation_id')
            success = digital_thread_service.record_environmental_conditions(
                thread_id, operation_id, data
            )

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Environmental conditions recorded',
                    'thread_id': thread_id
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to record conditions'
                }), 500

        except Exception as e:
            logger.error(f"[DigitalThread] Error recording environment: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/threads/<thread_id>/complete', methods=['POST'])
    def complete_thread(thread_id: str):
        """
        Mark thread as completed.

        Returns:
            200: Thread completed
            500: Server error
        """
        try:
            success = digital_thread_service.complete_thread(thread_id)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Thread completed',
                    'thread_id': thread_id
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to complete thread'
                }), 500

        except Exception as e:
            logger.error(f"[DigitalThread] Error completing thread: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/threads/<thread_id>', methods=['GET'])
    def get_thread(thread_id: str):
        """
        Get complete thread data.

        Returns:
            200: Thread data
            404: Thread not found
            500: Server error
        """
        try:
            thread = digital_thread_service.get_thread(thread_id)

            if thread:
                return jsonify({
                    'success': True,
                    'data': thread
                }), 200
            else:
                return jsonify({
                    'error': f'Thread not found: {thread_id}'
                }), 404

        except Exception as e:
            logger.error(f"[DigitalThread] Error getting thread: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/threads', methods=['GET'])
    def list_threads():
        """
        List digital threads.

        Query Parameters:
            part_number: Filter by part number
            status: Filter by status (active, completed, failed)
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            limit: Maximum threads (default: 100)

        Returns:
            200: List of threads
            500: Server error
        """
        try:
            part_number = request.args.get('part_number')
            status = request.args.get('status')
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            limit = request.args.get('limit', 100, type=int)

            threads = digital_thread_service.list_threads(
                part_number=part_number,
                status=status,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            return jsonify({
                'count': len(threads),
                'threads': threads
            }), 200

        except Exception as e:
            logger.error(f"[DigitalThread] Error listing threads: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/threads/<thread_id>/genealogy', methods=['GET'])
    def get_genealogy(thread_id: str):
        """
        Get complete genealogy path.

        Returns:
            200: Genealogy path
            404: Thread not found
            500: Server error
        """
        try:
            genealogy = digital_thread_service.get_genealogy_path(thread_id)

            if genealogy:
                return jsonify({
                    'success': True,
                    'thread_id': thread_id,
                    'genealogy': genealogy,
                    'count': len(genealogy)
                }), 200
            else:
                return jsonify({
                    'error': f'Thread not found: {thread_id}'
                }), 404

        except Exception as e:
            logger.error(f"[DigitalThread] Error getting genealogy: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_statistics():
        """
        Get service statistics.

        Returns:
            200: Statistics
        """
        try:
            stats = digital_thread_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[DigitalThread] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Digital Thread API',
    'version': '1.0.0',
    'description': 'REST API for product genealogy and traceability tracking',
    'base_path': '/api/v1/digital-thread',
    'endpoints': [
        {'path': '/health', 'method': 'GET', 'description': 'Health check'},
        {'path': '/threads', 'method': 'POST', 'description': 'Create new thread'},
        {'path': '/threads/<thread_id>/operations', 'method': 'POST', 'description': 'Record operation'},
        {'path': '/threads/<thread_id>/quality', 'method': 'POST', 'description': 'Record quality check'},
        {'path': '/threads/<thread_id>/tool-changes', 'method': 'POST', 'description': 'Record tool change'},
        {'path': '/threads/<thread_id>/environment', 'method': 'POST', 'description': 'Record environment'},
        {'path': '/threads/<thread_id>/complete', 'method': 'POST', 'description': 'Complete thread'},
        {'path': '/threads/<thread_id>', 'method': 'GET', 'description': 'Get thread data'},
        {'path': '/threads', 'method': 'GET', 'description': 'List threads'},
        {'path': '/threads/<thread_id>/genealogy', 'method': 'GET', 'description': 'Get genealogy path'},
        {'path': '/statistics', 'method': 'GET', 'description': 'Get statistics'}
    ]
}
