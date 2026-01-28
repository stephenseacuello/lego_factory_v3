"""
Vision API Routes for CNC SCADA.

Provides REST endpoints for:
- Sketch-to-CAD conversion
- Photo measurement
- Part inspection
- Drawing OCR
- Camera management
"""

from flask import Blueprint, request, jsonify
import logging
import base64
import asyncio

logger = logging.getLogger(__name__)

vision_bp = Blueprint("vision", __name__, url_prefix="/api/vision")


def run_async(coro):
    """Run an async coroutine synchronously in Flask context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If there's already a running loop, create a new one
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop exists, create one
        return asyncio.run(coro)


def get_service():
    """Get the vision service instance."""
    from services.vision import get_vision_service
    return get_vision_service()


# =============================================================================
# Sketch-to-CAD
# =============================================================================


@vision_bp.route("/sketch/analyze", methods=["POST"])
def analyze_sketch():
    """
    Analyze a hand-drawn sketch for CAD conversion.

    Request body:
    {
        "image": "base64 encoded image",
        "image_type": "image/png",
        "context": "Optional context about the sketch"
    }

    Returns:
    {
        "success": true,
        "geometries": [...],
        "dimensions": [...],
        "confidence": 0.85
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        # Decode base64 image
        image_data = base64.b64decode(data["image"])
        image_type = data.get("image_type", "image/png")
        context = data.get("context", "")

        service = get_service()
        result = run_async(service.analyze_sketch(image_data, image_type, context))

        return jsonify({
            "success": result.success,
            "geometries": [g.to_dict() for g in result.geometries] if result.geometries else [],
            "dimensions": [d.to_dict() for d in result.dimensions] if result.dimensions else [],
            "notes": result.notes,
            "confidence": result.confidence,
            "raw_interpretation": result.raw_interpretation,
        })

    except Exception as e:
        logger.error(f"Sketch analysis error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/sketch/to-gcode", methods=["POST"])
def sketch_to_gcode():
    """
    Convert a sketch directly to G-code suggestions.

    Request body:
    {
        "image": "base64 encoded image",
        "material": "aluminum",
        "tool_diameter": 0.25
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])
        material = data.get("material", "aluminum")
        tool_diameter = data.get("tool_diameter", 0.25)

        service = get_service()
        result = run_async(service.sketch_to_gcode(image_data, material, tool_diameter))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Sketch to G-code error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Photo Measurement
# =============================================================================


@vision_bp.route("/measure", methods=["POST"])
def measure_from_photo():
    """
    Extract measurements from a photo.

    Request body:
    {
        "image": "base64 encoded image",
        "image_type": "image/jpeg",
        "reference_type": "ruler",
        "output_unit": "inches"
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])
        image_type = data.get("image_type", "image/jpeg")
        reference_type = data.get("reference_type")

        # Parse output unit
        output_unit = None
        if data.get("output_unit"):
            from services.vision.photo_measurement import MeasurementUnit
            unit_map = {
                "mm": MeasurementUnit.MM,
                "inches": MeasurementUnit.INCHES,
                "cm": MeasurementUnit.CM,
            }
            output_unit = unit_map.get(data["output_unit"].lower())

        service = get_service()
        result = run_async(service.measure_from_photo(
            image_data, image_type, reference_type, output_unit
        ))

        return jsonify({
            "success": result.success,
            "dimensions": [d.to_dict() for d in result.dimensions] if result.dimensions else [],
            "reference": result.reference.to_dict() if result.reference else None,
            "scale_factor": result.scale_factor,
            "notes": result.notes,
            "confidence": result.confidence,
        })

    except Exception as e:
        logger.error(f"Photo measurement error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/measure/with-scale", methods=["POST"])
