"""
Demand API - Demand forecasting and planning.
"""

from flask import Blueprint, jsonify, request

from models import get_db_session
from services.erp import DemandService

demand_bp = Blueprint('demand', __name__, url_prefix='/demand')


@demand_bp.route('/history/<part_id>', methods=['GET'])
def get_demand_history(part_id: str):
    """
    Get demand history for a part.

    Query params:
    - periods: Number of periods (default 12)
    - period_type: 'day', 'week', or 'month' (default 'month')
    """
    periods = request.args.get('periods', 12, type=int)
    period_type = request.args.get('period_type', 'month')

    with get_db_session() as session:
        service = DemandService(session)
        history = service.get_demand_history(
            part_id=part_id,
            periods=periods,
            period_type=period_type
        )

        return jsonify({
            'part_id': part_id,
            'period_type': period_type,
            'history': history
        })


@demand_bp.route('/forecast/<part_id>', methods=['GET'])
def get_forecast(part_id: str):
    """
    Get demand forecast for a part.

    Query params:
    - periods_ahead: Number of periods to forecast (default 3)
    - method: 'moving_average' or 'exponential_smoothing' (default)
    """
    periods_ahead = request.args.get('periods_ahead', 3, type=int)
    method = request.args.get('method', 'exponential_smoothing')

    with get_db_session() as session:
        service = DemandService(session)

        try:
            if method == 'moving_average':
                forecasts = service.forecast_moving_average(
                    part_id=part_id,
                    periods_ahead=periods_ahead
                )
            else:
                forecasts = service.forecast_exponential_smoothing(
                    part_id=part_id,
                    periods_ahead=periods_ahead
                )

            return jsonify({
                'part_id': part_id,
                'method': method,
                'forecasts': [
                    {
                        'period': f.period,
                        'forecast': f.forecast_quantity,
                        'confidence_low': f.confidence_low,
                        'confidence_high': f.confidence_high
                    }
                    for f in forecasts
                ]
            })

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@demand_bp.route('/seasonality/<part_id>', methods=['GET'])
def detect_seasonality(part_id: str):
    """Detect seasonal patterns in demand."""
    periods = request.args.get('periods', 24, type=int)

    with get_db_session() as session:
        service = DemandService(session)
        result = service.detect_seasonality(
            part_id=part_id,
            periods=periods
        )

        return jsonify(result)


@demand_bp.route('/plan/<part_id>', methods=['GET'])
def get_demand_plan(part_id: str):
    """
    Generate complete demand plan.

    Query params:
    - horizon_months: Planning horizon (default 6)
    - method: Forecast method (default 'exponential_smoothing')
    """
    horizon = request.args.get('horizon_months', 6, type=int)
    method = request.args.get('method', 'exponential_smoothing')

    with get_db_session() as session:
        service = DemandService(session)

        try:
            plan = service.generate_demand_plan(
                part_id=part_id,
                horizon_months=horizon,
                method=method
            )
            return jsonify(plan)

        except ValueError as e:
            return jsonify({'error': str(e)}), 400


@demand_bp.route('/accuracy/<part_id>', methods=['GET'])
def get_forecast_accuracy(part_id: str):
    """
    Calculate forecast accuracy metrics.

    Query params:
    - periods_back: Periods to evaluate (default 6)
    """
    periods_back = request.args.get('periods_back', 6, type=int)

    with get_db_session() as session:
        service = DemandService(session)
        accuracy = service.calculate_forecast_accuracy(
            part_id=part_id,
            periods_back=periods_back
        )

        return jsonify(accuracy)
