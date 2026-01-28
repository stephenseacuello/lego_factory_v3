"""
Job Event Simulator for OEE Testing.

Generates synthetic job events to test OEE calculations.
Simulates realistic job patterns with configurable:
- Cycle times
- Quality rates
- Job frequency
"""
import random
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from cnc_interfaces.msg import JobEvent


class JobSimulatorNode(Node):
    """Simulates job events for OEE testing."""

    def __init__(self):
        super().__init__('job_simulator')

        # Parameters
        self.declare_parameter('machine_id', 'tinyg_sim_001')
        self.declare_parameter('ideal_cycle_time', 60.0)  # seconds
        self.declare_parameter('cycle_time_variance', 0.15)  # 15% variance
        self.declare_parameter('quality_rate', 0.95)  # 95% pass rate
        self.declare_parameter('jobs_per_hour', 30)

        self.machine_id = self.get_parameter('machine_id').value
        self.ideal_cycle_time = self.get_parameter('ideal_cycle_time').value
        self.cycle_variance = self.get_parameter('cycle_time_variance').value
        self.quality_rate = self.get_parameter('quality_rate').value
        self.jobs_per_hour = self.get_parameter('jobs_per_hour').value

        # QoS
        reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Publisher
        self.job_pub = self.create_publisher(
            JobEvent,
            '/job/events',
            reliable_qos
        )

        # State
        self.job_counter = 0
        self.current_job_id = None
        self.job_start_time = None

        # Calculate interval between jobs
        interval = 3600.0 / self.jobs_per_hour
        self.create_timer(interval, self._simulate_job)

        self.get_logger().info('=' * 50)
        self.get_logger().info('Job Simulator Started')
        self.get_logger().info('=' * 50)
        self.get_logger().info(f'  Machine: {self.machine_id}')
        self.get_logger().info(f'  Cycle Time: {self.ideal_cycle_time}s +/- {self.cycle_variance*100}%')
        self.get_logger().info(f'  Quality Rate: {self.quality_rate*100}%')
        self.get_logger().info(f'  Jobs/Hour: {self.jobs_per_hour}')
        self.get_logger().info('=' * 50)

    def _simulate_job(self):
        """Simulate a complete job cycle."""
        self.job_counter += 1
        job_id = f'JOB-{self.job_counter:06d}'

        # Start event
        start_msg = JobEvent()
        start_msg.header.stamp = self.get_clock().now().to_msg()
        start_msg.job_id = job_id
        start_msg.machine_id = self.machine_id
        start_msg.work_order_id = f'WO-{(self.job_counter // 10) + 1:04d}'
        start_msg.part_number = 'PART-001'
        start_msg.event_type = JobEvent.EVENT_START
        start_msg.operator_id = 'OP-001'
        start_msg.shift_id = 'SHIFT-A'

        self.job_pub.publish(start_msg)
        self.get_logger().debug(f'Job started: {job_id}')

        # Simulate cycle time with variance
        variance = random.uniform(-self.cycle_variance, self.cycle_variance)
        actual_cycle_time = self.ideal_cycle_time * (1 + variance)

        # Complete event (after simulated delay in real implementation)
        complete_msg = JobEvent()
        complete_msg.header.stamp = self.get_clock().now().to_msg()
        complete_msg.job_id = job_id
        complete_msg.machine_id = self.machine_id
        complete_msg.work_order_id = start_msg.work_order_id
        complete_msg.part_number = start_msg.part_number
        complete_msg.event_type = JobEvent.EVENT_COMPLETE
        complete_msg.cycle_time = actual_cycle_time
        complete_msg.planned_time = self.ideal_cycle_time

        # Quality simulation
        if random.random() < self.quality_rate:
            complete_msg.passed_inspection = True
            complete_msg.quality_grade = random.randint(85, 100)
        else:
            complete_msg.passed_inspection = False
            complete_msg.quality_grade = random.randint(40, 70)
            complete_msg.reject_reason = random.choice([
                'Dimension out of tolerance',
                'Surface finish defect',
                'Tool marks',
                'Material defect'
            ])

        complete_msg.operator_id = 'OP-001'
        complete_msg.shift_id = 'SHIFT-A'

        self.job_pub.publish(complete_msg)

        status = 'PASS' if complete_msg.passed_inspection else 'REJECT'
        self.get_logger().info(
            f'Job {job_id}: {status} | Cycle: {actual_cycle_time:.1f}s | '
            f'Grade: {complete_msg.quality_grade}'
        )


def main(args=None):
    """Entry point for job_simulator node."""
    rclpy.init(args=args)

    node = JobSimulatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
