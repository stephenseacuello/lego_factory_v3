"""
WebSocket Events

Real-time event handling for the dashboard.
"""

import time
import threading

# Optional SocketIO support
try:
    from flask_socketio import emit, join_room, leave_room
    from flask import request

    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    emit = join_room = leave_room = None
    request = None


# Track connected clients
connected_clients = set()

# Background threads
_status_thread = None
_status_thread_running = False


def register_events(socketio):
    """Register all WebSocket event handlers."""

    if not SOCKETIO_AVAILABLE or socketio is None:
        return

    @socketio.on("connect")
    def handle_connect():
        """Handle client connection."""
        client_id = request.sid
        connected_clients.add(client_id)

        # Send welcome message
        emit(
            "connected",
            {
                "client_id": client_id,
                "message": "Connected to LEGO MCP Dashboard",
                "timestamp": time.time(),
            },
        )

        # Start status monitoring if not running
        start_status_monitoring(socketio)

    @socketio.on("disconnect")
    def handle_disconnect():
        """Handle client disconnection."""
        client_id = request.sid
        connected_clients.discard(client_id)

        # Stop monitoring if no clients
        if not connected_clients:
            stop_status_monitoring()

    @socketio.on("subscribe")
    def handle_subscribe(data):
        """Subscribe to a room/channel."""
        room = data.get("room")
        if room:
            join_room(room)
            emit("subscribed", {"room": room})

    @socketio.on("unsubscribe")
    def handle_unsubscribe(data):
        """Unsubscribe from a room/channel."""
        room = data.get("room")
        if room:
            leave_room(room)
            emit("unsubscribed", {"room": room})

    @socketio.on("ping")
    def handle_ping():
        """Handle ping (keep-alive)."""
        emit("pong", {"timestamp": time.time()})

    @socketio.on("check_status")
    def handle_check_status():
        """Check and emit system status."""
        from services.status_service import StatusService

        status = StatusService.get_all_status(use_cache=False)
        emit("status_update", status)

    @socketio.on("execute_tool")
    def handle_execute_tool(data):
        """Execute an MCP tool and emit progress/result."""
        from services.mcp_bridge import MCPBridge

        tool_name = data.get("tool")
        params = data.get("params", {})
        request_id = data.get("request_id", str(time.time()))

        # Emit start
        emit(
            "tool_started", {"request_id": request_id, "tool": tool_name, "timestamp": time.time()}
        )

        # Execute
        result = MCPBridge.execute_tool(tool_name, params)

        # Emit result
        emit(
            "tool_complete",
            {
                "request_id": request_id,
                "tool": tool_name,
                "result": result,
                "timestamp": time.time(),
            },
        )

    @socketio.on("watch_files")
    def handle_watch_files(data):
        """Watch a directory for file changes."""
        directory = data.get("directory", "")
        join_room(f"files:{directory}")
        emit("watching", {"directory": directory})


def start_status_monitoring(socketio):
    """Start background status monitoring."""
    global _status_thread, _status_thread_running

    if _status_thread_running:
        return

    _status_thread_running = True

    def monitor():
        from services.status_service import StatusService

        last_status = {}

        while _status_thread_running:
            try:
                status = StatusService.get_all_status(use_cache=False)

                # Check for changes
                if status != last_status:
                    socketio.emit("status_update", status)

                    # Check for specific changes
                    for service_id, service_status in status.get("services", {}).items():
                        old_status = last_status.get("services", {}).get(service_id, {})

                        if service_status.get("status") != old_status.get("status"):
                            socketio.emit(
                                "service_status_changed",
                                {
                                    "service": service_id,
                                    "old_status": old_status.get("status"),
                                    "new_status": service_status.get("status"),
                                    "timestamp": time.time(),
                                },
                            )

                    last_status = status

            except Exception as e:
                socketio.emit("error", {"type": "status_monitor", "message": str(e)})

            # Wait before next check
            time.sleep(10)

    _status_thread = threading.Thread(target=monitor, daemon=True)
    _status_thread.start()


def stop_status_monitoring():
    """Stop background status monitoring."""
    global _status_thread_running
    _status_thread_running = False


def emit_operation_progress(operation_id, step, total_steps, message, percent):
    """Emit operation progress update."""
    from app import socketio

    socketio.emit(
        "operation_progress",
        {
            "operation_id": operation_id,
            "step": step,
            "total_steps": total_steps,
            "message": message,
            "percent": percent,
            "timestamp": time.time(),
        },
    )


def emit_operation_complete(operation_id, result, duration_ms):
    """Emit operation complete."""
    from app import socketio

    socketio.emit(
        "operation_complete",
        {
            "operation_id": operation_id,
            "result": result,
            "duration_ms": duration_ms,
            "timestamp": time.time(),
        },
    )


def emit_file_created(file_path, size):
    """Emit file created event."""
    from app import socketio

    socketio.emit("file_created", {"path": file_path, "size": size, "timestamp": time.time()})


def emit_error(error_type, message, code=None):
    """Emit error event."""
    from app import socketio

    socketio.emit(
        "error", {"type": error_type, "message": message, "code": code, "timestamp": time.time()}
    )


# ============================================================
# Phase 2: Digital Twin WebSocket Events
# ============================================================


def emit_workspace_update(data):
    """Emit workspace update to all subscribers."""
    try:
        from app import socketio

        socketio.emit("workspace:update", {**data, "timestamp": time.time()}, room="workspace")
    except Exception:
        pass


def emit_detection_result(detections, detection_time_ms):
    """Emit detection results."""
    try:
        from app import socketio

        socketio.emit(
            "detection:result",
            {
                "detections": [d.to_dict() if hasattr(d, "to_dict") else d for d in detections],
                "detection_time_ms": detection_time_ms,
                "count": len(detections),
                "timestamp": time.time(),
            },
            room="workspace",
        )
    except Exception:
        pass


def emit_collection_update(item, action="add"):
    """Emit collection update."""
    try:
        from app import socketio

        socketio.emit(
            "collection:update",
            {
                "action": action,
                "item": item.to_dict() if hasattr(item, "to_dict") else item,
                "timestamp": time.time(),
            },
            room="collection",
        )
    except Exception:
        pass


def emit_scan_progress(batch_id, scanned, added, pending):
    """Emit scan progress update."""
    try:
        from app import socketio

        socketio.emit(
            "scan:progress",
            {
                "batch_id": batch_id,
                "scanned": scanned,
                "added": added,
                "pending": pending,
                "timestamp": time.time(),
            },
            room="scan",
        )
    except Exception:
        pass


def emit_build_check(build_id, check_result):
    """Emit build check result."""
    try:
        from app import socketio

        socketio.emit(
            "build:checked",
            {
                "build_id": build_id,
                "result": (
                    check_result.to_dict() if hasattr(check_result, "to_dict") else check_result
                ),
                "timestamp": time.time(),
            },
            room="builds",
        )
    except Exception:
        pass