def measure_with_scale():
    """
    Measure with a known reference scale.

    Request body:
    {
        "image": "base64 encoded image",
        "known_length": 25.4,
        "unit": "mm",
        "description": "1 inch ruler mark"
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        if "known_length" not in data:
            return jsonify({"error": "Missing known_length in request body"}), 400

        image_data = base64.b64decode(data["image"])
        known_length = float(data["known_length"])

        from services.vision.photo_measurement import MeasurementUnit
        unit_map = {
            "mm": MeasurementUnit.MM,
            "inches": MeasurementUnit.INCHES,
            "cm": MeasurementUnit.CM,
        }
        unit = unit_map.get(data.get("unit", "mm").lower(), MeasurementUnit.MM)
        description = data.get("description", "")

        service = get_service()
        result = run_async(service.measure_with_scale(
            image_data, known_length, unit, description
        ))

        return jsonify({
            "success": result.success,
            "dimensions": [d.to_dict() for d in result.dimensions] if result.dimensions else [],
            "scale_factor": result.scale_factor,
            "notes": result.notes,
            "confidence": result.confidence,
        })

    except Exception as e:
        logger.error(f"Measure with scale error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Part Inspection
# =============================================================================


@vision_bp.route("/inspect", methods=["POST"])
def inspect_part():
    """
    Inspect a part for quality defects.

    Request body:
    {
        "image": "base64 encoded image",
        "image_type": "image/jpeg",
        "part_number": "P12345",
        "expected_features": ["hole", "slot", "chamfer"],
        "material": "aluminum"
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])
        image_type = data.get("image_type", "image/jpeg")
        part_number = data.get("part_number")
        expected_features = data.get("expected_features")
        material = data.get("material")

        service = get_service()
        result = run_async(service.inspect_part(
            image_data, image_type, part_number, expected_features, material
        ))

        return jsonify({
            "success": result.success,
            "passed": result.passed,
            "quality_score": result.quality_score.to_dict() if result.quality_score else None,
            "defects": [d.to_dict() for d in result.defects] if result.defects else [],
            "features_verified": result.features_verified,
            "features_missing": result.features_missing,
            "notes": result.notes,
            "confidence": result.confidence,
        })

    except Exception as e:
        logger.error(f"Part inspection error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/inspect/compare", methods=["POST"])
def compare_parts():
    """
    Compare a part to a reference sample.

    Request body:
    {
        "part_image": "base64 encoded image of part to inspect",
        "reference_image": "base64 encoded image of reference part"
    }
    """
    try:
        data = request.get_json()

        if not data or "part_image" not in data or "reference_image" not in data:
            return jsonify({"error": "Missing part_image or reference_image"}), 400

        part_image = base64.b64decode(data["part_image"])
        reference_image = base64.b64decode(data["reference_image"])

        service = get_service()
        result = run_async(service.compare_parts(part_image, reference_image))

        return jsonify({
            "success": result.success,
            "passed": result.passed,
            "quality_score": result.quality_score.to_dict() if result.quality_score else None,
            "defects": [d.to_dict() for d in result.defects] if result.defects else [],
            "notes": result.notes,
            "confidence": result.confidence,
        })

    except Exception as e:
        logger.error(f"Part comparison error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Drawing OCR
# =============================================================================


@vision_bp.route("/ocr", methods=["POST"])
def read_drawing():
    """
    Extract text from an engineering drawing.

    Request body:
    {
        "image": "base64 encoded image",
        "image_type": "image/png"
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])
        image_type = data.get("image_type", "image/png")

        service = get_service()
        result = run_async(service.read_drawing(image_data, image_type))

        return jsonify({
            "success": result.success,
            "title_block": result.title_block,
            "dimensions": [d.to_dict() for d in result.dimensions] if result.dimensions else [],
            "tolerances": result.tolerances,
            "notes": result.notes,
            "materials": result.materials,
            "gdt_symbols": result.gdt_symbols,
            "confidence": result.confidence,
        })

    except Exception as e:
        logger.error(f"Drawing OCR error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ocr/part-info", methods=["POST"])
def extract_part_info():
    """
    Extract key part information from a drawing.

    Request body:
    {
        "image": "base64 encoded image"
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])

        service = get_service()
        result = run_async(service.extract_part_info(image_data))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Extract part info error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Camera Management
# =============================================================================


@vision_bp.route("/camera/list", methods=["GET"])
def list_cameras():
    """Get list of available cameras."""
    try:
        service = get_service()
        cameras = service.get_camera_list()
        return jsonify({"cameras": cameras})

    except Exception as e:
        logger.error(f"List cameras error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/camera/connect", methods=["POST"])
def connect_camera():
    """
    Connect to a camera device.

    Request body:
    {
        "device_id": 0
    }
    """
    try:
        data = request.get_json() or {}
        device_id = data.get("device_id")

        service = get_service()
        success = service.connect_camera(device_id)

        return jsonify({"success": success})

    except Exception as e:
        logger.error(f"Connect camera error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/camera/disconnect", methods=["POST"])
def disconnect_camera():
    """Disconnect from the camera."""
    try:
        service = get_service()
        service.disconnect_camera()
        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Disconnect camera error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/camera/capture", methods=["POST"])
