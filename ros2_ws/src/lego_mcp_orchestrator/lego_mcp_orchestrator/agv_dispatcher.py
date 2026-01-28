#!/usr/bin/env python3
"""
AGV Dispatcher - AGV Navigation and Fleet Dispatch

Provides AGV fleet management capabilities including:
- Mission dispatch and tracking
- Navigation action server
- Fleet coordination
- Traffic management

LEGO MCP Manufacturing System v7.0
VDA 5050 Inspired Fleet Management
"""

import json
import math
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, ActionClient, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from std_msgs.msg import String
from std_srvs.srv import Trigger
from geometry_msgs.msg import PoseStamped, Pose, Point, Quaternion, Twist

try:
    from lego_mcp_msgs.action import AGVNavigation
    from lego_mcp_msgs.msg import AGVStatus, AGVMission
    from lego_mcp_msgs.srv import DispatchAGV
    MSGS_AVAILABLE = True
except ImportError:
    MSGS_AVAILABLE = False
    print("Warning: lego_mcp_msgs not available, running in stub mode")


class AGVState(Enum):
    """AGV operational state."""
    IDLE = 0
    NAVIGATING = 1
    DOCKING = 2
    CHARGING = 3
    LOADING = 4
    UNLOADING = 5
    ERROR = 6
    EMERGENCY_STOP = 7


class MissionState(Enum):
    """Mission execution state."""
    PENDING = 0
    ASSIGNED = 1
    IN_PROGRESS = 2
    COMPLETED = 3
    FAILED = 4
    CANCELLED = 5


@dataclass
class Station:
    """Factory station definition."""
    station_id: str
    name: str
    pose: Tuple[float, float, float]  # x, y, theta
    station_type: str  # 'equipment', 'storage', 'charging', 'pickup', 'dropoff'
    docking_pose: Optional[Tuple[float, float, float]] = None


@dataclass
class AGVTracker:
    """Track individual AGV state."""
    agv_id: str
    name: str
    state: AGVState = AGVState.IDLE
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # x, y, theta
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # vx, vy, omega
    battery_percent: float = 100.0
    current_mission_id: Optional[str] = None
    current_station: Optional[str] = None
    is_available: bool = True
    last_seen: float = 0.0
    total_distance_m: float = 0.0


@dataclass
class NavigationSession:
    """Track navigation session."""
    session_id: str
    agv_id: str
    goal_pose: Tuple[float, float, float]
    station_id: Optional[str] = None

    # Path
    waypoints: List[Tuple[float, float, float]] = field(default_factory=list)
    current_waypoint: int = 0

    # Progress
    distance_traveled: float = 0.0
    distance_remaining: float = 0.0
    start_time: float = 0.0
    end_time: float = 0.0

    # State
    is_cancelled: bool = False
    is_recovering: bool = False
    recovery_reason: str = ""
    replan_count: int = 0
    recovery_count: int = 0


