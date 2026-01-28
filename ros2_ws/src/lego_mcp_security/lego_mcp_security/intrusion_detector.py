#!/usr/bin/env python3
"""
Intrusion Detection System for LEGO MCP ROS2 Network

Monitors DDS traffic and node behavior for security anomalies:
- Unauthorized node registration
- Unusual topic access patterns
- Protocol violations
- Denial of service indicators
- Zone boundary violations

Industry 4.0/5.0 Architecture - IEC 62443 FR5 (Restricted Data Flow)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Callable
from collections import deque
import threading
import statistics


class ThreatLevel(Enum):
    """Threat classification levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class DetectionType(Enum):
    """Types of detections."""
    UNAUTHORIZED_NODE = "unauthorized_node"
    TOPIC_SCAN = "topic_scan"
    SERVICE_SCAN = "service_scan"
    RATE_ANOMALY = "rate_anomaly"
    ZONE_VIOLATION = "zone_violation"
    PROTOCOL_VIOLATION = "protocol_violation"
    REPLAY_ATTACK = "replay_attack"
    DOS_INDICATOR = "dos_indicator"
    BRUTE_FORCE = "brute_force"


@dataclass
class Detection:
    """Security detection record."""
    detection_id: str
    timestamp: datetime
    detection_type: DetectionType
    threat_level: ThreatLevel
    source_node: str
    source_ip: Optional[str]
    target: str
    description: str
    evidence: Dict = field(default_factory=dict)
    mitigated: bool = False


@dataclass
class NodeProfile:
    """Behavioral profile for a node."""
    node_name: str
    first_seen: datetime
    last_seen: datetime
    authorized: bool = False
    expected_topics_pub: Set[str] = field(default_factory=set)
    expected_topics_sub: Set[str] = field(default_factory=set)
    expected_services: Set[str] = field(default_factory=set)
    observed_topics_pub: Set[str] = field(default_factory=set)
    observed_topics_sub: Set[str] = field(default_factory=set)
    observed_services: Set[str] = field(default_factory=set)
    message_rates: Dict[str, deque] = field(default_factory=dict)
    zone: str = ""


