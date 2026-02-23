"""
Cloud-Edge Synchronization Service.

Implements hybrid cloud-edge architecture with real-time synchronization
for manufacturing environments supporting:
- Offline-first operation at edge
- Conflict resolution (CRDT-based)
- Bandwidth-efficient delta sync
- Priority-based data tiering
- Store-and-forward for intermittent connectivity
- Edge-to-cloud and cloud-to-edge sync
- Multi-site federation

Architecture aligns with:
- ISA-95/IEC 62264 (Enterprise-Control Integration)
- Industrial Internet Consortium (IIC) Architecture
- AWS IoT Greengrass / Azure IoT Edge patterns
"""

import asyncio
import hashlib
import json
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """Data synchronization direction."""
    EDGE_TO_CLOUD = "edge_to_cloud"
    CLOUD_TO_EDGE = "cloud_to_edge"
    BIDIRECTIONAL = "bidirectional"


class SyncPriority(Enum):
    """Synchronization priority levels."""
    CRITICAL = 1  # Safety, alarms - immediate
    HIGH = 2  # Production data - seconds
    MEDIUM = 3  # Quality data - minutes
    LOW = 4  # Analytics - hours
    BATCH = 5  # Historical - daily


class ConflictResolution(Enum):
    """Conflict resolution strategies."""
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    CLOUD_WINS = "cloud_wins"
    EDGE_WINS = "edge_wins"
    MERGE = "merge"
    MANUAL = "manual"
    CRDT = "crdt"


class DataTier(Enum):
    """Data tiering for storage optimization."""
    HOT = "hot"  # Frequently accessed, local storage
    WARM = "warm"  # Occasionally accessed, hybrid
    COLD = "cold"  # Rarely accessed, cloud archive
    FROZEN = "frozen"  # Compliance archive only


class ConnectionState(Enum):
    """Edge-cloud connection state."""
    CONNECTED = "connected"
    INTERMITTENT = "intermittent"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


@dataclass
class EdgeNode:
    """Edge computing node representation."""
    node_id: str
    node_name: str
    site_id: str
    site_name: str
    ip_address: str
    capabilities: List[str] = field(default_factory=list)
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    last_heartbeat: Optional[datetime] = None
    last_sync: Optional[datetime] = None
    sync_lag_seconds: float = 0.0
    pending_uploads: int = 0
    pending_downloads: int = 0
    storage_used_mb: float = 0.0
    storage_capacity_mb: float = 1024.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    registered_at: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)


@dataclass
class SyncTopic:
    """Topic/channel for data synchronization."""
    topic_id: str
    topic_name: str
    direction: SyncDirection
    priority: SyncPriority
    conflict_resolution: ConflictResolution
    data_tier: DataTier
    schema_version: str = "1.0"
    compression_enabled: bool = True
    encryption_required: bool = True
    batch_size: int = 100
    sync_interval_seconds: int = 60
    retention_days: int = 30
    subscribed_nodes: List[str] = field(default_factory=list)


@dataclass
class SyncMessage:
    """Message for synchronization."""
    message_id: str
    topic_id: str
    source_node: str
    timestamp: datetime
    payload: Dict
    vector_clock: Dict[str, int] = field(default_factory=dict)
    checksum: str = ""
    compressed: bool = False
    encrypted: bool = False
    priority: SyncPriority = SyncPriority.MEDIUM
    retry_count: int = 0
    max_retries: int = 3
    acknowledged: bool = False


@dataclass
class ConflictRecord:
    """Record of sync conflict for resolution."""
    conflict_id: str
    topic_id: str
    key: str
    edge_value: Dict
    cloud_value: Dict
    edge_timestamp: datetime
    cloud_timestamp: datetime
    edge_node: str
    resolution_strategy: ConflictResolution
    resolved: bool = False
    resolved_value: Optional[Dict] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


@dataclass
class SyncCheckpoint:
    """Checkpoint for resumable synchronization."""
    checkpoint_id: str
    node_id: str
    topic_id: str
    last_sync_timestamp: datetime
    last_message_id: str
    vector_clock: Dict[str, int]
    pending_message_ids: List[str] = field(default_factory=list)


