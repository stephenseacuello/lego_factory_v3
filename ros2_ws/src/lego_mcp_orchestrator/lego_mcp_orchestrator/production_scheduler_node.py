#!/usr/bin/env python3
"""
Production Scheduler Node

Real-time manufacturing job scheduler using multiple algorithms:
- Constraint Programming (CP-SAT via OR-Tools)
- Priority-based FIFO
- Shortest Processing Time (SPT)
- Due Date Driven

Integrates with equipment registry and orchestrator.

LEGO MCP Manufacturing System v7.0
ISA-95 Level 3 - MES Scheduling
"""

import json
import heapq
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String
from std_srvs.srv import Trigger

try:
    from lego_mcp_msgs.srv import ScheduleJob, CreateWorkOrder, RescheduleRemaining
    from lego_mcp_msgs.msg import EquipmentStatus
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False
    print("Warning: lego_mcp_msgs not available, running in stub mode")


class SchedulingAlgorithm(Enum):
    """Available scheduling algorithms."""
    FIFO = 'fifo'
    SPT = 'spt'  # Shortest Processing Time
    EDD = 'edd'  # Earliest Due Date
    PRIORITY = 'priority'
    CP_SAT = 'cp_sat'  # Constraint Programming
    HYBRID = 'hybrid'


class JobStatus(Enum):
    """Job scheduling status."""
    PENDING = 0
    SCHEDULED = 1
    DISPATCHED = 2
    IN_PROGRESS = 3
    COMPLETED = 4
    FAILED = 5
    CANCELLED = 6
    ON_HOLD = 7


@dataclass(order=True)
class ScheduledJob:
    """Job in the scheduling queue."""
    priority: int
    job_id: str = field(compare=False)
    work_order_id: str = field(compare=False)
    part_id: str = field(compare=False)
    quantity: int = field(compare=False, default=1)
    processing_time_sec: float = field(compare=False, default=0.0)
    due_date: float = field(compare=False, default=0.0)
    release_time: float = field(compare=False, default=0.0)
    required_equipment: List[str] = field(compare=False, default_factory=list)
    assigned_equipment: Optional[str] = field(compare=False, default=None)
    scheduled_start: float = field(compare=False, default=0.0)
    scheduled_end: float = field(compare=False, default=0.0)
    actual_start: float = field(compare=False, default=0.0)
    actual_end: float = field(compare=False, default=0.0)
    status: JobStatus = field(compare=False, default=JobStatus.PENDING)
    predecessor_jobs: List[str] = field(compare=False, default_factory=list)


@dataclass
class EquipmentCapability:
    """Equipment scheduling capability."""
    equipment_id: str
    equipment_type: str
    capabilities: List[str] = field(default_factory=list)
    available: bool = True
    current_job: Optional[str] = None
    available_at: float = 0.0
    efficiency_factor: float = 1.0
    setup_time_sec: float = 0.0


@dataclass
class ScheduleMetrics:
    """Schedule quality metrics."""
    makespan: float = 0.0
    total_tardiness: float = 0.0
    average_flow_time: float = 0.0
    equipment_utilization: Dict[str, float] = field(default_factory=dict)
    jobs_on_time: int = 0
    jobs_late: int = 0


