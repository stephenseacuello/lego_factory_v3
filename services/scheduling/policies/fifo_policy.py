"""
FIFO (First In First Out) Scheduling Policy
============================================
Simple queue-based scheduling - jobs processed in arrival order.

Advantages:
- Simple and fair
- No starvation
- Predictable

Disadvantages:
- Ignores due dates and priorities
- May cause late deliveries

Author: Flask CNC SCADA System
"""

from typing import List
from datetime import datetime

from services.scheduling.policy_interface import (
    SchedulingPolicy,
    ScheduleState,
    ScheduleDecision,
    JobStatus,
    MachineStatus,
    register_policy
)


@register_policy("fifo")
class FIFOPolicy(SchedulingPolicy):
    """First In First Out scheduling policy."""

    @property
    def name(self) -> str:
        return "FIFO"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "First In First Out - processes jobs in arrival order"

    def suggest_schedule(self, state: ScheduleState) -> List[ScheduleDecision]:
        """
        Schedule jobs in FIFO order.

        Jobs are assigned to available machines in the order they arrived.
        """
        decisions = []
        now = datetime.now().timestamp()

        # Get pending jobs sorted by creation/release time
        pending = sorted(
            [j for j in state.jobs if j.status == JobStatus.PENDING],
            key=lambda j: j.release_date or 0
        )

        # Get available machines
        available = [m for m in state.machines if m.status == MachineStatus.AVAILABLE]

        # Assign jobs to machines
        for job in pending:
            if not available:
                break

            # Find first compatible machine
            for machine in available:
                if machine.can_process(job):
                    decision = ScheduleDecision(
                        decision_id=self._generate_decision_id(),
                        job_id=job.job_id,
                        machine_id=machine.machine_id,
                        start_time=now,
                        priority=job.priority,
                        policy_name=self.name,
                        policy_version=self.version,
                        confidence=1.0,
                        features_used={"queue_position": pending.index(job)},
                        reasoning=f"FIFO: Job arrived at position {pending.index(job)}"
                    )
                    decisions.append(decision)
                    available.remove(machine)
                    break

        return decisions
