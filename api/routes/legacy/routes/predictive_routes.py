"""
Predictive Manufacturing Intelligence API Routes.

Provides REST endpoints for:
- Cycle time prediction
- Tool wear prediction
- Quality forecasting
- Maintenance prediction
- Model training
"""

from flask import Blueprint, request, jsonify
import logging
import asyncio

logger = logging.getLogger(__name__)

predictive_bp = Blueprint("predictive", __name__, url_prefix="/api/predictive")


def run_async(coro):
    """Run an async coroutine synchronously in Flask context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def get_service():
    """Get the predictive service instance."""
    from services.predictive import get_predictive_service
    return get_predictive_service()


# =============================================================================
# Cycle Time Prediction
# =============================================================================


@predictive_bp.route("/cycle-time", methods=["POST"])
def predict_cycle_time():
    """
    Predict cycle time for a G-code program.

    Request body:
    {
        "gcode": "G-code program text",
        "material": "aluminum",
        "machine_type": "mill",
        "rapid_rate": 5000,
        "include_explanation": true
    }

    Returns:
    {
        "prediction": {
            "predicted_seconds": 180.5,
            "confidence": 0.85,
            "breakdown": {...}
        },
        "features": {...},
        "explanation": {...}
    }
    """
    try:
        data = request.get_json()

        if not data or "gcode" not in data:
            return jsonify({"error": "Missing gcode in request body"}), 400

        service = get_service()

        result = run_async(service.predict_cycle_time(
            gcode=data["gcode"],
            material=data.get("material", "aluminum"),
            machine_type=data.get("machine_type", "mill"),
            rapid_rate=data.get("rapid_rate", 5000.0),
            include_explanation=data.get("include_explanation", True),
        ))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Cycle time prediction error: {e}")
        return jsonify({"error": str(e)}), 500


@predictive_bp.route("/cycle-time/features", methods=["POST"])
def extract_gcode_features():
    """
    Extract features from G-code without making a prediction.

    Request body:
    {
        "gcode": "G-code program text"
    }
    """
    try:
        data = request.get_json()

        if not data or "gcode" not in data:
            return jsonify({"error": "Missing gcode in request body"}), 400

        service = get_service()
        features = service.extract_gcode_features(data["gcode"])

        return jsonify({"features": features})

    except Exception as e:
        logger.error(f"Feature extraction error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Tool Wear Prediction
# =============================================================================


@predictive_bp.route("/tool-wear", methods=["POST"])
def predict_tool_wear():
    """
    Predict tool wear and remaining life.

    Request body:
    {
        "tool_id": "T01",
        "tool_type": "endmill",
        "diameter": 10.0,
        "material": "carbide",
        "runtime_minutes": 45.0,
        "cut_distance_mm": 5000.0,
        "parts_cut": 25,
        "rated_life_minutes": 120.0,
        "vibration": 0.5,
        "load": 45.0,
        "temperature": 35.0,
        "last_material": "aluminum",
        "upcoming_job_minutes": 30.0,
        "upcoming_material": "steel"
    }
    """
    try:
        data = request.get_json()

        if not data or "tool_id" not in data:
            return jsonify({"error": "Missing tool_id in request body"}), 400

        from services.predictive import ToolCondition

        condition = ToolCondition(
            tool_id=data["tool_id"],
            tool_type=data.get("tool_type", "endmill"),
            diameter=data.get("diameter", 10.0),
            material=data.get("material", "carbide"),
            flutes=data.get("flutes", 4),
            total_runtime_minutes=data.get("runtime_minutes", 0.0),
            total_cut_distance_mm=data.get("cut_distance_mm", 0.0),
            total_parts_cut=data.get("parts_cut", 0),
            rated_life_minutes=data.get("rated_life_minutes", 120.0),
            rated_cut_distance_mm=data.get("rated_cut_distance_mm", 50000.0),
            current_vibration=data.get("vibration", 0.0),
            current_load=data.get("load", 0.0),
            current_temperature=data.get("temperature", 0.0),
            last_material=data.get("last_material", "aluminum"),
        )

        service = get_service()

        result = run_async(service.predict_tool_wear(
            tool_condition=condition,
            upcoming_job_minutes=data.get("upcoming_job_minutes", 0.0),
            upcoming_material=data.get("upcoming_material"),
            include_explanation=data.get("include_explanation", True),
        ))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Tool wear prediction error: {e}")
        return jsonify({"error": str(e)}), 500


@predictive_bp.route("/tool-wear/batch", methods=["POST"])
def predict_tool_wear_batch():
    """
    Predict wear for multiple tools.

    Request body:
    {
        "tools": [
            {"tool_id": "T01", "runtime_minutes": 45, ...},
            {"tool_id": "T02", "runtime_minutes": 80, ...}
        ]
    }
    """
    try:
        data = request.get_json()

        if not data or "tools" not in data:
            return jsonify({"error": "Missing tools in request body"}), 400

        from services.predictive import ToolCondition

        conditions = []
        for tool_data in data["tools"]:
            conditions.append(ToolCondition(
                tool_id=tool_data["tool_id"],
                tool_type=tool_data.get("tool_type", "endmill"),
                diameter=tool_data.get("diameter", 10.0),
                material=tool_data.get("material", "carbide"),
                total_runtime_minutes=tool_data.get("runtime_minutes", 0.0),
                total_cut_distance_mm=tool_data.get("cut_distance_mm", 0.0),
                total_parts_cut=tool_data.get("parts_cut", 0),
                rated_life_minutes=tool_data.get("rated_life_minutes", 120.0),
                current_vibration=tool_data.get("vibration", 0.0),
                current_load=tool_data.get("load", 0.0),
                last_material=tool_data.get("last_material", "aluminum"),
            ))

        service = get_service()
        predictions = service.predict_tool_wear_batch(conditions)

        # Convert to serializable format
        result = {
            tool_id: pred.to_dict()
            for tool_id, pred in predictions.items()
        }

        # Generate replacement schedule
        schedule = service.get_tool_replacement_schedule(predictions)

        return jsonify({
            "predictions": result,
            "replacement_schedule": schedule,
        })

    except Exception as e:
        logger.error(f"Batch tool wear prediction error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Quality Prediction
# =============================================================================


@predictive_bp.route("/quality", methods=["POST"])
def predict_quality():
    """
    Predict part quality.

    Request body:
    {
        "spindle_speed": 8000,
        "feed_rate": 500,
        "depth_of_cut": 2.0,
        "width_of_cut": 5.0,
        "tool_diameter": 10.0,
        "tool_length": 50.0,
        "tool_wear_percentage": 30.0,
        "material": "aluminum",
        "vibration": 0.3,
        "spindle_load": 45.0,
        "temperature": 35.0,
        "coolant_flow": 10.0,
        "target_tolerance": 0.05,
        "target_surface_finish": 1.6
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "Missing request body"}), 400

        from services.predictive.quality_forecaster import ProcessParameters

        params = ProcessParameters(
            spindle_speed=data.get("spindle_speed", 0.0),
            feed_rate=data.get("feed_rate", 0.0),
            depth_of_cut=data.get("depth_of_cut", 0.0),
            width_of_cut=data.get("width_of_cut", 0.0),
            tool_diameter=data.get("tool_diameter", 0.0),
            tool_length=data.get("tool_length", 0.0),
            tool_wear_percentage=data.get("tool_wear_percentage", 0.0),
            material=data.get("material", "aluminum"),
            spindle_load=data.get("spindle_load", 0.0),
            vibration=data.get("vibration", 0.0),
            temperature=data.get("temperature", 0.0),
            coolant_flow=data.get("coolant_flow", 0.0),
            historical_scrap_rate=data.get("historical_scrap_rate", 0.0),
        )

        service = get_service()

        result = run_async(service.predict_quality(
            process_params=params,
            target_tolerance=data.get("target_tolerance", 0.05),
            target_surface_finish=data.get("target_surface_finish", 1.6),
            include_explanation=data.get("include_explanation", True),
        ))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Quality prediction error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Maintenance Prediction
