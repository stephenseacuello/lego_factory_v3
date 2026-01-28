#!/usr/bin/env python3
"""
LEGO MCP Fleet Manager

Manages multiple Alvik AGVs in the factory cell.
Coordinates task assignment, traffic management, and fleet status monitoring.

Features:
- Dynamic AGV registration and discovery
- Task assignment and load balancing
- Traffic management and collision avoidance
- Fleet health monitoring
- Charging station management
- Integration with orchestrator for manufacturing tasks

LEGO MCP Manufacturing System v7.0
"""

import json
import time
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger
from geometry_msgs.msg import PoseStamped, Point


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class TaskType(Enum):
    """Types of AGV tasks."""
    PICKUP = "pickup"           # Pick up material/part
    DELIVERY = "delivery"       # Deliver to destination
    TRANSFER = "transfer"       # Pick up and deliver
    CHARGE = "charge"           # Go to charging station
    HOME = "home"               # Return to home position
    PATROL = "patrol"           # Patrol waypoints


@dataclass
class AGVInfo:
    """Information about a registered AGV."""
    agv_id: str
    state: str = "unknown"
    task_state: str = "none"
    position_x: float = 0.0
    position_y: float = 0.0
    orientation_yaw: float = 0.0
    battery_percentage: float = 100.0
    is_charging: bool = False
    current_task_id: Optional[str] = None
    payload: Optional[str] = None
    last_seen: float = 0.0
    capabilities: Set[str] = field(default_factory=set)

    @property
    def is_available(self) -> bool:
        """Check if AGV is available for new tasks."""
        return (
            self.state in ["idle", "moving"] and
            self.task_state in ["none", "completed"] and
            self.battery_percentage > 20 and
            not self.is_charging and
            self.current_task_id is None
        )

    @property
    def is_online(self) -> bool:
        """Check if AGV is online (seen recently)."""
        return time.time() - self.last_seen < 10.0


@dataclass
class TransportTask:
    """A transport task for an AGV."""
    task_id: str
    task_type: TaskType
    priority: TaskPriority = TaskPriority.NORMAL
    source_waypoint: Optional[str] = None
    destination_waypoint: str = ""
    payload_id: Optional[str] = None
    payload_type: Optional[str] = None
    assigned_agv: Optional[str] = None
    status: str = "pending"  # pending, assigned, in_progress, completed, failed
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'task_id': self.task_id,
            'task_type': self.task_type.value,
            'priority': self.priority.value,
            'source_waypoint': self.source_waypoint,
            'destination_waypoint': self.destination_waypoint,
            'payload_id': self.payload_id,
            'payload_type': self.payload_type,
            'assigned_agv': self.assigned_agv,
            'status': self.status,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'error_message': self.error_message,
        }


@dataclass
class Waypoint:
    """A waypoint in the factory floor."""
    waypoint_id: str
    name: str
    x: float
    y: float
    yaw: float = 0.0
    waypoint_type: str = "general"  # general, station, charging, storage
    capacity: int = 1
    current_occupancy: int = 0