class AGVDispatcherNode(Node):
    """
    ROS2 node for AGV fleet dispatch and navigation.

    Features:
    - AGV navigation action server
    - Fleet dispatch service
    - Traffic coordination
    - Station management
    - Battery management
    """

    def __init__(self):
        super().__init__('agv_dispatcher')

        # Parameters
        self.declare_parameter('feedback_rate_hz', 10.0)
        self.declare_parameter('max_velocity_ms', 0.5)
        self.declare_parameter('position_tolerance_m', 0.05)
        self.declare_parameter('orientation_tolerance_rad', 0.1)
        self.declare_parameter('battery_low_threshold', 20.0)
        self.declare_parameter('enable_traffic_management', True)

        self._feedback_rate = self.get_parameter('feedback_rate_hz').value
        self._max_velocity = self.get_parameter('max_velocity_ms').value
        self._pos_tolerance = self.get_parameter('position_tolerance_m').value
        self._orient_tolerance = self.get_parameter('orientation_tolerance_rad').value
        self._battery_low = self.get_parameter('battery_low_threshold').value
        self._traffic_enabled = self.get_parameter('enable_traffic_management').value

        # AGV fleet tracking
        self._agvs: Dict[str, AGVTracker] = {}
        self._navigation_sessions: Dict[str, NavigationSession] = {}
        self._lock = threading.RLock()

        # Station definitions
        self._stations: Dict[str, Station] = {}
        self._load_stations()

        # Mission queue
        self._pending_missions: List[Dict] = []
        self._active_missions: Dict[str, Dict] = {}

        # Register known AGVs
        self._register_fleet()

        # Callback groups
        self._action_group = ReentrantCallbackGroup()
        self._service_group = MutuallyExclusiveCallbackGroup()

        # QoS
        reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            depth=10
        )

        # Action server
        if MSGS_AVAILABLE:
            self._nav_action_server = ActionServer(
                self,
                AGVNavigation,
                '/lego_mcp/agv/navigate',
                execute_callback=self._execute_navigation,
                goal_callback=self._goal_callback,
                cancel_callback=self._cancel_callback,
                callback_group=self._action_group
            )

        # Services
        if MSGS_AVAILABLE:
            self._dispatch_srv = self.create_service(
                DispatchAGV,
                '/lego_mcp/agv/dispatch',
                self._dispatch_agv_callback,
                callback_group=self._service_group
            )

        self._fleet_status_srv = self.create_service(
            Trigger,
            '/lego_mcp/agv/fleet_status',
            self._get_fleet_status,
            callback_group=self._service_group
        )

        self._stations_srv = self.create_service(
            Trigger,
            '/lego_mcp/agv/get_stations',
            self._get_stations,
            callback_group=self._service_group
        )

        # Publishers
        self._fleet_pub = self.create_publisher(
            String,
            '/lego_mcp/agv/fleet',
            reliable_qos
        )

        self._event_pub = self.create_publisher(
            String,
            '/lego_mcp/agv/events',
            10
        )

        # Command publisher for each AGV
        self._cmd_pubs: Dict[str, any] = {}
        for agv_id in self._agvs:
            self._cmd_pubs[agv_id] = self.create_publisher(
                Twist,
                f'/lego_mcp/agv/{agv_id}/cmd_vel',
                10
            )

        # Subscribers
        if MSGS_AVAILABLE:
            for agv_id in self._agvs:
                self.create_subscription(
                    AGVStatus,
                    f'/lego_mcp/agv/{agv_id}/status',
                    lambda msg, aid=agv_id: self._on_agv_status(aid, msg),
                    10
                )

        # Timers
        self._fleet_pub_timer = self.create_timer(
            1.0,
            self._publish_fleet_status
        )

        self._mission_timer = self.create_timer(
            0.5,
            self._process_mission_queue
        )

        self.get_logger().info(
            f'AGV Dispatcher started - {len(self._agvs)} AGVs registered'
        )

    def _load_stations(self):
        """Load factory station definitions."""
        # LEGO factory floor stations
        self._stations = {
            'storage_in': Station(
                station_id='storage_in',
                name='Raw Material Storage',
                pose=(0.0, 0.0, 0.0),
                station_type='storage',
                docking_pose=(0.0, -0.5, 0.0),
            ),
            'formlabs_sla': Station(
                station_id='formlabs_sla',
                name='Formlabs SLA Printer',
                pose=(2.0, 0.0, 0.0),
                station_type='equipment',
                docking_pose=(2.0, -0.5, 0.0),
            ),
            'bambu_fdm': Station(
                station_id='bambu_fdm',
                name='Bambu Lab FDM Printer',
                pose=(4.0, 0.0, 0.0),
                station_type='equipment',
                docking_pose=(4.0, -0.5, 0.0),
            ),
            'grbl_cnc': Station(
                station_id='grbl_cnc',
                name='GRBL CNC/Laser',
                pose=(6.0, 0.0, 0.0),
                station_type='equipment',
                docking_pose=(6.0, -0.5, 0.0),
            ),
            'vision_station': Station(
                station_id='vision_station',
                name='Vision Inspection Station',
                pose=(4.0, 2.0, math.pi/2),
                station_type='equipment',
                docking_pose=(4.0, 1.5, math.pi/2),
            ),
            'ned2_robot': Station(
                station_id='ned2_robot',
                name='Niryo Ned2 Assembly',
                pose=(2.0, 2.0, math.pi/2),
                station_type='equipment',
                docking_pose=(2.0, 1.5, math.pi/2),
            ),
            'xarm_robot': Station(
                station_id='xarm_robot',
                name='xArm Assembly',
                pose=(0.0, 2.0, math.pi/2),
                station_type='equipment',
                docking_pose=(0.0, 1.5, math.pi/2),
            ),
            'storage_out': Station(
                station_id='storage_out',
                name='Finished Goods Storage',
                pose=(6.0, 2.0, math.pi),
                station_type='storage',
                docking_pose=(6.5, 2.0, math.pi),
            ),
            'charging_1': Station(
                station_id='charging_1',
                name='Charging Station 1',
                pose=(0.0, -2.0, -math.pi/2),
                station_type='charging',
                docking_pose=(0.0, -1.5, -math.pi/2),
            ),
            'charging_2': Station(
                station_id='charging_2',
                name='Charging Station 2',
                pose=(6.0, -2.0, -math.pi/2),
                station_type='charging',
                docking_pose=(6.0, -1.5, -math.pi/2),
            ),
        }

    def _register_fleet(self):
        """Register known AGVs in fleet."""
        # Arduino Alvik-based AGVs
        self._agvs = {
            'alvik_01': AGVTracker(
                agv_id='alvik_01',
                name='Alvik AGV 01',
                position=(0.0, -2.0, math.pi/2),
                current_station='charging_1',
            ),
            'alvik_02': AGVTracker(
                agv_id='alvik_02',
                name='Alvik AGV 02',
                position=(6.0, -2.0, math.pi/2),
                current_station='charging_2',
            ),
        }

    def _goal_callback(self, goal_request) -> GoalResponse:
        """Accept or reject navigation goal."""
        agv_id = goal_request.agv_id

        self.get_logger().info(f'Received navigation request for AGV: {agv_id}')

        # Check AGV exists and is available
        with self._lock:
            if agv_id not in self._agvs:
                self.get_logger().warning(f'Unknown AGV: {agv_id}')
                return GoalResponse.REJECT

            agv = self._agvs[agv_id]
            if not agv.is_available:
                self.get_logger().warning(f'AGV {agv_id} not available')
                return GoalResponse.REJECT

            if agv.state == AGVState.EMERGENCY_STOP:
                self.get_logger().warning(f'AGV {agv_id} in emergency stop')
                return GoalResponse.REJECT

        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle: ServerGoalHandle) -> CancelResponse:
        """Handle cancellation request."""
        self.get_logger().info('Received cancel request for navigation')
        return CancelResponse.ACCEPT

    async def _execute_navigation(self, goal_handle: ServerGoalHandle):
        """Execute AGV navigation with progress feedback."""
        request = goal_handle.request
        agv_id = request.agv_id
        session_id = f"NAV-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # Determine goal
        if request.station_id:
            # Navigate to station
            station = self._stations.get(request.station_id)
            if not station:
                self.get_logger().error(f'Unknown station: {request.station_id}')
                result = self._create_nav_result()
                result.success = False
                result.message = f"Unknown station: {request.station_id}"
                goal_handle.abort()
                return result

            goal_pose = station.docking_pose or station.pose
            station_id = request.station_id
        else:
            # Navigate to pose
            goal_pose = (
                request.goal_pose.pose.position.x,
                request.goal_pose.pose.position.y,
                self._quaternion_to_yaw(request.goal_pose.pose.orientation),
            )
            station_id = None

        # Get current AGV position
        with self._lock:
            agv = self._agvs[agv_id]
            start_pose = agv.position

        # Plan path
        waypoints = self._plan_path(start_pose, goal_pose)

        # Create navigation session
        session = NavigationSession(
            session_id=session_id,
            agv_id=agv_id,
            goal_pose=goal_pose,
            station_id=station_id,
            waypoints=waypoints,
            distance_remaining=self._path_length(waypoints),
            start_time=time.time(),
        )

        with self._lock:
            self._navigation_sessions[session_id] = session
            agv.state = AGVState.NAVIGATING
            agv.is_available = False

        self._publish_event('navigation_started', {
            'session_id': session_id,
            'agv_id': agv_id,
            'station_id': station_id,
            'waypoint_count': len(waypoints),
        })

        # Create result and feedback
        if MSGS_AVAILABLE:
            result = AGVNavigation.Result()
            feedback = AGVNavigation.Feedback()
        else:
            result = self._create_nav_result()
            feedback = self._create_nav_feedback()

        try:
            # Execute navigation
            max_velocity = request.max_velocity if request.max_velocity > 0 else self._max_velocity
            pos_tolerance = request.position_tolerance if request.position_tolerance > 0 else self._pos_tolerance
            orient_tolerance = request.orientation_tolerance if request.orientation_tolerance > 0 else self._orient_tolerance

            while session.current_waypoint < len(session.waypoints):
                if session.is_cancelled:
                    break

                target_wp = session.waypoints[session.current_waypoint]

                # Move towards waypoint
                while not self._is_at_pose(agv.position, target_wp, pos_tolerance, orient_tolerance):
                    if session.is_cancelled:
                        break

                    # Compute velocity command
                    cmd = self._compute_velocity_command(
                        agv.position, target_wp, max_velocity
                    )

                    # Publish command
                    self._publish_cmd_vel(agv_id, cmd)

                    # Simulate AGV movement (in real system, position comes from AGV)
                    new_pos = self._simulate_movement(agv.position, cmd, 1.0 / self._feedback_rate)
                    distance = self._distance_2d(agv.position, new_pos)

                    with self._lock:
                        agv.position = new_pos
                        agv.velocity = cmd
                        session.distance_traveled += distance

                    # Update feedback
                    session.distance_remaining = (
                        self._distance_2d(new_pos, target_wp) +
                        self._remaining_path_length(session.waypoints, session.current_waypoint + 1)
                    )

                    self._update_nav_feedback(feedback, session, agv)
                    goal_handle.publish_feedback(feedback)

                    await self._async_sleep(1.0 / self._feedback_rate)

                # Waypoint reached
                session.current_waypoint += 1
                self.get_logger().debug(
                    f'AGV {agv_id} reached waypoint {session.current_waypoint}/{len(session.waypoints)}'
                )

            # Final docking if needed
            if station_id and request.precise_docking:
                session.is_recovering = False
                await self._execute_docking(agv, session)

        except Exception as e:
            self.get_logger().error(f'Navigation error: {e}')
            result.success = False
            result.message = str(e)

        finally:
            session.end_time = time.time()

            # Stop AGV
            self._publish_cmd_vel(agv_id, (0.0, 0.0, 0.0))

            with self._lock:
                del self._navigation_sessions[session_id]
                agv.state = AGVState.IDLE
                agv.is_available = True
                agv.velocity = (0.0, 0.0, 0.0)
                if station_id:
                    agv.current_station = station_id
                agv.total_distance_m += session.distance_traveled

        # Compute final result
        final_pose = agv.position
        position_error = self._distance_2d(final_pose, goal_pose)
        orientation_error = abs(self._normalize_angle(final_pose[2] - goal_pose[2]))

        if session.is_cancelled:
            goal_handle.canceled()
            result.success = False
            result.message = "Navigation cancelled"
        elif position_error <= pos_tolerance and orientation_error <= orient_tolerance:
            goal_handle.succeed()
            result.success = True
            result.message = f"Navigation complete to {station_id or 'goal pose'}"
        else:
            goal_handle.abort()
            result.success = False
            result.message = f"Failed to reach goal: pos_error={position_error:.3f}m"

        # Populate result
        if MSGS_AVAILABLE:
            result.final_pose = PoseStamped()
            result.final_pose.pose.position.x = final_pose[0]
            result.final_pose.pose.position.y = final_pose[1]
            result.final_pose.pose.orientation = self._yaw_to_quaternion(final_pose[2])

        result.position_error = position_error
        result.orientation_error = orientation_error
        result.total_distance_m = session.distance_traveled
        result.total_time_sec = session.end_time - session.start_time
        result.replan_count = session.replan_count
        result.recovery_count = session.recovery_count

        self._publish_event('navigation_completed', {
            'session_id': session_id,
            'agv_id': agv_id,
            'success': result.success,
            'distance_m': session.distance_traveled,
            'duration_sec': result.total_time_sec,
        })

        return result

    def _plan_path(
        self,
        start: Tuple[float, float, float],
        goal: Tuple[float, float, float]
    ) -> List[Tuple[float, float, float]]:
        """Plan path from start to goal."""
        # Simple direct path planning
        # In production, would use proper path planner (A*, RRT, etc.)
        waypoints = []

        # Add intermediate waypoints for longer paths
        distance = self._distance_2d(start, goal)
        step_size = 0.5  # meters

        if distance > step_size:
            steps = int(distance / step_size)
            for i in range(1, steps):
                t = i / steps
                x = start[0] + t * (goal[0] - start[0])
                y = start[1] + t * (goal[1] - start[1])
                theta = start[2] + t * self._normalize_angle(goal[2] - start[2])
                waypoints.append((x, y, theta))

        waypoints.append(goal)
        return waypoints

    def _compute_velocity_command(
        self,
        current: Tuple[float, float, float],
        target: Tuple[float, float, float],
        max_vel: float
    ) -> Tuple[float, float, float]:
        """Compute velocity command to move towards target."""
        dx = target[0] - current[0]
        dy = target[1] - current[1]
        dtheta = self._normalize_angle(target[2] - current[2])

        distance = math.sqrt(dx*dx + dy*dy)

        if distance > 0.01:
            # Transform to robot frame
            cos_theta = math.cos(current[2])
            sin_theta = math.sin(current[2])

            vx_world = dx / distance * min(max_vel, distance)
            vy_world = dy / distance * min(max_vel, distance)

            vx = cos_theta * vx_world + sin_theta * vy_world
            vy = -sin_theta * vx_world + cos_theta * vy_world
        else:
            vx = 0.0
            vy = 0.0

        # Angular velocity
        omega = max(-1.0, min(1.0, dtheta * 2.0))

        return (vx, vy, omega)

    def _simulate_movement(
        self,
        position: Tuple[float, float, float],
        velocity: Tuple[float, float, float],
        dt: float
    ) -> Tuple[float, float, float]:
        """Simulate AGV movement (for testing without real AGV)."""
        x, y, theta = position
        vx, vy, omega = velocity

        # Transform velocity to world frame
        cos_theta = math.cos(theta)
        sin_theta = math.sin(theta)

        dx = (cos_theta * vx - sin_theta * vy) * dt
        dy = (sin_theta * vx + cos_theta * vy) * dt
        dtheta = omega * dt

        return (x + dx, y + dy, self._normalize_angle(theta + dtheta))

    async def _execute_docking(self, agv: AGVTracker, session: NavigationSession):
        """Execute precise docking maneuver."""
        with self._lock:
            agv.state = AGVState.DOCKING

        # Slow approach for docking
        # In production, would use sensors for precise alignment
        await self._async_sleep(1.0)

        with self._lock:
            agv.state = AGVState.IDLE

    def _update_nav_feedback(self, feedback, session: NavigationSession, agv: AGVTracker):
        """Update navigation feedback."""
        # Current state
        if MSGS_AVAILABLE:
            feedback.current_pose = PoseStamped()
            feedback.current_pose.pose.position.x = agv.position[0]
            feedback.current_pose.pose.position.y = agv.position[1]
            feedback.current_pose.pose.orientation = self._yaw_to_quaternion(agv.position[2])

            feedback.current_velocity = Twist()
            feedback.current_velocity.linear.x = agv.velocity[0]
            feedback.current_velocity.linear.y = agv.velocity[1]
            feedback.current_velocity.angular.z = agv.velocity[2]

        # Progress
        total_distance = session.distance_traveled + session.distance_remaining
        feedback.progress_percent = (
            session.distance_traveled / total_distance * 100
            if total_distance > 0 else 0
        )
        feedback.distance_remaining_m = session.distance_remaining

        avg_speed = session.distance_traveled / max(0.1, time.time() - session.start_time)
        feedback.estimated_time_remaining_sec = (
            session.distance_remaining / avg_speed if avg_speed > 0 else 0
        )

        # Path info
        feedback.current_waypoint = session.current_waypoint
        feedback.total_waypoints = len(session.waypoints)

        if session.current_waypoint < len(session.waypoints) and MSGS_AVAILABLE:
            wp = session.waypoints[session.current_waypoint]
            feedback.next_waypoint = PoseStamped()
            feedback.next_waypoint.pose.position.x = wp[0]
            feedback.next_waypoint.pose.position.y = wp[1]
            feedback.next_waypoint.pose.orientation = self._yaw_to_quaternion(wp[2])

        # Status
        feedback.recovering = session.is_recovering
        feedback.recovery_reason = session.recovery_reason
        feedback.status_message = (
            f"Navigating to waypoint {session.current_waypoint + 1}/{len(session.waypoints)}"
        )

    def _dispatch_agv_callback(self, request, response):
        """Handle AGV dispatch request."""
        mission_id = f"MIS-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        self.get_logger().info(
            f'Dispatch request: {request.pickup_station} -> {request.delivery_station}'
        )

        # Validate stations
        if request.pickup_station not in self._stations:
            response.success = False
            response.message = f"Unknown pickup station: {request.pickup_station}"
            return response

        if request.delivery_station not in self._stations:
            response.success = False
            response.message = f"Unknown delivery station: {request.delivery_station}"
            return response

        # Find available AGV
        assigned_agv = None
        with self._lock:
            for agv in self._agvs.values():
                if agv.is_available and agv.state == AGVState.IDLE:
                    if agv.battery_percent >= self._battery_low:
                        assigned_agv = agv.agv_id
                        agv.is_available = False
                        break

        if not assigned_agv:
            # Queue mission
            self._pending_missions.append({
                'mission_id': mission_id,
                'pickup_station': request.pickup_station,
                'delivery_station': request.delivery_station,
                'payload_id': request.payload_id,
                'priority': request.priority,
            })

            response.success = True
            response.message = "Mission queued - no AGV available"
            response.mission_id = mission_id
            response.assigned_agv_id = ""
            return response

        # Create active mission
        self._active_missions[mission_id] = {
            'mission_id': mission_id,
            'agv_id': assigned_agv,
            'pickup_station': request.pickup_station,
            'delivery_station': request.delivery_station,
            'payload_id': request.payload_id,
            'state': MissionState.ASSIGNED,
        }

        self._publish_event('mission_assigned', {
            'mission_id': mission_id,
            'agv_id': assigned_agv,
            'pickup': request.pickup_station,
            'delivery': request.delivery_station,
        })

        response.success = True
        response.message = f"Mission assigned to AGV {assigned_agv}"
        response.mission_id = mission_id
        response.assigned_agv_id = assigned_agv

        # Estimate arrival time
        pickup_station = self._stations[request.pickup_station]
        agv_pos = self._agvs[assigned_agv].position
        distance_to_pickup = self._distance_2d(agv_pos, pickup_station.pose)
        response.estimated_arrival_sec = distance_to_pickup / self._max_velocity

        return response

    def _process_mission_queue(self):
        """Process pending missions."""
        if not self._pending_missions:
            return

        with self._lock:
            # Find available AGV
            for agv in self._agvs.values():
                if agv.is_available and agv.state == AGVState.IDLE:
                    if agv.battery_percent >= self._battery_low:
                        # Assign oldest mission
                        mission = self._pending_missions.pop(0)
                        agv.is_available = False
                        mission['agv_id'] = agv.agv_id
                        mission['state'] = MissionState.ASSIGNED
                        self._active_missions[mission['mission_id']] = mission

                        self._publish_event('mission_assigned', {
                            'mission_id': mission['mission_id'],
                            'agv_id': agv.agv_id,
                            'pickup': mission['pickup_station'],
                            'delivery': mission['delivery_station'],
                        })
                        break

    def _on_agv_status(self, agv_id: str, msg):
        """Handle AGV status update."""
        with self._lock:
            if agv_id in self._agvs:
                agv = self._agvs[agv_id]
                agv.position = (msg.position_x, msg.position_y, msg.orientation)
                agv.battery_percent = msg.battery_percent
                agv.last_seen = time.time()

                if msg.estop_active:
                    agv.state = AGVState.EMERGENCY_STOP
                elif msg.is_charging:
                    agv.state = AGVState.CHARGING

    def _publish_fleet_status(self):
        """Publish fleet status."""
        with self._lock:
            fleet_data = {
                'timestamp': time.time(),
                'agv_count': len(self._agvs),
                'available_count': sum(1 for a in self._agvs.values() if a.is_available),
                'agvs': [
                    {
                        'agv_id': agv.agv_id,
                        'name': agv.name,
                        'state': agv.state.name,
                        'position': list(agv.position),
                        'battery_percent': agv.battery_percent,
                        'current_station': agv.current_station,
                        'is_available': agv.is_available,
                    }
                    for agv in self._agvs.values()
                ],
                'pending_missions': len(self._pending_missions),
                'active_missions': len(self._active_missions),
            }

        msg = String()
        msg.data = json.dumps(fleet_data)
        self._fleet_pub.publish(msg)

    def _publish_cmd_vel(self, agv_id: str, velocity: Tuple[float, float, float]):
        """Publish velocity command to AGV."""
        if agv_id in self._cmd_pubs:
            msg = Twist()
            msg.linear.x = velocity[0]
            msg.linear.y = velocity[1]
            msg.angular.z = velocity[2]
            self._cmd_pubs[agv_id].publish(msg)

    def _publish_event(self, event_type: str, data: dict):
        """Publish fleet event."""
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'data': data,
        }
        msg = String()
        msg.data = json.dumps(event)
        self._event_pub.publish(msg)

    def _get_fleet_status(self, request, response):
        """Get fleet status."""
        with self._lock:
            status = {
                'total_agvs': len(self._agvs),
                'available': sum(1 for a in self._agvs.values() if a.is_available),
                'navigating': sum(1 for a in self._agvs.values() if a.state == AGVState.NAVIGATING),
                'charging': sum(1 for a in self._agvs.values() if a.state == AGVState.CHARGING),
                'error': sum(1 for a in self._agvs.values() if a.state in [AGVState.ERROR, AGVState.EMERGENCY_STOP]),
                'pending_missions': len(self._pending_missions),
                'active_missions': len(self._active_missions),
            }

        response.success = True
        response.message = json.dumps(status)
        return response

    def _get_stations(self, request, response):
        """Get station definitions."""
        stations = [
            {
                'station_id': s.station_id,
                'name': s.name,
                'type': s.station_type,
                'pose': list(s.pose),
            }
            for s in self._stations.values()
        ]

        response.success = True
        response.message = json.dumps({
            'station_count': len(stations),
            'stations': stations,
        })
        return response

    # Helper methods
    def _is_at_pose(
        self,
        current: Tuple[float, float, float],
        target: Tuple[float, float, float],
        pos_tol: float,
        orient_tol: float
    ) -> bool:
        """Check if at target pose within tolerance."""
        pos_error = self._distance_2d(current, target)
        orient_error = abs(self._normalize_angle(current[2] - target[2]))
        return pos_error <= pos_tol and orient_error <= orient_tol

    def _distance_2d(
        self,
        p1: Tuple[float, float, float],
        p2: Tuple[float, float, float]
    ) -> float:
        """Compute 2D distance."""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return math.sqrt(dx*dx + dy*dy)

    def _path_length(self, waypoints: List[Tuple[float, float, float]]) -> float:
        """Compute total path length."""
        if len(waypoints) < 2:
            return 0.0
        length = 0.0
        for i in range(1, len(waypoints)):
            length += self._distance_2d(waypoints[i-1], waypoints[i])
        return length

    def _remaining_path_length(
        self,
        waypoints: List[Tuple[float, float, float]],
        from_idx: int
    ) -> float:
        """Compute remaining path length from index."""
        if from_idx >= len(waypoints):
            return 0.0
        return self._path_length(waypoints[from_idx:])

    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to [-pi, pi]."""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle

    def _quaternion_to_yaw(self, q: Quaternion) -> float:
        """Convert quaternion to yaw angle."""
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def _yaw_to_quaternion(self, yaw: float) -> Quaternion:
        """Convert yaw angle to quaternion."""
        q = Quaternion()
        q.x = 0.0
        q.y = 0.0
        q.z = math.sin(yaw / 2.0)
        q.w = math.cos(yaw / 2.0)
        return q

    def _create_nav_result(self):
        """Create stub result object."""
        return type('Result', (), {
            'success': False,
            'message': '',
            'position_error': 0.0,
            'orientation_error': 0.0,
            'total_distance_m': 0.0,
            'total_time_sec': 0.0,
            'replan_count': 0,
            'recovery_count': 0,
        })()

    def _create_nav_feedback(self):
        """Create stub feedback object."""
        return type('Feedback', (), {
            'progress_percent': 0.0,
            'distance_remaining_m': 0.0,
            'estimated_time_remaining_sec': 0.0,
            'current_waypoint': 0,
            'total_waypoints': 0,
            'recovering': False,
            'recovery_reason': '',
            'status_message': '',
        })()

    async def _async_sleep(self, duration: float):
        """Async sleep helper."""
        import asyncio
        await asyncio.sleep(duration)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = AGVDispatcherNode()

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