# =============================================================================


@predictive_bp.route("/maintenance", methods=["POST"])
def predict_maintenance():
    """
    Predict maintenance needs.

    Request body:
    {
        "machine_id": "CNC-001",
        "machine_type": "mill",
        "runtime_hours": 5000,
        "runtime_since_maintenance": 450,
        "spindle_vibration": 0.8,
        "x_vibration": 0.3,
        "y_vibration": 0.3,
        "z_vibration": 0.4,
        "spindle_temperature": 45.0,
        "coolant_level": 80,
        "alarm_count_30d": 5,
        "servo_error_count_30d": 2,
        "x_backlash": 0.015,
        "y_backlash": 0.012,
        "z_backlash": 0.008,
        "planning_horizon_days": 30
    }
    """
    try:
        data = request.get_json()

        if not data or "machine_id" not in data:
            return jsonify({"error": "Missing machine_id in request body"}), 400

        from services.predictive.maintenance_predictor import MachineState
        from datetime import datetime

        # Parse last maintenance date
        last_maint = None
        if data.get("last_maintenance"):
            last_maint = datetime.fromisoformat(data["last_maintenance"])

        state = MachineState(
            machine_id=data["machine_id"],
            machine_type=data.get("machine_type", "mill"),
            total_runtime_hours=data.get("runtime_hours", 0.0),
            runtime_since_last_maintenance=data.get("runtime_since_maintenance", 0.0),
            power_cycles=data.get("power_cycles", 0),
            spindle_vibration=data.get("spindle_vibration", 0.0),
            x_axis_vibration=data.get("x_vibration", 0.0),
            y_axis_vibration=data.get("y_vibration", 0.0),
            z_axis_vibration=data.get("z_vibration", 0.0),
            spindle_temperature=data.get("spindle_temperature", 0.0),
            coolant_temperature=data.get("coolant_temperature", 0.0),
            coolant_level=data.get("coolant_level", 100.0),
            air_pressure=data.get("air_pressure", 0.0),
            x_backlash=data.get("x_backlash", 0.0),
            y_backlash=data.get("y_backlash", 0.0),
            z_backlash=data.get("z_backlash", 0.0),
            alarm_count_30d=data.get("alarm_count_30d", 0),
            servo_error_count_30d=data.get("servo_error_count_30d", 0),
            spindle_overload_count_30d=data.get("spindle_overload_count_30d", 0),
            last_maintenance=last_maint,
        )

        service = get_service()

        result = run_async(service.predict_maintenance(
            machine_state=state,
            planning_horizon_days=data.get("planning_horizon_days", 30),
            include_explanation=data.get("include_explanation", True),
        ))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Maintenance prediction error: {e}")
        return jsonify({"error": str(e)}), 500


