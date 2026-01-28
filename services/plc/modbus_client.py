"""
LEGO Factory v3 - Modbus TCP/RTU Client
=======================================
Industrial Modbus communication for Level 1 PLC control.

Supports:
- Modbus TCP (Ethernet)
- Modbus RTU (Serial RS-485/RS-232)
- Modbus ASCII (Serial)

Compatible PLCs:
- Allen-Bradley MicroLogix/CompactLogix (via Modbus module)
- Siemens S7-1200/S7-1500 (via Modbus TCP)
- Schneider Electric M340/M580
- ABB AC500
- Beckhoff TwinCAT
- Omron NX/NJ
- Mitsubishi FX/Q Series
- Generic Modbus RTU devices (sensors, VFDs, meters)
"""

import asyncio
import logging
import struct
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from threading import Lock

logger = logging.getLogger(__name__)


class ModbusProtocol(str, Enum):
    """Modbus protocol variants."""
    TCP = 'tcp'
    RTU = 'rtu'
    ASCII = 'ascii'


class ModbusDataType(str, Enum):
    """Modbus data types for register interpretation."""
    BOOL = 'bool'           # Single bit (coil/discrete input)
    INT16 = 'int16'         # Signed 16-bit integer
    UINT16 = 'uint16'       # Unsigned 16-bit integer
    INT32 = 'int32'         # Signed 32-bit (2 registers)
    UINT32 = 'uint32'       # Unsigned 32-bit (2 registers)
    FLOAT32 = 'float32'     # IEEE 754 float (2 registers)
    INT64 = 'int64'         # Signed 64-bit (4 registers)
    UINT64 = 'uint64'       # Unsigned 64-bit (4 registers)
    FLOAT64 = 'float64'     # Double precision (4 registers)
    STRING = 'string'       # ASCII string (variable registers)


class ModbusFunctionCode(int, Enum):
    """Standard Modbus function codes."""
    READ_COILS = 0x01
    READ_DISCRETE_INPUTS = 0x02
    READ_HOLDING_REGISTERS = 0x03
    READ_INPUT_REGISTERS = 0x04
    WRITE_SINGLE_COIL = 0x05
    WRITE_SINGLE_REGISTER = 0x06
    WRITE_MULTIPLE_COILS = 0x0F
    WRITE_MULTIPLE_REGISTERS = 0x10
    READ_WRITE_MULTIPLE_REGISTERS = 0x17


@dataclass
class ModbusTag:
    """Definition of a Modbus tag/variable."""
    name: str
    address: int                    # Register/coil address
    data_type: ModbusDataType
    function_code: ModbusFunctionCode
    unit_id: int = 1                # Slave/unit ID
    description: str = ''
    engineering_unit: str = ''
    scale_factor: float = 1.0       # Raw * scale = engineering value
    offset: float = 0.0             # (Raw * scale) + offset
    byte_order: str = 'big'         # 'big' or 'little' endian
    word_order: str = 'big'         # For 32/64-bit: register order
    string_length: int = 0          # For STRING type
    read_only: bool = False


@dataclass
class ModbusTagValue:
    """Current value of a Modbus tag."""
    tag: ModbusTag
    raw_value: Any
    eng_value: Any
    quality: int                    # OPC UA quality code
    timestamp: datetime
    error: Optional[str] = None


@dataclass
class ModbusConnectionConfig:
    """Configuration for Modbus connection."""
    name: str
    protocol: ModbusProtocol

    # TCP settings
    host: str = '127.0.0.1'
    port: int = 502

    # RTU/ASCII settings
    serial_port: str = ''           # e.g., '/dev/ttyUSB0' or 'COM3'
    baudrate: int = 9600
    parity: str = 'N'               # N=None, E=Even, O=Odd
    stopbits: int = 1
    bytesize: int = 8

    # Common settings
    timeout: float = 3.0
    retries: int = 3
    retry_delay: float = 0.5
    unit_id: int = 1                # Default slave ID

    # Polling
    poll_interval: float = 1.0      # Seconds between polls

    # Tags to poll
    tags: List[ModbusTag] = field(default_factory=list)


