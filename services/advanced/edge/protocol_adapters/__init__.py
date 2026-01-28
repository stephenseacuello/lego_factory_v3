"""
Protocol Adapters for IIoT Communication

LegoMCP World-Class Manufacturing System v5.0
Phase 25: Edge Computing & IIoT

Supports:
- OPC-UA (Industrial automation standard, OPC 40501 CNC)
- MQTT (Lightweight messaging)
- Modbus TCP/RTU (Legacy PLC communication)
- MTConnect (ANSI/MTC1.4-2018 CNC data streaming)
- Sparkplug B (IIoT MQTT specification with birth/death)
"""

from .opcua_adapter import OPCUAAdapter, get_opcua_adapter
from .mqtt_adapter import MQTTAdapter, get_mqtt_adapter
from .modbus_adapter import ModbusAdapter, get_modbus_adapter
from .mtconnect_adapter import (
    MTConnectAdapter,
    MTConnectAgent,
    MTConnectDataItem,
    create_cnc_device,
)
from .sparkplug_b import (
    SparkplugBEdgeNode,
    SparkplugBHostApplication,
    SparkplugMetric,
    MetricDataType,
)

__all__ = [
    # OPC-UA
    'OPCUAAdapter',
    'get_opcua_adapter',
    # MQTT
    'MQTTAdapter',
    'get_mqtt_adapter',
    # Modbus
    'ModbusAdapter',
    'get_modbus_adapter',
    # MTConnect
    'MTConnectAdapter',
    'MTConnectAgent',
    'MTConnectDataItem',
    'create_cnc_device',
    # Sparkplug B
    'SparkplugBEdgeNode',
    'SparkplugBHostApplication',
    'SparkplugMetric',
    'MetricDataType',
]
