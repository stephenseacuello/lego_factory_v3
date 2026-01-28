"""
OEE Aggregator Node for CNC Machines.

Calculates Overall Equipment Effectiveness (OEE) metrics:
- Availability = Run Time / Planned Production Time
- Performance = (Ideal Cycle Time x Total Count) / Run Time
- Quality = Good Count / Total Count
- OEE = Availability x Performance x Quality

Subscribes to:
- /machine/status (MachineStatus) - Machine state changes
- /job/events (JobEvent) - Job lifecycle events

Publishes to:
- /kpi/oee (OeeMetrics) - Calculated OEE metrics

Exposes Prometheus metrics on port 9100 for Grafana integration.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from collections import deque
from threading import Thread

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from cnc_interfaces.msg import MachineStatus, JobEvent, OeeMetrics

# Prometheus metrics (optional - graceful fallback if not available)
try:
    from prometheus_client import Gauge, Counter, Histogram, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


@dataclass
class MachineOeeState:
    """Tracks OEE state for a single machine."""
    machine_id: str

    # Time tracking (seconds since epoch)
    shift_start: float = 0.0
    last_state_change: float = 0.0

    # Cumulative time (seconds)
    planned_time: float = 0.0
    run_time: float = 0.0
    idle_time: float = 0.0
    downtime: float = 0.0

    # Counts
    total_count: int = 0
    good_count: int = 0
    reject_count: int = 0

    # Cycle time tracking
    ideal_cycle_time: float = 60.0  # Default 60 seconds
    cycle_times: deque = field(default_factory=lambda: deque(maxlen=100))

    # Current state
    current_state: int = MachineStatus.STATE_IDLE
    current_job_id: Optional[str] = None

    # Failure tracking for MTBF/MTTR
    failure_times: list = field(default_factory=list)
    repair_times: list = field(default_factory=list)

    def reset_shift(self):
        """Reset counters for new shift."""
        self.shift_start = time.time()
        self.last_state_change = self.shift_start
        self.planned_time = 0.0
        self.run_time = 0.0
        self.idle_time = 0.0
        self.downtime = 0.0
        self.total_count = 0
        self.good_count = 0
        self.reject_count = 0
        self.cycle_times.clear()


class OeeAggregatorNode(Node):
    """Real-time OEE calculation for multiple CNC machines."""

    def __init__(self):
        super().__init__('oee_aggregator')

        # Parameters
        self.declare_parameter('publish_rate', 1.0)  # Hz
        self.declare_parameter('shift_duration_hours', 8.0)
        self.declare_parameter('prometheus_port', 9100)
        self.declare_parameter('machines', ['tinyg_sim_001', 'grbl_sim_001'])

        self.publish_rate = self.get_parameter('publish_rate').value
        self.shift_duration = self.get_parameter('shift_duration_hours').value * 3600
        self.prometheus_port = self.get_parameter('prometheus_port').value
        self.machine_ids = self.get_parameter('machines').value

        # Machine state tracking
        self.machines: Dict[str, MachineOeeState] = {}
        for machine_id in self.machine_ids:
            self.machines[machine_id] = MachineOeeState(
                machine_id=machine_id,
                shift_start=time.time(),
                last_state_change=time.time()
            )

        # QoS profiles
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Subscriptions
        self.status_sub = self.create_subscription(
            MachineStatus,
            '/machine/status',
            self._status_callback,
            reliable_qos
        )

        self.tinyg_sub = self.create_subscription(
            MachineStatus,
            '/tinyg/status',
            self._status_callback,
            reliable_qos
        )

        self.grbl_sub = self.create_subscription(
            MachineStatus,
            '/grbl/machine_status',
            self._status_callback,
            reliable_qos
        )

        self.job_sub = self.create_subscription(
            JobEvent,
            '/job/events',
            self._job_callback,
            reliable_qos
        )

        # Publisher
        self.oee_pub = self.create_publisher(
            OeeMetrics,
            '/kpi/oee',
            reliable_qos
        )

        # Prometheus metrics setup
        self._setup_prometheus()

        # Calculation timer
        self.create_timer(1.0 / self.publish_rate, self._calculate_and_publish)

        # Shift reset timer (check every minute)
        self.create_timer(60.0, self._check_shift_reset)

        self.get_logger().info('=' * 60)
        self.get_logger().info('OEE Aggregator Started')
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'  Machines: {self.machine_ids}')
        self.get_logger().info(f'  Publish Rate: {self.publish_rate} Hz')
        self.get_logger().info(f'  Shift Duration: {self.shift_duration / 3600} hours')
        if PROMETHEUS_AVAILABLE:
            self.get_logger().info(f'  Prometheus: http://localhost:{self.prometheus_port}/metrics')
        self.get_logger().info('=' * 60)

    def _setup_prometheus(self):
        """Initialize Prometheus metrics."""
        if not PROMETHEUS_AVAILABLE:
            self.get_logger().warn('prometheus_client not available - metrics disabled')
            return

        # Gauges for current values
        self.prom_oee = Gauge('cnc_oee_score', 'Overall OEE score (0-1)', ['machine_id'])
        self.prom_availability = Gauge('cnc_oee_availability', 'Availability (0-1)', ['machine_id'])
        self.prom_performance = Gauge('cnc_oee_performance', 'Performance (0-1)', ['machine_id'])
        self.prom_quality = Gauge('cnc_oee_quality', 'Quality (0-1)', ['machine_id'])

        self.prom_run_time = Gauge('cnc_run_time_seconds', 'Total run time', ['machine_id'])
        self.prom_downtime = Gauge('cnc_downtime_seconds', 'Total downtime', ['machine_id'])
        self.prom_idle_time = Gauge('cnc_idle_time_seconds', 'Total idle time', ['machine_id'])

        self.prom_total_count = Gauge('cnc_total_parts', 'Total parts produced', ['machine_id'])
        self.prom_good_count = Gauge('cnc_good_parts', 'Good parts produced', ['machine_id'])
        self.prom_reject_count = Gauge('cnc_rejected_parts', 'Rejected parts', ['machine_id'])

        self.prom_cycle_time = Gauge('cnc_cycle_time_seconds', 'Average cycle time', ['machine_id'])
        self.prom_mtbf = Gauge('cnc_mtbf_hours', 'Mean Time Between Failures', ['machine_id'])
        self.prom_mttr = Gauge('cnc_mttr_hours', 'Mean Time To Repair', ['machine_id'])

        self.prom_machine_state = Gauge('cnc_machine_state', 'Current machine state', ['machine_id'])

        # Counters for events
        self.prom_job_complete = Counter('cnc_jobs_completed_total', 'Total jobs completed', ['machine_id'])
        self.prom_job_reject = Counter('cnc_jobs_rejected_total', 'Total jobs rejected', ['machine_id'])

        # Histogram for cycle times
        self.prom_cycle_hist = Histogram(
            'cnc_cycle_time_histogram',
            'Cycle time distribution',
            ['machine_id'],
            buckets=[10, 30, 60, 120, 300, 600, 1800, 3600]
        )

        # Start Prometheus HTTP server in background thread
        try:
            start_http_server(self.prometheus_port)
            self.get_logger().info(f'Prometheus metrics server started on port {self.prometheus_port}')
        except Exception as e:
            self.get_logger().error(f'Failed to start Prometheus server: {e}')

    def _status_callback(self, msg: MachineStatus):
        """Process machine status updates."""
        machine_id = msg.machine_id
        if not machine_id:
            return

        # Auto-register unknown machines
        if machine_id not in self.machines:
            self.machines[machine_id] = MachineOeeState(
                machine_id=machine_id,
                shift_start=time.time(),
                last_state_change=time.time()
            )
            self.get_logger().info(f'Auto-registered machine: {machine_id}')

        state = self.machines[machine_id]
        now = time.time()
        elapsed = now - state.last_state_change

        # Accumulate time based on previous state
        if state.current_state == MachineStatus.STATE_RUN:
            state.run_time += elapsed
        elif state.current_state == MachineStatus.STATE_IDLE:
            state.idle_time += elapsed
        elif state.current_state in (MachineStatus.STATE_ALARM, MachineStatus.STATE_HOLD):
            state.downtime += elapsed

        # Track state transition for MTBF/MTTR
        if msg.state == MachineStatus.STATE_ALARM and state.current_state != MachineStatus.STATE_ALARM:
            state.failure_times.append(now)
        elif state.current_state == MachineStatus.STATE_ALARM and msg.state != MachineStatus.STATE_ALARM:
            if state.failure_times:
                repair_duration = now - state.failure_times[-1]
                state.repair_times.append(repair_duration)

        # Update state
        state.current_state = msg.state
        state.last_state_change = now

        # Update Prometheus machine state
        if PROMETHEUS_AVAILABLE:
            self.prom_machine_state.labels(machine_id=machine_id).set(msg.state)

    def _job_callback(self, msg: JobEvent):
        """Process job lifecycle events."""
        machine_id = msg.machine_id
        if machine_id not in self.machines:
            return

        state = self.machines[machine_id]

        if msg.event_type == JobEvent.EVENT_START:
            state.current_job_id = msg.job_id
            self.get_logger().debug(f'Job started: {msg.job_id} on {machine_id}')

        elif msg.event_type == JobEvent.EVENT_COMPLETE:
            state.total_count += 1
            if msg.passed_inspection:
                state.good_count += 1
            else:
                state.reject_count += 1

            # Track cycle time
            if msg.cycle_time > 0:
                state.cycle_times.append(msg.cycle_time)
                if PROMETHEUS_AVAILABLE:
                    self.prom_cycle_hist.labels(machine_id=machine_id).observe(msg.cycle_time)
                    self.prom_job_complete.labels(machine_id=machine_id).inc()

            state.current_job_id = None
            self.get_logger().debug(f'Job completed: {msg.job_id} on {machine_id}')

        elif msg.event_type == JobEvent.EVENT_REJECT:
            state.total_count += 1
            state.reject_count += 1
            if PROMETHEUS_AVAILABLE:
                self.prom_job_reject.labels(machine_id=machine_id).inc()

    def _calculate_oee(self, state: MachineOeeState) -> OeeMetrics:
        """Calculate OEE metrics for a machine."""
        msg = OeeMetrics()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.machine_id = state.machine_id

        # Calculate planned time (time since shift start)
        now = time.time()
        state.planned_time = now - state.shift_start

        # Availability = Run Time / Planned Production Time
        if state.planned_time > 0:
            msg.availability = min(1.0, state.run_time / state.planned_time)
        else:
            msg.availability = 1.0

        # Performance = (Ideal Cycle × Count) / Run Time
        if state.run_time > 0 and state.total_count > 0:
            expected_run_time = state.ideal_cycle_time * state.total_count
            msg.performance = min(1.0, expected_run_time / state.run_time)
        elif state.run_time > 0:
            msg.performance = 0.0
        else:
            msg.performance = 1.0

        # Quality = Good Count / Total Count
        if state.total_count > 0:
            msg.quality = state.good_count / state.total_count
        else:
            msg.quality = 1.0

        # OEE = A × P × Q
        msg.oee = msg.availability * msg.performance * msg.quality

        # Time metrics
        msg.planned_time = state.planned_time
        msg.run_time = state.run_time
        msg.downtime = state.downtime
        msg.idle_time = state.idle_time

        # Count metrics
        msg.total_count = state.total_count
        msg.good_count = state.good_count
        msg.reject_count = state.reject_count

        # Cycle time
        msg.ideal_cycle_time = state.ideal_cycle_time
        if state.cycle_times:
            msg.actual_cycle_time = sum(state.cycle_times) / len(state.cycle_times)
        else:
            msg.actual_cycle_time = 0.0

        # MTBF/MTTR
        if len(state.failure_times) > 1:
            intervals = [
                state.failure_times[i] - state.failure_times[i-1]
                for i in range(1, len(state.failure_times))
            ]
            msg.mtbf = (sum(intervals) / len(intervals)) / 3600  # Convert to hours
        else:
            msg.mtbf = 0.0

        if state.repair_times:
            msg.mttr = (sum(state.repair_times) / len(state.repair_times)) / 3600
        else:
            msg.mttr = 0.0

        # Time window
        msg.time_window = 'shift'

        return msg

    def _calculate_and_publish(self):
        """Calculate and publish OEE for all machines."""
        for machine_id, state in self.machines.items():
            # Update accumulated time for current state
            now = time.time()
            elapsed = now - state.last_state_change

            # Calculate OEE
            oee_msg = self._calculate_oee(state)

            # Publish
            self.oee_pub.publish(oee_msg)

            # Update Prometheus metrics
            if PROMETHEUS_AVAILABLE:
                self.prom_oee.labels(machine_id=machine_id).set(oee_msg.oee)
                self.prom_availability.labels(machine_id=machine_id).set(oee_msg.availability)
                self.prom_performance.labels(machine_id=machine_id).set(oee_msg.performance)
                self.prom_quality.labels(machine_id=machine_id).set(oee_msg.quality)

                self.prom_run_time.labels(machine_id=machine_id).set(oee_msg.run_time)
                self.prom_downtime.labels(machine_id=machine_id).set(oee_msg.downtime)
                self.prom_idle_time.labels(machine_id=machine_id).set(oee_msg.idle_time)

                self.prom_total_count.labels(machine_id=machine_id).set(oee_msg.total_count)
                self.prom_good_count.labels(machine_id=machine_id).set(oee_msg.good_count)
                self.prom_reject_count.labels(machine_id=machine_id).set(oee_msg.reject_count)

                self.prom_cycle_time.labels(machine_id=machine_id).set(oee_msg.actual_cycle_time)
                self.prom_mtbf.labels(machine_id=machine_id).set(oee_msg.mtbf)
                self.prom_mttr.labels(machine_id=machine_id).set(oee_msg.mttr)

    def _check_shift_reset(self):
        """Check if shift has ended and reset counters."""
        now = time.time()
        for machine_id, state in self.machines.items():
            if now - state.shift_start >= self.shift_duration:
                self.get_logger().info(f'Shift ended for {machine_id} - resetting OEE counters')
                state.reset_shift()


def main(args=None):
    """Entry point for oee_aggregator node."""
    rclpy.init(args=args)

    node = OeeAggregatorNode()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass  # Already shutdown


if __name__ == '__main__':
    main()
