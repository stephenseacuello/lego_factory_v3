"""
MTConnect Adapter for Flask CNC SCADA
=====================================
Translates TinyG controller and sensor data to MTConnect format.

The adapter acts as the bridge between the proprietary TinyG protocol
and the standardized MTConnect data model.

Reference: MTConnect Standard v2.0 - Adapter Interface
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from collections import deque

from .data_items import (
    MTConnectDevice,
    MTConnectDataItem,
    DataItemCategory,
    ExecutionState,
    ControllerMode,
    AvailabilityState,
    ConditionState,
    create_tinyg_device,
)

logger = logging.getLogger(__name__)


@dataclass
class DataItemObservation:
    """
    A single observation of a data item value.

    Stored in the circular buffer for MTConnect current/sample queries.
    """
    data_item_id: str
    value: Any
    timestamp: datetime
    sequence: int


class MTConnectAdapter:
    """
    MTConnect Adapter for TinyG CNC Controller.

    Responsibilities:
    - Map TinyG status fields to MTConnect data items
    - Maintain circular buffer of observations
    - Track sequence numbers for streaming
    - Provide data for Agent queries (probe, current, sample)
    """

    def __init__(
        self,
        device_id: str = "tinyg-1",
        device_name: str = "Nomad3",
        buffer_size: int = 100000,
        instance_id: int = None,
    ):
        """
        Initialize MTConnect adapter.

        Args:
            device_id: Unique device identifier
            device_name: Human-readable device name
            buffer_size: Size of circular observation buffer
            instance_id: Agent instance ID (changes on restart)
        """
        self._lock = threading.RLock()
        self.device_id = device_id
        self.buffer_size = buffer_size
        self.instance_id = instance_id or int(time.time())

        # Create device model
        self.device = create_tinyg_device(device_id, device_name)

        # Build data item lookup
        self._data_items: Dict[str, MTConnectDataItem] = {}
        for item in self.device.get_all_data_items():
            self._data_items[item.id] = item

        # Circular buffer for observations
        self._buffer: deque = deque(maxlen=buffer_size)
        self._sequence = 0
        self._first_sequence = 0

        # Callbacks for data changes
        self._callbacks: List[Callable[[DataItemObservation], None]] = []

        # TinyG status mapping
        self._tinyg_map = self._create_tinyg_mapping()

        # Initialize all data items as UNAVAILABLE
        self._initialize_unavailable()

        logger.info(f"MTConnect adapter initialized for {device_id} with {len(self._data_items)} data items")

    def _create_tinyg_mapping(self) -> Dict[str, str]:
        """
        Create mapping from TinyG status fields to MTConnect data item IDs.

        TinyG status fields:
        - stat: Machine state (0-9)
        - line: Current G-code line
        - vel: Velocity (mm/min)
        - feed: Feed rate
        - unit: Units mode (0=inches, 1=mm)
        - coor: Coordinate system (G54-G59)
        - momo: Motion mode (G0, G1, G2, G3)
        - plan: Plane select (G17-G19)
        - path: Path control mode
        - dist: Distance mode (G90/G91)
        - frmo: Feed rate mode (G93/G94)
        - posx/y/z: Machine position
        - mpox/y/z: Machine position (alias)
        - wx/wy/wz: Work position (computed)
        - sps: Spindle speed (RPM)
        """
        return {
            # Positions
            'wx': f'{self.device_id}_xpos',
            'wy': f'{self.device_id}_ypos',
            'wz': f'{self.device_id}_zpos',
            'posx': f'{self.device_id}_xmpos',
            'posy': f'{self.device_id}_ympos',
            'posz': f'{self.device_id}_zmpos',
            'mpox': f'{self.device_id}_xmpos',
            'mpoy': f'{self.device_id}_ympos',
            'mpoz': f'{self.device_id}_zmpos',

            # Velocity/feedrate
            'vel': f'{self.device_id}_Frt',

            # Spindle
            'sps': f'{self.device_id}_Srpm',

            # State (needs transformation)
            'stat': f'{self.device_id}_exec',
            'line': f'{self.device_id}_line',
        }

    def _initialize_unavailable(self):
        """Set all data items to UNAVAILABLE state."""
        ts = datetime.utcnow()
        for item_id, item in self._data_items.items():
            self._add_observation(item_id, "UNAVAILABLE", ts)

    def _add_observation(
        self,
        data_item_id: str,
        value: Any,
        timestamp: datetime = None,
    ) -> Optional[DataItemObservation]:
        """
        Add an observation to the buffer.

        Args:
            data_item_id: Data item ID
            value: Observed value
            timestamp: Observation timestamp

        Returns:
            The observation if added, None if data item not found
        """
        if data_item_id not in self._data_items:
            logger.warning(f"Unknown data item: {data_item_id}")
            return None

        with self._lock:
            self._sequence += 1
            ts = timestamp or datetime.utcnow()

            obs = DataItemObservation(
                data_item_id=data_item_id,
                value=value,
                timestamp=ts,
                sequence=self._sequence,
            )

            self._buffer.append(obs)

            # Update data item's current value
            item = self._data_items[data_item_id]
            item.update(value, ts, self._sequence)

            # Update first sequence if buffer wrapped
            if len(self._buffer) == self.buffer_size:
                self._first_sequence = self._buffer[0].sequence

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(obs)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return obs

    def register_callback(self, callback: Callable[[DataItemObservation], None]):
        """Register a callback for data changes."""
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[DataItemObservation], None]):
        """Unregister a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    # =========================================================================
    # TinyG Integration
    # =========================================================================

    def update_from_tinyg(self, status: Dict[str, Any]):
        """
        Update data items from TinyG status report.

        Args:
            status: TinyG status dictionary (from JSON response)
        """
        ts = datetime.utcnow()

        # Set availability
        self._add_observation(f'{self.device_id}_avail', 'AVAILABLE', ts)

        # Map direct fields
        for tinyg_field, mtc_id in self._tinyg_map.items():
            if tinyg_field in status:
                value = status[tinyg_field]

                # Transform special fields
                if tinyg_field == 'stat':
                    value = self._map_tinyg_state(value)
                elif tinyg_field == 'vel':
                    # Convert mm/min to mm/s
                    value = round(value / 60.0, 3)

                self._add_observation(mtc_id, value, ts)

        # Set controller mode based on context
        # TinyG doesn't report mode directly, infer from state
        mode = ControllerMode.AUTOMATIC.value
        if status.get('stat') == 1:  # RESET
            mode = ControllerMode.MANUAL.value
        self._add_observation(f'{self.device_id}_mode', mode, ts)

    def _map_tinyg_state(self, stat: int) -> str:
        """
        Map TinyG stat value to MTConnect execution state.

        TinyG stat values:
        0 = Initializing
        1 = Ready (RESET)
        2 = Alarm
        3 = Program Stop
        4 = Program End
        5 = Run
        6 = Hold
        7 = Probe cycle
        8 = Cycle / Homing
        9 = Jog
        """
        mapping = {
            0: ExecutionState.STOPPED.value,
            1: ExecutionState.READY.value,
            2: ExecutionState.STOPPED.value,  # Alarm
            3: ExecutionState.PROGRAM_STOPPED.value,
            4: ExecutionState.PROGRAM_COMPLETED.value,
            5: ExecutionState.ACTIVE.value,
            6: ExecutionState.FEED_HOLD.value,
            7: ExecutionState.ACTIVE.value,  # Probe
            8: ExecutionState.ACTIVE.value,  # Homing
            9: ExecutionState.ACTIVE.value,  # Jog
        }
        return mapping.get(stat, ExecutionState.STOPPED.value)

    def update_motor_currents(self, currents: Dict[str, float]):
        """
        Update motor current data items from MCC DAQ.

        Args:
            currents: Dict with spindle, x_motor, y_motor, z_motor currents
        """
        ts = datetime.utcnow()
        for motor, current in currents.items():
            item_id = f'{self.device_id}_{motor}_amp'
            if item_id in self._data_items:
                self._add_observation(item_id, round(current, 3), ts)

    def update_sensor_data(self, sensor_data: Dict[str, Any]):
        """
        Update environmental data items from Arduino sensors.

        Args:
            sensor_data: Dict with temperature, vibration, pressure, etc.
        """
        ts = datetime.utcnow()

        if 'Temperature' in sensor_data:
            self._add_observation(f'{self.device_id}_temp', sensor_data['Temperature'], ts)

        if 'RMS' in sensor_data or 'vibration_rms' in sensor_data:
            # Convert RMS to acceleration (simplified)
            rms = sensor_data.get('RMS') or sensor_data.get('vibration_rms', 0)
            self._add_observation(f'{self.device_id}_vib', rms, ts)

        if 'Pressure' in sensor_data:
            # Convert hPa to Pa
            pressure = sensor_data['Pressure'] * 100
            self._add_observation(f'{self.device_id}_pressure', pressure, ts)

    def set_program_name(self, program: str):
        """Set the current program name."""
        self._add_observation(f'{self.device_id}_pgm', program)

    def set_unavailable(self):
        """Set device as unavailable (disconnected)."""
        self._add_observation(f'{self.device_id}_avail', 'UNAVAILABLE')

    # =========================================================================
    # Query Methods (for Agent)
    # =========================================================================

    def get_current_values(self) -> Dict[str, MTConnectDataItem]:
        """Get current values of all data items."""
        with self._lock:
            return dict(self._data_items)

    def get_current_sequence(self) -> int:
        """Get the current sequence number."""
        with self._lock:
            return self._sequence

    def get_first_sequence(self) -> int:
        """Get the first sequence in buffer."""
        with self._lock:
            return self._first_sequence

    def get_samples(
        self,
        from_sequence: int = 0,
        count: int = 100,
        path: str = None,
    ) -> List[DataItemObservation]:
        """
        Get observations from the buffer.

        Args:
            from_sequence: Start sequence number
            count: Maximum observations to return
            path: Filter by data item path (optional)

        Returns:
            List of observations
        """
        with self._lock:
            results = []
            for obs in self._buffer:
                if obs.sequence >= from_sequence:
                    if path is None or obs.data_item_id.startswith(path):
                        results.append(obs)
                        if len(results) >= count:
                            break
            return results

    def get_device(self) -> MTConnectDevice:
        """Get the device model."""
        return self.device