class VectorClock:
    """
    Vector clock implementation for causal ordering.

    Enables detection of concurrent updates across distributed nodes.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.clock: Dict[str, int] = defaultdict(int)

    def increment(self) -> Dict[str, int]:
        """Increment local clock."""
        self.clock[self.node_id] += 1
        return dict(self.clock)

    def update(self, other_clock: Dict[str, int]):
        """Update clock by taking max of each entry."""
        for node, time in other_clock.items():
            self.clock[node] = max(self.clock[node], time)
        self.increment()

    def compare(self, other_clock: Dict[str, int]) -> str:
        """
        Compare two vector clocks.

        Returns:
            'before': self happened before other
            'after': self happened after other
            'concurrent': neither happened before the other
            'equal': clocks are equal
        """
        all_nodes = set(self.clock.keys()) | set(other_clock.keys())

        self_before = False
        self_after = False

        for node in all_nodes:
            self_time = self.clock.get(node, 0)
            other_time = other_clock.get(node, 0)

            if self_time < other_time:
                self_before = True
            elif self_time > other_time:
                self_after = True

        if self_before and not self_after:
            return "before"
        elif self_after and not self_before:
            return "after"
        elif not self_before and not self_after:
            return "equal"
        else:
            return "concurrent"


class GCounter:
    """Grow-only counter CRDT."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.counts: Dict[str, int] = defaultdict(int)

    def increment(self, amount: int = 1):
        """Increment counter."""
        self.counts[self.node_id] += amount

    def value(self) -> int:
        """Get current value."""
        return sum(self.counts.values())

    def merge(self, other_counts: Dict[str, int]):
        """Merge with another counter."""
        for node, count in other_counts.items():
            self.counts[node] = max(self.counts[node], count)

    def state(self) -> Dict[str, int]:
        """Get state for synchronization."""
        return dict(self.counts)


