"""
Quality Agent - Autonomous Quality Control

LegoMCP World-Class Manufacturing System v5.0
Phase 17: AI Manufacturing Copilot

Autonomous agent for quality monitoring and intervention:
- Monitors SPC charts for signals
- Analyzes defect patterns
- Triggers quality holds
- Adjusts inspection levels
- Recommends process adjustments
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class QualityAction(str, Enum):
    """Actions the quality agent can take."""
    ALERT = "alert"
    HOLD_PRODUCTION = "hold_production"
    TIGHTEN_INSPECTION = "tighten_inspection"
    RELAX_INSPECTION = "relax_inspection"
    ADJUST_PROCESS = "adjust_process"
    ESCALATE = "escalate"
    LOG_ONLY = "log_only"


@dataclass
class QualityEvent:
    """A quality event for the agent to process."""
    event_type: str
    timestamp: datetime
    machine_id: str
    metric_name: str
    metric_value: float
    threshold: Optional[float] = None
    severity: str = "info"
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityDecision:
    """A decision made by the quality agent."""
    decision_id: str
    timestamp: datetime
    trigger_event: QualityEvent
    action: QualityAction
    rationale: str
    auto_executed: bool = False
    confidence: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)


class QualityAgent:
    """
    Autonomous Quality Control Agent.

    Monitors quality metrics and takes appropriate actions
    based on configured rules and AI analysis.
    """

    # Thresholds for autonomous action
    AUTO_EXECUTE_CONFIDENCE = 0.95
    ESCALATE_THRESHOLD = 0.7

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        copilot: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.event_bus = event_bus
        self.copilot = copilot
        self.config = config or {}

        self._running = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._decision_history: List[QualityDecision] = []
        self._action_handlers: Dict[QualityAction, Callable] = {}

        # State tracking
        self._machine_states: Dict[str, Dict[str, Any]] = {}
        self._consecutive_signals: Dict[str, int] = {}

    def register_action_handler(
        self,
        action: QualityAction,
        handler: Callable
    ) -> None:
        """Register a handler for an action type."""
        self._action_handlers[action] = handler

    async def start(self) -> None:
        """Start the quality agent."""
        self._running = True
        logger.info("Quality Agent started")

        # Start event processing loop
        asyncio.create_task(self._process_events())

        # Subscribe to quality events if event bus available
        if self.event_bus:
            await self.event_bus.subscribe(
                categories=['quality'],
                callback=self._on_quality_event,
                group_name='quality_agent',
                consumer_name='qa-1',
            )

    async def stop(self) -> None:
        """Stop the quality agent."""
        self._running = False
        logger.info("Quality Agent stopped")

    async def process_event(self, event: QualityEvent) -> Optional[QualityDecision]:
        """Process a quality event and decide on action."""
        from uuid import uuid4

        decision = None
        action = QualityAction.LOG_ONLY
        rationale = ""
        confidence = 0.0
        parameters = {}

        # Update state tracking
        self._update_machine_state(event)

        # Analyze event
        if event.event_type == "spc_signal":
            action, rationale, confidence = await self._analyze_spc_signal(event)
        elif event.event_type == "defect_detected":
            action, rationale, confidence = await self._analyze_defect(event)
        elif event.event_type == "measurement_oor":  # Out of range
            action, rationale, confidence = await self._analyze_measurement(event)
        elif event.event_type == "trend_detected":
            action, rationale, confidence = await self._analyze_trend(event)

        if action != QualityAction.LOG_ONLY:
            decision = QualityDecision(
                decision_id=str(uuid4()),
                timestamp=datetime.utcnow(),
                trigger_event=event,
                action=action,
                rationale=rationale,
                confidence=confidence,
                parameters=parameters,
            )

            # Execute if confidence high enough
            if confidence >= self.AUTO_EXECUTE_CONFIDENCE:
                await self._execute_action(decision)
                decision.auto_executed = True
            elif confidence < self.ESCALATE_THRESHOLD:
                decision.action = QualityAction.ESCALATE

            self._decision_history.append(decision)
            logger.info(f"Quality decision: {action.value} (confidence: {confidence:.0%})")

        return decision

    async def _analyze_spc_signal(
        self,
        event: QualityEvent
    ) -> tuple[QualityAction, str, float]:
        """Analyze SPC signal and determine action."""
        signal_type = event.context.get('signal_type', '')
        consecutive = self._consecutive_signals.get(event.machine_id, 0)

        # Critical signals - immediate action
        if signal_type == 'rule_1':  # Beyond 3 sigma
            return (
                QualityAction.HOLD_PRODUCTION,
                "Control limit violation detected. Production hold required pending investigation.",
                0.98
            )

        # Zone warnings - tighten inspection
        if signal_type in ('zone_a', 'zone_b'):
            self._consecutive_signals[event.machine_id] = consecutive + 1

            if consecutive >= 2:
                return (
                    QualityAction.TIGHTEN_INSPECTION,
                    f"Multiple zone warnings ({consecutive + 1}). Implementing 100% inspection.",
                    0.92
                )
            return (
                QualityAction.ALERT,
                f"Zone {signal_type[-1].upper()} warning on {event.metric_name}. Monitoring closely.",
                0.85
            )

        # Trend signals - adjust process
        if signal_type == 'rule_3':  # 6 points trending
            direction = "increasing" if event.context.get('trend', 0) > 0 else "decreasing"
            return (
                QualityAction.ADJUST_PROCESS,
                f"Process drift detected ({direction}). Recommend parameter adjustment.",
                0.88
            )

        # Clear consecutive count for normal events
        self._consecutive_signals[event.machine_id] = 0

        return (QualityAction.LOG_ONLY, "", 0.0)

    async def _analyze_defect(
        self,
        event: QualityEvent
    ) -> tuple[QualityAction, str, float]:
        """Analyze detected defect and determine action."""
        defect_type = event.context.get('defect_type', '')
        severity = event.severity

        # Critical defects - hold production
        if severity == 'critical' or defect_type in ('safety_issue', 'structural_failure'):
            return (
                QualityAction.HOLD_PRODUCTION,
                f"Critical defect ({defect_type}) detected. Production hold required.",
                0.99
            )

        # Major defects - tighten inspection and alert
        if severity == 'major':
            return (
                QualityAction.TIGHTEN_INSPECTION,
                f"Major defect ({defect_type}). Implementing increased inspection.",
                0.90
            )

        # LEGO-specific defects
        if defect_type in ('clutch_power_low', 'clutch_power_high'):
            return (
                QualityAction.ADJUST_PROCESS,
                f"Clutch power issue: {defect_type}. Process adjustment recommended.",
                0.85
            )

        return (
            QualityAction.ALERT,
            f"Defect detected: {defect_type}. Logged for analysis.",
            0.75
        )

    async def _analyze_measurement(
        self,
        event: QualityEvent
    ) -> tuple[QualityAction, str, float]:
        """Analyze out-of-range measurement."""
        deviation = abs(event.metric_value - (event.threshold or 0))
        metric = event.metric_name

        # Large deviation - potential issue
        if deviation > 0.1:  # More than 0.1mm for dimensions
            return (
                QualityAction.TIGHTEN_INSPECTION,
                f"{metric} out of range by {deviation:.3f}. Tightened inspection.",
                0.88
            )

        return (
            QualityAction.ALERT,
            f"{metric} slightly out of range. Monitoring.",
            0.80
        )

    async def _analyze_trend(
        self,
        event: QualityEvent
    ) -> tuple[QualityAction, str, float]:
        """Analyze quality trend."""
        trend_direction = event.context.get('direction', 'unknown')
        rate = event.context.get('rate', 0)

        if abs(rate) > 0.05:  # Significant drift rate
            return (
                QualityAction.ADJUST_PROCESS,
                f"Quality trend detected: {trend_direction} at {rate:.3f}/hour. Process adjustment recommended.",
                0.82
            )

        return (QualityAction.LOG_ONLY, "", 0.0)

    async def _execute_action(self, decision: QualityDecision) -> None:
        """Execute a quality action."""
        action = decision.action

        if action in self._action_handlers:
            try:
                handler = self._action_handlers[action]
                if asyncio.iscoroutinefunction(handler):
                    await handler(decision)
                else:
                    handler(decision)
            except Exception as e:
                logger.error(f"Action handler failed: {e}")
                return

        # Default implementations
        if action == QualityAction.HOLD_PRODUCTION:
            logger.warning(f"PRODUCTION HOLD: {decision.rationale}")
            # Would integrate with MES to actually pause

        elif action == QualityAction.TIGHTEN_INSPECTION:
            logger.info(f"Inspection tightened: {decision.trigger_event.machine_id}")

        elif action == QualityAction.ALERT:
            logger.info(f"Quality Alert: {decision.rationale}")

        elif action == QualityAction.ADJUST_PROCESS:
            logger.info(f"Process adjustment recommended: {decision.rationale}")

    def _update_machine_state(self, event: QualityEvent) -> None:
        """Update machine state tracking."""
        machine_id = event.machine_id

        if machine_id not in self._machine_states:
            self._machine_states[machine_id] = {
                'last_event': None,
                'event_count': 0,
                'quality_score': 100.0,
            }

        state = self._machine_states[machine_id]
        state['last_event'] = event
        state['event_count'] += 1

        # Adjust quality score
        if event.severity == 'critical':
            state['quality_score'] = max(0, state['quality_score'] - 20)
        elif event.severity == 'major':
            state['quality_score'] = max(0, state['quality_score'] - 5)
        elif event.severity == 'minor':
            state['quality_score'] = max(0, state['quality_score'] - 1)
        else:
            # Slowly recover
            state['quality_score'] = min(100, state['quality_score'] + 0.1)

    async def _process_events(self) -> None:
        """Background event processing loop."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                await self.process_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Event processing error: {e}")

    async def _on_quality_event(self, event: Any) -> None:
        """Handle quality event from event bus."""
        # Convert to QualityEvent
        quality_event = QualityEvent(
            event_type=event.event_type,
            timestamp=event.timestamp,
            machine_id=event.work_center_id or 'unknown',
            metric_name=event.payload.get('metric', ''),
            metric_value=event.payload.get('value', 0),
            threshold=event.payload.get('threshold'),
            severity=str(event.priority),
            context=event.payload,
        )
        await self._event_queue.put(quality_event)

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            'running': self._running,
            'decisions_made': len(self._decision_history),
            'machines_monitored': len(self._machine_states),
            'machine_states': {
                m_id: {
                    'quality_score': state['quality_score'],
                    'event_count': state['event_count'],
                }
                for m_id, state in self._machine_states.items()
            },
        }

    def get_recent_decisions(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent decisions."""
        return [
            {
                'decision_id': d.decision_id,
                'timestamp': d.timestamp.isoformat(),
                'action': d.action.value,
                'rationale': d.rationale,
                'auto_executed': d.auto_executed,
                'confidence': d.confidence,
            }
            for d in self._decision_history[-count:]
        ]