@predictive_bp.route("/maintenance/schedule/<machine_id>", methods=["GET"])
def get_maintenance_schedule(machine_id: str):
    """
    Get maintenance schedule for a machine.

    Returns the full maintenance schedule with all tasks.
    """
    try:
        # In a real implementation, you would fetch the machine state from a database
        from services.predictive.maintenance_predictor import MachineState

        # For now, create a default state
        state = MachineState(
            machine_id=machine_id,
            machine_type="mill",
            runtime_since_last_maintenance=250.0,
        )

        service = get_service()
        result = run_async(service.predict_maintenance(
            machine_state=state,
            planning_horizon_days=90,
            include_explanation=False,
        ))

        if "prediction" in result and "schedule" in result["prediction"]:
            return jsonify(result["prediction"]["schedule"])

        return jsonify({"tasks": [], "message": "No maintenance scheduled"})

    except Exception as e:
        logger.error(f"Get maintenance schedule error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Model Training
# =============================================================================


@predictive_bp.route("/train/cycle-time", methods=["POST"])
def train_cycle_time_model():
    """
    Train a cycle time prediction model.

    Request body:
    {
        "training_data": [
            {"line_count": 100, "move_count": 50, ..., "actual_cycle_time": 180},
            ...
        ],
        "feature_columns": ["line_count", "move_count", ...]
    }
    """
    try:
        data = request.get_json()

        if not data or "training_data" not in data:
            return jsonify({"error": "Missing training_data in request body"}), 400

        service = get_service()
        result = service.train_cycle_time_model(
            training_data=data["training_data"],
            feature_columns=data.get("feature_columns"),
        )

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"Train cycle time model error: {e}")
        return jsonify({"error": str(e)}), 500


@predictive_bp.route("/train/quality", methods=["POST"])
def train_quality_model():
    """
    Train a quality prediction model.

    Request body:
    {
        "training_data": [
            {"spindle_speed": 8000, "feed_rate": 500, ..., "quality_score": 85},
            ...
        ],
        "is_classification": false
    }
    """
    try:
        data = request.get_json()

        if not data or "training_data" not in data:
            return jsonify({"error": "Missing training_data in request body"}), 400

        service = get_service()
        result = service.train_quality_model(
            training_data=data["training_data"],
            feature_columns=data.get("feature_columns"),
        )

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"Train quality model error: {e}")
        return jsonify({"error": str(e)}), 500


@predictive_bp.route("/models", methods=["GET"])
def list_models():
    """List available trained models."""
    try:
        service = get_service()
        models = service.get_available_models()
        return jsonify({"models": models})

    except Exception as e:
        logger.error(f"List models error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Service Status
# =============================================================================


@predictive_bp.route("/status", methods=["GET"])
def get_status():
    """Get predictive service status."""
    try:
        service = get_service()
        return jsonify(service.get_service_status())

    except Exception as e:
        logger.error(f"Get status error: {e}")
        return jsonify({"error": str(e)}), 500


@predictive_bp.route("/history", methods=["GET"])
def get_prediction_history():
    """
    Get prediction history.

    Query parameters:
    - type: Filter by prediction type (cycle_time, tool_wear, quality, maintenance)
    - limit: Maximum number of records (default: 100)
    """
    try:
        prediction_type = request.args.get("type")
        limit = int(request.args.get("limit", 100))

        service = get_service()
        history = service.get_prediction_history(
            prediction_type=prediction_type,
            limit=limit,
        )

        return jsonify({"history": history})

    except Exception as e:
        logger.error(f"Get prediction history error: {e}")
        return jsonify({"error": str(e)}), 500


@predictive_bp.route("/features/info", methods=["GET"])
def get_feature_info():
    """Get information about available features."""
    try:
        service = get_service()
        info = service.feature_store.get_feature_info()
        return jsonify({"features": info})

    except Exception as e:
        logger.error(f"Get feature info error: {e}")
        return jsonify({"error": str(e)}), 500
