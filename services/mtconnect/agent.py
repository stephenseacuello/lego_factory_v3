"""
MTConnect Agent for Flask CNC SCADA
====================================
Provides MTConnect-compliant HTTP REST API for device data.

The Agent exposes three standard MTConnect endpoints:
- /probe: Device metadata and data item definitions
- /current: Current values of all data items
- /sample: Historical sample stream with sequence numbers

Reference: MTConnect Standard v2.0 - Agent Interface
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from xml.etree import ElementTree as ET

from .adapter import MTConnectAdapter, get_mtconnect_adapter, DataItemObservation
from .data_items import (
    MTConnectDevice,
    MTConnectDataItem,
    DataItemCategory,
)

logger = logging.getLogger(__name__)

# MTConnect XML namespaces
MTCONNECT_NS = "urn:mtconnect.org:MTConnectDevices:2.0"
MTCONNECT_STREAMS_NS = "urn:mtconnect.org:MTConnectStreams:2.0"
MTCONNECT_ERROR_NS = "urn:mtconnect.org:MTConnectError:2.0"

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


class MTConnectAgent:
    """
    MTConnect Agent implementation.

    Provides standard MTConnect REST API responses in XML format.
    Works with MTConnectAdapter for data translation.
    """

    def __init__(self, adapter: MTConnectAdapter = None):
        """
        Initialize MTConnect Agent.

        Args:
            adapter: MTConnectAdapter instance (uses singleton if not provided)
        """
        self.adapter = adapter or get_mtconnect_adapter()
        self.sender = "FlaskCNC-Agent"
        self.version = "2.0.0"
        logger.info("MTConnect Agent initialized")

    # =========================================================================
    # Probe Response (Device Metadata)
    # =========================================================================

    def probe(self) -> str:
        """
        Generate MTConnect Probe response (device metadata).

        Returns:
            XML string with device structure and data item definitions
        """
        root = self._create_devices_header()

        # Add Devices element
        devices = ET.SubElement(root, "Devices")
        self._add_device_xml(devices, self.adapter.device)

        return self._to_xml_string(root)

    def probe_json(self) -> Dict[str, Any]:
        """
        Generate MTConnect Probe response as JSON (non-standard but useful).

        Returns:
            Dict with device structure and data item definitions
        """
        device = self.adapter.device
        return {
            "MTConnectDevices": {
                "Header": self._create_header_dict("probe"),
                "Devices": [self._device_to_dict(device)]
            }
        }

    def _add_device_xml(self, parent: ET.Element, device: MTConnectDevice):
        """Add device XML structure recursively."""
        device_elem = ET.SubElement(parent, "Device", {
            "id": device.id,
            "name": device.name,
            "uuid": device.uuid,
        })

        if device.description:
            desc = ET.SubElement(device_elem, "Description")
            desc.text = device.description

        # Add components
        if device.components:
            components_elem = ET.SubElement(device_elem, "Components")
            for component in device.components:
                self._add_component_xml(components_elem, component)

    def _add_component_xml(self, parent: ET.Element, component):
        """Add component XML structure recursively."""
        comp_elem = ET.SubElement(parent, component.type, {
            "id": component.id,
            "name": component.name,
        })

        # Add data items
        if component.data_items:
            data_items_elem = ET.SubElement(comp_elem, "DataItems")
            for item in component.data_items:
                self._add_data_item_xml(data_items_elem, item)

        # Add nested components
        if hasattr(component, 'components') and component.components:
            nested_comps = ET.SubElement(comp_elem, "Components")
            for nested in component.components:
                self._add_component_xml(nested_comps, nested)

    def _add_data_item_xml(self, parent: ET.Element, item: MTConnectDataItem):
        """Add data item XML element."""
        attrs = {
            "id": item.id,
            "name": item.name,
            "category": item.category.value,
            "type": item.type,
        }
        if item.units:
            attrs["units"] = item.units
        if item.sub_type:
            attrs["subType"] = item.sub_type

        ET.SubElement(parent, "DataItem", attrs)

    # =========================================================================
    # Current Response (Latest Values)
    # =========================================================================

    def current(self, path: str = None, at: int = None) -> str:
        """
        Generate MTConnect Current response.

        Args:
            path: Filter by data item path (optional)
            at: Sequence number to retrieve values at (optional)

        Returns:
            XML string with current data item values
        """
        root = self._create_streams_header()

        # Add Streams element
        streams = ET.SubElement(root, "Streams")
        device_stream = ET.SubElement(streams, "DeviceStream", {
            "name": self.adapter.device.name,
            "uuid": self.adapter.device.uuid,
        })

        # Group data items by component
        data_items = self.adapter.get_current_values()
        self._add_component_streams(device_stream, data_items, path)

        return self._to_xml_string(root)

    def current_json(self, path: str = None) -> Dict[str, Any]:
        """
        Generate MTConnect Current response as JSON.

        Args:
            path: Filter by data item path (optional)

        Returns:
            Dict with current data item values
        """
        data_items = self.adapter.get_current_values()

        # Filter by path if specified
        if path:
            data_items = {k: v for k, v in data_items.items() if k.startswith(path)}

        items_list = []
        for item_id, item in data_items.items():
            items_list.append({
                "dataItemId": item.id,
                "name": item.name,
                "category": item.category.value,
                "type": item.type,
                "value": item.value,
                "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                "sequence": item.sequence,
            })

        return {
            "MTConnectStreams": {
                "Header": self._create_header_dict("current"),
                "Streams": {
                    "DeviceStream": {
                        "name": self.adapter.device.name,
                        "uuid": self.adapter.device.uuid,
                        "DataItems": items_list
                    }
                }
            }
        }

    def _add_component_streams(
        self,
        parent: ET.Element,
        data_items: Dict[str, MTConnectDataItem],
        path: str = None
    ):
        """Add component stream elements with data item values."""
        # Group by category
        samples = []
        events = []
        conditions = []

        for item_id, item in data_items.items():
            if path and not item_id.startswith(path):
                continue

            if item.category == DataItemCategory.SAMPLE:
                samples.append(item)
            elif item.category == DataItemCategory.EVENT:
                events.append(item)
            elif item.category == DataItemCategory.CONDITION:
                conditions.append(item)

        # Add ComponentStream
        comp_stream = ET.SubElement(parent, "ComponentStream", {
            "component": "Device",
            "componentId": self.adapter.device_id,
        })

        # Add Samples
        if samples:
            samples_elem = ET.SubElement(comp_stream, "Samples")
            for item in samples:
                self._add_data_item_value(samples_elem, item)

        # Add Events
        if events:
            events_elem = ET.SubElement(comp_stream, "Events")
            for item in events:
                self._add_data_item_value(events_elem, item)

        # Add Conditions
        if conditions:
            conditions_elem = ET.SubElement(comp_stream, "Condition")
            for item in conditions:
                self._add_condition_value(conditions_elem, item)

    def _add_data_item_value(self, parent: ET.Element, item: MTConnectDataItem):
        """Add data item value element."""
        attrs = {
            "dataItemId": item.id,
            "timestamp": item.timestamp.isoformat() if item.timestamp else "",
            "sequence": str(item.sequence),
        }
        if item.name:
            attrs["name"] = item.name

        elem = ET.SubElement(parent, item.type, attrs)
        elem.text = str(item.value) if item.value is not None else "UNAVAILABLE"

    def _add_condition_value(self, parent: ET.Element, item: MTConnectDataItem):
        """Add condition value element."""
        # Conditions have special structure: Normal, Warning, Fault, Unavailable
        value = item.value or "UNAVAILABLE"
        condition_type = "Normal"

        if value == "UNAVAILABLE":
            condition_type = "Unavailable"
        elif value in ("WARNING", "CAUTION"):
            condition_type = "Warning"
        elif value in ("FAULT", "ALARM", "ERROR"):
            condition_type = "Fault"

        attrs = {
            "dataItemId": item.id,
            "timestamp": item.timestamp.isoformat() if item.timestamp else "",
            "sequence": str(item.sequence),
            "type": item.type,
        }

        elem = ET.SubElement(parent, condition_type, attrs)
        if condition_type not in ("Normal", "Unavailable"):
            elem.text = str(value)

    # =========================================================================
    # Sample Response (Historical Data)
    # =========================================================================

    def sample(
        self,
        from_seq: int = None,
        count: int = 100,
        path: str = None
    ) -> str:
        """
        Generate MTConnect Sample response.

        Args:
            from_seq: Starting sequence number
            count: Maximum samples to return
            path: Filter by data item path (optional)

        Returns:
            XML string with historical samples
        """
        if from_seq is None:
            from_seq = self.adapter.get_first_sequence()

        observations = self.adapter.get_samples(from_seq, count, path)

        root = self._create_streams_header(from_seq, len(observations))

        # Add Streams element
        streams = ET.SubElement(root, "Streams")
        device_stream = ET.SubElement(streams, "DeviceStream", {
            "name": self.adapter.device.name,
            "uuid": self.adapter.device.uuid,
        })

        self._add_observation_streams(device_stream, observations)

        return self._to_xml_string(root)

    def sample_json(
        self,
        from_seq: int = None,
        count: int = 100,
        path: str = None
    ) -> Dict[str, Any]:
        """
        Generate MTConnect Sample response as JSON.

        Args:
            from_seq: Starting sequence number
            count: Maximum samples to return
            path: Filter by data item path (optional)

        Returns:
            Dict with historical samples
        """
        if from_seq is None:
            from_seq = self.adapter.get_first_sequence()

        observations = self.adapter.get_samples(from_seq, count, path)

        samples_list = []
        for obs in observations:
            samples_list.append({
                "dataItemId": obs.data_item_id,
                "value": obs.value,
                "timestamp": obs.timestamp.isoformat(),
                "sequence": obs.sequence,
            })

        return {
            "MTConnectStreams": {
                "Header": self._create_header_dict("sample", from_seq, len(observations)),
                "Streams": {
                    "DeviceStream": {
                        "name": self.adapter.device.name,
                        "uuid": self.adapter.device.uuid,
                        "Samples": samples_list
                    }
                }
            }
        }

    def _add_observation_streams(
        self,
        parent: ET.Element,
        observations: List[DataItemObservation]
    ):
        """Add observation elements to stream."""
        comp_stream = ET.SubElement(parent, "ComponentStream", {
            "component": "Device",
            "componentId": self.adapter.device_id,
        })

        # Group by category
        samples_elem = ET.SubElement(comp_stream, "Samples")
        events_elem = ET.SubElement(comp_stream, "Events")

        data_items = self.adapter.get_current_values()

        for obs in observations:
            item = data_items.get(obs.data_item_id)
            if not item:
                continue

            attrs = {
                "dataItemId": obs.data_item_id,
                "timestamp": obs.timestamp.isoformat(),
                "sequence": str(obs.sequence),
            }

            if item.category == DataItemCategory.SAMPLE:
                elem = ET.SubElement(samples_elem, item.type, attrs)
            else:
                elem = ET.SubElement(events_elem, item.type, attrs)

            elem.text = str(obs.value) if obs.value is not None else "UNAVAILABLE"

    # =========================================================================
    # Error Response
    # =========================================================================

    def error(self, error_code: str, error_text: str) -> str:
        """
        Generate MTConnect Error response.

        Args:
            error_code: MTConnect error code
            error_text: Human-readable error description

        Returns:
            XML string with error
        """
        root = ET.Element("MTConnectError", {
            "xmlns": MTCONNECT_ERROR_NS,
            "xmlns:xsi": XSI_NS,
        })

        header = ET.SubElement(root, "Header", {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.sender,
            "version": self.version,
        })

        errors = ET.SubElement(root, "Errors")
        error = ET.SubElement(errors, "Error", {"errorCode": error_code})
        error.text = error_text

        return self._to_xml_string(root)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _create_devices_header(self) -> ET.Element:
        """Create MTConnectDevices root element with header."""
        root = ET.Element("MTConnectDevices", {
            "xmlns": MTCONNECT_NS,
            "xmlns:xsi": XSI_NS,
        })

        ET.SubElement(root, "Header", {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.sender,
            "instanceId": str(self.adapter.instance_id),
            "version": self.version,
            "bufferSize": str(self.adapter.buffer_size),
            "assetBufferSize": "1024",
            "assetCount": "0",
        })

        return root

    def _create_streams_header(
        self,
        first_sequence: int = None,
        count: int = None
    ) -> ET.Element:
        """Create MTConnectStreams root element with header."""
        root = ET.Element("MTConnectStreams", {
            "xmlns": MTCONNECT_STREAMS_NS,
            "xmlns:xsi": XSI_NS,
        })

        attrs = {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.sender,
            "instanceId": str(self.adapter.instance_id),
            "version": self.version,
            "bufferSize": str(self.adapter.buffer_size),
            "nextSequence": str(self.adapter.get_current_sequence() + 1),
            "firstSequence": str(first_sequence or self.adapter.get_first_sequence()),
            "lastSequence": str(self.adapter.get_current_sequence()),
        }

        ET.SubElement(root, "Header", attrs)

        return root

    def _create_header_dict(
        self,
        request_type: str,
        first_sequence: int = None,
        count: int = None
    ) -> Dict[str, Any]:
        """Create header dict for JSON responses."""
        header = {
            "creationTime": datetime.utcnow().isoformat() + "Z",
            "sender": self.sender,
            "instanceId": self.adapter.instance_id,
            "version": self.version,
            "bufferSize": self.adapter.buffer_size,
        }

        if request_type in ("current", "sample"):
            header["nextSequence"] = self.adapter.get_current_sequence() + 1
            header["firstSequence"] = first_sequence or self.adapter.get_first_sequence()
            header["lastSequence"] = self.adapter.get_current_sequence()

        return header

    def _device_to_dict(self, device: MTConnectDevice) -> Dict[str, Any]:
        """Convert device to dictionary."""
        result = {
            "id": device.id,
            "name": device.name,
            "uuid": device.uuid,
            "description": device.description,
            "Components": []
        }

        for component in device.components:
            result["Components"].append(self._component_to_dict(component))

        return result

    def _component_to_dict(self, component) -> Dict[str, Any]:
        """Convert component to dictionary."""
        result = {
            "type": component.type,
            "id": component.id,
            "name": component.name,
            "DataItems": []
        }

        for item in component.data_items:
            result["DataItems"].append({
                "id": item.id,
                "name": item.name,
                "category": item.category.value,
                "type": item.type,
                "units": item.units,
                "subType": item.sub_type,
            })

        if hasattr(component, 'components') and component.components:
            result["Components"] = []
            for nested in component.components:
                result["Components"].append(self._component_to_dict(nested))

        return result

    def _to_xml_string(self, root: ET.Element) -> str:
        """Convert ElementTree to XML string."""
        return ET.tostring(root, encoding="unicode", method="xml")


# =============================================================================
# Singleton Instance
# =============================================================================

_agent: Optional[MTConnectAgent] = None


def get_mtconnect_agent() -> MTConnectAgent:
    """Get or create the MTConnect agent singleton."""
    global _agent
    if _agent is None:
        _agent = MTConnectAgent()
    return _agent


def init_mtconnect_agent(adapter: MTConnectAdapter = None) -> MTConnectAgent:
    """Initialize the MTConnect agent with custom adapter."""
    global _agent
    _agent = MTConnectAgent(adapter)
    return _agent
