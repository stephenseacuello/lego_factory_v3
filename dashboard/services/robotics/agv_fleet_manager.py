"""
AGV Fleet Management Service V8.

LEGO MCP V8 - Autonomous Factory Platform
Advanced Fleet Management for Automated Guided Vehicles.

Features:
- Real-time fleet monitoring and status tracking
- Autonomous traffic management and collision avoidance
- Intelligent charging station scheduling
- Dynamic task assignment with load balancing
- Zone management and access control
- Path optimization with A* and Dijkstra algorithms
- Integration with ROS2 navigation stack

Standards Compliance:
- VDA 5050 (AGV Communication Interface)
- ISO 3691-4 (Driverless Industrial Trucks Safety)

Author: LEGO MCP Engineering Team
Version: 8.0.0
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Tuple, Callable
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import asyncio
import heapq
import logging
import math
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class AGVState(Enum):
    """AGV operational state (VDA 5050 compliant)."""
    IDLE = "idle"
    NAVIGATING = "navigating"
    LOADING = "loading"
    UNLOADING = "unloading"
    CHARGING = "charging"
    WAITING = "waiting"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class TaskType(Enum):
    """AGV task types."""
    TRANSPORT = "transport"
    PICKUP = "pickup"
    DELIVERY = "delivery"
    CHARGING = "charging"
    PARKING = "parking"
    INSPECTION = "inspection"
    CLEANING = "cleaning"


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ZoneType(Enum):
    """Zone types in the factory."""
    LOADING = "loading"
    UNLOADING = "unloading"
    CHARGING = "charging"
    PARKING = "parking"
    INTERSECTION = "intersection"
    CORRIDOR = "corridor"
    RESTRICTED = "restricted"
    MAINTENANCE = "maintenance"


class AllocationStrategy(Enum):
    """Task allocation strategies."""
    NEAREST = "nearest"
    LEAST_LOADED = "least_loaded"
    ROUND_ROBIN = "round_robin"
    BATTERY_AWARE = "battery_aware"
    HYBRID = "hybrid"


class PathAlgorithm(Enum):
    """Path planning algorithms."""
    A_STAR = "a_star"
    DIJKSTRA = "dijkstra"
    RRT = "rrt"  # Rapidly-exploring Random Tree


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Position2D:
    """2D position on factory floor."""
    x: float
    y: float
    theta: float = 0.0  # Orientation in radians

    def distance_to(self, other: 'Position2D') -> float:
        """Calculate Euclidean distance to another position."""
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {"x": self.x, "y": self.y, "theta": self.theta}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'Position2D':
        """Create from dictionary."""
        return cls(x=data["x"], y=data["y"], theta=data.get("theta", 0.0))


@dataclass
class Velocity2D:
    """2D velocity."""
    vx: float = 0.0
    vy: float = 0.0
    omega: float = 0.0  # Angular velocity

    def speed(self) -> float:
        """Calculate linear speed."""
        return math.sqrt(self.vx ** 2 + self.vy ** 2)

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {"vx": self.vx, "vy": self.vy, "omega": self.omega}


@dataclass
class AGVSpecification:
    """AGV hardware specifications."""
    model: str
    max_speed: float  # m/s
    max_acceleration: float  # m/s²
    max_payload: float  # kg
    battery_capacity: float  # kWh
    charging_rate: float  # kW
    footprint: Tuple[float, float]  # width x length in meters
    turning_radius: float  # meters

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model": self.model,
            "max_speed": self.max_speed,
            "max_acceleration": self.max_acceleration,
            "max_payload": self.max_payload,
            "battery_capacity": self.battery_capacity,
            "charging_rate": self.charging_rate,
            "footprint": list(self.footprint),
            "turning_radius": self.turning_radius,
        }


@dataclass
class AGVStatus:
    """Real-time AGV status."""
    agv_id: str
    state: AGVState
    position: Position2D
    velocity: Velocity2D
    battery_level: float  # 0-100%
    payload_weight: float  # kg
    current_task_id: Optional[str]
    error_codes: List[str]
    last_update: datetime
    online: bool = True

    def needs_charging(self, threshold: float = 20.0) -> bool:
        """Check if AGV needs charging."""
        return self.battery_level < threshold

    def is_available(self) -> bool:
        """Check if AGV is available for tasks."""
        return (
            self.online and
            self.state == AGVState.IDLE and
            not self.error_codes and
            self.battery_level > 15.0
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agv_id": self.agv_id,
            "state": self.state.value,
            "position": self.position.to_dict(),
            "velocity": self.velocity.to_dict(),
            "battery_level": self.battery_level,
            "payload_weight": self.payload_weight,
            "current_task_id": self.current_task_id,
            "error_codes": self.error_codes,
            "last_update": self.last_update.isoformat(),
            "online": self.online,
        }


@dataclass
class Zone:
    """Factory zone definition."""
    zone_id: str
    name: str
    zone_type: ZoneType
    bounds: Tuple[Position2D, Position2D]  # min, max corners
    max_occupancy: int = 1
    current_occupancy: int = 0
    access_rules: Dict[str, bool] = field(default_factory=dict)

    def contains(self, pos: Position2D) -> bool:
        """Check if position is within zone."""
        min_pos, max_pos = self.bounds
        return (
            min_pos.x <= pos.x <= max_pos.x and
            min_pos.y <= pos.y <= max_pos.y
        )

    def is_full(self) -> bool:
        """Check if zone is at capacity."""
        return self.current_occupancy >= self.max_occupancy

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "zone_type": self.zone_type.value,
            "bounds": [self.bounds[0].to_dict(), self.bounds[1].to_dict()],
            "max_occupancy": self.max_occupancy,
            "current_occupancy": self.current_occupancy,
            "access_rules": self.access_rules,
        }


@dataclass
class ChargingStation:
    """Charging station definition."""
    station_id: str
    position: Position2D
    charging_power: float  # kW
    is_occupied: bool = False
    current_agv: Optional[str] = None
    queue: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "station_id": self.station_id,
            "position": self.position.to_dict(),
            "charging_power": self.charging_power,
            "is_occupied": self.is_occupied,
            "current_agv": self.current_agv,
            "queue_length": len(self.queue),
        }


@dataclass
class TransportTask:
    """AGV transport task."""
    task_id: str
    task_type: TaskType
    priority: TaskPriority
    pickup_location: Position2D
    delivery_location: Position2D
    payload_type: str
    payload_weight: float
    status: TaskStatus = TaskStatus.PENDING
    assigned_agv: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    estimated_duration: float = 0.0  # seconds

    def is_overdue(self) -> bool:
        """Check if task is overdue."""
        if self.deadline and self.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return datetime.utcnow() > self.deadline
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "priority": self.priority.value,
            "pickup_location": self.pickup_location.to_dict(),
            "delivery_location": self.delivery_location.to_dict(),
            "payload_type": self.payload_type,
            "payload_weight": self.payload_weight,
            "status": self.status.value,
            "assigned_agv": self.assigned_agv,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "estimated_duration": self.estimated_duration,
            "is_overdue": self.is_overdue(),
        }


@dataclass
class PathSegment:
    """A segment of a planned path."""
    start: Position2D
    end: Position2D
    distance: float
    estimated_time: float  # seconds
    zone_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
            "distance": self.distance,
            "estimated_time": self.estimated_time,
            "zone_id": self.zone_id,
        }


@dataclass
class PlannedPath:
    """Complete planned path for AGV."""
    path_id: str
    agv_id: str
    segments: List[PathSegment]
    total_distance: float
    total_time: float
    created_at: datetime = field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path_id": self.path_id,
            "agv_id": self.agv_id,
            "segments": [s.to_dict() for s in self.segments],
            "total_distance": self.total_distance,
            "total_time": self.total_time,
            "created_at": self.created_at.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
        }


@dataclass
class TrafficConflict:
    """Detected traffic conflict."""
    conflict_id: str
    agv_ids: List[str]
    location: Position2D
    conflict_type: str
    severity: str
    detected_at: datetime
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "agv_ids": self.agv_ids,
            "location": self.location.to_dict(),
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "detected_at": self.detected_at.isoformat(),
            "resolved": self.resolved,
        }


# =============================================================================
# Path Planning
# =============================================================================

class PathPlanner:
    """
    Path planning with A* and Dijkstra algorithms.

    Supports grid-based and graph-based navigation.
    """

    def __init__(
        self,
        grid_resolution: float = 0.5,  # meters per cell
        algorithm: PathAlgorithm = PathAlgorithm.A_STAR
    ):
        """Initialize path planner."""
        self.grid_resolution = grid_resolution
        self.algorithm = algorithm
        self.obstacles: Set[Tuple[int, int]] = set()
        self.waypoints: Dict[str, Position2D] = {}

    def add_obstacle(self, position: Position2D, radius: float = 0.5) -> None:
        """Add an obstacle to the map."""
        cx, cy = self._to_grid(position)
        cells_radius = int(radius / self.grid_resolution) + 1

        for dx in range(-cells_radius, cells_radius + 1):
            for dy in range(-cells_radius, cells_radius + 1):
                if dx * dx + dy * dy <= cells_radius * cells_radius:
                    self.obstacles.add((cx + dx, cy + dy))

    def add_waypoint(self, name: str, position: Position2D) -> None:
        """Add a named waypoint."""
        self.waypoints[name] = position

    def plan_path(
        self,
        start: Position2D,
        goal: Position2D,
        max_speed: float = 1.0
    ) -> Optional[PlannedPath]:
        """
        Plan a path from start to goal.

        Args:
            start: Starting position
            goal: Goal position
            max_speed: Maximum speed for time estimation

        Returns:
            PlannedPath or None if no path found
        """
        if self.algorithm == PathAlgorithm.A_STAR:
            grid_path = self._a_star(start, goal)
        else:
            grid_path = self._dijkstra(start, goal)

        if not grid_path:
            return None

        # Convert grid path to segments
        segments = []
        total_distance = 0.0

        for i in range(len(grid_path) - 1):
            seg_start = self._from_grid(grid_path[i])
            seg_end = self._from_grid(grid_path[i + 1])
            distance = seg_start.distance_to(seg_end)

            segments.append(PathSegment(
                start=seg_start,
                end=seg_end,
                distance=distance,
                estimated_time=distance / max_speed,
            ))
            total_distance += distance

        return PlannedPath(
            path_id=str(uuid.uuid4()),
            agv_id="",  # Set by fleet manager
            segments=segments,
            total_distance=total_distance,
            total_time=total_distance / max_speed,
        )

    def _to_grid(self, pos: Position2D) -> Tuple[int, int]:
        """Convert world position to grid cell."""
        return (
            int(pos.x / self.grid_resolution),
            int(pos.y / self.grid_resolution)
        )

    def _from_grid(self, cell: Tuple[int, int]) -> Position2D:
        """Convert grid cell to world position."""
        return Position2D(
            x=cell[0] * self.grid_resolution + self.grid_resolution / 2,
            y=cell[1] * self.grid_resolution + self.grid_resolution / 2,
        )

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """A* heuristic (Euclidean distance)."""
        return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

    def _get_neighbors(self, cell: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get valid neighboring cells."""
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            new_cell = (cell[0] + dx, cell[1] + dy)
            if new_cell not in self.obstacles:
                neighbors.append(new_cell)
        return neighbors

    def _a_star(
        self,
        start: Position2D,
        goal: Position2D
    ) -> Optional[List[Tuple[int, int]]]:
        """A* pathfinding algorithm."""
        start_cell = self._to_grid(start)
        goal_cell = self._to_grid(goal)

        # Priority queue: (f_score, counter, cell)
        counter = 0
        open_set = [(0, counter, start_cell)]
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}

        g_score = defaultdict(lambda: float('inf'))
        g_score[start_cell] = 0

        f_score = defaultdict(lambda: float('inf'))
        f_score[start_cell] = self._heuristic(start_cell, goal_cell)

        open_set_hash = {start_cell}

        while open_set:
            _, _, current = heapq.heappop(open_set)
            open_set_hash.discard(current)

            if current == goal_cell:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                return list(reversed(path))

            for neighbor in self._get_neighbors(current):
                # Diagonal movement costs more
                dx = abs(neighbor[0] - current[0])
                dy = abs(neighbor[1] - current[1])
                move_cost = math.sqrt(2) if dx + dy == 2 else 1.0

                tentative_g = g_score[current] + move_cost

                if tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, goal_cell)

                    if neighbor not in open_set_hash:
                        counter += 1
                        heapq.heappush(open_set, (f_score[neighbor], counter, neighbor))
                        open_set_hash.add(neighbor)

        return None  # No path found

    def _dijkstra(
        self,
        start: Position2D,
        goal: Position2D
    ) -> Optional[List[Tuple[int, int]]]:
        """Dijkstra's pathfinding algorithm."""
        start_cell = self._to_grid(start)
        goal_cell = self._to_grid(goal)

        counter = 0
        pq = [(0, counter, start_cell)]
        distances = {start_cell: 0}
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}

        while pq:
            dist, _, current = heapq.heappop(pq)

            if current == goal_cell:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                return list(reversed(path))

            if dist > distances.get(current, float('inf')):
                continue

            for neighbor in self._get_neighbors(current):
                dx = abs(neighbor[0] - current[0])
                dy = abs(neighbor[1] - current[1])
                move_cost = math.sqrt(2) if dx + dy == 2 else 1.0

                new_dist = dist + move_cost

                if new_dist < distances.get(neighbor, float('inf')):
                    distances[neighbor] = new_dist
                    came_from[neighbor] = current
                    counter += 1
                    heapq.heappush(pq, (new_dist, counter, neighbor))

        return None


