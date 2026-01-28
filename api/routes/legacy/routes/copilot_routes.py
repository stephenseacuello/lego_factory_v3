"""
API Routes for Real-time Copilot Service.

Provides REST and WebSocket endpoints for:
- Chat interface with copilot
- Machine status queries
- Notification management
- Shift management
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from functools import wraps
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

copilot_bp = Blueprint("copilot", __name__, url_prefix="/api/copilot")


def get_copilot_service():
    """Get the copilot service instance."""
    from services.copilot import get_copilot
    return get_copilot()


def run_async(coro):
    """Run an async coroutine in the current thread."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# =============================================================================
# Chat Endpoints
# =============================================================================

@copilot_bp.route("/chat", methods=["POST"])
def chat():
    """
    Send a message to the copilot.

    Request body:
        {
            "message": "What's the status of the mill?",
            "session_id": "optional-session-id",
            "machine_id": "optional-machine-context"
        }

    Response:
        {
            "response": "The TinyG mill is currently idle at X=0, Y=0, Z=0...",
            "session_id": "session-123",
            "timestamp": "2024-01-15T10:30:00Z"
        }
    """
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "Message is required"}), 400

        message = data["message"]
        session_id = data.get("session_id", f"session-{datetime.now().timestamp()}")
        machine_id = data.get("machine_id")

        copilot = get_copilot_service()
        response = run_async(copilot.chat(session_id, message, machine_id))

        return jsonify({
            "response": response,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        })

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 500


