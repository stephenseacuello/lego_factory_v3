"""
Workspace Routes

Live digital twin of the physical LEGO workspace.
Real-time camera feed with brick detection and sync.
"""

from flask import Blueprint, render_template, request, jsonify, Response
import time
import json

workspace_bp = Blueprint("workspace", __name__)

# Detection caching to reduce API calls
_last_detection_time = 0
_last_detection_result = None
_detection_cache_ttl = 0.8  # Cache results for 800ms


@workspace_bp.route("/")
def workspace():
    """Main workspace page - the digital twin."""
    from services.vision import get_camera_manager, get_detector
    from services.inventory import get_workspace_manager

    camera_manager = get_camera_manager()
    workspace_manager = get_workspace_manager()

    cameras = camera_manager.list_cameras()
    current_bricks = workspace_manager.get_current_bricks()
    summary = workspace_manager.get_summary()
    config = workspace_manager.get_config()

    # Get detector info
    try:
        detector = get_detector()
        detector_info = detector.get_info()
    except Exception:
        detector_info = {"backend": "not_initialized"}

    return render_template(
        "pages/workspace.html",
        cameras=cameras,
        current_bricks=[b.to_dict() for b in current_bricks],
        summary=summary,
        config=config.__dict__,
        detector_info=detector_info,
    )


@workspace_bp.route("/frame")
def get_frame():
    """Get a single camera frame as JPEG."""
    from services.vision import get_camera_manager

    camera_manager = get_camera_manager()

    # Ensure camera is open
    if camera_manager._active_camera is None:
        cameras = camera_manager.list_cameras()
        if cameras:
            camera_manager.open(cameras[0].id)

    jpeg_bytes = camera_manager.get_frame_jpeg(quality=60)  # Lower quality for speed

    if jpeg_bytes is None:
        return jsonify({"error": "No frame available"}), 500

    return Response(jpeg_bytes, mimetype="image/jpeg")


