#!/usr/bin/env python3
"""
LEGO MCP Discovery Server

Central discovery service for dynamic equipment registration,
node discovery, and factory cell topology management.

Features:
- Equipment registration with capability advertisement
- Automatic node and topic discovery via ROS2 graph API
- Service discovery and endpoint management
- Heartbeat-based health monitoring
- Bandwidth optimization through selective QoS
- Event-driven topology updates

LEGO MCP Manufacturing System v7.0
"""

import json
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Callable
from collections import defaultdict

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String, Bool
from std_srvs.srv import Trigger, SetBool


class EquipmentType(Enum):
    """Types of discoverable equipment."""
    ROBOT_ARM = "robot_arm"
    AGV = "agv"
    CNC = "cnc"
    LASER = "laser"
    SLA_PRINTER = "sla_printer"
    FDM_PRINTER = "fdm_printer"
    CAMERA = "camera"
    SENSOR = "sensor"
    CONTROLLER = "controller"
    UNKNOWN = "unknown"


class EquipmentState(Enum):
    """Equipment lifecycle states."""
    DISCOVERED = "discovered"
    REGISTERING = "registering"
    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    OFFLINE = "offline"
    DEREGISTERED = "deregistered"


@dataclass
class EquipmentCapability:
    """Capability advertised by equipment."""
    name: str
    version: str = "1.0"
    parameters: Dict = field(default_factory=dict)


@dataclass
class EquipmentEndpoint:
    """Communication endpoint for equipment."""
    endpoint_type: str  # topic, service, action
    name: str
    message_type: str
    qos_profile: Optional[str] = None


@dataclass
class RegisteredEquipment:
    """Registered equipment information."""
    equipment_id: str
    equipment_type: EquipmentType
    state: EquipmentState = EquipmentState.DISCOVERED
    node_name: Optional[str] = None
    namespace: Optional[str] = None
    capabilities: List[EquipmentCapability] = field(default_factory=list)
    endpoints: List[EquipmentEndpoint] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    heartbeat_count: int = 0

    def to_dict(self) -> Dict:
        return {
            'equipment_id': self.equipment_id,
            'equipment_type': self.equipment_type.value,
            'state': self.state.value,
            'node_name': self.node_name,
            'namespace': self.namespace,
            'capabilities': [
                {'name': c.name, 'version': c.version, 'parameters': c.parameters}
                for c in self.capabilities
            ],
            'endpoints': [
                {
                    'type': e.endpoint_type,
                    'name': e.name,
                    'message_type': e.message_type,
                    'qos': e.qos_profile
                }
                for e in self.endpoints
            ],
            'metadata': self.metadata,
            'registered_at': self.registered_at,
            'registered_at_iso': datetime.fromtimestamp(self.registered_at).isoformat(),
            'last_heartbeat': self.last_heartbeat,
            'uptime_seconds': time.time() - self.registered_at,
        }


@dataclass
class TopologyNode:
    """Node in the factory topology graph."""
    node_id: str
    node_name: str
    namespace: str
    publishers: List[str] = field(default_factory=list)
    subscribers: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    clients: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)


