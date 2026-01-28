"""
EDD (Earliest Due Date) Scheduling Policy
==========================================
Prioritizes jobs with earliest due dates.

Advantages:
- Minimizes maximum lateness
- Good for meeting customer deadlines
- Reduces late deliveries

Disadvantages:
- May increase average flow time
- Ignores processing time efficiency

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


@register_policy("edd")
class EDDPolicy(SchedulingPolicy):
    """Earliest Due Date scheduling policy."""

    @property
    def name(self) -> str:
        return "EDD"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Earliest Due Date - minimizes maximum lateness"

    def suggest_schedule(self, state: ScheduleState) -> List[ScheduleDecision]:
        """
        Schedule jobs by earliest due date first.

        Jobs without due dates are scheduled last.
        """
        decisions = []
        now = datetime.now().timestamp()

        # Get pending jobs
        pending = [j for j in state.jobs if j.status == JobStatus.PENDING]

        # Sort by due date (jobs without due date go last)
        pending.sort(key=lambda j: j.due_date if j.due_date else float('inf'))

        # Get available machines
        available = [m for m in state.machines if m.status == MachineStatus.AVAILABLE]

        # Assign jobs to machines
        for job in pending:
            if not available:
                break

            # Find compatible machine
            for machine in available:
                if machine.can_process(job):
                    # Calculate slack
                    slack = job.slack_time
                    is_critical = slack is not None and slack < 0

                    decision = ScheduleDecision(
                        decision_id=self._generate_decision_id(),
                        job_id=job.job_id,
                        machine_id=machine.machine_id,
                        start_time=now,
                        priority=1 if is_critical else job.priority,  # Boost priority if critical
                        policy_name=self.name,
                        policy_version=self.version,
                        confidence=1.0,
                        features_used={
                            "due_date": job.due_date or 0,
                            "slack_time": slack or 0,
                            "is_critical": 1 if is_critical else 0,
                            "is_late": 1 if job.is_late else 0
                        },
                        reasoning=f"EDD: Due date priority, slack={slack:.1f}min" if slack else "EDD: No due date"
                    )
                    decisions.append(decision)
                    available.remove(machine)
                    break

        return decisions
