"""
Custom KPI Builder API Routes
REST API endpoints for custom KPI definition and management.
Part of Feature 4.5: Custom KPI Builder (Phase 4)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Global service reference
kpi_builder_service = None


def init_kpi_builder_routes(app, service):
    """Initialize KPI builder routes"""
    global kpi_builder_service
    kpi_builder_service = service

    bp = create_kpi_builder_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/kpis')
    logger.info("[KPI Builder] Routes initialized")


def create_kpi_builder_blueprint() -> Blueprint:
    """Create and configure KPI builder blueprint"""
    bp = Blueprint('kpi_builder', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """
        Health check endpoint.

        Returns:
            200: Service healthy
            500: Service unhealthy
        """
        try:
            stats = kpi_builder_service.get_statistics()
            return jsonify({
                'status': 'healthy',
                'service': 'custom_kpi_builder',
                'details': stats
            }), 200
        except Exception as e:
            logger.error(f"[KPI Builder] Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e)
            }), 500

    @bp.route('/', methods=['POST'])
    def create_kpi():
        """
        Create custom KPI.

        Request Body:
        {
            "kpi_id": "kpi_production_efficiency",
            "name": "Production Efficiency",
            "description": "Overall production efficiency metric",
            "formula": "{production.throughput} / {production.target} * 100",
            "unit": "%",
            "data_sources": ["production", "machine_status"],
            "aggregation_method": "average",
            "time_window": 3600,
            "thresholds": [
                {
                    "operator": "lt",
                    "value": 70.0,
                    "severity": "warning",
                    "message": "Production efficiency below target"
                },
                {
                    "operator": "lt",
                    "value": 50.0,
                    "severity": "critical",
                    "message": "Production efficiency critically low"
                }
            ],
            "category": "production",
            "enabled": true
        }

        Returns:
            201: KPI created
            400: Invalid request
            500: Server error
        """
        try:
            data = request.get_json()

            if not data or not all(k in data for k in ['kpi_id', 'name', 'formula']):
                return jsonify({
                    'error': 'Required fields: kpi_id, name, formula'
                }), 400

            result = kpi_builder_service.create_kpi(data)

            if 'error' in result:
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'message': 'KPI created successfully',
                'data': result
            }), 201

        except Exception as e:
            logger.error(f"[KPI Builder] Error creating KPI: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<kpi_id>', methods=['PUT'])
    def update_kpi(kpi_id: str):
        """
        Update KPI definition.

        Request Body: (Same structure as create, all fields optional)

        Returns:
            200: KPI updated
            404: KPI not found
            500: Server error
        """
        try:
            data = request.get_json()

            if not data:
                return jsonify({'error': 'Request body required'}), 400

            result = kpi_builder_service.update_kpi(kpi_id, data)

            if 'error' in result:
                if 'not found' in result['error']:
                    return jsonify(result), 404
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'message': 'KPI updated successfully',
                'data': result
            }), 200

        except Exception as e:
            logger.error(f"[KPI Builder] Error updating KPI: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<kpi_id>', methods=['DELETE'])
    def delete_kpi(kpi_id: str):
        """
        Delete KPI.

        Returns:
            200: KPI deleted
            404: KPI not found
            500: Server error
        """
        try:
            result = kpi_builder_service.delete_kpi(kpi_id)

            if 'error' in result:
                if 'not found' in result['error']:
                    return jsonify(result), 404
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'message': 'KPI deleted successfully',
                'data': result
            }), 200

        except Exception as e:
            logger.error(f"[KPI Builder] Error deleting KPI: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<kpi_id>', methods=['GET'])
    def get_kpi(kpi_id: str):
        """
        Get KPI definition.

        Returns:
            200: KPI definition
            404: KPI not found
            500: Server error
        """
        try:
            result = kpi_builder_service.get_kpi(kpi_id)

            if 'error' in result:
                if 'not found' in result['error']:
                    return jsonify(result), 404
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'data': result['kpi']
            }), 200

        except Exception as e:
            logger.error(f"[KPI Builder] Error getting KPI: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/', methods=['GET'])
    def list_kpis():
        """
        List all KPIs.

        Query Parameters:
        - category: Filter by category (optional)

        Returns:
            200: KPI list
            500: Server error
        """
        try:
            category = request.args.get('category')

            result = kpi_builder_service.get_all_kpis(category)

            if 'error' in result:
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'data': result['kpis'],
                'total': result['total']
            }), 200

        except Exception as e:
            logger.error(f"[KPI Builder] Error listing KPIs: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<kpi_id>/calculate', methods=['POST'])
    def calculate_kpi(kpi_id: str):
        """
        Calculate KPI value.

        Request Body (optional):
        {
            "context_data": {
                "production.throughput": 85.0,
                "production.target": 100.0
            }
        }

        Returns:
            200: Calculated value
            404: KPI not found
            500: Server error
        """
        try:
            data = request.get_json() or {}
            context_data = data.get('context_data')

            result = kpi_builder_service.calculate_kpi(kpi_id, context_data)

            if 'error' in result:
                if 'not found' in result['error'] or 'disabled' in result['error']:
                    return jsonify(result), 404
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'data': result
            }), 200

        except Exception as e:
            logger.error(f"[KPI Builder] Error calculating KPI: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<kpi_id>/history', methods=['GET'])
    def get_kpi_history(kpi_id: str):
        """
        Get KPI value history.

        Query Parameters:
        - hours: Number of hours to look back (default: 24)

        Returns:
            200: Historical values
            500: Server error
        """
        try:
            hours = request.args.get('hours', 24, type=int)

            result = kpi_builder_service.get_kpi_history(kpi_id, hours)

            if 'error' in result:
                return jsonify(result), 500

            return jsonify({
                'success': True,
                'data': result
            }), 200

        except Exception as e:
            logger.error(f"[KPI Builder] Error getting KPI history: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_statistics():
        """
        Get KPI builder statistics.

        Returns:
            200: KPI builder statistics
            500: Server error
        """
        try:
            stats = kpi_builder_service.get_statistics()

            if 'error' in stats:
                return jsonify(stats), 500

            return jsonify(stats), 200

        except Exception as e:
            logger.error(f"[KPI Builder] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Custom KPI Builder API',
    'version': '1.0.0',
    'description': 'REST API for custom KPI definition, calculation, and management',
    'base_path': '/api/v1/kpis',
    'endpoints': [
        {'path': '/health', 'method': 'GET', 'description': 'Health check'},
        {'path': '/', 'method': 'POST', 'description': 'Create custom KPI'},
        {'path': '/<kpi_id>', 'method': 'PUT', 'description': 'Update KPI definition'},
        {'path': '/<kpi_id>', 'method': 'DELETE', 'description': 'Delete KPI'},
        {'path': '/<kpi_id>', 'method': 'GET', 'description': 'Get KPI definition'},
        {'path': '/', 'method': 'GET', 'description': 'List all KPIs'},
        {'path': '/<kpi_id>/calculate', 'method': 'POST', 'description': 'Calculate KPI value'},
        {'path': '/<kpi_id>/history', 'method': 'GET', 'description': 'Get KPI history'},
        {'path': '/statistics', 'method': 'GET', 'description': 'Get KPI builder statistics'}
    ]
}
