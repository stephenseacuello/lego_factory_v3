"""
Fleet Manager Node for Multi-Machine CNC Factory.

Central coordinator for:
- Machine registration and capability tracking
- Job dispatch with intelligent machine selection
- Machine allocation for maintenance/priority jobs
- Fleet-wide status aggregation

Services:
- /fleet/dispatch_job (DispatchJob) - Assign job to best machine
- /fleet/get_status (GetFleetStatus) - Get fleet-wide status
- /fleet/allocate (AllocateMachine) - Reserve machine for exclusive use

Subscribes to:
- /tinyg/status, /grbl/machine_status (MachineStatus) - Machine updates
- /kpi/oee (OeeMetrics) - OEE data for dispatch decisions

Publishes:
- /fleet/events (FleetEvent) - Fleet-level events
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from cnc_interfaces.msg import MachineStatus, OeeMetrics, FleetEvent
from cnc_interfaces.srv import DispatchJob, GetFleetStatus, AllocateMachine


@dataclass
class MachineInfo:
    """Tracks information about a registered machine."""
    machine_id: str
    machine_type: str = "unknown"
    capabilities: List[str] = field(default_factory=list)
    work_envelope: Dict[str, float] = field(default_factory=dict)
    max_spindle_rpm: int = 0

    # Runtime state
    status: Optional[MachineStatus] = None
    oee: Optional[OeeMetrics] = None
    last_seen: float = 0.0
    is_online: bool = False

    # Job queue
    job_queue: deque = field(default_factory=lambda: deque(maxlen=100))
    current_job: Optional[str] = None

    # Allocation
    allocated_to: Optional[str] = None
    allocation_reason: str = ""
    allocation_expires: float = 0.0


class FleetManagerNode(Node):
    """Central coordinator for multi-machine factory."""

    def __init__(self):
        super().__init__('fleet_manager')

        # Parameters
        self.declare_parameter('heartbeat_timeout', 10.0)  # seconds
        self.declare_parameter('default_strategy', 1)  # LEAST_LOADED

        self.heartbeat_timeout = self.get_parameter('heartbeat_timeout').value
        self.default_strategy = self.get_parameter('default_strategy').value

        # Machine registry
        self.machines: Dict[str, MachineInfo] = {}

        # Round-robin counter
        self.rr_index = 0

        # QoS
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Status subscriptions (add more as needed)
        self.create_subscription(
            MachineStatus, '/tinyg/status',
            lambda m: self._status_callback(m), reliable_qos)
        self.create_subscription(
            MachineStatus, '/grbl/machine_status',
            lambda m: self._status_callback(m), reliable_qos)
        self.create_subscription(
            MachineStatus, '/machine/status',
            lambda m: self._status_callback(m), reliable_qos)

        # OEE subscription
        self.create_subscription(
            OeeMetrics, '/kpi/oee',
            self._oee_callback, reliable_qos)

        # Fleet event publisher
        self.event_pub = self.create_publisher(
            FleetEvent, '/fleet/events', reliable_qos)

        # Services
        self.dispatch_srv = self.create_service(
            DispatchJob, '/fleet/dispatch_job', self._dispatch_callback)
        self.status_srv = self.create_service(
            GetFleetStatus, '/fleet/get_status', self._status_srv_callback)
        self.allocate_srv = self.create_service(
            AllocateMachine, '/fleet/allocate', self._allocate_callback)

        # Heartbeat check timer
        self.create_timer(5.0, self._check_heartbeats)

        self.get_logger().info('=' * 60)
        self.get_logger().info('Fleet Manager Started')
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'  Heartbeat Timeout: {self.heartbeat_timeout}s')
        self.get_logger().info(f'  Default Strategy: {self._strategy_name(self.default_strategy)}')
        self.get_logger().info('=' * 60)

    def _strategy_name(self, strategy: int) -> str:
        """Get human-readable strategy name."""
        names = {
            0: 'ROUND_ROBIN',
            1: 'LEAST_LOADED',
            2: 'HIGHEST_OEE',
            3: 'SHORTEST_QUEUE',
            4: 'MANUAL'
        }
        return names.get(strategy, 'UNKNOWN')

    def _status_callback(self, msg: MachineStatus):
        """Process machine status updates."""
        machine_id = msg.machine_id
        if not machine_id:
            return

        now = time.time()

        # Auto-register unknown machines
        if machine_id not in self.machines:
            self.machines[machine_id] = MachineInfo(
                machine_id=machine_id,
                machine_type=msg.controller_type if msg.controller_type else 'unknown'
            )
            self.get_logger().info(f'Registered new machine: {machine_id}')
            self._publish_event(FleetEvent.EVENT_MACHINE_ONLINE, machine_id)

        machine = self.machines[machine_id]
        was_online = machine.is_online

        # Update status
        machine.status = msg
        machine.last_seen = now
        machine.is_online = True

        # Detect state changes
        if msg.state == MachineStatus.STATE_ALARM and (
            machine.status is None or machine.status.state != MachineStatus.STATE_ALARM
        ):
            self._publish_event(FleetEvent.EVENT_MACHINE_ALARM, machine_id,
                               f'Alarm: {msg.state_text}')

        if not was_online:
            self._publish_event(FleetEvent.EVENT_MACHINE_ONLINE, machine_id)

    def _oee_callback(self, msg: OeeMetrics):
        """Process OEE updates."""
        machine_id = msg.machine_id
        if machine_id in self.machines:
            self.machines[machine_id].oee = msg

    def _check_heartbeats(self):
        """Check for offline machines."""
        now = time.time()
        for machine_id, machine in self.machines.items():
            if machine.is_online and (now - machine.last_seen) > self.heartbeat_timeout:
                machine.is_online = False
                self.get_logger().warn(f'Machine offline: {machine_id}')
                self._publish_event(FleetEvent.EVENT_MACHINE_OFFLINE, machine_id)

            # Check allocation expiry
            if machine.allocated_to and machine.allocation_expires > 0:
                if now > machine.allocation_expires:
                    old_allocator = machine.allocated_to
                    machine.allocated_to = None
                    machine.allocation_reason = ""
                    machine.allocation_expires = 0.0
                    self.get_logger().info(
                        f'Allocation expired for {machine_id} (was: {old_allocator})')
                    self._publish_event(
                        FleetEvent.EVENT_ALLOCATION_CHANGED, machine_id,
                        f'Allocation expired for {old_allocator}')

    def _dispatch_callback(self, request, response):
        """Handle job dispatch requests."""
        job_id = request.job_id
        capabilities = list(request.required_capabilities)
        strategy = request.strategy if request.strategy != 0 else self.default_strategy

        self.get_logger().info(
            f'Dispatch request: {job_id}, caps={capabilities}, strategy={self._strategy_name(strategy)}')

        # Find capable machines
        candidates = self._find_capable_machines(capabilities)

        if not candidates:
            response.success = False
            response.message = f'No capable machines found for capabilities: {capabilities}'
            return response

        # Filter out allocated machines (unless forced)
        available = [m for m in candidates
                    if self.machines[m].allocated_to is None]

        if not available:
            response.success = False
            response.message = 'All capable machines are currently allocated'
            return response

        # Select by strategy
        if strategy == DispatchJob.Request.STRATEGY_MANUAL:
            if request.preferred_machine in available:
                selected = request.preferred_machine
            else:
                response.success = False
                response.message = f'Preferred machine {request.preferred_machine} not available'
                return response
        elif strategy == DispatchJob.Request.STRATEGY_ROUND_ROBIN:
            selected = self._select_round_robin(available)
        elif strategy == DispatchJob.Request.STRATEGY_LEAST_LOADED:
            selected = self._select_least_loaded(available)
        elif strategy == DispatchJob.Request.STRATEGY_HIGHEST_OEE:
            selected = self._select_highest_oee(available)
        elif strategy == DispatchJob.Request.STRATEGY_SHORTEST_QUEUE:
            selected = self._select_shortest_queue(available)
        else:
            selected = available[0]

        # Add to queue
        machine = self.machines[selected]
        machine.job_queue.append(job_id)
        queue_pos = len(machine.job_queue)

        # Estimate start time
        if machine.oee and machine.oee.actual_cycle_time > 0:
            estimated_start = (queue_pos - 1) * machine.oee.actual_cycle_time
        else:
            estimated_start = (queue_pos - 1) * request.estimated_cycle_time

        response.success = True
        response.assigned_machine = selected
        response.queue_position = queue_pos
        response.estimated_start_time = estimated_start
        response.message = f'Job {job_id} assigned to {selected}'

        self._publish_event(
            FleetEvent.EVENT_JOB_DISPATCHED, selected, job_id,
            [f'queue_pos={queue_pos}', f'strategy={self._strategy_name(strategy)}'])

        self.get_logger().info(f'Dispatched {job_id} to {selected} (queue pos: {queue_pos})')
        return response

    def _find_capable_machines(self, required_caps: List[str]) -> List[str]:
        """Find machines that have all required capabilities."""
        if not required_caps:
            # No specific requirements - return all online machines
            return [m_id for m_id, m in self.machines.items() if m.is_online]

        capable = []
        for machine_id, machine in self.machines.items():
            if not machine.is_online:
                continue
            if all(cap in machine.capabilities for cap in required_caps):
                capable.append(machine_id)

        # If no exact matches, return all online machines
        # (capabilities might not be configured)
        if not capable:
            return [m_id for m_id, m in self.machines.items() if m.is_online]

        return capable

    def _select_round_robin(self, candidates: List[str]) -> str:
        """Select machine using round-robin."""
        self.rr_index = (self.rr_index + 1) % len(candidates)
        return candidates[self.rr_index]

    def _select_least_loaded(self, candidates: List[str]) -> str:
        """Select machine with smallest queue."""
        return min(candidates,
                  key=lambda m: len(self.machines[m].job_queue))

    def _select_highest_oee(self, candidates: List[str]) -> str:
        """Select machine with highest OEE."""
        def get_oee(m_id):
            oee = self.machines[m_id].oee
            return oee.oee if oee else 0.5  # Default 50% if unknown
        return max(candidates, key=get_oee)

    def _select_shortest_queue(self, candidates: List[str]) -> str:
        """Select machine with shortest estimated queue time."""
        def queue_time(m_id):
            machine = self.machines[m_id]
            if machine.oee and machine.oee.actual_cycle_time > 0:
                return len(machine.job_queue) * machine.oee.actual_cycle_time
            return len(machine.job_queue) * 60.0  # Default 60s
        return min(candidates, key=queue_time)

    def _status_srv_callback(self, request, response):
        """Handle fleet status requests."""
        machine_filter = list(request.machine_filter) if request.machine_filter else None

        machines_list = []
        oee_list = []
        running = idle = alarm = offline = 0
        total_queued = 0

        for machine_id, machine in self.machines.items():
            if machine_filter and machine_id not in machine_filter:
                continue

            if machine.status:
                machines_list.append(machine.status)

            if request.include_oee and machine.oee:
                oee_list.append(machine.oee)

            if not machine.is_online:
                offline += 1
            elif machine.status:
                if machine.status.state == MachineStatus.STATE_RUN:
                    running += 1
                elif machine.status.state == MachineStatus.STATE_IDLE:
                    idle += 1
                elif machine.status.state == MachineStatus.STATE_ALARM:
                    alarm += 1

            total_queued += len(machine.job_queue)

        response.machines = machines_list
        response.oee_data = oee_list
        response.total_machines = len(self.machines)
        response.machines_running = running
        response.machines_idle = idle
        response.machines_alarm = alarm
        response.machines_offline = offline
        response.total_jobs_queued = total_queued

        # Calculate fleet average OEE
        if oee_list:
            response.fleet_oee = sum(o.oee for o in oee_list) / len(oee_list)
        else:
            response.fleet_oee = 0.0

        return response

    def _allocate_callback(self, request, response):
        """Handle machine allocation requests."""
        machine_id = request.machine_id

        if machine_id not in self.machines:
            response.success = False
            response.message = f'Unknown machine: {machine_id}'
            return response

        machine = self.machines[machine_id]

        # Check if already allocated
        if machine.allocated_to and not request.force:
            response.success = False
            response.message = f'Machine already allocated to {machine.allocated_to}'
            response.previous_allocation = machine.allocated_to
            return response

        # Store previous allocation for response
        response.previous_allocation = machine.allocated_to or ''

        # Set allocation
        machine.allocated_to = request.requester_id
        machine.allocation_reason = request.reason
        if request.duration_minutes > 0:
            machine.allocation_expires = time.time() + (request.duration_minutes * 60)
            response.expires_at.sec = int(machine.allocation_expires)
        else:
            machine.allocation_expires = 0.0

        response.success = True
        response.message = f'Machine {machine_id} allocated to {request.requester_id}'

        self._publish_event(
            FleetEvent.EVENT_ALLOCATION_CHANGED, machine_id,
            f'Allocated to {request.requester_id}',
            [f'reason={request.reason}', f'duration={request.duration_minutes}min'])

        self.get_logger().info(
            f'Allocated {machine_id} to {request.requester_id} ({request.reason})')
        return response

    def _publish_event(self, event_type: int, machine_id: str,
                       message: str = '', details: List[str] = None):
        """Publish fleet event."""
        msg = FleetEvent()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.event_type = event_type
        msg.machine_id = machine_id
        msg.message = message
        msg.details = details or []
        self.event_pub.publish(msg)


def main(args=None):
    """Entry point for fleet_manager node."""
    rclpy.init(args=args)

    node = FleetManagerNode()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
