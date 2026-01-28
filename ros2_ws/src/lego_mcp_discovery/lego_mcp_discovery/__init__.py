"""
LEGO MCP Discovery Package

Dynamic equipment discovery, registration, and topology management
for the factory cell.

Components:
- discovery_server: Central discovery service
- bandwidth_optimizer: Network bandwidth optimization
- equipment_registry: Equipment registration and lookup
- topology_manager: Network topology management
- health_monitor: Equipment health monitoring

LEGO MCP Manufacturing System v7.0
"""

__version__ = "7.0.0"

from .discovery_server import (
    DiscoveryServerNode,
    EquipmentType,
    EquipmentState,
    RegisteredEquipment,
    EquipmentCapability,
    EquipmentEndpoint,
)
from .bandwidth_optimizer import (
    BandwidthOptimizerNode,
    BandwidthPriority,
    TopicStats,
)

__all__ = [
    'DiscoveryServerNode',
    'EquipmentType',
    'EquipmentState',
    'RegisteredEquipment',
    'EquipmentCapability',
    'EquipmentEndpoint',
    'BandwidthOptimizerNode',
    'BandwidthPriority',
    'TopicStats',
]
