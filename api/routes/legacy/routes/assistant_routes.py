"""
Claude AI Assistant API Routes.

Provides REST and WebSocket endpoints for the Claude Assistant.
"""

import logging
import uuid
import asyncio
from typing import Dict, Any, Optional

from flask import Blueprint, request, jsonify, session
from flask_socketio import emit, join_room, leave_room

logger = logging.getLogger(__name__)

# Create blueprint
assistant_bp = Blueprint("assistant", __name__, url_prefix="/api/assistant")

# Assistant service instance (initialized on first use)
_assistant_service = None


def get_assistant_service():
    """Get or create the assistant service instance."""
    global _assistant_service
    if _assistant_service is None:
        from services.claude_assistant import AssistantService
        _assistant_service = AssistantService()
    return _assistant_service


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


def get_session_id() -> str:
    """Get or create session ID for current user."""
    if "assistant_session_id" not in session:
        session["assistant_session_id"] = str(uuid.uuid4())
    return session["assistant_session_id"]


# ─────────────────────────────────────────────────────────────────────────────
# REST API Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@assistant_bp.route("/chat", methods=["POST"])
def chat():
    """
    Process a chat message and return assistant response.

    Request body:
    {
        "message": "User's message",
        "session_id": "optional-session-id"
    }

    Response:
    {
        "success": true,
        "response": {
            "text": "Assistant's response",
            "type": "info|success|warning|error",
            "data": {...},
            "actions": [...]
        },
        "session_id": "session-id"
    }
    """
    try:
        data = request.get_json() or {}
        message = data.get("message", "").strip()
        session_id = data.get("session_id") or get_session_id()
        user_id = data.get("user_id")

        if not message:
            return jsonify({
                "success": False,
                "error": "Message is required",
            }), 400

        service = get_assistant_service()
        response = run_async(service.process_message(
            session_id=session_id,
            user_message=message,
            user_id=user_id,
        ))

        return jsonify({
            "success": True,
            "response": {
                "text": response.text,
                "type": response.message_type.value,
                "data": response.data,
                "actions": response.actions,
                "requires_input": response.requires_input,
                "voice_text": response.voice_text,
            },
            "session_id": session_id,
        })

    except Exception as e:
        logger.exception("Error processing chat message")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@assistant_bp.route("/session", methods=["GET"])
def get_session():
    """
    Get current session information.

    Response:
    {
        "success": true,
        "session": {
            "session_id": "...",
            "message_count": 10,
            "machine_connected": true,
            ...
        }
    }
    """
    try:
        session_id = get_session_id()
        service = get_assistant_service()
        session_info = service.get_session_info(session_id)

        if session_info:
            return jsonify({
                "success": True,
                "session": session_info,
            })
        else:
            return jsonify({
                "success": True,
                "session": {
                    "session_id": session_id,
                    "message_count": 0,
                    "is_new": True,
                },
            })

    except Exception as e:
        logger.exception("Error getting session info")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@assistant_bp.route("/session", methods=["DELETE"])
def clear_session():
    """
    Clear the current session and start fresh.

    Response:
    {
        "success": true,
        "message": "Session cleared"
    }
    """
    try:
        if "assistant_session_id" in session:
            del session["assistant_session_id"]

        return jsonify({
            "success": True,
            "message": "Session cleared",
        })

    except Exception as e:
        logger.exception("Error clearing session")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@assistant_bp.route("/confirm/<confirmation_id>", methods=["POST"])
def confirm_action(confirmation_id: str):
    """
    Confirm a pending action.

    Response:
    {
        "success": true,
        "result": {...}
    }
    """
    try:
        session_id = get_session_id()
        service = get_assistant_service()

        # Process confirmation through the normal message flow
        response = run_async(service.process_message(
            session_id=session_id,
            user_message=f"confirm {confirmation_id}",
        ))

        return jsonify({
            "success": True,
            "response": {
                "text": response.text,
                "type": response.message_type.value,
                "data": response.data,
            },
        })

    except Exception as e:
        logger.exception("Error confirming action")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@assistant_bp.route("/cancel", methods=["POST"])
def cancel_action():
    """
    Cancel any pending actions.

    Response:
    {
        "success": true,
        "message": "Pending actions cancelled"
    }
    """
    try:
        session_id = get_session_id()
        service = get_assistant_service()

        response = run_async(service.process_message(
            session_id=session_id,
            user_message="cancel",
        ))

        return jsonify({
            "success": True,
            "response": {
                "text": response.text,
                "type": response.message_type.value,
            },
        })

    except Exception as e:
        logger.exception("Error cancelling action")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@assistant_bp.route("/quick-actions", methods=["GET"])
