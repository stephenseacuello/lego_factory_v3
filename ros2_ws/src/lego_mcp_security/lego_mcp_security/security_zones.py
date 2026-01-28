#!/usr/bin/env python3
"""
IEC 62443 Security Zone Manager

Implements ISA/IEC 62443 compliant security zones and conduits for
industrial control system security.

Industry 4.0/5.0 Architecture - Defense in Depth
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import json


class ConduitType(Enum):
    """Types of connections between zones."""
    DATA_DIODE = "data_diode"         # One-way only
    FIREWALL = "firewall"             # Bi-directional with rules
    DMZ_PROXY = "dmz_proxy"           # Through DMZ
    VPN = "vpn"                       # Encrypted tunnel
    AIR_GAP = "air_gap"               # No electronic connection


@dataclass
class SecurityConduit:
    """Connection between two security zones."""
    conduit_id: str
    source_zone: str
    dest_zone: str
    conduit_type: ConduitType
    allowed_protocols: List[str] = field(default_factory=list)
    allowed_ports: List[int] = field(default_factory=list)
    encryption_required: bool = True
    authentication_required: bool = True
    max_bandwidth_mbps: float = 100.0
    logging_enabled: bool = True


@dataclass
class ZoneDefinition:
    """IEC 62443 Security Zone Definition."""
    zone_id: str
    zone_name: str
    description: str
    security_level_target: int  # SL-T (1-4)
    security_level_achieved: int = 0  # SL-A
    security_level_capability: int = 0  # SL-C
    assets: List[str] = field(default_factory=list)
    parent_zone: Optional[str] = None
    conduits: List[str] = field(default_factory=list)


class IEC62443ZoneManager:
    """
    IEC 62443 Security Zone Manager.

    Manages security zones and conduits according to IEC 62443 standard:
    - Zone definition and hierarchy
    - Conduit management between zones
    - Security level assessment
    - Access control enforcement

    LEGO MCP Zone Architecture:
    ┌────────────────────────────────────────────────────────────┐
    │                      ENTERPRISE ZONE (SL-1)                │
    │  Cloud Services, Analytics, External APIs                  │
    └───────────────────────────┬────────────────────────────────┘
                                │ DMZ Conduit
    ┌───────────────────────────▼────────────────────────────────┐
    │                        DMZ ZONE (SL-2)                     │
    │  Web Server, API Gateway, Rosbridge                        │
    └───────────────────────────┬────────────────────────────────┘
                                │ Firewall Conduit
    ┌───────────────────────────▼────────────────────────────────┐
    │                       MES ZONE (SL-2)                      │
    │  Dashboard, Scheduling, Quality, Digital Twin              │
    └───────────────────────────┬────────────────────────────────┘
                                │ Firewall Conduit
    ┌───────────────────────────▼────────────────────────────────┐
    │                   SUPERVISORY ZONE (SL-2)                  │
    │  Orchestrator, AGV Fleet Manager, Vision System            │
    └───────────────────────────┬────────────────────────────────┘
                                │ Firewall Conduit
    ┌───────────────────────────▼────────────────────────────────┐
    │                     CONTROL ZONE (SL-3)                    │
    │  Equipment Nodes (CNC, Laser, Printers, Robots)            │
    └───────────────────────────┬────────────────────────────────┘
                                │ Data Diode (one-way up)
    ┌───────────────────────────▼────────────────────────────────┐
    │                     SAFETY ZONE (SL-4)                     │
    │  E-Stop, Watchdog, Safety PLCs                             │
    │  (Isolated, highest protection)                            │
    └────────────────────────────────────────────────────────────┘
    """

    def __init__(self):
        """Initialize the zone manager with default LEGO MCP zones."""
        self._zones: Dict[str, ZoneDefinition] = {}
        self._conduits: Dict[str, SecurityConduit] = {}
        self._initialize_default_zones()

    def _initialize_default_zones(self):
        """Create default LEGO MCP security zones per IEC 62443."""

        # Zone 0: Safety Zone (SL-4) - Highest security
        self.create_zone(ZoneDefinition(
            zone_id="safety",
            zone_name="Safety Zone",
            description="Safety-critical systems: E-stop, watchdog, safety PLCs",
            security_level_target=4,
            security_level_achieved=4,
            security_level_capability=4,
            assets=[
                "safety_lifecycle_node",
                "safety_node",
                "watchdog_node",
                "e_stop_relay",
            ],
        ))

        # Zone 1: Control Zone (SL-3)
        self.create_zone(ZoneDefinition(
            zone_id="control",
            zone_name="Control Zone",
            description="Equipment controllers: CNC, laser, printers, robots",
            security_level_target=3,
            security_level_achieved=3,
            security_level_capability=3,
            assets=[
                "grbl_node",
                "tinyg_node",
                "formlabs_node",
                "bambu_node",
                "ned2_interface",
                "xarm_interface",
            ],
        ))

        # Zone 2: Supervisory Zone (SL-2)
        self.create_zone(ZoneDefinition(
            zone_id="supervisory",
            zone_name="Supervisory Zone",
            description="Coordination: Orchestrator, AGV fleet, vision",
            security_level_target=2,
            security_level_achieved=2,
            security_level_capability=3,
            assets=[
                "lego_mcp_orchestrator",
                "orchestrator_lifecycle_node",
                "agv_fleet_manager",
                "vision_system",
                "lego_mcp_supervisor",
            ],
        ))

        # Zone 3: MES Zone (SL-2)
        self.create_zone(ZoneDefinition(
            zone_id="mes",
            zone_name="MES Zone",
            description="Manufacturing execution: Dashboard, scheduling, quality",
            security_level_target=2,
            security_level_achieved=2,
            security_level_capability=2,
            assets=[
                "flask_dashboard",
                "scheduling_service",
                "quality_service",
                "digital_twin_service",
            ],
        ))

        # Zone 4: DMZ (SL-2)
        self.create_zone(ZoneDefinition(
            zone_id="dmz",
            zone_name="DMZ Zone",
            description="Demilitarized zone: External interfaces",
            security_level_target=2,
            security_level_achieved=2,
            security_level_capability=2,
            assets=[
                "rosbridge_websocket",
                "opcua_server",
                "mtconnect_adapter",
            ],
        ))

        # Zone 5: Enterprise Zone (SL-1)
        self.create_zone(ZoneDefinition(
            zone_id="enterprise",
            zone_name="Enterprise Zone",
            description="Business systems: Cloud, analytics, APIs",
            security_level_target=1,
            security_level_achieved=1,
            security_level_capability=1,
            assets=[
                "cloud_connector",
                "erp_integration",
                "analytics_service",
            ],
        ))

        # Create conduits between zones
        self._create_default_conduits()

    def _create_default_conduits(self):
        """Create default conduits between zones."""

        # Safety ← Control (data diode, safety can only receive)
        self.create_conduit(SecurityConduit(
            conduit_id="safety_control",
            source_zone="control",
            dest_zone="safety",
            conduit_type=ConduitType.DATA_DIODE,
            allowed_protocols=["DDS"],
            encryption_required=True,
            authentication_required=True,
        ))

        # Control ↔ Supervisory
        self.create_conduit(SecurityConduit(
            conduit_id="control_supervisory",
            source_zone="control",
            dest_zone="supervisory",
            conduit_type=ConduitType.FIREWALL,
            allowed_protocols=["DDS", "ROS2"],
            allowed_ports=[7400, 7401, 7402],  # DDS default ports
            encryption_required=True,
            authentication_required=True,
        ))

        # Supervisory ↔ MES
        self.create_conduit(SecurityConduit(
            conduit_id="supervisory_mes",
            source_zone="supervisory",
            dest_zone="mes",
            conduit_type=ConduitType.FIREWALL,
            allowed_protocols=["HTTP", "WebSocket", "DDS"],
            allowed_ports=[5000, 9090, 7400],
            encryption_required=True,
            authentication_required=True,
        ))

        # MES ↔ DMZ
        self.create_conduit(SecurityConduit(
            conduit_id="mes_dmz",
            source_zone="mes",
            dest_zone="dmz",
            conduit_type=ConduitType.DMZ_PROXY,
            allowed_protocols=["HTTPS", "OPC-UA", "MQTT"],
            allowed_ports=[443, 4840, 8883],
            encryption_required=True,
            authentication_required=True,
        ))

        # DMZ ↔ Enterprise
        self.create_conduit(SecurityConduit(
            conduit_id="dmz_enterprise",
            source_zone="dmz",
            dest_zone="enterprise",
            conduit_type=ConduitType.FIREWALL,
            allowed_protocols=["HTTPS"],
            allowed_ports=[443],
            encryption_required=True,
            authentication_required=True,
        ))

    def create_zone(self, zone: ZoneDefinition) -> bool:
        """Create or update a security zone."""
        self._zones[zone.zone_id] = zone
        return True

    def create_conduit(self, conduit: SecurityConduit) -> bool:
        """Create or update a conduit between zones."""
        if conduit.source_zone not in self._zones:
            return False
        if conduit.dest_zone not in self._zones:
            return False

        self._conduits[conduit.conduit_id] = conduit

        # Update zone conduit references
        self._zones[conduit.source_zone].conduits.append(conduit.conduit_id)
        self._zones[conduit.dest_zone].conduits.append(conduit.conduit_id)

        return True

    def check_communication_allowed(
        self,
        source_zone_id: str,
        dest_zone_id: str,
        protocol: str = "DDS",
    ) -> Tuple[bool, Optional[SecurityConduit]]:
        """
        Check if communication between zones is allowed.

        Args:
            source_zone_id: Source zone ID
            dest_zone_id: Destination zone ID
            protocol: Protocol being used

        Returns:
            Tuple of (allowed, conduit) where conduit is the matching conduit if allowed
        """
        # Same zone always allowed
        if source_zone_id == dest_zone_id:
            return True, None

        # Find conduit
        for conduit in self._conduits.values():
            if conduit.source_zone == source_zone_id and conduit.dest_zone == dest_zone_id:
                if protocol in conduit.allowed_protocols:
                    return True, conduit
                return False, conduit

            # Check reverse direction for bidirectional conduits
            if conduit.conduit_type != ConduitType.DATA_DIODE:
                if conduit.source_zone == dest_zone_id and conduit.dest_zone == source_zone_id:
                    if protocol in conduit.allowed_protocols:
                        return True, conduit

        return False, None

    def get_zone(self, zone_id: str) -> Optional[ZoneDefinition]:
        """Get a zone definition."""
        return self._zones.get(zone_id)

    def get_zone_for_asset(self, asset_name: str) -> Optional[ZoneDefinition]:
        """Find which zone an asset belongs to."""
        for zone in self._zones.values():
            if asset_name in zone.assets:
                return zone
        return None

    def add_asset_to_zone(self, zone_id: str, asset_name: str) -> bool:
        """Add an asset to a zone."""
        zone = self._zones.get(zone_id)
        if zone and asset_name not in zone.assets:
            zone.assets.append(asset_name)
            return True
        return False

    def get_security_level(self, zone_id: str) -> int:
        """Get the target security level for a zone."""
        zone = self._zones.get(zone_id)
        return zone.security_level_target if zone else 0

    def assess_zone_compliance(self, zone_id: str) -> Dict:
        """
        Assess zone compliance with security level requirements.

        Returns:
            Dictionary with compliance assessment
        """
        zone = self._zones.get(zone_id)
        if not zone:
            return {"error": "Zone not found"}

        gap = zone.security_level_target - zone.security_level_achieved
        compliant = gap <= 0

        return {
            "zone_id": zone_id,
            "zone_name": zone.zone_name,
            "sl_target": zone.security_level_target,
            "sl_achieved": zone.security_level_achieved,
            "sl_capability": zone.security_level_capability,
            "compliant": compliant,
            "gap": max(0, gap),
            "asset_count": len(zone.assets),
            "conduit_count": len(zone.conduits),
        }

    def export_zone_topology(self) -> Dict:
        """Export zone topology for visualization."""
        return {
            "zones": {
                zone_id: {
                    "name": zone.zone_name,
                    "sl_target": zone.security_level_target,
                    "assets": zone.assets,
                }
                for zone_id, zone in self._zones.items()
            },
            "conduits": {
                cid: {
                    "source": c.source_zone,
                    "dest": c.dest_zone,
                    "type": c.conduit_type.value,
                    "protocols": c.allowed_protocols,
                }
                for cid, c in self._conduits.items()
            },
        }
