"""
MTConnect Agent Implementation

HTTP server providing MTConnect XML responses for
connected manufacturing devices.

Reference: MTConnect Standard v2.0 (REST API)
"""

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """MTConnect Agent Configuration."""
    # Server
    host: str = "0.0.0.0"
    http_port: int = 5000
    adapter_port: int = 7878

    # Instance
    instance_id: int = 0
    sender: str = "LEGO MCP Agent"
    version: str = "2.0"

    # Buffer
    buffer_size: int = 131072  # Sequence buffer size
    checkpoint_frequency: int = 1000

    # Assets
    max_assets: int = 1024
    max_asset_size: int = 1048576  # 1MB


@dataclass
class StreamData:
    """Data item value with sequence number."""
    sequence: int
    timestamp: float
    data_item_id: str
    value: Any
    is_unavailable: bool = False


class MTConnectAgent:
    """
    MTConnect Agent Implementation.

    Provides HTTP REST API for MTConnect data access:
    - /probe - Device information
    - /current - Current values
    - /sample - Historical samples
    - /assets - Asset documents

    Usage:
        >>> agent = MTConnectAgent(config)
        >>> agent.add_device(device)
        >>> await agent.start()
    """

    # XML namespaces
    MTConnect_NS = "urn:mtconnect.org:MTConnectDevices:2.0"
    MTConnect_STREAMS_NS = "urn:mtconnect.org:MTConnectStreams:2.0"
    MTConnect_ASSETS_NS = "urn:mtconnect.org:MTConnectAssets:2.0"
    MTConnect_ERROR_NS = "urn:mtconnect.org:MTConnectError:2.0"

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize MTConnect Agent.

        Args:
            config: Agent configuration
        """
        self.config = config or AgentConfig()

        # Devices
        self._devices: Dict[str, Any] = {}

        # Data buffer (circular)
        self._buffer: deque = deque(maxlen=self.config.buffer_size)
        self._sequence = 1
        self._first_sequence = 1

        # Assets
        self._assets: Dict[str, Dict] = {}

        # Adapter connections
        self._adapters: Dict[str, asyncio.StreamReader] = {}

        # Server
        self._server = None
        self._adapter_server = None
        self._running = False

        logger.info(f"MTConnectAgent initialized on port {self.config.http_port}")

    def add_device(self, device: "MTConnectDevice") -> None:
        """
        Add a device to the agent.

        Args:
            device: MTConnect device definition
        """
        self._devices[device.uuid] = device
        logger.info(f"Added device: {device.name} ({device.uuid})")

    async def start(self) -> bool:
        """
        Start the MTConnect Agent.

        Returns:
            True if started successfully
        """
        if self._running:
            return True

        try:
            self._running = True

            # Start adapter listener
            self._adapter_server = await asyncio.start_server(
                self._handle_adapter_connection,
                self.config.host,
                self.config.adapter_port
            )

            # Start HTTP server (using basic implementation)
            # In production, would use aiohttp or similar
            self._server = await asyncio.start_server(
                self._handle_http_request,
                self.config.host,
                self.config.http_port
            )

            logger.info(f"Agent started - HTTP:{self.config.http_port}, Adapter:{self.config.adapter_port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start agent: {e}")
            self._running = False
            return False

    async def stop(self) -> None:
        """Stop the agent."""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        if self._adapter_server:
            self._adapter_server.close()
            await self._adapter_server.wait_closed()

        logger.info("Agent stopped")

    async def _handle_adapter_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming adapter connection."""
        addr = writer.get_extra_info('peername')
        logger.info(f"Adapter connected from {addr}")

        try:
            while self._running:
                line = await reader.readline()
                if not line:
                    break

                self._process_shdr_line(line.decode('utf-8').strip())

        except Exception as e:
            logger.error(f"Adapter connection error: {e}")
        finally:
            writer.close()
            logger.info(f"Adapter disconnected: {addr}")

    def _process_shdr_line(self, line: str) -> None:
        """Process SHDR data line from adapter."""
        if not line or line.startswith('*'):
            return  # Heartbeat or comment

        parts = line.split('|')
        if len(parts) < 3:
            return

        try:
            timestamp_str = parts[0]
            data_item_id = parts[1]
            value = parts[2] if len(parts) > 2 else ""

            # Parse timestamp
            try:
                dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")
                timestamp = dt.timestamp()
            except ValueError:
                timestamp = time.time()

            # Add to buffer
            is_unavailable = value == "UNAVAILABLE"
            stream_data = StreamData(
                sequence=self._sequence,
                timestamp=timestamp,
                data_item_id=data_item_id,
                value=value,
                is_unavailable=is_unavailable
            )

            self._buffer.append(stream_data)
            self._sequence += 1

            # Update first sequence if buffer full
            if len(self._buffer) == self.config.buffer_size:
                self._first_sequence = self._buffer[0].sequence

        except Exception as e:
            logger.error(f"Error processing SHDR: {e}")

    async def _handle_http_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle HTTP request."""
        try:
            request_line = await reader.readline()
            if not request_line:
                return

            # Parse request
            parts = request_line.decode('utf-8').strip().split()
            if len(parts) < 2:
                return

            method = parts[0]
            path = parts[1]

            # Read headers
            headers = {}
            while True:
                header_line = await reader.readline()
                if header_line == b'\r\n' or not header_line:
                    break
                header = header_line.decode('utf-8').strip()
                if ':' in header:
                    key, value = header.split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            # Route request
            if path.startswith('/probe'):
                response = self._handle_probe(path)
            elif path.startswith('/current'):
                response = self._handle_current(path)
            elif path.startswith('/sample'):
                response = self._handle_sample(path)
            elif path.startswith('/assets'):
                response = self._handle_assets(path)
            else:
                response = self._error_response("NOT_FOUND", "Invalid request path")

            # Send response
            http_response = f"HTTP/1.1 200 OK\r\nContent-Type: application/xml\r\nContent-Length: {len(response)}\r\n\r\n{response}"
            writer.write(http_response.encode('utf-8'))
            await writer.drain()

        except Exception as e:
            logger.error(f"HTTP request error: {e}")
        finally:
            writer.close()

    def _handle_probe(self, path: str) -> str:
        """Handle /probe request - return device information."""
        root = ET.Element("MTConnectDevices", {
            "xmlns": self.MTConnect_NS,
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"
        })

        # Header
        header = ET.SubElement(root, "Header", {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.config.sender,
            "instanceId": str(self.config.instance_id),
            "version": self.config.version,
            "bufferSize": str(self.config.buffer_size)
        })

        # Devices
        devices_elem = ET.SubElement(root, "Devices")
        for device in self._devices.values():
            device_elem = ET.SubElement(devices_elem, "Device", {
                "uuid": device.uuid,
                "name": device.name,
                "id": device.id
            })

            # Add components and data items
            self._add_device_components(device_elem, device)

        return ET.tostring(root, encoding='unicode')

    def _handle_current(self, path: str) -> str:
        """Handle /current request - return current values."""
        # Parse path for device filter
        device_filter = self._parse_path_filter(path)

        root = ET.Element("MTConnectStreams", {
            "xmlns": self.MTConnect_STREAMS_NS
        })

        # Header
        ET.SubElement(root, "Header", {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.config.sender,
            "instanceId": str(self.config.instance_id),
            "version": self.config.version,
            "bufferSize": str(self.config.buffer_size),
            "nextSequence": str(self._sequence),
            "firstSequence": str(self._first_sequence),
            "lastSequence": str(self._sequence - 1)
        })

        # Streams
        streams = ET.SubElement(root, "Streams")

        # Get current values (latest for each data item)
        current_values: Dict[str, StreamData] = {}
        for data in self._buffer:
            current_values[data.data_item_id] = data

        # Add device streams
        for device in self._devices.values():
            if device_filter and device.uuid != device_filter:
                continue

            device_stream = ET.SubElement(streams, "DeviceStream", {
                "uuid": device.uuid,
                "name": device.name
            })

            # Add component streams with samples/events
            self._add_component_streams(device_stream, device, current_values)

        return ET.tostring(root, encoding='unicode')

    def _handle_sample(self, path: str) -> str:
        """Handle /sample request - return historical samples."""
        # Parse parameters
        params = self._parse_query_params(path)
        from_seq = int(params.get("from", self._first_sequence))
        count = min(int(params.get("count", 100)), 10000)

        root = ET.Element("MTConnectStreams", {
            "xmlns": self.MTConnect_STREAMS_NS
        })

        # Header
        ET.SubElement(root, "Header", {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.config.sender,
            "instanceId": str(self.config.instance_id),
            "version": self.config.version,
            "bufferSize": str(self.config.buffer_size),
            "nextSequence": str(min(from_seq + count, self._sequence)),
            "firstSequence": str(self._first_sequence),
            "lastSequence": str(self._sequence - 1)
        })

        # Get samples in range
        samples = [
            d for d in self._buffer
            if from_seq <= d.sequence < from_seq + count
        ]

        # Streams
        streams = ET.SubElement(root, "Streams")

        for device in self._devices.values():
            device_stream = ET.SubElement(streams, "DeviceStream", {
                "uuid": device.uuid,
                "name": device.name
            })

            self._add_sample_streams(device_stream, device, samples)

        return ET.tostring(root, encoding='unicode')

    def _handle_assets(self, path: str) -> str:
        """Handle /assets request - return asset documents."""
        root = ET.Element("MTConnectAssets", {
            "xmlns": self.MTConnect_ASSETS_NS
        })

        # Header
        ET.SubElement(root, "Header", {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.config.sender,
            "instanceId": str(self.config.instance_id),
            "version": self.config.version,
            "assetCount": str(len(self._assets))
        })

        # Assets
        assets_elem = ET.SubElement(root, "Assets")
        for asset_id, asset in self._assets.items():
            asset_elem = ET.SubElement(assets_elem, asset.get("type", "Asset"), {
                "assetId": asset_id,
                "timestamp": asset.get("timestamp", ""),
                "deviceUuid": asset.get("device_uuid", "")
            })
            # Add asset content
            for key, value in asset.get("content", {}).items():
                ET.SubElement(asset_elem, key).text = str(value)

        return ET.tostring(root, encoding='unicode')

    def _error_response(self, code: str, message: str) -> str:
        """Generate error response."""
        root = ET.Element("MTConnectError", {
            "xmlns": self.MTConnect_ERROR_NS
        })

        ET.SubElement(root, "Header", {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.config.sender,
            "version": self.config.version
        })

        errors = ET.SubElement(root, "Errors")
        error = ET.SubElement(errors, "Error", {"errorCode": code})
        error.text = message

        return ET.tostring(root, encoding='unicode')

    def _add_device_components(self, device_elem: ET.Element, device: Any) -> None:
        """Add device components to XML."""
        # Simplified - in production would walk component tree
        components = ET.SubElement(device_elem, "Components")
        controller = ET.SubElement(components, "Controller", {
            "id": f"{device.id}_controller",
            "name": "Controller"
        })

        # Add data items
        data_items = ET.SubElement(controller, "DataItems")
        for item in device.data_items:
            ET.SubElement(data_items, "DataItem", {
                "id": item.id,
                "name": item.name,
                "category": item.category.value,
                "type": item.type.value
            })

    def _add_component_streams(
        self,
        device_stream: ET.Element,
        device: Any,
        current_values: Dict[str, StreamData]
    ) -> None:
        """Add component streams with current values."""
        comp_stream = ET.SubElement(device_stream, "ComponentStream", {
            "component": "Controller",
            "componentId": f"{device.id}_controller"
        })

        samples = ET.SubElement(comp_stream, "Samples")
        events = ET.SubElement(comp_stream, "Events")
        conditions = ET.SubElement(comp_stream, "Condition")

        for item in device.data_items:
            data = current_values.get(item.id)
            value = data.value if data else "UNAVAILABLE"
            timestamp = datetime.fromtimestamp(data.timestamp).isoformat() if data else datetime.utcnow().isoformat()
            seq = str(data.sequence) if data else "0"

            attrs = {
                "dataItemId": item.id,
                "name": item.name,
                "timestamp": timestamp + "Z",
                "sequence": seq
            }

            if item.category.value == "SAMPLE":
                elem = ET.SubElement(samples, item.type.value, attrs)
                elem.text = str(value)
            elif item.category.value == "EVENT":
                elem = ET.SubElement(events, item.type.value, attrs)
                elem.text = str(value)
            else:  # CONDITION
                elem = ET.SubElement(conditions, "Normal" if value == "NORMAL" else "Warning", attrs)
                if isinstance(value, dict):
                    elem.text = value.get("message", "")

    def _add_sample_streams(
        self,
        device_stream: ET.Element,
        device: Any,
        samples: List[StreamData]
    ) -> None:
        """Add sample streams for historical data."""
        comp_stream = ET.SubElement(device_stream, "ComponentStream", {
            "component": "Controller",
            "componentId": f"{device.id}_controller"
        })

        samples_elem = ET.SubElement(comp_stream, "Samples")
        events_elem = ET.SubElement(comp_stream, "Events")

        # Group by data item
        item_map = {item.id: item for item in device.data_items}

        for sample in samples:
            item = item_map.get(sample.data_item_id)
            if not item:
                continue

            attrs = {
                "dataItemId": sample.data_item_id,
                "timestamp": datetime.fromtimestamp(sample.timestamp).isoformat() + "Z",
                "sequence": str(sample.sequence)
            }

            if item.category.value == "SAMPLE":
                elem = ET.SubElement(samples_elem, item.type.value, attrs)
                elem.text = str(sample.value)
            elif item.category.value == "EVENT":
                elem = ET.SubElement(events_elem, item.type.value, attrs)
                elem.text = str(sample.value)

    def _parse_path_filter(self, path: str) -> Optional[str]:
        """Parse device filter from path."""
        parts = path.split('/')
        if len(parts) > 2:
            return parts[2]
        return None

    def _parse_query_params(self, path: str) -> Dict[str, str]:
        """Parse query parameters from path."""
        params = {}
        if '?' in path:
            query = path.split('?')[1]
            for param in query.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = value
        return params

    def add_asset(
        self,
        asset_id: str,
        asset_type: str,
        device_uuid: str,
        content: Dict[str, Any]
    ) -> None:
        """
        Add or update an asset.

        Args:
            asset_id: Unique asset ID
            asset_type: Asset type (CuttingTool, etc.)
            device_uuid: Associated device UUID
            content: Asset content
        """
        self._assets[asset_id] = {
            "type": asset_type,
            "device_uuid": device_uuid,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "content": content
        }

    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "sender": self.config.sender,
            "version": self.config.version,
            "http_port": self.config.http_port,
            "adapter_port": self.config.adapter_port,
            "device_count": len(self._devices),
            "asset_count": len(self._assets),
            "buffer_size": self.config.buffer_size,
            "sequence": self._sequence,
            "first_sequence": self._first_sequence,
            "running": self._running
        }
