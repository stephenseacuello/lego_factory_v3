"""
Claude AI Assistant Service for CNC SCADA.

Main orchestration service that integrates Claude API with MCP tools
for intelligent manufacturing assistance.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

import aiohttp

from services.claude_assistant.intent_parser import IntentParser, ParsedIntent, IntentCategory, IntentAction
from services.claude_assistant.context_manager import ContextManager, ConversationRole, SessionContext
from services.claude_assistant.response_formatter import ResponseFormatter, FormattedResponse, MessageType

logger = logging.getLogger(__name__)


# System prompt for Claude
SYSTEM_PROMPT = """You are an AI assistant for a CNC SCADA (Supervisory Control and Data Acquisition) system.

You help machinists and operators with:
- Monitoring machine status and health
- Diagnosing alarms and troubleshooting issues
- Analyzing G-code and toolpaths
- Quality predictions and SPC analysis
- Approving NC programs for production
- Providing setup guidance

## Available Tools

You have access to the following MCP tools:

### Machine Control
- get_machine_status: Get current machine state, position, and connection info
- send_gcode: Send G-code commands (use dry_run=true for testing)
- feed_hold: Emergency stop all motion
- safe_resume: Resume after feed hold
- jog_axis: Move an axis manually
- home_machine: Home the machine
- zero_axis: Set work coordinate origin

### G-code Analysis
- analyze_toolpath: Analyze G-code for issues
- parse_gcode: Parse G-code program
- validate_gcode: Validate G-code safety
- estimate_time: Estimate cycle time

### Quality
- get_spc_analysis: Get SPC control chart analysis
- predict_quality: Get quality prediction
- get_process_capability: Get Cp/Cpk metrics

### Diagnostics
- diagnose_alarm: Diagnose alarm codes
- get_machine_health: Overall machine health assessment

### Fusion 360 Integration
- approve_nc_program: Approve NC program for production
- reject_nc_program: Reject NC program
- sync_fusion_parameters: Sync CAD parameters

## Safety Rules

1. NEVER send motion commands without confirming with the user first
2. Always recommend dry_run=true for new G-code
3. Feed hold is always safe to execute immediately
4. For alarm conditions, always diagnose before suggesting resolution
5. Log all approval decisions for audit trail

## Response Guidelines

- Be concise but thorough
- Use technical terms appropriately for machinists
- Always explain why you're recommending an action
- If unsure, ask for clarification
- Proactively suggest next steps

