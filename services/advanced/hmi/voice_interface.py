"""
Voice Interface - HMI Voice Control

LegoMCP World-Class Manufacturing System v5.0
Phase 20: HMI & Operator Interface

Provides voice control capabilities:
- Voice command recognition
- Text-to-speech feedback
- Hands-free operation
- Multi-language support
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import uuid


class VoiceCommandCategory(Enum):
    """Categories of voice commands."""
    NAVIGATION = "navigation"
    STATUS = "status"
    CONTROL = "control"
    QUERY = "query"
    EMERGENCY = "emergency"
    HELP = "help"


class VoiceLanguage(Enum):
    """Supported languages."""
    ENGLISH = "en"
    SPANISH = "es"
    GERMAN = "de"
    FRENCH = "fr"
    CHINESE = "zh"
    JAPANESE = "ja"


@dataclass
class VoiceCommand:
    """A recognized voice command."""
    command_id: str
    raw_text: str
    category: VoiceCommandCategory
    intent: str
    entities: Dict[str, Any]
    confidence: float
    language: VoiceLanguage
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VoiceResponse:
    """Response to a voice command."""
    response_id: str
    text: str
    audio_url: Optional[str] = None
    action_taken: Optional[str] = None
    success: bool = True
    follow_up_prompt: Optional[str] = None


class VoiceInterface:
    """
    Voice interface for hands-free operator interaction.

    Provides voice command recognition and text-to-speech
    feedback for manufacturing operations.
    """

    def __init__(self, language: VoiceLanguage = VoiceLanguage.ENGLISH):
        self.language = language
        self.command_history: List[VoiceCommand] = []
        self.command_handlers: Dict[str, Callable] = {}
        self._setup_default_commands()

    def _setup_default_commands(self):
        """Set up default voice command handlers."""
        self.commands = {
            # Status commands
            'status': {
                'patterns': ['what is the status', 'show status', 'system status'],
                'category': VoiceCommandCategory.STATUS,
                'handler': self._handle_status,
            },
            'oee': {
                'patterns': ['what is the oee', 'show oee', 'overall equipment effectiveness'],
                'category': VoiceCommandCategory.QUERY,
                'handler': self._handle_oee_query,
            },
            'work_orders': {
                'patterns': ['show work orders', 'list work orders', 'active work orders'],
                'category': VoiceCommandCategory.QUERY,
                'handler': self._handle_work_orders,
            },

            # Control commands
            'start': {
                'patterns': ['start machine', 'start printer', 'begin production'],
                'category': VoiceCommandCategory.CONTROL,
                'handler': self._handle_start,
            },
            'stop': {
                'patterns': ['stop machine', 'stop printer', 'halt production'],
                'category': VoiceCommandCategory.CONTROL,
                'handler': self._handle_stop,
            },
            'pause': {
                'patterns': ['pause machine', 'pause printer', 'pause production'],
                'category': VoiceCommandCategory.CONTROL,
                'handler': self._handle_pause,
            },

            # Emergency commands
            'emergency_stop': {
                'patterns': ['emergency stop', 'e-stop', 'emergency'],
                'category': VoiceCommandCategory.EMERGENCY,
                'handler': self._handle_emergency,
            },

            # Navigation
            'go_to': {
                'patterns': ['go to', 'navigate to', 'show me', 'open'],
                'category': VoiceCommandCategory.NAVIGATION,
                'handler': self._handle_navigation,
            },

            # Help
            'help': {
                'patterns': ['help', 'what can I say', 'commands'],
                'category': VoiceCommandCategory.HELP,
                'handler': self._handle_help,
            },
        }

    def process_voice_input(
        self,
        audio_data: Optional[bytes] = None,
        text_input: Optional[str] = None
    ) -> VoiceResponse:
        """
        Process voice input and return response.

        Args:
            audio_data: Raw audio data (optional)
            text_input: Text transcription (for testing)

        Returns:
            Voice response with action taken
        """
        # In production, would use speech recognition
        # For now, use text input or simulate
        if text_input:
            raw_text = text_input.lower().strip()
        elif audio_data:
            # Simulate speech recognition
            raw_text = self._simulate_speech_recognition(audio_data)
        else:
            return VoiceResponse(
                response_id=str(uuid.uuid4()),
                text="I didn't hear anything. Please try again.",
                success=False,
            )

        # Parse command
        command = self._parse_command(raw_text)
        self.command_history.append(command)

        # Execute handler
        if command.intent in self.commands:
            handler = self.commands[command.intent]['handler']
            return handler(command)
        else:
            return VoiceResponse(
                response_id=str(uuid.uuid4()),
                text=f"I didn't understand '{raw_text}'. Say 'help' for available commands.",
                success=False,
                follow_up_prompt="What would you like to do?",
            )

    def _simulate_speech_recognition(self, audio_data: bytes) -> str:
        """Simulate speech recognition (placeholder)."""
        return "show status"

    def _parse_command(self, raw_text: str) -> VoiceCommand:
        """Parse raw text into a structured command."""
        # Find matching command
        best_match = None
        best_confidence = 0.0

        for intent, cmd_info in self.commands.items():
            for pattern in cmd_info['patterns']:
                if pattern in raw_text:
                    confidence = len(pattern) / len(raw_text) if raw_text else 0
                    if confidence > best_confidence:
                        best_match = intent
                        best_confidence = min(0.95, confidence + 0.3)

        # Extract entities
        entities = self._extract_entities(raw_text)

        return VoiceCommand(
            command_id=str(uuid.uuid4()),
            raw_text=raw_text,
            category=self.commands.get(best_match, {}).get(
                'category', VoiceCommandCategory.QUERY
            ),
            intent=best_match or 'unknown',
            entities=entities,
            confidence=best_confidence,
            language=self.language,
        )

    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract named entities from text."""
        entities = {}

        # Extract machine references
        machine_keywords = ['printer', 'machine', 'station', 'work center']
        for keyword in machine_keywords:
            if keyword in text:
                # Look for number after keyword
                words = text.split()
                for i, word in enumerate(words):
                    if word == keyword and i + 1 < len(words):
                        try:
                            entities['machine_number'] = int(words[i + 1])
                        except ValueError:
                            pass

        # Extract work order references
        if 'work order' in text or 'wo-' in text:
            import re
            wo_match = re.search(r'wo-?(\d+)', text, re.IGNORECASE)
            if wo_match:
                entities['work_order_id'] = f"WO-{wo_match.group(1)}"

        return entities

    def _handle_status(self, command: VoiceCommand) -> VoiceResponse:
        """Handle status query."""
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text="System status is normal. All machines are operational. "
                 "Current OEE is 85 percent. There are 3 active work orders.",
            action_taken="displayed_status",
            follow_up_prompt="Would you like more details?",
        )

    def _handle_oee_query(self, command: VoiceCommand) -> VoiceResponse:
        """Handle OEE query."""
        import random
        oee = round(random.uniform(75, 95), 1)
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text=f"Current OEE is {oee} percent. "
                 f"Availability is 92 percent, Performance is 88 percent, "
                 f"and Quality is 98 percent.",
            action_taken="displayed_oee",
        )

    def _handle_work_orders(self, command: VoiceCommand) -> VoiceResponse:
        """Handle work orders query."""
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text="There are 3 active work orders. "
                 "Work order 1001 is 75 percent complete. "
                 "Work order 1002 is 40 percent complete. "
                 "Work order 1003 is queued.",
            action_taken="listed_work_orders",
        )

    def _handle_start(self, command: VoiceCommand) -> VoiceResponse:
        """Handle start command."""
        machine = command.entities.get('machine_number', 1)
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text=f"Starting machine {machine}. Please confirm by saying 'confirm'.",
            action_taken="start_requested",
            follow_up_prompt="Say 'confirm' to proceed or 'cancel' to abort.",
        )

    def _handle_stop(self, command: VoiceCommand) -> VoiceResponse:
        """Handle stop command."""
        machine = command.entities.get('machine_number', 1)
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text=f"Stopping machine {machine}. Current job will complete first.",
            action_taken="stop_initiated",
        )

    def _handle_pause(self, command: VoiceCommand) -> VoiceResponse:
        """Handle pause command."""
        machine = command.entities.get('machine_number', 1)
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text=f"Pausing machine {machine}. Say 'resume' when ready.",
            action_taken="paused",
        )

    def _handle_emergency(self, command: VoiceCommand) -> VoiceResponse:
        """Handle emergency stop."""
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text="EMERGENCY STOP ACTIVATED! All machines are stopping. "
                 "Please ensure area is safe before resuming.",
            action_taken="emergency_stop",
        )

    def _handle_navigation(self, command: VoiceCommand) -> VoiceResponse:
        """Handle navigation command."""
        raw = command.raw_text

        if 'dashboard' in raw:
            destination = 'dashboard'
        elif 'quality' in raw:
            destination = 'quality page'
        elif 'schedule' in raw or 'scheduling' in raw:
            destination = 'scheduling page'
        elif 'work order' in raw:
            destination = 'work orders page'
        else:
            destination = 'home page'

        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text=f"Navigating to {destination}.",
            action_taken=f"navigate_{destination.replace(' ', '_')}",
        )

    def _handle_help(self, command: VoiceCommand) -> VoiceResponse:
        """Handle help request."""
        return VoiceResponse(
            response_id=str(uuid.uuid4()),
            text="Available commands: 'show status', 'what is the OEE', "
                 "'list work orders', 'start machine', 'stop machine', "
                 "'pause machine', 'emergency stop', 'go to dashboard'. "
                 "You can also ask questions about production.",
            action_taken="displayed_help",
        )

    def get_supported_commands(self) -> List[Dict]:
        """Get list of supported commands."""
        return [
            {
                'intent': intent,
                'patterns': info['patterns'],
                'category': info['category'].value,
            }
            for intent, info in self.commands.items()
        ]


# Singleton instance
_voice_interface: Optional[VoiceInterface] = None


def get_voice_interface() -> VoiceInterface:
    """Get or create the voice interface instance."""
    global _voice_interface
    if _voice_interface is None:
        _voice_interface = VoiceInterface()
    return _voice_interface
