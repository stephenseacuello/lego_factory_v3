"""
Scan Routes

Bulk scanning mode for inventorying LEGO collections.
"""

from flask import Blueprint, render_template, request, jsonify, session
import time
from datetime import datetime
from typing import List, Dict, Any

scan_bp = Blueprint("scan", __name__)


# Session-based scan tracking
def get_scan_session() -> Dict[str, Any]:
    """Get or create scan session."""
    if "scan_session" not in session:
        session["scan_session"] = {
            "id": f"scan_{int(time.time())}",
            "started": datetime.now().isoformat(),
            "batches": [],
            "total_scanned": 0,
            "total_added": 0,
            "pending": [],
        }
    return session["scan_session"]


def save_scan_session(scan_session: Dict[str, Any]):
    """Save scan session to session storage."""
    session["scan_session"] = scan_session
    session.modified = True


@scan_bp.route("/")
def scan_page():
    """Bulk scanning page."""
    from services.vision import get_camera_manager, get_detector

    camera_manager = get_camera_manager()
    cameras = camera_manager.list_cameras()

    # Get detector info
    try:
        detector = get_detector()
        detector_info = detector.get_info()
    except Exception:
        detector_info = {"backend": "not_initialized"}

    # Get current session
    scan_session = get_scan_session()

    return render_template(
        "pages/scan.html", cameras=cameras, detector_info=detector_info, scan_session=scan_session
    )


@scan_bp.route("/detect", methods=["POST"])
def detect_batch():
    """Detect bricks in current frame for batch scanning."""
    from services.vision import get_camera_manager, get_detector

    camera_manager = get_camera_manager()
    detector = get_detector()

    # Ensure camera is open
    if camera_manager._active_camera is None:
        cameras = camera_manager.list_cameras()
        if cameras:
            camera_manager.open(cameras[0].id)

    # Get frame
    frame = camera_manager.get_frame()
    if frame is None:
        return jsonify({"error": "No frame available"}), 500

    # Run detection
    start_time = time.time()
    detections = detector.detect(frame)
    detection_time = (time.time() - start_time) * 1000

    # Categorize by confidence
    high_confidence = []
    low_confidence = []

    for det in detections:
        det_dict = det.to_dict()
        if det.confidence >= 0.8:
            det_dict["status"] = "confirmed"
            high_confidence.append(det_dict)
        elif det.confidence >= 0.5:
            det_dict["status"] = "review"
            low_confidence.append(det_dict)

    # Update session pending list
    scan_session = get_scan_session()
    scan_session["pending"] = high_confidence + low_confidence
    save_scan_session(scan_session)

    return jsonify(
        {
            "success": True,
            "detection_time_ms": round(detection_time, 1),
            "total": len(detections),
            "high_confidence": len(high_confidence),
            "low_confidence": len(low_confidence),
            "detections": high_confidence + low_confidence,
        }
    )


@scan_bp.route("/confirm", methods=["POST"])
def confirm_batch():
    """Confirm and add detected bricks to collection."""
    from services.inventory import get_inventory_manager

    data = request.get_json()
    bricks = data.get("bricks", [])

    if not bricks:
        # Use pending from session
        scan_session = get_scan_session()
        bricks = [b for b in scan_session.get("pending", []) if b.get("status") == "confirmed"]

    inventory = get_inventory_manager()
    added = []

    for brick in bricks:
        item = inventory.add_brick(
            brick_id=brick.get("brick_id", "unknown"),
            quantity=brick.get("quantity", 1),
            color=brick.get("color", "unknown"),
            category=brick.get("category", "brick"),
            brick_name=brick.get("brick_name"),
            source="scan",
        )
        added.append(item.to_dict())

    # Update session
    scan_session = get_scan_session()
    scan_session["batches"].append({"timestamp": datetime.now().isoformat(), "count": len(added)})
    scan_session["total_scanned"] += len(bricks)
    scan_session["total_added"] += len(added)
    scan_session["pending"] = []
    save_scan_session(scan_session)

    return jsonify({"success": True, "added": len(added), "items": added, "session": scan_session})


