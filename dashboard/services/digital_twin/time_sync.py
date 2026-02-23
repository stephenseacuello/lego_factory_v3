"""
Time Synchronization Service
============================

Ensures consistent timestamps across distributed digital twin systems.

Features:
- NTP integration for absolute time
- Clock drift compensation
- Event ordering guarantees
- Network latency estimation

ISO 23247 Compliance:
- Accurate timestamping for event correlation
- Consistent ordering across domains

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
import time
import statistics
import logging
import socket

logger = logging.getLogger(__name__)


class ClockSource(Enum):
    """Clock source types."""
    LOCAL = "local"           # Local system clock
    NTP = "ntp"              # NTP server
    GPS = "gps"              # GPS receiver
    PTP = "ptp"              # Precision Time Protocol (IEEE 1588)
    CUSTOM = "custom"        # Custom time source


class SyncQuality(Enum):
    """Time synchronization quality levels."""
    EXCELLENT = "excellent"  # < 1ms offset
    GOOD = "good"           # < 10ms offset
    FAIR = "fair"           # < 100ms offset
    POOR = "poor"           # < 1000ms offset
    UNKNOWN = "unknown"     # No sync data


@dataclass
class TimeOffset:
    """Time offset measurement."""
    offset_ms: float          # Local - Reference (positive = local ahead)
    round_trip_ms: float      # Network round trip time
    measured_at: datetime
    source: ClockSource
    server: Optional[str] = None

    @property
    def quality(self) -> SyncQuality:
        """Determine sync quality from offset."""
        abs_offset = abs(self.offset_ms)
        if abs_offset < 1:
            return SyncQuality.EXCELLENT
        elif abs_offset < 10:
            return SyncQuality.GOOD
        elif abs_offset < 100:
            return SyncQuality.FAIR
        elif abs_offset < 1000:
            return SyncQuality.POOR
        return SyncQuality.UNKNOWN


@dataclass
class TimeSyncConfig:
    """Time synchronization configuration."""
    ntp_servers: List[str] = field(default_factory=lambda: [
        "pool.ntp.org",
        "time.google.com",
        "time.cloudflare.com"
    ])
    sync_interval_seconds: float = 300.0  # 5 minutes
    max_offset_ms: float = 1000.0         # Max acceptable offset
    min_samples: int = 3                   # Min samples for averaging
    max_samples: int = 8                   # Max samples to keep
    timeout_seconds: float = 5.0
    drift_correction: bool = True


class VectorClock:
    """
    Vector clock for distributed event ordering.

    Ensures causal ordering of events across multiple nodes
    without requiring synchronized wall clocks.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._clock: Dict[str, int] = {node_id: 0}
        self._lock = threading.Lock()

    def tick(self) -> Dict[str, int]:
        """Increment local clock and return current vector."""
        with self._lock:
            self._clock[self.node_id] = self._clock.get(self.node_id, 0) + 1
            return self._clock.copy()

    def update(self, other_clock: Dict[str, int]):
        """Merge with another vector clock."""
        with self._lock:
            for node, time in other_clock.items():
                self._clock[node] = max(self._clock.get(node, 0), time)
            # Increment own clock
            self._clock[self.node_id] = self._clock.get(self.node_id, 0) + 1

    def get_clock(self) -> Dict[str, int]:
        """Get current vector clock state."""
        with self._lock:
            return self._clock.copy()

    def happens_before(self, other_clock: Dict[str, int]) -> bool:
        """Check if this clock happens before other."""
        with self._lock:
            all_leq = all(
                self._clock.get(k, 0) <= other_clock.get(k, 0)
                for k in set(self._clock.keys()) | set(other_clock.keys())
            )
            any_lt = any(
                self._clock.get(k, 0) < other_clock.get(k, 0)
                for k in other_clock.keys()
            )
            return all_leq and any_lt

    def concurrent(self, other_clock: Dict[str, int]) -> bool:
        """Check if clocks are concurrent (no causal relationship)."""
        return not self.happens_before(other_clock) and not self._other_happens_before(other_clock)

    def _other_happens_before(self, other_clock: Dict[str, int]) -> bool:
        """Check if other clock happens before this one."""
        with self._lock:
            all_leq = all(
                other_clock.get(k, 0) <= self._clock.get(k, 0)
                for k in set(self._clock.keys()) | set(other_clock.keys())
            )
            any_lt = any(
                other_clock.get(k, 0) < self._clock.get(k, 0)
                for k in self._clock.keys()
            )
            return all_leq and any_lt