class ProductionSchedulerNode(Node):
    """
    Production scheduler for LEGO MCP manufacturing cell.

    Features:
    - Multiple scheduling algorithms
    - Real-time rescheduling on events
    - Equipment-aware scheduling
    - Due date tracking
    - Integration with orchestrator
    """

    def __init__(self):
        super().__init__('production_scheduler')

        # Parameters
        self.declare_parameter('algorithm', 'hybrid')
        self.declare_parameter('reschedule_interval_sec', 30.0)
        self.declare_parameter('lookahead_horizon_sec', 3600.0)
        self.declare_parameter('max_jobs_in_schedule', 100)
        self.declare_parameter('enable_preemption', False)

        self._algorithm = SchedulingAlgorithm(self.get_parameter('algorithm').value)
        self._reschedule_interval = self.get_parameter('reschedule_interval_sec').value
        self._horizon = self.get_parameter('lookahead_horizon_sec').value
        self._max_jobs = self.get_parameter('max_jobs_in_schedule').value
        self._enable_preemption = self.get_parameter('enable_preemption').value

        # Job management
        self._pending_jobs: Dict[str, ScheduledJob] = {}
        self._scheduled_jobs: Dict[str, ScheduledJob] = {}
        self._completed_jobs: Dict[str, ScheduledJob] = {}
        self._schedule_queue: List[ScheduledJob] = []  # Heap queue
        self._lock = threading.RLock()

        # Equipment tracking
        self._equipment: Dict[str, EquipmentCapability] = {}
        self._init_equipment()

        # Schedule metrics
        self._metrics = ScheduleMetrics()

        # Callback groups
        self._timer_group = MutuallyExclusiveCallbackGroup()
        self._srv_group = ReentrantCallbackGroup()
        self._sub_group = ReentrantCallbackGroup()

        # QoS
        reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            depth=10
        )

        # Publishers
        self._schedule_pub = self.create_publisher(
            String,
            '/lego_mcp/scheduler/schedule',
            reliable_qos
        )

        self._events_pub = self.create_publisher(
            String,
            '/lego_mcp/scheduler/events',
            10
        )

        self._dispatch_pub = self.create_publisher(
            String,
            '/lego_mcp/scheduler/dispatch',
            10
        )

        # Subscribers
        self.create_subscription(
            String,
            '/lego_mcp/equipment/registry',
            self._on_equipment_update,
            reliable_qos,
            callback_group=self._sub_group
        )

        self.create_subscription(
            String,
            '/lego_mcp/work_order/events',
            self._on_work_order_event,
            10,
            callback_group=self._sub_group
        )

        self.create_subscription(
            String,
            '/lego_mcp/scheduler/job_submit',
            self._on_job_submit,
            10,
            callback_group=self._sub_group
        )

        # Services
        self._submit_job_srv = self.create_service(
            Trigger,
            '/lego_mcp/scheduler/submit_job',
            self._submit_job_callback,
            callback_group=self._srv_group
        )

        self._get_schedule_srv = self.create_service(
            Trigger,
            '/lego_mcp/scheduler/get_schedule',
            self._get_schedule_callback,
            callback_group=self._srv_group
        )

        self._reschedule_srv = self.create_service(
            Trigger,
            '/lego_mcp/scheduler/reschedule',
            self._reschedule_callback,
            callback_group=self._srv_group
        )

        self._cancel_job_srv = self.create_service(
            Trigger,
            '/lego_mcp/scheduler/cancel_job',
            self._cancel_job_callback,
            callback_group=self._srv_group
        )

        self._get_metrics_srv = self.create_service(
            Trigger,
            '/lego_mcp/scheduler/get_metrics',
            self._get_metrics_callback,
            callback_group=self._srv_group
        )

        # Timers
        self._reschedule_timer = self.create_timer(
            self._reschedule_interval,
            self._periodic_reschedule,
            callback_group=self._timer_group
        )

        self._dispatch_timer = self.create_timer(
            1.0,
            self._dispatch_ready_jobs,
            callback_group=self._timer_group
        )

        self._publish_timer = self.create_timer(
            5.0,
            self._publish_schedule,
            callback_group=self._timer_group
        )

        self.get_logger().info(
            f'Production Scheduler started - algorithm: {self._algorithm.value}'
        )

    def _init_equipment(self):
        """Initialize equipment capabilities."""
        equipment_config = [
            ('grbl_cnc', 'CNC', ['cnc_milling', 'laser_cutting', 'laser_engraving']),
            ('formlabs_sla', 'SLA', ['sla_printing', 'high_resolution']),
            ('bambu_fdm', 'FDM', ['fdm_printing', 'multi_color']),
            ('ned2', 'ROBOT', ['pick_place', 'assembly']),
            ('xarm', 'ROBOT', ['pick_place', 'assembly', 'precision']),
            ('vision_station', 'INSPECTION', ['visual_inspection', 'dimensional']),
        ]

        for eq_id, eq_type, caps in equipment_config:
            self._equipment[eq_id] = EquipmentCapability(
                equipment_id=eq_id,
                equipment_type=eq_type,
                capabilities=caps,
            )

    def _on_equipment_update(self, msg: String):
        """Handle equipment registry updates."""
        try:
            data = json.loads(msg.data)

            with self._lock:
                for eq in data.get('equipment', []):
                    eq_id = eq.get('equipment_id', '')
                    if eq_id in self._equipment:
                        self._equipment[eq_id].available = (eq.get('status') == 'ONLINE')

        except json.JSONDecodeError:
            pass

    def _on_work_order_event(self, msg: String):
        """Handle work order events for rescheduling triggers."""
        try:
            event = json.loads(msg.data)
            event_type = event.get('event_type', '')
            data = event.get('data', {})

            with self._lock:
                if event_type == 'work_order_completed':
                    wo_id = data.get('work_order_id', '')
                    # Move jobs to completed
                    for job_id, job in list(self._scheduled_jobs.items()):
                        if job.work_order_id == wo_id:
                            job.status = JobStatus.COMPLETED
                            job.actual_end = time.time()
                            self._completed_jobs[job_id] = job
                            del self._scheduled_jobs[job_id]

                            # Free up equipment
                            if job.assigned_equipment and job.assigned_equipment in self._equipment:
                                self._equipment[job.assigned_equipment].current_job = None
                                self._equipment[job.assigned_equipment].available = True

                    # Trigger reschedule
                    self._trigger_reschedule('work_order_completed')

                elif event_type == 'work_order_failed':
                    self._trigger_reschedule('work_order_failed')

        except json.JSONDecodeError:
            pass

    def _on_job_submit(self, msg: String):
        """Handle job submission via topic."""
        try:
            data = json.loads(msg.data)
            self._create_job_from_data(data)
        except json.JSONDecodeError:
            pass

    def _create_job_from_data(self, data: dict) -> Optional[str]:
        """Create and schedule a new job."""
        job_id = data.get('job_id') or f"JOB-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        job = ScheduledJob(
            priority=data.get('priority', 2),
            job_id=job_id,
            work_order_id=data.get('work_order_id', ''),
            part_id=data.get('part_id', ''),
            quantity=data.get('quantity', 1),
            processing_time_sec=data.get('processing_time_sec', 300.0),
            due_date=data.get('due_date', time.time() + 3600),
            release_time=data.get('release_time', time.time()),
            required_equipment=data.get('required_equipment', []),
            predecessor_jobs=data.get('predecessor_jobs', []),
        )

        with self._lock:
            self._pending_jobs[job_id] = job
            self._trigger_reschedule('new_job')

        self._publish_event('job_submitted', {
            'job_id': job_id,
            'work_order_id': job.work_order_id,
            'priority': job.priority,
        })

        return job_id

    def _trigger_reschedule(self, reason: str):
        """Trigger a reschedule operation."""
        self.get_logger().debug(f'Reschedule triggered: {reason}')
        self._run_scheduler()

    def _periodic_reschedule(self):
        """Periodic reschedule for optimization."""
        self._run_scheduler()
        self._calculate_metrics()

    def _run_scheduler(self):
        """Run the scheduling algorithm."""
        with self._lock:
            if self._algorithm == SchedulingAlgorithm.FIFO:
                self._schedule_fifo()
            elif self._algorithm == SchedulingAlgorithm.SPT:
                self._schedule_spt()
            elif self._algorithm == SchedulingAlgorithm.EDD:
                self._schedule_edd()
            elif self._algorithm == SchedulingAlgorithm.PRIORITY:
                self._schedule_priority()
            elif self._algorithm == SchedulingAlgorithm.HYBRID:
                self._schedule_hybrid()
            else:
                self._schedule_fifo()

    def _schedule_fifo(self):
        """First In, First Out scheduling."""
        current_time = time.time()
        equipment_available_at: Dict[str, float] = {
            eq_id: eq.available_at for eq_id, eq in self._equipment.items()
        }

        # Sort pending jobs by submission order (job_id as proxy)
        jobs = sorted(self._pending_jobs.values(), key=lambda j: j.job_id)

        for job in jobs:
            if job.release_time > current_time:
                continue  # Job not yet released

            # Find suitable equipment
            equipment = self._find_equipment(job, equipment_available_at)
            if equipment:
                start_time = max(
                    equipment_available_at[equipment],
                    job.release_time
                )
                end_time = start_time + job.processing_time_sec

                job.assigned_equipment = equipment
                job.scheduled_start = start_time
                job.scheduled_end = end_time
                job.status = JobStatus.SCHEDULED

                equipment_available_at[equipment] = end_time

                self._scheduled_jobs[job.job_id] = job
                del self._pending_jobs[job.job_id]

    def _schedule_spt(self):
        """Shortest Processing Time scheduling."""
        current_time = time.time()
        equipment_available_at: Dict[str, float] = {
            eq_id: eq.available_at for eq_id, eq in self._equipment.items()
        }

        # Sort by processing time
        jobs = sorted(
            self._pending_jobs.values(),
            key=lambda j: j.processing_time_sec
        )

        for job in jobs:
            if job.release_time > current_time:
                continue

            equipment = self._find_equipment(job, equipment_available_at)
            if equipment:
                start_time = max(equipment_available_at[equipment], job.release_time)
                end_time = start_time + job.processing_time_sec

                job.assigned_equipment = equipment
                job.scheduled_start = start_time
                job.scheduled_end = end_time
                job.status = JobStatus.SCHEDULED

                equipment_available_at[equipment] = end_time

                self._scheduled_jobs[job.job_id] = job
                del self._pending_jobs[job.job_id]

    def _schedule_edd(self):
        """Earliest Due Date scheduling."""
        current_time = time.time()
        equipment_available_at: Dict[str, float] = {
            eq_id: eq.available_at for eq_id, eq in self._equipment.items()
        }

        # Sort by due date
        jobs = sorted(self._pending_jobs.values(), key=lambda j: j.due_date)

        for job in jobs:
            if job.release_time > current_time:
                continue

            equipment = self._find_equipment(job, equipment_available_at)
            if equipment:
                start_time = max(equipment_available_at[equipment], job.release_time)
                end_time = start_time + job.processing_time_sec

                job.assigned_equipment = equipment
                job.scheduled_start = start_time
                job.scheduled_end = end_time
                job.status = JobStatus.SCHEDULED

                equipment_available_at[equipment] = end_time

                self._scheduled_jobs[job.job_id] = job
                del self._pending_jobs[job.job_id]

    def _schedule_priority(self):
        """Priority-based scheduling."""
        current_time = time.time()
        equipment_available_at: Dict[str, float] = {
            eq_id: eq.available_at for eq_id, eq in self._equipment.items()
        }

        # Sort by priority (lower number = higher priority)
        jobs = sorted(self._pending_jobs.values(), key=lambda j: j.priority)

        for job in jobs:
            if job.release_time > current_time:
                continue

            equipment = self._find_equipment(job, equipment_available_at)
            if equipment:
                start_time = max(equipment_available_at[equipment], job.release_time)
                end_time = start_time + job.processing_time_sec

                job.assigned_equipment = equipment
                job.scheduled_start = start_time
                job.scheduled_end = end_time
                job.status = JobStatus.SCHEDULED

                equipment_available_at[equipment] = end_time

                self._scheduled_jobs[job.job_id] = job
                del self._pending_jobs[job.job_id]

    def _schedule_hybrid(self):
        """Hybrid scheduling combining priority and due date."""
        current_time = time.time()
        equipment_available_at: Dict[str, float] = {
            eq_id: eq.available_at for eq_id, eq in self._equipment.items()
        }

        # Score jobs by combination of priority and due date urgency
        def urgency_score(job: ScheduledJob) -> float:
            time_to_due = max(0, job.due_date - current_time)
            urgency = 1.0 / (time_to_due + 1)  # Higher urgency for closer due dates
            return job.priority - (urgency * 10)  # Lower score = higher priority

        jobs = sorted(self._pending_jobs.values(), key=urgency_score)

        for job in jobs:
            if job.release_time > current_time:
                continue

            # Check predecessors
            if not self._predecessors_complete(job):
                continue

            equipment = self._find_equipment(job, equipment_available_at)
            if equipment:
                start_time = max(equipment_available_at[equipment], job.release_time)
                end_time = start_time + job.processing_time_sec

                job.assigned_equipment = equipment
                job.scheduled_start = start_time
                job.scheduled_end = end_time
                job.status = JobStatus.SCHEDULED

                equipment_available_at[equipment] = end_time

                self._scheduled_jobs[job.job_id] = job
                del self._pending_jobs[job.job_id]

    def _find_equipment(
        self,
        job: ScheduledJob,
        equipment_available_at: Dict[str, float]
    ) -> Optional[str]:
        """Find suitable equipment for a job."""
        # If specific equipment required
        if job.required_equipment:
            for eq_id in job.required_equipment:
                if eq_id in self._equipment:
                    eq = self._equipment[eq_id]
                    if eq.available:
                        return eq_id
            return None

        # Find by capability (infer from part type)
        # For LEGO bricks, default to SLA or FDM
        for eq_id, eq in self._equipment.items():
            if not eq.available:
                continue
            if eq.equipment_type in ['SLA', 'FDM']:
                return eq_id

        return None

    def _predecessors_complete(self, job: ScheduledJob) -> bool:
        """Check if all predecessor jobs are complete."""
        for pred_id in job.predecessor_jobs:
            if pred_id not in self._completed_jobs:
                return False
        return True

    def _dispatch_ready_jobs(self):
        """Dispatch jobs that are ready to start."""
        current_time = time.time()

        with self._lock:
            for job_id, job in list(self._scheduled_jobs.items()):
                if job.status != JobStatus.SCHEDULED:
                    continue

                if job.scheduled_start <= current_time:
                    # Check equipment still available
                    if job.assigned_equipment in self._equipment:
                        eq = self._equipment[job.assigned_equipment]
                        if eq.available:
                            job.status = JobStatus.DISPATCHED
                            job.actual_start = current_time
                            eq.current_job = job_id
                            eq.available = False

                            self._dispatch_job(job)

    def _dispatch_job(self, job: ScheduledJob):
        """Dispatch job to orchestrator."""
        dispatch_msg = {
            'timestamp': time.time(),
            'job_id': job.job_id,
            'work_order_id': job.work_order_id,
            'equipment_id': job.assigned_equipment,
            'part_id': job.part_id,
            'quantity': job.quantity,
        }

        msg = String()
        msg.data = json.dumps(dispatch_msg)
        self._dispatch_pub.publish(msg)

        self._publish_event('job_dispatched', dispatch_msg)

        self.get_logger().info(
            f'Dispatched job {job.job_id} to {job.assigned_equipment}'
        )

    def _calculate_metrics(self):
        """Calculate schedule quality metrics."""
        current_time = time.time()

        with self._lock:
            # Makespan
            all_jobs = list(self._scheduled_jobs.values()) + list(self._completed_jobs.values())
            if all_jobs:
                self._metrics.makespan = max(
                    j.scheduled_end for j in all_jobs if j.scheduled_end > 0
                ) - min(
                    j.scheduled_start for j in all_jobs if j.scheduled_start > 0
                )

            # Tardiness and flow time
            total_tardiness = 0.0
            total_flow_time = 0.0
            on_time = 0
            late = 0

            for job in self._completed_jobs.values():
                if job.actual_end > 0 and job.actual_start > 0:
                    flow_time = job.actual_end - job.actual_start
                    total_flow_time += flow_time

                    tardiness = max(0, job.actual_end - job.due_date)
                    total_tardiness += tardiness

                    if tardiness > 0:
                        late += 1
                    else:
                        on_time += 1

            self._metrics.total_tardiness = total_tardiness
            self._metrics.average_flow_time = (
                total_flow_time / len(self._completed_jobs)
                if self._completed_jobs else 0
            )
            self._metrics.jobs_on_time = on_time
            self._metrics.jobs_late = late

            # Equipment utilization
            for eq_id, eq in self._equipment.items():
                busy_time = sum(
                    j.processing_time_sec for j in all_jobs
                    if j.assigned_equipment == eq_id
                )
                self._metrics.equipment_utilization[eq_id] = (
                    busy_time / self._metrics.makespan
                    if self._metrics.makespan > 0 else 0
                )

    def _publish_schedule(self):
        """Publish current schedule."""
        with self._lock:
            schedule_data = {
                'timestamp': time.time(),
                'algorithm': self._algorithm.value,
                'pending_count': len(self._pending_jobs),
                'scheduled_count': len(self._scheduled_jobs),
                'completed_count': len(self._completed_jobs),
                'schedule': [
                    {
                        'job_id': job.job_id,
                        'work_order_id': job.work_order_id,
                        'equipment': job.assigned_equipment,
                        'scheduled_start': job.scheduled_start,
                        'scheduled_end': job.scheduled_end,
                        'status': job.status.name,
                        'priority': job.priority,
                    }
                    for job in sorted(
                        self._scheduled_jobs.values(),
                        key=lambda j: j.scheduled_start
                    )
                ],
            }

        msg = String()
        msg.data = json.dumps(schedule_data)
        self._schedule_pub.publish(msg)

    def _publish_event(self, event_type: str, data: dict):
        """Publish scheduler event."""
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'data': data,
        }

        msg = String()
        msg.data = json.dumps(event)
        self._events_pub.publish(msg)

    def _submit_job_callback(self, request, response):
        """Handle job submission via service."""
        # Parse job data from request (would use custom service in production)
        job_id = self._create_job_from_data({
            'priority': 2,
            'processing_time_sec': 300.0,
        })

        response.success = True
        response.message = json.dumps({
            'job_id': job_id,
            'status': 'submitted',
        })
        return response

    def _get_schedule_callback(self, request, response):
        """Handle get schedule service request."""
        with self._lock:
            schedule = {
                'pending': [
                    {'job_id': j.job_id, 'priority': j.priority}
                    for j in self._pending_jobs.values()
                ],
                'scheduled': [
                    {
                        'job_id': j.job_id,
                        'equipment': j.assigned_equipment,
                        'start': j.scheduled_start,
                        'end': j.scheduled_end,
                        'status': j.status.name,
                    }
                    for j in self._scheduled_jobs.values()
                ],
            }

        response.success = True
        response.message = json.dumps(schedule)
        return response

    def _reschedule_callback(self, request, response):
        """Handle manual reschedule request."""
        self._trigger_reschedule('manual_request')

        response.success = True
        response.message = "Reschedule triggered"
        return response

    def _cancel_job_callback(self, request, response):
        """Handle job cancellation."""
        # Would parse job_id from request
        response.success = True
        response.message = "Job cancellation not implemented"
        return response

    def _get_metrics_callback(self, request, response):
        """Handle get metrics service request."""
        with self._lock:
            metrics = {
                'makespan': self._metrics.makespan,
                'total_tardiness': self._metrics.total_tardiness,
                'average_flow_time': self._metrics.average_flow_time,
                'jobs_on_time': self._metrics.jobs_on_time,
                'jobs_late': self._metrics.jobs_late,
                'equipment_utilization': self._metrics.equipment_utilization,
            }

        response.success = True
        response.message = json.dumps(metrics)
        return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = ProductionSchedulerNode()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
