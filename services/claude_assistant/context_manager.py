"""
Context Manager for Claude Assistant.

Manages conversation context, session state, and manufacturing context.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ConversationRole(Enum):
    """Conversation message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class Message:
    """A conversation message."""
    role: ConversationRole
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class MachineContext:
    """Current machine state context."""
    machine_id: str = "default"
    controller_type: str = "tinyg"
    connected: bool = False
    state: str = "unknown"
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    current_job: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)
    alarms: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class QualityContext:
    """Current quality/SPC context."""
    last_prediction_score: Optional[float] = None
    risk_level: str = "unknown"
    active_alerts: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SessionContext:
    """Complete session context."""
    session_id: str
    user_id: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    messages: List[Message] = field(default_factory=list)
    machine_context: MachineContext = field(default_factory=MachineContext)
    quality_context: QualityContext = field(default_factory=QualityContext)
    pending_confirmations: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """
    Manages conversation and manufacturing context for Claude Assistant.

    Responsibilities:
    - Maintain conversation history
    - Track machine state
    - Manage pending confirmations for dangerous operations
    - Provide context for Claude API calls
    """

    def __init__(self, max_history: int = 50, session_timeout_minutes: int = 30):
        """
        Initialize context manager.

        Args:
            max_history: Maximum number of messages to retain
            session_timeout_minutes: Session timeout in minutes
        """
        self.max_history = max_history
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.sessions: Dict[str, SessionContext] = {}

    def create_session(self, session_id: str, user_id: Optional[str] = None) -> SessionContext:
        """Create a new session context."""
        session = SessionContext(
            session_id=session_id,
            user_id=user_id,
        )
        self.sessions[session_id] = session
        logger.info(f"Created new session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Get session by ID, returns None if expired or not found."""
        session = self.sessions.get(session_id)
        if session:
            if datetime.utcnow() - session.last_activity > self.session_timeout:
                logger.info(f"Session expired: {session_id}")
                del self.sessions[session_id]
                return None
            return session
        return None

    def get_or_create_session(self, session_id: str, user_id: Optional[str] = None) -> SessionContext:
        """Get existing session or create new one."""
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id, user_id)
        return session

    def add_message(
        self,
        session_id: str,
        role: ConversationRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Message:
        """Add a message to the session."""
        session = self.get_or_create_session(session_id)

        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
            tool_calls=tool_calls or [],
            tool_results=tool_results or [],
        )

        session.messages.append(message)
        session.last_activity = datetime.utcnow()

        # Trim history if needed
        if len(session.messages) > self.max_history:
            session.messages = session.messages[-self.max_history:]

        return message

    def update_machine_context(
        self,
        session_id: str,
        machine_id: Optional[str] = None,
        controller_type: Optional[str] = None,
        connected: Optional[bool] = None,
        state: Optional[str] = None,
        position: Optional[Dict[str, float]] = None,
        current_job: Optional[str] = None,
        alarms: Optional[List[Dict[str, Any]]] = None,
    ) -> MachineContext:
        """Update machine context for the session."""
        session = self.get_or_create_session(session_id)
        ctx = session.machine_context

        if machine_id is not None:
            ctx.machine_id = machine_id
        if controller_type is not None:
            ctx.controller_type = controller_type
        if connected is not None:
            ctx.connected = connected
        if state is not None:
            ctx.state = state
        if position is not None:
            ctx.position = position
        if current_job is not None:
            ctx.current_job = current_job
        if alarms is not None:
            ctx.alarms = alarms

        ctx.last_updated = datetime.utcnow()
        return ctx

    def update_quality_context(
        self,
        session_id: str,
        prediction_score: Optional[float] = None,
        risk_level: Optional[str] = None,
        active_alerts: Optional[List[str]] = None,
    ) -> QualityContext:
        """Update quality context for the session."""
        session = self.get_or_create_session(session_id)
        ctx = session.quality_context

        if prediction_score is not None:
            ctx.last_prediction_score = prediction_score
        if risk_level is not None:
            ctx.risk_level = risk_level
        if active_alerts is not None:
            ctx.active_alerts = active_alerts

        ctx.last_updated = datetime.utcnow()
        return ctx

    def add_pending_confirmation(
        self,
        session_id: str,
        action: str,
        description: str,
        params: Dict[str, Any],
        expires_in_seconds: int = 60,
    ) -> str:
        """
        Add a pending confirmation for a dangerous action.

        Returns confirmation ID that user must reference to confirm.
        """
        session = self.get_or_create_session(session_id)

        confirmation_id = f"confirm_{int(time.time() * 1000)}"
        confirmation = {
            "id": confirmation_id,
            "action": action,
            "description": description,
            "params": params,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in_seconds),
        }

        session.pending_confirmations.append(confirmation)
        logger.info(f"Added pending confirmation: {confirmation_id} for {action}")

        return confirmation_id

    def get_pending_confirmation(
        self,
        session_id: str,
        confirmation_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get and remove a pending confirmation if valid."""
        session = self.get_session(session_id)
        if not session:
            return None

        now = datetime.utcnow()
        for i, conf in enumerate(session.pending_confirmations):
            if conf["id"] == confirmation_id:
                if conf["expires_at"] > now:
                    # Remove and return
                    return session.pending_confirmations.pop(i)
                else:
                    # Expired, remove it
                    session.pending_confirmations.pop(i)
                    return None

        return None

    def clear_expired_confirmations(self, session_id: str) -> int:
        """Clear expired confirmations, returns count removed."""
        session = self.get_session(session_id)
        if not session:
            return 0

        now = datetime.utcnow()
        original_count = len(session.pending_confirmations)
        session.pending_confirmations = [
            c for c in session.pending_confirmations
            if c["expires_at"] > now
        ]
        return original_count - len(session.pending_confirmations)

    def get_conversation_for_api(
        self,
        session_id: str,
        include_system: bool = True,
        max_messages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history formatted for Claude API.

        Returns list of messages in Claude API format.
        """
        session = self.get_session(session_id)
        if not session:
            return []

        messages = session.messages
        if max_messages:
            messages = messages[-max_messages:]

        api_messages = []
        for msg in messages:
            if msg.role == ConversationRole.SYSTEM and not include_system:
                continue

            api_msg = {
                "role": msg.role.value,
                "content": msg.content,
            }

            # Add tool use if present
            if msg.tool_calls:
                api_msg["tool_calls"] = msg.tool_calls

            api_messages.append(api_msg)

        return api_messages

    def get_system_context(self, session_id: str) -> str:
        """
        Generate system context string for Claude.

        Includes current machine state, quality context, and pending items.
        """
        session = self.get_session(session_id)
        if not session:
            return ""

        mc = session.machine_context
        qc = session.quality_context

        context_parts = [
            "## Current Manufacturing Context",
            "",
            "### Machine Status",
            f"- Machine ID: {mc.machine_id}",
            f"- Controller: {mc.controller_type}",
            f"- Connected: {'Yes' if mc.connected else 'No'}",
            f"- State: {mc.state}",
            f"- Position: X={mc.position.get('x', 0):.3f}, Y={mc.position.get('y', 0):.3f}, Z={mc.position.get('z', 0):.3f}",
        ]

        if mc.current_job:
            context_parts.append(f"- Current Job: {mc.current_job}")

        if mc.alarms:
            context_parts.append(f"- Active Alarms: {len(mc.alarms)}")
            for alarm in mc.alarms[:3]:  # Show max 3
                context_parts.append(f"  - {alarm.get('code', 'N/A')}: {alarm.get('message', 'Unknown')}")

        context_parts.extend([
            "",
            "### Quality Status",
            f"- Risk Level: {qc.risk_level}",
        ])

        if qc.last_prediction_score is not None:
            context_parts.append(f"- Last Quality Score: {qc.last_prediction_score:.1f}/100")

        if qc.active_alerts:
            context_parts.append(f"- Active Quality Alerts: {len(qc.active_alerts)}")

        if session.pending_confirmations:
            context_parts.extend([
                "",
                "### Pending Confirmations",
                f"There are {len(session.pending_confirmations)} action(s) awaiting confirmation.",
            ])

        return "\n".join(context_parts)

    def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions, returns count removed."""
        now = datetime.utcnow()
        expired = [
            sid for sid, session in self.sessions.items()
            if now - session.last_activity > self.session_timeout
        ]

        for sid in expired:
            del self.sessions[sid]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

        return len(expired)

    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about active sessions."""
        now = datetime.utcnow()
        active_count = 0
        total_messages = 0

        for session in self.sessions.values():
            if now - session.last_activity <= self.session_timeout:
                active_count += 1
                total_messages += len(session.messages)

        return {
            "total_sessions": len(self.sessions),
            "active_sessions": active_count,
            "total_messages": total_messages,
        }
