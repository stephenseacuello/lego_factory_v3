"""
Modbus Protocol Adapter - Legacy PLC Communication

LegoMCP World-Class Manufacturing System v5.0
Phase 25: Edge Computing & IIoT

Provides Modbus client capabilities:
- Modbus TCP and RTU support
- Register read/write operations
- Coil operations
- Data type conversions
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import uuid
import struct


class ModbusProtocol(Enum):
    """Modbus protocol variants."""
    TCP = "TCP"
    RTU = "RTU"
    ASCII = "ASCII"


class ModbusFunctionCode(Enum):
    """Modbus function codes."""
    READ_COILS = 1
    READ_DISCRETE_INPUTS = 2
    READ_HOLDING_REGISTERS = 3
    READ_INPUT_REGISTERS = 4
    WRITE_SINGLE_COIL = 5
    WRITE_SINGLE_REGISTER = 6
    WRITE_MULTIPLE_COILS = 15
    WRITE_MULTIPLE_REGISTERS = 16


class ModbusDataType(Enum):
    """Data types for register interpretation."""
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    STRING = "string"
    BOOL = "bool"


@dataclass
class ModbusRegister:
    """A Modbus register definition."""
    address: int
    name: str
    data_type: ModbusDataType
    scale_factor: float = 1.0
    unit: str = ""
    description: str = ""
    read_only: bool = False


@dataclass
class ModbusDevice:
    """A Modbus device/slave."""
    device_id: str
    unit_id: int  # Slave address (1-247)
    name: str
    protocol: ModbusProtocol
    host: Optional[str] = None  # For TCP
    port: int = 502  # For TCP
    serial_port: Optional[str] = None  # For RTU
    baud_rate: int = 9600  # For RTU
    registers: Dict[str, ModbusRegister] = field(default_factory=dict)
    connected: bool = False
    last_poll: Optional[datetime] = None


@dataclass
class ModbusResponse:
    """Response from a Modbus operation."""
    success: bool
    function_code: ModbusFunctionCode
    address: int
    count: int
    values: List[int]
    interpreted_values: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error_code: Optional[int] = None
    error_message: Optional[str] = None


class ModbusAdapter:
    """
    Modbus protocol adapter for legacy PLC communication.

    Provides Modbus TCP and RTU client functionality for
    communicating with PLCs and industrial devices.
    """

    def __init__(self):
        self.devices: Dict[str, ModbusDevice] = {}
        self._register_values: Dict[str, Dict[int, int]] = {}
        self._setup_demo_devices()

    def _setup_demo_devices(self):
        """Set up demo Modbus devices."""
        # Simulated 3D printer PLC
        printer_plc = ModbusDevice(
            device_id='printer-plc-001',
            unit_id=1,
            name='3D Printer Controller',
            protocol=ModbusProtocol.TCP,
            host='192.168.1.100',
            port=502,
            connected=True,
        )

        # Define registers
        printer_plc.registers = {
            'nozzle_temp': ModbusRegister(
                address=0, name='Nozzle Temperature',
                data_type=ModbusDataType.FLOAT32, unit='°C',
            ),
            'bed_temp': ModbusRegister(
                address=2, name='Bed Temperature',
                data_type=ModbusDataType.FLOAT32, unit='°C',
            ),
            'fan_speed': ModbusRegister(
                address=4, name='Fan Speed',
                data_type=ModbusDataType.UINT16, unit='%',
            ),
            'print_progress': ModbusRegister(
                address=5, name='Print Progress',
                data_type=ModbusDataType.UINT16, unit='%', scale_factor=0.1,
            ),
            'layer_current': ModbusRegister(
                address=6, name='Current Layer',
                data_type=ModbusDataType.UINT16,
            ),
            'layer_total': ModbusRegister(
                address=7, name='Total Layers',
                data_type=ModbusDataType.UINT16,
            ),
            'status': ModbusRegister(
                address=8, name='Status Code',
                data_type=ModbusDataType.UINT16,
            ),
            'error_code': ModbusRegister(
                address=9, name='Error Code',
                data_type=ModbusDataType.UINT16, read_only=True,
            ),
        }

        self.devices[printer_plc.device_id] = printer_plc

        # Initialize simulated register values
        self._register_values['printer-plc-001'] = {
            0: 0x4358,  # 215.0 as float32 (high word)
            1: 0x0000,  # 215.0 as float32 (low word)
            2: 0x4270,  # 60.0 as float32 (high word)
            3: 0x0000,  # 60.0 as float32 (low word)
            4: 100,     # Fan speed 100%
            5: 455,     # Progress 45.5% (scaled by 10)
            6: 127,     # Current layer
            7: 280,     # Total layers
            8: 1,       # Status: Printing
            9: 0,       # No error
        }

    def add_device(self, device: ModbusDevice) -> bool:
        """Add a Modbus device."""
        self.devices[device.device_id] = device
        self._register_values[device.device_id] = {}
        return True

    def remove_device(self, device_id: str) -> bool:
        """Remove a Modbus device."""
        if device_id in self.devices:
            del self.devices[device_id]
            if device_id in self._register_values:
                del self._register_values[device_id]
            return True
        return False

    def connect(self, device_id: str) -> bool:
        """Connect to a Modbus device."""
        if device_id in self.devices:
            self.devices[device_id].connected = True
            return True
        return False

    def disconnect(self, device_id: str) -> bool:
        """Disconnect from a Modbus device."""
        if device_id in self.devices:
            self.devices[device_id].connected = False
            return True
        return False

    def read_holding_registers(
        self,
        device_id: str,
        address: int,
        count: int = 1
    ) -> ModbusResponse:
        """
        Read holding registers (FC 03).

        Args:
            device_id: Device ID
            address: Starting register address
            count: Number of registers to read

        Returns:
            ModbusResponse with register values
        """
        if device_id not in self.devices:
            return ModbusResponse(
                success=False,
                function_code=ModbusFunctionCode.READ_HOLDING_REGISTERS,
                address=address,
                count=count,
                values=[],
                error_code=0x02,
                error_message='Device not found',
            )

        device = self.devices[device_id]
        if not device.connected:
            return ModbusResponse(
                success=False,
                function_code=ModbusFunctionCode.READ_HOLDING_REGISTERS,
                address=address,
                count=count,
                values=[],
                error_code=0x0B,
                error_message='Device not connected',
            )

        # Get register values
        values = []
        for i in range(count):
            addr = address + i
            val = self._register_values.get(device_id, {}).get(addr, 0)
            values.append(val)

        device.last_poll = datetime.utcnow()

        return ModbusResponse(
            success=True,
            function_code=ModbusFunctionCode.READ_HOLDING_REGISTERS,
            address=address,
            count=count,
            values=values,
        )

    def write_single_register(
        self,
        device_id: str,
        address: int,
        value: int
    ) -> ModbusResponse:
        """
        Write single holding register (FC 06).

        Args:
            device_id: Device ID
            address: Register address
            value: Value to write (0-65535)

        Returns:
            ModbusResponse with result
        """
        if device_id not in self.devices:
            return ModbusResponse(
                success=False,
                function_code=ModbusFunctionCode.WRITE_SINGLE_REGISTER,
                address=address,
                count=1,
                values=[],
                error_code=0x02,
                error_message='Device not found',
            )

        device = self.devices[device_id]
        if not device.connected:
            return ModbusResponse(
                success=False,
                function_code=ModbusFunctionCode.WRITE_SINGLE_REGISTER,
                address=address,
                count=1,
                values=[],
                error_code=0x0B,
                error_message='Device not connected',
            )

        # Check if register is read-only
        for reg in device.registers.values():
            if reg.address == address and reg.read_only:
                return ModbusResponse(
                    success=False,
                    function_code=ModbusFunctionCode.WRITE_SINGLE_REGISTER,
                    address=address,
                    count=1,
                    values=[],
                    error_code=0x03,
                    error_message='Register is read-only',
                )

        # Write value
        if device_id not in self._register_values:
            self._register_values[device_id] = {}
        self._register_values[device_id][address] = value & 0xFFFF

        return ModbusResponse(
            success=True,
            function_code=ModbusFunctionCode.WRITE_SINGLE_REGISTER,
            address=address,
            count=1,
            values=[value],
        )

    def write_multiple_registers(
        self,
        device_id: str,
        address: int,
        values: List[int]
    ) -> ModbusResponse:
        """
        Write multiple holding registers (FC 16).

        Args:
            device_id: Device ID
            address: Starting register address
            values: Values to write

        Returns:
            ModbusResponse with result
        """
        if device_id not in self.devices:
            return ModbusResponse(
                success=False,
                function_code=ModbusFunctionCode.WRITE_MULTIPLE_REGISTERS,
                address=address,
                count=len(values),
                values=[],
                error_code=0x02,
                error_message='Device not found',
            )

        device = self.devices[device_id]
        if not device.connected:
            return ModbusResponse(
                success=False,
                function_code=ModbusFunctionCode.WRITE_MULTIPLE_REGISTERS,
                address=address,
                count=len(values),
                values=[],
                error_code=0x0B,
                error_message='Device not connected',
            )

        # Write values
        if device_id not in self._register_values:
            self._register_values[device_id] = {}

        for i, val in enumerate(values):
            self._register_values[device_id][address + i] = val & 0xFFFF

        return ModbusResponse(
            success=True,
            function_code=ModbusFunctionCode.WRITE_MULTIPLE_REGISTERS,
            address=address,
            count=len(values),
            values=values,
        )

    def read_named_register(
        self,
        device_id: str,
        register_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Read a named register with type interpretation.

        Args:
            device_id: Device ID
            register_name: Register name from device definition

        Returns:
            Dictionary with value and metadata
        """
        if device_id not in self.devices:
            return None

        device = self.devices[device_id]
        if register_name not in device.registers:
            return None

        reg = device.registers[register_name]

        # Determine register count based on data type
        count = 1
        if reg.data_type in [ModbusDataType.INT32, ModbusDataType.UINT32, ModbusDataType.FLOAT32]:
            count = 2
        elif reg.data_type == ModbusDataType.FLOAT64:
            count = 4

        response = self.read_holding_registers(device_id, reg.address, count)
        if not response.success:
            return None

        # Interpret value
        raw_value = response.values
        interpreted = self._interpret_value(raw_value, reg.data_type)
        scaled = interpreted * reg.scale_factor

        return {
            'name': reg.name,
            'address': reg.address,
            'raw_values': raw_value,
            'value': scaled,
            'unit': reg.unit,
            'data_type': reg.data_type.value,
            'timestamp': response.timestamp.isoformat(),
        }

    def _interpret_value(
        self,
        registers: List[int],
        data_type: ModbusDataType
    ) -> Union[int, float, bool, str]:
        """Interpret register values based on data type."""
        if data_type == ModbusDataType.UINT16:
            return registers[0]
        elif data_type == ModbusDataType.INT16:
            val = registers[0]
            return val if val < 32768 else val - 65536
        elif data_type == ModbusDataType.UINT32:
            return (registers[0] << 16) | registers[1]
        elif data_type == ModbusDataType.INT32:
            val = (registers[0] << 16) | registers[1]
            return val if val < 2147483648 else val - 4294967296
        elif data_type == ModbusDataType.FLOAT32:
            # Combine registers and interpret as float
            combined = (registers[0] << 16) | registers[1]
            return struct.unpack('>f', struct.pack('>I', combined))[0]
        elif data_type == ModbusDataType.BOOL:
            return registers[0] != 0

        return registers[0]

    def get_device_status(self, device_id: str) -> Optional[Dict]:
        """Get device status."""
        if device_id not in self.devices:
            return None

        device = self.devices[device_id]
        return {
            'device_id': device.device_id,
            'name': device.name,
            'unit_id': device.unit_id,
            'protocol': device.protocol.value,
            'host': device.host,
            'port': device.port,
            'connected': device.connected,
            'register_count': len(device.registers),
            'last_poll': device.last_poll.isoformat() if device.last_poll else None,
        }

    def get_all_devices(self) -> List[Dict]:
        """Get all device statuses."""
        return [
            self.get_device_status(device_id)
            for device_id in self.devices
        ]


# Singleton instance
_modbus_adapter: Optional[ModbusAdapter] = None


def get_modbus_adapter() -> ModbusAdapter:
    """Get or create the Modbus adapter instance."""
    global _modbus_adapter
    if _modbus_adapter is None:
        _modbus_adapter = ModbusAdapter()
    return _modbus_adapter