def capture_image():
    """Capture an image from the connected camera."""
    try:
        service = get_service()
        image = service.capture_image()

        if image:
            return jsonify({
                "success": True,
                "image": base64.b64encode(image.data).decode(),
                "format": image.format,
                "width": image.width,
                "height": image.height,
                "timestamp": image.timestamp.isoformat(),
            })
        else:
            return jsonify({"success": False, "error": "Failed to capture image"}), 500

    except Exception as e:
        logger.error(f"Capture image error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/camera/capture-and-analyze", methods=["POST"])
def capture_and_analyze():
    """
    Capture an image and analyze it.

    Request body:
    {
        "analysis_type": "inspection",
        "part_number": "P12345",
        "expected_features": ["hole", "slot"]
    }
    """
    try:
        data = request.get_json() or {}
        analysis_type = data.get("analysis_type", "inspection")

        # Remove analysis_type from kwargs
        kwargs = {k: v for k, v in data.items() if k != "analysis_type"}

        service = get_service()
        result = run_async(service.capture_and_analyze(analysis_type, **kwargs))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Capture and analyze error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Service Status
# =============================================================================


@vision_bp.route("/status", methods=["GET"])
def get_status():
    """Get vision service status."""
    try:
        service = get_service()
        return jsonify({
            "available": service.is_available(),
            "camera_connected": service.camera.state.value != "disconnected",
        })

    except Exception as e:
        logger.error(f"Get status error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/history", methods=["GET"])
def get_analysis_history():
    """
    Get analysis history.

    Query parameters:
    - type: Filter by analysis type
    - limit: Maximum number of records (default: 50)
    """
    try:
        analysis_type = request.args.get("type")
        limit = int(request.args.get("limit", 50))

        service = get_service()
        history = service.get_analysis_history(limit, analysis_type)

        return jsonify({"history": history})

    except Exception as e:
        logger.error(f"Get analysis history error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# YOLO Inference - Roboflow Integration
# =============================================================================


def get_yolo_service():
    """Get the YOLO inference service instance."""
    from services.yolo_inference_service import get_yolo_service as _get_yolo
    return _get_yolo()


def get_ros2_bridge():
    """Get the ROS2 bridge service instance."""
    from services.ros2_bridge_service import get_ros2_bridge as _get_bridge
    return _get_bridge()


@vision_bp.route("/yolo/health", methods=["GET"])
def yolo_health():
    """Check YOLO inference server health."""
    try:
        service = get_yolo_service()
        result = run_async(service.check_health())
        return jsonify(result)
    except Exception as e:
        logger.error(f"YOLO health check error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/yolo/status", methods=["GET"])
def yolo_status():
    """Get YOLO inference service status."""
    try:
        service = get_yolo_service()
        return jsonify(service.get_status())
    except Exception as e:
        logger.error(f"YOLO status error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/yolo/detect", methods=["POST"])
def yolo_detect():
    """
    Run YOLO detection on an image.

    Request body:
    {
        "image": "base64 encoded image",
        "detection_type": "defect|tool_wear|part|safety",
        "machine_id": "default",
        "confidence_threshold": 0.7
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])
        detection_type = data.get("detection_type", "defect")
        machine_id = data.get("machine_id", "default")
        confidence = data.get("confidence_threshold")

        service = get_yolo_service()

        if detection_type == "defect":
            result = run_async(service.detect_defects(
                image_data,
                part_number=data.get("part_number", ""),
                machine_id=machine_id,
                confidence_threshold=confidence,
            ))
        elif detection_type == "tool_wear":
            result = run_async(service.detect_tool_wear(
                image_data,
                tool_number=data.get("tool_number", 1),
                tool_type=data.get("tool_type", "endmill"),
                machine_id=machine_id,
            ))
        elif detection_type == "part":
            result = run_async(service.verify_part_position(
                image_data,
                expected_class=data.get("expected_class", "part"),
                tolerance_mm=data.get("tolerance_mm", 1.0),
                machine_id=machine_id,
            ))
        elif detection_type == "safety":
            result = run_async(service.check_safety_zone(
                image_data,
                zone_name=data.get("zone_name", "work_envelope"),
                machine_id=machine_id,
            ))
        else:
            return jsonify({"error": f"Unknown detection_type: {detection_type}"}), 400

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"YOLO detection error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/yolo/inspect-part", methods=["POST"])
def yolo_inspect_part():
    """
    Inspect a part for manufacturing defects using YOLO.

    Request body:
    {
        "image": "base64 encoded image",
        "part_number": "P12345",
        "machine_id": "default",
        "confidence_threshold": 0.7
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])

        service = get_yolo_service()
        result = run_async(service.detect_defects(
            image_data,
            part_number=data.get("part_number", ""),
            machine_id=data.get("machine_id", "default"),
            confidence_threshold=data.get("confidence_threshold"),
        ))

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"YOLO part inspection error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/yolo/tool-wear", methods=["POST"])
def yolo_tool_wear():
    """
    Analyze tool for wear using YOLO.

    Request body:
    {
        "image": "base64 encoded image",
        "tool_number": 1,
        "tool_type": "endmill",
        "machine_id": "default"
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])

        service = get_yolo_service()
        result = run_async(service.detect_tool_wear(
            image_data,
            tool_number=data.get("tool_number", 1),
            tool_type=data.get("tool_type", "endmill"),
            machine_id=data.get("machine_id", "default"),
        ))

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"YOLO tool wear error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/yolo/verify-position", methods=["POST"])
def yolo_verify_position():
    """
    Verify part position in fixture using YOLO.

    Request body:
    {
        "image": "base64 encoded image",
        "expected_class": "part",
        "tolerance_mm": 1.0,
        "machine_id": "default"
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])

        service = get_yolo_service()
        result = run_async(service.verify_part_position(
            image_data,
            expected_class=data.get("expected_class", "part"),
            tolerance_mm=data.get("tolerance_mm", 1.0),
            machine_id=data.get("machine_id", "default"),
        ))

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"YOLO position verification error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/yolo/safety-check", methods=["POST"])
def yolo_safety_check():
    """
    Check safety zone for hazards (hands, people) using YOLO.

    CRITICAL: This is a safety-critical endpoint.
    On error, assumes unsafe (fail-safe behavior).

    Request body:
    {
        "image": "base64 encoded image",
        "zone_name": "work_envelope",
        "machine_id": "default"
    }
    """
    try:
        data = request.get_json()

        if not data or "image" not in data:
            return jsonify({"error": "Missing image in request body"}), 400

        image_data = base64.b64decode(data["image"])

        service = get_yolo_service()
        result = run_async(service.check_safety_zone(
            image_data,
            zone_name=data.get("zone_name", "work_envelope"),
            machine_id=data.get("machine_id", "default"),
        ))

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"YOLO safety check error: {e}")
        # Fail-safe: assume unsafe on error
        return jsonify({
            "success": False,
            "zone_clear": False,
            "alert_level": 2,
            "hazards": [],
            "requires_estop": True,
            "zone_name": data.get("zone_name", "work_envelope") if data else "unknown",
            "message": f"Safety check FAILED: {e} - Assuming unsafe",
        }), 500


