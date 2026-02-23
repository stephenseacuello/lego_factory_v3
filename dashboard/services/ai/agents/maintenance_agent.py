"""
Maintenance Agent - Predictive Maintenance Control

LegoMCP World-Class Manufacturing System v5.0
Phase 17: AI Manufacturing Copilot

Autonomous agent for maintenance management:
- Monitors equipment health
- Predicts failures
- Schedules preventive maintenance
- Coordinates with production schedule
- Tracks maintenance history
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class MaintenanceAction(str, Enum):
    """Actions the maintenance agent can take."""
    SCHEDULE_PM = "schedule_pm"  # Preventive maintenance
    SCHEDULE_CM = "schedule_cm"  # Corrective maintenance
    EMERGENCY_STOP = "emergency_stop"
    ORDER_PARTS = "order_parts"
    ALERT = "alert"
    ESCALATE = "escalate"
    DEFER = "defer"


class MaintenanceUrgency(str, Enum):
    """Urgency levels for maintenance."""
    IMMEDIATE = "immediate"
    TODAY = "today"
    THIS_WEEK = "this_week"
    THIS_MONTH = "this_month"
    SCHEDULED = "scheduled"


@dataclass
class EquipmentHealth:
    """Health status of equipment."""
    machine_id: str
    timestamp: datetime
    health_score: float  # 0-100
    failure_probability: float  # 0-1 for next 24 hours
    degradation_rate: float  # per hour
    components: Dict[str, float] = field(default_factory=dict)  # Component -> health
    alerts: List[str] = field(default_factory=list)
    last_maintenance: Optional[datetime] = None
    next_scheduled: Optional[datetime] = None
    runtime_hours: float = 0.0


@dataclass
class MaintenanceDecision:
    """A decision made by the maintenance agent."""
    decision_id: str
    timestamp: datetime
    machine_id: str
    action: MaintenanceAction
    urgency: MaintenanceUrgency
    rationale: str
    estimated_downtime_hours: float = 0.0
    estimated_cost: float = 0.0
    parts_needed: List[str] = field(default_factory=list)
    auto_executed: bool = False
    confidence: float = 0.0


class MaintenanceAgent:
    """
    Autonomous Maintenance Agent.

    Monitors equipment health and manages maintenance scheduling
    using predictive analytics and production coordination.
    """

    # Thresholds
    CRITICAL_HEALTH = 20  # Health score below this is critical
    WARNING_HEALTH = 50
    FAILURE_PROB_THRESHOLD = 0.3  # 30% failure probability triggers action
    AUTO_EXECUTE_CONFIDENCE = 0.88

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        schedule_service: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.event_bus = event_bus
        self.schedule_service = schedule_service
        self.config = config or {}

        self._running = False
        self._equipment_states: Dict[str, EquipmentHealth] = {}
        self._decision_history: List[MaintenanceDecision] = []
        self._pending_maintenance: List[MaintenanceDecision] = []

        # Maintenance knowledge base
        self._maintenance_rules: Dict[str, Dict[str, Any]] = self._load_maintenance_rules()

    def _load_maintenance_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load maintenance rules and intervals."""
        return {
            '3d_printer': {
                'pm_interval_hours': 500,
                'components': {
                    'nozzle': {'interval': 200, 'cost': 15},
                    'bed_surface': {'interval': 100, 'cost': 25},
                    'belts': {'interval': 1000, 'cost': 40},
                    'bearings': {'interval': 2000, 'cost': 60},
                },
                'failure_modes': [
                    'nozzle_clog',
                    'bed_adhesion_failure',
                    'axis_misalignment',
                ],
            },
            'cnc_mill': {
                'pm_interval_hours': 250,
                'components': {
                    'spindle': {'interval': 500, 'cost': 500},
                    'coolant': {'interval': 100, 'cost': 30},
                    'tool_holder': {'interval': 200, 'cost': 100},
                },
                'failure_modes': [
                    'spindle_bearing_failure',
                    'axis_wear',
                    'coolant_system_failure',
                ],
            },
            'laser_engraver': {
                'pm_interval_hours': 300,
                'components': {
                    'laser_tube': {'interval': 2000, 'cost': 300},
                    'mirrors': {'interval': 500, 'cost': 50},
                    'lens': {'interval': 200, 'cost': 75},
                },
                'failure_modes': [
                    'laser_power_degradation',
                    'optical_misalignment',
                ],
            },
        }

    async def start(self) -> None:
        """Start the maintenance agent."""
        self._running = True
        logger.info("Maintenance Agent started")

        # Start background monitoring
        asyncio.create_task(self._monitor_equipment())
        asyncio.create_task(self._check_scheduled_maintenance())

        # Subscribe to events
        if self.event_bus:
            await self.event_bus.subscribe(
                categories=['maintenance', 'machine'],
                callback=self._on_event,
                group_name='maintenance_agent',
                consumer_name='ma-1',
            )

    async def stop(self) -> None:
        """Stop the maintenance agent."""
        self._running = False
        logger.info("Maintenance Agent stopped")

    async def evaluate_equipment(
        self,
        health: EquipmentHealth
    ) -> Optional[MaintenanceDecision]:
        """Evaluate equipment health and decide on maintenance."""
        from uuid import uuid4

        self._equipment_states[health.machine_id] = health

        # Check for critical conditions
        if health.health_score < self.CRITICAL_HEALTH:
            return await self._create_emergency_decision(health)

        # Check failure probability
        if health.failure_probability > self.FAILURE_PROB_THRESHOLD:
            return await self._create_preventive_decision(health)

        # Check component health
        for component, component_health in health.components.items():
            if component_health < 30:
                return await self._create_component_decision(health, component)

        # Check if PM is due
        if health.next_scheduled and health.next_scheduled <= datetime.utcnow() + timedelta(days=1):
            return await self._create_scheduled_decision(health)

        return None

    async def _create_emergency_decision(
        self,
        health: EquipmentHealth
    ) -> MaintenanceDecision:
        """Create emergency maintenance decision."""
        from uuid import uuid4

        decision = MaintenanceDecision(
            decision_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            machine_id=health.machine_id,
            action=MaintenanceAction.EMERGENCY_STOP,
            urgency=MaintenanceUrgency.IMMEDIATE,
            rationale=f"Critical health score ({health.health_score:.0f}%). "
                      f"Failure probability: {health.failure_probability*100:.0f}%. "
                      f"Immediate maintenance required to prevent unplanned failure.",
            estimated_downtime_hours=4.0,
            estimated_cost=500.0,
            confidence=0.95,
        )

        self._decision_history.append(decision)
        logger.warning(f"EMERGENCY: {health.machine_id} requires immediate maintenance")

        return decision

    async def _create_preventive_decision(
        self,
        health: EquipmentHealth
    ) -> MaintenanceDecision:
        """Create preventive maintenance decision."""
        from uuid import uuid4

        # Find optimal maintenance window
        window = await self._find_maintenance_window(health.machine_id, hours_ahead=48)

        decision = MaintenanceDecision(
            decision_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            machine_id=health.machine_id,
            action=MaintenanceAction.SCHEDULE_PM,
            urgency=MaintenanceUrgency.TODAY if health.failure_probability > 0.5 else MaintenanceUrgency.THIS_WEEK,
            rationale=f"Elevated failure risk ({health.failure_probability*100:.0f}%). "
                      f"Health score: {health.health_score:.0f}%. "
                      f"Scheduling preventive maintenance to avoid unplanned downtime.",
            estimated_downtime_hours=2.0,
            estimated_cost=200.0,
            confidence=0.85,
        )

        self._decision_history.append(decision)
        self._pending_maintenance.append(decision)

        return decision

    async def _create_component_decision(
        self,
        health: EquipmentHealth,
        component: str
    ) -> MaintenanceDecision:
        """Create component-specific maintenance decision."""
        from uuid import uuid4

        component_health = health.components.get(component, 100)

        # Get component info from rules
        machine_type = self._get_machine_type(health.machine_id)
        rules = self._maintenance_rules.get(machine_type, {})
        component_info = rules.get('components', {}).get(component, {})

        decision = MaintenanceDecision(
            decision_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            machine_id=health.machine_id,
            action=MaintenanceAction.SCHEDULE_PM,
            urgency=MaintenanceUrgency.THIS_WEEK,
            rationale=f"Component '{component}' degraded to {component_health:.0f}% health. "
                      f"Recommend replacement before failure.",
            estimated_downtime_hours=1.0,
            estimated_cost=component_info.get('cost', 100),
            parts_needed=[component],
            confidence=0.82,
        )

        # Check parts availability
        if not await self._check_parts_available([component]):
            decision.action = MaintenanceAction.ORDER_PARTS
            decision.rationale += " Parts need to be ordered."

        self._decision_history.append(decision)

        return decision

    async def _create_scheduled_decision(
        self,
        health: EquipmentHealth
    ) -> MaintenanceDecision:
        """Create scheduled maintenance decision."""
        from uuid import uuid4

        decision = MaintenanceDecision(
            decision_id=str(uuid4()),
            timestamp=datetime.utcnow(),
            machine_id=health.machine_id,
            action=MaintenanceAction.SCHEDULE_PM,
            urgency=MaintenanceUrgency.SCHEDULED,
            rationale=f"Scheduled preventive maintenance due. "
                      f"Runtime since last PM: {health.runtime_hours:.0f} hours.",
            estimated_downtime_hours=1.5,
            estimated_cost=150.0,
            confidence=0.90,
        )

        self._decision_history.append(decision)

        return decision

    async def _find_maintenance_window(
        self,
        machine_id: str,
        hours_ahead: int = 48
    ) -> Optional[datetime]:
        """Find optimal maintenance window considering production schedule."""
        # In practice, would query schedule service
        # For now, return next shift change
        now = datetime.utcnow()
        next_shift = now.replace(hour=8 if now.hour >= 16 else 16, minute=0, second=0)
        if next_shift <= now:
            next_shift += timedelta(days=1)
        return next_shift

    async def _check_parts_available(self, parts: List[str]) -> bool:
        """Check if required parts are available."""
        # In practice, would query inventory
        return True  # Assume parts available

    def _get_machine_type(self, machine_id: str) -> str:
        """Get machine type from ID."""
        if 'printer' in machine_id.lower():
            return '3d_printer'
        elif 'cnc' in machine_id.lower() or 'mill' in machine_id.lower():
            return 'cnc_mill'
        elif 'laser' in machine_id.lower():
            return 'laser_engraver'
        return 'unknown'

    async def _monitor_equipment(self) -> None:
        """Background equipment monitoring."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute

                for machine_id, health in self._equipment_states.items():
                    # Simulate health degradation
                    health.health_score = max(0, health.health_score - health.degradation_rate / 60)
                    health.runtime_hours += 1 / 60

                    # Re-evaluate if health changed significantly
                    if health.health_score < self.WARNING_HEALTH:
                        await self.evaluate_equipment(health)

            except Exception as e:
                logger.error(f"Equipment monitor error: {e}")

    async def _check_scheduled_maintenance(self) -> None:
        """Check for upcoming scheduled maintenance."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes

                now = datetime.utcnow()

                for machine_id, health in self._equipment_states.items():
                    if health.next_scheduled:
                        time_until = health.next_scheduled - now
                        if time_until < timedelta(hours=24):
                            # Alert about upcoming maintenance
                            logger.info(f"Maintenance due for {machine_id} in {time_until}")

            except Exception as e:
                logger.error(f"Scheduled maintenance check error: {e}")

    async def _on_event(self, event: Any) -> None:
        """Handle event from event bus."""
        # Convert to health update
        if event.event_type == 'health_update':
            health = EquipmentHealth(
                machine_id=event.work_center_id or 'unknown',
                timestamp=event.timestamp,
                health_score=event.payload.get('health_score', 100),
                failure_probability=event.payload.get('failure_probability', 0),
                degradation_rate=event.payload.get('degradation_rate', 0.01),
                components=event.payload.get('components', {}),
            )
            await self.evaluate_equipment(health)

    def update_equipment_health(
        self,
        machine_id: str,
        health_score: float,
        failure_probability: float = 0.0,
        components: Optional[Dict[str, float]] = None,
    ) -> None:
        """Update equipment health state."""
        if machine_id in self._equipment_states:
            state = self._equipment_states[machine_id]
            state.health_score = health_score
            state.failure_probability = failure_probability
            state.timestamp = datetime.utcnow()
            if components:
                state.components = components
        else:
            self._equipment_states[machine_id] = EquipmentHealth(
                machine_id=machine_id,
                timestamp=datetime.utcnow(),
                health_score=health_score,
                failure_probability=failure_probability,
                degradation_rate=0.01,
                components=components or {},
            )

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            'running': self._running,
            'equipment_monitored': len(self._equipment_states),
            'pending_maintenance': len(self._pending_maintenance),
            'decisions_made': len(self._decision_history),
            'equipment_summary': {
                m_id: {
                    'health': health.health_score,
                    'failure_prob': health.failure_probability,
                }
                for m_id, health in self._equipment_states.items()
            },
        }

    def get_equipment_health(self, machine_id: str) -> Optional[Dict[str, Any]]:
        """Get health status for specific equipment."""
        if machine_id not in self._equipment_states:
            return None

        health = self._equipment_states[machine_id]
        return {
            'machine_id': machine_id,
            'health_score': health.health_score,
            'failure_probability': health.failure_probability,
            'runtime_hours': health.runtime_hours,
            'last_maintenance': health.last_maintenance.isoformat() if health.last_maintenance else None,
            'next_scheduled': health.next_scheduled.isoformat() if health.next_scheduled else None,
            'components': health.components,
            'alerts': health.alerts,
        }

    def get_maintenance_schedule(self) -> List[Dict[str, Any]]:
        """Get pending maintenance schedule."""
        return [
            {
                'machine_id': d.machine_id,
                'action': d.action.value,
                'urgency': d.urgency.value,
                'estimated_downtime': d.estimated_downtime_hours,
                'rationale': d.rationale,
            }
            for d in self._pending_maintenance
        ]

    def get_recent_decisions(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent decisions."""
        return [
            {
                'decision_id': d.decision_id,
                'timestamp': d.timestamp.isoformat(),
                'machine_id': d.machine_id,
                'action': d.action.value,
                'urgency': d.urgency.value,
                'rationale': d.rationale,
            }
            for d in self._decision_history[-count:]
        ]