class FleetManagerNode(Node):
    """
    Fleet manager for coordinating multiple Alvik AGVs.

    Topics Published:
    - /fleet/status: Fleet-wide status summary
    - /fleet/task_updates: Task status updates
    - /<agv_id>/task_command: Commands for specific AGVs

    Topics Subscribed:
    - /<agv_id>/status: Status from each AGV

    Services:
    - /fleet/submit_task: Submit a new transport task
    - /fleet/cancel_task: Cancel a pending/active task
    - /fleet/register_agv: Register a new AGV
    - /fleet/get_status: Get fleet status
    """

    def __init__(self):
        super().__init__('fleet_manager')

        # Parameters
        self.declare_parameter('max_agvs', 10)
        self.declare_parameter('task_timeout_seconds', 300.0)
        self.declare_parameter('low_battery_threshold', 20.0)
        self.declare_parameter('critical_battery_threshold', 10.0)
        self.declare_parameter('auto_charge_threshold', 30.0)

        self.max_agvs = self.get_parameter('max_agvs').value
        self.task_timeout = self.get_parameter('task_timeout_seconds').value
        self.low_battery = self.get_parameter('low_battery_threshold').value
        self.critical_battery = self.get_parameter('critical_battery_threshold').value
        self.auto_charge = self.get_parameter('auto_charge_threshold').value

        # Fleet state
        self.agvs: Dict[str, AGVInfo] = {}
        self.tasks: Dict[str, TransportTask] = {}
        self.task_queue: List[str] = []  # Task IDs in priority order
        self.task_counter = 0
        self.waypoints: Dict[str, Waypoint] = {}

        # Callback group
        self.cb_group = ReentrantCallbackGroup()

        # AGV status subscribers (dynamically created)
        self.agv_subscribers: Dict[str, any] = {}
        self.agv_task_publishers: Dict[str, any] = {}

        # Publishers
        self.fleet_status_pub = self.create_publisher(
            String, '/fleet/status', 10
        )
        self.task_update_pub = self.create_publisher(
            String, '/fleet/task_updates', 10
        )

        # Services
        self.create_service(
            Trigger, '/fleet/submit_task',
            self._srv_submit_task, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, '/fleet/cancel_task',
            self._srv_cancel_task, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, '/fleet/register_agv',
            self._srv_register_agv, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, '/fleet/get_status',
            self._srv_get_status, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, '/fleet/emergency_stop_all',
            self._srv_emergency_stop_all, callback_group=self.cb_group
        )

        # Subscribe to task requests from orchestrator
        self.create_subscription(
            String, '/lego_mcp/transport_request',
            self._on_transport_request, 10,
            callback_group=self.cb_group
        )

        # Timers
        self.status_timer = self.create_timer(
            1.0, self._publish_fleet_status, callback_group=self.cb_group
        )
        self.allocation_timer = self.create_timer(
            0.5, self._process_task_queue, callback_group=self.cb_group
        )
        self.health_timer = self.create_timer(
            5.0, self._check_fleet_health, callback_group=self.cb_group
        )

        # Initialize default waypoints
        self._initialize_default_waypoints()

        self.get_logger().info('Fleet Manager initialized')

    def _initialize_default_waypoints(self):
        """Initialize default factory waypoints."""
        default_waypoints = [
            Waypoint('home', 'Home Position', 0.0, 0.0, 0.0, 'general'),
            Waypoint('charging_1', 'Charging Station 1', -0.5, 0.0, 3.14, 'charging'),
            Waypoint('charging_2', 'Charging Station 2', -0.5, 0.3, 3.14, 'charging'),
            Waypoint('printer_pickup', 'Printer Pickup', 0.8, 0.0, 0.0, 'station'),
            Waypoint('cnc_pickup', 'CNC Pickup', 0.2, 0.6, 1.57, 'station'),
            Waypoint('laser_pickup', 'Laser Pickup', 0.5, 0.6, 1.57, 'station'),
            Waypoint('assembly_ned2', 'Ned2 Assembly Station', 0.3, 0.2, 0.0, 'station'),
            Waypoint('assembly_xarm', 'xArm Assembly Station', 0.3, -0.2, 0.0, 'station'),
            Waypoint('quality_inspection', 'Quality Inspection', 0.6, 0.3, 0.78, 'station'),
            Waypoint('storage_in', 'Storage Input', -0.3, 0.4, 1.57, 'storage'),
            Waypoint('storage_out', 'Storage Output', -0.3, -0.4, -1.57, 'storage'),
        ]

        for wp in default_waypoints:
            self.waypoints[wp.waypoint_id] = wp

    def register_agv(self, agv_id: str, capabilities: Set[str] = None) -> bool:
        """Register a new AGV with the fleet."""
        if len(self.agvs) >= self.max_agvs:
            self.get_logger().error(f'Cannot register {agv_id}: fleet at capacity')
            return False

        if agv_id in self.agvs:
            self.get_logger().warn(f'AGV {agv_id} already registered')
            return True

        # Create AGV info
        self.agvs[agv_id] = AGVInfo(
            agv_id=agv_id,
            capabilities=capabilities or {'transport', 'patrol'},
        )

        # Create subscriber for AGV status
        self.agv_subscribers[agv_id] = self.create_subscription(
            String, f'/{agv_id}/status',
            lambda msg, aid=agv_id: self._on_agv_status(aid, msg),
            10, callback_group=self.cb_group
        )

        # Create publisher for AGV commands
        self.agv_task_publishers[agv_id] = self.create_publisher(
            String, f'/{agv_id}/task_command', 10
        )

        self.get_logger().info(f'Registered AGV: {agv_id}')
        return True

    def unregister_agv(self, agv_id: str) -> bool:
        """Unregister an AGV from the fleet."""
        if agv_id not in self.agvs:
            return False

        # Cancel any active tasks
        agv = self.agvs[agv_id]
        if agv.current_task_id:
            self._fail_task(agv.current_task_id, "AGV unregistered")

        # Remove subscriber and publisher
        if agv_id in self.agv_subscribers:
            self.destroy_subscription(self.agv_subscribers[agv_id])
            del self.agv_subscribers[agv_id]

        if agv_id in self.agv_task_publishers:
            self.destroy_publisher(self.agv_task_publishers[agv_id])
            del self.agv_task_publishers[agv_id]

        del self.agvs[agv_id]
        self.get_logger().info(f'Unregistered AGV: {agv_id}')
        return True

    def submit_task(self, task_type: TaskType, destination: str,
                    source: str = None, payload_id: str = None,
                    payload_type: str = None,
                    priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Submit a new transport task."""
        self.task_counter += 1
        task_id = f'task_{self.task_counter:04d}'

        task = TransportTask(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            source_waypoint=source,
            destination_waypoint=destination,
            payload_id=payload_id,
            payload_type=payload_type,
        )

        self.tasks[task_id] = task

        # Insert into queue based on priority
        self._insert_task_in_queue(task_id)

        self.get_logger().info(
            f'Task submitted: {task_id} ({task_type.value}) to {destination}'
        )

        # Publish task update
        self._publish_task_update(task)

        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]

        if task.status in ['completed', 'failed']:
            return False

        # If assigned, notify AGV
        if task.assigned_agv and task.assigned_agv in self.agvs:
            self._send_task_cancel(task.assigned_agv, task_id)
            self.agvs[task.assigned_agv].current_task_id = None

        task.status = 'failed'
        task.error_message = 'Cancelled by user'

        # Remove from queue
        if task_id in self.task_queue:
            self.task_queue.remove(task_id)

        self._publish_task_update(task)
        return True

    def _insert_task_in_queue(self, task_id: str):
        """Insert task into queue based on priority."""
        task = self.tasks[task_id]

        # Find insertion point
        insert_idx = 0
        for i, queued_id in enumerate(self.task_queue):
            queued_task = self.tasks[queued_id]
            if task.priority.value > queued_task.priority.value:
                insert_idx = i
                break
            insert_idx = i + 1

        self.task_queue.insert(insert_idx, task_id)

    def _on_agv_status(self, agv_id: str, msg: String):
        """Handle status update from an AGV."""
        try:
            data = json.loads(msg.data)

            if agv_id not in self.agvs:
                # Auto-register discovered AGV
                self.register_agv(agv_id)

            agv = self.agvs[agv_id]
            agv.state = data.get('state', 'unknown')
            agv.task_state = data.get('task_state', 'none')
            agv.last_seen = time.time()

            # Update position
            pos = data.get('position', {})
            agv.position_x = pos.get('x', 0.0)
            agv.position_y = pos.get('y', 0.0)
            agv.orientation_yaw = pos.get('yaw', 0.0)

            # Update battery
            battery = data.get('battery', {})
            agv.battery_percentage = battery.get('percentage', 100.0)
            agv.is_charging = battery.get('is_charging', False)

            # Update task info
            task_info = data.get('task', {})
            agv.current_task_id = task_info.get('task_id')
            agv.payload = task_info.get('payload')

            # Check for task completion
            if agv.task_state == 'completed' and agv.current_task_id:
                self._complete_task(agv.current_task_id)

        except json.JSONDecodeError:
            pass

    def _on_transport_request(self, msg: String):
        """Handle transport requests from orchestrator."""
        try:
            data = json.loads(msg.data)

            task_type = TaskType(data.get('type', 'transfer'))
            priority = TaskPriority(data.get('priority', 2))

            self.submit_task(
                task_type=task_type,
                destination=data.get('destination'),
                source=data.get('source'),
                payload_id=data.get('payload_id'),
                payload_type=data.get('payload_type'),
                priority=priority,
            )

        except (json.JSONDecodeError, ValueError) as e:
            self.get_logger().error(f'Invalid transport request: {e}')

    def _process_task_queue(self):
        """Process pending tasks and assign to available AGVs."""
        if not self.task_queue:
            return

        # Get available AGVs
        available_agvs = [
            agv for agv in self.agvs.values()
            if agv.is_available and agv.is_online
        ]

        if not available_agvs:
            return

        # Process tasks in priority order
        tasks_to_remove = []

        for task_id in self.task_queue[:]:
            if not available_agvs:
                break

            task = self.tasks[task_id]
            if task.status != 'pending':
                tasks_to_remove.append(task_id)
                continue

            # Find best AGV for this task
            best_agv = self._select_best_agv(task, available_agvs)
            if best_agv:
                self._assign_task(task, best_agv)
                available_agvs.remove(best_agv)
                tasks_to_remove.append(task_id)

        # Remove assigned tasks from queue
        for task_id in tasks_to_remove:
            if task_id in self.task_queue:
                self.task_queue.remove(task_id)

    def _select_best_agv(self, task: TransportTask,
                         available_agvs: List[AGVInfo]) -> Optional[AGVInfo]:
        """Select the best AGV for a task based on distance and battery."""
        if not available_agvs:
            return None

        # Get destination waypoint
        dest_wp = self.waypoints.get(task.destination_waypoint)
        if not dest_wp:
            return available_agvs[0]  # Default to first available

        # Score each AGV
        scored_agvs = []
        for agv in available_agvs:
            # Distance to destination (or source if pickup required)
            if task.source_waypoint:
                src_wp = self.waypoints.get(task.source_waypoint)
                if src_wp:
                    dist = self._calculate_distance(
                        agv.position_x, agv.position_y,
                        src_wp.x, src_wp.y
                    )
                else:
                    dist = 0
            else:
                dist = self._calculate_distance(
                    agv.position_x, agv.position_y,
                    dest_wp.x, dest_wp.y
                )

            # Score: lower distance + higher battery = better
            score = dist - (agv.battery_percentage / 100.0)
            scored_agvs.append((agv, score))

        # Sort by score (lower is better)
        scored_agvs.sort(key=lambda x: x[1])
        return scored_agvs[0][0] if scored_agvs else None

    def _calculate_distance(self, x1: float, y1: float,
                            x2: float, y2: float) -> float:
        """Calculate Euclidean distance."""
        return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

    def _assign_task(self, task: TransportTask, agv: AGVInfo):
        """Assign a task to an AGV."""
        task.assigned_agv = agv.agv_id
        task.status = 'assigned'
        task.started_at = time.time()
        agv.current_task_id = task.task_id

        # Send task command to AGV
        self._send_task_command(agv.agv_id, task)

        self.get_logger().info(f'Assigned {task.task_id} to {agv.agv_id}')
        self._publish_task_update(task)

    def _send_task_command(self, agv_id: str, task: TransportTask):
        """Send task command to an AGV."""
        if agv_id not in self.agv_task_publishers:
            return

        command = {
            'command': 'execute_task',
            'task_id': task.task_id,
            'task_type': task.task_type.value,
            'source_waypoint': task.source_waypoint,
            'destination_waypoint': task.destination_waypoint,
            'payload_id': task.payload_id,
            'payload_type': task.payload_type,
        }

        # Add waypoint coordinates
        if task.source_waypoint and task.source_waypoint in self.waypoints:
            wp = self.waypoints[task.source_waypoint]
            command['source_pose'] = {'x': wp.x, 'y': wp.y, 'yaw': wp.yaw}

        if task.destination_waypoint in self.waypoints:
            wp = self.waypoints[task.destination_waypoint]
            command['destination_pose'] = {'x': wp.x, 'y': wp.y, 'yaw': wp.yaw}

        msg = String()
        msg.data = json.dumps(command)
        self.agv_task_publishers[agv_id].publish(msg)

    def _send_task_cancel(self, agv_id: str, task_id: str):
        """Send task cancellation to an AGV."""
        if agv_id not in self.agv_task_publishers:
            return

        command = {
            'command': 'cancel_task',
            'task_id': task_id,
        }

        msg = String()
        msg.data = json.dumps(command)
        self.agv_task_publishers[agv_id].publish(msg)

    def _complete_task(self, task_id: str):
        """Mark a task as completed."""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]
        task.status = 'completed'
        task.completed_at = time.time()

        # Clear AGV task
        if task.assigned_agv and task.assigned_agv in self.agvs:
            self.agvs[task.assigned_agv].current_task_id = None

        self.get_logger().info(f'Task completed: {task_id}')
        self._publish_task_update(task)

    def _fail_task(self, task_id: str, error: str):
        """Mark a task as failed."""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]
        task.status = 'failed'
        task.error_message = error
        task.completed_at = time.time()

        # Clear AGV task
        if task.assigned_agv and task.assigned_agv in self.agvs:
            self.agvs[task.assigned_agv].current_task_id = None

        self.get_logger().error(f'Task failed: {task_id} - {error}')
        self._publish_task_update(task)

    def _check_fleet_health(self):
        """Check fleet health and handle issues."""
        now = time.time()

        for agv in self.agvs.values():
            # Check for offline AGVs
            if not agv.is_online and agv.state != 'disconnected':
                self.get_logger().warn(f'{agv.agv_id}: Lost connection')
                if agv.current_task_id:
                    self._fail_task(agv.current_task_id, 'AGV disconnected')

            # Check for low battery
            if agv.battery_percentage < self.critical_battery and not agv.is_charging:
                self.get_logger().error(f'{agv.agv_id}: Critical battery!')
                # Auto-send to charging
                if not agv.current_task_id:
                    self.submit_task(
                        TaskType.CHARGE, 'charging_1',
                        priority=TaskPriority.URGENT
                    )

            elif agv.battery_percentage < self.auto_charge and not agv.is_charging:
                if not agv.current_task_id and agv.is_available:
                    self.submit_task(
                        TaskType.CHARGE, 'charging_1',
                        priority=TaskPriority.LOW
                    )

            # Check for task timeouts
            if agv.current_task_id:
                task = self.tasks.get(agv.current_task_id)
                if task and task.started_at:
                    if now - task.started_at > self.task_timeout:
                        self._fail_task(task.task_id, 'Task timeout')

    def _publish_fleet_status(self):
        """Publish fleet-wide status."""
        online_count = sum(1 for agv in self.agvs.values() if agv.is_online)
        available_count = sum(1 for agv in self.agvs.values() if agv.is_available)
        charging_count = sum(1 for agv in self.agvs.values() if agv.is_charging)

        pending_tasks = sum(1 for t in self.tasks.values() if t.status == 'pending')
        active_tasks = sum(1 for t in self.tasks.values() if t.status in ['assigned', 'in_progress'])

        status = {
            'timestamp': time.time(),
            'timestamp_iso': datetime.now().isoformat(),
            'fleet_size': len(self.agvs),
            'online': online_count,
            'available': available_count,
            'charging': charging_count,
            'tasks': {
                'pending': pending_tasks,
                'active': active_tasks,
                'queue_length': len(self.task_queue),
            },
            'agvs': {
                agv_id: {
                    'state': agv.state,
                    'battery': agv.battery_percentage,
                    'position': {'x': agv.position_x, 'y': agv.position_y},
                    'current_task': agv.current_task_id,
                    'online': agv.is_online,
                }
                for agv_id, agv in self.agvs.items()
            },
        }

        msg = String()
        msg.data = json.dumps(status)
        self.fleet_status_pub.publish(msg)

    def _publish_task_update(self, task: TransportTask):
        """Publish task status update."""
        msg = String()
        msg.data = json.dumps(task.to_dict())
        self.task_update_pub.publish(msg)

    # === Services ===

    def _srv_submit_task(self, request, response):
        """Service to submit a task (expects JSON in trigger message)."""
        # Note: This is a simplified interface. In production,
        # use a custom service type with proper fields.
        response.success = True
        response.message = "Use /lego_mcp/transport_request topic for task submission"
        return response

    def _srv_cancel_task(self, request, response):
        """Service to cancel a task."""
        response.success = True
        response.message = "Use cancel_task method with task_id"
        return response

    def _srv_register_agv(self, request, response):
        """Service to register an AGV."""
        response.success = True
        response.message = "AGVs are auto-registered when they publish status"
        return response

    def _srv_get_status(self, request, response):
        """Service to get fleet status."""
        response.success = True
        response.message = json.dumps({
            'fleet_size': len(self.agvs),
            'queue_length': len(self.task_queue),
            'agv_ids': list(self.agvs.keys()),
        })
        return response

    def _srv_emergency_stop_all(self, request, response):
        """Emergency stop all AGVs."""
        self.get_logger().error('EMERGENCY STOP ALL AGVs')

        for agv_id in self.agv_task_publishers:
            command = {'command': 'emergency_stop'}
            msg = String()
            msg.data = json.dumps(command)
            self.agv_task_publishers[agv_id].publish(msg)

        response.success = True
        response.message = "Emergency stop sent to all AGVs"
        return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    node = FleetManagerNode()

    executor = MultiThreadedExecutor()
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