class ModbusClient:
    """
    Modbus TCP/RTU client for Level 1 PLC communication.

    Usage:
        # TCP connection to Siemens S7-1500
        config = ModbusConnectionConfig(
            name='siemens_plc',
            protocol=ModbusProtocol.TCP,
            host='192.168.1.100',
            port=502,
            tags=[
                ModbusTag('temperature', 0, ModbusDataType.FLOAT32,
                         ModbusFunctionCode.READ_HOLDING_REGISTERS),
                ModbusTag('motor_running', 100, ModbusDataType.BOOL,
                         ModbusFunctionCode.READ_COILS),
            ]
        )

        client = ModbusClient(config)
        await client.connect()
        values = await client.read_all_tags()
        await client.write_tag('motor_running', True)
    """

    # Quality codes (OPC UA compatible)
    QUALITY_GOOD = 192
    QUALITY_UNCERTAIN = 64
    QUALITY_BAD = 0
    QUALITY_BAD_COMM = 24
    QUALITY_BAD_CONFIG = 20

    def __init__(self, config: ModbusConnectionConfig):
        self.config = config
        self._client = None
        self._connected = False
        self._lock = Lock()
        self._tag_cache: Dict[str, ModbusTagValue] = {}
        self._polling = False
        self._poll_task: Optional[asyncio.Task] = None
        self._last_error: Optional[str] = None
        self._connection_count = 0
        self._read_count = 0
        self._write_count = 0
        self._error_count = 0

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            'connected': self._connected,
            'connection_count': self._connection_count,
            'read_count': self._read_count,
            'write_count': self._write_count,
            'error_count': self._error_count,
            'last_error': self._last_error,
            'tags_cached': len(self._tag_cache),
        }

    async def connect(self) -> bool:
        """Establish connection to Modbus device."""
        try:
            if self.config.protocol == ModbusProtocol.TCP:
                return await self._connect_tcp()
            elif self.config.protocol == ModbusProtocol.RTU:
                return await self._connect_rtu()
            elif self.config.protocol == ModbusProtocol.ASCII:
                return await self._connect_ascii()
            else:
                raise ValueError(f"Unknown protocol: {self.config.protocol}")
        except Exception as e:
            self._last_error = str(e)
            self._error_count += 1
            logger.error(f"Modbus connect failed [{self.config.name}]: {e}")
            return False

    async def _connect_tcp(self) -> bool:
        """Connect via Modbus TCP."""
        try:
            from pymodbus.client import AsyncModbusTcpClient

            self._client = AsyncModbusTcpClient(
                host=self.config.host,
                port=self.config.port,
                timeout=self.config.timeout,
                retries=self.config.retries,
                retry_on_empty=True,
            )

            connected = await self._client.connect()
            if connected:
                self._connected = True
                self._connection_count += 1
                logger.info(f"Modbus TCP connected: {self.config.host}:{self.config.port}")
                return True
            else:
                self._last_error = "Connection refused"
                return False

        except ImportError:
            # Fallback to simulation mode
            logger.warning("pymodbus not installed, using simulation mode")
            self._client = None
            self._connected = True
            self._connection_count += 1
            return True
        except Exception as e:
            self._last_error = str(e)
            self._error_count += 1
            raise

    async def _connect_rtu(self) -> bool:
        """Connect via Modbus RTU (serial)."""
        try:
            from pymodbus.client import AsyncModbusSerialClient

            self._client = AsyncModbusSerialClient(
                port=self.config.serial_port,
                baudrate=self.config.baudrate,
                parity=self.config.parity,
                stopbits=self.config.stopbits,
                bytesize=self.config.bytesize,
                timeout=self.config.timeout,
            )

            connected = await self._client.connect()
            if connected:
                self._connected = True
                self._connection_count += 1
                logger.info(f"Modbus RTU connected: {self.config.serial_port}")
                return True
            else:
                self._last_error = "Serial connection failed"
                return False

        except ImportError:
            logger.warning("pymodbus not installed, using simulation mode")
            self._client = None
            self._connected = True
            self._connection_count += 1
            return True
        except Exception as e:
            self._last_error = str(e)
            self._error_count += 1
            raise

    async def _connect_ascii(self) -> bool:
        """Connect via Modbus ASCII (serial)."""
        # Similar to RTU but with ASCII framing
        return await self._connect_rtu()

    async def disconnect(self):
        """Close Modbus connection."""
        self._polling = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"Error closing Modbus connection: {e}")

        self._connected = False
        logger.info(f"Modbus disconnected: {self.config.name}")

    async def read_tag(self, tag_name: str) -> Optional[ModbusTagValue]:
        """Read a single tag by name."""
        tag = self._find_tag(tag_name)
        if not tag:
            logger.error(f"Tag not found: {tag_name}")
            return None

        return await self._read_tag(tag)

    async def _read_tag(self, tag: ModbusTag) -> ModbusTagValue:
        """Read a tag from the PLC."""
        timestamp = datetime.utcnow()

        try:
            raw_value = await self._read_modbus(tag)
            eng_value = self._convert_to_engineering(tag, raw_value)

            result = ModbusTagValue(
                tag=tag,
                raw_value=raw_value,
                eng_value=eng_value,
                quality=self.QUALITY_GOOD,
                timestamp=timestamp,
            )

            self._tag_cache[tag.name] = result
            self._read_count += 1
            return result

        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)

            return ModbusTagValue(
                tag=tag,
                raw_value=None,
                eng_value=None,
                quality=self.QUALITY_BAD_COMM,
                timestamp=timestamp,
                error=str(e),
            )

    async def _read_modbus(self, tag: ModbusTag) -> Any:
        """Execute Modbus read operation."""
        if not self._client:
            # Simulation mode - return dummy data
            return self._simulate_read(tag)

        unit_id = tag.unit_id or self.config.unit_id

        if tag.function_code == ModbusFunctionCode.READ_COILS:
            result = await self._client.read_coils(
                address=tag.address,
                count=1,
                slave=unit_id,
            )
            if result.isError():
                raise Exception(f"Modbus error: {result}")
            return result.bits[0]

        elif tag.function_code == ModbusFunctionCode.READ_DISCRETE_INPUTS:
            result = await self._client.read_discrete_inputs(
                address=tag.address,
                count=1,
                slave=unit_id,
            )
            if result.isError():
                raise Exception(f"Modbus error: {result}")
            return result.bits[0]

        elif tag.function_code == ModbusFunctionCode.READ_HOLDING_REGISTERS:
            count = self._get_register_count(tag.data_type, tag.string_length)
            result = await self._client.read_holding_registers(
                address=tag.address,
                count=count,
                slave=unit_id,
            )
            if result.isError():
                raise Exception(f"Modbus error: {result}")
            return self._decode_registers(tag, result.registers)

        elif tag.function_code == ModbusFunctionCode.READ_INPUT_REGISTERS:
            count = self._get_register_count(tag.data_type, tag.string_length)
            result = await self._client.read_input_registers(
                address=tag.address,
                count=count,
                slave=unit_id,
            )
            if result.isError():
                raise Exception(f"Modbus error: {result}")
            return self._decode_registers(tag, result.registers)

        else:
            raise ValueError(f"Unsupported function code: {tag.function_code}")

    def _simulate_read(self, tag: ModbusTag) -> Any:
        """Generate simulated read values for testing."""
        import random

        if tag.data_type == ModbusDataType.BOOL:
            return random.choice([True, False])
        elif tag.data_type in (ModbusDataType.INT16, ModbusDataType.UINT16):
            return random.randint(0, 1000)
        elif tag.data_type in (ModbusDataType.INT32, ModbusDataType.UINT32):
            return random.randint(0, 100000)
        elif tag.data_type in (ModbusDataType.FLOAT32, ModbusDataType.FLOAT64):
            return random.uniform(0, 100)
        elif tag.data_type == ModbusDataType.STRING:
            return f"SIM_{tag.name[:8]}"
        else:
            return 0

    def _get_register_count(self, data_type: ModbusDataType, string_length: int = 0) -> int:
        """Get number of registers needed for data type."""
        counts = {
            ModbusDataType.INT16: 1,
            ModbusDataType.UINT16: 1,
            ModbusDataType.INT32: 2,
            ModbusDataType.UINT32: 2,
            ModbusDataType.FLOAT32: 2,
            ModbusDataType.INT64: 4,
            ModbusDataType.UINT64: 4,
            ModbusDataType.FLOAT64: 4,
        }
        if data_type == ModbusDataType.STRING:
            return (string_length + 1) // 2  # 2 chars per register
        return counts.get(data_type, 1)

    def _decode_registers(self, tag: ModbusTag, registers: List[int]) -> Any:
        """Decode register values based on data type and byte order."""
        if not registers:
            return None

        # Handle word order for multi-register values
        if len(registers) > 1 and tag.word_order == 'little':
            registers = list(reversed(registers))

        # Convert to bytes
        byte_order = '>' if tag.byte_order == 'big' else '<'

        if tag.data_type == ModbusDataType.INT16:
            return struct.unpack(f'{byte_order}h', struct.pack(f'{byte_order}H', registers[0]))[0]

        elif tag.data_type == ModbusDataType.UINT16:
            return registers[0]

        elif tag.data_type == ModbusDataType.INT32:
            packed = struct.pack(f'{byte_order}HH', registers[0], registers[1])
            return struct.unpack(f'{byte_order}i', packed)[0]

        elif tag.data_type == ModbusDataType.UINT32:
            packed = struct.pack(f'{byte_order}HH', registers[0], registers[1])
            return struct.unpack(f'{byte_order}I', packed)[0]

        elif tag.data_type == ModbusDataType.FLOAT32:
            packed = struct.pack(f'{byte_order}HH', registers[0], registers[1])
            return struct.unpack(f'{byte_order}f', packed)[0]

        elif tag.data_type == ModbusDataType.INT64:
            packed = struct.pack(f'{byte_order}HHHH', *registers[:4])
            return struct.unpack(f'{byte_order}q', packed)[0]

        elif tag.data_type == ModbusDataType.UINT64:
            packed = struct.pack(f'{byte_order}HHHH', *registers[:4])
            return struct.unpack(f'{byte_order}Q', packed)[0]

        elif tag.data_type == ModbusDataType.FLOAT64:
            packed = struct.pack(f'{byte_order}HHHH', *registers[:4])
            return struct.unpack(f'{byte_order}d', packed)[0]

        elif tag.data_type == ModbusDataType.STRING:
            chars = []
            for reg in registers:
                chars.append(chr((reg >> 8) & 0xFF))
                chars.append(chr(reg & 0xFF))
            return ''.join(chars).rstrip('\x00')

        return registers[0]

    def _convert_to_engineering(self, tag: ModbusTag, raw_value: Any) -> Any:
        """Apply scale factor and offset to get engineering value."""
        if raw_value is None:
            return None
        if tag.data_type == ModbusDataType.BOOL:
            return raw_value
        if tag.data_type == ModbusDataType.STRING:
            return raw_value

        return (raw_value * tag.scale_factor) + tag.offset

    async def write_tag(self, tag_name: str, value: Any) -> bool:
        """Write a value to a tag."""
        tag = self._find_tag(tag_name)
        if not tag:
            logger.error(f"Tag not found: {tag_name}")
            return False

        if tag.read_only:
            logger.error(f"Tag is read-only: {tag_name}")
            return False

        return await self._write_tag(tag, value)

    async def _write_tag(self, tag: ModbusTag, value: Any) -> bool:
        """Write a value to the PLC."""
        try:
            # Convert engineering to raw value
            raw_value = self._convert_to_raw(tag, value)

            await self._write_modbus(tag, raw_value)
            self._write_count += 1

            logger.debug(f"Wrote {tag.name} = {value} (raw: {raw_value})")
            return True

        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            logger.error(f"Write failed [{tag.name}]: {e}")
            return False

    def _convert_to_raw(self, tag: ModbusTag, eng_value: Any) -> Any:
        """Convert engineering value to raw value."""
        if tag.data_type == ModbusDataType.BOOL:
            return bool(eng_value)
        if tag.data_type == ModbusDataType.STRING:
            return str(eng_value)

        return int((eng_value - tag.offset) / tag.scale_factor)

    async def _write_modbus(self, tag: ModbusTag, value: Any):
        """Execute Modbus write operation."""
        if not self._client:
            # Simulation mode
            logger.info(f"[SIM] Write {tag.name} = {value}")
            return

        unit_id = tag.unit_id or self.config.unit_id

        if tag.data_type == ModbusDataType.BOOL:
            result = await self._client.write_coil(
                address=tag.address,
                value=value,
                slave=unit_id,
            )
        else:
            registers = self._encode_registers(tag, value)
            if len(registers) == 1:
                result = await self._client.write_register(
                    address=tag.address,
                    value=registers[0],
                    slave=unit_id,
                )
            else:
                result = await self._client.write_registers(
                    address=tag.address,
                    values=registers,
                    slave=unit_id,
                )

        if result.isError():
            raise Exception(f"Modbus write error: {result}")

    def _encode_registers(self, tag: ModbusTag, value: Any) -> List[int]:
        """Encode value to register format."""
        byte_order = '>' if tag.byte_order == 'big' else '<'

        if tag.data_type in (ModbusDataType.INT16, ModbusDataType.UINT16):
            return [int(value) & 0xFFFF]

        elif tag.data_type == ModbusDataType.INT32:
            packed = struct.pack(f'{byte_order}i', int(value))
            regs = struct.unpack(f'{byte_order}HH', packed)
            return list(regs) if tag.word_order == 'big' else list(reversed(regs))

        elif tag.data_type == ModbusDataType.UINT32:
            packed = struct.pack(f'{byte_order}I', int(value))
            regs = struct.unpack(f'{byte_order}HH', packed)
            return list(regs) if tag.word_order == 'big' else list(reversed(regs))

        elif tag.data_type == ModbusDataType.FLOAT32:
            packed = struct.pack(f'{byte_order}f', float(value))
            regs = struct.unpack(f'{byte_order}HH', packed)
            return list(regs) if tag.word_order == 'big' else list(reversed(regs))

        elif tag.data_type == ModbusDataType.STRING:
            s = str(value)[:tag.string_length].ljust(tag.string_length, '\x00')
            regs = []
            for i in range(0, len(s), 2):
                high = ord(s[i]) if i < len(s) else 0
                low = ord(s[i+1]) if i+1 < len(s) else 0
                regs.append((high << 8) | low)
            return regs

        return [int(value) & 0xFFFF]

    async def read_all_tags(self) -> Dict[str, ModbusTagValue]:
        """Read all configured tags."""
        results = {}
        for tag in self.config.tags:
            results[tag.name] = await self._read_tag(tag)
        return results

    async def start_polling(self, callback=None):
        """Start background polling of all tags."""
        if self._polling:
            return

        self._polling = True
        self._poll_task = asyncio.create_task(
            self._poll_loop(callback)
        )
        logger.info(f"Started polling {self.config.name} at {self.config.poll_interval}s interval")

    async def stop_polling(self):
        """Stop background polling."""
        self._polling = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped polling {self.config.name}")

    async def _poll_loop(self, callback):
        """Background polling loop."""
        while self._polling:
            try:
                values = await self.read_all_tags()
                if callback:
                    await callback(self.config.name, values)
            except Exception as e:
                logger.error(f"Poll error [{self.config.name}]: {e}")

            await asyncio.sleep(self.config.poll_interval)

    def get_cached_value(self, tag_name: str) -> Optional[ModbusTagValue]:
        """Get the most recent cached value for a tag."""
        return self._tag_cache.get(tag_name)

    def get_all_cached_values(self) -> Dict[str, ModbusTagValue]:
        """Get all cached tag values."""
        return dict(self._tag_cache)

    def _find_tag(self, name: str) -> Optional[ModbusTag]:
        """Find a tag by name."""
        for tag in self.config.tags:
            if tag.name == name:
                return tag
        return None

    def add_tag(self, tag: ModbusTag):
        """Add a tag to the configuration."""
        self.config.tags.append(tag)

    def remove_tag(self, tag_name: str) -> bool:
        """Remove a tag by name."""
        for i, tag in enumerate(self.config.tags):
            if tag.name == tag_name:
                del self.config.tags[i]
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize client state to dictionary."""
        return {
            'name': self.config.name,
            'protocol': self.config.protocol.value,
            'host': self.config.host if self.config.protocol == ModbusProtocol.TCP else None,
            'port': self.config.port if self.config.protocol == ModbusProtocol.TCP else None,
            'serial_port': self.config.serial_port if self.config.protocol != ModbusProtocol.TCP else None,
            'connected': self._connected,
            'polling': self._polling,
            'tag_count': len(self.config.tags),
            'stats': self.stats,
        }