class DiscoveryServerNode(Node):
    """
    Central discovery server for the factory cell.

    Maintains a registry of all equipment, tracks topology,
    and provides discovery services to other nodes.

    Published Topics:
    - /discovery/equipment_list: List of registered equipment
    - /discovery/topology: Current topology graph
    - /discovery/events: Discovery events (register, deregister, etc.)

    Services:
    - /discovery/register: Register new equipment
    - /discovery/deregister: Deregister equipment
    - /discovery/lookup: Lookup equipment by ID or type
    - /discovery/get_endpoints: Get endpoints for equipment
    - /discovery/get_topology: Get full topology
    """

    def __init__(self):
        super().__init__('discovery_server')

        # Parameters
        self.declare_parameter('heartbeat_timeout_seconds', 10.0)
        self.declare_parameter('discovery_interval_seconds', 5.0)
        self.declare_parameter('publish_interval_seconds', 1.0)
        self.declare_parameter('enable_auto_discovery', True)

        self.heartbeat_timeout = self.get_parameter('heartbeat_timeout_seconds').value
        self.discovery_interval = self.get_parameter('discovery_interval_seconds').value
        self.publish_interval = self.get_parameter('publish_interval_seconds').value
        self.auto_discovery = self.get_parameter('enable_auto_discovery').value

        # Equipment registry
        self.equipment: Dict[str, RegisteredEquipment] = {}
        self.equipment_by_type: Dict[EquipmentType, Set[str]] = defaultdict(set)
        self.equipment_lock = threading.Lock()

        # Topology
        self.topology: Dict[str, TopologyNode] = {}
        self.topic_publishers: Dict[str, Set[str]] = defaultdict(set)
        self.topic_subscribers: Dict[str, Set[str]] = defaultdict(set)

        # Event callbacks
        self.event_callbacks: List[Callable] = []

        # Callback group
        self.cb_group = ReentrantCallbackGroup()

        # QoS profiles
        self.transient_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # Publishers
        self.equipment_list_pub = self.create_publisher(
            String, '/discovery/equipment_list', self.transient_qos
        )
        self.topology_pub = self.create_publisher(
            String, '/discovery/topology', 10
        )
        self.events_pub = self.create_publisher(
            String, '/discovery/events', 10
        )

        # Heartbeat subscriber (equipment sends heartbeats here)
        self.create_subscription(
            String, '/discovery/heartbeat',
            self._on_heartbeat, 10,
            callback_group=self.cb_group
        )

        # Registration subscriber (alternative to service)
        self.create_subscription(
            String, '/discovery/register_request',
            self._on_register_request, 10,
            callback_group=self.cb_group
        )

        # Services
        self.create_service(
            Trigger, '/discovery/register',
            self._srv_register, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, '/discovery/deregister',
            self._srv_deregister, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, '/discovery/lookup',
            self._srv_lookup, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, '/discovery/get_topology',
            self._srv_get_topology, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, '/discovery/force_discovery',
            self._srv_force_discovery, callback_group=self.cb_group
        )

        # Timers
        self.publish_timer = self.create_timer(
            self.publish_interval, self._publish_equipment_list,
            callback_group=self.cb_group
        )
        self.health_timer = self.create_timer(
            self.heartbeat_timeout / 2, self._check_equipment_health,
            callback_group=self.cb_group
        )

        if self.auto_discovery:
            self.discovery_timer = self.create_timer(
                self.discovery_interval, self._discover_ros_graph,
                callback_group=self.cb_group
            )

        self.get_logger().info('Discovery Server initialized')

    def register_equipment(self, equipment_id: str, equipment_type: EquipmentType,
                          capabilities: List[EquipmentCapability] = None,
                          endpoints: List[EquipmentEndpoint] = None,
                          metadata: Dict = None,
                          node_name: str = None,
                          namespace: str = None) -> bool:
        """Register new equipment with the discovery server."""
        with self.equipment_lock:
            if equipment_id in self.equipment:
                # Update existing registration
                equip = self.equipment[equipment_id]
                equip.state = EquipmentState.ACTIVE
                equip.last_heartbeat = time.time()
                if capabilities:
                    equip.capabilities = capabilities
                if endpoints:
                    equip.endpoints = endpoints
                if metadata:
                    equip.metadata.update(metadata)
                self.get_logger().info(f'Updated registration for {equipment_id}')
            else:
                # New registration
                equip = RegisteredEquipment(
                    equipment_id=equipment_id,
                    equipment_type=equipment_type,
                    state=EquipmentState.REGISTERED,
                    node_name=node_name,
                    namespace=namespace,
                    capabilities=capabilities or [],
                    endpoints=endpoints or [],
                    metadata=metadata or {},
                )
                self.equipment[equipment_id] = equip
                self.equipment_by_type[equipment_type].add(equipment_id)
                self.get_logger().info(f'Registered new equipment: {equipment_id} ({equipment_type.value})')

            # Publish event
            self._publish_event('registered', equipment_id, equip.to_dict())

        return True

    def deregister_equipment(self, equipment_id: str) -> bool:
        """Deregister equipment from the discovery server."""
        with self.equipment_lock:
            if equipment_id not in self.equipment:
                return False

            equip = self.equipment[equipment_id]
            equip.state = EquipmentState.DEREGISTERED

            # Remove from type index
            self.equipment_by_type[equip.equipment_type].discard(equipment_id)

            # Publish event before removal
            self._publish_event('deregistered', equipment_id, equip.to_dict())

            del self.equipment[equipment_id]
            self.get_logger().info(f'Deregistered equipment: {equipment_id}')

        return True

    def lookup_equipment(self, equipment_id: str = None,
                        equipment_type: EquipmentType = None,
                        capability: str = None) -> List[RegisteredEquipment]:
        """Lookup equipment by ID, type, or capability."""
        results = []

        with self.equipment_lock:
            if equipment_id:
                if equipment_id in self.equipment:
                    results.append(self.equipment[equipment_id])
            elif equipment_type:
                for eq_id in self.equipment_by_type.get(equipment_type, []):
                    if eq_id in self.equipment:
                        results.append(self.equipment[eq_id])
            elif capability:
                for equip in self.equipment.values():
                    if any(c.name == capability for c in equip.capabilities):
                        results.append(equip)
            else:
                results = list(self.equipment.values())

        return results

    def get_endpoints_for_equipment(self, equipment_id: str,
                                    endpoint_type: str = None) -> List[EquipmentEndpoint]:
        """Get communication endpoints for equipment."""
        with self.equipment_lock:
            if equipment_id not in self.equipment:
                return []

            endpoints = self.equipment[equipment_id].endpoints

            if endpoint_type:
                endpoints = [e for e in endpoints if e.endpoint_type == endpoint_type]

            return endpoints

    def _on_heartbeat(self, msg: String):
        """Handle heartbeat from equipment."""
        try:
            data = json.loads(msg.data)
            equipment_id = data.get('equipment_id')

            if not equipment_id:
                return

            with self.equipment_lock:
                if equipment_id in self.equipment:
                    equip = self.equipment[equipment_id]
                    equip.last_heartbeat = time.time()
                    equip.heartbeat_count += 1

                    if equip.state == EquipmentState.INACTIVE:
                        equip.state = EquipmentState.ACTIVE
                        self._publish_event('activated', equipment_id, equip.to_dict())

                    # Update any provided metadata
                    if 'metadata' in data:
                        equip.metadata.update(data['metadata'])

                else:
                    # Auto-register on first heartbeat
                    eq_type = EquipmentType(data.get('equipment_type', 'unknown'))
                    self.register_equipment(
                        equipment_id=equipment_id,
                        equipment_type=eq_type,
                        metadata=data.get('metadata', {}),
                        node_name=data.get('node_name'),
                        namespace=data.get('namespace'),
                    )

        except (json.JSONDecodeError, ValueError) as e:
            self.get_logger().debug(f'Invalid heartbeat: {e}')

    def _on_register_request(self, msg: String):
        """Handle registration request via topic."""
        try:
            data = json.loads(msg.data)
            equipment_id = data.get('equipment_id')
            eq_type = EquipmentType(data.get('equipment_type', 'unknown'))

            capabilities = [
                EquipmentCapability(
                    name=c.get('name'),
                    version=c.get('version', '1.0'),
                    parameters=c.get('parameters', {})
                )
                for c in data.get('capabilities', [])
            ]

            endpoints = [
                EquipmentEndpoint(
                    endpoint_type=e.get('type'),
                    name=e.get('name'),
                    message_type=e.get('message_type'),
                    qos_profile=e.get('qos')
                )
                for e in data.get('endpoints', [])
            ]

            self.register_equipment(
                equipment_id=equipment_id,
                equipment_type=eq_type,
                capabilities=capabilities,
                endpoints=endpoints,
                metadata=data.get('metadata', {}),
                node_name=data.get('node_name'),
                namespace=data.get('namespace'),
            )

        except (json.JSONDecodeError, ValueError) as e:
            self.get_logger().error(f'Invalid registration request: {e}')

    def _check_equipment_health(self):
        """Check equipment health based on heartbeats."""
        now = time.time()

        with self.equipment_lock:
            for equipment_id, equip in list(self.equipment.items()):
                if equip.state == EquipmentState.DEREGISTERED:
                    continue

                elapsed = now - equip.last_heartbeat

                if elapsed > self.heartbeat_timeout * 2:
                    # Mark as offline
                    if equip.state != EquipmentState.OFFLINE:
                        equip.state = EquipmentState.OFFLINE
                        self.get_logger().warn(f'Equipment offline: {equipment_id}')
                        self._publish_event('offline', equipment_id, equip.to_dict())

                elif elapsed > self.heartbeat_timeout:
                    # Mark as inactive
                    if equip.state == EquipmentState.ACTIVE:
                        equip.state = EquipmentState.INACTIVE
                        self.get_logger().info(f'Equipment inactive: {equipment_id}')
                        self._publish_event('inactive', equipment_id, equip.to_dict())

    def _discover_ros_graph(self):
        """Discover nodes and topics from ROS2 graph."""
        try:
            # Get all node names
            node_names_and_namespaces = self.get_node_names_and_namespaces()

            for node_name, namespace in node_names_and_namespaces:
                full_name = f'{namespace}/{node_name}' if namespace != '/' else f'/{node_name}'

                # Skip our own node and system nodes
                if node_name in ['discovery_server', 'ros2cli']:
                    continue

                # Get publishers for this node
                try:
                    pubs = self.get_publisher_names_and_types_by_node(node_name, namespace)
                    subs = self.get_subscriber_names_and_types_by_node(node_name, namespace)
                    services = self.get_service_names_and_types_by_node(node_name, namespace)
                except Exception:
                    continue

                # Update topology
                if full_name not in self.topology:
                    self.topology[full_name] = TopologyNode(
                        node_id=full_name,
                        node_name=node_name,
                        namespace=namespace,
                    )

                topo_node = self.topology[full_name]
                topo_node.publishers = [p[0] for p in pubs]
                topo_node.subscribers = [s[0] for s in subs]
                topo_node.services = [s[0] for s in services]

                # Update topic mappings
                for topic, _ in pubs:
                    self.topic_publishers[topic].add(full_name)
                for topic, _ in subs:
                    self.topic_subscribers[topic].add(full_name)

                # Auto-detect equipment type from node name
                self._auto_register_from_node(node_name, namespace, pubs, subs)

        except Exception as e:
            self.get_logger().debug(f'Graph discovery error: {e}')

    def _auto_register_from_node(self, node_name: str, namespace: str,
                                  pubs: List, subs: List):
        """Auto-register equipment based on node naming patterns."""
        # Detect equipment type from node name
        eq_type = EquipmentType.UNKNOWN
        equipment_id = None

        name_lower = node_name.lower()

        if 'alvik' in name_lower or 'agv' in name_lower:
            eq_type = EquipmentType.AGV
            equipment_id = node_name.replace('alvik_driver_', '').replace('alvik_sim_', '')
        elif 'ned2' in name_lower or 'xarm' in name_lower:
            eq_type = EquipmentType.ROBOT_ARM
            equipment_id = node_name
        elif 'grbl' in name_lower or 'cnc' in name_lower:
            eq_type = EquipmentType.CNC
            equipment_id = node_name
        elif 'laser' in name_lower:
            eq_type = EquipmentType.LASER
            equipment_id = node_name
        elif 'formlabs' in name_lower or 'sla' in name_lower:
            eq_type = EquipmentType.SLA_PRINTER
            equipment_id = node_name
        elif 'camera' in name_lower or 'vision' in name_lower:
            eq_type = EquipmentType.CAMERA
            equipment_id = node_name

        if equipment_id and eq_type != EquipmentType.UNKNOWN:
            # Build endpoints from discovered topics
            endpoints = []
            for topic, types in pubs:
                endpoints.append(EquipmentEndpoint(
                    endpoint_type='publisher',
                    name=topic,
                    message_type=types[0] if types else 'unknown',
                ))
            for topic, types in subs:
                endpoints.append(EquipmentEndpoint(
                    endpoint_type='subscriber',
                    name=topic,
                    message_type=types[0] if types else 'unknown',
                ))

            # Register if not already registered
            with self.equipment_lock:
                if equipment_id not in self.equipment:
                    self.register_equipment(
                        equipment_id=equipment_id,
                        equipment_type=eq_type,
                        endpoints=endpoints,
                        node_name=node_name,
                        namespace=namespace,
                        metadata={'auto_discovered': True},
                    )

    def _publish_equipment_list(self):
        """Publish current equipment list."""
        with self.equipment_lock:
            equipment_list = {
                'timestamp': time.time(),
                'timestamp_iso': datetime.now().isoformat(),
                'equipment_count': len(self.equipment),
                'equipment': {
                    eq_id: eq.to_dict()
                    for eq_id, eq in self.equipment.items()
                },
                'by_type': {
                    eq_type.value: list(eq_ids)
                    for eq_type, eq_ids in self.equipment_by_type.items()
                    if eq_ids
                },
            }

        msg = String()
        msg.data = json.dumps(equipment_list)
        self.equipment_list_pub.publish(msg)

    def _publish_event(self, event_type: str, equipment_id: str, data: Dict = None):
        """Publish discovery event."""
        event = {
            'event_type': event_type,
            'equipment_id': equipment_id,
            'timestamp': time.time(),
            'timestamp_iso': datetime.now().isoformat(),
            'data': data or {},
        }

        msg = String()
        msg.data = json.dumps(event)
        self.events_pub.publish(msg)

        # Call registered callbacks
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                self.get_logger().error(f'Event callback error: {e}')

    # Services
    def _srv_register(self, request, response):
        """Register service (use topic for full data)."""
        response.success = True
        response.message = "Use /discovery/register_request topic for registration"
        return response

    def _srv_deregister(self, request, response):
        """Deregister service."""
        response.success = True
        response.message = "Use equipment_id in request"
        return response

    def _srv_lookup(self, request, response):
        """Lookup service."""
        equipment_list = self.lookup_equipment()
        response.success = True
        response.message = json.dumps([e.to_dict() for e in equipment_list])
        return response

    def _srv_get_topology(self, request, response):
        """Get topology service."""
        topology_data = {
            'nodes': {
                node_id: {
                    'name': node.node_name,
                    'namespace': node.namespace,
                    'publishers': node.publishers,
                    'subscribers': node.subscribers,
                    'services': node.services,
                }
                for node_id, node in self.topology.items()
            },
            'topics': {
                topic: {
                    'publishers': list(pubs),
                    'subscribers': list(self.topic_subscribers.get(topic, [])),
                }
                for topic, pubs in self.topic_publishers.items()
            },
        }
        response.success = True
        response.message = json.dumps(topology_data)
        return response

    def _srv_force_discovery(self, request, response):
        """Force immediate discovery."""
        self._discover_ros_graph()
        response.success = True
        response.message = f"Discovery complete. Found {len(self.equipment)} equipment."
        return response


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    node = DiscoveryServerNode()

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
