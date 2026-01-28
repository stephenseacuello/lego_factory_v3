"""
ISO 23247 Digital Twin Compliance API Routes
REST API endpoints for ISO 23247 compliant digital twin operations.
Part of Feature 1.4: ISO 23247 Compliance (MEDIUM PRIORITY)
"""

import logging
from flask import Blueprint, jsonify, request
from typing import Dict

logger = logging.getLogger(__name__)

# Global service reference
iso23247_service = None


def init_iso23247_routes(app, service):
    """
    Initialize ISO 23247 routes with service dependency.

    Args:
        app: Flask application instance
        service: ISO23247Service instance
    """
    global iso23247_service
    iso23247_service = service

    bp = create_iso23247_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/iso23247')
    logger.info("[ISO23247] Routes initialized")


def create_iso23247_blueprint() -> Blueprint:
    """Create and configure ISO 23247 blueprint"""
    bp = Blueprint('iso23247', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = iso23247_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'iso23247',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[ISO23247] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/entities', methods=['GET'])
    def list_entities():
        """
        List all registered ISO 23247 entities.

        Returns:
            200: List of entity IDs
            500: Server error
        """
        try:
            entities = iso23247_service.list_entities()
            return jsonify({
                'count': len(entities),
                'entities': entities
            }), 200
        except Exception as e:
            logger.error(f"[ISO23247] Error listing entities: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/entities/<entity_id>/state', methods=['POST'])
    def store_entity_state(entity_id: str):
        """
        Store ISO 23247 compliant entity state.

        Request Body:
        {
            "EntityIdentification": {
                "EntityId": "CNC-001",
                "EntityType": "MachineToolResource",
                "ManufacturingSite": "Plant-A",
                "Timestamp": "2025-01-14T..."
            },
            "ObservableInformation": {
                "Position": {"X": 0.1, "Y": 0.05, "Z": 0.2},
                "Orientation": {"Roll": 0, "Pitch": 0, "Yaw": 0},
                "Velocity": {"VX": 0, "VY": 0, "VZ": 0},
                "Status": "Operating"
            },
            "CapabilityInformation": {
                "AvailableCapabilities": ["3-axis-milling", "tool-change"],
                "MaxFeedRate": 5000,
                "MaxSpindleSpeed": 24000,
                "WorkspaceVolume": {
                    "XMin": -200, "XMax": 200,
                    "YMin": -150, "YMax": 150,
                    "ZMin": 0, "ZMax": 300
                }
            },
            "StateVersion": 42
        }

        Returns:
            201: State stored successfully
            400: Invalid request data
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'No data provided'}), 400

            # Validate required sections
            required_sections = ['EntityIdentification', 'ObservableInformation', 'CapabilityInformation']
            for section in required_sections:
                if section not in data:
                    return jsonify({'error': f'Missing required section: {section}'}), 400

            # Store state
            success = iso23247_service.store_entity_state(entity_id, data)

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Entity state stored',
                    'entity_id': entity_id,
                    'state_version': data.get('StateVersion', 0)
                }), 201
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to store state'
                }), 500

        except Exception as e:
            logger.error(f"[ISO23247] Error storing state: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/entities/<entity_id>/state', methods=['GET'])
    def get_entity_state(entity_id: str):
        """
        Get current state for an entity.

        Returns:
            200: Current state data
            404: Entity not found
            500: Server error
        """
        try:
            state = iso23247_service.get_entity_state(entity_id)

            if state:
                return jsonify({
                    'entity_id': entity_id,
                    'state': state
                }), 200
            else:
                return jsonify({
                    'error': f'Entity {entity_id} not found'
                }), 404

        except Exception as e:
            logger.error(f"[ISO23247] Error retrieving state: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/entities/<entity_id>/history', methods=['GET'])
    def get_state_history(entity_id: str):
        """
        Get state history for an entity.

        Query Parameters:
            start_time: Start time (RFC3339 or relative like '-1h')
            end_time: End time (RFC3339 or relative like 'now')
            limit: Maximum records (default: 100)

        Returns:
            200: Historical state data
            500: Server error
        """
        try:
            start_time = request.args.get('start_time')
            end_time = request.args.get('end_time')
            limit = request.args.get('limit', 100, type=int)

            history = iso23247_service.get_state_history(
                entity_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )

            return jsonify({
                'entity_id': entity_id,
                'count': len(history),
                'history': history
            }), 200

        except Exception as e:
            logger.error(f"[ISO23247] Error retrieving history: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/entities/<entity_id>/validate', methods=['POST'])
    def validate_compliance(entity_id: str):
        """
        Validate ISO 23247 compliance for entity state.

        Request Body: Complete ISO 23247 state structure

        Returns:
            200: Validation report
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'No data provided'}), 400

            report = iso23247_service.validate_compliance(entity_id, data)

            return jsonify({
                'success': True,
                'report': report
            }), 200

        except Exception as e:
            logger.error(f"[ISO23247] Error validating compliance: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_service_statistics():
        """
        Get ISO 23247 service statistics.

        Returns:
            200: Service statistics
        """
        try:
            stats = iso23247_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[ISO23247] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/compliance/report', methods=['GET'])
    def get_compliance_report():
        """
        Get compliance report for all entities.

        Returns:
            200: Aggregated compliance report
            500: Server error
        """
        try:
            entities = iso23247_service.list_entities()

            reports = []
            total_compliant = 0
            total_score = 0

            for entity_id in entities:
                state = iso23247_service.get_entity_state(entity_id)
                if state:
                    report = iso23247_service.validate_compliance(entity_id, state)
                    reports.append(report)

                    if report['is_compliant']:
                        total_compliant += 1
                    total_score += report['compliance_score']

            avg_score = total_score / len(entities) if entities else 0

            return jsonify({
                'total_entities': len(entities),
                'compliant_entities': total_compliant,
                'non_compliant_entities': len(entities) - total_compliant,
                'average_compliance_score': avg_score,
                'entity_reports': reports
            }), 200

        except Exception as e:
            logger.error(f"[ISO23247] Error generating compliance report: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'ISO 23247 Digital Twin API',
    'version': '1.0.0',
    'description': 'REST API for ISO 23247 compliant digital twin operations',
    'base_path': '/api/v1/iso23247',
    'standard': 'ISO 23247: Digital twin framework for manufacturing',
    'parts_implemented': [
        'Part 1: Overview and general principles',
        'Part 2: Reference architecture',
        'Part 3: Digital representation of manufacturing elements',
        'Part 4: Information exchange'
    ],
    'endpoints': [
        {
            'path': '/health',
            'method': 'GET',
            'description': 'Health check endpoint'
        },
        {
            'path': '/entities',
            'method': 'GET',
            'description': 'List all registered entities'
        },
        {
            'path': '/entities/<entity_id>/state',
            'method': 'POST',
            'description': 'Store entity state (ISO 23247-3 compliant)'
        },
        {
            'path': '/entities/<entity_id>/state',
            'method': 'GET',
            'description': 'Get current entity state'
        },
        {
            'path': '/entities/<entity_id>/history',
            'method': 'GET',
            'description': 'Get state history'
        },
        {
            'path': '/entities/<entity_id>/validate',
            'method': 'POST',
            'description': 'Validate ISO 23247 compliance'
        },
        {
            'path': '/statistics',
            'method': 'GET',
            'description': 'Get service statistics'
        },
        {
            'path': '/compliance/report',
            'method': 'GET',
            'description': 'Get aggregated compliance report'
        }
    ]
}