class LWWRegister:
    """Last-Writer-Wins Register CRDT."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.value: Any = None
        self.timestamp: float = 0.0

    def set(self, value: Any, timestamp: float = None):
        """Set value with timestamp."""
        ts = timestamp or datetime.now().timestamp()
        if ts > self.timestamp:
            self.value = value
            self.timestamp = ts

    def get(self) -> Any:
        """Get current value."""
        return self.value

    def merge(self, other_value: Any, other_timestamp: float):
        """Merge with another register."""
        if other_timestamp > self.timestamp:
            self.value = other_value
            self.timestamp = other_timestamp

    def state(self) -> Tuple[Any, float]:
        """Get state for synchronization."""
        return (self.value, self.timestamp)


class CloudEdgeSyncService:
    """
    Cloud-Edge Synchronization Service.

    Provides reliable data synchronization between cloud and edge
    nodes with offline support and conflict resolution.
    """

    def __init__(self, cloud_node_id: str = "cloud-primary"):
        self.cloud_node_id = cloud_node_id
        self.edge_nodes: Dict[str, EdgeNode] = {}
        self.topics: Dict[str, SyncTopic] = {}
        self.pending_messages: Dict[str, List[SyncMessage]] = defaultdict(list)
        self.checkpoints: Dict[str, SyncCheckpoint] = {}
        self.conflicts: Dict[str, ConflictRecord] = {}
        self.vector_clocks: Dict[str, VectorClock] = {}
        self._message_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._store: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._sync_metrics: Dict[str, Dict] = {}

        # Initialize cloud's vector clock
        self.vector_clocks[cloud_node_id] = VectorClock(cloud_node_id)

    def _generate_id(self, prefix: str = "SYNC") -> str:
        """Generate unique identifier."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{timestamp}-{unique}"

    def _calculate_checksum(self, data: Dict) -> str:
        """Calculate checksum for data integrity."""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]

    def _compress_payload(self, payload: Dict) -> bytes:
        """Compress payload for bandwidth efficiency."""
        data_str = json.dumps(payload)
        return zlib.compress(data_str.encode())

    def _decompress_payload(self, compressed: bytes) -> Dict:
        """Decompress payload."""
        data_str = zlib.decompress(compressed).decode()
        return json.loads(data_str)

    # =========================================================================
    # Edge Node Management
    # =========================================================================

    async def register_edge_node(
        self,
        node_name: str,
        site_id: str,
        site_name: str,
        ip_address: str,
        capabilities: List[str] = None,
        storage_capacity_mb: float = 1024.0
    ) -> EdgeNode:
        """
        Register an edge node for synchronization.

        Args:
            node_name: Human-readable node name
            site_id: Manufacturing site identifier
            site_name: Site name
            ip_address: Node IP address
            capabilities: List of node capabilities
            storage_capacity_mb: Local storage capacity

        Returns:
            Registered EdgeNode
        """
        node_id = self._generate_id("EDGE")

        node = EdgeNode(
            node_id=node_id,
            node_name=node_name,
            site_id=site_id,
            site_name=site_name,
            ip_address=ip_address,
            capabilities=capabilities or [],
            storage_capacity_mb=storage_capacity_mb
        )

        self.edge_nodes[node_id] = node
        self.vector_clocks[node_id] = VectorClock(node_id)

        logger.info(f"Registered edge node: {node_name} ({node_id})")

        return node

    async def update_node_heartbeat(
        self,
        node_id: str,
        metrics: Dict = None
    ) -> EdgeNode:
        """Update edge node heartbeat and metrics."""
        if node_id not in self.edge_nodes:
            raise ValueError(f"Edge node not found: {node_id}")

        node = self.edge_nodes[node_id]
        node.last_heartbeat = datetime.now()
        node.connection_state = ConnectionState.CONNECTED

        if metrics:
            node.cpu_usage = metrics.get("cpu_usage", node.cpu_usage)
            node.memory_usage = metrics.get("memory_usage", node.memory_usage)
            node.storage_used_mb = metrics.get("storage_used_mb", node.storage_used_mb)

        return node

    async def detect_disconnected_nodes(
        self,
        timeout_seconds: int = 60
    ) -> List[str]:
        """Detect nodes that have missed heartbeats."""
        disconnected = []
        cutoff = datetime.now() - timedelta(seconds=timeout_seconds)

        for node_id, node in self.edge_nodes.items():
            if node.last_heartbeat and node.last_heartbeat < cutoff:
                if node.connection_state == ConnectionState.CONNECTED:
                    node.connection_state = ConnectionState.DISCONNECTED
                    disconnected.append(node_id)
                    logger.warning(f"Edge node disconnected: {node.node_name}")

        return disconnected

    # =========================================================================
    # Topic Management
    # =========================================================================

    async def create_topic(
        self,
        topic_name: str,
        direction: SyncDirection,
        priority: SyncPriority = SyncPriority.MEDIUM,
        conflict_resolution: ConflictResolution = ConflictResolution.LAST_WRITE_WINS,
        data_tier: DataTier = DataTier.HOT,
        sync_interval_seconds: int = 60,
        compression_enabled: bool = True
    ) -> SyncTopic:
        """
        Create a synchronization topic.

        Topics define what data is synchronized and how.
        """
        topic_id = self._generate_id("TOPIC")

        topic = SyncTopic(
            topic_id=topic_id,
            topic_name=topic_name,
            direction=direction,
            priority=priority,
            conflict_resolution=conflict_resolution,
            data_tier=data_tier,
            sync_interval_seconds=sync_interval_seconds,
            compression_enabled=compression_enabled
        )

        self.topics[topic_id] = topic
        logger.info(f"Created sync topic: {topic_name} ({direction.value})")

        return topic

    async def subscribe_node(
        self,
        node_id: str,
        topic_id: str
    ) -> SyncTopic:
        """Subscribe an edge node to a topic."""
        if node_id not in self.edge_nodes:
            raise ValueError(f"Edge node not found: {node_id}")
        if topic_id not in self.topics:
            raise ValueError(f"Topic not found: {topic_id}")

        topic = self.topics[topic_id]
        if node_id not in topic.subscribed_nodes:
            topic.subscribed_nodes.append(node_id)

        # Create checkpoint for new subscription
        checkpoint_id = f"{node_id}:{topic_id}"
        self.checkpoints[checkpoint_id] = SyncCheckpoint(
            checkpoint_id=checkpoint_id,
            node_id=node_id,
            topic_id=topic_id,
            last_sync_timestamp=datetime.now(),
            last_message_id="",
            vector_clock={}
        )

        logger.info(f"Node {node_id} subscribed to topic {topic_id}")

        return topic

    # =========================================================================
    # Message Publishing
    # =========================================================================

    async def publish_from_edge(
        self,
        node_id: str,
        topic_id: str,
        key: str,
        payload: Dict
    ) -> SyncMessage:
        """
        Publish data from edge to cloud.

        Stores locally at edge and queues for cloud sync.
        """
        if node_id not in self.edge_nodes:
            raise ValueError(f"Edge node not found: {node_id}")
        if topic_id not in self.topics:
            raise ValueError(f"Topic not found: {topic_id}")

        topic = self.topics[topic_id]

        # Get or create vector clock for node
        vc = self.vector_clocks.get(node_id)
        if not vc:
            vc = VectorClock(node_id)
            self.vector_clocks[node_id] = vc

        vector_clock = vc.increment()

        message = SyncMessage(
            message_id=self._generate_id("MSG"),
            topic_id=topic_id,
            source_node=node_id,
            timestamp=datetime.now(),
            payload={"key": key, "data": payload},
            vector_clock=vector_clock,
            checksum=self._calculate_checksum(payload),
            compressed=topic.compression_enabled,
            priority=topic.priority
        )

        # Store in pending queue
        self.pending_messages[node_id].append(message)

        # Update node metrics
        node = self.edge_nodes[node_id]
        node.pending_uploads += 1

        # Store locally
        self._store[f"{topic_id}:{key}"][node_id] = {
            "data": payload,
            "timestamp": message.timestamp,
            "vector_clock": vector_clock
        }

        logger.debug(f"Edge message queued: {message.message_id} from {node_id}")

        return message

    async def publish_from_cloud(
        self,
        topic_id: str,
        key: str,
        payload: Dict,
        target_nodes: List[str] = None
    ) -> List[SyncMessage]:
        """
        Publish data from cloud to edge nodes.

        Broadcasts to all subscribed nodes or specific targets.
        """
        if topic_id not in self.topics:
            raise ValueError(f"Topic not found: {topic_id}")

        topic = self.topics[topic_id]
        vc = self.vector_clocks[self.cloud_node_id]
        vector_clock = vc.increment()

        # Determine target nodes
        targets = target_nodes or topic.subscribed_nodes

        messages = []
        for node_id in targets:
            if node_id not in self.edge_nodes:
                continue

            message = SyncMessage(
                message_id=self._generate_id("MSG"),
                topic_id=topic_id,
                source_node=self.cloud_node_id,
                timestamp=datetime.now(),
                payload={"key": key, "data": payload},
                vector_clock=vector_clock,
                checksum=self._calculate_checksum(payload),
                compressed=topic.compression_enabled,
                priority=topic.priority
            )

            self.pending_messages[node_id].append(message)

            node = self.edge_nodes[node_id]
            node.pending_downloads += 1

            messages.append(message)

        # Store in cloud
        self._store[f"{topic_id}:{key}"][self.cloud_node_id] = {
            "data": payload,
            "timestamp": datetime.now(),
            "vector_clock": vector_clock
        }

        logger.debug(f"Cloud message broadcast to {len(messages)} nodes")

        return messages

    # =========================================================================
    # Synchronization
    # =========================================================================

    async def sync_edge_to_cloud(
        self,
        node_id: str,
        max_messages: int = 100
    ) -> Dict:
        """
        Synchronize pending messages from edge to cloud.

        Returns sync statistics.
        """
        if node_id not in self.edge_nodes:
            raise ValueError(f"Edge node not found: {node_id}")

        node = self.edge_nodes[node_id]
        pending = self.pending_messages.get(node_id, [])

        # Filter for edge-to-cloud messages
        to_sync = [
            m for m in pending[:max_messages]
            if m.source_node == node_id
        ]

        synced = 0
        conflicts = 0
        errors = 0

        for message in to_sync:
            try:
                result = await self._process_edge_message(message)
                if result == "synced":
                    synced += 1
                    pending.remove(message)
                    node.pending_uploads = max(0, node.pending_uploads - 1)
                elif result == "conflict":
                    conflicts += 1
            except Exception as e:
                errors += 1
                message.retry_count += 1
                if message.retry_count >= message.max_retries:
                    pending.remove(message)
                logger.error(f"Sync error for {message.message_id}: {e}")

        node.last_sync = datetime.now()

        return {
            "node_id": node_id,
            "synced": synced,
            "conflicts": conflicts,
            "errors": errors,
            "remaining": len(pending)
        }

    async def _process_edge_message(self, message: SyncMessage) -> str:
        """Process an incoming edge message."""
        topic = self.topics.get(message.topic_id)
        if not topic:
            return "error"

        key = message.payload.get("key")
        data = message.payload.get("data")
        store_key = f"{message.topic_id}:{key}"

        # Check for conflicts
        cloud_data = self._store.get(store_key, {}).get(self.cloud_node_id)

        if cloud_data:
            edge_vc = message.vector_clock
            cloud_vc = cloud_data.get("vector_clock", {})

            vc = VectorClock(self.cloud_node_id)
            vc.clock = cloud_vc
            comparison = vc.compare(edge_vc)

            if comparison == "concurrent":
                # Conflict detected
                await self._handle_conflict(
                    topic, key, data, cloud_data["data"],
                    message.timestamp, cloud_data["timestamp"],
                    message.source_node
                )
                return "conflict"

        # Apply message
        self._store[store_key][self.cloud_node_id] = {
            "data": data,
            "timestamp": message.timestamp,
            "vector_clock": message.vector_clock
        }

        # Update cloud's vector clock
        self.vector_clocks[self.cloud_node_id].update(message.vector_clock)

        # Notify handlers
        for handler in self._message_handlers.get(message.topic_id, []):
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")

        return "synced"

    async def sync_cloud_to_edge(
        self,
        node_id: str,
        max_messages: int = 100
    ) -> Dict:
        """
        Synchronize pending messages from cloud to edge.

        Returns sync statistics.
        """
        if node_id not in self.edge_nodes:
            raise ValueError(f"Edge node not found: {node_id}")

        node = self.edge_nodes[node_id]

        if node.connection_state != ConnectionState.CONNECTED:
            return {
                "node_id": node_id,
                "status": "disconnected",
                "synced": 0
            }

        pending = self.pending_messages.get(node_id, [])

        # Filter for cloud-to-edge messages
        to_sync = [
            m for m in pending[:max_messages]
            if m.source_node == self.cloud_node_id
        ]

        synced = 0
        for message in to_sync:
            # Simulate edge acknowledgment
            message.acknowledged = True
            synced += 1
            pending.remove(message)
            node.pending_downloads = max(0, node.pending_downloads - 1)

        node.last_sync = datetime.now()

        return {
            "node_id": node_id,
            "synced": synced,
            "remaining": len(pending)
        }

    async def full_sync(self, node_id: str) -> Dict:
        """Perform full bidirectional sync for a node."""
        edge_result = await self.sync_edge_to_cloud(node_id)
        cloud_result = await self.sync_cloud_to_edge(node_id)

        return {
            "node_id": node_id,
            "edge_to_cloud": edge_result,
            "cloud_to_edge": cloud_result,
            "timestamp": datetime.now().isoformat()
        }

    # =========================================================================
    # Conflict Resolution
    # =========================================================================

    async def _handle_conflict(
        self,
        topic: SyncTopic,
        key: str,
        edge_value: Dict,
        cloud_value: Dict,
        edge_timestamp: datetime,
        cloud_timestamp: datetime,
        edge_node: str
    ) -> ConflictRecord:
        """Handle a synchronization conflict."""
        conflict_id = self._generate_id("CONF")

        conflict = ConflictRecord(
            conflict_id=conflict_id,
            topic_id=topic.topic_id,
            key=key,
            edge_value=edge_value,
            cloud_value=cloud_value,
            edge_timestamp=edge_timestamp,
            cloud_timestamp=cloud_timestamp,
            edge_node=edge_node,
            resolution_strategy=topic.conflict_resolution
        )

        self.conflicts[conflict_id] = conflict

        # Auto-resolve if possible
        if topic.conflict_resolution != ConflictResolution.MANUAL:
            resolved_value = await self._auto_resolve_conflict(conflict)
            if resolved_value is not None:
                conflict.resolved = True
                conflict.resolved_value = resolved_value
                conflict.resolved_by = "auto"
                conflict.resolved_at = datetime.now()

                # Apply resolved value
                store_key = f"{topic.topic_id}:{key}"
                self._store[store_key][self.cloud_node_id] = {
                    "data": resolved_value,
                    "timestamp": datetime.now(),
                    "vector_clock": self.vector_clocks[self.cloud_node_id].increment()
                }

        logger.warning(f"Sync conflict detected: {conflict_id} for key {key}")

        return conflict

    async def _auto_resolve_conflict(
        self,
        conflict: ConflictRecord
    ) -> Optional[Dict]:
        """Automatically resolve conflict based on strategy."""
        strategy = conflict.resolution_strategy

        if strategy == ConflictResolution.LAST_WRITE_WINS:
            if conflict.edge_timestamp > conflict.cloud_timestamp:
                return conflict.edge_value
            else:
                return conflict.cloud_value

        elif strategy == ConflictResolution.FIRST_WRITE_WINS:
            if conflict.edge_timestamp < conflict.cloud_timestamp:
                return conflict.edge_value
            else:
                return conflict.cloud_value

        elif strategy == ConflictResolution.CLOUD_WINS:
            return conflict.cloud_value

        elif strategy == ConflictResolution.EDGE_WINS:
            return conflict.edge_value

        elif strategy == ConflictResolution.MERGE:
            # Simple merge - combine both dicts
            merged = {**conflict.cloud_value, **conflict.edge_value}
            return merged

        elif strategy == ConflictResolution.CRDT:
            # For CRDT, merge using LWW for each field
            merged = {}
            all_keys = set(conflict.cloud_value.keys()) | set(conflict.edge_value.keys())
            for k in all_keys:
                edge_val = conflict.edge_value.get(k)
                cloud_val = conflict.cloud_value.get(k)
                if edge_val is not None and cloud_val is not None:
                    # Both have value - use timestamp
                    if conflict.edge_timestamp > conflict.cloud_timestamp:
                        merged[k] = edge_val
                    else:
                        merged[k] = cloud_val
                elif edge_val is not None:
                    merged[k] = edge_val
                else:
                    merged[k] = cloud_val
            return merged

        return None

    async def resolve_conflict_manually(
        self,
        conflict_id: str,
        resolved_value: Dict,
        resolved_by: str
    ) -> ConflictRecord:
        """Manually resolve a conflict."""
        if conflict_id not in self.conflicts:
            raise ValueError(f"Conflict not found: {conflict_id}")

        conflict = self.conflicts[conflict_id]
        conflict.resolved = True
        conflict.resolved_value = resolved_value
        conflict.resolved_by = resolved_by
        conflict.resolved_at = datetime.now()

        # Apply resolved value
        store_key = f"{conflict.topic_id}:{conflict.key}"
        self._store[store_key][self.cloud_node_id] = {
            "data": resolved_value,
            "timestamp": datetime.now(),
            "vector_clock": self.vector_clocks[self.cloud_node_id].increment()
        }

        logger.info(f"Conflict {conflict_id} manually resolved by {resolved_by}")

        return conflict

    def get_pending_conflicts(self) -> List[ConflictRecord]:
        """Get all unresolved conflicts."""
        return [c for c in self.conflicts.values() if not c.resolved]

    # =========================================================================
    # Data Access
    # =========================================================================

    async def get_value(
        self,
        topic_id: str,
        key: str,
        node_id: str = None
    ) -> Optional[Dict]:
        """Get current value for a key."""
        store_key = f"{topic_id}:{key}"
        source = node_id or self.cloud_node_id

        data = self._store.get(store_key, {}).get(source)
        if data:
            return data.get("data")
        return None

    async def query_values(
        self,
        topic_id: str,
        filter_func: Callable[[str, Dict], bool] = None
    ) -> List[Tuple[str, Dict]]:
        """Query all values for a topic with optional filter."""
        results = []
        prefix = f"{topic_id}:"

        for store_key, versions in self._store.items():
            if store_key.startswith(prefix):
                key = store_key[len(prefix):]
                cloud_data = versions.get(self.cloud_node_id)
                if cloud_data:
                    data = cloud_data.get("data")
                    if filter_func is None or filter_func(key, data):
                        results.append((key, data))

        return results

    # =========================================================================
    # Handlers and Subscriptions
    # =========================================================================

    def register_handler(
        self,
        topic_id: str,
        handler: Callable[[SyncMessage], None]
    ):
        """Register a message handler for a topic."""
        self._message_handlers[topic_id].append(handler)

    # =========================================================================
    # Metrics and Monitoring
    # =========================================================================

    async def get_sync_metrics(self) -> Dict:
        """Get synchronization metrics."""
        total_pending = sum(len(msgs) for msgs in self.pending_messages.values())
        connected_nodes = sum(
            1 for n in self.edge_nodes.values()
            if n.connection_state == ConnectionState.CONNECTED
        )

        # Calculate average sync lag
        sync_lags = [
            (datetime.now() - n.last_sync).total_seconds()
            for n in self.edge_nodes.values()
            if n.last_sync
        ]
        avg_lag = sum(sync_lags) / len(sync_lags) if sync_lags else 0

        return {
            "timestamp": datetime.now().isoformat(),
            "edge_nodes": {
                "total": len(self.edge_nodes),
                "connected": connected_nodes,
                "disconnected": len(self.edge_nodes) - connected_nodes
            },
            "topics": len(self.topics),
            "messages": {
                "pending_total": total_pending,
                "pending_by_node": {
                    node_id: len(msgs)
                    for node_id, msgs in self.pending_messages.items()
                }
            },
            "conflicts": {
                "total": len(self.conflicts),
                "unresolved": len(self.get_pending_conflicts())
            },
            "sync_lag_seconds": round(avg_lag, 2)
        }

    async def get_node_status(self, node_id: str) -> Dict:
        """Get detailed status for an edge node."""
        if node_id not in self.edge_nodes:
            raise ValueError(f"Edge node not found: {node_id}")

        node = self.edge_nodes[node_id]
        pending = self.pending_messages.get(node_id, [])

        return {
            "node_id": node_id,
            "node_name": node.node_name,
            "site": node.site_name,
            "connection_state": node.connection_state.value,
            "last_heartbeat": node.last_heartbeat.isoformat() if node.last_heartbeat else None,
            "last_sync": node.last_sync.isoformat() if node.last_sync else None,
            "pending_messages": len(pending),
            "pending_uploads": node.pending_uploads,
            "pending_downloads": node.pending_downloads,
            "storage": {
                "used_mb": node.storage_used_mb,
                "capacity_mb": node.storage_capacity_mb,
                "percent_used": round(node.storage_used_mb / node.storage_capacity_mb * 100, 2)
            },
            "resources": {
                "cpu_usage": node.cpu_usage,
                "memory_usage": node.memory_usage
            }
        }

    async def get_topic_statistics(self, topic_id: str) -> Dict:
        """Get statistics for a sync topic."""
        if topic_id not in self.topics:
            raise ValueError(f"Topic not found: {topic_id}")

        topic = self.topics[topic_id]

        # Count messages for this topic
        message_count = 0
        for messages in self.pending_messages.values():
            message_count += sum(1 for m in messages if m.topic_id == topic_id)

        # Count stored keys
        prefix = f"{topic_id}:"
        key_count = sum(1 for k in self._store.keys() if k.startswith(prefix))

        return {
            "topic_id": topic_id,
            "topic_name": topic.topic_name,
            "direction": topic.direction.value,
            "priority": topic.priority.value,
            "subscribed_nodes": len(topic.subscribed_nodes),
            "pending_messages": message_count,
            "stored_keys": key_count,
            "sync_interval_seconds": topic.sync_interval_seconds,
            "compression_enabled": topic.compression_enabled
        }


# Factory function
def create_cloud_edge_service(cloud_node_id: str = "cloud-primary") -> CloudEdgeSyncService:
    """Create and return a CloudEdgeSyncService instance."""
    return CloudEdgeSyncService(cloud_node_id=cloud_node_id)