class IntrusionDetector:
    """
    Intrusion Detection System for ROS2/DDS.

    Provides:
    - Node registration monitoring
    - Topic/service access monitoring
    - Rate-based anomaly detection
    - Zone boundary enforcement
    - Real-time alerting

    Usage:
        detector = IntrusionDetector()
        detector.register_authorized_node("safety_node", "safety", {...})
        detector.on_node_discovered("unknown_node")  # Triggers alert
    """

    def __init__(
        self,
        rate_window_seconds: int = 60,
        rate_anomaly_threshold: float = 3.0,  # Standard deviations
        dos_rate_threshold: int = 1000,  # Messages per second
        scan_threshold: int = 10,  # Topics accessed in short time
        scan_window_seconds: int = 5,
    ):
        """
        Initialize the intrusion detector.

        Args:
            rate_window_seconds: Window for rate calculations
            rate_anomaly_threshold: Std devs for anomaly detection
            dos_rate_threshold: Rate indicating DoS
            scan_threshold: Number of accesses indicating scan
            scan_window_seconds: Window for scan detection
        """
        self._rate_window = rate_window_seconds
        self._rate_threshold = rate_anomaly_threshold
        self._dos_threshold = dos_rate_threshold
        self._scan_threshold = scan_threshold
        self._scan_window = scan_window_seconds

        self._node_profiles: Dict[str, NodeProfile] = {}
        self._detections: List[Detection] = []
        self._lock = threading.RLock()
        self._detection_count = 0

        # Alert handlers
        self._alert_handlers: List[Callable[[Detection], None]] = []

        # Authorized nodes (loaded from security manager)
        self._authorized_nodes: Set[str] = set()

        # Recent activity tracking for scan detection
        self._recent_accesses: Dict[str, deque] = {}

    def register_authorized_node(
        self,
        node_name: str,
        zone: str,
        expected_pubs: Optional[List[str]] = None,
        expected_subs: Optional[List[str]] = None,
        expected_services: Optional[List[str]] = None,
    ):
        """
        Register an authorized node with expected behavior.

        Args:
            node_name: Node name
            zone: Security zone
            expected_pubs: Expected publish topics
            expected_subs: Expected subscribe topics
            expected_services: Expected services
        """
        with self._lock:
            self._authorized_nodes.add(node_name)

            profile = NodeProfile(
                node_name=node_name,
                first_seen=datetime.now(),
                last_seen=datetime.now(),
                authorized=True,
                expected_topics_pub=set(expected_pubs or []),
                expected_topics_sub=set(expected_subs or []),
                expected_services=set(expected_services or []),
                zone=zone,
            )
            self._node_profiles[node_name] = profile

    def add_alert_handler(self, handler: Callable[[Detection], None]):
        """Add a handler for detection alerts."""
        self._alert_handlers.append(handler)

    def on_node_discovered(self, node_name: str, node_ip: Optional[str] = None):
        """
        Called when a new node is discovered on the network.

        Args:
            node_name: Discovered node name
            node_ip: Optional IP address
        """
        with self._lock:
            if node_name not in self._authorized_nodes:
                detection = self._create_detection(
                    detection_type=DetectionType.UNAUTHORIZED_NODE,
                    threat_level=ThreatLevel.HIGH,
                    source_node=node_name,
                    source_ip=node_ip,
                    target="ros2_network",
                    description=f"Unauthorized node '{node_name}' discovered on network",
                    evidence={"node_name": node_name, "ip": node_ip},
                )
                self._trigger_alert(detection)

            # Update or create profile
            if node_name not in self._node_profiles:
                self._node_profiles[node_name] = NodeProfile(
                    node_name=node_name,
                    first_seen=datetime.now(),
                    last_seen=datetime.now(),
                    authorized=node_name in self._authorized_nodes,
                )
            else:
                self._node_profiles[node_name].last_seen = datetime.now()

    def on_topic_access(
        self,
        node_name: str,
        topic: str,
        access_type: str,  # "publish" or "subscribe"
        source_zone: Optional[str] = None,
    ):
        """
        Called when a node accesses a topic.

        Args:
            node_name: Node accessing the topic
            topic: Topic being accessed
            access_type: "publish" or "subscribe"
            source_zone: Zone of the accessing node
        """
        with self._lock:
            profile = self._node_profiles.get(node_name)
            now = datetime.now()

            # Track access for scan detection
            if node_name not in self._recent_accesses:
                self._recent_accesses[node_name] = deque(maxlen=100)
            self._recent_accesses[node_name].append((now, topic))

            # Check for topic scan
            recent = [
                t for ts, t in self._recent_accesses[node_name]
                if (now - ts).total_seconds() < self._scan_window
            ]
            unique_topics = len(set(recent))
            if unique_topics >= self._scan_threshold:
                detection = self._create_detection(
                    detection_type=DetectionType.TOPIC_SCAN,
                    threat_level=ThreatLevel.MEDIUM,
                    source_node=node_name,
                    target="topic_namespace",
                    description=f"Node '{node_name}' accessed {unique_topics} unique topics in {self._scan_window}s",
                    evidence={"topics": list(set(recent))[:20]},
                )
                self._trigger_alert(detection)

            if profile:
                profile.last_seen = now

                # Check for unexpected access
                if access_type == "publish":
                    profile.observed_topics_pub.add(topic)
                    if profile.expected_topics_pub and topic not in profile.expected_topics_pub:
                        detection = self._create_detection(
                            detection_type=DetectionType.ZONE_VIOLATION,
                            threat_level=ThreatLevel.MEDIUM,
                            source_node=node_name,
                            target=topic,
                            description=f"Node '{node_name}' publishing to unexpected topic '{topic}'",
                        )
                        self._trigger_alert(detection)

                elif access_type == "subscribe":
                    profile.observed_topics_sub.add(topic)
                    if profile.expected_topics_sub and topic not in profile.expected_topics_sub:
                        detection = self._create_detection(
                            detection_type=DetectionType.ZONE_VIOLATION,
                            threat_level=ThreatLevel.LOW,
                            source_node=node_name,
                            target=topic,
                            description=f"Node '{node_name}' subscribing to unexpected topic '{topic}'",
                        )
                        self._trigger_alert(detection)

    def on_message_received(
        self,
        node_name: str,
        topic: str,
        message_size: int,
        timestamp: Optional[datetime] = None,
    ):
        """
        Called when a message is received (for rate monitoring).

        Args:
            node_name: Publishing node
            topic: Topic
            message_size: Size in bytes
            timestamp: Message timestamp
        """
        with self._lock:
            profile = self._node_profiles.get(node_name)
            now = timestamp or datetime.now()

            if profile:
                # Track message rate
                rate_key = f"{node_name}:{topic}"
                if rate_key not in profile.message_rates:
                    profile.message_rates[rate_key] = deque(maxlen=1000)

                profile.message_rates[rate_key].append(now)

                # Calculate current rate
                window_start = now - timedelta(seconds=self._rate_window)
                recent = [
                    ts for ts in profile.message_rates[rate_key]
                    if ts > window_start
                ]
                rate = len(recent) / self._rate_window

                # Check for DoS
                if rate > self._dos_threshold:
                    detection = self._create_detection(
                        detection_type=DetectionType.DOS_INDICATOR,
                        threat_level=ThreatLevel.CRITICAL,
                        source_node=node_name,
                        target=topic,
                        description=f"Possible DoS: {rate:.0f} msg/s from '{node_name}' on '{topic}'",
                        evidence={"rate": rate, "threshold": self._dos_threshold},
                    )
                    self._trigger_alert(detection)

    def on_authentication_failure(
        self,
        node_name: str,
        source_ip: Optional[str] = None,
        details: Optional[Dict] = None,
    ):
        """
        Called on authentication failure (brute force detection).

        Args:
            node_name: Node attempting authentication
            source_ip: Source IP if available
            details: Additional details
        """
        with self._lock:
            # Track auth failures
            key = f"auth_fail:{node_name}"
            if key not in self._recent_accesses:
                self._recent_accesses[key] = deque(maxlen=100)

            now = datetime.now()
            self._recent_accesses[key].append(now)

            # Check for brute force
            recent = [
                ts for ts in self._recent_accesses[key]
                if (now - ts).total_seconds() < 60
            ]
            if len(recent) >= 5:
                detection = self._create_detection(
                    detection_type=DetectionType.BRUTE_FORCE,
                    threat_level=ThreatLevel.HIGH,
                    source_node=node_name,
                    source_ip=source_ip,
                    target="authentication",
                    description=f"Brute force attempt: {len(recent)} failures from '{node_name}' in 60s",
                    evidence={"failure_count": len(recent), "details": details},
                )
                self._trigger_alert(detection)

    def on_zone_crossing(
        self,
        source_node: str,
        source_zone: str,
        dest_zone: str,
        resource: str,
        allowed: bool,
    ):
        """
        Called when cross-zone communication occurs.

        Args:
            source_node: Node initiating communication
            source_zone: Source security zone
            dest_zone: Destination security zone
            resource: Resource being accessed
            allowed: Whether the crossing was allowed
        """
        if not allowed:
            with self._lock:
                detection = self._create_detection(
                    detection_type=DetectionType.ZONE_VIOLATION,
                    threat_level=ThreatLevel.HIGH,
                    source_node=source_node,
                    target=resource,
                    description=f"Unauthorized zone crossing: {source_zone} -> {dest_zone}",
                    evidence={
                        "source_zone": source_zone,
                        "dest_zone": dest_zone,
                        "resource": resource,
                    },
                )
                self._trigger_alert(detection)

    def _create_detection(
        self,
        detection_type: DetectionType,
        threat_level: ThreatLevel,
        source_node: str,
        target: str,
        description: str,
        source_ip: Optional[str] = None,
        evidence: Optional[Dict] = None,
    ) -> Detection:
        """Create a detection record."""
        self._detection_count += 1

        detection = Detection(
            detection_id=f"DET-{self._detection_count:06d}",
            timestamp=datetime.now(),
            detection_type=detection_type,
            threat_level=threat_level,
            source_node=source_node,
            source_ip=source_ip,
            target=target,
            description=description,
            evidence=evidence or {},
        )

        self._detections.append(detection)
        return detection

    def _trigger_alert(self, detection: Detection):
        """Trigger alert handlers."""
        for handler in self._alert_handlers:
            try:
                handler(detection)
            except Exception as e:
                print(f"Alert handler error: {e}")

    def get_detections(
        self,
        min_threat_level: Optional[ThreatLevel] = None,
        detection_type: Optional[DetectionType] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Detection]:
        """
        Get detection records.

        Args:
            min_threat_level: Minimum threat level filter
            detection_type: Filter by detection type
            since: Only detections after this time
            limit: Maximum number to return

        Returns:
            List of Detection records
        """
        with self._lock:
            results = []
            for det in reversed(self._detections):
                if len(results) >= limit:
                    break
                if min_threat_level and det.threat_level.value < min_threat_level.value:
                    continue
                if detection_type and det.detection_type != detection_type:
                    continue
                if since and det.timestamp < since:
                    continue
                results.append(det)
            return results

    def get_node_profile(self, node_name: str) -> Optional[NodeProfile]:
        """Get the behavioral profile for a node."""
        return self._node_profiles.get(node_name)

    def get_statistics(self) -> Dict:
        """Get IDS statistics."""
        with self._lock:
            threat_counts = {}
            type_counts = {}

            for det in self._detections:
                threat_counts[det.threat_level.name] = threat_counts.get(det.threat_level.name, 0) + 1
                type_counts[det.detection_type.value] = type_counts.get(det.detection_type.value, 0) + 1

            return {
                "total_detections": len(self._detections),
                "authorized_nodes": len(self._authorized_nodes),
                "profiled_nodes": len(self._node_profiles),
                "by_threat_level": threat_counts,
                "by_type": type_counts,
                "unmitigated": len([d for d in self._detections if not d.mitigated]),
            }