class HybridLogicalClock:
    """
    Hybrid Logical Clock (HLC) combining physical and logical time.

    Provides:
    - Monotonically increasing timestamps
    - Causal ordering
    - Close correlation with wall clock time
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._physical: int = 0   # Physical time (ms since epoch)
        self._logical: int = 0    # Logical counter
        self._lock = threading.Lock()

    def now(self) -> Tuple[int, int]:
        """Get current HLC timestamp."""
        with self._lock:
            wall_ms = int(time.time() * 1000)

            if wall_ms > self._physical:
                self._physical = wall_ms
                self._logical = 0
            else:
                self._logical += 1

            return (self._physical, self._logical)

    def update(self, other_physical: int, other_logical: int) -> Tuple[int, int]:
        """Update clock with received timestamp."""
        with self._lock:
            wall_ms = int(time.time() * 1000)

            if wall_ms > self._physical and wall_ms > other_physical:
                self._physical = wall_ms
                self._logical = 0
            elif other_physical > self._physical:
                self._physical = other_physical
                self._logical = other_logical + 1
            elif self._physical == other_physical:
                self._logical = max(self._logical, other_logical) + 1
            else:
                self._logical += 1

            return (self._physical, self._logical)

    def compare(self, ts1: Tuple[int, int], ts2: Tuple[int, int]) -> int:
        """Compare two HLC timestamps. Returns -1, 0, or 1."""
        if ts1[0] < ts2[0]:
            return -1
        elif ts1[0] > ts2[0]:
            return 1
        elif ts1[1] < ts2[1]:
            return -1
        elif ts1[1] > ts2[1]:
            return 1
        return 0

    def to_datetime(self, hlc: Tuple[int, int]) -> datetime:
        """Convert HLC to datetime."""
        return datetime.utcfromtimestamp(hlc[0] / 1000)


class TimeSyncService:
    """
    Service for time synchronization across digital twin nodes.

    Provides:
    - NTP-based time synchronization
    - Clock offset estimation and compensation
    - Drift rate calculation
    - Event ordering with vector/hybrid clocks
    """

    def __init__(self, node_id: str, config: TimeSyncConfig = None):
        self.node_id = node_id
        self.config = config or TimeSyncConfig()

        # Clock offset tracking
        self._offsets: List[TimeOffset] = []
        self._current_offset_ms: float = 0.0
        self._drift_rate_ppm: float = 0.0  # Parts per million

        # Logical clocks
        self._vector_clock = VectorClock(node_id)
        self._hlc = HybridLogicalClock(node_id)

        # Background sync
        self._sync_thread: Optional[threading.Thread] = None
        self._running = False
        self._last_sync: Optional[datetime] = None

        # Statistics
        self._stats = {
            'sync_count': 0,
            'sync_failures': 0,
            'avg_offset_ms': 0.0,
            'avg_rtt_ms': 0.0,
            'drift_rate_ppm': 0.0
        }

        self._lock = threading.RLock()

        logger.info(f"TimeSyncService initialized for node {node_id}")

    def start(self):
        """Start background synchronization."""
        if self._running:
            return

        self._running = True
        self._sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._sync_thread.start()
        logger.info("Time sync service started")

    def stop(self):
        """Stop background synchronization."""
        self._running = False
        if self._sync_thread:
            self._sync_thread.join(timeout=2.0)
        logger.info("Time sync service stopped")

    def sync_now(self) -> Optional[TimeOffset]:
        """Perform immediate time synchronization."""
        for server in self.config.ntp_servers:
            try:
                offset = self._query_ntp(server)
                if offset:
                    self._add_offset(offset)
                    self._stats['sync_count'] += 1
                    return offset
            except Exception as e:
                logger.warning(f"NTP query to {server} failed: {e}")
                self._stats['sync_failures'] += 1

        return None

    def get_synchronized_time(self) -> datetime:
        """Get current time corrected for clock offset."""
        local = datetime.utcnow()
        correction = timedelta(milliseconds=-self._current_offset_ms)
        return local + correction

    def get_synchronized_timestamp(self) -> float:
        """Get current Unix timestamp corrected for offset."""
        return time.time() - (self._current_offset_ms / 1000)

    def get_offset(self) -> float:
        """Get current estimated clock offset in milliseconds."""
        return self._current_offset_ms

    def get_sync_quality(self) -> SyncQuality:
        """Get current synchronization quality."""
        if not self._offsets:
            return SyncQuality.UNKNOWN
        return self._offsets[-1].quality

    def get_vector_clock(self) -> VectorClock:
        """Get vector clock for distributed ordering."""
        return self._vector_clock

    def get_hlc(self) -> HybridLogicalClock:
        """Get hybrid logical clock."""
        return self._hlc

    def tick_vector_clock(self) -> Dict[str, int]:
        """Increment and return vector clock."""
        return self._vector_clock.tick()

    def update_vector_clock(self, other_clock: Dict[str, int]):
        """Update vector clock with received clock."""
        self._vector_clock.update(other_clock)

    def get_hlc_timestamp(self) -> Tuple[int, int]:
        """Get current HLC timestamp."""
        return self._hlc.now()

    def update_hlc(self, physical: int, logical: int) -> Tuple[int, int]:
        """Update HLC with received timestamp."""
        return self._hlc.update(physical, logical)

    def estimate_latency(self, server: str = None) -> Optional[float]:
        """Estimate network latency to server in milliseconds."""
        target = server or (self.config.ntp_servers[0] if self.config.ntp_servers else None)
        if not target:
            return None

        try:
            # Simple ICMP-like round trip estimation
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.config.timeout_seconds)
            sock.connect((target, 123))  # NTP port
            sock.send(b'\x1b' + 47 * b'\0')  # NTP query
            sock.recv(1024)
            rtt = (time.time() - start) * 1000
            sock.close()
            return rtt / 2  # One-way estimate
        except Exception:
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics."""
        with self._lock:
            return {
                **self._stats,
                'current_offset_ms': self._current_offset_ms,
                'last_sync': self._last_sync.isoformat() if self._last_sync else None,
                'quality': self.get_sync_quality().value,
                'samples': len(self._offsets)
            }

    def _sync_loop(self):
        """Background sync loop."""
        # Initial sync
        self.sync_now()

        while self._running:
            time.sleep(self.config.sync_interval_seconds)
            if self._running:
                self.sync_now()

    def _query_ntp(self, server: str) -> Optional[TimeOffset]:
        """Query NTP server for time offset."""
        try:
            import struct

            # NTP request (version 3, mode 3 = client)
            ntp_msg = b'\x1b' + 47 * b'\0'

            # Connect and measure
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.config.timeout_seconds)

            t1 = time.time()  # Client transmit
            sock.sendto(ntp_msg, (server, 123))

            data, _ = sock.recvfrom(1024)
            t4 = time.time()  # Client receive

            sock.close()

            if len(data) < 48:
                return None

            # Parse NTP response
            # Transmit timestamp at bytes 40-47
            unpacked = struct.unpack('!12I', data)
            t3 = unpacked[10] + unpacked[11] / (2**32)  # Server transmit
            t2 = unpacked[8] + unpacked[9] / (2**32)    # Server receive

            # Convert NTP time (seconds since 1900) to Unix time
            ntp_epoch = 2208988800
            t2 -= ntp_epoch
            t3 -= ntp_epoch

            # Calculate offset and RTT
            # offset = ((t2 - t1) + (t3 - t4)) / 2
            offset = ((t2 - t1) + (t3 - t4)) / 2
            rtt = (t4 - t1) - (t3 - t2)

            return TimeOffset(
                offset_ms=offset * 1000,
                round_trip_ms=rtt * 1000,
                measured_at=datetime.utcnow(),
                source=ClockSource.NTP,
                server=server
            )

        except Exception as e:
            logger.debug(f"NTP query error: {e}")
            return None

    def _add_offset(self, offset: TimeOffset):
        """Add new offset measurement and update estimate."""
        with self._lock:
            self._offsets.append(offset)
            self._last_sync = datetime.utcnow()

            # Keep limited history
            if len(self._offsets) > self.config.max_samples:
                self._offsets.pop(0)

            # Update current estimate using median
            if len(self._offsets) >= self.config.min_samples:
                offsets = [o.offset_ms for o in self._offsets]
                self._current_offset_ms = statistics.median(offsets)
                self._stats['avg_offset_ms'] = statistics.mean(offsets)
                self._stats['avg_rtt_ms'] = statistics.mean(
                    [o.round_trip_ms for o in self._offsets]
                )

                # Estimate drift rate
                if len(self._offsets) >= 2 and self.config.drift_correction:
                    self._estimate_drift()

    def _estimate_drift(self):
        """Estimate clock drift rate."""
        if len(self._offsets) < 2:
            return

        # Simple linear regression on offset vs time
        times = []
        offsets = []
        base_time = self._offsets[0].measured_at.timestamp()

        for o in self._offsets:
            times.append(o.measured_at.timestamp() - base_time)
            offsets.append(o.offset_ms)

        n = len(times)
        if n < 2:
            return

        mean_t = statistics.mean(times)
        mean_o = statistics.mean(offsets)

        # Calculate slope
        numerator = sum((t - mean_t) * (o - mean_o) for t, o in zip(times, offsets))
        denominator = sum((t - mean_t) ** 2 for t in times)

        if denominator > 0:
            slope = numerator / denominator  # ms per second
            self._drift_rate_ppm = slope * 1000  # Convert to ppm
            self._stats['drift_rate_ppm'] = self._drift_rate_ppm


# Singleton instance
_time_sync_service: Optional[TimeSyncService] = None


def get_time_sync_service(node_id: str = "main") -> TimeSyncService:
    """Get or create time sync service."""
    global _time_sync_service
    if _time_sync_service is None:
        _time_sync_service = TimeSyncService(node_id)
    return _time_sync_service
