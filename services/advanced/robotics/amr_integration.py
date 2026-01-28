"""
Autonomous Mobile Robot (AMR) Integration Service.

Implements fleet management and integration for autonomous mobile
robots and automated guided vehicles (AGVs) in manufacturing:
- Fleet orchestration and dispatch
- Path planning and traffic management
- Zone-based access control
- Task assignment and optimization
- Battery and charging management
- Safety interlock integration
- Integration with WMS/MES systems

Compliant with:
- ISO 3691-4 (Industrial Trucks - Driverless)
- ANSI/RIA R15.08 (Industrial Mobile Robots)
- IEC 62443 (Cybersecurity for Industrial Automation)
- ISO 13482 (Personal Care Robots - Safety)
"""

import asyncio
import heapq
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
import logging
import math

logger = logging.getLogger(__name__)


class RobotType(Enum):
    """Types of autonomous mobile robots."""
    AGV = "automated_guided_vehicle"  # Fixed path following
    AMR = "autonomous_mobile_robot"  # Free navigation
    COBOT = "collaborative_robot"  # Human collaboration
    FORKLIFT = "autonomous_forklift"  # Heavy lifting
    TUGGER = "autonomous_tugger"  # Trailer/cart pulling
    PICKING = "picking_robot"  # Item picking/sorting
    CLEANING = "cleaning_robot"  # Floor cleaning


class RobotState(Enum):
    """Robot operational states."""
    IDLE = "idle"
    NAVIGATING = "navigating"
    LOADING = "loading"
    UNLOADING = "unloading"
    CHARGING = "charging"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"
    WAITING = "waiting"  # Traffic/obstruction


class TaskType(Enum):
    """Types of robot tasks."""
    TRANSPORT = "transport"  # Point-to-point material transport
    PICK = "pick"  # Pick items
    DELIVER = "deliver"  # Delivery to station
    CHARGE = "charge"  # Go to charging station
    PATROL = "patrol"  # Security/inspection patrol
    CLEAN = "clean"  # Cleaning task
    RETURN_HOME = "return_home"  # Return to home position


class TaskPriority(Enum):
    """Task priority levels."""
    EMERGENCY = 1
    CRITICAL = 2
    HIGH = 3
    NORMAL = 4
    LOW = 5


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ZoneType(Enum):
    """Types of zones in facility."""
    PRODUCTION = "production"
    WAREHOUSE = "warehouse"
    STAGING = "staging"
    SHIPPING = "shipping"
    RECEIVING = "receiving"
    CHARGING = "charging"
    MAINTENANCE = "maintenance"
    RESTRICTED = "restricted"
    PEDESTRIAN = "pedestrian"
    CROSSWALK = "crosswalk"


@dataclass
class Position:
    """2D position in facility coordinate system."""
    x: float  # meters
    y: float  # meters
    theta: float = 0.0  # orientation in radians


@dataclass
class Velocity:
    """Robot velocity."""
    linear: float = 0.0  # m/s
    angular: float = 0.0  # rad/s


@dataclass
class Zone:
    """Facility zone definition."""
    zone_id: str
    zone_name: str
    zone_type: ZoneType
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    max_robots: int = 5
    speed_limit: float = 1.0  # m/s
    access_required: List[str] = field(default_factory=list)  # Robot types allowed
    is_active: bool = True


@dataclass
class Waypoint:
    """Navigation waypoint."""
    waypoint_id: str
    name: str
    position: Position
    zone_id: str
    is_charging_station: bool = False
    is_pick_location: bool = False
    is_drop_location: bool = False
    docking_required: bool = False


@dataclass
class PathSegment:
    """Segment of navigation path."""
    start_waypoint: str
    end_waypoint: str
    distance: float  # meters
    travel_time: float  # seconds at normal speed
    is_bidirectional: bool = True
    max_speed: float = 1.0  # m/s
    is_blocked: bool = False


@dataclass
class Robot:
    """Autonomous mobile robot."""
    robot_id: str
    robot_name: str
    robot_type: RobotType
    state: RobotState
    position: Position
    velocity: Velocity
    battery_percent: float
    max_payload_kg: float
    current_payload_kg: float = 0.0
    current_task_id: Optional[str] = None
    current_path: List[str] = field(default_factory=list)  # Waypoint IDs
    path_index: int = 0
    home_waypoint: Optional[str] = None
    allowed_zones: List[str] = field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    last_heartbeat: datetime = field(default_factory=datetime.now)
    registered_at: datetime = field(default_factory=datetime.now)
    total_distance_m: float = 0.0
    total_tasks_completed: int = 0
    maintenance_due: Optional[datetime] = None


@dataclass
class Task:
    """Robot task definition."""
    task_id: str
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    source_waypoint: str
    destination_waypoint: str
    payload_description: Optional[str] = None
    payload_weight_kg: float = 0.0
    assigned_robot: Optional[str] = None
    requested_by: str = ""
    requested_at: datetime = field(default_factory=datetime.now)
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    notes: str = ""


@dataclass
class TrafficControl:
    """Traffic control rule."""
    rule_id: str
    zone_id: str
    rule_type: str  # one_way, priority, mutex
    direction: Optional[str] = None  # For one-way
    priority_robot_types: List[RobotType] = field(default_factory=list)
    active: bool = True


@dataclass
class ChargingStation:
    """Robot charging station."""
    station_id: str
    waypoint_id: str
    station_name: str
    power_kw: float
    is_available: bool = True
    current_robot: Optional[str] = None
    compatible_types: List[RobotType] = field(default_factory=list)


@dataclass
class SafetyEvent:
    """Safety-related event."""
    event_id: str
    event_type: str  # collision_avoid, e_stop, obstacle_detect
    robot_id: str
    timestamp: datetime
    position: Position
    description: str
    severity: str = "low"  # low, medium, high, critical


