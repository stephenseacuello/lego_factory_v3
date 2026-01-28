"""
Real-time Shop Floor Co-pilot Service.

Provides Claude-powered assistance with live machine context:
- Real-time status monitoring
- Proactive issue detection and notification
- Context-aware assistance
- Shift handoff summaries
"""

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import json

from .event_processor import EventProcessor, MachineEvent, EventType
from .notification_manager import (
    NotificationManager,
    NotificationConfig,
    Notification,
    NotificationChannel,
    NotificationPriority,
)

logger = logging.getLogger(__name__)


class CopilotMode(Enum):
    """Copilot operating modes."""
    MONITORING = "monitoring"      # Passive monitoring
    ASSISTING = "assisting"        # Active assistance
    DIAGNOSTIC = "diagnostic"      # Troubleshooting mode
    MAINTENANCE = "maintenance"    # Maintenance guidance


@dataclass
class CopilotConfig:
    """Configuration for the real-time copilot."""
    # Claude API
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-sonnet-4-20250514"

    # Monitoring
    status_poll_interval: float = 1.0  # seconds
    alert_cooldown: float = 60.0       # seconds between same alert

    # Proactive features
    enable_proactive_diagnosis: bool = True
    enable_quality_monitoring: bool = True
    enable_maintenance_alerts: bool = True
    enable_shift_summaries: bool = True

    # Shift settings
    shift_start_hour: int = 6   # 6 AM
    shift_length_hours: int = 8

    # Notification settings
    notification_config: NotificationConfig = field(
        default_factory=NotificationConfig
    )