def register_phase2_events(socketio):
    """Register Phase 2 WebSocket event handlers."""

    if not SOCKETIO_AVAILABLE or socketio is None:
        return

    @socketio.on("workspace:subscribe")
    def handle_workspace_subscribe():
        """Subscribe to workspace updates."""
        join_room("workspace")
        emit("workspace:subscribed", {"status": "ok"})

    @socketio.on("workspace:unsubscribe")
    def handle_workspace_unsubscribe():
        """Unsubscribe from workspace updates."""
        leave_room("workspace")

    @socketio.on("workspace:detect")
    def handle_workspace_detect():
        """Trigger detection on workspace."""
        from services.vision import get_camera_manager, get_detector
        from services.inventory import get_workspace_manager

        camera_manager = get_camera_manager()
        detector = get_detector()
        workspace_manager = get_workspace_manager()

        frame = camera_manager.get_frame()
        if frame is None:
            emit("workspace:error", {"error": "No frame available"})
            return

        start = time.time()
        detections = detector.detect(frame)
        detection_time = (time.time() - start) * 1000

        result = workspace_manager.update_from_detections([d.to_dict() for d in detections])
        result["detection_time_ms"] = round(detection_time, 1)

        emit("workspace:update", result)
        socketio.emit("workspace:update", result, room="workspace", include_self=False)

    @socketio.on("workspace:state")
    def handle_workspace_state():
        """Get current workspace state."""
        from services.inventory import get_workspace_manager

        ws = get_workspace_manager()
        emit(
            "workspace:state",
            {"bricks": [b.to_dict() for b in ws.get_current_bricks()], "summary": ws.get_summary()},
        )

    @socketio.on("collection:subscribe")
    def handle_collection_subscribe():
        """Subscribe to collection updates."""
        join_room("collection")
        emit("collection:subscribed", {"status": "ok"})

    @socketio.on("scan:subscribe")
    def handle_scan_subscribe():
        """Subscribe to scan updates."""
        join_room("scan")
        emit("scan:subscribed", {"status": "ok"})

    @socketio.on("scan:detect")
    def handle_scan_detect():
        """Run detection for scanning."""
        from services.vision import get_camera_manager, get_detector

        camera_manager = get_camera_manager()
        detector = get_detector()

        frame = camera_manager.get_frame()
        if frame is None:
            emit("scan:error", {"error": "No frame available"})
            return

        start = time.time()
        detections = detector.detect(frame)
        detection_time = (time.time() - start) * 1000

        results = []
        for det in detections:
            d = det.to_dict()
            d["status"] = "confirmed" if det.confidence >= 0.8 else "review"
            results.append(d)

        emit(
            "scan:detected",
            {
                "detections": results,
                "detection_time_ms": round(detection_time, 1),
                "total": len(results),
            },
        )

    @socketio.on("builds:subscribe")
    def handle_builds_subscribe():
        """Subscribe to builds updates."""
        join_room("builds")
        emit("builds:subscribed", {"status": "ok"})

    @socketio.on("builds:check")
    def handle_builds_check(data):
        """Check a build against inventory."""
        from services.builds import get_build_planner

        build_id = data.get("build_id")
        if not build_id:
            emit("builds:error", {"error": "No build_id"})
            return

        planner = get_build_planner()
        check = planner.check_build(build_id)

        if check:
            emit("builds:checked", check.to_dict())
        else:
            emit("builds:error", {"error": "Build not found"})

    @socketio.on("camera:subscribe")
    def handle_camera_subscribe():
        """Subscribe to camera frames."""
        join_room("camera")
        emit("camera:subscribed", {"status": "ok"})

    @socketio.on("camera:frame")
    def handle_camera_frame():
        """Get a single camera frame as base64."""
        from services.vision import get_camera_manager

        camera_manager = get_camera_manager()
        frame_b64 = camera_manager.get_frame_base64(quality=70)

        if frame_b64:
            emit("camera:frame", {"image": frame_b64})
        else:
            emit("camera:error", {"error": "No frame"})


# ============================================================
# Phase 5: Manufacturing & MES WebSocket Events
# ============================================================


def emit_work_order_update(work_order_id, status, progress=None, details=None):
    """Emit work order status update."""
    try:
        from app import socketio

        socketio.emit(
            "mes:work_order_update",
            {
                "work_order_id": work_order_id,
                "status": status,
                "progress": progress,
                "details": details,
                "timestamp": time.time(),
            },
            room="manufacturing",
        )
    except Exception:
        pass


def emit_machine_status(machine_id, status, oee=None, current_job=None):
    """Emit machine status change."""
    try:
        from app import socketio

        socketio.emit(
            "mes:machine_status",
            {
                "machine_id": machine_id,
                "status": status,
                "oee": oee,
                "current_job": current_job,
                "timestamp": time.time(),
            },
            room="manufacturing",
        )
    except Exception:
        pass


def emit_quality_alert(alert_type, severity, message, work_order_id=None, part_id=None):
    """Emit quality alert."""
    try:
        from app import socketio

        socketio.emit(
            "quality:alert",
            {
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "work_order_id": work_order_id,
                "part_id": part_id,
                "timestamp": time.time(),
            },
            room="quality",
        )
    except Exception:
        pass


def emit_spc_violation(chart_id, rule_violated, value, ucl, lcl, measurement_id=None):
    """Emit SPC control limit violation."""
    try:
        from app import socketio

        socketio.emit(
            "quality:spc_violation",
            {
                "chart_id": chart_id,
                "rule_violated": rule_violated,
                "value": value,
                "ucl": ucl,
                "lcl": lcl,
                "measurement_id": measurement_id,
                "timestamp": time.time(),
            },
            room="quality",
        )
    except Exception:
        pass


def emit_oee_update(work_center_id, oee_data):
    """Emit OEE metrics update."""
    try:
        from app import socketio

        socketio.emit(
            "mes:oee_update",
            {
                "work_center_id": work_center_id,
                "availability": oee_data.get("availability"),
                "performance": oee_data.get("performance"),
                "quality": oee_data.get("quality"),
                "oee": oee_data.get("oee"),
                "timestamp": time.time(),
            },
            room="manufacturing",
        )
    except Exception:
        pass


def emit_andon_event(work_center_id, andon_type, message, operator_id=None):
    """Emit Andon event (help call, quality stop, etc.)."""
    try:
        from app import socketio

        socketio.emit(
            "mes:andon",
            {
                "work_center_id": work_center_id,
                "andon_type": andon_type,
                "message": message,
                "operator_id": operator_id,
                "timestamp": time.time(),
            },
            room="manufacturing",
        )

        # Also emit to Andon-specific room for displays
        socketio.emit(
            "andon:event",
            {
                "work_center_id": work_center_id,
                "andon_type": andon_type,
                "message": message,
                "timestamp": time.time(),
            },
            room="andon",
        )
    except Exception:
        pass


def emit_maintenance_alert(machine_id, alert_type, rul_hours=None, message=None):
    """Emit predictive maintenance alert."""
    try:
        from app import socketio

        socketio.emit(
            "maintenance:alert",
            {
                "machine_id": machine_id,
                "alert_type": alert_type,
                "rul_hours": rul_hours,
                "message": message,
                "timestamp": time.time(),
            },
            room="maintenance",
        )
    except Exception:
        pass


def emit_schedule_update(schedule_id, changes):
    """Emit schedule update notification."""
    try:
        from app import socketio

        socketio.emit(
            "scheduling:update",
            {
                "schedule_id": schedule_id,
                "changes": changes,
                "timestamp": time.time(),
            },
            room="scheduling",
        )
    except Exception:
        pass


def emit_carbon_update(scope, emissions_kg, energy_kwh=None):
    """Emit carbon/sustainability update."""
    try:
        from app import socketio

        socketio.emit(
            "sustainability:carbon_update",
            {
                "scope": scope,
                "emissions_kg": emissions_kg,
                "energy_kwh": energy_kwh,
                "timestamp": time.time(),
            },
            room="sustainability",
        )
    except Exception:
        pass


def emit_edge_data(device_id, measurements):
    """Emit real-time IIoT/edge data."""
    try:
        from app import socketio

        socketio.emit(
            "edge:data",
            {
                "device_id": device_id,
                "measurements": measurements,
                "timestamp": time.time(),
            },
            room="edge",
        )
    except Exception:
        pass


def emit_ai_insight(insight_type, message, confidence=None, recommendations=None):
    """Emit AI copilot insight."""
    try:
        from app import socketio

        socketio.emit(
            "ai:insight",
            {
                "insight_type": insight_type,
                "message": message,
                "confidence": confidence,
                "recommendations": recommendations,
                "timestamp": time.time(),
            },
            room="ai",
        )
    except Exception:
        pass