class AMRIntegrationService:
    """
    Autonomous Mobile Robot fleet management service.

    Provides complete AMR integration including dispatch,
    path planning, traffic management, and safety systems.
    """

    def __init__(self):
        self.robots: Dict[str, Robot] = {}
        self.tasks: Dict[str, Task] = {}
        self.zones: Dict[str, Zone] = {}
        self.waypoints: Dict[str, Waypoint] = {}
        self.path_graph: Dict[str, List[PathSegment]] = {}  # waypoint_id -> segments
        self.charging_stations: Dict[str, ChargingStation] = {}
        self.traffic_rules: Dict[str, TrafficControl] = {}
        self.safety_events: List[SafetyEvent] = []
        self._task_queue: List[Tuple[int, str]] = []  # (priority, task_id) heap
        self._zone_occupancy: Dict[str, Set[str]] = {}  # zone_id -> robot_ids

    def _generate_id(self, prefix: str = "AMR") -> str:
        """Generate unique identifier."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{timestamp}-{unique}"

    # =========================================================================
    # Zone and Map Management
    # =========================================================================

    async def create_zone(
        self,
        zone_name: str,
        zone_type: ZoneType,
        x_min: float,
        y_min: float,
        x_max: float,
        y_max: float,
        max_robots: int = 5,
        speed_limit: float = 1.0
    ) -> Zone:
        """
        Create a facility zone.

        Zones define areas with specific access and speed rules.
        """
        zone_id = self._generate_id("ZONE")

        zone = Zone(
            zone_id=zone_id,
            zone_name=zone_name,
            zone_type=zone_type,
            x_min=x_min,
            y_min=y_min,
            x_max=x_max,
            y_max=y_max,
            max_robots=max_robots,
            speed_limit=speed_limit
        )

        self.zones[zone_id] = zone
        self._zone_occupancy[zone_id] = set()

        logger.info(f"Created zone: {zone_name} ({zone_type.value})")

        return zone

    async def create_waypoint(
        self,
        name: str,
        x: float,
        y: float,
        theta: float = 0.0,
        zone_id: str = None,
        is_charging_station: bool = False,
        is_pick_location: bool = False,
        is_drop_location: bool = False
    ) -> Waypoint:
        """Create a navigation waypoint."""
        waypoint_id = self._generate_id("WP")

        # Auto-detect zone if not specified
        if not zone_id:
            for z in self.zones.values():
                if z.x_min <= x <= z.x_max and z.y_min <= y <= z.y_max:
                    zone_id = z.zone_id
                    break

        waypoint = Waypoint(
            waypoint_id=waypoint_id,
            name=name,
            position=Position(x=x, y=y, theta=theta),
            zone_id=zone_id or "",
            is_charging_station=is_charging_station,
            is_pick_location=is_pick_location,
            is_drop_location=is_drop_location
        )

        self.waypoints[waypoint_id] = waypoint
        self.path_graph[waypoint_id] = []

        logger.info(f"Created waypoint: {name} at ({x}, {y})")

        return waypoint

    async def connect_waypoints(
        self,
        waypoint_a: str,
        waypoint_b: str,
        is_bidirectional: bool = True,
        max_speed: float = 1.0
    ) -> PathSegment:
        """Create a path connection between waypoints."""
        if waypoint_a not in self.waypoints:
            raise ValueError(f"Waypoint not found: {waypoint_a}")
        if waypoint_b not in self.waypoints:
            raise ValueError(f"Waypoint not found: {waypoint_b}")

        wp_a = self.waypoints[waypoint_a]
        wp_b = self.waypoints[waypoint_b]

        # Calculate distance
        dx = wp_b.position.x - wp_a.position.x
        dy = wp_b.position.y - wp_a.position.y
        distance = math.sqrt(dx * dx + dy * dy)

        # Calculate travel time
        travel_time = distance / max_speed

        segment = PathSegment(
            start_waypoint=waypoint_a,
            end_waypoint=waypoint_b,
            distance=distance,
            travel_time=travel_time,
            is_bidirectional=is_bidirectional,
            max_speed=max_speed
        )

        self.path_graph[waypoint_a].append(segment)

        if is_bidirectional:
            reverse_segment = PathSegment(
                start_waypoint=waypoint_b,
                end_waypoint=waypoint_a,
                distance=distance,
                travel_time=travel_time,
                is_bidirectional=True,
                max_speed=max_speed
            )
            self.path_graph[waypoint_b].append(reverse_segment)

        return segment

    # =========================================================================
    # Robot Management
    # =========================================================================

    async def register_robot(
        self,
        robot_name: str,
        robot_type: RobotType,
        initial_position: Position,
        max_payload_kg: float,
        home_waypoint: str = None,
        allowed_zones: List[str] = None
    ) -> Robot:
        """
        Register a new robot in the fleet.

        Args:
            robot_name: Human-readable robot name
            robot_type: Type of robot
            initial_position: Starting position
            max_payload_kg: Maximum payload capacity
            home_waypoint: Home/return waypoint
            allowed_zones: List of zone IDs robot can access

        Returns:
            Registered Robot
        """
        robot_id = self._generate_id("ROB")

        robot = Robot(
            robot_id=robot_id,
            robot_name=robot_name,
            robot_type=robot_type,
            state=RobotState.IDLE,
            position=initial_position,
            velocity=Velocity(),
            battery_percent=100.0,
            max_payload_kg=max_payload_kg,
            home_waypoint=home_waypoint,
            allowed_zones=allowed_zones or list(self.zones.keys())
        )

        self.robots[robot_id] = robot

        # Update zone occupancy
        for zone_id, zone in self.zones.items():
            if self._is_position_in_zone(initial_position, zone):
                self._zone_occupancy[zone_id].add(robot_id)
                break

        logger.info(f"Registered robot: {robot_name} ({robot_type.value})")

        return robot

    async def update_robot_state(
        self,
        robot_id: str,
        position: Position = None,
        velocity: Velocity = None,
        battery_percent: float = None,
        state: RobotState = None,
        current_payload_kg: float = None
    ) -> Robot:
        """Update robot telemetry data."""
        if robot_id not in self.robots:
            raise ValueError(f"Robot not found: {robot_id}")

        robot = self.robots[robot_id]
        robot.last_heartbeat = datetime.now()

        if position:
            # Track distance traveled
            dx = position.x - robot.position.x
            dy = position.y - robot.position.y
            distance = math.sqrt(dx * dx + dy * dy)
            robot.total_distance_m += distance

            # Update zone occupancy
            old_zone = self._get_robot_zone(robot.position)
            new_zone = self._get_robot_zone(position)

            if old_zone != new_zone:
                if old_zone:
                    self._zone_occupancy[old_zone].discard(robot_id)
                if new_zone:
                    self._zone_occupancy[new_zone].add(robot_id)

            robot.position = position

        if velocity:
            robot.velocity = velocity
        if battery_percent is not None:
            robot.battery_percent = battery_percent
        if state:
            robot.state = state
        if current_payload_kg is not None:
            robot.current_payload_kg = current_payload_kg

        return robot

    def _is_position_in_zone(self, position: Position, zone: Zone) -> bool:
        """Check if position is within zone bounds."""
        return (zone.x_min <= position.x <= zone.x_max and
                zone.y_min <= position.y <= zone.y_max)

    def _get_robot_zone(self, position: Position) -> Optional[str]:
        """Get zone containing position."""
        for zone_id, zone in self.zones.items():
            if self._is_position_in_zone(position, zone):
                return zone_id
        return None

    async def report_error(
        self,
        robot_id: str,
        error_code: str,
        error_message: str
    ) -> Robot:
        """Report a robot error."""
        if robot_id not in self.robots:
            raise ValueError(f"Robot not found: {robot_id}")

        robot = self.robots[robot_id]
        robot.state = RobotState.ERROR
        robot.error_code = error_code
        robot.error_message = error_message

        logger.error(f"Robot {robot.robot_name} error: {error_code} - {error_message}")

        return robot

    async def clear_error(
        self,
        robot_id: str,
        cleared_by: str
    ) -> Robot:
        """Clear robot error state."""
        if robot_id not in self.robots:
            raise ValueError(f"Robot not found: {robot_id}")

        robot = self.robots[robot_id]
        robot.error_code = None
        robot.error_message = None
        robot.state = RobotState.IDLE

        logger.info(f"Robot {robot.robot_name} error cleared by {cleared_by}")

        return robot

    async def trigger_emergency_stop(
        self,
        robot_id: str = None,
        reason: str = "manual_trigger"
    ) -> List[Robot]:
        """
        Trigger emergency stop.

        Args:
            robot_id: Specific robot to stop, or None for all
            reason: Reason for e-stop

        Returns:
            List of affected robots
        """
        affected = []

        targets = [robot_id] if robot_id else list(self.robots.keys())

        for rid in targets:
            if rid in self.robots:
                robot = self.robots[rid]
                robot.state = RobotState.EMERGENCY_STOP
                robot.velocity = Velocity()  # Zero velocity
                affected.append(robot)

                # Log safety event
                self.safety_events.append(SafetyEvent(
                    event_id=self._generate_id("SAF"),
                    event_type="e_stop",
                    robot_id=rid,
                    timestamp=datetime.now(),
                    position=robot.position,
                    description=reason,
                    severity="critical"
                ))

        logger.warning(f"Emergency stop triggered: {len(affected)} robots stopped")

        return affected

    async def release_emergency_stop(
        self,
        robot_id: str = None,
        released_by: str = ""
    ) -> List[Robot]:
        """Release emergency stop."""
        released = []

        targets = [robot_id] if robot_id else list(self.robots.keys())

        for rid in targets:
            if rid in self.robots:
                robot = self.robots[rid]
                if robot.state == RobotState.EMERGENCY_STOP:
                    robot.state = RobotState.IDLE
                    released.append(robot)

        logger.info(f"Emergency stop released for {len(released)} robots by {released_by}")

        return released

    # =========================================================================
    # Task Management
    # =========================================================================

    async def create_task(
        self,
        task_type: TaskType,
        source_waypoint: str,
        destination_waypoint: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        payload_description: str = None,
        payload_weight_kg: float = 0.0,
        requested_by: str = "",
        deadline: datetime = None
    ) -> Task:
        """
        Create a new robot task.

        Args:
            task_type: Type of task
            source_waypoint: Starting waypoint
            destination_waypoint: Target waypoint
            priority: Task priority
            payload_description: Description of payload
            payload_weight_kg: Payload weight
            requested_by: Requestor identifier
            deadline: Optional deadline

        Returns:
            Created Task
        """
        if source_waypoint not in self.waypoints:
            raise ValueError(f"Source waypoint not found: {source_waypoint}")
        if destination_waypoint not in self.waypoints:
            raise ValueError(f"Destination waypoint not found: {destination_waypoint}")

        task_id = self._generate_id("TASK")

        task = Task(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            status=TaskStatus.PENDING,
            source_waypoint=source_waypoint,
            destination_waypoint=destination_waypoint,
            payload_description=payload_description,
            payload_weight_kg=payload_weight_kg,
            requested_by=requested_by,
            deadline=deadline
        )

        self.tasks[task_id] = task

        # Add to priority queue
        heapq.heappush(self._task_queue, (priority.value, task_id))

        logger.info(f"Created task: {task_type.value} from {source_waypoint} to {destination_waypoint}")

        return task

    async def assign_task(
        self,
        task_id: str,
        robot_id: str = None
    ) -> Tuple[Task, Robot]:
        """
        Assign a task to a robot.

        If robot_id is None, automatically selects best available robot.
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task not found: {task_id}")

        task = self.tasks[task_id]

        if task.status != TaskStatus.PENDING:
            raise ValueError(f"Task not pending: {task.status}")

        # Auto-select robot if not specified
        if not robot_id:
            robot_id = await self._select_best_robot(task)

        if not robot_id:
            raise ValueError("No suitable robot available")

        if robot_id not in self.robots:
            raise ValueError(f"Robot not found: {robot_id}")

        robot = self.robots[robot_id]

        if robot.state not in [RobotState.IDLE, RobotState.WAITING]:
            raise ValueError(f"Robot not available: {robot.state}")

        if robot.max_payload_kg < task.payload_weight_kg:
            raise ValueError(f"Robot cannot carry payload: {task.payload_weight_kg}kg > {robot.max_payload_kg}kg")

        # Assign task
        task.status = TaskStatus.ASSIGNED
        task.assigned_robot = robot_id
        task.assigned_at = datetime.now()

        robot.current_task_id = task_id
        robot.state = RobotState.NAVIGATING

        # Calculate path
        path = await self._calculate_path(
            robot.position,
            task.source_waypoint,
            task.destination_waypoint
        )
        robot.current_path = path
        robot.path_index = 0

        logger.info(f"Assigned task {task_id} to robot {robot.robot_name}")

        return task, robot

    async def _select_best_robot(self, task: Task) -> Optional[str]:
        """Select best available robot for a task."""
        candidates = []

        source_wp = self.waypoints[task.source_waypoint]

        for robot_id, robot in self.robots.items():
            # Check availability
            if robot.state not in [RobotState.IDLE, RobotState.WAITING]:
                continue

            # Check payload capacity
            if robot.max_payload_kg < task.payload_weight_kg:
                continue

            # Check battery (need at least 20% for task)
            if robot.battery_percent < 20:
                continue

            # Check zone access
            if source_wp.zone_id and source_wp.zone_id not in robot.allowed_zones:
                continue

            # Calculate distance to source
            dx = source_wp.position.x - robot.position.x
            dy = source_wp.position.y - robot.position.y
            distance = math.sqrt(dx * dx + dy * dy)

            # Score: lower is better (distance + inverse battery)
            score = distance + (100 - robot.battery_percent) * 0.1

            candidates.append((score, robot_id))

        if not candidates:
            return None

        # Return robot with lowest score
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    async def _calculate_path(
        self,
        start_position: Position,
        source_waypoint: str,
        destination_waypoint: str
    ) -> List[str]:
        """
        Calculate path from current position through waypoints.

        Uses Dijkstra's algorithm for shortest path.
        """
        # Find nearest waypoint to start position
        nearest_start = None
        min_dist = float('inf')

        for wp_id, wp in self.waypoints.items():
            dx = wp.position.x - start_position.x
            dy = wp.position.y - start_position.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < min_dist:
                min_dist = dist
                nearest_start = wp_id

        if not nearest_start:
            return [source_waypoint, destination_waypoint]

        # Dijkstra from nearest start to source, then to destination
        path_to_source = self._dijkstra(nearest_start, source_waypoint)
        path_to_dest = self._dijkstra(source_waypoint, destination_waypoint)

        # Combine paths (avoid duplicate source waypoint)
        full_path = path_to_source + path_to_dest[1:]

        return full_path

    def _dijkstra(self, start: str, end: str) -> List[str]:
        """Dijkstra's shortest path algorithm."""
        if start == end:
            return [start]

        distances = {wp: float('inf') for wp in self.waypoints}
        distances[start] = 0
        previous = {}
        visited = set()
        pq = [(0, start)]

        while pq:
            current_dist, current = heapq.heappop(pq)

            if current in visited:
                continue

            visited.add(current)

            if current == end:
                break

            for segment in self.path_graph.get(current, []):
                if segment.is_blocked:
                    continue

                neighbor = segment.end_waypoint
                distance = current_dist + segment.distance

                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous[neighbor] = current
                    heapq.heappush(pq, (distance, neighbor))

        # Reconstruct path
        path = []
        current = end

        while current in previous:
            path.append(current)
            current = previous[current]

        path.append(start)
        path.reverse()

        return path if path[0] == start and path[-1] == end else [start, end]

    async def complete_task(
        self,
        task_id: str,
        success: bool = True,
        notes: str = ""
    ) -> Task:
        """Mark a task as completed."""
        if task_id not in self.tasks:
            raise ValueError(f"Task not found: {task_id}")

        task = self.tasks[task_id]
        task.completed_at = datetime.now()
        task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        task.notes = notes

        # Update robot
        if task.assigned_robot:
            robot = self.robots.get(task.assigned_robot)
            if robot:
                robot.current_task_id = None
                robot.current_path = []
                robot.state = RobotState.IDLE
                robot.current_payload_kg = 0

                if success:
                    robot.total_tasks_completed += 1

        logger.info(f"Task {task_id} completed: success={success}")

        return task

    async def cancel_task(
        self,
        task_id: str,
        reason: str = ""
    ) -> Task:
        """Cancel a task."""
        if task_id not in self.tasks:
            raise ValueError(f"Task not found: {task_id}")

        task = self.tasks[task_id]
        task.status = TaskStatus.CANCELLED
        task.notes = reason

        # Release assigned robot
        if task.assigned_robot:
            robot = self.robots.get(task.assigned_robot)
            if robot:
                robot.current_task_id = None
                robot.current_path = []
                robot.state = RobotState.IDLE

        logger.info(f"Task {task_id} cancelled: {reason}")

        return task

    async def dispatch_pending_tasks(self) -> List[Tuple[Task, Robot]]:
        """Dispatch all pending tasks to available robots."""
        dispatched = []

        while self._task_queue:
            _, task_id = heapq.heappop(self._task_queue)

            if task_id not in self.tasks:
                continue

            task = self.tasks[task_id]
            if task.status != TaskStatus.PENDING:
                continue

            try:
                result = await self.assign_task(task_id)
                dispatched.append(result)
            except ValueError as e:
                # No suitable robot - re-queue
                heapq.heappush(self._task_queue, (task.priority.value, task_id))
                break

        return dispatched

    # =========================================================================
    # Charging Management
    # =========================================================================

    async def create_charging_station(
        self,
        station_name: str,
        waypoint_id: str,
        power_kw: float,
        compatible_types: List[RobotType] = None
    ) -> ChargingStation:
        """Create a charging station."""
        if waypoint_id not in self.waypoints:
            raise ValueError(f"Waypoint not found: {waypoint_id}")

        station_id = self._generate_id("CHG")

        station = ChargingStation(
            station_id=station_id,
            waypoint_id=waypoint_id,
            station_name=station_name,
            power_kw=power_kw,
            compatible_types=compatible_types or list(RobotType)
        )

        self.charging_stations[station_id] = station

        # Mark waypoint as charging station
        self.waypoints[waypoint_id].is_charging_station = True

        logger.info(f"Created charging station: {station_name}")

        return station

    async def send_to_charge(
        self,
        robot_id: str,
        station_id: str = None
    ) -> Task:
        """Send a robot to charge."""
        if robot_id not in self.robots:
            raise ValueError(f"Robot not found: {robot_id}")

        robot = self.robots[robot_id]

        # Auto-select station if not specified
        if not station_id:
            station_id = await self._select_best_charging_station(robot)

        if not station_id:
            raise ValueError("No charging station available")

        station = self.charging_stations[station_id]

        if not station.is_available:
            raise ValueError(f"Station not available: {station_id}")

        if robot.robot_type not in station.compatible_types:
            raise ValueError(f"Incompatible robot type: {robot.robot_type}")

        # Create charging task
        current_wp = await self._find_nearest_waypoint(robot.position)

        task = await self.create_task(
            task_type=TaskType.CHARGE,
            source_waypoint=current_wp,
            destination_waypoint=station.waypoint_id,
            priority=TaskPriority.HIGH
        )

        # Reserve station
        station.is_available = False
        station.current_robot = robot_id

        # Assign task
        await self.assign_task(task.task_id, robot_id)

        return task

    async def _select_best_charging_station(self, robot: Robot) -> Optional[str]:
        """Select best available charging station for robot."""
        candidates = []

        for station_id, station in self.charging_stations.items():
            if not station.is_available:
                continue
            if robot.robot_type not in station.compatible_types:
                continue

            wp = self.waypoints[station.waypoint_id]
            dx = wp.position.x - robot.position.x
            dy = wp.position.y - robot.position.y
            distance = math.sqrt(dx * dx + dy * dy)

            candidates.append((distance, station_id))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    async def _find_nearest_waypoint(self, position: Position) -> str:
        """Find nearest waypoint to position."""
        min_dist = float('inf')
        nearest = None

        for wp_id, wp in self.waypoints.items():
            dx = wp.position.x - position.x
            dy = wp.position.y - position.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < min_dist:
                min_dist = dist
                nearest = wp_id

        return nearest

    async def complete_charging(
        self,
        robot_id: str
    ) -> Robot:
        """Complete charging session."""
        if robot_id not in self.robots:
            raise ValueError(f"Robot not found: {robot_id}")

        robot = self.robots[robot_id]

        # Find and release station
        for station in self.charging_stations.values():
            if station.current_robot == robot_id:
                station.is_available = True
                station.current_robot = None
                break

        robot.state = RobotState.IDLE
        robot.battery_percent = 100.0

        logger.info(f"Robot {robot.robot_name} charging complete")

        return robot

    # =========================================================================
    # Traffic Management
    # =========================================================================

    async def check_zone_access(
        self,
        robot_id: str,
        zone_id: str
    ) -> Tuple[bool, str]:
        """
        Check if robot can enter a zone.

        Returns:
            Tuple of (allowed, reason)
        """
        if robot_id not in self.robots:
            return False, "Robot not found"

        if zone_id not in self.zones:
            return False, "Zone not found"

        robot = self.robots[robot_id]
        zone = self.zones[zone_id]

        # Check zone access list
        if zone_id not in robot.allowed_zones:
            return False, "Robot not authorized for zone"

        # Check max occupancy
        if len(self._zone_occupancy[zone_id]) >= zone.max_robots:
            return False, f"Zone at capacity ({zone.max_robots})"

        # Check robot type access
        if zone.access_required and robot.robot_type.value not in zone.access_required:
            return False, "Robot type not allowed"

        return True, "Access granted"

    async def reserve_zone_entry(
        self,
        robot_id: str,
        zone_id: str
    ) -> bool:
        """Reserve entry into a zone (traffic semaphore)."""
        allowed, reason = await self.check_zone_access(robot_id, zone_id)

        if allowed:
            self._zone_occupancy[zone_id].add(robot_id)
            return True

        logger.warning(f"Zone entry denied for {robot_id}: {reason}")
        return False

    async def release_zone(
        self,
        robot_id: str,
        zone_id: str
    ):
        """Release zone occupancy."""
        if zone_id in self._zone_occupancy:
            self._zone_occupancy[zone_id].discard(robot_id)

    async def add_traffic_rule(
        self,
        zone_id: str,
        rule_type: str,
        direction: str = None,
        priority_types: List[RobotType] = None
    ) -> TrafficControl:
        """Add traffic control rule."""
        if zone_id not in self.zones:
            raise ValueError(f"Zone not found: {zone_id}")

        rule_id = self._generate_id("TRF")

        rule = TrafficControl(
            rule_id=rule_id,
            zone_id=zone_id,
            rule_type=rule_type,
            direction=direction,
            priority_robot_types=priority_types or []
        )

        self.traffic_rules[rule_id] = rule

        return rule

    # =========================================================================
    # Safety and Monitoring
    # =========================================================================

    async def report_obstacle(
        self,
        robot_id: str,
        position: Position,
        obstacle_type: str
    ) -> SafetyEvent:
        """Report obstacle detection."""
        event = SafetyEvent(
            event_id=self._generate_id("SAF"),
            event_type="obstacle_detect",
            robot_id=robot_id,
            timestamp=datetime.now(),
            position=position,
            description=f"Obstacle detected: {obstacle_type}",
            severity="medium"
        )

        self.safety_events.append(event)

        # Update robot state
        if robot_id in self.robots:
            self.robots[robot_id].state = RobotState.WAITING

        return event

    async def report_near_collision(
        self,
        robot_id: str,
        other_robot_id: str,
        position: Position,
        distance_m: float
    ) -> SafetyEvent:
        """Report near-collision avoidance."""
        event = SafetyEvent(
            event_id=self._generate_id("SAF"),
            event_type="collision_avoid",
            robot_id=robot_id,
            timestamp=datetime.now(),
            position=position,
            description=f"Near collision with {other_robot_id}, distance: {distance_m}m",
            severity="high"
        )

        self.safety_events.append(event)

        return event

    async def get_fleet_status(self) -> Dict:
        """Get overall fleet status."""
        by_state = {}
        for state in RobotState:
            by_state[state.value] = sum(
                1 for r in self.robots.values() if r.state == state
            )

        total_tasks = len(self.tasks)
        pending_tasks = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING)
        active_tasks = sum(1 for t in self.tasks.values() if t.status == TaskStatus.IN_PROGRESS)

        low_battery = [
            r.robot_id for r in self.robots.values()
            if r.battery_percent < 20
        ]

        return {
            "timestamp": datetime.now().isoformat(),
            "fleet_size": len(self.robots),
            "robots_by_state": by_state,
            "tasks": {
                "total": total_tasks,
                "pending": pending_tasks,
                "active": active_tasks,
                "queue_size": len(self._task_queue)
            },
            "zones": {
                zone_id: len(robots)
                for zone_id, robots in self._zone_occupancy.items()
            },
            "charging_stations": {
                "total": len(self.charging_stations),
                "available": sum(1 for s in self.charging_stations.values() if s.is_available)
            },
            "alerts": {
                "low_battery": low_battery,
                "errors": [r.robot_id for r in self.robots.values() if r.state == RobotState.ERROR],
                "e_stopped": [r.robot_id for r in self.robots.values() if r.state == RobotState.EMERGENCY_STOP]
            },
            "safety_events_24h": sum(
                1 for e in self.safety_events
                if e.timestamp > datetime.now() - timedelta(hours=24)
            )
        }

    async def get_robot_details(self, robot_id: str) -> Dict:
        """Get detailed robot information."""
        if robot_id not in self.robots:
            raise ValueError(f"Robot not found: {robot_id}")

        robot = self.robots[robot_id]

        current_task = None
        if robot.current_task_id and robot.current_task_id in self.tasks:
            task = self.tasks[robot.current_task_id]
            current_task = {
                "task_id": task.task_id,
                "type": task.task_type.value,
                "destination": task.destination_waypoint,
                "status": task.status.value
            }

        return {
            "robot_id": robot_id,
            "robot_name": robot.robot_name,
            "robot_type": robot.robot_type.value,
            "state": robot.state.value,
            "position": {
                "x": robot.position.x,
                "y": robot.position.y,
                "theta": robot.position.theta
            },
            "velocity": {
                "linear": robot.velocity.linear,
                "angular": robot.velocity.angular
            },
            "battery_percent": robot.battery_percent,
            "payload": {
                "current_kg": robot.current_payload_kg,
                "max_kg": robot.max_payload_kg
            },
            "current_task": current_task,
            "path": robot.current_path,
            "path_progress": f"{robot.path_index}/{len(robot.current_path)}",
            "statistics": {
                "total_distance_m": round(robot.total_distance_m, 2),
                "total_tasks_completed": robot.total_tasks_completed
            },
            "error": {
                "code": robot.error_code,
                "message": robot.error_message
            } if robot.error_code else None,
            "last_heartbeat": robot.last_heartbeat.isoformat()
        }


# Factory function
def create_amr_service() -> AMRIntegrationService:
    """Create and return an AMRIntegrationService instance."""
    return AMRIntegrationService()