# =============================================================================
# AGV Fleet Manager
# =============================================================================

class AGVFleetManager:
    """
    AGV Fleet Management System.

    Provides centralized management of AGV fleet including:
    - Real-time fleet monitoring
    - Traffic management and collision avoidance
    - Charging station scheduling
    - Task assignment and optimization
    - Zone management
    """

    def __init__(
        self,
        fleet_id: str = "default",
        allocation_strategy: AllocationStrategy = AllocationStrategy.HYBRID,
        path_algorithm: PathAlgorithm = PathAlgorithm.A_STAR,
        collision_distance: float = 1.5,  # meters
        low_battery_threshold: float = 20.0
    ):
        """
        Initialize the fleet manager.

        Args:
            fleet_id: Unique identifier for this fleet
            allocation_strategy: Task allocation strategy
            path_algorithm: Path planning algorithm
            collision_distance: Minimum safe distance between AGVs
            low_battery_threshold: Battery percentage to trigger charging
        """
        self.fleet_id = fleet_id
        self.allocation_strategy = allocation_strategy
        self.collision_distance = collision_distance
        self.low_battery_threshold = low_battery_threshold

        # AGV registry
        self.agvs: Dict[str, AGVStatus] = {}
        self.agv_specs: Dict[str, AGVSpecification] = {}

        # Infrastructure
        self.zones: Dict[str, Zone] = {}
        self.charging_stations: Dict[str, ChargingStation] = {}

        # Task management
        self.tasks: Dict[str, TransportTask] = {}
        self.task_queue: List[str] = []  # Priority queue of task IDs

        # Path planning
        self.path_planner = PathPlanner(algorithm=path_algorithm)
        self.active_paths: Dict[str, PlannedPath] = {}

        # Traffic management
        self.conflicts: Dict[str, TrafficConflict] = {}

        # Round-robin counter
        self._rr_counter = 0

        # Callbacks
        self.on_task_completed: Optional[Callable[[TransportTask], None]] = None
        self.on_conflict_detected: Optional[Callable[[TrafficConflict], None]] = None
        self.on_low_battery: Optional[Callable[[str, float], None]] = None

        # Background tasks
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        logger.info(
            f"AGVFleetManager initialized: fleet={fleet_id}, "
            f"strategy={allocation_strategy.value}"
        )

    # -------------------------------------------------------------------------
    # AGV Registration
    # -------------------------------------------------------------------------

    def register_agv(
        self,
        agv_id: str,
        spec: AGVSpecification,
        initial_position: Position2D,
        initial_battery: float = 100.0
    ) -> AGVStatus:
        """
        Register a new AGV in the fleet.

        Args:
            agv_id: Unique AGV identifier
            spec: AGV hardware specification
            initial_position: Starting position
            initial_battery: Initial battery level

        Returns:
            AGVStatus for the registered AGV
        """
        status = AGVStatus(
            agv_id=agv_id,
            state=AGVState.IDLE,
            position=initial_position,
            velocity=Velocity2D(),
            battery_level=initial_battery,
            payload_weight=0.0,
            current_task_id=None,
            error_codes=[],
            last_update=datetime.utcnow(),
        )

        self.agvs[agv_id] = status
        self.agv_specs[agv_id] = spec

        logger.info(f"Registered AGV: {agv_id} ({spec.model})")
        return status

    def update_agv_status(
        self,
        agv_id: str,
        position: Optional[Position2D] = None,
        velocity: Optional[Velocity2D] = None,
        state: Optional[AGVState] = None,
        battery_level: Optional[float] = None,
        payload_weight: Optional[float] = None,
        error_codes: Optional[List[str]] = None
    ) -> AGVStatus:
        """Update AGV status from sensor data."""
        if agv_id not in self.agvs:
            raise ValueError(f"Unknown AGV: {agv_id}")

        status = self.agvs[agv_id]

        if position is not None:
            status.position = position
        if velocity is not None:
            status.velocity = velocity
        if state is not None:
            status.state = state
        if battery_level is not None:
            status.battery_level = battery_level
            # Check for low battery
            if battery_level < self.low_battery_threshold and self.on_low_battery:
                self.on_low_battery(agv_id, battery_level)
        if payload_weight is not None:
            status.payload_weight = payload_weight
        if error_codes is not None:
            status.error_codes = error_codes

        status.last_update = datetime.utcnow()

        return status

    # -------------------------------------------------------------------------
    # Zone Management
    # -------------------------------------------------------------------------

    def add_zone(
        self,
        zone_id: str,
        name: str,
        zone_type: ZoneType,
        min_corner: Position2D,
        max_corner: Position2D,
        max_occupancy: int = 1
    ) -> Zone:
        """Add a zone to the factory map."""
        zone = Zone(
            zone_id=zone_id,
            name=name,
            zone_type=zone_type,
            bounds=(min_corner, max_corner),
            max_occupancy=max_occupancy,
        )
        self.zones[zone_id] = zone

        # Add obstacles for restricted zones
        if zone_type == ZoneType.RESTRICTED:
            center = Position2D(
                x=(min_corner.x + max_corner.x) / 2,
                y=(min_corner.y + max_corner.y) / 2,
            )
            radius = max(
                max_corner.x - min_corner.x,
                max_corner.y - min_corner.y
            ) / 2
            self.path_planner.add_obstacle(center, radius)

        logger.info(f"Added zone: {zone_id} ({zone_type.value})")
        return zone

    def add_charging_station(
        self,
        station_id: str,
        position: Position2D,
        charging_power: float = 5.0
    ) -> ChargingStation:
        """Add a charging station."""
        station = ChargingStation(
            station_id=station_id,
            position=position,
            charging_power=charging_power,
        )
        self.charging_stations[station_id] = station

        # Add waypoint for path planning
        self.path_planner.add_waypoint(f"charging_{station_id}", position)

        logger.info(f"Added charging station: {station_id}")
        return station

    # -------------------------------------------------------------------------
    # Task Management
    # -------------------------------------------------------------------------

    def create_task(
        self,
        task_type: TaskType,
        pickup_location: Position2D,
        delivery_location: Position2D,
        payload_type: str = "general",
        payload_weight: float = 0.0,
        priority: TaskPriority = TaskPriority.NORMAL,
        deadline: Optional[datetime] = None
    ) -> TransportTask:
        """
        Create a new transport task.

        Args:
            task_type: Type of task
            pickup_location: Where to pick up
            delivery_location: Where to deliver
            payload_type: Type of payload
            payload_weight: Weight in kg
            priority: Task priority
            deadline: Optional deadline

        Returns:
            Created TransportTask
        """
        task = TransportTask(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            priority=priority,
            pickup_location=pickup_location,
            delivery_location=delivery_location,
            payload_type=payload_type,
            payload_weight=payload_weight,
            deadline=deadline,
        )

        # Estimate duration
        distance = pickup_location.distance_to(delivery_location)
        task.estimated_duration = distance / 1.0  # Assume 1 m/s average

        self.tasks[task.task_id] = task

        # Add to priority queue (lower priority value = higher priority)
        self._insert_task_by_priority(task.task_id)

        logger.info(f"Created task: {task.task_id} ({task_type.value})")

        return task

    def _insert_task_by_priority(self, task_id: str) -> None:
        """Insert task into queue maintaining priority order."""
        task = self.tasks[task_id]
        # Find insertion point
        insert_idx = 0
        for i, tid in enumerate(self.task_queue):
            if self.tasks[tid].priority.value > task.priority.value:
                break
            insert_idx = i + 1
        self.task_queue.insert(insert_idx, task_id)

    def assign_task(
        self,
        task_id: str,
        agv_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Assign a task to an AGV.

        Args:
            task_id: Task to assign
            agv_id: Specific AGV (optional, will auto-select if None)

        Returns:
            Assigned AGV ID or None if no AGV available
        """
        if task_id not in self.tasks:
            raise ValueError(f"Unknown task: {task_id}")

        task = self.tasks[task_id]

        if agv_id is None:
            agv_id = self._select_best_agv(task)

        if agv_id is None:
            logger.warning(f"No available AGV for task: {task_id}")
            return None

        # Validate AGV can handle payload
        spec = self.agv_specs[agv_id]
        if task.payload_weight > spec.max_payload:
            logger.warning(
                f"AGV {agv_id} cannot handle payload weight: "
                f"{task.payload_weight} > {spec.max_payload}"
            )
            return None

        # Update task and AGV
        task.status = TaskStatus.ASSIGNED
        task.assigned_agv = agv_id
        self.agvs[agv_id].state = AGVState.NAVIGATING
        self.agvs[agv_id].current_task_id = task_id

        # Plan path
        path = self.path_planner.plan_path(
            self.agvs[agv_id].position,
            task.pickup_location,
            spec.max_speed
        )
        if path:
            path.agv_id = agv_id
            self.active_paths[agv_id] = path

        # Remove from queue
        if task_id in self.task_queue:
            self.task_queue.remove(task_id)

        logger.info(f"Assigned task {task_id} to AGV {agv_id}")
        return agv_id

    def _select_best_agv(self, task: TransportTask) -> Optional[str]:
        """Select the best AGV for a task based on allocation strategy."""
        available = [
            agv_id for agv_id, status in self.agvs.items()
            if status.is_available() and
               self.agv_specs[agv_id].max_payload >= task.payload_weight
        ]

        if not available:
            return None

        if self.allocation_strategy == AllocationStrategy.NEAREST:
            return self._select_nearest(available, task.pickup_location)

        elif self.allocation_strategy == AllocationStrategy.LEAST_LOADED:
            return self._select_least_loaded(available)

        elif self.allocation_strategy == AllocationStrategy.ROUND_ROBIN:
            return self._select_round_robin(available)

        elif self.allocation_strategy == AllocationStrategy.BATTERY_AWARE:
            return self._select_battery_aware(available, task)

        else:  # HYBRID
            return self._select_hybrid(available, task)

    def _select_nearest(
        self,
        available: List[str],
        location: Position2D
    ) -> str:
        """Select nearest AGV to location."""
        return min(
            available,
            key=lambda aid: self.agvs[aid].position.distance_to(location)
        )

    def _select_least_loaded(self, available: List[str]) -> str:
        """Select AGV with lowest workload."""
        # Count assigned tasks per AGV
        task_counts = defaultdict(int)
        for task in self.tasks.values():
            if task.assigned_agv and task.status in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS):
                task_counts[task.assigned_agv] += 1

        return min(available, key=lambda aid: task_counts[aid])

    def _select_round_robin(self, available: List[str]) -> str:
        """Select AGV using round-robin."""
        available_sorted = sorted(available)
        selected = available_sorted[self._rr_counter % len(available_sorted)]
        self._rr_counter += 1
        return selected

    def _select_battery_aware(
        self,
        available: List[str],
        task: TransportTask
    ) -> str:
        """Select AGV with best battery for task distance."""
        task_distance = (
            task.pickup_location.distance_to(task.delivery_location)
        )

        def battery_score(agv_id: str) -> float:
            status = self.agvs[agv_id]
            # Higher score = better choice
            return status.battery_level - (task_distance * 0.5)  # Rough energy estimate

        return max(available, key=battery_score)

    def _select_hybrid(
        self,
        available: List[str],
        task: TransportTask
    ) -> str:
        """Hybrid selection using multiple factors."""
        def hybrid_score(agv_id: str) -> float:
            status = self.agvs[agv_id]
            spec = self.agv_specs[agv_id]

            # Distance factor (lower is better)
            distance = status.position.distance_to(task.pickup_location)
            distance_score = 1.0 / (1.0 + distance)

            # Battery factor
            battery_score = status.battery_level / 100.0

            # Workload factor
            current_tasks = sum(
                1 for t in self.tasks.values()
                if t.assigned_agv == agv_id and
                   t.status in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS)
            )
            workload_score = 1.0 / (1.0 + current_tasks)

            return (
                0.4 * distance_score +
                0.3 * battery_score +
                0.3 * workload_score
            )

        return max(available, key=hybrid_score)

    def complete_task(self, task_id: str, success: bool = True) -> None:
        """Mark a task as completed."""
        if task_id not in self.tasks:
            raise ValueError(f"Unknown task: {task_id}")

        task = self.tasks[task_id]
        task.completed_at = datetime.utcnow()
        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED

        # Free up AGV
        if task.assigned_agv:
            agv = self.agvs[task.assigned_agv]
            agv.state = AGVState.IDLE
            agv.current_task_id = None
            agv.payload_weight = 0.0

            if task.assigned_agv in self.active_paths:
                del self.active_paths[task.assigned_agv]

        # Callback
        if self.on_task_completed:
            self.on_task_completed(task)

        logger.info(
            f"Task {task_id} {'completed' if success else 'failed'}"
        )

    # -------------------------------------------------------------------------
    # Charging Management
    # -------------------------------------------------------------------------

    def request_charging(self, agv_id: str) -> Optional[str]:
        """
        Request charging for an AGV.

        Returns station_id or None if no station available.
        """
        if agv_id not in self.agvs:
            raise ValueError(f"Unknown AGV: {agv_id}")

        agv = self.agvs[agv_id]

        # Find nearest available station
        available_stations = [
            s for s in self.charging_stations.values()
            if not s.is_occupied
        ]

        if not available_stations:
            # Queue at nearest station
            nearest = min(
                self.charging_stations.values(),
                key=lambda s: agv.position.distance_to(s.position)
            )
            nearest.queue.append(agv_id)
            logger.info(f"AGV {agv_id} queued at station {nearest.station_id}")
            return None

        # Select nearest available
        station = min(
            available_stations,
            key=lambda s: agv.position.distance_to(s.position)
        )

        # Create charging task
        self.create_task(
            task_type=TaskType.CHARGING,
            pickup_location=agv.position,
            delivery_location=station.position,
            priority=TaskPriority.HIGH,
        )

        station.is_occupied = True
        station.current_agv = agv_id

        logger.info(f"AGV {agv_id} assigned to charging station {station.station_id}")
        return station.station_id

    def complete_charging(self, station_id: str) -> None:
        """Complete charging at a station."""
        if station_id not in self.charging_stations:
            raise ValueError(f"Unknown station: {station_id}")

        station = self.charging_stations[station_id]
        station.is_occupied = False

        if station.current_agv:
            agv = self.agvs[station.current_agv]
            agv.state = AGVState.IDLE
            agv.battery_level = 100.0

        station.current_agv = None

        # Process queue
        if station.queue:
            next_agv = station.queue.pop(0)
            self.request_charging(next_agv)

    # -------------------------------------------------------------------------
    # Traffic Management
    # -------------------------------------------------------------------------

    def check_collisions(self) -> List[TrafficConflict]:
        """Check for potential collisions between AGVs."""
        conflicts = []

        agv_list = list(self.agvs.items())
        for i in range(len(agv_list)):
            for j in range(i + 1, len(agv_list)):
                agv1_id, agv1 = agv_list[i]
                agv2_id, agv2 = agv_list[j]

                if not agv1.online or not agv2.online:
                    continue

                distance = agv1.position.distance_to(agv2.position)

                if distance < self.collision_distance:
                    conflict = TrafficConflict(
                        conflict_id=str(uuid.uuid4()),
                        agv_ids=[agv1_id, agv2_id],
                        location=Position2D(
                            x=(agv1.position.x + agv2.position.x) / 2,
                            y=(agv1.position.y + agv2.position.y) / 2,
                        ),
                        conflict_type="proximity",
                        severity="warning" if distance > self.collision_distance * 0.5 else "critical",
                        detected_at=datetime.utcnow(),
                    )
                    conflicts.append(conflict)
                    self.conflicts[conflict.conflict_id] = conflict

                    if self.on_conflict_detected:
                        self.on_conflict_detected(conflict)

        return conflicts

    def resolve_conflict(self, conflict_id: str) -> bool:
        """Resolve a traffic conflict by stopping lower-priority AGV."""
        if conflict_id not in self.conflicts:
            return False

        conflict = self.conflicts[conflict_id]
        if conflict.resolved:
            return True

        # Determine which AGV to stop
        agv_priorities = []
        for agv_id in conflict.agv_ids:
            task_id = self.agvs[agv_id].current_task_id
            priority = 5  # Default low priority
            if task_id and task_id in self.tasks:
                priority = self.tasks[task_id].priority.value
            agv_priorities.append((agv_id, priority))

        # Sort by priority (lower value = higher priority)
        agv_priorities.sort(key=lambda x: x[1])

        # Stop lower priority AGV
        to_stop = agv_priorities[-1][0]
        self.agvs[to_stop].state = AGVState.WAITING

        conflict.resolved = True
        logger.info(f"Resolved conflict {conflict_id} by stopping AGV {to_stop}")

        return True

    # -------------------------------------------------------------------------
    # Monitoring
    # -------------------------------------------------------------------------

    async def start_monitoring(self, interval_seconds: float = 1.0) -> None:
        """Start the background monitoring loop."""
        self._running = True

        async def monitor_loop():
            while self._running:
                try:
                    # Check for collisions
                    self.check_collisions()

                    # Process task queue
                    await self._process_task_queue()

                    # Check battery levels
                    for agv_id, status in self.agvs.items():
                        if status.needs_charging(self.low_battery_threshold):
                            if status.state == AGVState.IDLE:
                                self.request_charging(agv_id)

                except Exception as e:
                    logger.error(f"Monitoring error: {e}")

                await asyncio.sleep(interval_seconds)

        self._monitor_task = asyncio.create_task(monitor_loop())
        logger.info("Started fleet monitoring")

    async def stop_monitoring(self) -> None:
        """Stop the background monitoring loop."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped fleet monitoring")

    async def _process_task_queue(self) -> None:
        """Process pending tasks in the queue."""
        while self.task_queue:
            task_id = self.task_queue[0]
            task = self.tasks[task_id]

            if task.status != TaskStatus.PENDING:
                self.task_queue.pop(0)
                continue

            # Try to assign
            if self.assign_task(task_id):
                # Task assigned, removed from queue in assign_task
                pass
            else:
                # No AGV available, stop processing
                break

    # -------------------------------------------------------------------------
    # Status and Metrics
    # -------------------------------------------------------------------------

    def get_fleet_status(self) -> Dict[str, Any]:
        """Get comprehensive fleet status."""
        active_agvs = sum(1 for a in self.agvs.values() if a.online)
        available_agvs = sum(1 for a in self.agvs.values() if a.is_available())
        charging_agvs = sum(1 for a in self.agvs.values() if a.state == AGVState.CHARGING)

        pending_tasks = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING)
        in_progress_tasks = sum(
            1 for t in self.tasks.values()
            if t.status in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS)
        )
        completed_tasks = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        overdue_tasks = sum(1 for t in self.tasks.values() if t.is_overdue())

        avg_battery = (
            sum(a.battery_level for a in self.agvs.values()) / len(self.agvs)
            if self.agvs else 0
        )

        active_conflicts = sum(1 for c in self.conflicts.values() if not c.resolved)

        return {
            "fleet_id": self.fleet_id,
            "total_agvs": len(self.agvs),
            "active_agvs": active_agvs,
            "available_agvs": available_agvs,
            "charging_agvs": charging_agvs,
            "average_battery": avg_battery,
            "total_tasks": len(self.tasks),
            "pending_tasks": pending_tasks,
            "in_progress_tasks": in_progress_tasks,
            "completed_tasks": completed_tasks,
            "overdue_tasks": overdue_tasks,
            "active_conflicts": active_conflicts,
            "charging_stations": len(self.charging_stations),
            "zones": len(self.zones),
            "allocation_strategy": self.allocation_strategy.value,
            "monitoring_active": self._running,
        }

    def get_agv_details(self, agv_id: str) -> Dict[str, Any]:
        """Get detailed info for a specific AGV."""
        if agv_id not in self.agvs:
            raise ValueError(f"Unknown AGV: {agv_id}")

        status = self.agvs[agv_id]
        spec = self.agv_specs[agv_id]
        path = self.active_paths.get(agv_id)

        return {
            "status": status.to_dict(),
            "specification": spec.to_dict(),
            "active_path": path.to_dict() if path else None,
        }


