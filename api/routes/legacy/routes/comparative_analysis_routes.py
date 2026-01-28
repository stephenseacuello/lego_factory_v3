"""
Comparative Analysis API Routes
REST API endpoints for comparing machining runs and analyzing trends.
Part of Feature 2.4: Comparative Analysis (Phase 2)
"""

import logging
from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

# Global service reference
comparative_analysis_service = None


def init_comparative_analysis_routes(app, service):
    """Initialize comparative analysis routes"""
    global comparative_analysis_service
    comparative_analysis_service = service

    bp = create_comparative_analysis_blueprint()
    app.register_blueprint(bp, url_prefix='/api/v1/comparative-analysis')
    logger.info("[ComparativeAnalysis] Routes initialized")


def create_comparative_analysis_blueprint() -> Blueprint:
    """Create and configure comparative analysis blueprint"""
    bp = Blueprint('comparative_analysis', __name__)

    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        try:
            stats = comparative_analysis_service.get_statistics()
            return jsonify({'status': 'healthy', 'service': 'comparative_analysis', 'details': stats}), 200
        except Exception as e:
            logger.error(f"[ComparativeAnalysis] Health check failed: {e}")
            return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

    @bp.route('/runs/<run_id>', methods=['POST'])
    def store_run(run_id: str):
        """Store machining run data"""
        try:
            data = request.get_json()
            if not data or 'machine_id' not in data:
                return jsonify({'error': 'machine_id required'}), 400

            machine_id = data.pop('machine_id')
            success = comparative_analysis_service.store_run_data(run_id, machine_id, data)

            return jsonify({'success': success, 'run_id': run_id}), 201 if success else 500
        except Exception as e:
            logger.error(f"[ComparativeAnalysis] Error storing run: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/compare/<run_id1>/<run_id2>', methods=['GET'])
    def compare_runs(run_id1: str, run_id2: str):
        """Compare two runs"""
        try:
            comparison = comparative_analysis_service.compare_runs(run_id1, run_id2)
            if 'error' in comparison:
                return jsonify(comparison), 404
            return jsonify({'success': True, 'data': comparison}), 200
        except Exception as e:
            logger.error(f"[ComparativeAnalysis] Error comparing runs: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/trends/<metric>', methods=['GET'])
    def get_trends(machine_id: str, metric: str):
        """Analyze trends for a metric"""
        try:
            time_range = request.args.get('time_range', '-7d')
            trends = comparative_analysis_service.analyze_trends(machine_id, metric, time_range)
            if 'error' in trends:
                return jsonify(trends), 500
            return jsonify({'success': True, 'data': trends}), 200
        except Exception as e:
            logger.error(f"[ComparativeAnalysis] Error analyzing trends: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/<machine_id>/anomalies/<metric>', methods=['GET'])
    def detect_anomalies(machine_id: str, metric: str):
        """Detect anomalies in run data"""
        try:
            threshold = request.args.get('threshold', 2.5, type=float)
            anomalies = comparative_analysis_service.detect_anomalies(machine_id, metric, threshold)
            if 'error' in anomalies:
                return jsonify(anomalies), 500
            return jsonify({'success': True, 'data': anomalies}), 200
        except Exception as e:
            logger.error(f"[ComparativeAnalysis] Error detecting anomalies: {e}")
            return jsonify({'error': str(e)}), 500

    @bp.route('/statistics', methods=['GET'])
    def get_service_statistics():
        """Get service statistics"""
        try:
            stats = comparative_analysis_service.get_statistics()
            return jsonify(stats), 200
        except Exception as e:
            logger.error(f"[ComparativeAnalysis] Error getting statistics: {e}")
            return jsonify({'error': str(e)}), 500

    return bp


# API Documentation
API_DOCS = {
    'name': 'Comparative Analysis API',
    'version': '1.0.0',
    'description': 'REST API for comparing machining runs',
    'base_path': '/api/v1/comparative-analysis',
    'endpoints': [
        {'path': '/health', 'method': 'GET', 'description': 'Health check'},
        {'path': '/runs/<run_id>', 'method': 'POST', 'description': 'Store run data'},
        {'path': '/compare/<run_id1>/<run_id2>', 'method': 'GET', 'description': 'Compare two runs'},
        {'path': '/<machine_id>/trends/<metric>', 'method': 'GET', 'description': 'Analyze trends'},
        {'path': '/<machine_id>/anomalies/<metric>', 'method': 'GET', 'description': 'Detect anomalies'},
        {'path': '/statistics', 'method': 'GET', 'description': 'Get service statistics'}
    ]
}
