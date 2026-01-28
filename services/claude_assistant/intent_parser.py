"""
Intent Parser for Claude Assistant.

Parses user intents from natural language to determine appropriate actions.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class IntentCategory(Enum):
    """Categories of user intents."""
    MACHINE_STATUS = "machine_status"
    MACHINE_CONTROL = "machine_control"
    EMERGENCY = "emergency"
    GCODE = "gcode"
    QUALITY = "quality"
    DIAGNOSTIC = "diagnostic"
    APPROVAL = "approval"
    JOB_MANAGEMENT = "job_management"
    SETUP = "setup"
    HELP = "help"
    CONVERSATION = "conversation"
    UNKNOWN = "unknown"


class IntentAction(Enum):
    """Specific actions within intent categories."""
    # Machine Status
    GET_STATUS = "get_status"
    GET_POSITION = "get_position"
    CHECK_CONNECTION = "check_connection"

    # Machine Control
    SEND_GCODE = "send_gcode"
    JOG_AXIS = "jog_axis"
    HOME_MACHINE = "home_machine"
    ZERO_AXIS = "zero_axis"
    SET_FEED_OVERRIDE = "set_feed_override"

    # Emergency
    FEED_HOLD = "feed_hold"
    EMERGENCY_STOP = "emergency_stop"
    RESUME = "resume"

    # G-code
    ANALYZE_TOOLPATH = "analyze_toolpath"
    PARSE_GCODE = "parse_gcode"
    VALIDATE_GCODE = "validate_gcode"
    ESTIMATE_TIME = "estimate_time"

    # Quality
    GET_SPC = "get_spc"
    PREDICT_QUALITY = "predict_quality"
    GET_CAPABILITY = "get_capability"

    # Diagnostic
    DIAGNOSE_ALARM = "diagnose_alarm"
    TROUBLESHOOT = "troubleshoot"
    GET_HEALTH = "get_health"

    # Approval
    APPROVE_PROGRAM = "approve_program"
    REJECT_PROGRAM = "reject_program"
    LIST_PENDING = "list_pending"

    # Job Management
    START_JOB = "start_job"
    PAUSE_JOB = "pause_job"
    CANCEL_JOB = "cancel_job"
    GET_JOB_STATUS = "get_job_status"

    # Setup
    SETUP_GUIDANCE = "setup_guidance"

    # Help
    GET_HELP = "get_help"
    LIST_COMMANDS = "list_commands"

    # Conversation
    GREETING = "greeting"
    THANKS = "thanks"
    CONFIRM = "confirm"
    DENY = "deny"

    # Unknown
    UNKNOWN = "unknown"


@dataclass
class ParsedIntent:
    """Parsed intent from user input."""
    category: IntentCategory
    action: IntentAction
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    original_text: str = ""
    requires_confirmation: bool = False
    suggested_tools: List[str] = field(default_factory=list)


# Intent patterns with associated actions
INTENT_PATTERNS: List[Tuple[str, IntentCategory, IntentAction, List[str], bool]] = [
    # Emergency - highest priority
    (r"\b(stop|halt|e-?stop|emergency)\b", IntentCategory.EMERGENCY, IntentAction.EMERGENCY_STOP, ["feed_hold"], True),
    (r"\b(feed\s*hold|pause\s*motion|freeze)\b", IntentCategory.EMERGENCY, IntentAction.FEED_HOLD, ["feed_hold"], False),
    (r"\b(resume|continue|start\s*again|unpause)\b", IntentCategory.EMERGENCY, IntentAction.RESUME, ["safe_resume"], False),

    # Machine Status
    (r"\b(status|state|what('s|\s+is)\s+(the\s+)?(machine|mill|router|cnc)?\s*(doing|status)?)\b", IntentCategory.MACHINE_STATUS, IntentAction.GET_STATUS, ["get_machine_status"], False),
    (r"\b(position|where|location|coordinates?)\b", IntentCategory.MACHINE_STATUS, IntentAction.GET_POSITION, ["get_machine_status"], False),
    (r"\b(connect(ed|ion)?|online|communicat(e|ing|ion))\b", IntentCategory.MACHINE_STATUS, IntentAction.CHECK_CONNECTION, ["get_machine_status"], False),

    # Machine Control
    (r"\b(jog|move)\s+([xyz])\s*([-+]?\d+(\.\d+)?)\b", IntentCategory.MACHINE_CONTROL, IntentAction.JOG_AXIS, ["jog_axis"], True),
    (r"\b(home|homing|reference)\b", IntentCategory.MACHINE_CONTROL, IntentAction.HOME_MACHINE, ["home_machine"], True),
    (r"\b(zero|set\s*zero|origin)\s*([xyz]+)?\b", IntentCategory.MACHINE_CONTROL, IntentAction.ZERO_AXIS, ["zero_axis"], True),
    (r"\b(send|execute|run)\s*(g-?code|command)?\s*[:\-]?\s*([gm]\d+.*)\b", IntentCategory.MACHINE_CONTROL, IntentAction.SEND_GCODE, ["send_gcode"], True),

    # G-code Analysis
    (r"\b(analyz|check|review)\w*\s*(toolpath|g-?code|program)\b", IntentCategory.GCODE, IntentAction.ANALYZE_TOOLPATH, ["analyze_toolpath"], False),
    (r"\b(pars|read)\w*\s*(g-?code|program)\b", IntentCategory.GCODE, IntentAction.PARSE_GCODE, ["parse_gcode"], False),
    (r"\b(valid(ate)?|verify)\s*(g-?code|program)\b", IntentCategory.GCODE, IntentAction.VALIDATE_GCODE, ["validate_gcode"], False),
    (r"\b(time|duration|how\s+long|estimat)\b.*\b(program|job|g-?code)?\b", IntentCategory.GCODE, IntentAction.ESTIMATE_TIME, ["estimate_time"], False),

    # Quality
    (r"\b(spc|control\s+chart|statistical)\b", IntentCategory.QUALITY, IntentAction.GET_SPC, ["get_spc_analysis"], False),
    (r"\b(quality|predict|forecast)\b.*\b(score|prediction|quality)?\b", IntentCategory.QUALITY, IntentAction.PREDICT_QUALITY, ["predict_quality"], False),
    (r"\b(capability|cpk?|ppk?)\b", IntentCategory.QUALITY, IntentAction.GET_CAPABILITY, ["get_process_capability"], False),

    # Diagnostic
    (r"\b(alarm|error|fault)\s*(code)?\s*(\d+)?\b", IntentCategory.DIAGNOSTIC, IntentAction.DIAGNOSE_ALARM, ["diagnose_alarm"], False),
    (r"\b(troubleshoot|diagnos|debug|fix|why)\b", IntentCategory.DIAGNOSTIC, IntentAction.TROUBLESHOOT, ["diagnose_alarm", "get_machine_health"], False),
    (r"\b(health|condition|mainten)\b", IntentCategory.DIAGNOSTIC, IntentAction.GET_HEALTH, ["get_machine_health"], False),

    # Approval
    (r"\b(approv)\w*\s*(program|nc|g-?code)?\b", IntentCategory.APPROVAL, IntentAction.APPROVE_PROGRAM, ["approve_nc_program"], True),
    (r"\b(reject|deny|decline)\s*(program|nc|g-?code)?\b", IntentCategory.APPROVAL, IntentAction.REJECT_PROGRAM, ["reject_nc_program"], True),
    (r"\b(pending|wait(ing)?|queue)\s*(approval)?\b", IntentCategory.APPROVAL, IntentAction.LIST_PENDING, [], False),

    # Job Management
    (r"\b(start|begin|run)\s*(job|program|part)?\b", IntentCategory.JOB_MANAGEMENT, IntentAction.START_JOB, ["send_gcode"], True),
    (r"\b(pause|hold)\s*(job)?\b", IntentCategory.JOB_MANAGEMENT, IntentAction.PAUSE_JOB, ["feed_hold"], False),
    (r"\b(cancel|abort|stop)\s*(job|program)?\b", IntentCategory.JOB_MANAGEMENT, IntentAction.CANCEL_JOB, ["feed_hold"], True),
    (r"\b(job|program)\s*(status|progress)\b", IntentCategory.JOB_MANAGEMENT, IntentAction.GET_JOB_STATUS, ["get_machine_status"], False),

    # Setup
    (r"\b(setup|set\s*up|prepare|configure)\b", IntentCategory.SETUP, IntentAction.SETUP_GUIDANCE, [], False),

    # Help
    (r"\b(help|assist|support|how\s+do\s+i)\b", IntentCategory.HELP, IntentAction.GET_HELP, [], False),
    (r"\b(commands?|what\s+can\s+you|capabilities)\b", IntentCategory.HELP, IntentAction.LIST_COMMANDS, [], False),

    # Conversation
    (r"\b(hello|hi|hey|good\s+(morning|afternoon|evening))\b", IntentCategory.CONVERSATION, IntentAction.GREETING, [], False),
    (r"\b(thanks?|thank\s+you|appreciate)\b", IntentCategory.CONVERSATION, IntentAction.THANKS, [], False),
    (r"\b(yes|yeah|yep|confirm|ok|okay|sure|go\s+ahead|proceed)\b", IntentCategory.CONVERSATION, IntentAction.CONFIRM, [], False),
    (r"\b(no|nope|cancel|don'?t|stop|abort|never\s*mind)\b", IntentCategory.CONVERSATION, IntentAction.DENY, [], False),
]


class IntentParser:
    """
    Parse user intents from natural language input.

    Uses pattern matching and entity extraction to determine
    what the user wants to do.
    """

    def __init__(self):
        """Initialize intent parser."""
        self.patterns = INTENT_PATTERNS
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), category, action, tools, confirm)
            for pattern, category, action, tools, confirm in self.patterns
        ]

    def parse(self, text: str) -> ParsedIntent:
        """
        Parse user input to determine intent.

        Args:
            text: User input text

        Returns:
            ParsedIntent with category, action, and extracted entities
        """
        text = text.strip()
        if not text:
            return ParsedIntent(
                category=IntentCategory.UNKNOWN,
                action=IntentAction.UNKNOWN,
                confidence=0.0,
                original_text=text,
            )

        # Try pattern matching
        best_match = None
        best_confidence = 0.0

        for compiled_pattern, category, action, tools, confirm in self.compiled_patterns:
            match = compiled_pattern.search(text)
            if match:
                # Calculate confidence based on match coverage
                coverage = len(match.group()) / len(text)
                confidence = min(0.5 + coverage * 0.5, 1.0)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = (match, category, action, tools, confirm)

        if best_match:
            match, category, action, tools, confirm = best_match

            # Extract entities
            entities = self._extract_entities(text, category, action, match)

            return ParsedIntent(
                category=category,
                action=action,
                confidence=best_confidence,
                entities=entities,
                original_text=text,
                requires_confirmation=confirm,
                suggested_tools=tools,
            )

        # No pattern matched
        return ParsedIntent(
            category=IntentCategory.UNKNOWN,
            action=IntentAction.UNKNOWN,
            confidence=0.0,
            original_text=text,
        )

    def _extract_entities(
        self,
        text: str,
        category: IntentCategory,
        action: IntentAction,
        match: re.Match,
    ) -> Dict[str, Any]:
        """Extract entities from the matched text."""
        entities = {}

        # Extract axis and distance for jog
        if action == IntentAction.JOG_AXIS:
            axis_match = re.search(r'\b([xyz])\s*([-+]?\d+(\.\d+)?)', text, re.IGNORECASE)
            if axis_match:
                entities["axis"] = axis_match.group(1).upper()
                entities["distance"] = float(axis_match.group(2))

        # Extract axis for zero/home
        elif action in (IntentAction.ZERO_AXIS, IntentAction.HOME_MACHINE):
            axis_match = re.search(r'\b([xyz]+)\b', text, re.IGNORECASE)
            if axis_match:
                entities["axes"] = axis_match.group(1).upper()
            else:
                entities["axes"] = "ALL"

        # Extract G-code command
        elif action == IntentAction.SEND_GCODE:
            gcode_match = re.search(r'[:\-]?\s*([gm]\d+[^\n]*)', text, re.IGNORECASE)
            if gcode_match:
                entities["gcode"] = gcode_match.group(1).strip()

        # Extract alarm code
        elif action == IntentAction.DIAGNOSE_ALARM:
            code_match = re.search(r'\b(\d+)\b', text)
            if code_match:
                entities["alarm_code"] = int(code_match.group(1))

        # Extract program name for approval
        elif action in (IntentAction.APPROVE_PROGRAM, IntentAction.REJECT_PROGRAM):
            # Look for program name pattern
            name_match = re.search(r'(?:program|file|nc)\s+["\']?([a-zA-Z0-9_\-\.]+)["\']?', text, re.IGNORECASE)
            if name_match:
                entities["program_name"] = name_match.group(1)

        # Extract feature for quality/SPC
        elif action in (IntentAction.GET_SPC, IntentAction.GET_CAPABILITY):
            feature_match = re.search(r'for\s+["\']?(\w+)["\']?', text, re.IGNORECASE)
            if feature_match:
                entities["feature"] = feature_match.group(1)

        # Extract confirmation ID
        elif action == IntentAction.CONFIRM:
            confirm_match = re.search(r'confirm[_\-]?(\w+)', text, re.IGNORECASE)
            if confirm_match:
                entities["confirmation_id"] = f"confirm_{confirm_match.group(1)}"

        return entities

    def is_confirmation(self, text: str) -> bool:
        """Check if input is a confirmation response."""
        intent = self.parse(text)
        return intent.action == IntentAction.CONFIRM

    def is_denial(self, text: str) -> bool:
        """Check if input is a denial response."""
        intent = self.parse(text)
        return intent.action == IntentAction.DENY

    def is_emergency(self, text: str) -> bool:
        """Check if input is an emergency command."""
        intent = self.parse(text)
        return intent.category == IntentCategory.EMERGENCY

    def extract_gcode(self, text: str) -> Optional[str]:
        """Extract G-code command from text."""
        # Look for G-code patterns
        patterns = [
            r'["\']([gm]\d+[^"\']*)["\']',  # Quoted
            r':\s*([gm]\d+.*?)(?:\.|$)',     # After colon
            r'\b([gm]\d+(?:\s+[a-z][\d\.]+)*)',  # Bare G-code
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def get_intent_description(self, intent: ParsedIntent) -> str:
        """Get human-readable description of the intent."""
        descriptions = {
            IntentAction.GET_STATUS: "Get machine status",
            IntentAction.GET_POSITION: "Get current position",
            IntentAction.CHECK_CONNECTION: "Check connection status",
            IntentAction.SEND_GCODE: "Send G-code command",
            IntentAction.JOG_AXIS: f"Jog {intent.entities.get('axis', 'axis')} by {intent.entities.get('distance', '?')}mm",
            IntentAction.HOME_MACHINE: f"Home {intent.entities.get('axes', 'all')} axes",
            IntentAction.ZERO_AXIS: f"Zero {intent.entities.get('axes', 'axis')}",
            IntentAction.FEED_HOLD: "Feed hold (pause motion)",
            IntentAction.EMERGENCY_STOP: "Emergency stop",
            IntentAction.RESUME: "Resume operation",
            IntentAction.ANALYZE_TOOLPATH: "Analyze toolpath",
            IntentAction.DIAGNOSE_ALARM: f"Diagnose alarm {intent.entities.get('alarm_code', '')}",
            IntentAction.GET_SPC: "Get SPC analysis",
            IntentAction.PREDICT_QUALITY: "Predict quality",
            IntentAction.APPROVE_PROGRAM: f"Approve program {intent.entities.get('program_name', '')}",
            IntentAction.REJECT_PROGRAM: f"Reject program {intent.entities.get('program_name', '')}",
        }

        return descriptions.get(intent.action, f"Execute {intent.action.value}")
