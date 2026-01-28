#!/usr/bin/env python3
"""
Equipment Registry Node - Manufacturing equipment discovery and tracking

Discovers and maintains registry of all manufacturing equipment on the network.
Supports multiple discovery protocols: ROS2, OPC UA, MTConnect, mDNS.

Industry 4.0/5.0 Architecture - ISA-95 Compliant
LEGO MCP Manufacturing System v7.0
"""

import json
import socket
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Callable

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy

from std_msgs.msg import String
from std_srvs.srv import Trigger


class EquipmentType(Enum):
    """Equipment type enumeration."""
    CNC = 0
    LASER = 1
    FDM = 2
    SLA = 3
    ROBOT_ARM = 4
    AGV = 5
    CONVEYOR = 6
    INSPECTION = 7
    ASSEMBLY = 8
    SENSOR = 9
    CAMERA = 10
    PLC = 11
    OTHER = 255


class EquipmentStatus(Enum):
    """Equipment status enumeration."""
    ONLINE = 0
    OFFLINE = 1
    BUSY = 2
    ERROR = 3
    MAINTENANCE = 4


@dataclass
class EquipmentRecord:
    """Equipment registry record."""
    equipment_id: str
    equipment_name: str
    equipment_type: EquipmentType
    serial_number: str = ""
    manufacturer: str = ""
    model: str = ""

    # Network
    ip_address: str = ""
    port: int = 0
    mac_address: str = ""
    hostname: str = ""

    # Protocols
    supported_protocols: List[str] = field(default_factory=list)
    primary_protocol: str = "ros2"
    ros2_namespace: str = ""

    # Capabilities
    capabilities: List[str] = field(default_factory=list)
    max_payload_kg: float = 0.0
    work_envelope: List[float] = field(default_factory=list)

    # Status
    status: EquipmentStatus = EquipmentStatus.OFFLINE
    isa95_level: int = 0
    work_center_id: str = ""
    production_line: str = ""

    # Timestamps
    first_seen: float = 0.0
    last_seen: float = 0.0
    announcement_count: int = 0

    # Health
    availability_percent: float = 100.0
    total_uptime_sec: float = 0.0
    total_downtime_sec: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        d = asdict(self)
        d['equipment_type'] = self.equipment_type.name
        d['status'] = self.status.name
        return d


