"""
V8 Autonomous Self-Healing Service
===================================

Provides automatic fault detection, recovery, and self-repair:
- Circuit breaker pattern for service protection
- Automatic failure recovery with exponential backoff
- Self-repair through redundancy and failover
- Health monitoring and proactive intervention
- Root cause analysis and remediation

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import asyncio
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================
# Enums
# ============================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class HealthLevel(Enum):
    """Component health levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    FAILED = "failed"
    RECOVERING = "recovering"


class RecoveryAction(Enum):
    """Types of recovery actions."""
    RESTART = "restart"
    FAILOVER = "failover"
    SCALE_UP = "scale_up"
    RECONFIGURE = "reconfigure"
    ISOLATE = "isolate"
    NOTIFY = "notify"
    ROLLBACK = "rollback"
    RETRY = "retry"


class FaultType(Enum):
    """Types of faults."""
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DATA_CORRUPTION = "data_corruption"
    HARDWARE_FAILURE = "hardware_failure"
    SOFTWARE_ERROR = "software_error"
    CONFIGURATION_ERROR = "configuration_error"
    DEPENDENCY_FAILURE = "dependency_failure"


# ============================================
# Data Classes
# ============================================

@dataclass
class Fault:
    """Detected fault."""
    fault_id: str
    fault_type: FaultType
    component: str
    message: str
    severity: int  # 1-5, 5 being most severe
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    resolved: bool = False
    resolution: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fault_id": self.fault_id,
            "fault_type": self.fault_type.value,
            "component": self.component,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass
class RecoveryPlan:
    """Plan for recovering from a fault."""
    plan_id: str
    fault_id: str
    actions: List[RecoveryAction]
    estimated_duration_seconds: int
    success_probability: float
    created_at: datetime = field(default_factory=datetime.now)
    executed: bool = False
    success: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "fault_id": self.fault_id,
            "actions": [a.value for a in self.actions],
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "success_probability": self.success_probability,
            "created_at": self.created_at.isoformat(),
            "executed": self.executed,
            "success": self.success,
        }


@dataclass
class ComponentHealth:
    """Health status of a component."""
    component_id: str
    name: str
    health_level: HealthLevel
    last_check: datetime
    uptime_seconds: float
    error_count: int
    recovery_count: int
    metrics: Dict[str, float] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "name": self.name,
            "health_level": self.health_level.value,
            "last_check": self.last_check.isoformat(),
            "uptime_seconds": self.uptime_seconds,
            "error_count": self.error_count,
            "recovery_count": self.recovery_count,
            "metrics": self.metrics,
            "dependencies": self.dependencies,
        }


# ============================================
# Circuit Breaker
# ============================================