@scan_bp.route("/confirm-item", methods=["POST"])
def confirm_item():
    """Confirm a single brick detection."""
    data = request.get_json()
    brick_id = data.get("brick_id")
    color = data.get("color")

    scan_session = get_scan_session()

    for brick in scan_session.get("pending", []):
        if brick.get("brick_id") == brick_id and brick.get("color") == color:
            brick["status"] = "confirmed"
            break

    save_scan_session(scan_session)

    return jsonify({"success": True})


@scan_bp.route("/reject-item", methods=["POST"])
def reject_item():
    """Reject a brick detection."""
    data = request.get_json()
    brick_id = data.get("brick_id")
    color = data.get("color")

    scan_session = get_scan_session()

    scan_session["pending"] = [
        b
        for b in scan_session.get("pending", [])
        if not (b.get("brick_id") == brick_id and b.get("color") == color)
    ]

    save_scan_session(scan_session)

    return jsonify({"success": True})


@scan_bp.route("/update-item", methods=["POST"])
def update_item():
    """Update a brick detection (change type/color)."""
    data = request.get_json()
    old_brick_id = data.get("old_brick_id")
    old_color = data.get("old_color")
    new_brick_id = data.get("brick_id")
    new_color = data.get("color")
    new_name = data.get("brick_name")

    scan_session = get_scan_session()

    for brick in scan_session.get("pending", []):
        if brick.get("brick_id") == old_brick_id and brick.get("color") == old_color:
            brick["brick_id"] = new_brick_id
            brick["color"] = new_color
            brick["brick_name"] = new_name or new_brick_id.replace("_", " ").title()
            brick["status"] = "confirmed"
            break

    save_scan_session(scan_session)

    return jsonify({"success": True})


@scan_bp.route("/session")
def get_session():
    """Get current scan session."""
    scan_session = get_scan_session()
    return jsonify(scan_session)


@scan_bp.route("/session/clear", methods=["POST"])
def clear_session():
    """Clear scan session."""
    if "scan_session" in session:
        del session["scan_session"]

    return jsonify({"success": True, "message": "Session cleared"})


@scan_bp.route("/session/export")
def export_session():
    """Export scan session as JSON."""
    scan_session = get_scan_session()

    from flask import Response
    import json

    return Response(
        json.dumps(scan_session, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=scan_session.json"},
    )


@scan_bp.route("/quick-add", methods=["POST"])
def quick_add():
    """Quick add multiple of a single brick type."""
    from services.inventory import get_inventory_manager

    data = request.get_json()
    brick_id = data.get("brick_id")
    color = data.get("color", "unknown")
    quantity = data.get("quantity", 1)

    inventory = get_inventory_manager()
    item = inventory.add_brick(
        brick_id=brick_id, quantity=quantity, color=color, source="scan_quick"
    )

    # Update session
    scan_session = get_scan_session()
    scan_session["total_scanned"] += quantity
    scan_session["total_added"] += quantity
    save_scan_session(scan_session)

    return jsonify({"success": True, "item": item.to_dict(), "session": scan_session})


@scan_bp.route("/upload", methods=["POST"])
def upload_image():
    """Process an uploaded image for detection."""
    from services.vision import get_detector

    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400

    file = request.files["image"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Read image
    import cv2
    import numpy as np

    file_bytes = file.read()
    nparr = np.frombuffer(file_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify({"error": "Could not decode image"}), 400

    # Run detection
    detector = get_detector()
    start_time = time.time()
    detections = detector.detect(frame)
    detection_time = (time.time() - start_time) * 1000

    # Categorize
    results = []
    for det in detections:
        det_dict = det.to_dict()
        det_dict["status"] = "confirmed" if det.confidence >= 0.8 else "review"
        results.append(det_dict)

    # Update session
    scan_session = get_scan_session()
    scan_session["pending"].extend(results)
    save_scan_session(scan_session)

    return jsonify(
        {
            "success": True,
            "detection_time_ms": round(detection_time, 1),
            "total": len(detections),
            "detections": results,
        }
    )
