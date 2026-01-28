"""
Scenario Planning API Routes
REST API endpoints for production scenario planning.
Part of Feature 4.2: Scenario Planning (Phase 4)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Global service reference
scenario_planning_service = None


def init_scenario_planning_routes(app, service):
    """Initialize scenario planning routes"""
    global scenario_planning_service
    scenario_planning_service = service

    bp = create_scenario_planning_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/scenarios')
    logger.info("[ScenarioPlanning] Routes initialized")


def create_scenario_planning_blueprint() -> Blueprint:
    """Create and configure scenario planning blueprint"""
    bp = Blueprint('scenario_planning', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        try:
            stats = scenario_planning_service.get_statistics()
            return jsonify({'status': 'healthy', 'service': 'scenario_planning', 'details': stats}), 200
        except Exception as e:
            logger.error(f"[ScenarioPlanning] Health check failed: {e}")
            return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

    @bp.route('/', methods=['POST'])
    def create_scenario():
        """Create new scenario."""
        try:
            data = request.get_json()
            if not data or 'scenario_id' not in data or 'name' not in data:
                return jsonify({'error': 'scenario_id and name required'}), 400

            success = scenario_planning_service.create_scenario(data)
            if success:
                return jsonify({'success': True, 'scenario_id': data['scenario_id']}), 201
            return jsonify({'success': False, 'error': 'Failed to create scenario'}), 500
        except Exception as e:
            logger.error(f"[ScenarioPlanning] Error creating scenario: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<scenario_id>/evaluate', methods=['POST'])
    def evaluate_scenario(scenario_id: str):
        """Evaluate scenario."""
        try:
            data = request.get_json()
            success = scenario_planning_service.evaluate_scenario(scenario_id, data)
            if success:
                return jsonify({'success': True, 'scenario_id': scenario_id}), 200
            return jsonify({'success': False, 'error': 'Failed to evaluate scenario'}), 500
        except Exception as e:
            logger.error(f"[ScenarioPlanning] Error evaluating scenario: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/compare', methods=['POST'])
    def compare_scenarios():
        """Compare two scenarios."""
        try:
            data = request.get_json()
            if not data or 'scenario1_id' not in data or 'scenario2_id' not in data:
                return jsonify({'error': 'scenario1_id and scenario2_id required'}), 400

            comparison = scenario_planning_service.compare_scenarios(data['scenario1_id'], data['scenario2_id'])
            if 'error' in comparison:
                return jsonify(comparison), 500
            return jsonify({'success': True, 'comparison': comparison}), 200
        except Exception as e:
            logger.error(f"[ScenarioPlanning] Error comparing scenarios: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_statistics():
        """Get statistics."""
        try:
            stats = scenario_planning_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[ScenarioPlanning] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


API_DOCS = {
    'name': 'Scenario Planning API',
    'version': '1.0.0',
    'description': 'REST API for production scenario planning and what-if analysis',
    'base_path': '/api/v1/scenarios'
}