@dataclass
class MachineContext:
    """Current context for a machine."""
    machine_id: str
    status: str = "unknown"
    position: Dict[str, float] = field(default_factory=dict)
    current_job: Optional[str] = None
    job_progress: float = 0.0
    alarms: List[str] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)
    sensor_data: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Maintains conversation context with a user."""
    session_id: str
    machine_id: Optional[str] = None
    messages: List[Dict[str, str]] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    mode: CopilotMode = CopilotMode.ASSISTING


class RealtimeCopilot:
    """
    Real-time shop floor co-pilot powered by Claude.

    Features:
    - Live machine context awareness
    - Proactive issue detection and notification
    - Natural language interaction
    - Shift handoff summaries
    """

    def __init__(self, config: Optional[CopilotConfig] = None):
        """Initialize the copilot."""
        self.config = config or CopilotConfig()

        # Core components
        self.event_processor = EventProcessor()
        self.notification_manager = NotificationManager(
            self.config.notification_config
        )

        # State
        self._machines: Dict[str, MachineContext] = {}
        self._conversations: Dict[str, ConversationContext] = {}
        self._shift_events: List[MachineEvent] = []
        self._running = False
        self._tasks: List[asyncio.Task] = []

        # Claude client (lazy init)
        self._claude_client = None

        # Register event handlers
        self._setup_event_handlers()

    def _setup_event_handlers(self):
        """Register handlers for different event types."""
        self.event_processor.register_handler(
            EventType.ALARM,
            self._handle_alarm_event
        )
        self.event_processor.register_handler(
            EventType.ERROR,
            self._handle_error_event
        )
        self.event_processor.register_handler(
            EventType.SPC_VIOLATION,
            self._handle_spc_violation
        )
        self.event_processor.register_handler(
            EventType.MAINTENANCE_DUE,
            self._handle_maintenance_due
        )
        self.event_processor.register_handler(
            EventType.JOB_COMPLETED,
            self._handle_job_completed
        )

    @property
    def claude_client(self):
        """Lazy initialization of Claude client."""
        if self._claude_client is None:
            if self.config.anthropic_api_key:
                try:
                    import anthropic
                    self._claude_client = anthropic.Anthropic(
                        api_key=self.config.anthropic_api_key
                    )
                except ImportError:
                    logger.warning("anthropic package not installed")
        return self._claude_client

    async def start(self):
        """Start the copilot service."""
        if self._running:
            return

        self._running = True
        logger.info("Starting real-time copilot service")

        # Start background tasks
        if self.config.enable_shift_summaries:
            self._tasks.append(
                asyncio.create_task(self._shift_summary_task())
            )

        if self.config.enable_quality_monitoring:
            self._tasks.append(
                asyncio.create_task(self._quality_monitoring_task())
            )

        # Start notification batch processing
        self._tasks.append(
            asyncio.create_task(self._notification_batch_task())
        )

    async def stop(self):
        """Stop the copilot service."""
        self._running = False

        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()
        logger.info("Copilot service stopped")

    def update_machine_context(
        self,
        machine_id: str,
        status: Optional[str] = None,
        position: Optional[Dict[str, float]] = None,
        job: Optional[str] = None,
        progress: Optional[float] = None,
        alarms: Optional[List[str]] = None,
        sensor_data: Optional[Dict[str, Any]] = None,
    ):
        """Update the context for a machine."""
        if machine_id not in self._machines:
            self._machines[machine_id] = MachineContext(machine_id=machine_id)

        ctx = self._machines[machine_id]

        if status is not None:
            # Check for status change events
            if ctx.status != status:
                self.event_processor.process_event(MachineEvent(
                    id=f"status-{datetime.now().timestamp()}",
                    event_type=EventType.STATUS_CHANGE,
                    machine_id=machine_id,
                    data={"old_status": ctx.status, "new_status": status},
                    message=f"Machine status changed: {ctx.status} → {status}",
                ))
            ctx.status = status

        if position is not None:
            ctx.position = position

        if job is not None:
            ctx.current_job = job

        if progress is not None:
            ctx.job_progress = progress

        if alarms is not None:
            # Check for new alarms
            new_alarms = set(alarms) - set(ctx.alarms)
            for alarm in new_alarms:
                self.event_processor.process_event(MachineEvent(
                    id=f"alarm-{datetime.now().timestamp()}",
                    event_type=EventType.ALARM,
                    machine_id=machine_id,
                    severity="high",
                    data={"alarm_code": alarm},
                    message=f"Alarm triggered: {alarm}",
                ))
            ctx.alarms = alarms

        if sensor_data is not None:
            ctx.sensor_data = sensor_data

        ctx.last_update = datetime.now()

    def get_machine_context(self, machine_id: str) -> Optional[MachineContext]:
        """Get the current context for a machine."""
        return self._machines.get(machine_id)

    def get_all_machines(self) -> Dict[str, MachineContext]:
        """Get context for all machines."""
        return self._machines.copy()

    async def chat(
        self,
        session_id: str,
        message: str,
        machine_id: Optional[str] = None,
    ) -> str:
        """
        Process a chat message from the user.

        Args:
            session_id: Unique session identifier
            message: User's message
            machine_id: Optional machine context

        Returns:
            Copilot's response
        """
        # Get or create conversation context
        if session_id not in self._conversations:
            self._conversations[session_id] = ConversationContext(
                session_id=session_id,
                machine_id=machine_id,
            )

        ctx = self._conversations[session_id]
        ctx.last_activity = datetime.now()

        if machine_id:
            ctx.machine_id = machine_id

        # Add user message
        ctx.messages.append({"role": "user", "content": message})

        # Build system prompt with machine context
        system_prompt = self._build_system_prompt(ctx)

        # Get response from Claude
        response = await self._get_claude_response(
            system_prompt,
            ctx.messages,
        )

        # Add assistant response
        ctx.messages.append({"role": "assistant", "content": response})

        # Keep conversation history manageable
        if len(ctx.messages) > 20:
            ctx.messages = ctx.messages[-20:]

        return response

    def _build_system_prompt(self, ctx: ConversationContext) -> str:
        """Build system prompt with current machine context."""
        prompt_parts = [
            "You are a helpful CNC shop floor co-pilot assistant.",
            "You help operators with machine status, troubleshooting, and job management.",
            "Be concise and technical when appropriate.",
            "",
        ]

        # Add machine context if available
        if ctx.machine_id and ctx.machine_id in self._machines:
            machine = self._machines[ctx.machine_id]
            prompt_parts.extend([
                f"Current Machine: {machine.machine_id}",
                f"Status: {machine.status}",
                f"Position: X={machine.position.get('x', 0):.3f}, "
                f"Y={machine.position.get('y', 0):.3f}, "
                f"Z={machine.position.get('z', 0):.3f}",
            ])

            if machine.current_job:
                prompt_parts.append(
                    f"Current Job: {machine.current_job} "
                    f"({machine.job_progress:.1f}% complete)"
                )

            if machine.alarms:
                prompt_parts.append(f"Active Alarms: {', '.join(machine.alarms)}")

            prompt_parts.append("")

        # Add fleet overview
        if self._machines:
            prompt_parts.append("Fleet Overview:")
            for mid, m in self._machines.items():
                status_icon = "🟢" if m.status == "idle" else (
                    "🔴" if m.alarms else "🟡"
                )
                prompt_parts.append(f"  {status_icon} {mid}: {m.status}")
            prompt_parts.append("")

        # Add recent events
        recent_events = self.event_processor.get_recent_events(limit=5)
        if recent_events:
            prompt_parts.append("Recent Events:")
            for event in recent_events:
                prompt_parts.append(
                    f"  - [{event.timestamp.strftime('%H:%M')}] "
                    f"{event.message}"
                )

        return "\n".join(prompt_parts)

    async def _get_claude_response(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> str:
        """Get a response from Claude."""
        if not self.claude_client:
            return self._get_fallback_response(messages[-1]["content"])

        try:
            response = self.claude_client.messages.create(
                model=self.config.claude_model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return self._get_fallback_response(messages[-1]["content"])

    def _get_fallback_response(self, message: str) -> str:
        """Generate a fallback response when Claude is unavailable."""
        message_lower = message.lower()

        if "status" in message_lower:
            if self._machines:
                lines = ["Current machine status:"]
                for mid, m in self._machines.items():
                    lines.append(f"  {mid}: {m.status}")
                return "\n".join(lines)
            return "No machines are currently connected."

        if "alarm" in message_lower:
            alarms = []
            for mid, m in self._machines.items():
                if m.alarms:
                    alarms.extend([f"{mid}: {a}" for a in m.alarms])
            if alarms:
                return "Active alarms:\n" + "\n".join(f"  - {a}" for a in alarms)
            return "No active alarms."

        if "help" in message_lower:
            return (
                "I can help you with:\n"
                "  - Machine status checks\n"
                "  - Alarm diagnosis\n"
                "  - Job progress tracking\n"
                "  - Quality monitoring\n"
                "Try asking: 'What's the status of the mill?'"
            )

        return (
            "I'm the shop floor co-pilot. I can help with machine status, "
            "alarms, jobs, and quality. What would you like to know?"
        )

    async def _handle_alarm_event(self, event: MachineEvent):
        """Handle alarm events with proactive diagnosis."""
        if not self.config.enable_proactive_diagnosis:
            return

        # Get diagnosis from Claude
        diagnosis = await self._diagnose_alarm(
            event.machine_id,
            event.data.get("alarm_code", "unknown"),
        )

        # Send notification
        notification = self.notification_manager.create_notification(
            title=f"Alarm on {event.machine_id}",
            message=f"{event.message}\n\nDiagnosis: {diagnosis}",
            priority="high",
            channels=["websocket", "slack"],
            machine_id=event.machine_id,
            data={"alarm": event.data, "diagnosis": diagnosis},
        )

        await self.notification_manager.send(notification)

        # Track for shift summary
        self._shift_events.append(event)

    async def _handle_error_event(self, event: MachineEvent):
        """Handle error events."""
        notification = self.notification_manager.create_notification(
            title=f"Error on {event.machine_id}",
            message=event.message,
            priority="medium",
            channels=["websocket"],
            machine_id=event.machine_id,
        )

        await self.notification_manager.send(notification)
        self._shift_events.append(event)

    async def _handle_spc_violation(self, event: MachineEvent):
        """Handle SPC control limit violations."""
        if not self.config.enable_quality_monitoring:
            return

        notification = self.notification_manager.create_notification(
            title=f"Quality Alert: {event.machine_id}",
            message=event.message,
            priority="high",
            channels=["websocket", "slack", "email"],
            machine_id=event.machine_id,
            data=event.data,
        )

        await self.notification_manager.send(notification)
        self._shift_events.append(event)

    async def _handle_maintenance_due(self, event: MachineEvent):
        """Handle maintenance due events."""
        if not self.config.enable_maintenance_alerts:
            return

        notification = self.notification_manager.create_notification(
            title=f"Maintenance Due: {event.machine_id}",
            message=event.message,
            priority="medium",
            channels=["websocket", "email"],
            machine_id=event.machine_id,
            data=event.data,
        )

        await self.notification_manager.send(notification)

    async def _handle_job_completed(self, event: MachineEvent):
        """Handle job completion events."""
        notification = self.notification_manager.create_notification(
            title=f"Job Complete: {event.machine_id}",
            message=event.message,
            priority="low",
            channels=["websocket"],
            machine_id=event.machine_id,
            data=event.data,
        )

        await self.notification_manager.send(notification)
        self._shift_events.append(event)

    async def _diagnose_alarm(
        self,
        machine_id: str,
        alarm_code: str,
    ) -> str:
        """Get AI diagnosis for an alarm."""
        if not self.claude_client:
            return f"Alarm {alarm_code} triggered. Check machine manual for details."

        try:
            machine = self._machines.get(machine_id)
            context = ""
            if machine:
                context = (
                    f"Machine Status: {machine.status}\n"
                    f"Position: {machine.position}\n"
                    f"Current Job: {machine.current_job or 'None'}"
                )

            response = self.claude_client.messages.create(
                model=self.config.claude_model,
                max_tokens=300,
                system=(
                    "You are a CNC machine diagnostic expert. "
                    "Provide brief, actionable diagnosis and resolution steps."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Diagnose this CNC alarm:\n"
                        f"Machine: {machine_id}\n"
                        f"Alarm Code: {alarm_code}\n"
                        f"{context}\n\n"
                        f"What's the likely cause and how to resolve it?"
                    ),
                }],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Diagnosis error: {e}")
            return f"Alarm {alarm_code} triggered. Manual review recommended."

    async def generate_shift_summary(self) -> Dict[str, Any]:
        """Generate a summary of the current shift."""
        now = datetime.now()
        shift_start = now.replace(
            hour=self.config.shift_start_hour,
            minute=0,
            second=0,
            microsecond=0,
        )

        if now.hour < self.config.shift_start_hour:
            shift_start -= timedelta(days=1)

        # Filter events for this shift
        shift_events = [
            e for e in self._shift_events
            if e.timestamp >= shift_start
        ]

        # Calculate metrics
        alarms = [e for e in shift_events if e.event_type == EventType.ALARM]
        jobs_completed = [
            e for e in shift_events if e.event_type == EventType.JOB_COMPLETED
        ]
        spc_violations = [
            e for e in shift_events if e.event_type == EventType.SPC_VIOLATION
        ]

        summary = {
            "shift_start": shift_start.isoformat(),
            "generated_at": now.isoformat(),
            "metrics": {
                "total_events": len(shift_events),
                "alarms": len(alarms),
                "jobs_completed": len(jobs_completed),
                "quality_issues": len(spc_violations),
            },
            "machines": {},
            "notable_events": [],
        }

        # Machine-specific summaries
        for mid, machine in self._machines.items():
            machine_events = [e for e in shift_events if e.machine_id == mid]
            summary["machines"][mid] = {
                "current_status": machine.status,
                "events": len(machine_events),
                "alarms": len([
                    e for e in machine_events if e.event_type == EventType.ALARM
                ]),
            }

        # Notable events (high severity)
        notable = [
            e for e in shift_events if e.severity in ("high", "critical")
        ]
        summary["notable_events"] = [
            {
                "time": e.timestamp.strftime("%H:%M"),
                "machine": e.machine_id,
                "message": e.message,
            }
            for e in notable[:10]
        ]

        # Get AI summary if available
        if self.claude_client and shift_events:
            try:
                events_text = "\n".join([
                    f"[{e.timestamp.strftime('%H:%M')}] {e.machine_id}: {e.message}"
                    for e in shift_events[-20:]
                ])

                response = self.claude_client.messages.create(
                    model=self.config.claude_model,
                    max_tokens=500,
                    system="Generate a brief shift handoff summary for incoming operators.",
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Summarize this shift for handoff:\n\n"
                            f"Metrics:\n"
                            f"- Jobs completed: {len(jobs_completed)}\n"
                            f"- Alarms: {len(alarms)}\n"
                            f"- Quality issues: {len(spc_violations)}\n\n"
                            f"Recent events:\n{events_text}"
                        ),
                    }],
                )
                summary["ai_summary"] = response.content[0].text
            except Exception as e:
                logger.error(f"Shift summary generation error: {e}")

        return summary

    async def _shift_summary_task(self):
        """Background task to generate shift summaries."""
        while self._running:
            try:
                now = datetime.now()
                shift_end_hour = (
                    self.config.shift_start_hour +
                    self.config.shift_length_hours
                ) % 24

                # Check if we're near shift end (within 15 minutes)
                minutes_to_shift_end = (
                    (shift_end_hour - now.hour) * 60 - now.minute
                ) % (24 * 60)

                if 0 <= minutes_to_shift_end <= 15:
                    summary = await self.generate_shift_summary()

                    # Send shift summary notification
                    notification = self.notification_manager.create_notification(
                        title="Shift Summary Ready",
                        message=summary.get(
                            "ai_summary",
                            f"Shift complete: {summary['metrics']['jobs_completed']} jobs, "
                            f"{summary['metrics']['alarms']} alarms"
                        ),
                        priority="low",
                        channels=["slack", "email"],
                    )
                    await self.notification_manager.send(notification)

                    # Clear shift events
                    self._shift_events.clear()

                    # Wait until next shift
                    await asyncio.sleep(self.config.shift_length_hours * 3600 - 900)
                else:
                    # Check every 5 minutes
                    await asyncio.sleep(300)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Shift summary task error: {e}")
                await asyncio.sleep(60)

    async def _quality_monitoring_task(self):
        """Background task for quality monitoring."""
        while self._running:
            try:
                # Check quality metrics periodically
                for machine in self._machines.values():
                    if machine.sensor_data:
                        # Check for anomalies in sensor data
                        await self._check_quality_metrics(machine)

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Quality monitoring error: {e}")
                await asyncio.sleep(60)

    async def _check_quality_metrics(self, machine: MachineContext):
        """Check quality metrics for a machine."""
        # Implement quality checks based on sensor data
        # This would integrate with the SPC service
        pass

    async def _notification_batch_task(self):
        """Background task to process batched notifications."""
        while self._running:
            try:
                await self.notification_manager.process_batch()
                await asyncio.sleep(self.config.notification_config.batch_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Notification batch error: {e}")
                await asyncio.sleep(30)


# Module-level instance for easy access
_copilot_instance: Optional[RealtimeCopilot] = None


def get_copilot() -> RealtimeCopilot:
    """Get the global copilot instance."""
    global _copilot_instance
    if _copilot_instance is None:
        _copilot_instance = RealtimeCopilot()
    return _copilot_instance


def configure_copilot(config: CopilotConfig):
    """Configure the global copilot instance."""
    global _copilot_instance
    _copilot_instance = RealtimeCopilot(config)
    return _copilot_instance