@vision_bp.route("/yolo/history", methods=["GET"])
def yolo_detection_history():
    """
    Get YOLO detection history.

    Query parameters:
    - type: Detection type filter (defect, tool_wear, part, safety)
    - machine_id: Machine ID filter
    - limit: Maximum number of records (default: 100)
    """
    try:
        from services.yolo_inference_service import DetectionType

        detection_type = request.args.get("type")
        machine_id = request.args.get("machine_id")
        limit = int(request.args.get("limit", 100))

        # Convert type string to enum
        type_enum = None
        if detection_type:
            type_map = {
                "defect": DetectionType.DEFECT,
                "tool_wear": DetectionType.TOOL_WEAR,
                "part": DetectionType.PART,
                "safety": DetectionType.SAFETY,
            }
            type_enum = type_map.get(detection_type.lower())

        service = get_yolo_service()
        history = service.get_detection_history(
            detection_type=type_enum,
            limit=limit,
            machine_id=machine_id,
        )

        return jsonify({"history": history, "count": len(history)})

    except Exception as e:
        logger.error(f"YOLO history error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# ROS2 Bridge - Machine Fleet Integration
# =============================================================================


@vision_bp.route("/ros2/status", methods=["GET"])
def ros2_bridge_status():
    """Get ROS2 bridge service status."""
    try:
        bridge = get_ros2_bridge()
        return jsonify(bridge.get_status())
    except Exception as e:
        logger.error(f"ROS2 bridge status error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ros2/machines", methods=["GET"])
def ros2_list_machines():
    """Get list of discovered ROS2 machines."""
    try:
        bridge = get_ros2_bridge()
        machines = bridge.get_known_machines()
        return jsonify({"machines": machines, "count": len(machines)})
    except Exception as e:
        logger.error(f"ROS2 list machines error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ros2/machines/<machine_id>/status", methods=["GET"])
def ros2_machine_status(machine_id: str):
    """Get status of a specific machine via ROS2."""
    try:
        bridge = get_ros2_bridge()
        status = run_async(bridge.get_machine_state(machine_id))

        if status:
            return jsonify(status.to_dict())
        else:
            return jsonify({"error": f"Machine {machine_id} not found"}), 404

    except Exception as e:
        logger.error(f"ROS2 machine status error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ros2/fleet", methods=["GET"])
def ros2_fleet_status():
    """Get status of all machines in the fleet."""
    try:
        bridge = get_ros2_bridge()
        fleet = run_async(bridge.get_fleet_status())

        return jsonify({
            "machines": {k: v.to_dict() for k, v in fleet.items()},
            "count": len(fleet),
        })

    except Exception as e:
        logger.error(f"ROS2 fleet status error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ros2/service", methods=["POST"])
def ros2_call_service():
    """
    Call a ROS2 service via the bridge.

    Request body:
    {
        "service_name": "cnc/default/home",
        "request": {"axes": ["x", "y", "z"]},
        "timeout": 30.0
    }
    """
    try:
        data = request.get_json()

        if not data or "service_name" not in data:
            return jsonify({"error": "Missing service_name"}), 400

        bridge = get_ros2_bridge()
        result = run_async(bridge.call_service(
            service_name=data["service_name"],
            request=data.get("request", {}),
            timeout=data.get("timeout"),
        ))

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"ROS2 service call error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ros2/action", methods=["POST"])
def ros2_trigger_action():
    """
    Trigger a ROS2 action via the bridge.

    Request body:
    {
        "action_name": "cnc/default/execute_gcode",
        "goal": {"file_path": "/gcode/part1.nc"},
        "timeout": 300.0
    }
    """
    try:
        data = request.get_json()

        if not data or "action_name" not in data:
            return jsonify({"error": "Missing action_name"}), 400

        bridge = get_ros2_bridge()
        result = run_async(bridge.trigger_action(
            action_name=data["action_name"],
            goal=data.get("goal", {}),
            timeout=data.get("timeout"),
        ))

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"ROS2 action trigger error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ros2/machines/<machine_id>/home", methods=["POST"])
def ros2_home_machine(machine_id: str):
    """Home a specific machine."""
    try:
        bridge = get_ros2_bridge()
        result = run_async(bridge.home_machine(machine_id))
        return jsonify(result.to_dict())
    except Exception as e:
        logger.error(f"ROS2 home machine error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ros2/machines/<machine_id>/estop", methods=["POST"])
