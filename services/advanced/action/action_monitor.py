"""
Action Monitor - Real-time action execution monitoring.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class MonitoringLevel(Enum):
    """Level of monitoring intensity."""
    MINIMAL = "minimal"      # Basic completion check
    STANDARD = "standard"    # Progress tracking
    INTENSIVE = "intensive"  # Continuous sensor monitoring


@dataclass
class MonitoringConfig:
    """Configuration for action monitoring."""
    level: MonitoringLevel = MonitoringLevel.STANDARD
    poll_interval_ms: int = 1000
    timeout_seconds: float = 300.0
    verify_completion: bool = True
    track_metrics: bool = True


@dataclass
class MonitoringEvent:
    """Event during action monitoring."""
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    severity: str = "info"  # info, warning, error


@dataclass
class MonitoringResult:
    """Result of action monitoring."""
    action_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    success: bool
    events: List[MonitoringEvent] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    final_state: Dict[str, Any] = field(default_factory=dict)


class ActionMonitor:
    """
    Monitor action execution in real-time.

    Features:
    - Progress tracking
    - Anomaly detection
    - Metric collection
    - Timeout handling
    - Event logging
    """

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()
        self._state_provider: Optional[Callable] = None
        self._active_monitors: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, MonitoringResult] = {}
        self._listeners: List[Callable] = []

    def set_state_provider(self, provider: Callable) -> None:
        """Set function to get current equipment state."""
        self._state_provider = provider

    def add_listener(self, listener: Callable[[MonitoringEvent], None]) -> None:
        """Add event listener."""
        self._listeners.append(listener)

    async def start_monitoring(self,
                              action_id: str,
                              expected_outcome: Dict[str, Any]) -> None:
        """
        Start monitoring an action.

        Args:
            action_id: Unique action identifier
            expected_outcome: Expected state after action completes
        """
        if action_id in self._active_monitors:
            logger.warning(f"Already monitoring action {action_id}")
            return

        result = MonitoringResult(
            action_id=action_id,
            started_at=datetime.utcnow(),
            completed_at=None,
            success=False
        )
        self._results[action_id] = result

        # Start monitoring task
        task = asyncio.create_task(
            self._monitor_loop(action_id, expected_outcome, result)
        )
        self._active_monitors[action_id] = task

        await self._emit_event(MonitoringEvent(
            event_type="monitoring_started",
            timestamp=datetime.utcnow(),
            data={'action_id': action_id}
        ))

    async def stop_monitoring(self, action_id: str) -> Optional[MonitoringResult]:
        """Stop monitoring an action."""
        if action_id not in self._active_monitors:
            return self._results.get(action_id)

        task = self._active_monitors.pop(action_id)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        result = self._results.get(action_id)
        if result and result.completed_at is None:
            result.completed_at = datetime.utcnow()

        return result

    async def _monitor_loop(self,
                           action_id: str,
                           expected_outcome: Dict[str, Any],
                           result: MonitoringResult) -> None:
        """Main monitoring loop."""
        start_time = datetime.utcnow()
        timeout = timedelta(seconds=self.config.timeout_seconds)
        poll_interval = self.config.poll_interval_ms / 1000.0

        try:
            while datetime.utcnow() - start_time < timeout:
                # Get current state
                state = await self._get_state()

                if state:
                    # Check for anomalies
                    anomalies = self._detect_anomalies(state)
                    for anomaly in anomalies:
                        result.events.append(anomaly)
                        await self._emit_event(anomaly)

                    # Collect metrics
                    if self.config.track_metrics:
                        self._collect_metrics(state, result)

                    # Check for completion
                    if self.config.verify_completion:
                        if self._check_completion(state, expected_outcome):
                            result.success = True
                            result.completed_at = datetime.utcnow()
                            result.final_state = state

                            await self._emit_event(MonitoringEvent(
                                event_type="action_completed",
                                timestamp=datetime.utcnow(),
                                data={'action_id': action_id, 'success': True}
                            ))
                            return

                await asyncio.sleep(poll_interval)

            # Timeout
            result.success = False
            result.completed_at = datetime.utcnow()
            result.events.append(MonitoringEvent(
                event_type="timeout",
                timestamp=datetime.utcnow(),
                data={'action_id': action_id},
                severity="error"
            ))

        except asyncio.CancelledError:
            result.events.append(MonitoringEvent(
                event_type="monitoring_cancelled",
                timestamp=datetime.utcnow(),
                data={'action_id': action_id}
            ))
            raise

        except Exception as e:
            logger.error(f"Monitoring error for {action_id}: {e}")
            result.events.append(MonitoringEvent(
                event_type="error",
                timestamp=datetime.utcnow(),
                data={'action_id': action_id, 'error': str(e)},
                severity="error"
            ))

    async def _get_state(self) -> Optional[Dict[str, Any]]:
        """Get current equipment state."""
        if self._state_provider is None:
            return None

        try:
            if asyncio.iscoroutinefunction(self._state_provider):
                return await self._state_provider()
            else:
                return self._state_provider()
        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            return None

    def _detect_anomalies(self, state: Dict[str, Any]) -> List[MonitoringEvent]:
        """Detect anomalies in current state."""
        anomalies = []

        # Temperature anomalies
        temps = state.get('temperatures', {})
        for name, temp in temps.items():
            if 'target' in name:
                continue
            target_key = f"{name}_target"
            target = temps.get(target_key, 0)

            if target > 0 and abs(temp - target) > 10:
                anomalies.append(MonitoringEvent(
                    event_type="temperature_deviation",
                    timestamp=datetime.utcnow(),
                    data={
                        'heater': name,
                        'actual': temp,
                        'target': target,
                        'deviation': abs(temp - target)
                    },
                    severity="warning"
                ))

        # Error state
        if state.get('error'):
            anomalies.append(MonitoringEvent(
                event_type="equipment_error",
                timestamp=datetime.utcnow(),
                data={'error': state.get('error')},
                severity="error"
            ))

        return anomalies

    def _collect_metrics(self, state: Dict[str, Any], result: MonitoringResult) -> None:
        """Collect metrics from state."""
        timestamp = datetime.utcnow().isoformat()

        if 'metrics_history' not in result.metrics:
            result.metrics['metrics_history'] = []

        result.metrics['metrics_history'].append({
            'timestamp': timestamp,
            'temperatures': state.get('temperatures', {}),
            'progress': state.get('progress', 0),
            'status': state.get('status', 'unknown')
        })

        # Update summary metrics
        temps = state.get('temperatures', {})
        for name, temp in temps.items():
            if 'target' not in name:
                key = f"max_{name}"
                current_max = result.metrics.get(key, 0)
                result.metrics[key] = max(current_max, temp)

    def _check_completion(self,
                         state: Dict[str, Any],
                         expected: Dict[str, Any]) -> bool:
        """Check if action has completed successfully."""
        for key, expected_value in expected.items():
            actual_value = state.get(key)

            if actual_value is None:
                return False

            if isinstance(expected_value, dict):
                if expected_value.get('min') is not None:
                    if actual_value < expected_value['min']:
                        return False
                if expected_value.get('max') is not None:
                    if actual_value > expected_value['max']:
                        return False
                if expected_value.get('equals') is not None:
                    if actual_value != expected_value['equals']:
                        return False
            else:
                if actual_value != expected_value:
                    return False

        return True

    async def _emit_event(self, event: MonitoringEvent) -> None:
        """Emit event to listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
            except Exception as e:
                logger.error(f"Listener error: {e}")

    def get_result(self, action_id: str) -> Optional[MonitoringResult]:
        """Get monitoring result for action."""
        return self._results.get(action_id)

    def get_active_monitors(self) -> List[str]:
        """Get list of actively monitored actions."""
        return list(self._active_monitors.keys())

    async def wait_for_completion(self,
                                 action_id: str,
                                 timeout: float = 300.0) -> MonitoringResult:
        """Wait for action monitoring to complete."""
        if action_id not in self._active_monitors:
            result = self._results.get(action_id)
            if result:
                return result
            raise ValueError(f"Unknown action: {action_id}")

        task = self._active_monitors[action_id]

        try:
            await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            await self.stop_monitoring(action_id)

        return self._results[action_id]