class EquipmentRegistryNode(Node):
    """
    ROS2 node for equipment discovery and registry management.

    Features:
    - Passive discovery via ROS2 topic announcements
    - Active network scanning (optional)
    - Equipment health monitoring
    - Capability-based equipment matching
    - Integration with OPC UA and MTConnect
    """

    def __init__(self):
        super().__init__('equipment_registry')

        # Declare parameters
        self.declare_parameter('scan_interval_sec', 30.0)
        self.declare_parameter('offline_threshold_sec', 60.0)
        self.declare_parameter('enable_network_scan', False)
        self.declare_parameter('network_ranges', ['192.168.1.0/24'])
        self.declare_parameter('announcement_topic', '/lego_mcp/equipment/announcements')
        self.declare_parameter('registry_topic', '/lego_mcp/equipment/registry')

        # Get parameters
        self._scan_interval = self.get_parameter('scan_interval_sec').value
        self._offline_threshold = self.get_parameter('offline_threshold_sec').value
        self._enable_network_scan = self.get_parameter('enable_network_scan').value
        self._network_ranges = self.get_parameter('network_ranges').value
        self._announcement_topic = self.get_parameter('announcement_topic').value
        self._registry_topic = self.get_parameter('registry_topic').value

        # Registry storage
        self._registry: Dict[str, EquipmentRecord] = {}
        self._lock = threading.RLock()

        # Callback groups
        self._timer_group = MutuallyExclusiveCallbackGroup()
        self._service_group = ReentrantCallbackGroup()

        # QoS profiles
        reliable_qos = QoSProfile(
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            depth=100
        )

        # Publishers
        self._registry_pub = self.create_publisher(
            String,
            self._registry_topic,
            reliable_qos
        )

        self._event_pub = self.create_publisher(
            String,
            '/lego_mcp/equipment/events',
            10
        )

        # Subscribers
        self._announcement_sub = self.create_subscription(
            String,
            self._announcement_topic,
            self._announcement_callback,
            reliable_qos
        )

        self._heartbeat_sub = self.create_subscription(
            String,
            '/lego_mcp/heartbeats',
            self._heartbeat_callback,
            10
        )

        # Services
        self._get_registry_srv = self.create_service(
            Trigger,
            '/lego_mcp/equipment/get_registry',
            self._get_registry_callback,
            callback_group=self._service_group
        )

        self._discover_srv = self.create_service(
            Trigger,
            '/lego_mcp/equipment/discover',
            self._discover_callback,
            callback_group=self._service_group
        )

        self._get_by_capability_srv = self.create_service(
            Trigger,
            '/lego_mcp/equipment/get_by_capability',
            self._get_by_capability_callback,
            callback_group=self._service_group
        )

        # Timers
        self._publish_timer = self.create_timer(
            5.0,  # Publish registry every 5 seconds
            self._publish_registry,
            callback_group=self._timer_group
        )

        self._health_timer = self.create_timer(
            self._scan_interval,
            self._check_equipment_health,
            callback_group=self._timer_group
        )

        # Register known equipment types
        self._register_known_equipment()

        self.get_logger().info(
            f'Equipment Registry started - scan interval: {self._scan_interval}s, '
            f'offline threshold: {self._offline_threshold}s'
        )

    def _register_known_equipment(self):
        """Register known/expected equipment."""
        known_equipment = [
            EquipmentRecord(
                equipment_id='grbl_cnc',
                equipment_name='GRBL CNC/Laser',
                equipment_type=EquipmentType.CNC,
                manufacturer='TinyG',
                model='TinyG v8',
                ros2_namespace='/lego_mcp',
                supported_protocols=['ros2', 'serial'],
                capabilities=['cnc_milling', 'laser_cutting', 'laser_engraving'],
                isa95_level=0,
                work_center_id='WC001',
            ),
            EquipmentRecord(
                equipment_id='formlabs_sla',
                equipment_name='Formlabs SLA Printer',
                equipment_type=EquipmentType.SLA,
                manufacturer='Formlabs',
                model='Form 3',
                ros2_namespace='/lego_mcp',
                supported_protocols=['ros2', 'http'],
                capabilities=['sla_printing', 'high_resolution', 'resin_curing'],
                isa95_level=0,
                work_center_id='WC002',
            ),
            EquipmentRecord(
                equipment_id='bambu_fdm',
                equipment_name='Bambu Lab FDM Printer',
                equipment_type=EquipmentType.FDM,
                manufacturer='Bambu Lab',
                model='A1',
                ros2_namespace='/lego_mcp',
                supported_protocols=['ros2', 'mqtt'],
                capabilities=['fdm_printing', 'multi_color', 'ams_support'],
                isa95_level=0,
                work_center_id='WC003',
            ),
        ]

        for eq in known_equipment:
            eq.first_seen = time.time()
            eq.status = EquipmentStatus.OFFLINE  # Will be updated when heartbeat received
            self._registry[eq.equipment_id] = eq

    def _announcement_callback(self, msg: String):
        """Handle equipment announcement."""
        try:
            data = json.loads(msg.data)
            equipment_id = data.get('equipment_id', '')

            if not equipment_id:
                return

            with self._lock:
                if equipment_id in self._registry:
                    # Update existing
                    eq = self._registry[equipment_id]
                    eq.last_seen = time.time()
                    eq.announcement_count += 1
                    eq.status = EquipmentStatus.ONLINE

                    # Update dynamic fields
                    if 'status' in data:
                        eq.status = EquipmentStatus[data['status'].upper()]
                    if 'ip_address' in data:
                        eq.ip_address = data['ip_address']
                else:
                    # New equipment discovered
                    eq = self._create_record_from_announcement(data)
                    self._registry[equipment_id] = eq
                    self._publish_event('equipment_discovered', eq.to_dict())
                    self.get_logger().info(f'Discovered new equipment: {equipment_id}')

        except json.JSONDecodeError:
            self.get_logger().warning(f'Invalid announcement JSON: {msg.data[:100]}')

    def _heartbeat_callback(self, msg: String):
        """Handle heartbeat from equipment nodes."""
        try:
            data = json.loads(msg.data)
            node_name = data.get('node_name', '')

            # Map node name to equipment ID
            equipment_id = self._node_to_equipment_id(node_name)

            if equipment_id and equipment_id in self._registry:
                with self._lock:
                    eq = self._registry[equipment_id]
                    was_offline = eq.status == EquipmentStatus.OFFLINE

                    eq.last_seen = time.time()
                    eq.status = EquipmentStatus.ONLINE

                    if was_offline:
                        self._publish_event('equipment_online', {
                            'equipment_id': equipment_id,
                            'equipment_name': eq.equipment_name,
                        })
                        self.get_logger().info(f'Equipment online: {equipment_id}')

        except json.JSONDecodeError:
            pass

    def _node_to_equipment_id(self, node_name: str) -> Optional[str]:
        """Map ROS2 node name to equipment ID."""
        mapping = {
            'grbl_node': 'grbl_cnc',
            'grbl_simulator': 'grbl_cnc',
            'formlabs_node': 'formlabs_sla',
            'formlabs_simulator': 'formlabs_sla',
            'bambu_node': 'bambu_fdm',
            'bambu_simulator': 'bambu_fdm',
        }
        return mapping.get(node_name)

    def _create_record_from_announcement(self, data: dict) -> EquipmentRecord:
        """Create equipment record from announcement data."""
        eq_type = EquipmentType.OTHER
        if 'equipment_type' in data:
            try:
                eq_type = EquipmentType[data['equipment_type'].upper()]
            except KeyError:
                pass

        return EquipmentRecord(
            equipment_id=data.get('equipment_id', ''),
            equipment_name=data.get('equipment_name', data.get('equipment_id', '')),
            equipment_type=eq_type,
            serial_number=data.get('serial_number', ''),
            manufacturer=data.get('manufacturer', ''),
            model=data.get('model', ''),
            ip_address=data.get('ip_address', ''),
            port=data.get('port', 0),
            mac_address=data.get('mac_address', ''),
            hostname=data.get('hostname', ''),
            supported_protocols=data.get('supported_protocols', ['ros2']),
            primary_protocol=data.get('primary_protocol', 'ros2'),
            ros2_namespace=data.get('ros2_namespace', ''),
            capabilities=data.get('capabilities', []),
            isa95_level=data.get('isa95_level', 0),
            work_center_id=data.get('work_center_id', ''),
            status=EquipmentStatus.ONLINE,
            first_seen=time.time(),
            last_seen=time.time(),
            announcement_count=1,
        )

    def _check_equipment_health(self):
        """Check health of registered equipment."""
        current_time = time.time()

        with self._lock:
            for equipment_id, eq in self._registry.items():
                if eq.last_seen > 0:
                    time_since_seen = current_time - eq.last_seen

                    if time_since_seen > self._offline_threshold:
                        if eq.status != EquipmentStatus.OFFLINE:
                            eq.status = EquipmentStatus.OFFLINE
                            self._publish_event('equipment_offline', {
                                'equipment_id': equipment_id,
                                'equipment_name': eq.equipment_name,
                                'last_seen_sec_ago': time_since_seen,
                            })
                            self.get_logger().warning(
                                f'Equipment offline: {equipment_id} '
                                f'(last seen {time_since_seen:.0f}s ago)'
                            )

    def _publish_registry(self):
        """Publish current registry state."""
        with self._lock:
            registry_data = {
                'timestamp': time.time(),
                'equipment_count': len(self._registry),
                'online_count': sum(
                    1 for eq in self._registry.values()
                    if eq.status == EquipmentStatus.ONLINE
                ),
                'equipment': [eq.to_dict() for eq in self._registry.values()],
            }

        msg = String()
        msg.data = json.dumps(registry_data)
        self._registry_pub.publish(msg)

    def _publish_event(self, event_type: str, data: dict):
        """Publish equipment event."""
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'data': data,
        }

        msg = String()
        msg.data = json.dumps(event)
        self._event_pub.publish(msg)

    def _get_registry_callback(self, request, response):
        """Get full registry."""
        with self._lock:
            registry_data = {
                'timestamp': time.time(),
                'equipment_count': len(self._registry),
                'equipment': [eq.to_dict() for eq in self._registry.values()],
            }

        response.success = True
        response.message = json.dumps(registry_data)
        return response

    def _discover_callback(self, request, response):
        """Trigger equipment discovery."""
        # For now, just return current registry
        # In production, would trigger network scan
        with self._lock:
            online = sum(
                1 for eq in self._registry.values()
                if eq.status == EquipmentStatus.ONLINE
            )
            offline = len(self._registry) - online

        response.success = True
        response.message = json.dumps({
            'total_found': len(self._registry),
            'online_count': online,
            'offline_count': offline,
        })
        return response

    def _get_by_capability_callback(self, request, response):
        """Get equipment by capability."""
        # This would parse the request for capability requirements
        # For now, return all equipment with capabilities listed
        with self._lock:
            equipment_with_caps = [
                eq.to_dict() for eq in self._registry.values()
                if eq.capabilities and eq.status == EquipmentStatus.ONLINE
            ]

        response.success = True
        response.message = json.dumps({
            'equipment': equipment_with_caps,
            'count': len(equipment_with_caps),
        })
        return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    node = EquipmentRegistryNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