def ros2_estop_machine(machine_id: str):
    """Trigger emergency stop on a machine."""
    try:
        bridge = get_ros2_bridge()
        result = run_async(bridge.emergency_stop(machine_id))
        return jsonify(result.to_dict())
    except Exception as e:
        logger.error(f"ROS2 E-stop error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ros2/machines/<machine_id>/jog", methods=["POST"])
def ros2_jog_machine(machine_id: str):
    """
    Jog a machine on specified axis.

    Request body:
    {
        "axis": "x",
        "distance": 10.0,
        "feed_rate": 1000.0
    }
    """
    try:
        data = request.get_json()

        if not data or "axis" not in data or "distance" not in data:
            return jsonify({"error": "Missing axis or distance"}), 400

        bridge = get_ros2_bridge()
        result = run_async(bridge.jog_machine(
            machine_id,
            axis=data["axis"],
            distance=float(data["distance"]),
            feed_rate=float(data.get("feed_rate", 1000.0)),
        ))

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"ROS2 jog error: {e}")
        return jsonify({"error": str(e)}), 500


@vision_bp.route("/ros2/machines/<machine_id>/gcode", methods=["POST"])
def ros2_send_gcode(machine_id: str):
    """
    Send G-code command to a machine.

    Request body:
    {
        "gcode": "G0 X10 Y10"
    }
    """
    try:
        data = request.get_json()

        if not data or "gcode" not in data:
            return jsonify({"error": "Missing gcode"}), 400

        bridge = get_ros2_bridge()
        result = run_async(bridge.send_gcode(machine_id, data["gcode"]))

        return jsonify(result.to_dict())

    except Exception as e:
        logger.error(f"ROS2 G-code send error: {e}")
        return jsonify({"error": str(e)}), 500
