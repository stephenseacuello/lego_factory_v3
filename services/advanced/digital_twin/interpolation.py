"""
State Interpolation Service
===========================

Provides smooth state transitions for Unity visualization at 60fps.

Features:
- Linear interpolation for positions
- Spherical interpolation (SLERP) for rotations
- Spline interpolation for trajectories
- Prediction for network latency compensation
- Dead reckoning for temporary disconnections

Author: LegoMCP Team
Version: 2.0.0
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import math
import logging
import time
import threading
from collections import deque

logger = logging.getLogger(__name__)


class InterpolationMode(Enum):
    """Interpolation modes for different data types."""
    LINEAR = "linear"          # Linear interpolation
    SLERP = "slerp"           # Spherical linear interpolation (rotations)
    CUBIC = "cubic"           # Cubic spline interpolation
    CATMULL_ROM = "catmull_rom"  # Catmull-Rom spline (smooth curves)
    STEP = "step"             # No interpolation, use nearest value
    ELASTIC = "elastic"       # Spring-like easing
    EASE_IN_OUT = "ease_in_out"  # Smooth acceleration/deceleration


@dataclass
class StateSnapshot:
    """A snapshot of state at a specific time."""
    timestamp: float  # Unix timestamp
    state: Dict[str, Any]
    sequence: int
    source: str = "sensor"  # sensor, prediction, interpolated


@dataclass
class InterpolationConfig:
    """Configuration for interpolation."""
    mode: InterpolationMode = InterpolationMode.LINEAR
    buffer_size: int = 10  # Number of snapshots to keep
    interpolation_delay_ms: float = 100  # Delay for smooth interpolation
    extrapolation_limit_ms: float = 200  # Max time to extrapolate
    prediction_enabled: bool = True
    smoothing_factor: float = 0.1  # For exponential smoothing


class Vector3:
    """Simple 3D vector for interpolation."""

    def __init__(self, x: float = 0, y: float = 0, z: float = 0):
        self.x = x
        self.y = y
        self.z = z

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'Vector3':
        return cls(d.get('x', 0), d.get('y', 0), d.get('z', 0))

    def to_dict(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z}

    def lerp(self, other: 'Vector3', t: float) -> 'Vector3':
        """Linear interpolation to another vector."""
        return Vector3(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t,
            self.z + (other.z - self.z) * t
        )

    def distance(self, other: 'Vector3') -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

    def __add__(self, other: 'Vector3') -> 'Vector3':
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: 'Vector3') -> 'Vector3':
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> 'Vector3':
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)


class Quaternion:
    """Quaternion for rotation interpolation."""

    def __init__(self, x: float = 0, y: float = 0, z: float = 0, w: float = 1):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> 'Quaternion':
        return cls(d.get('x', 0), d.get('y', 0), d.get('z', 0), d.get('w', 1))

    def to_dict(self) -> Dict[str, float]:
        return {'x': self.x, 'y': self.y, 'z': self.z, 'w': self.w}

    def normalize(self) -> 'Quaternion':
        """Normalize quaternion."""
        mag = math.sqrt(self.x**2 + self.y**2 + self.z**2 + self.w**2)
        if mag > 0:
            return Quaternion(self.x/mag, self.y/mag, self.z/mag, self.w/mag)
        return Quaternion()

    def dot(self, other: 'Quaternion') -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z + self.w * other.w

    def slerp(self, other: 'Quaternion', t: float) -> 'Quaternion':
        """Spherical linear interpolation."""
        # Normalize inputs
        q1 = self.normalize()
        q2 = other.normalize()

        dot = q1.dot(q2)

        # If negative dot, negate one quaternion to take shorter path
        if dot < 0:
            q2 = Quaternion(-q2.x, -q2.y, -q2.z, -q2.w)
            dot = -dot

        # If very close, use linear interpolation
        if dot > 0.9995:
            result = Quaternion(
                q1.x + (q2.x - q1.x) * t,
                q1.y + (q2.y - q1.y) * t,
                q1.z + (q2.z - q1.z) * t,
                q1.w + (q2.w - q1.w) * t
            )
            return result.normalize()

        # Spherical interpolation
        theta_0 = math.acos(dot)
        theta = theta_0 * t

        sin_theta = math.sin(theta)
        sin_theta_0 = math.sin(theta_0)

        s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
        s1 = sin_theta / sin_theta_0

        return Quaternion(
            s0 * q1.x + s1 * q2.x,
            s0 * q1.y + s1 * q2.y,
            s0 * q1.z + s1 * q2.z,
            s0 * q1.w + s1 * q2.w
        )


class InterpolationBuffer:
    """
    Buffer for state snapshots with interpolation capabilities.

    Maintains a rolling buffer of recent state snapshots and
    provides interpolated values for any requested timestamp.
    """

    def __init__(self, config: InterpolationConfig = None):
        self.config = config or InterpolationConfig()
        self._buffer: deque = deque(maxlen=self.config.buffer_size)
        self._lock = threading.RLock()
        self._last_sequence = -1

        # Velocity estimation for prediction
        self._velocities: Dict[str, Any] = {}

    def add_snapshot(self, snapshot: StateSnapshot):
        """Add a new snapshot to the buffer."""
        with self._lock:
            # Check sequence to avoid out-of-order
            if snapshot.sequence <= self._last_sequence:
                return

            self._last_sequence = snapshot.sequence
            self._buffer.append(snapshot)

            # Update velocity estimates
            if len(self._buffer) >= 2:
                self._update_velocities()

    def _update_velocities(self):
        """Estimate velocities from recent snapshots."""
        if len(self._buffer) < 2:
            return

        # Get two most recent snapshots
        s1 = self._buffer[-2]
        s2 = self._buffer[-1]

        dt = s2.timestamp - s1.timestamp
        if dt <= 0:
            return

        # Calculate velocities for numeric fields
        for key in s2.state:
            if key not in s1.state:
                continue

            v1 = s1.state[key]
            v2 = s2.state[key]

            if isinstance(v2, (int, float)) and isinstance(v1, (int, float)):
                self._velocities[key] = (v2 - v1) / dt

            elif isinstance(v2, dict) and isinstance(v1, dict):
                # Handle nested dicts (positions, temperatures)
                if key not in self._velocities:
                    self._velocities[key] = {}
                for subkey in v2:
                    if subkey in v1:
                        sv1 = v1[subkey]
                        sv2 = v2[subkey]
                        if isinstance(sv2, (int, float)) and isinstance(sv1, (int, float)):
                            self._velocities[key][subkey] = (sv2 - sv1) / dt

    def get_interpolated_state(self, target_time: float = None) -> Optional[Dict[str, Any]]:
        """
        Get interpolated state at target time.

        Args:
            target_time: Unix timestamp (default: now - interpolation_delay)

        Returns:
            Interpolated state dictionary
        """
        with self._lock:
            if len(self._buffer) == 0:
                return None

            if target_time is None:
                target_time = time.time() - (self.config.interpolation_delay_ms / 1000)

            # Find surrounding snapshots
            before = None
            after = None

            for snapshot in self._buffer:
                if snapshot.timestamp <= target_time:
                    before = snapshot
                elif snapshot.timestamp > target_time and after is None:
                    after = snapshot
                    break

            # Handle edge cases
            if before is None:
                # Before all snapshots - return oldest
                return self._buffer[0].state.copy()

            if after is None:
                # After all snapshots - extrapolate or return latest
                latest = self._buffer[-1]
                extra_time = target_time - latest.timestamp
                extra_limit = self.config.extrapolation_limit_ms / 1000

                if extra_time > extra_limit or not self.config.prediction_enabled:
                    return latest.state.copy()

                # Extrapolate using velocities
                return self._extrapolate(latest, extra_time)

            # Interpolate between before and after
            return self._interpolate(before, after, target_time)

    def _interpolate(
        self,
        before: StateSnapshot,
        after: StateSnapshot,
        target_time: float
    ) -> Dict[str, Any]:
        """Interpolate between two snapshots."""
        dt = after.timestamp - before.timestamp
        if dt <= 0:
            return after.state.copy()

        t = (target_time - before.timestamp) / dt

        # Apply easing
        t = self._apply_easing(t)

        result = {}

        for key in after.state:
            v1 = before.state.get(key)
            v2 = after.state[key]

            if v1 is None:
                result[key] = v2
            elif isinstance(v2, (int, float)) and isinstance(v1, (int, float)):
                # Numeric interpolation
                result[key] = v1 + (v2 - v1) * t
            elif isinstance(v2, dict) and isinstance(v1, dict):
                # Nested dict (positions, rotations, temperatures)
                result[key] = self._interpolate_dict(v1, v2, t)
            elif isinstance(v2, str):
                # String - use after value (no interpolation)
                result[key] = v2 if t >= 0.5 else v1
            else:
                result[key] = v2

        return result

    def _interpolate_dict(
        self,
        d1: Dict[str, Any],
        d2: Dict[str, Any],
        t: float
    ) -> Dict[str, Any]:
        """Interpolate nested dictionaries."""
        result = {}

        # Check if this looks like a quaternion (has x, y, z, w)
        is_quaternion = all(k in d2 for k in ['x', 'y', 'z', 'w'])

        # Check if this looks like a position (has x, y, z but not w)
        is_position = all(k in d2 for k in ['x', 'y', 'z']) and 'w' not in d2

        if is_quaternion and self.config.mode == InterpolationMode.SLERP:
            q1 = Quaternion.from_dict(d1)
            q2 = Quaternion.from_dict(d2)
            return q1.slerp(q2, t).to_dict()

        if is_position:
            v1 = Vector3.from_dict(d1)
            v2 = Vector3.from_dict(d2)
            return v1.lerp(v2, t).to_dict()

        # Generic dict interpolation
        for key in d2:
            v1 = d1.get(key)
            v2 = d2[key]

            if v1 is None:
                result[key] = v2
            elif isinstance(v2, (int, float)) and isinstance(v1, (int, float)):
                result[key] = v1 + (v2 - v1) * t
            else:
                result[key] = v2

        return result

    def _extrapolate(self, latest: StateSnapshot, dt: float) -> Dict[str, Any]:
        """Extrapolate state using velocity estimates."""
        result = latest.state.copy()

        for key, velocity in self._velocities.items():
            if key not in result:
                continue

            if isinstance(velocity, (int, float)):
                current = result[key]
                if isinstance(current, (int, float)):
                    result[key] = current + velocity * dt

            elif isinstance(velocity, dict):
                if key not in result or not isinstance(result[key], dict):
                    continue
                for subkey, subvel in velocity.items():
                    if subkey in result[key] and isinstance(subvel, (int, float)):
                        current = result[key][subkey]
                        if isinstance(current, (int, float)):
                            result[key][subkey] = current + subvel * dt

        return result

    def _apply_easing(self, t: float) -> float:
        """Apply easing function to interpolation parameter."""
        if self.config.mode == InterpolationMode.EASE_IN_OUT:
            # Smooth start and end
            return t * t * (3 - 2 * t)

        elif self.config.mode == InterpolationMode.ELASTIC:
            # Spring-like bounce
            if t == 0 or t == 1:
                return t
            p = 0.3
            return math.pow(2, -10 * t) * math.sin((t - p/4) * (2 * math.pi) / p) + 1

        elif self.config.mode == InterpolationMode.CUBIC:
            # Cubic ease-in-out
            if t < 0.5:
                return 4 * t * t * t
            return 1 - math.pow(-2 * t + 2, 3) / 2

        # Default: linear
        return t

    def get_latest(self) -> Optional[StateSnapshot]:
        """Get most recent snapshot."""
        with self._lock:
            return self._buffer[-1] if self._buffer else None

    def clear(self):
        """Clear buffer."""
        with self._lock:
            self._buffer.clear()
            self._velocities.clear()
            self._last_sequence = -1


class StateInterpolationService:
    """
    Service for managing state interpolation across multiple entities.

    Provides smooth 60fps updates for Unity visualization by:
    - Buffering incoming state updates
    - Interpolating between updates
    - Predicting future states during network gaps
    - Handling timestamp synchronization
    """

    def __init__(self, default_config: InterpolationConfig = None):
        self.default_config = default_config or InterpolationConfig()

        # Per-entity buffers
        self._buffers: Dict[str, InterpolationBuffer] = {}

        # Custom configs per entity
        self._configs: Dict[str, InterpolationConfig] = {}

        # Sequence counters
        self._sequences: Dict[str, int] = {}

        # Time sync
        self._time_offset: float = 0.0  # Server time - local time

        # Statistics
        self._stats = {
            'snapshots_received': 0,
            'interpolations_performed': 0,
            'extrapolations_performed': 0,
            'entities_tracked': 0
        }

        self._lock = threading.RLock()

        logger.info("StateInterpolationService initialized")

    def receive_state(
        self,
        entity_id: str,
        state: Dict[str, Any],
        timestamp: float = None,
        source: str = "sensor"
    ):
        """
        Receive new state data from sensor or digital twin.

        Args:
            entity_id: Entity identifier
            state: State dictionary
            timestamp: Server timestamp (default: now)
            source: Data source
        """
        with self._lock:
            if timestamp is None:
                timestamp = time.time() + self._time_offset

            # Get or create buffer
            if entity_id not in self._buffers:
                config = self._configs.get(entity_id, self.default_config)
                self._buffers[entity_id] = InterpolationBuffer(config)
                self._sequences[entity_id] = 0
                self._stats['entities_tracked'] = len(self._buffers)

            # Create snapshot
            self._sequences[entity_id] += 1
            snapshot = StateSnapshot(
                timestamp=timestamp,
                state=state,
                sequence=self._sequences[entity_id],
                source=source
            )

            self._buffers[entity_id].add_snapshot(snapshot)
            self._stats['snapshots_received'] += 1

    def get_interpolated_state(
        self,
        entity_id: str,
        target_time: float = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get interpolated state for an entity.

        Args:
            entity_id: Entity identifier
            target_time: Target timestamp (default: now - delay)

        Returns:
            Interpolated state dictionary
        """
        with self._lock:
            buffer = self._buffers.get(entity_id)
            if not buffer:
                return None

            result = buffer.get_interpolated_state(target_time)

            if result:
                self._stats['interpolations_performed'] += 1

            return result

    def get_all_interpolated_states(
        self,
        target_time: float = None
    ) -> Dict[str, Dict[str, Any]]:
        """Get interpolated states for all entities."""
        with self._lock:
            result = {}
            for entity_id in self._buffers:
                state = self.get_interpolated_state(entity_id, target_time)
                if state:
                    result[entity_id] = state
            return result

    def set_config(self, entity_id: str, config: InterpolationConfig):
        """Set interpolation config for specific entity."""
        with self._lock:
            self._configs[entity_id] = config
            if entity_id in self._buffers:
                self._buffers[entity_id].config = config

    def sync_time(self, server_time: float):
        """Synchronize time with server."""
        local_time = time.time()
        self._time_offset = server_time - local_time
        logger.debug(f"Time sync: offset = {self._time_offset:.3f}s")

    def remove_entity(self, entity_id: str):
        """Remove entity from tracking."""
        with self._lock:
            self._buffers.pop(entity_id, None)
            self._configs.pop(entity_id, None)
            self._sequences.pop(entity_id, None)
            self._stats['entities_tracked'] = len(self._buffers)

    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            **self._stats,
            'time_offset': self._time_offset,
            'buffer_sizes': {
                eid: len(buf._buffer)
                for eid, buf in self._buffers.items()
            }
        }


