"""
Events Routes - Real-time Event Streaming API

LegoMCP World-Class Manufacturing System v5.0
Phase 7: Event-Driven Architecture
"""

from flask import Blueprint

events_bp = Blueprint('events', __name__, url_prefix='/api/events')

from . import stream  # noqa: E402, F401
