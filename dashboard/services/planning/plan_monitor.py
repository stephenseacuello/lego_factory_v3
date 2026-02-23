"""
Plan Monitor - Real-time plan execution monitoring.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 1: Multi-Agent Orchestration Framework
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import logging

from .htn_planner import Plan
from .plan_executor import PlanExecution, ExecutionState

logger = logging.getLogger(__name__)


class PlanStatus(Enum):
    """High-level plan status."""
    ON_TRACK = "on_track"
    DELAYED = "delayed"
    AT_RISK = "at_risk"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PlanMetrics:
    """Plan execution metrics."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0
    total_retries: int = 0
    estimated_duration: float = 0
    actual_duration: float = 0
    efficiency: float = 1.0


class PlanMonitor:
    """
    Monitor plan execution with replanning capability.

    Features:
    - Real-time progress tracking
    - Deviation detection
    - Performance metrics
    - Replanning triggers
    - Alert generation
    """

    def __init__(self,
                 delay_threshold: float = 0.2,
                 failure_threshold: int = 2):
        self.delay_threshold = delay_threshold  # 20% delay triggers alert
        self.failure_threshold = failure_threshold
        self._monitored: Dict[str, Dict[str, Any]] = {}
        self._alerts: List[Dict[str, Any]] = []
        self._replan_callback: Optional[Callable] = None

    def set_replan_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for replanning requests."""
        self._replan_callback = callback

    def start_monitoring(self, execution: PlanExecution) -> None:
        """Start monitoring a plan execution."""
        plan_id = execution.plan.plan_id
        self._monitored[plan_id] = {
            'execution': execution,
            'start_time': datetime.utcnow(),
            'checkpoints': [],
            'metrics': PlanMetrics(
                total_tasks=len(execution.plan.tasks),
                estimated_duration=execution.plan.estimated_duration
            ),
            'status': PlanStatus.ON_TRACK
        }
        logger.info(f"Monitoring started for plan {plan_id}")

    def update(self, plan_id: str) -> PlanStatus:
        """Update monitoring state and check for issues."""
        if plan_id not in self._monitored:
            return PlanStatus.FAILED

        data = self._monitored[plan_id]
        execution = data['execution']
        metrics = data['metrics']

        # Update metrics
        metrics.completed_tasks = sum(
            1 for t in execution.task_executions
            if t.state == ExecutionState.COMPLETED
        )
        metrics.failed_tasks = sum(
            1 for t in execution.task_executions
            if t.state == ExecutionState.FAILED
        )
        metrics.total_retries = sum(
            t.retries for t in execution.task_executions
        )

        if execution.started_at:
            metrics.actual_duration = (
                datetime.utcnow() - execution.started_at
            ).total_seconds()

        # Determine status
        status = self._determine_status(execution, metrics)
        data['status'] = status

        # Check for alerts
        self._check_alerts(plan_id, status, metrics)

        return status

    def _determine_status(self,
                         execution: PlanExecution,
                         metrics: PlanMetrics) -> PlanStatus:
        """Determine current plan status."""
        if execution.state == ExecutionState.COMPLETED:
            return PlanStatus.COMPLETED

        if execution.state == ExecutionState.FAILED:
            return PlanStatus.FAILED

        if execution.state == ExecutionState.PAUSED:
            return PlanStatus.BLOCKED

        # Check if on track
        if metrics.total_tasks > 0:
            expected_progress = (
                metrics.actual_duration / metrics.estimated_duration
            ) if metrics.estimated_duration > 0 else 0

            actual_progress = metrics.completed_tasks / metrics.total_tasks

            if actual_progress < expected_progress * (1 - self.delay_threshold):
                if metrics.failed_tasks >= self.failure_threshold:
                    return PlanStatus.AT_RISK
                return PlanStatus.DELAYED

        return PlanStatus.ON_TRACK

    def _check_alerts(self,
                      plan_id: str,
                      status: PlanStatus,
                      metrics: PlanMetrics) -> None:
        """Check for alert conditions."""
        if status == PlanStatus.DELAYED:
            self._add_alert(plan_id, 'delay', 'Plan execution is delayed')

        if status == PlanStatus.AT_RISK:
            self._add_alert(plan_id, 'risk', 'Plan at risk due to failures')
            if self._replan_callback:
                self._replan_callback(plan_id, 'failures')

        if metrics.total_retries > metrics.total_tasks * 0.5:
            self._add_alert(plan_id, 'retries', 'High retry rate detected')

    def _add_alert(self, plan_id: str, alert_type: str, message: str) -> None:
        """Add an alert."""
        alert = {
            'plan_id': plan_id,
            'type': alert_type,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        self._alerts.append(alert)
        logger.warning(f"Plan alert: {message}")

    def get_metrics(self, plan_id: str) -> Optional[PlanMetrics]:
        """Get plan metrics."""
        if plan_id in self._monitored:
            return self._monitored[plan_id]['metrics']
        return None

    def get_status(self, plan_id: str) -> Optional[PlanStatus]:
        """Get plan status."""
        if plan_id in self._monitored:
            return self._monitored[plan_id]['status']
        return None

    def get_alerts(self,
                   plan_id: Optional[str] = None,
                   since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get alerts, optionally filtered."""
        alerts = self._alerts

        if plan_id:
            alerts = [a for a in alerts if a['plan_id'] == plan_id]

        if since:
            alerts = [
                a for a in alerts
                if datetime.fromisoformat(a['timestamp']) > since
            ]

        return alerts

    def get_summary(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get monitoring summary."""
        if plan_id not in self._monitored:
            return None

        data = self._monitored[plan_id]
        metrics = data['metrics']

        return {
            'plan_id': plan_id,
            'status': data['status'].value,
            'progress': {
                'completed': metrics.completed_tasks,
                'total': metrics.total_tasks,
                'percentage': (
                    metrics.completed_tasks / metrics.total_tasks * 100
                    if metrics.total_tasks > 0 else 0
                )
            },
            'timing': {
                'estimated': metrics.estimated_duration,
                'actual': metrics.actual_duration,
                'variance': metrics.actual_duration - metrics.estimated_duration
            },
            'quality': {
                'failed_tasks': metrics.failed_tasks,
                'retries': metrics.total_retries
            },
            'alerts': len([a for a in self._alerts if a['plan_id'] == plan_id])
        }

    def stop_monitoring(self, plan_id: str) -> None:
        """Stop monitoring a plan."""
        if plan_id in self._monitored:
            del self._monitored[plan_id]
            logger.info(f"Monitoring stopped for plan {plan_id}")