def get_quick_actions():
    """
    Get list of quick action buttons for the UI.

    Response:
    {
        "success": true,
        "actions": [
            {"label": "Machine Status", "command": "status"},
            ...
        ]
    }
    """
    quick_actions = [
        {"label": "📊 Machine Status", "command": "What's the machine status?", "category": "status"},
        {"label": "🔴 Feed Hold", "command": "feed hold", "category": "emergency"},
        {"label": "▶️ Resume", "command": "resume", "category": "control"},
        {"label": "📈 Quality Prediction", "command": "predict quality", "category": "quality"},
        {"label": "📉 SPC Analysis", "command": "show SPC data", "category": "quality"},
        {"label": "🏥 Machine Health", "command": "check machine health", "category": "diagnostic"},
        {"label": "🏠 Home Machine", "command": "home the machine", "category": "control"},
        {"label": "❓ Help", "command": "help", "category": "help"},
    ]

    return jsonify({
        "success": True,
        "actions": quick_actions,
    })


@assistant_bp.route("/history", methods=["GET"])
def get_history():
    """
    Get conversation history for current session.

    Query params:
    - limit: Maximum messages to return (default: 50)

    Response:
    {
        "success": true,
        "messages": [
            {"role": "user", "content": "...", "timestamp": "..."},
            {"role": "assistant", "content": "...", "timestamp": "..."}
        ]
    }
    """
    try:
        session_id = get_session_id()
        limit = request.args.get("limit", 50, type=int)

        service = get_assistant_service()
        session_ctx = service.context_manager.get_session(session_id)

        if not session_ctx:
            return jsonify({
                "success": True,
                "messages": [],
            })

        messages = []
        for msg in session_ctx.messages[-limit:]:
            messages.append({
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            })

        return jsonify({
            "success": True,
            "messages": messages,
        })

    except Exception as e:
        logger.exception("Error getting history")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Event Handlers (for real-time chat)
# ─────────────────────────────────────────────────────────────────────────────


def register_socketio_handlers(socketio):
    """Register Socket.IO event handlers for assistant."""

    @socketio.on("assistant_join")
    def on_join(data):
        """Join assistant chat room."""
        session_id = data.get("session_id") or str(uuid.uuid4())
        join_room(f"assistant_{session_id}")
        emit("assistant_joined", {"session_id": session_id})
        logger.info(f"Client joined assistant room: {session_id}")

    @socketio.on("assistant_leave")
    def on_leave(data):
        """Leave assistant chat room."""
        session_id = data.get("session_id")
        if session_id:
            leave_room(f"assistant_{session_id}")
            logger.info(f"Client left assistant room: {session_id}")

    @socketio.on("assistant_message")
    def on_message(data):
        """Handle incoming chat message via WebSocket."""
        session_id = data.get("session_id")
        message = data.get("message", "").strip()
        user_id = data.get("user_id")

        if not message:
            emit("assistant_error", {"error": "Message is required"})
            return

        # Emit typing indicator
        emit("assistant_typing", {"typing": True}, room=f"assistant_{session_id}")

        try:
            service = get_assistant_service()
            response = run_async(
                service.process_message(
                    session_id=session_id,
                    user_message=message,
                    user_id=user_id,
                )
            )

            # Stop typing indicator
            emit("assistant_typing", {"typing": False}, room=f"assistant_{session_id}")

            # Send response
            emit("assistant_response", {
                "text": response.text,
                "type": response.message_type.value,
                "data": response.data,
                "actions": response.actions,
                "requires_input": response.requires_input,
                "voice_text": response.voice_text,
                "markdown": response.markdown,
            }, room=f"assistant_{session_id}")

        except Exception as e:
            logger.exception("Error processing WebSocket message")
            emit("assistant_typing", {"typing": False}, room=f"assistant_{session_id}")
            emit("assistant_error", {"error": str(e)}, room=f"assistant_{session_id}")

    @socketio.on("assistant_confirm")
    def on_confirm(data):
        """Handle confirmation via WebSocket."""
        session_id = data.get("session_id")
        confirmation_id = data.get("confirmation_id")

        if not confirmation_id:
            emit("assistant_error", {"error": "Confirmation ID required"})
            return

        try:
            service = get_assistant_service()
            response = run_async(
                service.process_message(
                    session_id=session_id,
                    user_message=f"confirm {confirmation_id}",
                )
            )

            emit("assistant_response", {
                "text": response.text,
                "type": response.message_type.value,
                "data": response.data,
            }, room=f"assistant_{session_id}")

        except Exception as e:
            logger.exception("Error confirming via WebSocket")
            emit("assistant_error", {"error": str(e)}, room=f"assistant_{session_id}")

    @socketio.on("assistant_cancel")
    def on_cancel(data):
        """Handle cancellation via WebSocket."""
        session_id = data.get("session_id")

        try:
            service = get_assistant_service()
            response = run_async(
                service.process_message(
                    session_id=session_id,
                    user_message="cancel",
                )
            )

            emit("assistant_response", {
                "text": response.text,
                "type": response.message_type.value,
            }, room=f"assistant_{session_id}")

        except Exception as e:
            logger.exception("Error cancelling via WebSocket")
            emit("assistant_error", {"error": str(e)}, room=f"assistant_{session_id}")

    return socketio
