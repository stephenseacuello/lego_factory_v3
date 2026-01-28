"""
Scheduling Agent - Autonomous Schedule Optimization

LegoMCP World-Class Manufacturing System v5.0
Phase 17: AI Manufacturing Copilot

Autonomous agent for production scheduling:
- Monitors schedule adherence
- Detects and responds to disruptions
- Optimizes machine assignments
- Balances workloads
- Handles rush orders
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ScheduleAction(str, Enum):
    """Actions the scheduling agent can take."""
    RESCHEDULE = "reschedule"
    REASSIGN_MACHINE = "reassign_machine"
    EXPEDITE = "expedite"
    DELAY = "delay"
    SPLIT_ORDER = "split_order"
    MERGE_BATCHES = "merge_batches"
    ALERT = "alert"
    ESCALATE = "escalate"


@dataclass
class ScheduleEvent:
    """A scheduling event for the agent to process."""
    event_type: str  # machine_down, rush_order, delay, completion, etc.
    timestamp: datetime
    order_id: Optional[str] = None
    machine_id: Optional[str] = None
    expected_impact_hours: float = 0.0
    priority: str = "normal"
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScheduleDecision:
    """A decision made by the scheduling agent."""
    decision_id: str
    timestamp: datetime
    trigger_event: ScheduleEvent
    action: ScheduleAction
    affected_orders: List[str]
    rationale: str
    expected_improvement: Dict[str, float] = field(default_factory=dict)
    auto_executed: bool = False
    confidence: float = 0.0


class SchedulingAgent:
    """
    Autonomous Scheduling Agent.

    Monitors production schedule and makes real-time adjustments
    to optimize performance and respond to disruptions.
    """

    AUTO_EXECUTE_CONFIDENCE = 0.90
    ESCALATE_THRESHOLD = 0.6

    def __init__(
        self,
        scheduler_factory: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.scheduler = scheduler_factory
        self.event_bus = event_bus
        self.config = config or {}

        self._running = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._decision_history: List[ScheduleDecision] = []

        # Current schedule state
        self._current_schedule: Optional[Any] = None
        self._machine_availability: Dict[str, datetime] = {}
        self._order_status: Dict[str, Dict[str, Any]] = {}

    async def start(self) -> None:
        """Start the scheduling agent."""
        self._running = True
        logger.info("Scheduling Agent started")

        # Start background tasks
        asyncio.create_task(self._process_events())
        asyncio.create_task(self._monitor_schedule())

        # Subscribe to relevant events
        if self.event_bus:
            await self.event_bus.subscribe(
                categories=['scheduling', 'machine'],
                callback=self._on_event,
                group_name='scheduling_agent',
                consumer_name='sa-1',
            )

    async def stop(self) -> None:
        """Stop the scheduling agent."""
        self._running = False
        logger.info("Scheduling Agent stopped")

    async def handle_disruption(
        self,
        disruption: ScheduleEvent
    ) -> ScheduleDecision:
        """Handle a schedule disruption."""
        from uuid import uuid4

        action = ScheduleAction.ALERT
        affected_orders = []
        rationale = ""
        confidence = 0.0
        improvement = {}

        if disruption.event_type == "machine_down":
            action, affected_orders, rationale, confidence, improvement = \
                await self._handle_machine_down(disruption)

        elif disruption.event_type == "rush_order":
            action, affected_orders, rationale, confidence, improvement = \
                await self._handle_rush_order(disruption)

        elif disruption.event_type == "delay":
            action, affected_orders, rationale, confidence, improvement = \
                await self._handle_delay(disruption)

        elif disruption.event_type == "capacity_shortage":
            action, affected_orders, rationale, confidence, improvement = \
                await self._handle_capacity_shortage(disruption)

        decision = ScheduleDecision(
            decision_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            trigger_event=disruption,
            action=action,
            affected_orders=affected_orders,
            rationale=rationale,
            expected_improvement=improvement,
            confidence=confidence,
        )

        # Execute if confidence high enough
        if confidence >= self.AUTO_EXECUTE_CONFIDENCE:
            await self._execute_action(decision)
            decision.auto_executed = True
        elif confidence < self.ESCALATE_THRESHOLD:
            decision.action = ScheduleAction.ESCALATE

        self._decision_history.append(decision)
        logger.info(f"Schedule decision: {action.value} for {len(affected_orders)} orders")

        return decision

    async def _handle_machine_down(
        self,
        event: ScheduleEvent
    ) -> tuple[ScheduleAction, List[str], str, float, Dict[str, float]]:
        """Handle machine breakdown."""
        machine_id = event.machine_id
        downtime_hours = event.expected_impact_hours

        # Find affected orders
        affected = self._get_orders_on_machine(machine_id)

        if not affected:
            return (
                ScheduleAction.ALERT,
                [],
                f"Machine {machine_id} down but no orders affected",
                0.95,
                {}
            )

        # Check for alternative machines
        alternatives = self._get_alternative_machines(machine_id)

        if alternatives:
            return (
                ScheduleAction.REASSIGN_MACHINE,
                affected,
                f"Reassigning {len(affected)} orders from {machine_id} to {alternatives[0]}",
                0.88,
                {'tardiness_reduction_hours': downtime_hours * 0.8}
            )

        if downtime_hours > 4:
            return (
                ScheduleAction.RESCHEDULE,
                affected,
                f"Full reschedule needed. {machine_id} down for {downtime_hours} hours.",
                0.82,
                {'tardiness_reduction_hours': downtime_hours * 0.5}
            )

        return (
            ScheduleAction.DELAY,
            affected,
            f"Delaying {len(affected)} orders by {downtime_hours} hours",
            0.75,
            {}
        )

    async def _handle_rush_order(
        self,
        event: ScheduleEvent
    ) -> tuple[ScheduleAction, List[str], str, float, Dict[str, float]]:
        """Handle rush order insertion."""
        order_id = event.order_id
        priority = event.priority

        if priority == "critical":
            return (
                ScheduleAction.EXPEDITE,
                [order_id] if order_id else [],
                f"Expediting critical order {order_id}. May impact other orders.",
                0.92,
                {'on_time_probability': 0.95}
            )

        # Find insertion point with minimal disruption
        disrupted_orders = self._calculate_disruption(order_id)

        if len(disrupted_orders) <= 2:
            return (
                ScheduleAction.RESCHEDULE,
                [order_id] + disrupted_orders if order_id else disrupted_orders,
                f"Inserting rush order with minimal impact ({len(disrupted_orders)} orders affected)",
                0.85,
                {'total_tardiness_hours': len(disrupted_orders) * 0.5}
            )

        return (
            ScheduleAction.ESCALATE,
            [order_id] if order_id else [],
            f"Rush order would significantly impact {len(disrupted_orders)} orders. Escalating.",
            0.5,
            {}
        )

    async def _handle_delay(
        self,
        event: ScheduleEvent
    ) -> tuple[ScheduleAction, List[str], str, float, Dict[str, float]]:
        """Handle production delay."""
        delay_hours = event.expected_impact_hours
        order_id = event.order_id

        if delay_hours < 1:
            return (
                ScheduleAction.ALERT,
                [order_id] if order_id else [],
                f"Minor delay ({delay_hours:.1f}h). Absorbing within buffer.",
                0.90,
                {}
            )

        # Check if we can recover
        recovery_options = self._find_recovery_options(order_id, delay_hours)

        if recovery_options:
            best_option = recovery_options[0]
            return (
                ScheduleAction.RESCHEDULE,
                best_option.get('affected_orders', []),
                f"Recovering from {delay_hours:.1f}h delay via {best_option.get('method')}",
                0.82,
                {'recovery_percent': best_option.get('recovery', 80)}
            )

        return (
            ScheduleAction.DELAY,
            [order_id] if order_id else [],
            f"Delay of {delay_hours:.1f}h cannot be fully recovered",
            0.70,
            {}
        )

    async def _handle_capacity_shortage(
        self,
        event: ScheduleEvent
    ) -> tuple[ScheduleAction, List[str], str, float, Dict[str, float]]:
        """Handle capacity shortage."""
        shortage_hours = event.expected_impact_hours

        # Options: overtime, outsourcing, delay
        if shortage_hours <= 4:
            return (
                ScheduleAction.RESCHEDULE,
                [],
                f"Minor capacity shortage. Optimizing schedule to absorb.",
                0.85,
                {}
            )

        return (
            ScheduleAction.ESCALATE,
            [],
            f"Significant capacity shortage ({shortage_hours:.0f}h). Requires management decision.",
            0.5,
            {}
        )

    async def _execute_action(self, decision: ScheduleDecision) -> None:
        """Execute a scheduling action."""
        action = decision.action

        if action == ScheduleAction.RESCHEDULE:
            logger.info(f"Executing reschedule for {len(decision.affected_orders)} orders")
            # Would trigger scheduler.solve() with updated constraints

        elif action == ScheduleAction.REASSIGN_MACHINE:
            logger.info(f"Reassigning orders to alternative machine")
            # Would update machine assignments

        elif action == ScheduleAction.EXPEDITE:
            logger.info(f"Expediting order")
            # Would adjust priorities and reschedule

        elif action == ScheduleAction.DELAY:
            logger.info(f"Registering delay")
            # Would update expected completion times

        elif action == ScheduleAction.ALERT:
            logger.info(f"Schedule alert: {decision.rationale}")

    def _get_orders_on_machine(self, machine_id: str) -> List[str]:
        """Get orders currently scheduled on a machine."""
        if not self._current_schedule:
            return []

        orders = set()
        for op in getattr(self._current_schedule, 'operations', []):
            if op.machine_id == machine_id:
                orders.add(op.job_id)
        return list(orders)

    def _get_alternative_machines(self, machine_id: str) -> List[str]:
        """Get alternative machines for current work."""
        # In practice, this would query the routing database
        # For demo, return empty (no alternatives)
        alternatives = {
            'printer-001': ['printer-002', 'printer-003'],
            'printer-002': ['printer-001', 'printer-003'],
            'cnc-001': ['cnc-002'],
        }
        return alternatives.get(machine_id, [])

    def _calculate_disruption(self, rush_order_id: Optional[str]) -> List[str]:
        """Calculate orders disrupted by inserting a rush order."""
        # Simplified - in practice would analyze schedule
        return []

    def _find_recovery_options(
        self,
        order_id: Optional[str],
        delay_hours: float
    ) -> List[Dict[str, Any]]:
        """Find options to recover from a delay."""
        options = []

        # Speed up production (if possible)
        if delay_hours < 2:
            options.append({
                'method': 'increase_speed',
                'recovery': 90,
                'affected_orders': [],
            })

        # Overtime
        options.append({
            'method': 'overtime',
            'recovery': 80,
            'affected_orders': [],
            'cost': delay_hours * 50,  # $50/hour overtime
        })

        return options

    async def _process_events(self) -> None:
        """Background event processing loop."""
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                await self.handle_disruption(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Event processing error: {e}")

    async def _monitor_schedule(self) -> None:
        """Monitor schedule adherence."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute

                # Check for deviations
                deviations = self._check_schedule_adherence()
                for deviation in deviations:
                    await self._event_queue.put(deviation)

            except Exception as e:
                logger.error(f"Schedule monitor error: {e}")

    def _check_schedule_adherence(self) -> List[ScheduleEvent]:
        """Check for schedule adherence issues."""
        # In practice, would compare actual vs planned times
        return []

    async def _on_event(self, event: Any) -> None:
        """Handle event from event bus."""
        schedule_event = ScheduleEvent(
            event_type=event.event_type,
            timestamp=event.timestamp,
            order_id=event.payload.get('order_id'),
            machine_id=event.work_center_id,
            expected_impact_hours=event.payload.get('impact_hours', 0),
            priority=str(event.priority),
            context=event.payload,
        )
        await self._event_queue.put(schedule_event)

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            'running': self._running,
            'decisions_made': len(self._decision_history),
            'recent_actions': [d.action.value for d in self._decision_history[-5:]],
        }

    def get_recent_decisions(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent decisions."""
        return [
            {
                'decision_id': d.decision_id,
                'timestamp': d.timestamp.isoformat(),
                'action': d.action.value,
                'affected_orders': d.affected_orders,
                'rationale': d.rationale,
                'auto_executed': d.auto_executed,
            }
            for d in self._decision_history[-count:]
        ]
