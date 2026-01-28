"""
LEGO Factory v3 - Level 1 PLC Services
=======================================
Industrial PLC communication protocols for Level 1 control.

Supported Protocols:
- Modbus TCP/RTU (Allen-Bradley, Siemens S7, Schneider, etc.)
- OPC-UA (modern IIoT standard)
- EtherNet/IP (future)
- Profinet (future)
"""

from services.plc.modbus_client import ModbusClient, ModbusProtocol
from services.plc.opcua_client import OPCUAClient
from services.plc.plc_manager import PLCManager, PLCConnection

__all__ = [
    'ModbusClient',
    'ModbusProtocol',
    'OPCUAClient',
    'PLCManager',
    'PLCConnection',
]
