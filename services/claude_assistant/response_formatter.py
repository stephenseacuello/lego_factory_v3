"""
Response Formatter for Claude Assistant.

Formats responses for different output channels (chat, voice, API).
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """Output format types."""
    CHAT = "chat"           # Web chat UI
    VOICE = "voice"         # Voice output (TTS)
    API = "api"             # API response
    SLACK = "slack"         # Slack message
    TERMINAL = "terminal"   # Terminal output


class MessageType(Enum):
    """Types of messages."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CONFIRMATION = "confirmation"
    PROGRESS = "progress"


@dataclass
class FormattedResponse:
    """A formatted response for output."""
    text: str
    message_type: MessageType = MessageType.INFO
    data: Dict[str, Any] = field(default_factory=dict)
    actions: List[Dict[str, str]] = field(default_factory=list)
    requires_input: bool = False
    voice_text: Optional[str] = None  # Simplified text for TTS
    markdown: Optional[str] = None    # Rich markdown version


class ResponseFormatter:
    """
    Format responses for different output channels.

    Handles:
    - Chat UI formatting with markdown
    - Voice output simplification
    - API response structuring
    - Error message formatting
    """

    def __init__(self, default_format: OutputFormat = OutputFormat.CHAT):
        """Initialize formatter with default output format."""
        self.default_format = default_format

    def format_machine_status(
        self,
        status: Dict[str, Any],
        output_format: Optional[OutputFormat] = None,
    ) -> FormattedResponse:
        """Format machine status response."""
        output_format = output_format or self.default_format

        connected = status.get("connected", False)
        state = status.get("state", "unknown")
        position = status.get("position", {})
        interpretation = status.get("interpretation", "")

        # Determine message type
        if not connected:
            msg_type = MessageType.ERROR
        elif state == "alarm":
            msg_type = MessageType.WARNING
        else:
            msg_type = MessageType.INFO

        # Build text based on format
        if output_format == OutputFormat.VOICE:
            if not connected:
                text = "The machine is not connected."
            elif state == "alarm":
                text = f"Warning: The machine is in alarm state."
            elif state == "running":
                text = f"The machine is running at position X {position.get('x', 0):.1f}, Y {position.get('y', 0):.1f}, Z {position.get('z', 0):.1f}."
            else:
                text = f"The machine is {state}."
            voice_text = text
            markdown = None
        else:
            # Chat/API format with markdown
            lines = [
                f"## Machine Status",
                "",
                f"**State:** {state.upper()}",
                f"**Connected:** {'Yes' if connected else 'No'}",
                "",
                "### Position",
                f"- X: {position.get('x', 0):.4f} mm",
                f"- Y: {position.get('y', 0):.4f} mm",
                f"- Z: {position.get('z', 0):.4f} mm",
            ]

            if status.get("feed_rate"):
                lines.append(f"- Feed Rate: {status['feed_rate']} mm/min")
            if status.get("spindle_speed"):
                lines.append(f"- Spindle: {status['spindle_speed']} RPM")

            if interpretation:
                lines.extend(["", f"**Summary:** {interpretation}"])

            text = "\n".join(lines)
            markdown = text
            voice_text = f"Machine is {state}. Position X {position.get('x', 0):.1f}, Y {position.get('y', 0):.1f}, Z {position.get('z', 0):.1f}."

        return FormattedResponse(
            text=text,
            message_type=msg_type,
            data=status,
            voice_text=voice_text,
            markdown=markdown,
        )

    def format_gcode_result(
        self,
        result: Dict[str, Any],
        output_format: Optional[OutputFormat] = None,
    ) -> FormattedResponse:
        """Format G-code execution result."""
        output_format = output_format or self.default_format

        success = result.get("success", False)
        gcode = result.get("gcode", "")
        dry_run = result.get("dry_run", False)
        error = result.get("error", "")

        if success:
            msg_type = MessageType.SUCCESS
            if dry_run:
                text = f"**Dry run successful** for: `{gcode}`"
                voice_text = f"Dry run successful for {gcode}"
            else:
                text = f"**Command sent:** `{gcode}`"
                voice_text = f"Command sent: {gcode}"
        else:
            msg_type = MessageType.ERROR
            text = f"**Failed to send:** `{gcode}`\n\nError: {error}"
            voice_text = f"Failed to send command. Error: {error}"

        return FormattedResponse(
            text=text,
            message_type=msg_type,
            data=result,
            voice_text=voice_text,
            markdown=text,
        )

    def format_alarm_diagnosis(
        self,
        diagnosis: Dict[str, Any],
        output_format: Optional[OutputFormat] = None,
    ) -> FormattedResponse:
        """Format alarm diagnosis response."""
        output_format = output_format or self.default_format

        alarm_code = diagnosis.get("alarm_code", "?")
        alarm_name = diagnosis.get("alarm_name", "Unknown")
        description = diagnosis.get("description", "")
        causes = diagnosis.get("possible_causes", [])
        solutions = diagnosis.get("recommended_solutions", [])

        lines = [
            f"## Alarm {alarm_code}: {alarm_name}",
            "",
            f"**Description:** {description}",
            "",
            "### Possible Causes",
        ]

        for cause in causes:
            lines.append(f"- {cause}")

        lines.extend(["", "### Recommended Solutions"])

        for i, solution in enumerate(solutions, 1):
            lines.append(f"{i}. {solution}")

        text = "\n".join(lines)

        # Voice version is simplified
        voice_text = f"Alarm {alarm_code}: {alarm_name}. {description}. First, try: {solutions[0] if solutions else 'checking the machine'}."

        return FormattedResponse(
            text=text,
            message_type=MessageType.WARNING,
            data=diagnosis,
            voice_text=voice_text,
            markdown=text,
        )

    def format_quality_prediction(
        self,
        prediction: Dict[str, Any],
        output_format: Optional[OutputFormat] = None,
    ) -> FormattedResponse:
        """Format quality prediction response."""
        output_format = output_format or self.default_format

        score = prediction.get("predicted_score", 0)
        confidence = prediction.get("confidence", 0)
        risk_level = prediction.get("risk_level", "unknown")
        risk_factors = prediction.get("risk_factors", [])
        recommendations = prediction.get("recommendations", [])
        interpretation = prediction.get("interpretation", "")

        # Determine message type based on score
        if score >= 85:
            msg_type = MessageType.SUCCESS
            emoji = "✅"
        elif score >= 70:
            msg_type = MessageType.WARNING
            emoji = "⚠️"
        else:
            msg_type = MessageType.ERROR
            emoji = "🔴"

        lines = [
            f"## {emoji} Quality Prediction",
            "",
            f"**Score:** {score:.0f}/100",
            f"**Confidence:** {confidence * 100:.0f}%",
            f"**Risk Level:** {risk_level.upper()}",
            "",
        ]

        if interpretation:
            lines.append(f"**Assessment:** {interpretation}")
            lines.append("")

        if risk_factors:
            lines.append("### Risk Factors")
            for factor in risk_factors:
                lines.append(f"- {factor}")
            lines.append("")

        if recommendations:
            lines.append("### Recommendations")
            for rec in recommendations:
                lines.append(f"- {rec}")

        text = "\n".join(lines)
        voice_text = f"Quality prediction: {score:.0f} out of 100. Risk level is {risk_level}. {interpretation}"

        return FormattedResponse(
            text=text,
            message_type=msg_type,
            data=prediction,
            voice_text=voice_text,
            markdown=text,
        )

    def format_confirmation_request(
        self,
        action: str,
        description: str,
        confirmation_id: str,
        expires_seconds: int = 60,
    ) -> FormattedResponse:
        """Format a confirmation request for dangerous actions."""
        lines = [
            "## ⚠️ Confirmation Required",
            "",
            f"**Action:** {action}",
            f"**Details:** {description}",
            "",
            f"This action requires confirmation. Say **'confirm'** or **'yes'** to proceed.",
            f"Say **'cancel'** or **'no'** to abort.",
            "",
            f"*This confirmation expires in {expires_seconds} seconds.*",
        ]

        text = "\n".join(lines)
        voice_text = f"Confirmation required for {action}. {description}. Say confirm to proceed or cancel to abort."

        return FormattedResponse(
            text=text,
            message_type=MessageType.CONFIRMATION,
            data={
                "action": action,
                "description": description,
                "confirmation_id": confirmation_id,
                "expires_seconds": expires_seconds,
            },
            requires_input=True,
            voice_text=voice_text,
            markdown=text,
            actions=[
                {"label": "Confirm", "action": "confirm"},
                {"label": "Cancel", "action": "cancel"},
            ],
        )

    def format_error(
        self,
        error: str,
        details: Optional[str] = None,
        suggestion: Optional[str] = None,
    ) -> FormattedResponse:
        """Format an error message."""
        lines = [f"## ❌ Error", "", error]

        if details:
            lines.extend(["", f"**Details:** {details}"])

        if suggestion:
            lines.extend(["", f"**Suggestion:** {suggestion}"])

        text = "\n".join(lines)
        voice_text = f"Error: {error}. {suggestion or ''}"

        return FormattedResponse(
            text=text,
            message_type=MessageType.ERROR,
            data={"error": error, "details": details},
            voice_text=voice_text,
            markdown=text,
        )

    def format_success(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> FormattedResponse:
        """Format a success message."""
        lines = [f"## ✅ Success", "", message]

        if details:
            lines.extend(["", "**Details:**"])
            for key, value in details.items():
                lines.append(f"- {key}: {value}")

        text = "\n".join(lines)
        voice_text = message

        return FormattedResponse(
            text=text,
            message_type=MessageType.SUCCESS,
            data=details or {},
            voice_text=voice_text,
            markdown=text,
        )

    def format_help(self, commands: List[Dict[str, str]]) -> FormattedResponse:
        """Format help response with available commands."""
        lines = [
            "## 🤖 CNC SCADA Assistant",
            "",
            "I can help you with:",
            "",
            "### Machine Control",
            "- \"What's the machine status?\"",
            "- \"Jog X 10\" or \"Move Y -5\"",
            "- \"Home the machine\"",
            "- \"Zero Z\"",
            "",
            "### Emergency Commands",
            "- \"Stop\" or \"Feed hold\"",
            "- \"Resume\"",
            "",
            "### Quality & Diagnostics",
            "- \"Show SPC data\"",
            "- \"Predict quality\"",
            "- \"Diagnose alarm 3\"",
            "- \"Check machine health\"",
            "",
            "### G-code",
            "- \"Analyze the toolpath\"",
            "- \"Send G0 X10 Y20\"",
            "",
            "### Approvals",
            "- \"Approve program bracket.nc\"",
            "- \"Show pending approvals\"",
            "",
            "Just ask naturally and I'll help!",
        ]

        text = "\n".join(lines)
        voice_text = "I can help with machine control, diagnostics, quality analysis, and G-code operations. Just ask naturally."

        return FormattedResponse(
            text=text,
            message_type=MessageType.INFO,
            data={"commands": commands},
            voice_text=voice_text,
            markdown=text,
        )

    def format_spc_data(
        self,
        spc_data: Dict[str, Any],
        output_format: Optional[OutputFormat] = None,
    ) -> FormattedResponse:
        """Format SPC analysis data."""
        summary = spc_data.get("summary", "No SPC data available")
        charts = spc_data.get("charts", [])

        lines = ["## 📊 SPC Analysis", "", summary, ""]

        for chart in charts[:5]:  # Limit to 5 charts
            feature = chart.get("feature", "Unknown")
            status = chart.get("status", "unknown")
            status_emoji = {"in_control": "✅", "warning": "⚠️", "out_of_control": "🔴"}.get(status, "❓")

            lines.append(f"### {status_emoji} {feature}")
            lines.append(f"- UCL: {chart.get('ucl', 'N/A')}")
            lines.append(f"- CL: {chart.get('cl', 'N/A')}")
            lines.append(f"- LCL: {chart.get('lcl', 'N/A')}")
            lines.append(f"- Status: {status}")
            lines.append("")

        text = "\n".join(lines)
        voice_text = f"SPC Analysis: {summary}"

        # Determine message type
        if any(c.get("status") == "out_of_control" for c in charts):
            msg_type = MessageType.ERROR
        elif any(c.get("status") == "warning" for c in charts):
            msg_type = MessageType.WARNING
        else:
            msg_type = MessageType.SUCCESS

        return FormattedResponse(
            text=text,
            message_type=msg_type,
            data=spc_data,
            voice_text=voice_text,
            markdown=text,
        )

    def to_api_response(self, response: FormattedResponse) -> Dict[str, Any]:
        """Convert FormattedResponse to API response format."""
        return {
            "success": response.message_type not in (MessageType.ERROR,),
            "message": response.text,
            "type": response.message_type.value,
            "data": response.data,
            "actions": response.actions,
            "requires_input": response.requires_input,
            "voice_text": response.voice_text,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def to_slack_message(self, response: FormattedResponse) -> Dict[str, Any]:
        """Convert FormattedResponse to Slack message format."""
        color_map = {
            MessageType.SUCCESS: "good",
            MessageType.WARNING: "warning",
            MessageType.ERROR: "danger",
            MessageType.INFO: "#439FE0",
            MessageType.CONFIRMATION: "warning",
            MessageType.PROGRESS: "#439FE0",
        }

        return {
            "attachments": [
                {
                    "color": color_map.get(response.message_type, "#439FE0"),
                    "text": response.text,
                    "mrkdwn_in": ["text"],
                }
            ]
        }
