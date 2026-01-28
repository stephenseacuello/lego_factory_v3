"""
V8 Multi-Robot Coordinator
==========================

Advanced coordination for multiple robots:
- Swarm behavior coordination
- Collision avoidance
- Task allocation optimization
- Formation control
- Multi-agent path planning

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

import asyncio
import heapq
import logging
import math
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================
# Enums
# ============================================

class RobotType(Enum):
    """Types of robots."""
    ARM = "arm"
    AGV = "agv"
    AMR = "amr"
    COBOT = "cobot"
    DRONE = "drone"


class RobotState(Enum):
    """Robot operational states."""
    IDLE = "idle"
    MOVING = "moving"
    WORKING = "working"
    CHARGING = "charging"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    EMERGENCY_STOP = "emergency_stop"


class CoordinationMode(Enum):
    """Robot coordination modes."""
    INDEPENDENT = "independent"
    SYNCHRONIZED = "synchronized"
    LEADER_FOLLOWER = "leader_follower"
    FORMATION = "formation"
    SWARM = "swarm"


class AllocationStrategy(Enum):
    """Task allocation strategies."""
    NEAREST = "nearest"
    LOAD_BALANCED = "load_balanced"
    PRIORITY_BASED = "priority_based"
    AUCTION = "auction"
    LEARNING = "learning"


class CollisionAvoidanceMethod(Enum):
    """Collision avoidance methods."""
    NONE = "none"
    VELOCITY_OBSTACLES = "velocity_obstacles"
    RECIPROCAL = "reciprocal"
    PRIORITY_BASED = "priority_based"
    TIME_BASED = "time_based"


# ============================================
# Data Classes
# ============================================

@dataclass
class Position3D:
    """3D position."""
    x: float
    y: float
    z: float = 0.0

    def distance_to(self, other: 'Position3D') -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass
class Velocity3D:
    """3D velocity."""
    vx: float
    vy: float
    vz: float = 0.0

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.vx ** 2 + self.vy ** 2 + self.vz ** 2)

    def to_dict(self) -> Dict[str, float]:
        return {"vx": self.vx, "vy": self.vy, "vz": self.vz}


@dataclass
class RobotStatus:
    """Current status of a robot."""
    robot_id: str
    name: str
    robot_type: RobotType
    state: RobotState
    position: Position3D
    velocity: Velocity3D
    orientation: float  # radians
    battery_level: float  # 0-100
    current_task_id: Optional[str] = None
    workspace_id: str = "main"
    capabilities: List[str] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "robot_id": self.robot_id,
            "name": self.name,
            "robot_type": self.robot_type.value,
            "state": self.state.value,
            "position": self.position.to_dict(),
            "velocity": self.velocity.to_dict(),
            "orientation": self.orientation,
            "battery_level": self.battery_level,
            "current_task_id": self.current_task_id,
            "workspace_id": self.workspace_id,
            "capabilities": self.capabilities,
            "last_update": self.last_update.isoformat(),
            "error_message": self.error_message,
        }


@dataclass
class CoordinatedTask:
    """Task requiring multi-robot coordination."""
    task_id: str
    name: str
    task_type: str
    coordination_mode: CoordinationMode
    required_robots: int
    assigned_robots: List[str] = field(default_factory=list)
    waypoints: List[Position3D] = field(default_factory=list)
    priority: int = 5
    deadline: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "pending"
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type,
            "coordination_mode": self.coordination_mode.value,
            "required_robots": self.required_robots,
            "assigned_robots": self.assigned_robots,
            "waypoints": [w.to_dict() for w in self.waypoints],
            "priority": self.priority,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "parameters": self.parameters,
        }


@dataclass
class Formation:
    """Robot formation configuration."""
    formation_id: str
    name: str
    robot_positions: Dict[str, Position3D]  # robot_id -> relative position
    leader_id: Optional[str] = None
    formation_type: str = "custom"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "formation_id": self.formation_id,
            "name": self.name,
            "robot_positions": {k: v.to_dict() for k, v in self.robot_positions.items()},
            "leader_id": self.leader_id,
            "formation_type": self.formation_type,
        }


@dataclass
class CollisionRisk:
    """Detected collision risk."""
    risk_id: str
    robot_a: str
    robot_b: str
    time_to_collision: float  # seconds
    collision_point: Position3D
    severity: str  # low, medium, high, critical
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "robot_a": self.robot_a,
            "robot_b": self.robot_b,
            "time_to_collision": self.time_to_collision,
            "collision_point": self.collision_point.to_dict(),
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================
# Multi-Robot Coordinator
# ============================================

class MultiRobotCoordinator:
    """
    Advanced multi-robot coordination system.

    Capabilities:
    - Fleet management and status tracking
    - Task allocation and scheduling
    - Collision avoidance
    - Formation control
    - Swarm behavior
    """

    def __init__(
        self,
        collision_avoidance: CollisionAvoidanceMethod = CollisionAvoidanceMethod.RECIPROCAL,
        allocation_strategy: AllocationStrategy = AllocationStrategy.LOAD_BALANCED,
    ):
        self._robots: Dict[str, RobotStatus] = {}
        self._tasks: Dict[str, CoordinatedTask] = {}
        self._formations: Dict[str, Formation] = {}
        self._collision_risks: Dict[str, CollisionRisk] = {}
        self._lock = threading.RLock()

        self._collision_avoidance = collision_avoidance
        self._allocation_strategy = allocation_strategy

        # Spatial index for collision detection
        self._spatial_grid: Dict[Tuple[int, int], Set[str]] = defaultdict(set)
        self._grid_cell_size = 1.0  # meters

        # Safety parameters
        self._min_separation_distance = 0.5  # meters
        self._collision_detection_horizon = 5.0  # seconds

        # Background threads
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None

        # Built-in formations
        self._register_default_formations()

        logger.info("MultiRobotCoordinator initialized")

    def _register_default_formations(self):
        """Register default formation templates."""
        # Line formation
        self._formations["line"] = Formation(
            formation_id="line",
            name="Line Formation",
            robot_positions={
                "robot_0": Position3D(0, 0),
                "robot_1": Position3D(1, 0),
                "robot_2": Position3D(2, 0),
                "robot_3": Position3D(3, 0),
            },
            formation_type="line",
        )

        # V formation
        self._formations["v_formation"] = Formation(
            formation_id="v_formation",
            name="V Formation",
            robot_positions={
                "robot_0": Position3D(0, 0),
                "robot_1": Position3D(-1, -1),
                "robot_2": Position3D(1, -1),
                "robot_3": Position3D(-2, -2),
                "robot_4": Position3D(2, -2),
            },
            leader_id="robot_0",
            formation_type="v",
        )

        # Square formation
        self._formations["square"] = Formation(
            formation_id="square",
            name="Square Formation",
            robot_positions={
                "robot_0": Position3D(0, 0),
                "robot_1": Position3D(1, 0),
                "robot_2": Position3D(0, 1),
                "robot_3": Position3D(1, 1),
            },
            formation_type="square",
        )

    # ============================================
    # Robot Registration
    # ============================================

    def register_robot(
        self,
        robot_id: str,
        name: str,
        robot_type: RobotType,
        initial_position: Position3D,
        capabilities: List[str] = None,
        workspace_id: str = "main",
    ) -> RobotStatus:
        """Register a robot with the coordinator."""
        with self._lock:
            status = RobotStatus(
                robot_id=robot_id,
                name=name,
                robot_type=robot_type,
                state=RobotState.IDLE,
                position=initial_position,
                velocity=Velocity3D(0, 0, 0),
                orientation=0,
                battery_level=100.0,
                workspace_id=workspace_id,
                capabilities=capabilities or [],
            )

            self._robots[robot_id] = status
            self._update_spatial_index(robot_id, initial_position)

            logger.info(f"Registered robot: {name} ({robot_id})")
            return status

    def unregister_robot(self, robot_id: str) -> bool:
        """Unregister a robot."""
        with self._lock:
            if robot_id in self._robots:
                robot = self._robots.pop(robot_id)
                self._remove_from_spatial_index(robot_id)
                logger.info(f"Unregistered robot: {robot.name}")
                return True
            return False

    def update_robot_status(
        self,
        robot_id: str,
        position: Optional[Position3D] = None,
        velocity: Optional[Velocity3D] = None,
        state: Optional[RobotState] = None,
        battery_level: Optional[float] = None,
        orientation: Optional[float] = None,
    ):
        """Update robot status."""
        with self._lock:
            robot = self._robots.get(robot_id)
            if not robot:
                return

            if position:
                old_pos = robot.position
                robot.position = position
                self._update_spatial_index(robot_id, position, old_pos)

            if velocity:
                robot.velocity = velocity
            if state:
                robot.state = state
            if battery_level is not None:
                robot.battery_level = battery_level
            if orientation is not None:
                robot.orientation = orientation

            robot.last_update = datetime.now()

            # Check for collisions after position update
            if position:
                self._check_collisions(robot_id)

    def get_robot_status(self, robot_id: str) -> Optional[RobotStatus]:
        """Get current robot status."""
        return self._robots.get(robot_id)

    def get_all_robots(self) -> List[RobotStatus]:
        """Get all registered robots."""
        return list(self._robots.values())

    # ============================================
    # Spatial Indexing
    # ============================================

    def _pos_to_cell(self, pos: Position3D) -> Tuple[int, int]:
        """Convert position to grid cell."""
        return (
            int(pos.x / self._grid_cell_size),
            int(pos.y / self._grid_cell_size),
        )

    def _update_spatial_index(
        self,
        robot_id: str,
        new_pos: Position3D,
        old_pos: Optional[Position3D] = None,
    ):
        """Update spatial index for robot."""
        if old_pos:
            old_cell = self._pos_to_cell(old_pos)
            self._spatial_grid[old_cell].discard(robot_id)

        new_cell = self._pos_to_cell(new_pos)
        self._spatial_grid[new_cell].add(robot_id)

    def _remove_from_spatial_index(self, robot_id: str):
        """Remove robot from spatial index."""
        for cell_robots in self._spatial_grid.values():
            cell_robots.discard(robot_id)

    def _get_nearby_robots(
        self,
        position: Position3D,
        radius: float,
    ) -> List[str]:
        """Get robots within radius of position."""
        nearby = []
        center_cell = self._pos_to_cell(position)
        cell_radius = int(radius / self._grid_cell_size) + 1

        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell = (center_cell[0] + dx, center_cell[1] + dy)
                for robot_id in self._spatial_grid.get(cell, set()):
                    robot = self._robots.get(robot_id)
                    if robot and robot.position.distance_to(position) <= radius:
                        nearby.append(robot_id)

        return nearby

    # ============================================
    # Collision Avoidance
    # ============================================

    def _check_collisions(self, robot_id: str):
        """Check for potential collisions with nearby robots."""
        robot = self._robots.get(robot_id)
        if not robot:
            return

        nearby = self._get_nearby_robots(
            robot.position,
            self._min_separation_distance * 3,
        )

        for other_id in nearby:
            if other_id == robot_id:
                continue

            other = self._robots.get(other_id)
            if not other:
                continue

            # Calculate time to collision
            ttc = self._calculate_time_to_collision(robot, other)

            if ttc is not None and ttc < self._collision_detection_horizon:
                self._handle_collision_risk(robot, other, ttc)

    def _calculate_time_to_collision(
        self,
        robot_a: RobotStatus,
        robot_b: RobotStatus,
    ) -> Optional[float]:
        """Calculate time to collision between two robots."""
        # Relative position and velocity
        rel_pos = Position3D(
            robot_b.position.x - robot_a.position.x,
            robot_b.position.y - robot_a.position.y,
            robot_b.position.z - robot_a.position.z,
        )

        rel_vel = Velocity3D(
            robot_b.velocity.vx - robot_a.velocity.vx,
            robot_b.velocity.vy - robot_a.velocity.vy,
            robot_b.velocity.vz - robot_a.velocity.vz,
        )

        # Combined radius (separation distance)
        combined_radius = self._min_separation_distance * 2

        # Quadratic equation for collision time
        a = rel_vel.vx ** 2 + rel_vel.vy ** 2 + rel_vel.vz ** 2
        b = 2 * (rel_pos.x * rel_vel.vx + rel_pos.y * rel_vel.vy + rel_pos.z * rel_vel.vz)
        c = rel_pos.x ** 2 + rel_pos.y ** 2 + rel_pos.z ** 2 - combined_radius ** 2

        if a == 0:
            return None  # No relative motion

        discriminant = b ** 2 - 4 * a * c
        if discriminant < 0:
            return None  # No collision

        sqrt_disc = math.sqrt(discriminant)
        t1 = (-b - sqrt_disc) / (2 * a)
        t2 = (-b + sqrt_disc) / (2 * a)

        # Return earliest positive collision time
        if t1 > 0:
            return t1
        elif t2 > 0:
            return t2
        return None

    def _handle_collision_risk(
        self,
        robot_a: RobotStatus,
        robot_b: RobotStatus,
        time_to_collision: float,
    ):
        """Handle detected collision risk."""
        # Determine severity
        if time_to_collision < 1.0:
            severity = "critical"
        elif time_to_collision < 2.0:
            severity = "high"
        elif time_to_collision < 3.0:
            severity = "medium"
        else:
            severity = "low"

        # Calculate collision point
        collision_point = Position3D(
            (robot_a.position.x + robot_b.position.x) / 2,
            (robot_a.position.y + robot_b.position.y) / 2,
            (robot_a.position.z + robot_b.position.z) / 2,
        )

        risk = CollisionRisk(
            risk_id=f"risk-{uuid.uuid4().hex[:8]}",
            robot_a=robot_a.robot_id,
            robot_b=robot_b.robot_id,
            time_to_collision=time_to_collision,
            collision_point=collision_point,
            severity=severity,
        )

        self._collision_risks[risk.risk_id] = risk

        logger.warning(
            f"Collision risk detected: {robot_a.name} <-> {robot_b.name}, "
            f"TTC: {time_to_collision:.2f}s, severity: {severity}"
        )

        # Apply collision avoidance
        if self._collision_avoidance != CollisionAvoidanceMethod.NONE:
            self._apply_collision_avoidance(robot_a, robot_b, risk)

    def _apply_collision_avoidance(
        self,
        robot_a: RobotStatus,
        robot_b: RobotStatus,
        risk: CollisionRisk,
    ):
        """Apply collision avoidance strategy."""
        if self._collision_avoidance == CollisionAvoidanceMethod.PRIORITY_BASED:
            # Lower ID has priority, other robot stops
            if robot_a.robot_id < robot_b.robot_id:
                self._stop_robot(robot_b.robot_id)
            else:
                self._stop_robot(robot_a.robot_id)

        elif self._collision_avoidance == CollisionAvoidanceMethod.RECIPROCAL:
            # Both robots adjust velocity to avoid
            self._adjust_velocity_rvo(robot_a, robot_b)

        elif self._collision_avoidance == CollisionAvoidanceMethod.TIME_BASED:
            # Robot arriving later waits
            dist_a = robot_a.position.distance_to(risk.collision_point)
            dist_b = robot_b.position.distance_to(risk.collision_point)
            speed_a = robot_a.velocity.magnitude or 0.1
            speed_b = robot_b.velocity.magnitude or 0.1

            time_a = dist_a / speed_a
            time_b = dist_b / speed_b

            if time_a > time_b:
                self._stop_robot(robot_a.robot_id)
            else:
                self._stop_robot(robot_b.robot_id)

    def _stop_robot(self, robot_id: str):
        """Send stop command to robot."""
        robot = self._robots.get(robot_id)
        if robot:
            robot.velocity = Velocity3D(0, 0, 0)
            logger.info(f"Stopped robot {robot.name} for collision avoidance")

    def _adjust_velocity_rvo(
        self,
        robot_a: RobotStatus,
        robot_b: RobotStatus,
    ):
        """Apply Reciprocal Velocity Obstacles."""
        # Simplified RVO - reduce velocity by 50%
        robot_a.velocity = Velocity3D(
            robot_a.velocity.vx * 0.5,
            robot_a.velocity.vy * 0.5,
            robot_a.velocity.vz * 0.5,
        )
        robot_b.velocity = Velocity3D(
            robot_b.velocity.vx * 0.5,
            robot_b.velocity.vy * 0.5,
            robot_b.velocity.vz * 0.5,
        )

    # ============================================
    # Task Management
    # ============================================

    def create_coordinated_task(
        self,
        name: str,
        task_type: str,
        coordination_mode: CoordinationMode,
        required_robots: int,
        waypoints: List[Position3D] = None,
        priority: int = 5,
        deadline: Optional[datetime] = None,
        parameters: Dict[str, Any] = None,
    ) -> CoordinatedTask:
        """Create a new coordinated task."""
        task = CoordinatedTask(
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            name=name,
            task_type=task_type,
            coordination_mode=coordination_mode,
            required_robots=required_robots,
            waypoints=waypoints or [],
            priority=priority,
            deadline=deadline,
            parameters=parameters or {},
        )

        with self._lock:
            self._tasks[task.task_id] = task

            # Auto-allocate robots
            self._allocate_robots_to_task(task)

        logger.info(f"Created coordinated task: {name}")
        return task

    def _allocate_robots_to_task(self, task: CoordinatedTask):
        """Allocate robots to a task based on strategy."""
        available = [
            r for r in self._robots.values()
            if r.state == RobotState.IDLE and r.current_task_id is None
        ]

        if len(available) < task.required_robots:
            logger.warning(f"Not enough robots for task {task.task_id}")
            return

        if self._allocation_strategy == AllocationStrategy.NEAREST:
            # Sort by distance to first waypoint
            if task.waypoints:
                target = task.waypoints[0]
                available.sort(key=lambda r: r.position.distance_to(target))

        elif self._allocation_strategy == AllocationStrategy.LOAD_BALANCED:
            # Sort by battery level (prefer fully charged)
            available.sort(key=lambda r: -r.battery_level)

        # Assign robots
        for i, robot in enumerate(available[:task.required_robots]):
            task.assigned_robots.append(robot.robot_id)
            robot.current_task_id = task.task_id

        logger.info(f"Allocated {len(task.assigned_robots)} robots to task {task.task_id}")

    def start_task(self, task_id: str) -> bool:
        """Start executing a coordinated task."""
        task = self._tasks.get(task_id)
        if not task or len(task.assigned_robots) < task.required_robots:
            return False

        with self._lock:
            task.status = "running"
            task.started_at = datetime.now()

            for robot_id in task.assigned_robots:
                robot = self._robots.get(robot_id)
                if robot:
                    robot.state = RobotState.WORKING

        logger.info(f"Started coordinated task: {task_id}")
        return True

    def complete_task(self, task_id: str) -> bool:
        """Mark a task as complete."""
        task = self._tasks.get(task_id)
        if not task:
            return False

        with self._lock:
            task.status = "completed"
            task.completed_at = datetime.now()

            for robot_id in task.assigned_robots:
                robot = self._robots.get(robot_id)
                if robot:
                    robot.state = RobotState.IDLE
                    robot.current_task_id = None

        logger.info(f"Completed coordinated task: {task_id}")
        return True

    # ============================================
    # Formation Control
    # ============================================

    def create_formation(
        self,
        name: str,
        robot_positions: Dict[str, Position3D],
        leader_id: Optional[str] = None,
    ) -> Formation:
        """Create a custom formation."""
        formation = Formation(
            formation_id=f"formation-{uuid.uuid4().hex[:8]}",
            name=name,
            robot_positions=robot_positions,
            leader_id=leader_id,
            formation_type="custom",
        )

        self._formations[formation.formation_id] = formation
        return formation

    def apply_formation(
        self,
        formation_id: str,
        robot_ids: List[str],
        center: Position3D,
        scale: float = 1.0,
    ) -> bool:
        """Apply a formation to a set of robots."""
        formation = self._formations.get(formation_id)
        if not formation:
            return False

        positions = list(formation.robot_positions.values())
        if len(robot_ids) > len(positions):
            logger.warning("Not enough formation positions for all robots")
            return False

        with self._lock:
            for i, robot_id in enumerate(robot_ids):
                robot = self._robots.get(robot_id)
                if robot:
                    rel_pos = positions[i]
                    target = Position3D(
                        center.x + rel_pos.x * scale,
                        center.y + rel_pos.y * scale,
                        center.z + rel_pos.z * scale,
                    )
                    # In production, this would send move commands
                    logger.info(f"Moving {robot.name} to formation position {target.to_dict()}")

        return True

    # ============================================
    # Monitoring
    # ============================================

    def start_monitoring(self, interval_seconds: float = 0.5):
        """Start background monitoring."""
        if self._monitoring_active:
            return

        self._monitoring_active = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(interval_seconds,),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("Multi-robot monitoring started")

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)

    def _monitoring_loop(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring_active:
            try:
                self._check_all_collisions()
                self._cleanup_old_risks()
                self._check_task_progress()
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
            time.sleep(interval)

    def _check_all_collisions(self):
        """Check for collisions between all robots."""
        robot_ids = list(self._robots.keys())
        for i, robot_id in enumerate(robot_ids):
            self._check_collisions(robot_id)

    def _cleanup_old_risks(self):
        """Remove old collision risks."""
        cutoff = datetime.now() - timedelta(seconds=10)
        old_risks = [
            risk_id for risk_id, risk in self._collision_risks.items()
            if risk.timestamp < cutoff
        ]
        for risk_id in old_risks:
            del self._collision_risks[risk_id]

    def _check_task_progress(self):
        """Check progress of running tasks."""
        for task in self._tasks.values():
            if task.status == "running" and task.deadline:
                if datetime.now() > task.deadline:
                    logger.warning(f"Task {task.task_id} missed deadline")

    # ============================================
    # Statistics
    # ============================================

    def get_fleet_statistics(self) -> Dict[str, Any]:
        """Get fleet statistics."""
        state_counts = {}
        for state in RobotState:
            state_counts[state.value] = sum(
                1 for r in self._robots.values()
                if r.state == state
            )

        avg_battery = 0
        if self._robots:
            avg_battery = sum(r.battery_level for r in self._robots.values()) / len(self._robots)

        return {
            "total_robots": len(self._robots),
            "state_distribution": state_counts,
            "average_battery": round(avg_battery, 1),
            "active_tasks": sum(1 for t in self._tasks.values() if t.status == "running"),
            "pending_tasks": sum(1 for t in self._tasks.values() if t.status == "pending"),
            "collision_risks": len(self._collision_risks),
            "formations": len(self._formations),
        }


# ============================================
# Singleton Instance
# ============================================

_coordinator: Optional[MultiRobotCoordinator] = None
_coordinator_lock = threading.Lock()


def get_multi_robot_coordinator() -> MultiRobotCoordinator:
    """Get or create the multi-robot coordinator singleton."""
    global _coordinator

    if _coordinator is None:
        with _coordinator_lock:
            if _coordinator is None:
                _coordinator = MultiRobotCoordinator()

    return _coordinator


__all__ = [
    'RobotType',
    'RobotState',
    'CoordinationMode',
    'AllocationStrategy',
    'CollisionAvoidanceMethod',
    'Position3D',
    'Velocity3D',
    'RobotStatus',
    'CoordinatedTask',
    'Formation',
    'CollisionRisk',
    'MultiRobotCoordinator',
    'get_multi_robot_coordinator',
]