class CatmullRomSpline:
    """Catmull-Rom spline for smooth trajectory interpolation."""

    def __init__(self, points: List[Vector3], tension: float = 0.5):
        self.points = points
        self.tension = tension

    def interpolate(self, t: float) -> Vector3:
        """Interpolate along spline at parameter t (0-1)."""
        if len(self.points) < 4:
            # Fall back to linear
            if len(self.points) < 2:
                return self.points[0] if self.points else Vector3()
            idx = int(t * (len(self.points) - 1))
            idx = min(idx, len(self.points) - 2)
            local_t = t * (len(self.points) - 1) - idx
            return self.points[idx].lerp(self.points[idx + 1], local_t)

        # Find segment
        n = len(self.points) - 3
        segment = int(t * n)
        segment = max(0, min(segment, n - 1))

        # Local t within segment
        local_t = t * n - segment

        # Get 4 control points
        p0 = self.points[segment]
        p1 = self.points[segment + 1]
        p2 = self.points[segment + 2]
        p3 = self.points[segment + 3]

        # Catmull-Rom coefficients
        t2 = local_t * local_t
        t3 = t2 * local_t

        # Calculate position
        x = 0.5 * (
            (2 * p1.x) +
            (-p0.x + p2.x) * local_t +
            (2*p0.x - 5*p1.x + 4*p2.x - p3.x) * t2 +
            (-p0.x + 3*p1.x - 3*p2.x + p3.x) * t3
        )
        y = 0.5 * (
            (2 * p1.y) +
            (-p0.y + p2.y) * local_t +
            (2*p0.y - 5*p1.y + 4*p2.y - p3.y) * t2 +
            (-p0.y + 3*p1.y - 3*p2.y + p3.y) * t3
        )
        z = 0.5 * (
            (2 * p1.z) +
            (-p0.z + p2.z) * local_t +
            (2*p0.z - 5*p1.z + 4*p2.z - p3.z) * t2 +
            (-p0.z + 3*p1.z - 3*p2.z + p3.z) * t3
        )

        return Vector3(x, y, z)


# Singleton instance
_interpolation_service: Optional[StateInterpolationService] = None


def get_interpolation_service() -> StateInterpolationService:
    """Get the global interpolation service instance."""
    global _interpolation_service
    if _interpolation_service is None:
        _interpolation_service = StateInterpolationService()
    return _interpolation_service