def register_manufacturing_events(socketio):
    """Register manufacturing WebSocket event handlers."""

    if not SOCKETIO_AVAILABLE or socketio is None:
        return

    @socketio.on("manufacturing:subscribe")
    def handle_manufacturing_subscribe():
        """Subscribe to manufacturing/MES updates."""
        join_room("manufacturing")
        emit("manufacturing:subscribed", {"status": "ok", "rooms": ["manufacturing"]})

    @socketio.on("quality:subscribe")
    def handle_quality_subscribe():
        """Subscribe to quality updates."""
        join_room("quality")
        emit("quality:subscribed", {"status": "ok"})

    @socketio.on("maintenance:subscribe")
    def handle_maintenance_subscribe():
        """Subscribe to maintenance alerts."""
        join_room("maintenance")
        emit("maintenance:subscribed", {"status": "ok"})

    @socketio.on("scheduling:subscribe")
    def handle_scheduling_subscribe():
        """Subscribe to scheduling updates."""
        join_room("scheduling")
        emit("scheduling:subscribed", {"status": "ok"})

    @socketio.on("sustainability:subscribe")
    def handle_sustainability_subscribe():
        """Subscribe to sustainability/carbon updates."""
        join_room("sustainability")
        emit("sustainability:subscribed", {"status": "ok"})

    @socketio.on("edge:subscribe")
    def handle_edge_subscribe():
        """Subscribe to edge/IIoT data."""
        join_room("edge")
        emit("edge:subscribed", {"status": "ok"})

    @socketio.on("ai:subscribe")
    def handle_ai_subscribe():
        """Subscribe to AI copilot insights."""
        join_room("ai")
        emit("ai:subscribed", {"status": "ok"})

    @socketio.on("andon:subscribe")
    def handle_andon_subscribe():
        """Subscribe to Andon display updates."""
        join_room("andon")
        emit("andon:subscribed", {"status": "ok"})

    @socketio.on("mes:get_shop_floor")
    def handle_get_shop_floor():
        """Get current shop floor status."""
        try:
            # Get work center status
            work_centers = [
                {
                    "work_center_id": "WC-PRINT-01",
                    "name": "3D Printing Cell 1",
                    "status": "running",
                    "current_job": "WO-2024-0847",
                    "oee": {"availability": 92.5, "performance": 88.3, "quality": 99.1, "oee": 81.0},
                    "operator": "John Smith",
                },
                {
                    "work_center_id": "WC-PRINT-02",
                    "name": "3D Printing Cell 2",
                    "status": "idle",
                    "current_job": None,
                    "oee": {"availability": 85.0, "performance": 90.0, "quality": 98.5, "oee": 75.4},
                    "operator": None,
                },
                {
                    "work_center_id": "WC-CNC-01",
                    "name": "CNC Milling Center",
                    "status": "setup",
                    "current_job": "WO-2024-0849",
                    "oee": {"availability": 78.0, "performance": 92.0, "quality": 99.5, "oee": 71.4},
                    "operator": "Jane Doe",
                },
            ]

            emit("mes:shop_floor", {
                "work_centers": work_centers,
                "active_orders": 5,
                "completed_today": 12,
                "timestamp": time.time(),
            })

        except Exception as e:
            emit("mes:error", {"error": str(e)})

    @socketio.on("mes:get_oee_realtime")
    def handle_get_oee_realtime(data):
        """Get real-time OEE for a work center."""
        work_center_id = data.get("work_center_id")

        # Simulate real-time OEE calculation
        import random
        oee_data = {
            "work_center_id": work_center_id,
            "availability": round(85 + random.uniform(-5, 10), 1),
            "performance": round(88 + random.uniform(-8, 8), 1),
            "quality": round(97 + random.uniform(-2, 3), 1),
            "oee": 0,
        }
        oee_data["oee"] = round(
            oee_data["availability"] * oee_data["performance"] * oee_data["quality"] / 10000, 1
        )

        emit("mes:oee_update", oee_data)

    @socketio.on("quality:get_spc_chart")
    def handle_get_spc_chart(data):
        """Get SPC chart data."""
        chart_id = data.get("chart_id")

        # Simulate SPC data
        import random
        points = []
        mean = 10.0
        ucl = 10.3
        lcl = 9.7

        for i in range(30):
            value = mean + random.gauss(0, 0.08)
            points.append({
                "index": i,
                "value": round(value, 4),
                "in_control": lcl <= value <= ucl,
            })

        emit("quality:spc_data", {
            "chart_id": chart_id,
            "characteristic": "Stud Height",
            "mean": mean,
            "ucl": ucl,
            "lcl": lcl,
            "points": points,
            "timestamp": time.time(),
        })

    @socketio.on("ai:ask")
    def handle_ai_ask(data):
        """Ask the AI copilot a question."""
        question = data.get("question", "")

        # Emit thinking indicator
        emit("ai:thinking", {"status": "processing"})

        try:
            from services.ai.manufacturing_copilot import ManufacturingCopilot

            copilot = ManufacturingCopilot()
            response = copilot.ask(question)

            emit("ai:response", {
                "question": question,
                "answer": response.get("answer", ""),
                "confidence": response.get("confidence", 0.8),
                "sources": response.get("sources", []),
                "timestamp": time.time(),
            })

        except Exception as e:
            emit("ai:response", {
                "question": question,
                "answer": f"I'm sorry, I encountered an error: {str(e)}",
                "confidence": 0,
                "timestamp": time.time(),
            })

    @socketio.on("edge:get_devices")
    def handle_get_edge_devices():
        """Get list of connected edge devices."""
        devices = [
            {
                "device_id": "DEV-PRINT-01",
                "name": "Prusa MK3S+ #1",
                "type": "3d_printer",
                "status": "online",
                "last_data": time.time() - 5,
            },
            {
                "device_id": "DEV-PRINT-02",
                "name": "Prusa MK3S+ #2",
                "type": "3d_printer",
                "status": "online",
                "last_data": time.time() - 3,
            },
            {
                "device_id": "DEV-TEMP-01",
                "name": "Environment Sensor",
                "type": "sensor",
                "status": "online",
                "last_data": time.time() - 1,
            },
        ]

        emit("edge:devices", {
            "devices": devices,
            "count": len(devices),
            "timestamp": time.time(),
        })


# ============================================================
# Phase 6: VR Training WebSocket Events
# ============================================================


def emit_vr_session_started(session_id, scenario_id, trainee_id, scenario_name):
    """Emit VR training session started event."""
    try:
        from app import socketio

        socketio.emit(
            "vr:session_started",
            {
                "session_id": session_id,
                "scenario_id": scenario_id,
                "trainee_id": trainee_id,
                "scenario_name": scenario_name,
                "timestamp": time.time(),
            },
            room="vr_training",
        )
    except Exception:
        pass


def emit_vr_step_progress(session_id, step_number, total_steps, step_name, status, score=None):
    """Emit VR training step progress update."""
    try:
        from app import socketio

        socketio.emit(
            "vr:step_progress",
            {
                "session_id": session_id,
                "step_number": step_number,
                "total_steps": total_steps,
                "step_name": step_name,
                "status": status,
                "score": score,
                "progress_percent": round((step_number / total_steps) * 100, 1) if total_steps > 0 else 0,
                "timestamp": time.time(),
            },
            room="vr_training",
        )
    except Exception:
        pass


def emit_vr_session_complete(session_id, trainee_id, final_score, passed, duration_seconds):
    """Emit VR training session completion event."""
    try:
        from app import socketio

        socketio.emit(
            "vr:session_complete",
            {
                "session_id": session_id,
                "trainee_id": trainee_id,
                "final_score": final_score,
                "passed": passed,
                "duration_seconds": duration_seconds,
                "timestamp": time.time(),
            },
            room="vr_training",
        )
    except Exception:
        pass


