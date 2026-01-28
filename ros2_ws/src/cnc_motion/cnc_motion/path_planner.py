#!/usr/bin/env python3
"""
Path Planner - Motion path planning service for CNC machines

Provides path planning services for safe tool movement, including:
- Linear interpolation with collision checking
- Spline-based smooth paths
- Safe retract paths
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from typing import List, Tuple, Optional
import numpy as np
from geometry_msgs.msg import Point, Pose, PoseStamped

from cnc_interfaces.msg import PathPlan, CollisionWarning
from cnc_interfaces.srv import PlanPath


class PathPlannerNode(Node):
    """Path planning service for CNC machines"""

    def __init__(self):
        super().__init__('path_planner')

        # Parameters
        self.declare_parameter('default_clearance', 5.0)  # mm
        self.declare_parameter('default_max_velocity', 5000.0)  # mm/min
        self.declare_parameter('planning_resolution', 1.0)  # mm
        self.declare_parameter('optimization_iterations', 100)

        self.default_clearance = self.get_parameter('default_clearance').value
        self.default_velocity = self.get_parameter('default_max_velocity').value
        self.resolution = self.get_parameter('planning_resolution').value
        self.opt_iterations = self.get_parameter('optimization_iterations').value

        # Work envelope (should be loaded from config)
        self.envelope = {
            'x_min': 0, 'x_max': 300,
            'y_min': 0, 'y_max': 200,
            'z_min': -100, 'z_max': 0,
        }

        # Obstacles (simplified bounding boxes)
        self.obstacles = []

        # QoS
        qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # Service
        self.plan_srv = self.create_service(
            PlanPath,
            '/motion/plan_path',
            self.plan_path_callback
        )

        # Publisher
        self.path_pub = self.create_publisher(
            PathPlan,
            '/motion/planned_path',
            qos
        )

        self.get_logger().info('Path Planner service started')

    def plan_path_callback(self, request, response):
        """Handle path planning request"""
        import time
        start_time = time.time()

        machine_id = request.machine_id

        # Extract start and goal
        start = (
            request.start_pose.position.x,
            request.start_pose.position.y,
            request.start_pose.position.z
        )
        goal = (
            request.goal_pose.position.x,
            request.goal_pose.position.y,
            request.goal_pose.position.z
        )

        clearance = request.clearance_distance if request.clearance_distance > 0 else self.default_clearance
        max_vel = request.max_velocity if request.max_velocity > 0 else self.default_velocity
        algorithm = request.algorithm if request.algorithm else "linear"

        # Plan path based on algorithm
        if algorithm == "linear":
            waypoints = self.plan_linear(start, goal, clearance)
        elif algorithm == "spline":
            waypoints = self.plan_spline(start, goal, clearance)
        elif algorithm == "rrt":
            waypoints = self.plan_rrt(start, goal, clearance)
        else:
            waypoints = self.plan_linear(start, goal, clearance)

        # Check for collisions along path
        collision_free, collisions = self.check_path_collisions(waypoints, clearance)

        # Optimize path if requested
        if request.optimize and collision_free:
            waypoints = self.optimize_path(waypoints, request.optimization_goal)

        # Calculate path metrics
        total_distance = self.calculate_path_distance(waypoints)
        estimated_time = total_distance / max_vel * 60  # seconds

        # Build response
        response.success = collision_free
        response.message = "Path planned successfully" if collision_free else "Path has collisions"
        response.planning_time = time.time() - start_time

        # Build PathPlan message
        path = PathPlan()
        path.header.stamp = self.get_clock().now().to_msg()
        path.machine_id = machine_id
        path.plan_id = f"path_{int(time.time())}"
        path.start_pose = request.start_pose
        path.goal_pose = request.goal_pose
        path.planning_algorithm = algorithm

        # Add waypoints
        for i, wp in enumerate(waypoints):
            pose = PoseStamped()
            pose.header.stamp = path.header.stamp
            pose.pose.position = Point(x=wp[0], y=wp[1], z=wp[2])
            path.waypoints.append(pose)

            # Calculate velocities (ramp up/down at ends)
            ramp_factor = min(i / max(len(waypoints) / 4, 1),
                              (len(waypoints) - 1 - i) / max(len(waypoints) / 4, 1),
                              1.0)
            path.velocities.append(max_vel * ramp_factor)
            path.accelerations.append(0.0)

        path.total_distance = total_distance
        path.estimated_time = estimated_time
        path.max_velocity = max_vel

        path.collision_free = collision_free
        path.min_clearance = clearance
        path.potential_collisions = collisions

        path.waypoint_count = len(waypoints)
        path.smoothness_score = self.calculate_smoothness(waypoints)
        path.efficiency_score = self.calculate_efficiency(waypoints, start, goal)

        path.optimized = request.optimize
        path.optimization_method = request.optimization_goal

        path.status = PathPlan.STATUS_SUCCESS if collision_free else PathPlan.STATUS_COLLISION
        path.status_message = response.message

        response.path = path

        # Publish path
        self.path_pub.publish(path)

        return response

    def plan_linear(self, start: Tuple, goal: Tuple, clearance: float) -> List[Tuple]:
        """Plan a simple linear path with safe Z movements"""
        waypoints = []

        # Safe Z height (above work)
        safe_z = max(0, start[2], goal[2]) + clearance

        # If moving in XY, first retract to safe Z
        if abs(start[0] - goal[0]) > 0.1 or abs(start[1] - goal[1]) > 0.1:
            # Retract
            waypoints.append((start[0], start[1], safe_z))
            # Move XY
            waypoints.append((goal[0], goal[1], safe_z))
            # Plunge
            waypoints.append(goal)
        else:
            # Just Z movement
            waypoints.append(goal)

        return [start] + waypoints

    def plan_spline(self, start: Tuple, goal: Tuple, clearance: float) -> List[Tuple]:
        """Plan a smooth spline path"""
        # Generate intermediate points
        n_points = max(10, int(np.linalg.norm(np.array(goal) - np.array(start)) / self.resolution))

        # Simple cubic interpolation
        t = np.linspace(0, 1, n_points)

        waypoints = []
        for ti in t:
            # Smooth interpolation with Z arc
            x = start[0] + (goal[0] - start[0]) * ti
            y = start[1] + (goal[1] - start[1]) * ti

            # Arc up in Z for clearance
            z_base = start[2] + (goal[2] - start[2]) * ti
            z_arc = clearance * np.sin(np.pi * ti)  # Arc above linear path
            z = z_base + z_arc

            waypoints.append((x, y, z))

        return waypoints

    def plan_rrt(self, start: Tuple, goal: Tuple, clearance: float,
                 max_iterations: int = 1000) -> List[Tuple]:
        """
        Rapidly-exploring Random Tree path planning

        Simplified RRT for demonstration - in production use OMPL
        """
        # For CNC, usually linear paths are sufficient
        # Fall back to linear with obstacle avoidance
        return self.plan_linear(start, goal, clearance)

    def check_path_collisions(self, waypoints: List[Tuple],
                               clearance: float) -> Tuple[bool, List[CollisionWarning]]:
        """Check path for collisions with obstacles"""
        collisions = []

        for i, wp in enumerate(waypoints):
            # Check against envelope
            if not self.point_in_envelope(wp):
                warning = CollisionWarning()
                warning.collision_type = CollisionWarning.COLLISION_AXIS_LIMIT
                warning.severity = CollisionWarning.SEVERITY_CRITICAL
                warning.collision_point = Point(x=wp[0], y=wp[1], z=wp[2])
                warning.action_message = f"Waypoint {i} outside work envelope"
                collisions.append(warning)

            # Check against obstacles
            for obs in self.obstacles:
                dist = self.point_to_box_distance(wp, obs)
                if dist < clearance:
                    warning = CollisionWarning()
                    warning.collision_type = CollisionWarning.COLLISION_TOOL_FIXTURE
                    warning.severity = (CollisionWarning.SEVERITY_COLLISION if dist < 0
                                        else CollisionWarning.SEVERITY_WARNING)
                    warning.collision_point = Point(x=wp[0], y=wp[1], z=wp[2])
                    warning.min_distance = dist
                    warning.obstacle_id = obs.get('name', 'unknown')
                    collisions.append(warning)

        return len(collisions) == 0, collisions

    def point_in_envelope(self, point: Tuple) -> bool:
        """Check if point is within work envelope"""
        x, y, z = point
        return (self.envelope['x_min'] <= x <= self.envelope['x_max'] and
                self.envelope['y_min'] <= y <= self.envelope['y_max'] and
                self.envelope['z_min'] <= z <= self.envelope['z_max'])

    def point_to_box_distance(self, point: Tuple, box: dict) -> float:
        """Calculate distance from point to axis-aligned bounding box"""
        x, y, z = point
        dx = max(box['min_x'] - x, 0, x - box['max_x'])
        dy = max(box['min_y'] - y, 0, y - box['max_y'])
        dz = max(box['min_z'] - z, 0, z - box['max_z'])
        return np.sqrt(dx*dx + dy*dy + dz*dz)

    def optimize_path(self, waypoints: List[Tuple], goal: str) -> List[Tuple]:
        """Optimize path based on goal (time, distance, smoothness)"""
        if goal == "distance":
            return self.simplify_path(waypoints)
        elif goal == "smoothness":
            return self.smooth_path(waypoints)
        else:  # time
            return self.simplify_path(waypoints)

    def simplify_path(self, waypoints: List[Tuple], tolerance: float = 0.5) -> List[Tuple]:
        """Remove unnecessary waypoints using Ramer-Douglas-Peucker"""
        if len(waypoints) <= 2:
            return waypoints

        # Find point with maximum distance from line
        start = np.array(waypoints[0])
        end = np.array(waypoints[-1])

        max_dist = 0
        max_idx = 0

        for i in range(1, len(waypoints) - 1):
            point = np.array(waypoints[i])
            dist = self.point_to_line_distance(point, start, end)
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist > tolerance:
            # Recursive simplification
            left = self.simplify_path(waypoints[:max_idx + 1], tolerance)
            right = self.simplify_path(waypoints[max_idx:], tolerance)
            return left[:-1] + right
        else:
            return [waypoints[0], waypoints[-1]]

    def smooth_path(self, waypoints: List[Tuple], iterations: int = 10) -> List[Tuple]:
        """Apply smoothing filter to path"""
        if len(waypoints) <= 2:
            return waypoints

        smoothed = list(waypoints)

        for _ in range(iterations):
            new_path = [smoothed[0]]
            for i in range(1, len(smoothed) - 1):
                prev = np.array(smoothed[i - 1])
                curr = np.array(smoothed[i])
                next_pt = np.array(smoothed[i + 1])

                # Weighted average
                avg = 0.25 * prev + 0.5 * curr + 0.25 * next_pt
                new_path.append(tuple(avg))

            new_path.append(smoothed[-1])
            smoothed = new_path

        return smoothed

    def point_to_line_distance(self, point: np.ndarray, line_start: np.ndarray,
                               line_end: np.ndarray) -> float:
        """Calculate perpendicular distance from point to line"""
        if np.allclose(line_start, line_end):
            return np.linalg.norm(point - line_start)

        line_vec = line_end - line_start
        point_vec = point - line_start
        line_len = np.linalg.norm(line_vec)
        line_unit = line_vec / line_len

        proj_length = np.dot(point_vec, line_unit)
        proj_length = np.clip(proj_length, 0, line_len)

        proj_point = line_start + proj_length * line_unit
        return np.linalg.norm(point - proj_point)

    def calculate_path_distance(self, waypoints: List[Tuple]) -> float:
        """Calculate total path distance"""
        distance = 0.0
        for i in range(1, len(waypoints)):
            p1 = np.array(waypoints[i - 1])
            p2 = np.array(waypoints[i])
            distance += np.linalg.norm(p2 - p1)
        return distance

    def calculate_smoothness(self, waypoints: List[Tuple]) -> float:
        """Calculate path smoothness score (0-1)"""
        if len(waypoints) < 3:
            return 1.0

        angles = []
        for i in range(1, len(waypoints) - 1):
            v1 = np.array(waypoints[i]) - np.array(waypoints[i - 1])
            v2 = np.array(waypoints[i + 1]) - np.array(waypoints[i])

            if np.linalg.norm(v1) > 0 and np.linalg.norm(v2) > 0:
                cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                cos_angle = np.clip(cos_angle, -1, 1)
                angle = np.arccos(cos_angle)
                angles.append(angle)

        if not angles:
            return 1.0

        # Smoothness is inverse of average angle deviation
        avg_angle = np.mean(angles)
        return max(0, 1.0 - avg_angle / np.pi)

    def calculate_efficiency(self, waypoints: List[Tuple], start: Tuple,
                              goal: Tuple) -> float:
        """Calculate path efficiency (direct distance / actual distance)"""
        direct = np.linalg.norm(np.array(goal) - np.array(start))
        actual = self.calculate_path_distance(waypoints)

        if actual == 0:
            return 1.0

        return min(1.0, direct / actual)


def main(args=None):
    rclpy.init(args=args)
    node = PathPlannerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