@workspace_bp.route("/stream")
def stream():
    """Stream camera frames as MJPEG."""
    from services.vision import get_camera_manager

    camera_manager = get_camera_manager()

    # Ensure camera is open
    if camera_manager._active_camera is None:
        cameras = camera_manager.list_cameras()
        if cameras:
            camera_manager.open(cameras[0].id)

    def generate():
        while True:
            jpeg_bytes = camera_manager.get_frame_jpeg(quality=50)  # Lower quality for speed

            if jpeg_bytes:
                yield (b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n")

            time.sleep(0.1)  # ~10 FPS to reduce bandwidth

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@workspace_bp.route("/detect", methods=["POST"])
def detect():
    """Run detection on current frame and update workspace."""
    global _last_detection_time, _last_detection_result

    from services.vision import get_camera_manager, get_detector
    from services.inventory import get_workspace_manager

    # Return cached result if recent (reduces Roboflow API calls)
    current_time = time.time()
    if _last_detection_result and (current_time - _last_detection_time) < _detection_cache_ttl:
        _last_detection_result["cached"] = True
        return jsonify(_last_detection_result)

    camera_manager = get_camera_manager()
    detector = get_detector()
    workspace_manager = get_workspace_manager()

    # Get frame
    frame = camera_manager.get_frame()
    if frame is None:
        return jsonify({"error": "No frame available"}), 500

    # Run detection
    start_time = time.time()
    detections = detector.detect(frame)
    detection_time = (time.time() - start_time) * 1000

    # Update workspace state
    result = workspace_manager.update_from_detections([d.to_dict() for d in detections])
    result["detection_time_ms"] = round(detection_time, 1)
    result["detections"] = [d.to_dict() for d in detections]
    result["cached"] = False

    # Cache the result
    _last_detection_time = current_time
    _last_detection_result = result

    return jsonify(result)


@workspace_bp.route("/state")
def get_state():
    """Get current workspace state."""
    from services.inventory import get_workspace_manager

    workspace_manager = get_workspace_manager()

    bricks = workspace_manager.get_current_bricks()
    summary = workspace_manager.get_summary()

    return jsonify({"bricks": [b.to_dict() for b in bricks], "summary": summary})


@workspace_bp.route("/clear", methods=["POST"])
def clear_workspace():
    """Clear all bricks from workspace."""
    from services.inventory import get_workspace_manager

    workspace_manager = get_workspace_manager()
    workspace_manager.clear()

    return jsonify({"success": True, "message": "Workspace cleared"})


@workspace_bp.route("/add-all-to-collection", methods=["POST"])
def add_all_to_collection():
    """Add all workspace bricks to permanent collection."""
    from services.inventory import get_workspace_manager

    workspace_manager = get_workspace_manager()
    added = workspace_manager.add_all_to_inventory()

    return jsonify({"success": True, "added": len(added), "items": added})


@workspace_bp.route("/camera/<int:camera_id>/open", methods=["POST"])
def open_camera(camera_id):
    """Open a specific camera."""
    from services.vision import get_camera_manager

    camera_manager = get_camera_manager()
    success = camera_manager.open(camera_id)

    if success:
        return jsonify({"success": True, "camera_id": camera_id})
    else:
        return jsonify({"success": False, "error": "Failed to open camera"}), 500


@workspace_bp.route("/camera/close", methods=["POST"])
def close_camera():
    """Close the active camera."""
    from services.vision import get_camera_manager

    camera_manager = get_camera_manager()
    camera_manager.close()

    return jsonify({"success": True})


@workspace_bp.route("/cameras")
def list_cameras():
    """List available cameras."""
    from services.vision import get_camera_manager

    camera_manager = get_camera_manager()
    cameras = camera_manager.list_cameras()

    return jsonify(
        {"cameras": [c.to_dict() for c in cameras], "status": camera_manager.get_status()}
    )


@workspace_bp.route("/config", methods=["GET", "POST"])
def workspace_config():
    """Get or update workspace configuration."""
    from services.inventory import get_workspace_manager

    workspace_manager = get_workspace_manager()

    if request.method == "POST":
        data = request.get_json()
        config = workspace_manager.update_config(**data)
        return jsonify({"success": True, "config": config.__dict__})
    else:
        config = workspace_manager.get_config()
        return jsonify(config.__dict__)


@workspace_bp.route("/calibrate", methods=["POST"])
def calibrate():
    """Calibrate workspace from corner positions."""
    from services.inventory import get_workspace_manager

    data = request.get_json()

    workspace_manager = get_workspace_manager()
    workspace_manager.calibrate_from_corners(
        top_left=tuple(data["top_left"]),
        top_right=tuple(data["top_right"]),
        bottom_left=tuple(data["bottom_left"]),
        bottom_right=tuple(data["bottom_right"]),
    )

    return jsonify({"success": True, "message": "Calibration saved"})


@workspace_bp.route("/capture", methods=["POST"])
def capture_image():
    """Capture and save current frame."""
    from services.vision import get_camera_manager
    import os
    from datetime import datetime

    camera_manager = get_camera_manager()

    # Create captures directory
    captures_dir = "/home/claude/lego-mcp-fusion360/dashboard/data/captures"
    os.makedirs(captures_dir, exist_ok=True)

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(captures_dir, f"capture_{timestamp}.jpg")

    success = camera_manager.capture_image(filepath)

    if success:
        return jsonify({"success": True, "filepath": filepath})
    else:
        return jsonify({"success": False, "error": "Capture failed"}), 500


@workspace_bp.route("/detector/info")
def detector_info():
    """Get detector information."""
    from services.vision import get_detector

    try:
        detector = get_detector()
        return jsonify(detector.get_info())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================== Camera Settings ==================

# In-memory storage for saved cameras (would be DB in production)
_saved_cameras = {}


@workspace_bp.route("/settings")
def camera_settings():
    """Camera settings page."""
    from services.vision import get_camera_manager

    camera_manager = get_camera_manager()
    cameras = camera_manager.list_cameras()
    status = camera_manager.get_status()

    return render_template(
        "pages/camera_settings.html",
        cameras=cameras,
        saved_cameras=list(_saved_cameras.values()),
        status=status,
    )


@workspace_bp.route("/settings/cameras/scan", methods=["POST"])
def scan_cameras():
    """Scan for available USB cameras."""
    from services.vision import get_camera_manager

    camera_manager = get_camera_manager()

    # Force re-scan of cameras
    cameras = camera_manager.list_cameras()

    return jsonify({
        "success": True,
        "cameras": [c.to_dict() for c in cameras],
        "count": len(cameras)
    })


@workspace_bp.route("/settings/cameras/add", methods=["POST"])
def add_camera():
    """Add an IP camera."""
    from services.vision import get_camera_manager
    import uuid

    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    url = data.get("url", "").strip()
    name = data.get("name", "IP Camera").strip()
    camera_type = data.get("type", "ip")  # ip, rtsp, http, phone

    if not url:
        return jsonify({"success": False, "error": "URL is required"}), 400

    # Generate ID
    camera_id = str(uuid.uuid4())[:8]

    # Save camera config
    camera_config = {
        "id": camera_id,
        "name": name,
        "url": url,
        "type": camera_type,
        "active": False
    }
    _saved_cameras[camera_id] = camera_config

    # Add to camera manager
    camera_manager = get_camera_manager()
    camera_manager.add_ip_camera(url, name)

    return jsonify({
        "success": True,
        "camera": camera_config
    })


@workspace_bp.route("/settings/cameras/<camera_id>/remove", methods=["POST"])
def remove_camera(camera_id):
    """Remove a saved camera."""
    if camera_id in _saved_cameras:
        del _saved_cameras[camera_id]
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Camera not found"}), 404


@workspace_bp.route("/settings/cameras/<camera_id>/test", methods=["POST"])
def test_camera(camera_id):
    """Test a camera connection and get a preview frame."""
    from services.vision import get_camera_manager
    import base64

    camera_manager = get_camera_manager()

    # Try to open the camera
    try:
        # Check if it's a saved IP camera
        if camera_id in _saved_cameras:
            url = _saved_cameras[camera_id]["url"]
            camera_manager.add_ip_camera(url, _saved_cameras[camera_id]["name"])
            # Find the camera by URL match
            cameras = camera_manager.list_cameras()
            for cam in cameras:
                if hasattr(cam, 'url') and cam.url == url:
                    camera_id = cam.id
                    break

        # Open camera
        success = camera_manager.open(int(camera_id) if camera_id.isdigit() else camera_id)

        if not success:
            return jsonify({
                "success": False,
                "error": "Failed to open camera"
            }), 500

        # Get a test frame
        frame_b64 = camera_manager.get_frame_base64()

        if frame_b64:
            return jsonify({
                "success": True,
                "frame": frame_b64,
                "message": "Camera connected successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Camera opened but no frame received"
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@workspace_bp.route("/settings/cameras/<camera_id>/activate", methods=["POST"])
def activate_camera(camera_id):
    """Set a camera as the active camera for the workspace."""
    from services.vision import get_camera_manager

    camera_manager = get_camera_manager()

    try:
        # Handle saved IP cameras
        if camera_id in _saved_cameras:
            url = _saved_cameras[camera_id]["url"]
            camera_manager.add_ip_camera(url, _saved_cameras[camera_id]["name"])
            cameras = camera_manager.list_cameras()
            for cam in cameras:
                if hasattr(cam, 'url') and cam.url == url:
                    camera_id = cam.id
                    break

        # Open the camera
        cam_id = int(camera_id) if str(camera_id).isdigit() else camera_id
        success = camera_manager.open(cam_id)

        if success:
            # Mark as active in saved cameras
            for cid in _saved_cameras:
                _saved_cameras[cid]["active"] = (cid == camera_id)

            return jsonify({
                "success": True,
                "message": f"Camera {camera_id} activated"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to activate camera"
            }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@workspace_bp.route("/settings/cameras/presets")
def camera_presets():
    """Get common camera URL presets."""
    presets = [
        {
            "name": "IP Webcam (Android)",
            "url_template": "http://{ip}:8080/video",
            "description": "Use the 'IP Webcam' app on Android",
            "instructions": [
                "Install 'IP Webcam' from Play Store",
                "Open app and tap 'Start server'",
                "Note the IP address shown",
                "Replace {ip} with your phone's IP"
            ]
        },
        {
            "name": "DroidCam (Android/iOS)",
            "url_template": "http://{ip}:4747/video",
            "description": "Use DroidCam app for phone camera",
            "instructions": [
                "Install DroidCam on phone and PC",
                "Open app on phone",
                "Note the IP address",
                "Replace {ip} with phone IP"
            ]
        },
        {
            "name": "Bambu Lab Printer",
            "url_template": "rtsps://{ip}:322/streaming/live/1",
            "description": "Bambu Lab 3D printer camera",
            "instructions": [
                "Find printer IP in Bambu Studio",
                "Replace {ip} with printer IP",
                "May require access code"
            ]
        },
        {
            "name": "Wyze Cam (RTSP)",
            "url_template": "rtsp://{user}:{pass}@{ip}/live",
            "description": "Wyze camera with RTSP firmware",
            "instructions": [
                "Flash RTSP firmware on Wyze cam",
                "Set up RTSP in Wyze app",
                "Replace {user}, {pass}, {ip}"
            ]
        },
        {
            "name": "Generic RTSP",
            "url_template": "rtsp://{ip}:554/stream1",
            "description": "Generic IP camera RTSP stream",
            "instructions": [
                "Check camera documentation for URL",
                "Common ports: 554, 8554",
                "May need username/password"
            ]
        },
        {
            "name": "HTTP MJPEG Stream",
            "url_template": "http://{ip}/mjpeg/1",
            "description": "HTTP MJPEG stream from IP camera",
            "instructions": [
                "Check camera's web interface",
                "Look for MJPEG or stream URL",
                "Replace {ip} with camera IP"
            ]
        }
    ]
    return jsonify({"presets": presets})