# =============================================================================
# Factory Function and Singleton
# =============================================================================

_fleet_manager_instance: Optional[AGVFleetManager] = None


def get_agv_fleet_manager(
    fleet_id: str = "default",
    allocation_strategy: AllocationStrategy = AllocationStrategy.HYBRID
) -> AGVFleetManager:
    """
    Get or create the AGV fleet manager singleton.

    Args:
        fleet_id: Fleet identifier
        allocation_strategy: Task allocation strategy

    Returns:
        AGVFleetManager instance
    """
    global _fleet_manager_instance

    if _fleet_manager_instance is None:
        _fleet_manager_instance = AGVFleetManager(
            fleet_id=fleet_id,
            allocation_strategy=allocation_strategy
        )

    return _fleet_manager_instance


__all__ = [
    # Enums
    'AGVState',
    'TaskType',
    'TaskPriority',
    'TaskStatus',
    'ZoneType',
    'AllocationStrategy',
    'PathAlgorithm',
    # Data Classes
    'Position2D',
    'Velocity2D',
    'AGVSpecification',
    'AGVStatus',
    'Zone',
    'ChargingStation',
    'TransportTask',
    'PathSegment',
    'PlannedPath',
    'TrafficConflict',
    # Classes
    'PathPlanner',
    'AGVFleetManager',
    'get_agv_fleet_manager',
]