class CircuitBreaker:
    """
    Circuit breaker for protecting services from cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests rejected
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def record_success(self):
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_calls += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit {self.name} closed - service recovered")
            elif self._state == CircuitState.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} re-opened - recovery failed")
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(f"Circuit {self.name} opened - threshold exceeded")

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        elif state == CircuitState.OPEN:
            return False
        else:  # HALF_OPEN
            with self._lock:
                if self._half_open_calls < self.half_open_max_calls:
                    return True
                return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


# ============================================
# Self-Healing Orchestrator
# ============================================

class SelfHealingOrchestrator:
    """
    Orchestrates autonomous self-healing across the factory.

    Capabilities:
    - Fault detection and classification
    - Automatic recovery planning
    - Execution of recovery actions
    - Learning from past incidents
    """

    def __init__(self):
        self._components: Dict[str, ComponentHealth] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._faults: Dict[str, Fault] = {}
        self._recovery_plans: Dict[str, RecoveryPlan] = {}
        self._fault_history: deque = deque(maxlen=1000)
        self._recovery_handlers: Dict[RecoveryAction, Callable] = {}
        self._lock = threading.RLock()
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None

        # Recovery strategies by fault type
        self._recovery_strategies: Dict[FaultType, List[RecoveryAction]] = {
            FaultType.TIMEOUT: [RecoveryAction.RETRY, RecoveryAction.RESTART],
            FaultType.CONNECTION_ERROR: [RecoveryAction.RETRY, RecoveryAction.FAILOVER],
            FaultType.RESOURCE_EXHAUSTION: [RecoveryAction.SCALE_UP, RecoveryAction.RECONFIGURE],
            FaultType.DATA_CORRUPTION: [RecoveryAction.ROLLBACK, RecoveryAction.NOTIFY],
            FaultType.HARDWARE_FAILURE: [RecoveryAction.FAILOVER, RecoveryAction.ISOLATE],
            FaultType.SOFTWARE_ERROR: [RecoveryAction.RESTART, RecoveryAction.ROLLBACK],
            FaultType.CONFIGURATION_ERROR: [RecoveryAction.RECONFIGURE, RecoveryAction.ROLLBACK],
            FaultType.DEPENDENCY_FAILURE: [RecoveryAction.ISOLATE, RecoveryAction.RETRY],
        }

        # Register default recovery handlers
        self._register_default_handlers()

        logger.info("SelfHealingOrchestrator initialized")

    def _register_default_handlers(self):
        """Register default recovery action handlers."""
        self._recovery_handlers = {
            RecoveryAction.RESTART: self._handle_restart,
            RecoveryAction.FAILOVER: self._handle_failover,
            RecoveryAction.SCALE_UP: self._handle_scale_up,
            RecoveryAction.RECONFIGURE: self._handle_reconfigure,
            RecoveryAction.ISOLATE: self._handle_isolate,
            RecoveryAction.NOTIFY: self._handle_notify,
            RecoveryAction.ROLLBACK: self._handle_rollback,
            RecoveryAction.RETRY: self._handle_retry,
        }

    # ============================================
    # Component Management
    # ============================================

    def register_component(
        self,
        component_id: str,
        name: str,
        dependencies: List[str] = None,
        circuit_breaker_config: Dict[str, Any] = None,
    ) -> ComponentHealth:
        """Register a component for health monitoring."""
        with self._lock:
            health = ComponentHealth(
                component_id=component_id,
                name=name,
                health_level=HealthLevel.HEALTHY,
                last_check=datetime.now(),
                uptime_seconds=0,
                error_count=0,
                recovery_count=0,
                dependencies=dependencies or [],
            )
            self._components[component_id] = health

            # Create circuit breaker
            cb_config = circuit_breaker_config or {}
            self._circuit_breakers[component_id] = CircuitBreaker(
                name=component_id,
                failure_threshold=cb_config.get("failure_threshold", 5),
                recovery_timeout=cb_config.get("recovery_timeout", 30.0),
            )

            logger.info(f"Registered component: {name} ({component_id})")
            return health

    def update_component_health(
        self,
        component_id: str,
        health_level: HealthLevel,
        metrics: Dict[str, float] = None,
    ):
        """Update component health status."""
        with self._lock:
            if component_id in self._components:
                component = self._components[component_id]
                old_level = component.health_level
                component.health_level = health_level
                component.last_check = datetime.now()
                if metrics:
                    component.metrics.update(metrics)

                # Trigger healing if degraded
                if health_level in [HealthLevel.CRITICAL, HealthLevel.FAILED]:
                    if old_level not in [HealthLevel.CRITICAL, HealthLevel.FAILED]:
                        self._trigger_healing(component_id, health_level)

    def get_component_health(self, component_id: str) -> Optional[ComponentHealth]:
        """Get component health status."""
        return self._components.get(component_id)

    # ============================================
    # Fault Management
    # ============================================

    def report_fault(
        self,
        component: str,
        fault_type: FaultType,
        message: str,
        severity: int = 3,
        context: Dict[str, Any] = None,
        stack_trace: str = None,
    ) -> Fault:
        """Report a detected fault."""
        with self._lock:
            fault = Fault(
                fault_id=f"fault-{uuid.uuid4().hex[:12]}",
                fault_type=fault_type,
                component=component,
                message=message,
                severity=severity,
                context=context or {},
                stack_trace=stack_trace,
            )

            self._faults[fault.fault_id] = fault
            self._fault_history.append(fault)

            # Update circuit breaker
            if component in self._circuit_breakers:
                self._circuit_breakers[component].record_failure()

            # Update component health
            if component in self._components:
                self._components[component].error_count += 1
                if severity >= 4:
                    self._components[component].health_level = HealthLevel.CRITICAL
                elif severity >= 3:
                    self._components[component].health_level = HealthLevel.DEGRADED

            logger.warning(f"Fault reported: {fault.fault_id} - {message}")

            # Auto-generate recovery plan for high severity faults
            if severity >= 3:
                self._auto_recover(fault)

            return fault

    def resolve_fault(
        self,
        fault_id: str,
        resolution: str,
    ) -> bool:
        """Mark a fault as resolved."""
        with self._lock:
            if fault_id in self._faults:
                fault = self._faults[fault_id]
                fault.resolved = True
                fault.resolution = resolution

                # Update circuit breaker
                if fault.component in self._circuit_breakers:
                    self._circuit_breakers[fault.component].record_success()

                logger.info(f"Fault resolved: {fault_id}")
                return True
            return False

    def get_active_faults(self) -> List[Fault]:
        """Get all unresolved faults."""
        return [f for f in self._faults.values() if not f.resolved]

    # ============================================
    # Recovery Planning and Execution
    # ============================================

    def _auto_recover(self, fault: Fault):
        """Automatically create and execute recovery plan."""
        plan = self.create_recovery_plan(fault.fault_id)
        if plan:
            asyncio.create_task(self._execute_recovery_async(plan))

    def create_recovery_plan(self, fault_id: str) -> Optional[RecoveryPlan]:
        """Create a recovery plan for a fault."""
        fault = self._faults.get(fault_id)
        if not fault:
            return None

        actions = self._recovery_strategies.get(
            fault.fault_type,
            [RecoveryAction.NOTIFY]
        )

        # Calculate success probability based on fault history
        similar_faults = [
            f for f in self._fault_history
            if f.fault_type == fault.fault_type and f.resolved
        ]
        if similar_faults:
            success_rate = len([f for f in similar_faults if f.resolution]) / len(similar_faults)
        else:
            success_rate = 0.7

        plan = RecoveryPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            fault_id=fault_id,
            actions=actions,
            estimated_duration_seconds=30 * len(actions),
            success_probability=success_rate,
        )

        self._recovery_plans[plan.plan_id] = plan
        logger.info(f"Created recovery plan: {plan.plan_id} for fault {fault_id}")
        return plan

    async def execute_recovery_plan(self, plan_id: str) -> bool:
        """Execute a recovery plan."""
        plan = self._recovery_plans.get(plan_id)
        if not plan or plan.executed:
            return False

        fault = self._faults.get(plan.fault_id)
        if not fault:
            return False

        logger.info(f"Executing recovery plan: {plan_id}")
        plan.executed = True

        success = True
        for action in plan.actions:
            handler = self._recovery_handlers.get(action)
            if handler:
                try:
                    result = await handler(fault)
                    if not result:
                        success = False
                        break
                except Exception as e:
                    logger.error(f"Recovery action {action} failed: {e}")
                    success = False
                    break

        plan.success = success

        if success:
            self.resolve_fault(fault.fault_id, f"Auto-recovered via plan {plan_id}")
            if fault.component in self._components:
                self._components[fault.component].recovery_count += 1
                self._components[fault.component].health_level = HealthLevel.RECOVERING

        return success

    async def _execute_recovery_async(self, plan: RecoveryPlan):
        """Execute recovery plan asynchronously."""
        await self.execute_recovery_plan(plan.plan_id)

    # ============================================
    # Recovery Handlers
    # ============================================

    async def _handle_restart(self, fault: Fault) -> bool:
        """Handle restart recovery action."""
        logger.info(f"Restarting component: {fault.component}")
        await asyncio.sleep(2)  # Simulate restart
        return True

    async def _handle_failover(self, fault: Fault) -> bool:
        """Handle failover recovery action."""
        logger.info(f"Failing over component: {fault.component}")
        await asyncio.sleep(1)
        return True

    async def _handle_scale_up(self, fault: Fault) -> bool:
        """Handle scale up recovery action."""
        logger.info(f"Scaling up resources for: {fault.component}")
        await asyncio.sleep(1)
        return True

    async def _handle_reconfigure(self, fault: Fault) -> bool:
        """Handle reconfigure recovery action."""
        logger.info(f"Reconfiguring component: {fault.component}")
        await asyncio.sleep(1)
        return True

    async def _handle_isolate(self, fault: Fault) -> bool:
        """Handle isolate recovery action."""
        logger.info(f"Isolating component: {fault.component}")
        if fault.component in self._circuit_breakers:
            cb = self._circuit_breakers[fault.component]
            cb._state = CircuitState.OPEN
        return True

    async def _handle_notify(self, fault: Fault) -> bool:
        """Handle notify recovery action."""
        logger.info(f"Sending notification for fault: {fault.fault_id}")
        return True

    async def _handle_rollback(self, fault: Fault) -> bool:
        """Handle rollback recovery action."""
        logger.info(f"Rolling back component: {fault.component}")
        await asyncio.sleep(2)
        return True

    async def _handle_retry(self, fault: Fault) -> bool:
        """Handle retry with exponential backoff."""
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            delay = base_delay * (2 ** attempt)
            logger.info(f"Retry attempt {attempt + 1} for {fault.component}, waiting {delay}s")
            await asyncio.sleep(delay)

            # Check if component recovered
            if fault.component in self._components:
                health = self._components[fault.component]
                if health.health_level in [HealthLevel.HEALTHY, HealthLevel.RECOVERING]:
                    return True

        return False

    # ============================================
    # Monitoring
    # ============================================

    def _trigger_healing(self, component_id: str, health_level: HealthLevel):
        """Trigger healing process for a component."""
        fault_type = FaultType.SOFTWARE_ERROR
        if health_level == HealthLevel.FAILED:
            severity = 5
        else:
            severity = 4

        self.report_fault(
            component=component_id,
            fault_type=fault_type,
            message=f"Component {component_id} health degraded to {health_level.value}",
            severity=severity,
        )

    def start_monitoring(self, interval_seconds: float = 10.0):
        """Start background health monitoring."""
        if self._monitoring_active:
            return

        self._monitoring_active = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("Self-healing monitoring started")

    def stop_monitoring(self):
        """Stop background health monitoring."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        logger.info("Self-healing monitoring stopped")

    def _monitoring_loop(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring_active:
            try:
                self._check_all_components()
                self._check_circuit_breakers()
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
            time.sleep(interval)

    def _check_all_components(self):
        """Check health of all registered components."""
        now = datetime.now()
        for component_id, health in self._components.items():
            # Check for stale health data
            staleness = (now - health.last_check).total_seconds()
            if staleness > 60:
                self.update_component_health(
                    component_id,
                    HealthLevel.DEGRADED,
                    {"staleness_seconds": staleness},
                )

    def _check_circuit_breakers(self):
        """Check and log circuit breaker states."""
        for name, cb in self._circuit_breakers.items():
            if cb.state == CircuitState.OPEN:
                logger.warning(f"Circuit breaker {name} is OPEN")

    # ============================================
    # Statistics and Reporting
    # ============================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get self-healing statistics."""
        active_faults = self.get_active_faults()

        health_counts = {}
        for level in HealthLevel:
            health_counts[level.value] = sum(
                1 for c in self._components.values()
                if c.health_level == level
            )

        circuit_counts = {}
        for state in CircuitState:
            circuit_counts[state.value] = sum(
                1 for cb in self._circuit_breakers.values()
                if cb.state == state
            )

        return {
            "total_components": len(self._components),
            "health_distribution": health_counts,
            "circuit_breakers": circuit_counts,
            "active_faults": len(active_faults),
            "total_faults": len(self._fault_history),
            "recovery_plans": len(self._recovery_plans),
            "successful_recoveries": sum(
                1 for p in self._recovery_plans.values()
                if p.success is True
            ),
        }

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        return {
            "timestamp": datetime.now().isoformat(),
            "components": [c.to_dict() for c in self._components.values()],
            "circuit_breakers": [cb.to_dict() for cb in self._circuit_breakers.values()],
            "active_faults": [f.to_dict() for f in self.get_active_faults()],
            "statistics": self.get_statistics(),
        }


# ============================================
# Singleton Instance
# ============================================

_orchestrator: Optional[SelfHealingOrchestrator] = None
_orchestrator_lock = threading.Lock()


def get_self_healing_orchestrator() -> SelfHealingOrchestrator:
    """Get or create the self-healing orchestrator singleton."""
    global _orchestrator

    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:
                _orchestrator = SelfHealingOrchestrator()

    return _orchestrator


# ============================================
# Decorator for Protected Functions
# ============================================

def self_healing(
    component: str,
    fault_type: FaultType = FaultType.SOFTWARE_ERROR,
    max_retries: int = 3,
):
    """
    Decorator for automatic fault handling and recovery.

    Usage:
        @self_healing(component="api_service")
        def my_function():
            ...
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            orchestrator = get_self_healing_orchestrator()
            cb = orchestrator._circuit_breakers.get(component)

            if cb and not cb.allow_request():
                raise Exception(f"Circuit breaker open for {component}")

            for attempt in range(max_retries):
                try:
                    result = await func(*args, **kwargs)
                    if cb:
                        cb.record_success()
                    return result
                except Exception as e:
                    orchestrator.report_fault(
                        component=component,
                        fault_type=fault_type,
                        message=str(e),
                        severity=3 if attempt < max_retries - 1 else 4,
                    )
                    if attempt == max_retries - 1:
                        raise

        def sync_wrapper(*args, **kwargs):
            orchestrator = get_self_healing_orchestrator()
            cb = orchestrator._circuit_breakers.get(component)

            if cb and not cb.allow_request():
                raise Exception(f"Circuit breaker open for {component}")

            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    if cb:
                        cb.record_success()
                    return result
                except Exception as e:
                    orchestrator.report_fault(
                        component=component,
                        fault_type=fault_type,
                        message=str(e),
                        severity=3 if attempt < max_retries - 1 else 4,
                    )
                    if attempt == max_retries - 1:
                        raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


__all__ = [
    'CircuitState',
    'HealthLevel',
    'RecoveryAction',
    'FaultType',
    'Fault',
    'RecoveryPlan',
    'ComponentHealth',
    'CircuitBreaker',
    'SelfHealingOrchestrator',
    'get_self_healing_orchestrator',
    'self_healing',
]
