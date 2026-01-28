"""
SPT (Shortest Processing Time) Scheduling Policy
=================================================
Prioritizes jobs with shortest processing time.

Advantages:
- Minimizes average flow time
- Maximizes throughput
- Good for high-volume environments

Disadvantages:
- May starve long jobs
- Ignores due dates

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


@register_policy("spt")
class SPTPolicy(SchedulingPolicy):
    """Shortest Processing Time scheduling policy."""

    @property
    def name(self) -> str:
        return "SPT"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Shortest Processing Time - minimizes average flow time"

    def suggest_schedule(self, state: ScheduleState) -> List[ScheduleDecision]:
        """
        Schedule jobs by shortest processing time first.
        """
        decisions = []
        now = datetime.now().timestamp()

        # Get pending jobs sorted by processing time (shortest first)
        pending = sorted(
            [j for j in state.jobs if j.status == JobStatus.PENDING],
            key=lambda j: j.processing_time_min
        )

        # Get available machines
        available = [m for m in state.machines if m.status == MachineStatus.AVAILABLE]

        # Assign jobs to machines
        for job in pending:
            if not available:
                break

            # Find compatible machine with best fit (consider setup time)
            best_machine = None
            best_total_time = float('inf')

            for machine in available:
                if machine.can_process(job):
                    setup_time = machine.get_setup_time(job)
                    total_time = job.processing_time_min + setup_time

                    if total_time < best_total_time:
                        best_total_time = total_time
                        best_machine = machine

            if best_machine:
                setup_time = best_machine.get_setup_time(job)

                decision = ScheduleDecision(
                    decision_id=self._generate_decision_id(),
                    job_id=job.job_id,
                    machine_id=best_machine.machine_id,
                    start_time=now,
                    priority=job.priority,
                    policy_name=self.name,
                    policy_version=self.version,
                    confidence=1.0,
                    features_used={
                        "processing_time": job.processing_time_min,
                        "setup_time": setup_time,
                        "total_time": best_total_time
                    },
                    reasoning=f"SPT: Processing time {job.processing_time_min:.1f}min (setup: {setup_time:.1f}min)"
                )
                decisions.append(decision)
                available.remove(best_machine)

        return decisions
