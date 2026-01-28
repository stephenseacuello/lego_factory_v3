#!/usr/bin/env python3
"""
Scheduler Node - Job scheduling and optimization for CNC machines

Provides intelligent job scheduling with optimization for:
- Minimize makespan (total completion time)
- Balance machine load
- Meet due dates
- Handle priorities
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import heapq

from std_msgs.msg import String
from cnc_interfaces.msg import ScheduleJob, JobEvent, MachineStatus
from cnc_interfaces.srv import ScheduleJobs, DispatchJob


@dataclass
class JobQueue:
    """Priority queue for machine jobs"""
    machine_id: str
    jobs: List[ScheduleJob] = field(default_factory=list)
    current_job: Optional[ScheduleJob] = None
    estimated_completion: Optional[datetime] = None


class SchedulerNode(Node):
    """Job scheduling service"""

    def __init__(self):
        super().__init__('scheduler_node')

        # Parameters
        self.declare_parameter('optimization_goal', 'minimize_makespan')
        self.declare_parameter('rebalance_interval', 60.0)
        self.declare_parameter('max_queue_per_machine', 100)

        self.opt_goal = self.get_parameter('optimization_goal').value
        self.rebalance_interval = self.get_parameter('rebalance_interval').value
        self.max_queue = self.get_parameter('max_queue_per_machine').value

        # Machine queues
        self.queues: Dict[str, JobQueue] = {}
        self.machine_status: Dict[str, MachineStatus] = {}
        self.all_jobs: Dict[str, ScheduleJob] = {}

        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST, depth=10
        )

        # Subscribers
        self.status_sub = self.create_subscription(
            MachineStatus, '/machine/status', self.status_callback, qos)

        self.job_event_sub = self.create_subscription(
            JobEvent, '/job/events', self.job_event_callback, qos)

        # Publishers
        self.schedule_pub = self.create_publisher(ScheduleJob, '/scheduler/jobs', qos)
        self.event_pub = self.create_publisher(JobEvent, '/scheduler/events', qos)

        # Services
        self.schedule_srv = self.create_service(
            ScheduleJobs, '/scheduler/schedule_jobs', self.schedule_callback)

        # Rebalancing timer
        self.rebalance_timer = self.create_timer(
            self.rebalance_interval, self.rebalance_callback)

        self.get_logger().info('Scheduler Node started')

    def status_callback(self, msg: MachineStatus):
        """Track machine status"""
        self.machine_status[msg.machine_id] = msg

        if msg.machine_id not in self.queues:
            self.queues[msg.machine_id] = JobQueue(machine_id=msg.machine_id)

    def job_event_callback(self, msg: JobEvent):
        """Handle job completion events"""
        if msg.event_type == 'completed':
            queue = self.queues.get(msg.machine_id)
            if queue and queue.current_job:
                if queue.current_job.job_id == msg.job_id:
                    queue.current_job = None
                    self.dispatch_next_job(msg.machine_id)

    def schedule_callback(self, request, response):
        """Schedule jobs across machines"""
        jobs = list(request.jobs_to_schedule)
        available_machines = list(request.available_machines) or list(self.queues.keys())

        if request.reschedule_all:
            # Gather all pending jobs
            for queue in self.queues.values():
                jobs.extend(queue.jobs)
                queue.jobs = []

        # Sort by priority and due date
        jobs.sort(key=lambda j: (-j.priority, j.due_date.sec if j.due_date.sec > 0 else float('inf')))

        scheduled = []
        failed = []

        for job in jobs:
            # Find capable machines
            capable = [m for m in available_machines if m in job.capable_machines] or available_machines

            if not capable:
                failed.append(job)
                continue

            # Select best machine based on optimization goal
            best_machine = self.select_machine(job, capable)

            if best_machine and len(self.queues[best_machine].jobs) < self.max_queue:
                job.assigned_machine_id = best_machine
                job.status = ScheduleJob.STATUS_SCHEDULED
                self.queues[best_machine].jobs.append(job)
                self.all_jobs[job.job_id] = job
                scheduled.append(job)

                # Publish scheduled job
                self.schedule_pub.publish(job)
            else:
                failed.append(job)

        # Calculate metrics
        total_time = sum(j.estimated_runtime for j in scheduled)

        response.success = len(failed) == 0
        response.message = f"Scheduled {len(scheduled)} jobs, {len(failed)} failed"
        response.scheduled_jobs = scheduled
        response.jobs_scheduled = len(scheduled)
        response.jobs_failed = len(failed)
        response.estimated_makespan = float(total_time)
        response.schedule_efficiency = len(scheduled) / max(len(jobs), 1)

        return response

    def select_machine(self, job: ScheduleJob, machines: List[str]) -> Optional[str]:
        """Select best machine for job based on optimization goal"""
        if not machines:
            return None

        if self.opt_goal == 'balance_load':
            # Select machine with shortest queue
            return min(machines, key=lambda m: len(self.queues.get(m, JobQueue(m)).jobs))

        elif self.opt_goal == 'minimize_lateness':
            # Select machine that can complete soonest
            return min(machines, key=lambda m: self.estimate_completion_time(m, job))

        else:  # minimize_makespan
            # Select machine with earliest completion of current queue
            return min(machines, key=lambda m: sum(
                j.estimated_runtime for j in self.queues.get(m, JobQueue(m)).jobs
            ))

    def estimate_completion_time(self, machine_id: str, new_job: ScheduleJob) -> float:
        """Estimate when a new job would complete on a machine"""
        queue = self.queues.get(machine_id, JobQueue(machine_id))
        queue_time = sum(j.estimated_runtime for j in queue.jobs)
        return queue_time + new_job.estimated_runtime

    def dispatch_next_job(self, machine_id: str):
        """Dispatch next job from queue to machine"""
        queue = self.queues.get(machine_id)
        if not queue or not queue.jobs:
            return

        job = queue.jobs.pop(0)
        job.status = ScheduleJob.STATUS_RUNNING
        queue.current_job = job

        # Publish event
        event = JobEvent()
        event.header.stamp = self.get_clock().now().to_msg()
        event.machine_id = machine_id
        event.job_id = job.job_id
        event.event_type = 'started'
        self.event_pub.publish(event)

        self.schedule_pub.publish(job)

    def rebalance_callback(self):
        """Periodically rebalance jobs across machines"""
        # Simple rebalancing: move jobs from overloaded to underloaded machines
        if len(self.queues) < 2:
            return

        queue_sizes = [(len(q.jobs), mid) for mid, q in self.queues.items()]
        if not queue_sizes:
            return

        max_queue = max(queue_sizes)
        min_queue = min(queue_sizes)

        # If imbalance is significant, move a job
        if max_queue[0] - min_queue[0] > 3:
            from_queue = self.queues[max_queue[1]]
            to_queue = self.queues[min_queue[1]]

            if from_queue.jobs:
                # Move lowest priority job
                job = from_queue.jobs.pop()
                job.assigned_machine_id = min_queue[1]
                to_queue.jobs.append(job)
                self.get_logger().info(
                    f"Rebalanced job {job.job_id} from {max_queue[1]} to {min_queue[1]}")


def main(args=None):
    rclpy.init(args=args)
    node = SchedulerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
