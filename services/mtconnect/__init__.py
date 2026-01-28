"""
MTConnect Services for Flask CNC SCADA
======================================
Industry-standard MTConnect adapter and agent implementation.

MTConnect is an open, royalty-free standard for manufacturing
equipment data exchange (mtconnect.org).

Components:
- Adapter: Translates TinyG/sensor data to MTConnect format
- Agent: HTTP server exposing MTConnect XML/REST API
- DataItems: Standard data item definitions per MTConnect spec

Usage:
    from services.mtconnect import (
        get_mtconnect_adapter,
        get_mtconnect_agent,
        MTConnectDataItem,
    )
"""

from .adapter import MTConnectAdapter, get_mtconnect_adapter
from .agent import MTConnectAgent, get_mtconnect_agent
from .data_items import (
    MTConnectDataItem,
    DataItemCategory,
    DataItemType,
    DEVICE_DATA_ITEMS,
)

__all__ = [
    'MTConnectAdapter',
    'get_mtconnect_adapter',
    'MTConnectAgent',
    'get_mtconnect_agent',
    'MTConnectDataItem',
    'DataItemCategory',
    'DataItemType',
    'DEVICE_DATA_ITEMS',
]