@copilot_bp.route("/chat/history/<session_id>", methods=["GET"])
def get_chat_history(session_id):
    """
    Get chat history for a session.

    Response:
        {
            "session_id": "session-123",
            "messages": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ],
            "machine_id": "tinyg",
            "started_at": "2024-01-15T10:00:00Z"
        }
    """
    try:
        copilot = get_copilot_service()

        if session_id not in copilot._conversations:
            return jsonify({"error": "Session not found"}), 404

        ctx = copilot._conversations[session_id]

        return jsonify({
            "session_id": session_id,
            "messages": ctx.messages,
            "machine_id": ctx.machine_id,
            "started_at": ctx.started_at.isoformat(),
            "last_activity": ctx.last_activity.isoformat(),
            "mode": ctx.mode.value,
        })

    except Exception as e:
        logger.error(f"History error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Machine Context Endpoints
# =============================================================================

@copilot_bp.route("/machines", methods=["GET"])
def get_machines():
    """
    Get all machine contexts.

    Response:
        {
            "machines": [
                {
                    "machine_id": "tinyg",
                    "status": "idle",
                    "position": {"x": 0, "y": 0, "z": 0},
                    ...
                }
            ]
        }
    """
    try:
        copilot = get_copilot_service()
        machines = copilot.get_all_machines()

        return jsonify({
            "machines": [
                {
                    "machine_id": m.machine_id,
                    "status": m.status,
                    "position": m.position,
                    "current_job": m.current_job,
                    "job_progress": m.job_progress,
                    "alarms": m.alarms,
                    "last_update": m.last_update.isoformat(),
                }
                for m in machines.values()
            ]
        })

    except Exception as e:
        logger.error(f"Get machines error: {e}")
        return jsonify({"error": str(e)}), 500


@copilot_bp.route("/machines/<machine_id>", methods=["GET"])
def get_machine(machine_id):
    """Get context for a specific machine."""
    try:
        copilot = get_copilot_service()
        machine = copilot.get_machine_context(machine_id)

        if not machine:
            return jsonify({"error": "Machine not found"}), 404

        return jsonify({
            "machine_id": machine.machine_id,
            "status": machine.status,
            "position": machine.position,
            "current_job": machine.current_job,
            "job_progress": machine.job_progress,
            "alarms": machine.alarms,
            "sensor_data": machine.sensor_data,
            "metrics": machine.metrics,
            "last_update": machine.last_update.isoformat(),
        })

    except Exception as e:
        logger.error(f"Get machine error: {e}")
        return jsonify({"error": str(e)}), 500


@copilot_bp.route("/machines/<machine_id>/context", methods=["POST"])
def update_machine_context(machine_id):
    """
    Update context for a machine.

    Request body:
        {
            "status": "running",
            "position": {"x": 10.5, "y": 20.3, "z": -5.0},
            "job": "bracket-001",
            "progress": 45.5,
            "sensor_data": {...}
        }
    """
    try:
        data = request.get_json()
        copilot = get_copilot_service()

        copilot.update_machine_context(
            machine_id=machine_id,
            status=data.get("status"),
            position=data.get("position"),
            job=data.get("job"),
            progress=data.get("progress"),
            alarms=data.get("alarms"),
            sensor_data=data.get("sensor_data"),
        )

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Update context error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Event Endpoints
# =============================================================================

@copilot_bp.route("/events", methods=["GET"])
def get_events():
    """
    Get recent events.

    Query params:
        - limit: Maximum number of events (default: 50)
        - machine_id: Filter by machine
        - severity: Filter by severity (low, medium, high, critical)

    Response:
        {
            "events": [
                {
                    "id": "event-123",
                    "type": "ALARM",
                    "machine_id": "tinyg",
                    "message": "...",
                    "timestamp": "..."
                }
            ]
        }
    """
    try:
        limit = request.args.get("limit", 50, type=int)
        machine_id = request.args.get("machine_id")
        severity = request.args.get("severity")

        copilot = get_copilot_service()
        events = copilot.event_processor.get_recent_events(
            limit=limit,
            machine_id=machine_id,
            severity=severity,
        )

        return jsonify({
            "events": [
                {
                    "id": e.id,
                    "type": e.event_type.value,
                    "machine_id": e.machine_id,
                    "severity": e.severity,
                    "message": e.message,
                    "data": e.data,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in events
            ]
        })

    except Exception as e:
        logger.error(f"Get events error: {e}")
        return jsonify({"error": str(e)}), 500


@copilot_bp.route("/events", methods=["POST"])
def create_event():
    """
    Create a manual event.

    Request body:
        {
            "type": "ALARM",
            "machine_id": "tinyg",
            "severity": "high",
            "message": "Manual alarm triggered",
            "data": {...}
        }
    """
    try:
        data = request.get_json()

        from services.copilot import MachineEvent, EventType

        event = MachineEvent(
            id=f"manual-{datetime.now().timestamp()}",
            event_type=EventType(data.get("type", "STATUS_CHANGE")),
            machine_id=data.get("machine_id", "unknown"),
            severity=data.get("severity", "medium"),
            message=data.get("message", "Manual event"),
            data=data.get("data", {}),
        )

        copilot = get_copilot_service()
        copilot.event_processor.process_event(event)

        return jsonify({
            "success": True,
            "event_id": event.id,
        })

    except Exception as e:
        logger.error(f"Create event error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Notification Endpoints
# =============================================================================

@copilot_bp.route("/notifications/history", methods=["GET"])
def get_notification_history():
    """
    Get notification history.

    Query params:
        - limit: Maximum number (default: 50)
        - priority: Filter by priority

    Response:
        {
            "notifications": [...]
        }
    """
    try:
        limit = request.args.get("limit", 50, type=int)
        priority = request.args.get("priority")

        copilot = get_copilot_service()

        from services.copilot import NotificationPriority

        priority_enum = None
        if priority:
            priority_enum = NotificationPriority(priority)

        history = copilot.notification_manager.get_history(
            limit=limit,
            priority=priority_enum,
        )

        return jsonify({"notifications": history})

    except Exception as e:
        logger.error(f"Get notifications error: {e}")
        return jsonify({"error": str(e)}), 500


@copilot_bp.route("/notifications/send", methods=["POST"])
def send_notification():
    """
    Send a notification.

    Request body:
        {
            "title": "Test Alert",
            "message": "This is a test notification",
            "priority": "medium",
            "channels": ["websocket", "slack"],
            "machine_id": "tinyg"
        }
    """
    try:
        data = request.get_json()

        if not data.get("title") or not data.get("message"):
            return jsonify({"error": "Title and message are required"}), 400

        copilot = get_copilot_service()

        notification = copilot.notification_manager.create_notification(
            title=data["title"],
            message=data["message"],
            priority=data.get("priority", "medium"),
            channels=data.get("channels", ["websocket"]),
            machine_id=data.get("machine_id"),
            data=data.get("data"),
        )

        result = run_async(copilot.notification_manager.send(notification))

        return jsonify({
            "success": True,
            "notification_id": notification.id,
            "result": result,
        })

    except Exception as e:
        logger.error(f"Send notification error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Shift Endpoints
# =============================================================================

@copilot_bp.route("/shift/current", methods=["GET"])
def get_current_shift():
    """
    Get information about the current shift.

    Response:
        {
            "shift_name": "Day Shift",
            "shift_type": "day",
            "operators": [...],
            "time_remaining": "2:30:00",
            "metrics": {...}
        }
    """
    try:
        from services.copilot import ShiftSchedule, ShiftAwareness

        schedule = ShiftSchedule()
        awareness = ShiftAwareness(schedule)

        current = schedule.get_current_shift()
        if not current:
            return jsonify({
                "shift_name": None,
                "message": "No active shift",
            })

        operators = schedule.get_current_operators()
        remaining = schedule.time_until_shift_end()

        return jsonify({
            "shift_name": current.name,
            "shift_type": current.shift_type.value,
            "start_time": current.start_time.strftime("%H:%M"),
            "end_time": current.end_time.strftime("%H:%M"),
            "operators": [
                {"id": op.id, "name": op.name}
                for op in operators
            ],
            "time_remaining": str(remaining) if remaining else None,
            "context": awareness.get_notification_context(),
        })

    except Exception as e:
        logger.error(f"Get shift error: {e}")
        return jsonify({"error": str(e)}), 500


@copilot_bp.route("/shift/schedule", methods=["GET"])
def get_shift_schedule():
    """
    Get the weekly shift schedule.

    Query params:
        - start_date: Week start date (YYYY-MM-DD)

    Response:
        {
            "schedule": [...]
        }
    """
    try:
        from services.copilot import ShiftSchedule

        start_date = request.args.get("start_date")
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start = None

        schedule = ShiftSchedule()
        weekly = schedule.get_schedule_for_week(start)

        return jsonify({"schedule": weekly})

    except Exception as e:
        logger.error(f"Get schedule error: {e}")
        return jsonify({"error": str(e)}), 500


@copilot_bp.route("/shift/handoff", methods=["GET"])
def get_shift_handoff():
    """
    Generate a shift handoff report.

    Response:
        {
            "report": {...},
            "formatted": "=== Shift Handoff Report ===..."
        }
    """
    try:
        copilot = get_copilot_service()
        report = run_async(copilot.generate_shift_summary())

        from services.copilot import ShiftAwareness

        awareness = ShiftAwareness()
        formatted = awareness.format_handoff_message(report)

        return jsonify({
            "report": report,
            "formatted": formatted,
        })

    except Exception as e:
        logger.error(f"Handoff error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Diagnosis Endpoints
# =============================================================================

@copilot_bp.route("/diagnose/alarm", methods=["POST"])
def diagnose_alarm():
    """
    Get AI diagnosis for an alarm.

    Request body:
        {
            "machine_id": "tinyg",
            "alarm_code": "ALARM:9"
        }

    Response:
        {
            "diagnosis": "...",
            "suggested_actions": [...]
        }
    """
    try:
        data = request.get_json()

        machine_id = data.get("machine_id", "unknown")
        alarm_code = data.get("alarm_code", "unknown")

        copilot = get_copilot_service()
        diagnosis = run_async(copilot._diagnose_alarm(machine_id, alarm_code))

        return jsonify({
            "machine_id": machine_id,
            "alarm_code": alarm_code,
            "diagnosis": diagnosis,
            "timestamp": datetime.now().isoformat(),
        })

    except Exception as e:
        logger.error(f"Diagnosis error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Service Control Endpoints
# =============================================================================

@copilot_bp.route("/status", methods=["GET"])
def get_copilot_status():
    """
    Get copilot service status.

    Response:
        {
            "running": true,
            "machines_tracked": 3,
            "active_sessions": 2,
            "events_processed": 156,
            "mqtt_connected": true
        }
    """
    try:
        copilot = get_copilot_service()

        return jsonify({
            "running": copilot._running,
            "machines_tracked": len(copilot._machines),
            "active_sessions": len(copilot._conversations),
            "events_in_history": len(copilot.event_processor._history),
            "notifications_sent": len(copilot.notification_manager._sent_history),
            "config": {
                "claude_model": copilot.config.claude_model,
                "proactive_diagnosis": copilot.config.enable_proactive_diagnosis,
                "quality_monitoring": copilot.config.enable_quality_monitoring,
                "shift_summaries": copilot.config.enable_shift_summaries,
            },
        })

    except Exception as e:
        logger.error(f"Status error: {e}")
        return jsonify({"error": str(e)}), 500


@copilot_bp.route("/start", methods=["POST"])
def start_copilot():
    """Start the copilot service."""
    try:
        copilot = get_copilot_service()
        run_async(copilot.start())

        return jsonify({
            "success": True,
            "message": "Copilot service started",
        })

    except Exception as e:
        logger.error(f"Start error: {e}")
        return jsonify({"error": str(e)}), 500


@copilot_bp.route("/stop", methods=["POST"])
def stop_copilot():
    """Stop the copilot service."""
    try:
        copilot = get_copilot_service()
        run_async(copilot.stop())

        return jsonify({
            "success": True,
            "message": "Copilot service stopped",
        })

    except Exception as e:
        logger.error(f"Stop error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# WebSocket Setup (for Flask-SocketIO)
# =============================================================================

def setup_copilot_socketio(socketio):
    """
    Set up Socket.IO events for the copilot.

    Call this from app.py after creating the socketio instance.
    """
    from flask_socketio import emit, join_room, leave_room

    @socketio.on("connect", namespace="/copilot")
    def handle_connect():
        logger.info("Copilot client connected")
        emit("connected", {"status": "connected"})

    @socketio.on("disconnect", namespace="/copilot")
    def handle_disconnect():
        logger.info("Copilot client disconnected")

    @socketio.on("join_machine", namespace="/copilot")
    def handle_join_machine(data):
        machine_id = data.get("machine_id")
        if machine_id:
            join_room(f"machine_{machine_id}")
            emit("joined", {"machine_id": machine_id})

    @socketio.on("leave_machine", namespace="/copilot")
    def handle_leave_machine(data):
        machine_id = data.get("machine_id")
        if machine_id:
            leave_room(f"machine_{machine_id}")
            emit("left", {"machine_id": machine_id})

    @socketio.on("chat", namespace="/copilot")
    def handle_chat(data):
        message = data.get("message")
        session_id = data.get("session_id", "default")
        machine_id = data.get("machine_id")

        if message:
            copilot = get_copilot_service()
            response = run_async(copilot.chat(session_id, message, machine_id))

            emit("chat_response", {
                "response": response,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
            })

    @socketio.on("get_status", namespace="/copilot")
    def handle_get_status():
        copilot = get_copilot_service()
        machines = copilot.get_all_machines()

        emit("status_update", {
            "machines": [
                {
                    "machine_id": m.machine_id,
                    "status": m.status,
                    "position": m.position,
                    "alarms": m.alarms,
                }
                for m in machines.values()
            ],
            "timestamp": datetime.now().isoformat(),
        })

    logger.info("Copilot Socket.IO handlers registered")
