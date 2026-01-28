#!/usr/bin/env python3
"""
G-code Execution Action Server
==============================
ROS 2 Action server for long-running G-code program execution.
Provides progress feedback, cancellation support, and optional rosbag recording.

Features:
- Line-by-line G-code execution with progress feedback
- Feed override support
- Dry run mode (parse only)
- File or inline G-code support
- Cancellation handling
- Optional rosbag recording for traceability
"""

import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from cnc_interfaces.action import ExecuteGcode
from cnc_interfaces.srv import SendGcode, Home
from cnc_interfaces.msg import MachineStatus


class GcodeActionServer(Node):
    """
    Action server for G-code program execution.

    Subscribes to:
        - /machine/status: Real-time machine position/state

    Action Servers:
        - /execute_gcode: Long-running G-code execution

    Service Clients:
        - /cnc/send_gcode: Send individual G-code lines
        - /cnc/home: Home machine before execution (optional)
    """

    def __init__(self):
        super().__init__('gcode_action_server')

        # Parameters
        self.declare_parameter('machine_id', 'tinyg_001')
        self.declare_parameter('default_feed_rate', 1000.0)
        self.declare_parameter('enable_recording', False)
        self.declare_parameter('bag_output_dir', '/ros2_ws/bags')

        self.machine_id = self.get_parameter('machine_id').value
        self.default_feed_rate = self.get_parameter('default_feed_rate').value
        self.enable_recording = self.get_parameter('enable_recording').value
        self.bag_output_dir = self.get_parameter('bag_output_dir').value

        # Callback group for concurrent operations
        self.callback_group = ReentrantCallbackGroup()

        # Current machine state (from subscription)
        self.current_position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.current_state = 'unknown'
        self.current_feed_rate = 0.0
        self.current_spindle_speed = 0.0

        # Execution state
        self._goal_handle = None
        self._is_executing = False

        # Machine status subscription
        self.status_sub = self.create_subscription(
            MachineStatus,
            '/machine/status',
            self._status_callback,
            10,
            callback_group=self.callback_group
        )

        # Service clients
        self.send_gcode_client = self.create_client(
            SendGcode,
            '/cnc/send_gcode',
            callback_group=self.callback_group
        )

        self.home_client = self.create_client(
            Home,
            '/cnc/home',
            callback_group=self.callback_group
        )

        # Action server
        self._action_server = ActionServer(
            self,
            ExecuteGcode,
            'execute_gcode',
            execute_callback=self._execute_callback,
            goal_callback=self._goal_callback,
            cancel_callback=self._cancel_callback,
            callback_group=self.callback_group
        )

        self.get_logger().info('=' * 60)
        self.get_logger().info('G-code Execution Action Server Started')
        self.get_logger().info('=' * 60)
        self.get_logger().info(f'Machine ID: {self.machine_id}')
        self.get_logger().info(f'Recording enabled: {self.enable_recording}')
        self.get_logger().info('Action: /execute_gcode')
        self.get_logger().info('=' * 60)

    def _status_callback(self, msg: MachineStatus):
        """Update current machine state from status topic."""
        self.current_position = {
            'x': msg.mpos_x,
            'y': msg.mpos_y,
            'z': msg.mpos_z
        }
        self.current_state = msg.state_text
        self.current_feed_rate = msg.feed_rate
        self.current_spindle_speed = msg.spindle_speed

    def _goal_callback(self, goal_request):
        """Accept or reject a new goal request."""
        if self._is_executing:
            self.get_logger().warn('Rejecting goal - execution already in progress')
            return GoalResponse.REJECT

        self.get_logger().info(f'Accepting goal for machine: {goal_request.machine_id}')
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle):
        """Accept or reject a cancel request."""
        self.get_logger().warn('Received cancel request')
        return CancelResponse.ACCEPT

    async def _execute_callback(self, goal_handle):
        """Execute the G-code program with progress feedback."""
        self.get_logger().info('Starting G-code execution...')
        self._is_executing = True
        self._goal_handle = goal_handle

        request = goal_handle.request
        result = ExecuteGcode.Result()
        feedback = ExecuteGcode.Feedback()

        # Get G-code content
        gcode_lines = self._get_gcode_lines(request)
        if not gcode_lines:
            result.success = False
            result.message = 'No G-code content provided'
            result.errors = ['Empty G-code program or file not found']
            self._is_executing = False
            goal_handle.abort()
            return result

        total_lines = len(gcode_lines)
        executed_lines = 0
        errors: List[str] = []
        start_time = time.time()

        self.get_logger().info(f'Executing {total_lines} lines of G-code')
        self.get_logger().info(f'Dry run: {request.dry_run}')
        self.get_logger().info(f'Feed override: {request.feed_override * 100:.0f}%')

        # Execute line by line
        for i, line in enumerate(gcode_lines):
            # Check for cancellation
            if goal_handle.is_cancel_requested:
                self.get_logger().warn('Goal cancelled by client')
                result.success = False
                result.message = 'Execution cancelled'
                result.lines_executed = executed_lines
                result.lines_total = total_lines
                result.execution_time = time.time() - start_time
                result.errors = errors
                result.final_state = self.current_state
                self._is_executing = False
                goal_handle.canceled()
                return result

            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith('(') or stripped.startswith(';'):
                continue

            # Publish feedback
            elapsed = time.time() - start_time
            progress = ((i + 1) / total_lines) * 100.0

            # Estimate remaining time
            if i > 0:
                avg_time_per_line = elapsed / (i + 1)
                remaining = avg_time_per_line * (total_lines - i - 1)
            else:
                remaining = 0.0

            feedback.current_line = i + 1
            feedback.total_lines = total_lines
            feedback.progress_percent = progress
            feedback.current_gcode = stripped
            feedback.elapsed_time = elapsed
            feedback.estimated_remaining = remaining
            feedback.x = self.current_position['x']
            feedback.y = self.current_position['y']
            feedback.z = self.current_position['z']
            feedback.machine_state = self.current_state
            feedback.feed_rate = self.current_feed_rate
            feedback.spindle_speed = self.current_spindle_speed

            goal_handle.publish_feedback(feedback)

            # Execute line (or simulate in dry run mode)
            if request.dry_run:
                # Parse-only mode - just validate syntax
                if not self._validate_gcode_line(stripped):
                    errors.append(f'Line {i + 1}: Invalid syntax: {stripped}')
                await self._simulate_delay(0.01)  # Brief delay for feedback
            else:
                # Actually send to machine
                success, error_msg = await self._send_gcode_line(
                    stripped,
                    request.machine_id,
                    request.feed_override
                )
                if not success:
                    errors.append(f'Line {i + 1}: {error_msg}')
                    self.get_logger().error(f'Error at line {i + 1}: {error_msg}')
                    # Continue execution unless it's a critical error
                    if 'ALARM' in error_msg.upper():
                        break

            executed_lines += 1

            # Brief yield to allow other callbacks
            await self._simulate_delay(0.001)

        # Build result
        execution_time = time.time() - start_time
        result.success = len(errors) == 0
        result.lines_executed = executed_lines
        result.lines_total = total_lines
        result.execution_time = execution_time
        result.errors = errors
        result.final_state = self.current_state

        if result.success:
            result.message = f'Successfully executed {executed_lines} lines in {execution_time:.2f}s'
            self.get_logger().info(result.message)
        else:
            result.message = f'Completed with {len(errors)} errors'
            self.get_logger().warn(result.message)

        self._is_executing = False
        goal_handle.succeed()
        return result

    def _get_gcode_lines(self, request) -> List[str]:
        """Extract G-code lines from request (inline or file)."""
        # Prefer inline G-code
        if request.gcode_program:
            return request.gcode_program.strip().split('\n')

        # Try to load from file
        if request.file_path:
            file_path = Path(request.file_path)
            if file_path.exists():
                try:
                    return file_path.read_text().strip().split('\n')
                except Exception as e:
                    self.get_logger().error(f'Error reading file: {e}')

        return []

    def _validate_gcode_line(self, line: str) -> bool:
        """Basic G-code syntax validation."""
        # Skip comments
        if line.startswith('(') or line.startswith(';'):
            return True

        # Valid G-code typically starts with a letter
        valid_prefixes = (
            'G', 'M', 'T', 'S', 'F', 'N', 'X', 'Y', 'Z',
            'A', 'B', 'C', 'I', 'J', 'K', 'P', 'Q', 'R', 'L'
        )
        upper_line = line.upper().strip()

        if not upper_line:
            return True

        # Check if starts with valid prefix
        if upper_line[0] in valid_prefixes:
            return True

        # Allow % (program delimiters)
        if upper_line == '%':
            return True

        # Allow O-words (program numbers)
        if upper_line.startswith('O'):
            return True

        return False

    async def _send_gcode_line(
        self,
        line: str,
        machine_id: str,
        feed_override: float
    ) -> tuple[bool, str]:
        """Send a single G-code line to the machine."""
        # Apply feed override to F commands
        modified_line = self._apply_feed_override(line, feed_override)

        # Wait for service to be available
        if not self.send_gcode_client.wait_for_service(timeout_sec=1.0):
            return False, 'SendGcode service not available'

        request = SendGcode.Request()
        request.machine_id = machine_id
        request.gcode = modified_line
        request.wait_complete = True
        request.timeout = 30.0

        try:
            future = self.send_gcode_client.call_async(request)
            # Wait with timeout
            start = time.time()
            while not future.done():
                if time.time() - start > 30.0:
                    return False, 'Service call timeout'
                await self._simulate_delay(0.01)

            response = future.result()
            if response.success:
                return True, ''
            else:
                return False, response.message
        except Exception as e:
            return False, str(e)

    def _apply_feed_override(self, line: str, override: float) -> str:
        """Apply feed rate override to F commands."""
        if override == 1.0 or 'F' not in line.upper():
            return line

        # Simple regex-free approach
        import re
        pattern = r'F(\d+\.?\d*)'

        def replace_feed(match):
            original = float(match.group(1))
            overridden = original * override
            return f'F{overridden:.1f}'

        return re.sub(pattern, replace_feed, line, flags=re.IGNORECASE)

    async def _simulate_delay(self, seconds: float):
        """Async sleep helper."""
        await rclpy.task.sleep_for_duration(
            rclpy.duration.Duration(seconds=seconds)
        )


def main(args=None):
    rclpy.init(args=args)

    node = GcodeActionServer()

    # Use multi-threaded executor for concurrent callbacks
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down G-code action server...')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