def emit_vr_device_status(device_id, device_type, status, battery_percent=None, tracking_quality=None):
    """Emit VR device status update."""
    try:
        from app import socketio

        socketio.emit(
            "vr:device_status",
            {
                "device_id": device_id,
                "device_type": device_type,
                "status": status,
                "battery_percent": battery_percent,
                "tracking_quality": tracking_quality,
                "timestamp": time.time(),
            },
            room="vr_training",
        )
    except Exception:
        pass


def emit_vr_safety_event(session_id, event_type, message, severity="warning"):
    """Emit VR safety event (boundary breach, collision warning, etc.)."""
    try:
        from app import socketio

        socketio.emit(
            "vr:safety_event",
            {
                "session_id": session_id,
                "event_type": event_type,
                "message": message,
                "severity": severity,
                "timestamp": time.time(),
            },
            room="vr_training",
        )
    except Exception:
        pass


def register_vr_training_events(socketio):
    """Register VR Training WebSocket event handlers."""

    if not SOCKETIO_AVAILABLE or socketio is None:
        return

    @socketio.on("vr:subscribe")
    def handle_vr_subscribe():
        """Subscribe to VR training updates."""
        join_room("vr_training")
        emit("vr:subscribed", {"status": "ok", "room": "vr_training"})

    @socketio.on("vr:unsubscribe")
    def handle_vr_unsubscribe():
        """Unsubscribe from VR training updates."""
        leave_room("vr_training")
        emit("vr:unsubscribed", {"status": "ok"})

    @socketio.on("vr:session_subscribe")
    def handle_vr_session_subscribe(data):
        """Subscribe to specific VR session updates."""
        session_id = data.get("session_id")
        if session_id:
            join_room(f"vr_session:{session_id}")
            emit("vr:session_subscribed", {"session_id": session_id, "status": "ok"})

    @socketio.on("vr:trainee_subscribe")
    def handle_vr_trainee_subscribe(data):
        """Subscribe to trainee-specific updates."""
        trainee_id = data.get("trainee_id")
        if trainee_id:
            join_room(f"vr_trainee:{trainee_id}")
            emit("vr:trainee_subscribed", {"trainee_id": trainee_id, "status": "ok"})

    @socketio.on("vr:get_active_sessions")
    def handle_get_active_sessions():
        """Get list of active VR training sessions."""
        # Return simulated active sessions
        sessions = [
            {
                "session_id": "VRS-2024-001",
                "scenario_id": "equip-safety-01",
                "trainee_id": "TRN-001",
                "trainee_name": "John Smith",
                "scenario_name": "Equipment Safety Fundamentals",
                "progress_percent": 65,
                "current_step": "Module 3: Emergency Procedures",
                "started_at": time.time() - 1200,
            }
        ]

        emit("vr:active_sessions", {
            "sessions": sessions,
            "count": len(sessions),
            "timestamp": time.time(),
        })

    @socketio.on("vr:leaderboard")
    def handle_get_leaderboard(data):
        """Get VR training leaderboard."""
        scenario_id = data.get("scenario_id")
        limit = data.get("limit", 10)

        # Simulated leaderboard data
        leaderboard = [
            {"rank": 1, "trainee_name": "Alice Johnson", "score": 98.5, "time_seconds": 420},
            {"rank": 2, "trainee_name": "Bob Wilson", "score": 96.2, "time_seconds": 445},
            {"rank": 3, "trainee_name": "Carol Davis", "score": 94.8, "time_seconds": 398},
        ]

        emit("vr:leaderboard_data", {
            "scenario_id": scenario_id,
            "leaderboard": leaderboard[:limit],
            "timestamp": time.time(),
        })


# ============================================================
# Phase 7: Robotic Arms WebSocket Events
# ============================================================


def emit_robot_status(arm_id, status, position=None, velocity=None, payload_kg=None):
    """Emit robotic arm status update."""
    try:
        from app import socketio

        socketio.emit(
            "robot:status",
            {
                "arm_id": arm_id,
                "status": status,
                "position": position,
                "velocity": velocity,
                "payload_kg": payload_kg,
                "timestamp": time.time(),
            },
            room="robotics",
        )
    except Exception:
        pass


def emit_robot_task_update(arm_id, task_id, status, progress_percent=None, error=None):
    """Emit robotic arm task progress update."""
    try:
        from app import socketio

        socketio.emit(
            "robot:task_update",
            {
                "arm_id": arm_id,
                "task_id": task_id,
                "status": status,
                "progress_percent": progress_percent,
                "error": error,
                "timestamp": time.time(),
            },
            room="robotics",
        )
    except Exception:
        pass


def emit_robot_safety_violation(arm_id, zone_id, violation_type, severity, action_taken=None):
    """Emit robotic arm safety zone violation (ISO 10218 compliance)."""
    try:
        from app import socketio

        socketio.emit(
            "robot:safety_violation",
            {
                "arm_id": arm_id,
                "zone_id": zone_id,
                "violation_type": violation_type,
                "severity": severity,
                "action_taken": action_taken,
                "timestamp": time.time(),
            },
            room="robotics",
        )

        # Also emit to safety-specific room for critical alerts
        if severity in ("critical", "emergency"):
            socketio.emit(
                "safety:robot_violation",
                {
                    "arm_id": arm_id,
                    "zone_id": zone_id,
                    "violation_type": violation_type,
                    "severity": severity,
                    "timestamp": time.time(),
                },
                room="safety",
            )
    except Exception:
        pass


def emit_robot_sync_status(sync_id, arms, status, phase=None, error=None):
    """Emit synchronized motion status for multi-arm coordination."""
    try:
        from app import socketio

        socketio.emit(
            "robot:sync_status",
            {
                "sync_id": sync_id,
                "arms": arms,
                "status": status,
                "phase": phase,
                "error": error,
                "timestamp": time.time(),
            },
            room="robotics",
        )
    except Exception:
        pass


def emit_robot_trajectory_update(arm_id, trajectory_id, waypoint_index, total_waypoints, eta_seconds=None):
    """Emit trajectory execution progress."""
    try:
        from app import socketio

        socketio.emit(
            "robot:trajectory_update",
            {
                "arm_id": arm_id,
                "trajectory_id": trajectory_id,
                "waypoint_index": waypoint_index,
                "total_waypoints": total_waypoints,
                "progress_percent": round((waypoint_index / total_waypoints) * 100, 1) if total_waypoints > 0 else 0,
                "eta_seconds": eta_seconds,
                "timestamp": time.time(),
            },
            room="robotics",
        )
    except Exception:
        pass


def emit_robot_calibration_update(arm_id, calibration_type, status, accuracy_mm=None):
    """Emit calibration status update."""
    try:
        from app import socketio

        socketio.emit(
            "robot:calibration_update",
            {
                "arm_id": arm_id,
                "calibration_type": calibration_type,
                "status": status,
                "accuracy_mm": accuracy_mm,
                "timestamp": time.time(),
            },
            room="robotics",
        )
    except Exception:
        pass


