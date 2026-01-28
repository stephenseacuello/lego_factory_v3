"""
Claude AI Design Assistant for CNC SCADA.

This module provides an intelligent conversational interface for
CNC machine control, diagnostics, and manufacturing workflows.

Components:
- AssistantService: Main orchestration and Claude API integration
- IntentParser: Parse user intents from natural language
- ContextManager: Manage conversation context and state
- ResponseFormatter: Format responses for different outputs
- WorkflowHandlers: Handle specific manufacturing workflows
"""

from services.claude_assistant.assistant_service import AssistantService
from services.claude_assistant.intent_parser import IntentParser
from services.claude_assistant.context_manager import ContextManager
from services.claude_assistant.response_formatter import ResponseFormatter

__all__ = [
    "AssistantService",
    "IntentParser",
    "ContextManager",
    "ResponseFormatter",
]
