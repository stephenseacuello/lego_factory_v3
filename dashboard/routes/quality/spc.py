"""
SPC API - Statistical Process Control endpoints.
"""

from flask import Blueprint, jsonify, request, render_template

from models import get_db_session
from services.quality import SPCService

spc_bp = Blueprint('spc', __name__, url_prefix='/spc')


# Dashboard Page Route
@spc_bp.route('/page', methods=['GET'])
def spc_page():
    """Render SPC dashboard page."""
    return render_template('pages/quality/spc_dashboard.html')


@spc_bp.route('/control-chart/<metric_name>', methods=['GET'])
def get_control_chart(metric_name: str):
    """
    Get control chart data for X-bar and R charts.

    Query params:
    - subgroup_size: Size of subgroups (default 5)
    - num_points: Number of subgroups (default 25)
    """
    subgroup_size = request.args.get('subgroup_size', 5, type=int)
    num_points = request.args.get('num_points', 25, type=int)

    with get_db_session() as session:
        service = SPCService(session)
        data = service.get_control_chart_data(
            metric_name=metric_name,
            subgroup_size=subgroup_size,
            num_points=num_points
        )

        return jsonify(data)


@spc_bp.route('/out-of-control/<metric_name>', methods=['GET'])
def check_out_of_control(metric_name: str):
    """
    Check for out-of-control conditions (Western Electric rules).

    Query params:
    - subgroup_size: Size of subgroups (default 5)
    """
    subgroup_size = request.args.get('subgroup_size', 5, type=int)

    with get_db_session() as session:
        service = SPCService(session)
        result = service.check_out_of_control(
            metric_name=metric_name,
            subgroup_size=subgroup_size
        )

        return jsonify(result)


@spc_bp.route('/process-performance/<metric_name>', methods=['GET'])
def get_process_performance(metric_name: str):
    """
    Get Pp and Ppk (process performance indices).

    Query params:
    - limit: Number of samples (default 100)
    """
    limit = request.args.get('limit', 100, type=int)

    with get_db_session() as session:
        service = SPCService(session)
        result = service.calculate_process_performance(
            metric_name=metric_name,
            limit=limit
        )

        return jsonify(result)


@spc_bp.route('/dashboard', methods=['GET'])
def get_spc_dashboard():
    """
    Get SPC dashboard with key metrics for all tracked dimensions.

    Shows Cpk/Ppk summary and OOC status for LEGO critical dimensions.
    """
    critical_metrics = [
        'lego_stud_diameter',
        'lego_stud_height',
        'lego_wall_thickness',
        'lego_stud_pitch'
    ]

    with get_db_session() as session:
        service = SPCService(session)

        dashboard = []
        for metric in critical_metrics:
            try:
                performance = service.calculate_process_performance(metric, limit=50)
                ooc = service.check_out_of_control(metric, subgroup_size=5)

                dashboard.append({
                    'metric': metric,
                    'ppk': performance.get('ppk'),
                    'sigma_level': performance.get('sigma_level'),
                    'interpretation': performance.get('interpretation'),
                    'in_control': ooc.get('in_control', True),
                    'sample_count': performance.get('sample_count', 0)
                })
            except Exception:
                dashboard.append({
                    'metric': metric,
                    'ppk': None,
                    'message': 'Insufficient data'
                })

        return jsonify({
            'metrics': dashboard,
            'summary': {
                'total_metrics': len(dashboard),
                'in_control': sum(1 for d in dashboard if d.get('in_control', True)),
                'capable': sum(1 for d in dashboard if (d.get('ppk') or 0) >= 1.0)
            }
        })