def register_robotics_events(socketio):
    """Register Robotics WebSocket event handlers."""

    if not SOCKETIO_AVAILABLE or socketio is None:
        return

    @socketio.on("robotics:subscribe")
    def handle_robotics_subscribe():
        """Subscribe to robotics updates."""
        join_room("robotics")
        emit("robotics:subscribed", {"status": "ok", "room": "robotics"})

    @socketio.on("robotics:unsubscribe")
    def handle_robotics_unsubscribe():
        """Unsubscribe from robotics updates."""
        leave_room("robotics")
        emit("robotics:unsubscribed", {"status": "ok"})

    @socketio.on("robotics:arm_subscribe")
    def handle_arm_subscribe(data):
        """Subscribe to specific arm updates."""
        arm_id = data.get("arm_id")
        if arm_id:
            join_room(f"robot:{arm_id}")
            emit("robotics:arm_subscribed", {"arm_id": arm_id, "status": "ok"})

    @socketio.on("safety:subscribe")
    def handle_safety_subscribe():
        """Subscribe to safety alerts."""
        join_room("safety")
        emit("safety:subscribed", {"status": "ok"})

    @socketio.on("robotics:get_fleet_status")
    def handle_get_fleet_status():
        """Get status of all robotic arms."""
        import random

        arms = [
            {
                "arm_id": "ARM-001",
                "name": "Assembly Arm Alpha",
                "model": "UR10e",
                "status": "active",
                "current_task": "TSK-001",
                "position": {"x": 150.5, "y": 200.3, "z": 450.2, "rx": 0.0, "ry": 90.0, "rz": 45.0},
                "payload_kg": 2.5,
                "health_score": 95,
            },
            {
                "arm_id": "ARM-002",
                "name": "Assembly Arm Beta",
                "model": "UR10e",
                "status": "idle",
                "current_task": None,
                "position": {"x": 0.0, "y": 0.0, "z": 500.0, "rx": 0.0, "ry": 0.0, "rz": 0.0},
                "payload_kg": 0.0,
                "health_score": 98,
            },
            {
                "arm_id": "ARM-003",
                "name": "Inspection Arm",
                "model": "Franka Emika",
                "status": "calibrating",
                "current_task": "CAL-003",
                "position": {"x": 100.0, "y": 50.0, "z": 300.0, "rx": 0.0, "ry": 0.0, "rz": 0.0},
                "payload_kg": 0.5,
                "health_score": 92,
            },
        ]

        emit("robotics:fleet_status", {
            "arms": arms,
            "total_count": len(arms),
            "active_count": sum(1 for a in arms if a["status"] == "active"),
            "timestamp": time.time(),
        })

    @socketio.on("robotics:send_command")
    def handle_send_command(data):
        """Send immediate command to robotic arm."""
        arm_id = data.get("arm_id")
        command = data.get("command")

        if not arm_id or not command:
            emit("robotics:error", {"error": "Missing arm_id or command"})
            return

        # Acknowledge command
        emit("robotics:command_ack", {
            "arm_id": arm_id,
            "command": command,
            "status": "acknowledged",
            "timestamp": time.time(),
        })

        # Simulate command execution
        import threading

        def execute_command():
            time.sleep(0.5)
            socketio.emit("robot:command_complete", {
                "arm_id": arm_id,
                "command": command,
                "status": "completed",
                "timestamp": time.time(),
            }, room="robotics")

        threading.Thread(target=execute_command, daemon=True).start()


# ============================================================
# Phase 8: Unity Digital Twin WebSocket Events
# ============================================================


def emit_unity_scene_update(scene_name, equipment_updates, delta_only=True):
    """Emit Unity 3D scene update for equipment state changes."""
    try:
        from app import socketio

        socketio.emit(
            "unity:scene_update",
            {
                "scene_name": scene_name,
                "equipment_updates": equipment_updates,
                "delta_only": delta_only,
                "timestamp": time.time(),
            },
            room="unity",
        )
    except Exception:
        pass


def emit_unity_equipment_state(equipment_id, state, position=None, rotation=None, animation=None):
    """Emit single equipment state change for Unity visualization."""
    try:
        from app import socketio

        socketio.emit(
            "unity:equipment_state",
            {
                "equipment_id": equipment_id,
                "state": state,
                "position": position,
                "rotation": rotation,
                "animation": animation,
                "timestamp": time.time(),
            },
            room="unity",
        )
    except Exception:
        pass


def emit_unity_highlight(equipment_id, highlight_type, color=None, duration_ms=None):
    """Emit equipment highlight command for Unity (alerts, selection, etc.)."""
    try:
        from app import socketio

        socketio.emit(
            "unity:highlight",
            {
                "equipment_id": equipment_id,
                "highlight_type": highlight_type,
                "color": color,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            },
            room="unity",
        )
    except Exception:
        pass


def emit_unity_camera_command(command, target=None, position=None, rotation=None, duration_ms=None):
    """Emit camera command for Unity (focus, pan, zoom, preset)."""
    try:
        from app import socketio

        socketio.emit(
            "unity:camera_command",
            {
                "command": command,
                "target": target,
                "position": position,
                "rotation": rotation,
                "duration_ms": duration_ms,
                "timestamp": time.time(),
            },
            room="unity",
        )
    except Exception:
        pass


def emit_unity_heatmap_update(heatmap_type, data_points, color_scale=None):
    """Emit heatmap data update for Unity visualization."""
    try:
        from app import socketio

        socketio.emit(
            "unity:heatmap_update",
            {
                "heatmap_type": heatmap_type,
                "data_points": data_points,
                "color_scale": color_scale,
                "timestamp": time.time(),
            },
            room="unity",
        )
    except Exception:
        pass


def emit_unity_annotation(equipment_id, annotation_type, content, position_offset=None):
    """Emit 3D annotation/label for Unity overlay."""
    try:
        from app import socketio

        socketio.emit(
            "unity:annotation",
            {
                "equipment_id": equipment_id,
                "annotation_type": annotation_type,
                "content": content,
                "position_offset": position_offset,
                "timestamp": time.time(),
            },
            room="unity",
        )
    except Exception:
        pass


def register_unity_events(socketio):
    """Register Unity Digital Twin WebSocket event handlers."""

    if not SOCKETIO_AVAILABLE or socketio is None:
        return

    @socketio.on("unity:subscribe")
    def handle_unity_subscribe():
        """Subscribe to Unity digital twin updates."""
        join_room("unity")
        emit("unity:subscribed", {"status": "ok", "room": "unity"})

    @socketio.on("unity:unsubscribe")
    def handle_unity_unsubscribe():
        """Unsubscribe from Unity updates."""
        leave_room("unity")
        emit("unity:unsubscribed", {"status": "ok"})

    @socketio.on("unity:get_full_scene")
    def handle_get_full_scene(data):
        """Get full scene state for Unity initialization."""
        scene_name = data.get("scene_name", "FactoryFloor")

        # Simulated full scene state
        scene_data = {
            "scene_name": scene_name,
            "equipment": [
                {
                    "equipment_id": "EQ-PRINT-001",
                    "name": "Prusa MK3S+ #1",
                    "type": "3d_printer",
                    "model_asset": "Models/Prusa_MK3S",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                    "state": "printing",
                    "progress": 45.5,
                    "oee": 85.2,
                },
                {
                    "equipment_id": "EQ-PRINT-002",
                    "name": "Bambu A1 #1",
                    "type": "3d_printer",
                    "model_asset": "Models/Bambu_A1",
                    "position": {"x": 2.0, "y": 0.0, "z": 0.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                    "state": "idle",
                    "progress": 0.0,
                    "oee": 78.5,
                },
                {
                    "equipment_id": "EQ-CNC-001",
                    "name": "GRBL Mill",
                    "type": "cnc_mill",
                    "model_asset": "Models/GRBL_Mill",
                    "position": {"x": 4.0, "y": 0.0, "z": 0.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    "scale": {"x": 1.0, "y": 1.0, "z": 1.0},
                    "state": "maintenance",
                    "progress": 0.0,
                    "oee": 0.0,
                },
            ],
            "camera_presets": [
                {"name": "Overview", "position": {"x": 5.0, "y": 10.0, "z": -10.0}, "target": {"x": 2.0, "y": 0.0, "z": 0.0}},
                {"name": "PrinterRow", "position": {"x": 1.0, "y": 2.0, "z": -3.0}, "target": {"x": 1.0, "y": 0.5, "z": 0.0}},
            ],
            "timestamp": time.time(),
        }

        emit("unity:full_scene", scene_data)

    @socketio.on("unity:request_delta")
    def handle_request_delta(data):
        """Request delta updates since a timestamp."""
        since_timestamp = data.get("since_timestamp", 0)

        # Return any equipment changes since the timestamp
        emit("unity:scene_delta", {
            "since_timestamp": since_timestamp,
            "equipment_updates": [],
            "timestamp": time.time(),
        })

    @socketio.on("unity:focus_equipment")
    def handle_focus_equipment(data):
        """Request camera focus on specific equipment."""
        equipment_id = data.get("equipment_id")

        if equipment_id:
            emit_unity_camera_command(
                command="focus",
                target=equipment_id,
                duration_ms=1000
            )

    @socketio.on("unity:set_visualization_mode")
    def handle_set_visualization_mode(data):
        """Set visualization mode (normal, oee_heatmap, defect_overlay, etc.)."""
        mode = data.get("mode", "normal")

        socketio.emit(
            "unity:visualization_mode_changed",
            {
                "mode": mode,
                "timestamp": time.time(),
            },
            room="unity",
        )


# ============================================================
# Phase 9: Supply Chain Twin WebSocket Events
# ============================================================


def emit_supply_chain_disruption(disruption_id, node_id, disruption_type, severity, impact_summary):
    """Emit supply chain disruption alert."""
    try:
        from app import socketio

        socketio.emit(
            "supply_chain:disruption",
            {
                "disruption_id": disruption_id,
                "node_id": node_id,
                "disruption_type": disruption_type,
                "severity": severity,
                "impact_summary": impact_summary,
                "timestamp": time.time(),
            },
            room="supply_chain",
        )
    except Exception:
        pass


def emit_supply_chain_flow_update(edge_id, source_node, target_node, material_type, flow_rate, eta_hours=None):
    """Emit material flow update on supply chain edge."""
    try:
        from app import socketio

        socketio.emit(
            "supply_chain:flow_update",
            {
                "edge_id": edge_id,
                "source_node": source_node,
                "target_node": target_node,
                "material_type": material_type,
                "flow_rate": flow_rate,
                "eta_hours": eta_hours,
                "timestamp": time.time(),
            },
            room="supply_chain",
        )
    except Exception:
        pass


def emit_supply_chain_inventory_update(node_id, material_type, quantity, reorder_point, days_of_supply):
    """Emit inventory level update at supply chain node."""
    try:
        from app import socketio

        socketio.emit(
            "supply_chain:inventory_update",
            {
                "node_id": node_id,
                "material_type": material_type,
                "quantity": quantity,
                "reorder_point": reorder_point,
                "days_of_supply": days_of_supply,
                "alert": quantity <= reorder_point,
                "timestamp": time.time(),
            },
            room="supply_chain",
        )
    except Exception:
        pass


def emit_supply_chain_risk_update(node_id, risk_score, risk_factors, recommendations=None):
    """Emit supply chain risk score update."""
    try:
        from app import socketio

        socketio.emit(
            "supply_chain:risk_update",
            {
                "node_id": node_id,
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "recommendations": recommendations,
                "timestamp": time.time(),
            },
            room="supply_chain",
        )
    except Exception:
        pass


def emit_supply_chain_order_update(order_id, supplier_id, status, expected_delivery=None, items=None):
    """Emit purchase order status update."""
    try:
        from app import socketio

        socketio.emit(
            "supply_chain:order_update",
            {
                "order_id": order_id,
                "supplier_id": supplier_id,
                "status": status,
                "expected_delivery": expected_delivery,
                "items": items,
                "timestamp": time.time(),
            },
            room="supply_chain",
        )
    except Exception:
        pass


def emit_supply_chain_simulation_result(simulation_id, scenario_name, results_summary, detailed_results=None):
    """Emit supply chain simulation completion results."""
    try:
        from app import socketio

        socketio.emit(
            "supply_chain:simulation_result",
            {
                "simulation_id": simulation_id,
                "scenario_name": scenario_name,
                "results_summary": results_summary,
                "detailed_results": detailed_results,
                "timestamp": time.time(),
            },
            room="supply_chain",
        )
    except Exception:
        pass


def register_supply_chain_events(socketio):
    """Register Supply Chain Twin WebSocket event handlers."""

    if not SOCKETIO_AVAILABLE or socketio is None:
        return

    @socketio.on("supply_chain:subscribe")
    def handle_supply_chain_subscribe():
        """Subscribe to supply chain twin updates."""
        join_room("supply_chain")
        emit("supply_chain:subscribed", {"status": "ok", "room": "supply_chain"})

    @socketio.on("supply_chain:unsubscribe")
    def handle_supply_chain_unsubscribe():
        """Unsubscribe from supply chain updates."""
        leave_room("supply_chain")
        emit("supply_chain:unsubscribed", {"status": "ok"})

    @socketio.on("supply_chain:get_network")
    def handle_get_network():
        """Get full supply chain network topology."""
        network = {
            "nodes": [
                {
                    "node_id": "SUP-001",
                    "name": "Plastic Pellet Supplier",
                    "type": "supplier",
                    "location": {"lat": 40.7128, "lng": -74.0060},
                    "risk_score": 15,
                    "status": "active",
                },
                {
                    "node_id": "WH-001",
                    "name": "Raw Materials Warehouse",
                    "type": "warehouse",
                    "location": {"lat": 41.8781, "lng": -87.6298},
                    "risk_score": 8,
                    "status": "active",
                },
                {
                    "node_id": "FAC-001",
                    "name": "LEGO Production Facility",
                    "type": "factory",
                    "location": {"lat": 42.3601, "lng": -71.0589},
                    "risk_score": 5,
                    "status": "active",
                },
                {
                    "node_id": "DC-001",
                    "name": "Distribution Center East",
                    "type": "distribution",
                    "location": {"lat": 39.9526, "lng": -75.1652},
                    "risk_score": 10,
                    "status": "active",
                },
            ],
            "edges": [
                {
                    "edge_id": "E-001",
                    "source": "SUP-001",
                    "target": "WH-001",
                    "transport_mode": "truck",
                    "lead_time_days": 3,
                    "current_flow": 5000,
                },
                {
                    "edge_id": "E-002",
                    "source": "WH-001",
                    "target": "FAC-001",
                    "transport_mode": "truck",
                    "lead_time_days": 1,
                    "current_flow": 4500,
                },
                {
                    "edge_id": "E-003",
                    "source": "FAC-001",
                    "target": "DC-001",
                    "transport_mode": "truck",
                    "lead_time_days": 2,
                    "current_flow": 10000,
                },
            ],
            "timestamp": time.time(),
        }

        emit("supply_chain:network", network)

    @socketio.on("supply_chain:get_inventory_status")
    def handle_get_inventory_status():
        """Get inventory status across all nodes."""
        inventory = [
            {
                "node_id": "WH-001",
                "materials": [
                    {"type": "ABS_RED", "quantity": 50000, "unit": "kg", "reorder_point": 20000, "days_of_supply": 25},
                    {"type": "ABS_BLUE", "quantity": 45000, "unit": "kg", "reorder_point": 20000, "days_of_supply": 22},
                    {"type": "ABS_YELLOW", "quantity": 18000, "unit": "kg", "reorder_point": 20000, "days_of_supply": 9},
                ],
            },
            {
                "node_id": "FAC-001",
                "materials": [
                    {"type": "ABS_RED", "quantity": 5000, "unit": "kg", "reorder_point": 2000, "days_of_supply": 5},
                    {"type": "ABS_BLUE", "quantity": 4000, "unit": "kg", "reorder_point": 2000, "days_of_supply": 4},
                    {"type": "ABS_YELLOW", "quantity": 1500, "unit": "kg", "reorder_point": 2000, "days_of_supply": 1.5},
                ],
            },
        ]

        emit("supply_chain:inventory_status", {
            "inventory": inventory,
            "alerts": [
                {"node_id": "WH-001", "material": "ABS_YELLOW", "alert_type": "low_stock", "severity": "warning"},
                {"node_id": "FAC-001", "material": "ABS_YELLOW", "alert_type": "critical_low", "severity": "critical"},
            ],
            "timestamp": time.time(),
        })

    @socketio.on("supply_chain:simulate_disruption")
    def handle_simulate_disruption(data):
        """Trigger supply chain disruption simulation."""
        node_id = data.get("node_id")
        disruption_type = data.get("disruption_type", "supplier_shutdown")
        duration_days = data.get("duration_days", 7)

        # Acknowledge simulation start
        emit("supply_chain:simulation_started", {
            "node_id": node_id,
            "disruption_type": disruption_type,
            "duration_days": duration_days,
            "status": "running",
            "timestamp": time.time(),
        })

        # Simulate async completion
        import threading

        def run_simulation():
            time.sleep(2)  # Simulate processing

            results = {
                "affected_nodes": ["WH-001", "FAC-001", "DC-001"],
                "production_impact_percent": 35,
                "revenue_impact_usd": 150000,
                "recovery_time_days": duration_days + 5,
                "mitigation_options": [
                    {"option": "Secondary supplier activation", "cost_usd": 25000, "lead_time_days": 3},
                    {"option": "Air freight expedite", "cost_usd": 50000, "lead_time_days": 1},
                    {"option": "Inventory reallocation", "cost_usd": 5000, "lead_time_days": 2},
                ],
            }

            socketio.emit("supply_chain:simulation_result", {
                "simulation_id": f"SIM-{int(time.time())}",
                "scenario_name": f"{disruption_type} at {node_id}",
                "results_summary": results,
                "status": "completed",
                "timestamp": time.time(),
            }, room="supply_chain")

        threading.Thread(target=run_simulation, daemon=True).start()


# ============================================================
# V8: Unified Command Center WebSocket Events
# ============================================================


def emit_command_center_status(status_summary):
    """Emit complete system status update to command center."""
    try:
        from app import socketio

        socketio.emit(
            "command_center:status",
            {
                "summary": status_summary,
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def emit_kpi_update(kpi_name, value, target, unit, trend=None, category=None):
    """Emit single KPI update."""
    try:
        from app import socketio

        socketio.emit(
            "command_center:kpi_update",
            {
                "kpi_name": kpi_name,
                "value": value,
                "target": target,
                "unit": unit,
                "trend": trend,
                "category": category,
                "status": "on_target" if value >= target else "below_target",
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def emit_kpi_dashboard(dashboard_data):
    """Emit complete KPI dashboard update."""
    try:
        from app import socketio

        socketio.emit(
            "command_center:kpi_dashboard",
            {
                "dashboard": dashboard_data,
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def emit_alert_created(alert):
    """Emit new alert notification."""
    try:
        from app import socketio

        alert_data = alert.to_dict() if hasattr(alert, 'to_dict') else alert
        socketio.emit(
            "command_center:alert_created",
            {
                "alert": alert_data,
                "timestamp": time.time(),
            },
            room="command_center",
        )

        # Also emit to severity-specific rooms for priority routing
        severity = alert_data.get('severity', 'info')
        if severity in ('critical', 'high'):
            socketio.emit(
                "command_center:priority_alert",
                {
                    "alert": alert_data,
                    "timestamp": time.time(),
                },
                room="priority_alerts",
            )
    except Exception:
        pass


def emit_alert_updated(alert_id, status, updated_by=None, note=None):
    """Emit alert status change."""
    try:
        from app import socketio

        socketio.emit(
            "command_center:alert_updated",
            {
                "alert_id": alert_id,
                "status": status,
                "updated_by": updated_by,
                "note": note,
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def emit_alert_summary(summary):
    """Emit alert summary statistics."""
    try:
        from app import socketio

        summary_data = summary.to_dict() if hasattr(summary, 'to_dict') else summary
        socketio.emit(
            "command_center:alert_summary",
            {
                "summary": summary_data,
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def emit_action_created(action):
    """Emit new action requiring approval."""
    try:
        from app import socketio

        action_data = action.to_dict() if hasattr(action, 'to_dict') else action
        socketio.emit(
            "command_center:action_created",
            {
                "action": action_data,
                "timestamp": time.time(),
            },
            room="command_center",
        )

        # Emit to action console specific room
        socketio.emit(
            "action_console:new_action",
            {
                "action": action_data,
                "timestamp": time.time(),
            },
            room="action_console",
        )
    except Exception:
        pass


def emit_action_status_change(action_id, old_status, new_status, updated_by=None):
    """Emit action status change notification."""
    try:
        from app import socketio

        socketio.emit(
            "command_center:action_status_change",
            {
                "action_id": action_id,
                "old_status": old_status,
                "new_status": new_status,
                "updated_by": updated_by,
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def emit_action_execution_progress(action_id, step, total_steps, message, percent):
    """Emit action execution progress."""
    try:
        from app import socketio

        socketio.emit(
            "command_center:action_progress",
            {
                "action_id": action_id,
                "step": step,
                "total_steps": total_steps,
                "message": message,
                "percent": percent,
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def emit_cosim_started(simulation_id, config):
    """Emit co-simulation started notification."""
    try:
        from app import socketio

        config_data = config.to_dict() if hasattr(config, 'to_dict') else config
        socketio.emit(
            "command_center:cosim_started",
            {
                "simulation_id": simulation_id,
                "config": config_data,
                "status": "running",
                "timestamp": time.time(),
            },
            room="command_center",
        )

        socketio.emit(
            "cosimulation:started",
            {
                "simulation_id": simulation_id,
                "config": config_data,
                "timestamp": time.time(),
            },
            room="cosimulation",
        )
    except Exception:
        pass


def emit_cosim_progress(simulation_id, simulated_time, wall_time, metrics=None):
    """Emit co-simulation progress update."""
    try:
        from app import socketio

        socketio.emit(
            "cosimulation:progress",
            {
                "simulation_id": simulation_id,
                "simulated_time": simulated_time,
                "wall_time": wall_time,
                "metrics": metrics,
                "timestamp": time.time(),
            },
            room="cosimulation",
        )
    except Exception:
        pass


def emit_cosim_completed(simulation_id, result):
    """Emit co-simulation completion notification."""
    try:
        from app import socketio

        result_data = result.to_dict() if hasattr(result, 'to_dict') else result
        socketio.emit(
            "command_center:cosim_completed",
            {
                "simulation_id": simulation_id,
                "result": result_data,
                "status": "completed",
                "timestamp": time.time(),
            },
            room="command_center",
        )

        socketio.emit(
            "cosimulation:completed",
            {
                "simulation_id": simulation_id,
                "result": result_data,
                "timestamp": time.time(),
            },
            room="cosimulation",
        )
    except Exception:
        pass


def emit_decision_made(decision):
    """Emit decision engine result."""
    try:
        from app import socketio

        decision_data = decision.to_dict() if hasattr(decision, 'to_dict') else decision
        socketio.emit(
            "command_center:decision_made",
            {
                "decision": decision_data,
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def emit_event_correlated(correlated_event):
    """Emit event correlation result."""
    try:
        from app import socketio

        event_data = correlated_event.to_dict() if hasattr(correlated_event, 'to_dict') else correlated_event
        socketio.emit(
            "command_center:event_correlated",
            {
                "correlated_event": event_data,
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def emit_subsystem_health_change(subsystem_id, old_status, new_status, details=None):
    """Emit subsystem health status change."""
    try:
        from app import socketio

        socketio.emit(
            "command_center:subsystem_health_change",
            {
                "subsystem_id": subsystem_id,
                "old_status": old_status,
                "new_status": new_status,
                "details": details,
                "timestamp": time.time(),
            },
            room="command_center",
        )
    except Exception:
        pass


def register_command_center_events(socketio):
    """Register V8 Command Center WebSocket event handlers."""

    if not SOCKETIO_AVAILABLE or socketio is None:
        return

    @socketio.on("command_center:subscribe")
    def handle_command_center_subscribe():
        """Subscribe to command center updates."""
        join_room("command_center")
        emit("command_center:subscribed", {"status": "ok", "room": "command_center"})

    @socketio.on("command_center:unsubscribe")
    def handle_command_center_unsubscribe():
        """Unsubscribe from command center updates."""
        leave_room("command_center")
        emit("command_center:unsubscribed", {"status": "ok"})

    @socketio.on("priority_alerts:subscribe")
    def handle_priority_alerts_subscribe():
        """Subscribe to priority alerts only."""
        join_room("priority_alerts")
        emit("priority_alerts:subscribed", {"status": "ok"})

    @socketio.on("action_console:subscribe")
    def handle_action_console_subscribe():
        """Subscribe to action console updates."""
        join_room("action_console")
        emit("action_console:subscribed", {"status": "ok"})

    @socketio.on("cosimulation:subscribe")
    def handle_cosimulation_subscribe():
        """Subscribe to co-simulation updates."""
        join_room("cosimulation")
        emit("cosimulation:subscribed", {"status": "ok"})

    @socketio.on("command_center:get_status")
    def handle_get_status():
        """Get current system status."""
        try:
            from dashboard.services.command_center import get_health_service
            import asyncio

            health_service = get_health_service()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                summary = loop.run_until_complete(health_service.check_all())
            finally:
                loop.close()

            emit("command_center:status", {
                "summary": summary.to_dict(),
                "timestamp": time.time(),
            })
        except Exception as e:
            emit("command_center:error", {"error": str(e)})

    @socketio.on("command_center:get_kpis")
    def handle_get_kpis():
        """Get current KPI dashboard."""
        try:
            from dashboard.services.command_center import get_kpi_aggregator

            aggregator = get_kpi_aggregator()
            dashboard = aggregator.get_dashboard()

            emit("command_center:kpi_dashboard", {
                "dashboard": dashboard.to_dict(),
                "timestamp": time.time(),
            })
        except Exception as e:
            emit("command_center:error", {"error": str(e)})

    @socketio.on("command_center:get_alerts")
    def handle_get_alerts(data=None):
        """Get active alerts."""
        data = data or {}
        try:
            from dashboard.services.command_center import get_alert_manager

            limit = data.get('limit', 50)
            manager = get_alert_manager()
            alerts = manager.get_active_alerts(limit=limit)
            summary = manager.get_summary()

            emit("command_center:alerts", {
                "alerts": [a.to_dict() for a in alerts],
                "summary": summary.to_dict(),
                "timestamp": time.time(),
            })
        except Exception as e:
            emit("command_center:error", {"error": str(e)})

    @socketio.on("command_center:acknowledge_alert")
    def handle_acknowledge_alert(data):
        """Acknowledge an alert."""
        try:
            from dashboard.services.command_center import get_alert_manager

            alert_id = data.get('alert_id')
            user = data.get('user', 'anonymous')
            note = data.get('note', '')

            manager = get_alert_manager()
            alert = manager.acknowledge_alert(alert_id, user, note)

            if alert:
                emit("command_center:alert_acknowledged", {
                    "alert": alert.to_dict(),
                    "timestamp": time.time(),
                })

                # Broadcast to all subscribers
                socketio.emit("command_center:alert_updated", {
                    "alert_id": alert_id,
                    "status": "acknowledged",
                    "updated_by": user,
                    "timestamp": time.time(),
                }, room="command_center")
            else:
                emit("command_center:error", {"error": "Alert not found"})
        except Exception as e:
            emit("command_center:error", {"error": str(e)})

    @socketio.on("command_center:get_actions")
    def handle_get_actions():
        """Get pending actions."""
        try:
            from dashboard.services.command_center import get_action_console

            console = get_action_console()
            pending = console.get_pending_actions()
            stats = console.get_queue_stats()

            emit("command_center:actions", {
                "pending": [a.to_dict() for a in pending],
                "stats": stats.to_dict(),
                "timestamp": time.time(),
            })
        except Exception as e:
            emit("command_center:error", {"error": str(e)})

    @socketio.on("command_center:approve_action")
    def handle_approve_action(data):
        """Approve an action."""
        try:
            from dashboard.services.command_center import get_action_console

            action_id = data.get('action_id')
            user = data.get('user', 'anonymous')
            note = data.get('note', '')

            console = get_action_console()
            action = console.approve_action(action_id, user, note)

            if action:
                emit("command_center:action_approved", {
                    "action": action.to_dict(),
                    "timestamp": time.time(),
                })

                # Broadcast to all subscribers
                socketio.emit("command_center:action_status_change", {
                    "action_id": action_id,
                    "old_status": "pending_approval",
                    "new_status": "approved",
                    "updated_by": user,
                    "timestamp": time.time(),
                }, room="command_center")
            else:
                emit("command_center:error", {"error": "Action not found"})
        except Exception as e:
            emit("command_center:error", {"error": str(e)})

    @socketio.on("command_center:reject_action")
    def handle_reject_action(data):
        """Reject an action."""
        try:
            from dashboard.services.command_center import get_action_console

            action_id = data.get('action_id')
            user = data.get('user', 'anonymous')
            reason = data.get('reason', '')

            console = get_action_console()
            action = console.reject_action(action_id, user, reason)

            if action:
                emit("command_center:action_rejected", {
                    "action": action.to_dict(),
                    "timestamp": time.time(),
                })

                socketio.emit("command_center:action_status_change", {
                    "action_id": action_id,
                    "old_status": "pending_approval",
                    "new_status": "rejected",
                    "updated_by": user,
                    "timestamp": time.time(),
                }, room="command_center")
            else:
                emit("command_center:error", {"error": "Action not found"})
        except Exception as e:
            emit("command_center:error", {"error": str(e)})

    @socketio.on("cosimulation:run")
    def handle_cosim_run(data):
        """Start a co-simulation."""
        try:
            from dashboard.services.cosimulation import (
                get_cosim_coordinator,
                SimulationConfig,
                SimulationMode,
                SimulationEngine
            )
            from datetime import datetime, timedelta
            import asyncio

            coordinator = get_cosim_coordinator()

            config = SimulationConfig(
                mode=SimulationMode(data.get('mode', 'accelerated')),
                engines=[SimulationEngine(e) for e in data.get('engines', ['des'])],
                start_time=datetime.fromisoformat(data.get('start_time', datetime.now().isoformat())),
                end_time=datetime.fromisoformat(data.get('end_time', (datetime.now() + timedelta(hours=8)).isoformat())),
                time_step_seconds=data.get('time_step', 60.0),
                speedup_factor=data.get('speedup', 100.0),
                parameters=data.get('parameters', {})
            )

            # Emit start notification
            emit_cosim_started(f"COSIM-{int(time.time())}", config)

            # Run async simulation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coordinator.run_simulation(config))
            finally:
                loop.close()

            emit("cosimulation:completed", {
                "result": result.to_dict(),
                "timestamp": time.time(),
            })
        except Exception as e:
            emit("cosimulation:error", {"error": str(e)})

    @socketio.on("cosimulation:stop")
    def handle_cosim_stop(data):
        """Stop a running simulation."""
        try:
            from dashboard.services.cosimulation import get_cosim_coordinator

            simulation_id = data.get('simulation_id')
            coordinator = get_cosim_coordinator()
            coordinator.stop_simulation(simulation_id)

            emit("cosimulation:stopped", {
                "simulation_id": simulation_id,
                "timestamp": time.time(),
            })
        except Exception as e:
            emit("cosimulation:error", {"error": str(e)})
