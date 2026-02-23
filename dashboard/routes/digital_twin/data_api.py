"""
Digital Twin Data API - Live/Simulation Hybrid Endpoints

LegoMCP World-Class Manufacturing Platform v2.0

Provides REST API endpoints for the Digital Twin dashboard with:
- Automatic fallback from live DB to realistic simulation
- LIVE/SIMULATION mode indicator for UI
- Consistent data format regardless of source

These endpoints replace the Math.random() calls in digital_twin.html

Author: LegoMCP Team
Version: 2.0.0
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

from services.data_provider import (
    DataProvider,
    DataProviderMode,
    get_data_provider
)

logger = logging.getLogger(__name__)

data_api_bp = Blueprint('data_api', __name__, url_prefix='/data')


def _get_provider() -> DataProvider:
    """Get data provider with session if available."""
    try:
        from models import get_db_session
        with get_db_session() as session:
            return DataProvider(session=session, mode=DataProviderMode.HYBRID)
    except Exception:
        # No DB available, use simulation
        return DataProvider(session=None, mode=DataProviderMode.SIMULATION)


# =============================================================================
# Asset Endpoints
# =============================================================================

@data_api_bp.route('/assets', methods=['GET'])
def get_assets():
    """
    Get all digital twin assets (work centers).

    Returns list of assets with their current status.
    Automatically falls back to demo assets if DB unavailable.

    Response:
    {
        "assets": [...],
        "total": 5,
        "data_mode": "live" | "simulation",
        "timestamp": "2024-01-08T..."
    }
    """
    try:
        provider = _get_provider()
        assets = provider.get_work_center_assets()

        return jsonify({
            "success": True,
            "assets": assets,
            "total": len(assets),
            "data_mode": provider.get_data_mode(),
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error fetching assets: {e}")
        # Return fallback
        provider = DataProvider(session=None, mode=DataProviderMode.SIMULATION)
        return jsonify({
            "success": True,
            "assets": provider.get_work_center_assets(),
            "total": 5,
            "data_mode": "simulation",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


# =============================================================================
# State Endpoints
# =============================================================================

@data_api_bp.route('/state/<asset_id>', methods=['GET'])
def get_asset_state(asset_id: str):
    """
    Get current state of a specific asset.

    Returns temperature, position, progress, and status.
    Used by the dashboard for real-time updates.

    Response:
    {
        "work_center_id": "wc-001",
        "status": "running",
        "progress": 67.5,
        "position": {"x": 100, "y": 50, "z": 10},
        "temperatures": {...},
        "temperature": 215.0,  // Flattened for compatibility
        "data_mode": "live" | "simulation"
    }
    """
    try:
        provider = _get_provider()
        state = provider.get_asset_state(asset_id)

        return jsonify({
            "success": True,
            **state
        })

    except Exception as e:
        logger.error(f"Error fetching state for {asset_id}: {e}")
        provider = DataProvider(session=None, mode=DataProviderMode.SIMULATION)
        state = provider.get_asset_state(asset_id)
        state["error"] = str(e)
        return jsonify({
            "success": True,
            **state
        })


# =============================================================================
# KPI / OEE Endpoints
# =============================================================================

@data_api_bp.route('/kpis/<asset_id>', methods=['GET'])
def get_asset_kpis(asset_id: str):
    """
    Get KPIs for an asset with live or simulated data.

    Query params:
    - period: Hours to analyze (default 24)

    Response:
    {
        "asset_id": "wc-001",
        "oee": 82.5,
        "availability": 95.0,
        "performance": 88.0,
        "quality": 98.5,
        "data_mode": "live" | "simulation"
    }
    """
    period = request.args.get('period', 24, type=int)

    try:
        provider = _get_provider()
        oee = provider.get_oee_metrics(asset_id, period)

        return jsonify({
            "success": True,
            "asset_id": asset_id,
            "period_hours": period,
            **oee
        })

    except Exception as e:
        logger.error(f"Error fetching KPIs for {asset_id}: {e}")
        provider = DataProvider(session=None, mode=DataProviderMode.SIMULATION)
        oee = provider.get_oee_metrics(asset_id, period)
        return jsonify({
            "success": True,
            "asset_id": asset_id,
            "period_hours": period,
            "error": str(e),
            **oee
        })


@data_api_bp.route('/oee-trend/<asset_id>', methods=['GET'])
def get_oee_trend(asset_id: str):
    """
    Get OEE trend data for charting.

    Query params:
    - hours: Hours of history (default 24)

    Response:
    {
        "asset_id": "wc-001",
        "trend": [
            {"timestamp": "...", "oee": 82.5, "availability": 95.0, ...},
            ...
        ],
        "data_mode": "live" | "simulation"
    }
    """
    hours = request.args.get('hours', 24, type=int)

    try:
        provider = _get_provider()
        trend = provider.get_oee_trend(asset_id, hours)

        return jsonify({
            "success": True,
            "asset_id": asset_id,
            "hours": hours,
            "trend": trend,
            "data_mode": provider.get_data_mode(),
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error fetching OEE trend for {asset_id}: {e}")
        provider = DataProvider(session=None, mode=DataProviderMode.SIMULATION)
        trend = provider.get_oee_trend(asset_id, hours)
        return jsonify({
            "success": True,
            "asset_id": asset_id,
            "hours": hours,
            "trend": trend,
            "data_mode": "simulation",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


# =============================================================================
# Temperature History
# =============================================================================

@data_api_bp.route('/temperature-history/<asset_id>', methods=['GET'])
def get_temperature_history(asset_id: str):
    """
    Get temperature history for charting.

    Query params:
    - hours: Hours of history (default 24)

    Response:
    {
        "asset_id": "wc-001",
        "history": [
            {"timestamp": "...", "hotend": 215.0, "bed": 60.0, ...},
            ...
        ],
        "data_mode": "live" | "simulation"
    }
    """
    hours = request.args.get('hours', 24, type=int)

    try:
        provider = _get_provider()
        history = provider.get_temperature_history(asset_id, hours)

        return jsonify({
            "success": True,
            "asset_id": asset_id,
            "hours": hours,
            "history": history,
            "data_mode": provider.get_data_mode(),
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error fetching temperature history for {asset_id}: {e}")
        provider = DataProvider(session=None, mode=DataProviderMode.SIMULATION)
        history = provider.get_temperature_history(asset_id, hours)
        return jsonify({
            "success": True,
            "asset_id": asset_id,
            "hours": hours,
            "history": history,
            "data_mode": "simulation",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


# =============================================================================
# Production Context (for AI Copilot)
# =============================================================================

@data_api_bp.route('/context', methods=['GET'])
def get_production_context():
    """
    Get production context for AI copilot.

    This replaces the hardcoded values in copilot.py

    Query params:
    - work_center_id: Specific work center (optional)

    Response:
    {
        "oee": {"current": 0.82, "availability": 0.95, ...},
        "quality": {"fpy": 0.985, "defect_rate": 0.015},
        "scheduling": {"on_time_delivery": 0.98, ...},
        "maintenance": {"machine_health": 0.92},
        "data_mode": "live" | "simulation"
    }
    """
    work_center_id = request.args.get('work_center_id')

    try:
        provider = _get_provider()
        context = provider.get_production_context(work_center_id)

        return jsonify({
            "success": True,
            **context
        })

    except Exception as e:
        logger.error(f"Error fetching production context: {e}")
        provider = DataProvider(session=None, mode=DataProviderMode.SIMULATION)
        context = provider.get_production_context(work_center_id)
        context["error"] = str(e)
        return jsonify({
            "success": True,
            **context
        })


# =============================================================================
# Batch Updates (for efficient polling)
# =============================================================================

@data_api_bp.route('/batch', methods=['POST'])
def get_batch_data():
    """
    Get multiple data items in a single request.

    Reduces HTTP overhead for dashboard polling.

    Body:
    {
        "requests": [
            {"type": "state", "asset_id": "wc-001"},
            {"type": "kpis", "asset_id": "wc-001"},
            {"type": "assets"}
        ]
    }

    Response:
    {
        "results": [
            {"type": "state", "data": {...}},
            {"type": "kpis", "data": {...}},
            {"type": "assets", "data": [...]}
        ],
        "data_mode": "live" | "simulation"
    }
    """
    data = request.get_json() or {}
    requests = data.get('requests', [])

    if not requests:
        return jsonify({"error": "No requests provided"}), 400

    provider = _get_provider()
    results = []

    for req in requests:
        req_type = req.get('type')
        asset_id = req.get('asset_id')

        try:
            if req_type == 'state' and asset_id:
                result_data = provider.get_asset_state(asset_id)
            elif req_type == 'kpis' and asset_id:
                result_data = provider.get_oee_metrics(asset_id, req.get('period', 24))
            elif req_type == 'assets':
                result_data = provider.get_work_center_assets()
            elif req_type == 'context':
                result_data = provider.get_production_context(asset_id)
            else:
                result_data = {"error": f"Unknown request type: {req_type}"}

            results.append({
                "type": req_type,
                "asset_id": asset_id,
                "data": result_data
            })

        except Exception as e:
            results.append({
                "type": req_type,
                "asset_id": asset_id,
                "data": {"error": str(e)}
            })

    return jsonify({
        "success": True,
        "results": results,
        "data_mode": provider.get_data_mode(),
        "timestamp": datetime.utcnow().isoformat()
    })


# =============================================================================
# Health Check
# =============================================================================

@data_api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Check data provider health and mode.

    Response:
    {
        "status": "healthy",
        "data_mode": "live" | "simulation",
        "db_available": true | false
    }
    """
    try:
        provider = _get_provider()
        is_live = provider.is_live()

        return jsonify({
            "status": "healthy",
            "data_mode": provider.get_data_mode(),
            "db_available": is_live,
            "timestamp": datetime.utcnow().isoformat()
        })

    except Exception as e:
        return jsonify({
            "status": "degraded",
            "data_mode": "simulation",
            "db_available": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })
