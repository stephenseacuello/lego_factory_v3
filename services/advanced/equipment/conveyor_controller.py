"""
Conveyor Controller for Material Handling.

LEGO MCP v6.0 World-Class Manufacturing Research Platform
Phase 5: Algorithm-to-Action Bridge

Provides control interface for conveyor systems:
- Belt conveyor control
- Zone management
- Product tracking
- Integration with robotic pick/place
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


class ConveyorState(Enum):
    """Conveyor operational state."""
    STOPPED = "stopped"
    RUNNING = "running"
    FAULT = "fault"
    E_STOP = "e_stop"
    INITIALIZING = "initializing"


class ConveyorDirection(Enum):
    """Conveyor direction."""
    FORWARD = "forward"
    REVERSE = "reverse"


class ZoneState(Enum):
    """Conveyor zone state."""
    EMPTY = "empty"
    OCCUPIED = "occupied"
    BLOCKED = "blocked"
    ACCUMULATING = "accumulating"


class ProductState(Enum):
    """Product tracking state."""
    IN_TRANSIT = "in_transit"
    AT_STATION = "at_station"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"


@dataclass
class ConveyorZone:
    """A zone on the conveyor."""
    zone_id: str
    name: str
    position: float  # Position along conveyor (0-1)
    length: float  # Zone length in mm

    # State
    state: ZoneState = ZoneState.EMPTY
    current_product_id: Optional[str] = None

    # Sensors
    entry_sensor: bool = False
    exit_sensor: bool = False

    # Control
    can_accumulate: bool = True
    priority: int = 0

    # Timestamps
    last_entry: Optional[datetime] = None
    last_exit: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "position": self.position,
            "length": self.length,
            "state": self.state.value,
            "current_product_id": self.current_product_id,
            "entry_sensor": self.entry_sensor,
            "exit_sensor": self.exit_sensor,
        }


@dataclass
class TrackedProduct:
    """A product being tracked on the conveyor."""
    product_id: str
    product_type: str

    # Position
    current_zone_id: Optional[str] = None
    position_mm: float = 0.0

    # State
    state: ProductState = ProductState.IN_TRANSIT

    # Timestamps
    entry_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)

    # Quality/routing
    quality_status: str = "unknown"
    destination: Optional[str] = None
    route: List[str] = field(default_factory=list)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_type": self.product_type,
            "current_zone_id": self.current_zone_id,
            "position_mm": self.position_mm,
            "state": self.state.value,
            "entry_time": self.entry_time.isoformat(),
            "quality_status": self.quality_status,
            "destination": self.destination,
        }


@dataclass
class ConveyorStatus:
    """Complete conveyor system status."""
    conveyor_id: str
    state: ConveyorState
    direction: ConveyorDirection

    # Speed
    speed_setpoint: float  # mm/s
    actual_speed: float  # mm/s
    speed_percentage: float  # 0-100

    # Motor
    motor_current: float  # Amps
    motor_temperature: float  # Celsius

    # Zones
    zones: List[ConveyorZone]

    # Products
    product_count: int
    products_in_transit: List[str]

    # Faults
    fault_code: Optional[int] = None
    fault_message: Optional[str] = None

    # Timestamps
    timestamp: datetime = field(default_factory=datetime.now)
    run_time_hours: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conveyor_id": self.conveyor_id,
            "state": self.state.value,
            "direction": self.direction.value,
            "speed_setpoint": self.speed_setpoint,
            "actual_speed": self.actual_speed,
            "speed_percentage": self.speed_percentage,
            "motor_current": self.motor_current,
            "motor_temperature": self.motor_temperature,
            "zones": [z.to_dict() for z in self.zones],
            "product_count": self.product_count,
            "fault_code": self.fault_code,
            "fault_message": self.fault_message,
            "timestamp": self.timestamp.isoformat(),
        }


class ConveyorProtocol(ABC):
    """Abstract protocol for conveyor communication."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to conveyor controller."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from conveyor controller."""
        pass

    @abstractmethod
    async def start(self) -> bool:
        """Start conveyor."""
        pass

    @abstractmethod
    async def stop(self) -> bool:
        """Stop conveyor."""
        pass

    @abstractmethod
    async def set_speed(self, speed_percentage: float) -> bool:
        """Set conveyor speed (0-100%)."""
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get conveyor status."""
        pass