# =============================================================================
# WebSocket Streaming Integration
# =============================================================================

_websocket_callback_registered = False


def _websocket_observation_callback(obs: DataItemObservation):
    """
    Callback to push MTConnect observations via WebSocket.

    This enables real-time streaming of MTConnect data to web clients.
    """
    try:
        from services.socketio_service import emit_mtconnect_sample
        emit_mtconnect_sample({
            'dataItemId': obs.data_item_id,
            'value': obs.value,
            'timestamp': obs.timestamp.isoformat() if obs.timestamp else None,
            'sequence': obs.sequence,
        })
    except ImportError:
        pass  # SocketIO not available
    except Exception as e:
        logger.debug(f"WebSocket MTConnect emit error: {e}")


def _register_websocket_streaming(adapter: MTConnectAdapter):
    """Register WebSocket callback for real-time MTConnect streaming."""
    global _websocket_callback_registered
    if not _websocket_callback_registered:
        adapter.register_callback(_websocket_observation_callback)
        _websocket_callback_registered = True
        logger.info("MTConnect WebSocket streaming enabled")


# =============================================================================
# Singleton Instance
# =============================================================================

_adapter: Optional[MTConnectAdapter] = None


def get_mtconnect_adapter() -> MTConnectAdapter:
    """Get or create the MTConnect adapter singleton."""
    global _adapter
    if _adapter is None:
        _adapter = MTConnectAdapter()
        _register_websocket_streaming(_adapter)
    return _adapter


def init_mtconnect_adapter(
    device_id: str = "tinyg-1",
    device_name: str = "Nomad3",
    enable_websocket: bool = True,
) -> MTConnectAdapter:
    """
    Initialize the MTConnect adapter with custom settings.

    Args:
        device_id: MTConnect device ID
        device_name: Human-readable device name
        enable_websocket: Enable WebSocket streaming (default True)

    Returns:
        Configured MTConnectAdapter instance
    """
    global _adapter, _websocket_callback_registered
    _adapter = MTConnectAdapter(device_id, device_name)
    _websocket_callback_registered = False  # Reset for new adapter
    if enable_websocket:
        _register_websocket_streaming(_adapter)
    return _adapter