{context}
"""


@dataclass
class AssistantConfig:
    """Configuration for the assistant service."""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.7
    flask_url: str = "http://localhost:5000"
    require_confirmation_for: List[str] = None

    def __post_init__(self):
        if self.require_confirmation_for is None:
            self.require_confirmation_for = [
                "send_gcode",
                "jog_axis",
                "home_machine",
                "zero_axis",
                "approve_nc_program",
                "reject_nc_program",
            ]


class AssistantService:
    """
    Main Claude AI Assistant service for CNC SCADA.

    Orchestrates:
    - Claude API calls with tool use
    - Intent parsing for quick responses
    - Context management across sessions
    - Response formatting for different outputs
    """

    def __init__(self, config: Optional[AssistantConfig] = None):
        """
        Initialize the assistant service.

        Args:
            config: Assistant configuration
        """
        self.config = config or AssistantConfig()

        # Initialize components
        self.intent_parser = IntentParser()
        self.context_manager = ContextManager()
        self.response_formatter = ResponseFormatter()

        # Initialize Claude client
        self.client = None
        if ANTHROPIC_AVAILABLE:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                self.client = anthropic.Anthropic(api_key=api_key)
                logger.info("Claude API client initialized")
            else:
                logger.warning("ANTHROPIC_API_KEY not set, running in offline mode")
        else:
            logger.warning("anthropic package not installed, running in offline mode")

        # Tool handlers
        self.tool_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default tool handlers."""
        # These will call the Flask API
        async def handle_get_machine_status(args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._call_flask_api("GET", "/api/tinyg/status")

        async def handle_send_gcode(args: Dict[str, Any]) -> Dict[str, Any]:
            gcode = args.get("gcode", "")
            dry_run = args.get("dry_run", False)
            endpoint = "/api/tinyg/dry-run" if dry_run else "/api/tinyg/send"
            return await self._call_flask_api("POST", endpoint, {"gcode": gcode})

        async def handle_feed_hold(args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._call_flask_api("POST", "/api/tinyg/feed-hold")

        async def handle_safe_resume(args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._call_flask_api("POST", "/api/tinyg/safe-resume", args)

        async def handle_jog_axis(args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._call_flask_api("POST", "/api/tinyg/jog", args)

        async def handle_home_machine(args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._call_flask_api("POST", "/api/tinyg/home", args)

        async def handle_zero_axis(args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._call_flask_api("POST", "/api/tinyg/zero", args)

        async def handle_get_spc_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._call_flask_api("GET", "/api/quality/spc", args)

        async def handle_predict_quality(args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._call_flask_api("GET", "/api/quality/predict", args)

        async def handle_diagnose_alarm(args: Dict[str, Any]) -> Dict[str, Any]:
            # Use local knowledge base for alarm diagnosis
            from mcp_server.tools.diagnostic_tools import DiagnosticTools
            tools = DiagnosticTools(self.config.flask_url)
            return await tools._diagnose_alarm(args)

        async def handle_get_machine_health(args: Dict[str, Any]) -> Dict[str, Any]:
            from mcp_server.tools.diagnostic_tools import DiagnosticTools
            tools = DiagnosticTools(self.config.flask_url)
            return await tools._get_machine_health(args)

        async def handle_analyze_toolpath(args: Dict[str, Any]) -> Dict[str, Any]:
            return await self._call_flask_api("POST", "/api/gcode/analyze", args)

        # Register handlers
        self.tool_handlers = {
            "get_machine_status": handle_get_machine_status,
            "send_gcode": handle_send_gcode,
            "feed_hold": handle_feed_hold,
            "safe_resume": handle_safe_resume,
            "jog_axis": handle_jog_axis,
            "home_machine": handle_home_machine,
            "zero_axis": handle_zero_axis,
            "get_spc_analysis": handle_get_spc_analysis,
            "predict_quality": handle_predict_quality,
            "diagnose_alarm": handle_diagnose_alarm,
            "get_machine_health": handle_get_machine_health,
            "analyze_toolpath": handle_analyze_toolpath,
        }

    async def _call_flask_api(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Call the Flask backend API."""
        url = f"{self.config.flask_url}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    async with session.get(url, params=data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        return await response.json()
                else:
                    async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        return await response.json()
        except Exception as e:
            logger.exception(f"Error calling Flask API: {endpoint}")
            return {"success": False, "error": str(e)}

    async def process_message(
        self,
        session_id: str,
        user_message: str,
        user_id: Optional[str] = None,
    ) -> FormattedResponse:
        """
        Process a user message and generate a response.

        Args:
            session_id: Session identifier
            user_message: User's message
            user_id: Optional user identifier

        Returns:
            FormattedResponse with assistant's reply
        """
        # Get or create session
        session = self.context_manager.get_or_create_session(session_id, user_id)

        # Add user message to context
        self.context_manager.add_message(
            session_id,
            ConversationRole.USER,
            user_message,
        )

        # Parse intent for quick handling
        intent = self.intent_parser.parse(user_message)

        # Handle emergency commands immediately
        if intent.category == IntentCategory.EMERGENCY:
            return await self._handle_emergency(session_id, intent)

        # Handle confirmations
        if intent.action == IntentAction.CONFIRM:
            return await self._handle_confirmation(session_id, intent)

        if intent.action == IntentAction.DENY:
            return self._handle_denial(session_id)

        # Handle simple greetings locally
        if intent.action == IntentAction.GREETING:
            return self._handle_greeting()

        if intent.action == IntentAction.GET_HELP:
            return self.response_formatter.format_help([])

        # For other intents, check if we need confirmation
        if intent.requires_confirmation and intent.suggested_tools:
            return await self._request_confirmation(session_id, intent)

        # Use Claude for complex queries or if we have a client
        if self.client:
            return await self._process_with_claude(session_id, user_message, intent)

        # Offline mode - handle with local tools
        return await self._process_offline(session_id, intent)

    async def _handle_emergency(self, session_id: str, intent: ParsedIntent) -> FormattedResponse:
        """Handle emergency commands immediately without confirmation."""
        if intent.action == IntentAction.FEED_HOLD or intent.action == IntentAction.EMERGENCY_STOP:
            result = await self.tool_handlers["feed_hold"]({})

            self.context_manager.add_message(
                session_id,
                ConversationRole.ASSISTANT,
                "Emergency stop executed.",
                tool_results=[result],
            )

            return FormattedResponse(
                text="## 🛑 FEED HOLD EXECUTED\n\nAll motion has been stopped. Use 'resume' when safe to continue.",
                message_type=MessageType.WARNING,
                data=result,
                voice_text="Feed hold executed. All motion stopped.",
            )

        elif intent.action == IntentAction.RESUME:
            result = await self.tool_handlers["safe_resume"]({})

            self.context_manager.add_message(
                session_id,
                ConversationRole.ASSISTANT,
                "Resume executed.",
                tool_results=[result],
            )

            if result.get("success"):
                return FormattedResponse(
                    text="## ✅ Resume Successful\n\nMachine motion has resumed.",
                    message_type=MessageType.SUCCESS,
                    data=result,
                    voice_text="Machine resumed successfully.",
                )
            else:
                return self.response_formatter.format_error(
                    "Resume failed",
                    details=result.get("error"),
                    suggestion="Check machine position before retrying.",
                )

        return self.response_formatter.format_error("Unknown emergency command")

    async def _handle_confirmation(self, session_id: str, intent: ParsedIntent) -> FormattedResponse:
        """Handle confirmation of pending action."""
        session = self.context_manager.get_session(session_id)
        if not session or not session.pending_confirmations:
            return FormattedResponse(
                text="No pending action to confirm.",
                message_type=MessageType.INFO,
                voice_text="No pending action to confirm.",
            )

        # Get the most recent pending confirmation
        confirmation = session.pending_confirmations.pop(0)
        action = confirmation["action"]
        params = confirmation["params"]

        # Execute the action
        if action in self.tool_handlers:
            result = await self.tool_handlers[action](params)

            self.context_manager.add_message(
                session_id,
                ConversationRole.ASSISTANT,
                f"Executed {action}",
                tool_results=[result],
            )

            if result.get("success", True):
                return self.response_formatter.format_success(
                    f"Action '{action}' completed successfully.",
                    details=result,
                )
            else:
                return self.response_formatter.format_error(
                    f"Action '{action}' failed",
                    details=result.get("error"),
                )
        else:
            return self.response_formatter.format_error(f"Unknown action: {action}")

    def _handle_denial(self, session_id: str) -> FormattedResponse:
        """Handle denial of pending action."""
        session = self.context_manager.get_session(session_id)
        if session and session.pending_confirmations:
            session.pending_confirmations.clear()

        return FormattedResponse(
            text="Action cancelled.",
            message_type=MessageType.INFO,
            voice_text="Action cancelled.",
        )

    def _handle_greeting(self) -> FormattedResponse:
        """Handle greeting messages."""
        return FormattedResponse(
            text="Hello! I'm your CNC SCADA assistant. How can I help you today?\n\nYou can ask me about:\n- Machine status and diagnostics\n- G-code analysis\n- Quality predictions\n- Alarm troubleshooting\n\nJust ask naturally!",
            message_type=MessageType.INFO,
            voice_text="Hello! I'm your CNC SCADA assistant. How can I help you?",
        )

    async def _request_confirmation(self, session_id: str, intent: ParsedIntent) -> FormattedResponse:
        """Request confirmation for a dangerous action."""
        action = intent.suggested_tools[0] if intent.suggested_tools else intent.action.value
        description = self.intent_parser.get_intent_description(intent)

        confirmation_id = self.context_manager.add_pending_confirmation(
            session_id,
            action=action,
            description=description,
            params=intent.entities,
        )

        return self.response_formatter.format_confirmation_request(
            action=action,
            description=description,
            confirmation_id=confirmation_id,
        )

    async def _process_with_claude(
        self,
        session_id: str,
        user_message: str,
        intent: ParsedIntent,
    ) -> FormattedResponse:
        """Process message using Claude API with tool use."""
        session = self.context_manager.get_session(session_id)

        # Build system prompt with context
        system_context = self.context_manager.get_system_context(session_id)
        system_prompt = SYSTEM_PROMPT.format(context=system_context)

        # Get conversation history
        messages = self.context_manager.get_conversation_for_api(session_id, include_system=False)

        # Define available tools for Claude
        tools = self._get_claude_tools()

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=system_prompt,
                messages=messages,
                tools=tools,
            )

            # Process response
            assistant_text = ""
            tool_calls = []
            tool_results = []

            for content_block in response.content:
                if content_block.type == "text":
                    assistant_text += content_block.text
                elif content_block.type == "tool_use":
                    tool_calls.append({
                        "id": content_block.id,
                        "name": content_block.name,
                        "input": content_block.input,
                    })

                    # Execute tool
                    if content_block.name in self.tool_handlers:
                        result = await self.tool_handlers[content_block.name](content_block.input)
                        tool_results.append({
                            "tool_use_id": content_block.id,
                            "result": result,
                        })

            # If tools were called, we may need another round
            if tool_calls and response.stop_reason == "tool_use":
                # Add tool results and get final response
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                })
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tr["tool_use_id"],
                            "content": json.dumps(tr["result"]),
                        }
                        for tr in tool_results
                    ],
                })

                # Get final response
                final_response = self.client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                )

                for content_block in final_response.content:
                    if content_block.type == "text":
                        assistant_text = content_block.text

            # Add assistant response to context
            self.context_manager.add_message(
                session_id,
                ConversationRole.ASSISTANT,
                assistant_text,
                tool_calls=tool_calls,
                tool_results=tool_results,
            )

            return FormattedResponse(
                text=assistant_text,
                message_type=MessageType.INFO,
                data={"tool_calls": tool_calls, "tool_results": tool_results},
                markdown=assistant_text,
            )

        except Exception as e:
            logger.exception("Error calling Claude API")
            return self.response_formatter.format_error(
                "Failed to process request",
                details=str(e),
                suggestion="Try again or use a simpler command.",
            )

    async def _process_offline(self, session_id: str, intent: ParsedIntent) -> FormattedResponse:
        """Process message in offline mode using local tools."""
        # Handle based on intent
        if intent.action == IntentAction.GET_STATUS:
            result = await self.tool_handlers["get_machine_status"]({})
            return self.response_formatter.format_machine_status(result)

        elif intent.action == IntentAction.GET_SPC:
            result = await self.tool_handlers["get_spc_analysis"](intent.entities)
            return self.response_formatter.format_spc_data(result)

        elif intent.action == IntentAction.PREDICT_QUALITY:
            result = await self.tool_handlers["predict_quality"](intent.entities)
            return self.response_formatter.format_quality_prediction(result)

        elif intent.action == IntentAction.DIAGNOSE_ALARM:
            result = await self.tool_handlers["diagnose_alarm"](intent.entities)
            return self.response_formatter.format_alarm_diagnosis(result)

        elif intent.action == IntentAction.GET_HEALTH:
            result = await self.tool_handlers["get_machine_health"](intent.entities)
            return FormattedResponse(
                text=f"## Machine Health\n\n**Score:** {result.get('health_score', 0)}/100\n**Level:** {result.get('health_level', 'unknown')}\n\n**Issues:** {', '.join(result.get('issues', ['None']))}",
                message_type=MessageType.INFO,
                data=result,
            )

        else:
            return FormattedResponse(
                text="I'm running in offline mode. For complex queries, please ensure the Claude API is configured.\n\nAvailable offline commands:\n- Machine status\n- SPC analysis\n- Quality prediction\n- Alarm diagnosis\n- Machine health",
                message_type=MessageType.WARNING,
            )

    def _get_claude_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions for Claude API."""
        return [
            {
                "name": "get_machine_status",
                "description": "Get current CNC machine status including position, state, and connection info",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "send_gcode",
                "description": "Send G-code command to the machine. Use dry_run=true to simulate.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "gcode": {"type": "string", "description": "G-code command"},
                        "dry_run": {"type": "boolean", "description": "Simulate without sending", "default": True},
                    },
                    "required": ["gcode"],
                },
            },
            {
                "name": "feed_hold",
                "description": "Emergency stop - immediately halt all machine motion",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "diagnose_alarm",
                "description": "Diagnose a machine alarm code and provide solutions",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "alarm_code": {"type": "integer", "description": "Alarm code number"},
                    },
                    "required": ["alarm_code"],
                },
            },
            {
                "name": "get_spc_analysis",
                "description": "Get SPC control chart analysis",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "feature": {"type": "string", "description": "Feature to analyze"},
                        "hours": {"type": "integer", "description": "Time range in hours", "default": 24},
                    },
                    "required": [],
                },
            },
            {
                "name": "predict_quality",
                "description": "Get real-time quality prediction based on current conditions",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "get_machine_health",
                "description": "Get overall machine health assessment",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ]

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session."""
        session = self.context_manager.get_session(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "started_at": session.started_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "message_count": len(session.messages),
            "pending_confirmations": len(session.pending_confirmations),
            "machine_connected": session.machine_context.connected,
            "machine_state": session.machine_context.state,
        }