class ModbusTCPProtocol(ConveyorProtocol):
    """Modbus TCP protocol for industrial conveyors."""

    def __init__(self, host: str = "192.168.1.100", port: int = 502, unit_id: int = 1):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self._connected = False
        self._client = None

    async def connect(self) -> bool:
        """Connect via Modbus TCP."""
        try:
            # In production: use pymodbus
            # from pymodbus.client import AsyncModbusTcpClient
            # self._client = AsyncModbusTcpClient(self.host, port=self.port)
            # await self._client.connect()
            self._connected = True
            logger.info(f"Connected to conveyor at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    async def disconnect(self):
        """Disconnect Modbus."""
        self._connected = False
        if self._client:
            # await self._client.close()
            pass

    async def start(self) -> bool:
        """Start conveyor via Modbus coil."""
        # Write coil for start command
        # await self._client.write_coil(0, True, unit=self.unit_id)
        return True

    async def stop(self) -> bool:
        """Stop conveyor."""
        # await self._client.write_coil(1, True, unit=self.unit_id)
        return True

    async def set_speed(self, speed_percentage: float) -> bool:
        """Set speed via holding register."""
        speed_value = int(speed_percentage * 100)  # Scale to 0-10000
        # await self._client.write_register(0, speed_value, unit=self.unit_id)
        return True

    async def get_status(self) -> Dict[str, Any]:
        """Read status from Modbus registers."""
        # In production: read actual registers
        return {
            "running": True,
            "speed": 50.0,
            "current": 2.5,
            "temperature": 35.0,
            "fault": None,
        }


class EtherNetIPProtocol(ConveyorProtocol):
    """EtherNet/IP protocol for Allen-Bradley systems."""

    def __init__(self, host: str = "192.168.1.100"):
        self.host = host
        self._connected = False

    async def connect(self) -> bool:
        """Connect via EtherNet/IP."""
        # In production: use pycomm3 or cpppo
        self._connected = True
        return True

    async def disconnect(self):
        """Disconnect."""
        self._connected = False

    async def start(self) -> bool:
        """Start via tag write."""
        return True

    async def stop(self) -> bool:
        """Stop via tag write."""
        return True

    async def set_speed(self, speed_percentage: float) -> bool:
        """Set speed via tag write."""
        return True

    async def get_status(self) -> Dict[str, Any]:
        """Read status tags."""
        return {
            "running": True,
            "speed": 50.0,
            "current": 2.5,
            "temperature": 35.0,
            "fault": None,
        }


class ConveyorController:
    """
    Conveyor System Controller for automated material handling.

    Features:
    - Multi-zone management
    - Product tracking
    - Accumulation control
    - Integration with robotics
    - AI-driven routing
    """

    def __init__(
        self,
        protocol: ConveyorProtocol,
        conveyor_id: str = "conv-001",
        total_length_mm: float = 3000.0,
        max_speed_mm_s: float = 500.0,
    ):
        self.protocol = protocol
        self.conveyor_id = conveyor_id
        self.total_length_mm = total_length_mm
        self.max_speed_mm_s = max_speed_mm_s

        # State
        self._state = ConveyorState.STOPPED
        self._direction = ConveyorDirection.FORWARD
        self._speed_percentage = 0.0

        # Zones
        self.zones: Dict[str, ConveyorZone] = {}

        # Product tracking
        self.products: Dict[str, TrackedProduct] = {}
        self._product_callbacks: List[Callable[[TrackedProduct, str], None]] = []

        # Simulation/monitoring
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {
            "total_products": 0,
            "products_completed": 0,
            "products_rejected": 0,
            "runtime_seconds": 0,
        }

    async def connect(self) -> bool:
        """Connect to conveyor system."""
        return await self.protocol.connect()

    async def disconnect(self):
        """Disconnect from conveyor."""
        await self.stop()
        await self.protocol.disconnect()

    async def start(self, speed_percentage: float = 50.0) -> bool:
        """Start conveyor at specified speed."""
        if not await self.protocol.start():
            return False

        if not await self.protocol.set_speed(speed_percentage):
            return False

        self._state = ConveyorState.RUNNING
        self._speed_percentage = speed_percentage
        self._running = True

        # Start monitoring task
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info(f"Conveyor {self.conveyor_id} started at {speed_percentage}%")
        return True

    async def stop(self) -> bool:
        """Stop conveyor."""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        success = await self.protocol.stop()
        self._state = ConveyorState.STOPPED
        self._speed_percentage = 0.0

        logger.info(f"Conveyor {self.conveyor_id} stopped")
        return success

    async def set_speed(self, speed_percentage: float) -> bool:
        """Set conveyor speed (0-100%)."""
        if speed_percentage < 0 or speed_percentage > 100:
            raise ValueError("Speed must be 0-100%")

        success = await self.protocol.set_speed(speed_percentage)
        if success:
            self._speed_percentage = speed_percentage
        return success

    async def set_direction(self, direction: ConveyorDirection) -> bool:
        """Set conveyor direction."""
        # Most conveyors require stop before direction change
        was_running = self._state == ConveyorState.RUNNING

        if was_running:
            await self.stop()

        self._direction = direction

        if was_running:
            await self.start(self._speed_percentage)

        return True

    def add_zone(
        self,
        name: str,
        position: float,
        length: float,
        can_accumulate: bool = True,
        priority: int = 0,
    ) -> ConveyorZone:
        """Add a zone to the conveyor."""
        zone = ConveyorZone(
            zone_id=str(uuid.uuid4()),
            name=name,
            position=position,
            length=length,
            can_accumulate=can_accumulate,
            priority=priority,
        )
        self.zones[zone.zone_id] = zone
        return zone

    def track_product(
        self,
        product_type: str,
        entry_zone_id: Optional[str] = None,
        destination: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TrackedProduct:
        """Start tracking a new product."""
        product = TrackedProduct(
            product_id=str(uuid.uuid4()),
            product_type=product_type,
            current_zone_id=entry_zone_id,
            destination=destination,
            metadata=metadata or {},
        )

        self.products[product.product_id] = product
        self.stats["total_products"] += 1

        # Update zone if specified
        if entry_zone_id and entry_zone_id in self.zones:
            self.zones[entry_zone_id].state = ZoneState.OCCUPIED
            self.zones[entry_zone_id].current_product_id = product.product_id
            self.zones[entry_zone_id].last_entry = datetime.now()

        self._notify_product_event(product, "entered")

        return product

    def update_product_position(
        self,
        product_id: str,
        new_zone_id: str,
    ) -> bool:
        """Update product position to new zone."""
        if product_id not in self.products:
            return False

        product = self.products[product_id]

        # Clear old zone
        if product.current_zone_id and product.current_zone_id in self.zones:
            old_zone = self.zones[product.current_zone_id]
            old_zone.state = ZoneState.EMPTY
            old_zone.current_product_id = None
            old_zone.last_exit = datetime.now()

        # Update new zone
        if new_zone_id in self.zones:
            new_zone = self.zones[new_zone_id]
            new_zone.state = ZoneState.OCCUPIED
            new_zone.current_product_id = product_id
            new_zone.last_entry = datetime.now()

        product.current_zone_id = new_zone_id
        product.last_update = datetime.now()

        self._notify_product_event(product, "moved")

        return True

    def complete_product(
        self,
        product_id: str,
        status: str = "completed",
    ):
        """Mark product as completed and remove from tracking."""
        if product_id not in self.products:
            return

        product = self.products[product_id]

        # Clear zone
        if product.current_zone_id and product.current_zone_id in self.zones:
            zone = self.zones[product.current_zone_id]
            zone.state = ZoneState.EMPTY
            zone.current_product_id = None

        # Update stats
        if status == "completed":
            product.state = ProductState.COMPLETED
            self.stats["products_completed"] += 1
        else:
            product.state = ProductState.REJECTED
            self.stats["products_rejected"] += 1

        self._notify_product_event(product, status)

        # Remove from active tracking
        del self.products[product_id]

    def register_product_callback(
        self,
        callback: Callable[[TrackedProduct, str], None],
    ):
        """Register callback for product events."""
        self._product_callbacks.append(callback)

    def _notify_product_event(self, product: TrackedProduct, event: str):
        """Notify callbacks of product event."""
        for callback in self._product_callbacks:
            try:
                callback(product, event)
            except Exception as e:
                logger.error(f"Product callback error: {e}")

    async def get_status(self) -> ConveyorStatus:
        """Get complete conveyor status."""
        protocol_status = await self.protocol.get_status()

        actual_speed = (self._speed_percentage / 100) * self.max_speed_mm_s

        return ConveyorStatus(
            conveyor_id=self.conveyor_id,
            state=self._state,
            direction=self._direction,
            speed_setpoint=actual_speed,
            actual_speed=actual_speed,
            speed_percentage=self._speed_percentage,
            motor_current=protocol_status.get("current", 0),
            motor_temperature=protocol_status.get("temperature", 0),
            zones=list(self.zones.values()),
            product_count=len(self.products),
            products_in_transit=[p.product_id for p in self.products.values()],
            fault_code=protocol_status.get("fault"),
        )

    async def execute_ai_decision(
        self,
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute AI-generated routing decision."""
        decision_type = decision.get("type")

        if decision_type == "speed_adjustment":
            new_speed = decision.get("speed_percentage", 50)
            success = await self.set_speed(new_speed)
            return {"success": success, "action": f"Set speed to {new_speed}%"}

        elif decision_type == "route_product":
            product_id = decision.get("product_id")
            destination = decision.get("destination")
            if product_id in self.products:
                self.products[product_id].destination = destination
                return {"success": True, "action": f"Routed {product_id} to {destination}"}
            return {"success": False, "error": "Product not found"}

        elif decision_type == "reject_product":
            product_id = decision.get("product_id")
            reason = decision.get("reason", "quality")
            self.complete_product(product_id, "rejected")
            return {"success": True, "action": f"Rejected {product_id}: {reason}"}

        elif decision_type == "stop_zone":
            zone_id = decision.get("zone_id")
            if zone_id in self.zones:
                self.zones[zone_id].state = ZoneState.BLOCKED
                return {"success": True, "action": f"Blocked zone {zone_id}"}
            return {"success": False, "error": "Zone not found"}

        elif decision_type == "emergency_stop":
            await self.stop()
            self._state = ConveyorState.E_STOP
            return {"success": True, "action": "Emergency stop"}

        else:
            return {"success": False, "error": f"Unknown decision: {decision_type}"}

    async def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                # Simulate product movement
                current_speed_mm_s = (self._speed_percentage / 100) * self.max_speed_mm_s

                for product in list(self.products.values()):
                    # Update position
                    product.position_mm += current_speed_mm_s * 0.1  # 100ms updates
                    product.last_update = datetime.now()

                    # Check zone transitions
                    for zone in self.zones.values():
                        zone_start = zone.position * self.total_length_mm
                        zone_end = zone_start + zone.length

                        if zone_start <= product.position_mm < zone_end:
                            if product.current_zone_id != zone.zone_id:
                                self.update_product_position(product.product_id, zone.zone_id)

                    # Check if product reached end
                    if product.position_mm >= self.total_length_mm:
                        self.complete_product(product.product_id, "completed")

                self.stats["runtime_seconds"] += 0.1

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            await asyncio.sleep(0.1)


# Factory function
def create_conveyor_controller(
    protocol_type: str = "modbus",
    **kwargs,
) -> ConveyorController:
    """Create conveyor controller with specified protocol."""
    if protocol_type == "modbus":
        protocol = ModbusTCPProtocol(**kwargs)
    elif protocol_type == "ethernet_ip":
        protocol = EtherNetIPProtocol(**kwargs)
    else:
        raise ValueError(f"Unknown protocol: {protocol_type}")

    return ConveyorController(protocol)
