"""
B2MML (Business to Manufacturing Markup Language) Generator

Generates B2MML v7.0 compliant XML messages for
enterprise-manufacturing integration.

Reference: B2MML v7.0, IEC 62264
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from xml.dom import minidom

logger = logging.getLogger(__name__)


@dataclass
class B2MMLConfig:
    """B2MML Generator Configuration."""
    namespace: str = "http://www.mesa.org/xml/B2MML"
    schema_location: str = "B2MML-V0700.xsd"
    include_schema_location: bool = True
    pretty_print: bool = True


class B2MMLGenerator:
    """
    B2MML XML Message Generator.

    Generates B2MML v7.0 compliant XML for:
    - Operations Schedule
    - Operations Request
    - Operations Performance
    - Material Information
    - Equipment Information
    - Personnel Information

    Usage:
        >>> generator = B2MMLGenerator()
        >>> xml = generator.generate_operations_schedule(schedule_data)
        >>> generator.save_to_file(xml, "schedule.xml")
    """

    # B2MML namespaces
    B2MML_NS = "http://www.mesa.org/xml/B2MML"
    XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

    def __init__(self, config: Optional[B2MMLConfig] = None):
        """
        Initialize B2MML Generator.

        Args:
            config: Generator configuration
        """
        self.config = config or B2MMLConfig()

        # Register namespaces
        ET.register_namespace("", self.B2MML_NS)
        ET.register_namespace("xsi", self.XSI_NS)

        logger.info("B2MMLGenerator initialized")

    def generate_operations_schedule(
        self,
        schedule_id: str,
        operations: List[Dict[str, Any]],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None
    ) -> str:
        """
        Generate B2MML Operations Schedule.

        Args:
            schedule_id: Unique schedule identifier
            operations: List of operation requests
            start_time: Schedule start time
            end_time: Schedule end time
            description: Schedule description

        Returns:
            B2MML XML string
        """
        root = self._create_root("OperationsSchedule")

        # Header elements
        self._add_element(root, "ID", schedule_id)
        self._add_element(root, "Description", description or f"Operations Schedule {schedule_id}")
        self._add_element(root, "Version", "1.0")
        self._add_element(root, "PublishedDate", datetime.utcnow().isoformat() + "Z")
        self._add_element(root, "OperationsType", "Production")

        if start_time:
            self._add_element(root, "StartTime", start_time.isoformat() + "Z")
        if end_time:
            self._add_element(root, "EndTime", end_time.isoformat() + "Z")

        # Operations Requests
        for op in operations:
            self._add_operations_request(root, op)

        return self._to_string(root)

    def generate_operations_request(
        self,
        request_id: str,
        segment_requirements: List[Dict[str, Any]],
        priority: int = 3,
        requested_start: Optional[datetime] = None,
        requested_end: Optional[datetime] = None
    ) -> str:
        """
        Generate B2MML Operations Request.

        Args:
            request_id: Request identifier
            segment_requirements: List of segment requirements
            priority: Request priority
            requested_start: Requested start time
            requested_end: Requested end time

        Returns:
            B2MML XML string
        """
        root = self._create_root("OperationsRequest")

        self._add_element(root, "ID", request_id)
        self._add_element(root, "Version", "1.0")
        self._add_element(root, "PublishedDate", datetime.utcnow().isoformat() + "Z")
        self._add_element(root, "OperationsType", "Production")

        if requested_start:
            self._add_element(root, "RequestedStartTime", requested_start.isoformat() + "Z")
        if requested_end:
            self._add_element(root, "RequestedEndTime", requested_end.isoformat() + "Z")

        self._add_element(root, "Priority", str(priority))
        self._add_element(root, "RequestState", "Waiting")

        # Segment Requirements
        for seg in segment_requirements:
            self._add_segment_requirement(root, seg)

        return self._to_string(root)

    def generate_operations_performance(
        self,
        performance_id: str,
        request_id: str,
        segment_responses: List[Dict[str, Any]],
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> str:
        """
        Generate B2MML Operations Performance.

        Args:
            performance_id: Performance record identifier
            request_id: Related request identifier
            segment_responses: List of segment responses
            start_time: Actual start time
            end_time: Actual end time

        Returns:
            B2MML XML string
        """
        root = self._create_root("OperationsPerformance")

        self._add_element(root, "ID", performance_id)
        self._add_element(root, "Version", "1.0")
        self._add_element(root, "PublishedDate", datetime.utcnow().isoformat() + "Z")
        self._add_element(root, "OperationsType", "Production")
        self._add_element(root, "OperationsRequestID", request_id)

        # Operations Response
        ops_response = ET.SubElement(root, "OperationsResponse")
        self._add_element(ops_response, "ID", f"{performance_id}_response")
        self._add_element(ops_response, "ActualStartTime", start_time.isoformat() + "Z")
        if end_time:
            self._add_element(ops_response, "ActualEndTime", end_time.isoformat() + "Z")
        self._add_element(ops_response, "ResponseState", "Completed")

        for seg in segment_responses:
            self._add_segment_response(ops_response, seg)

        return self._to_string(root)

    def generate_material_information(
        self,
        materials: List[Dict[str, Any]]
    ) -> str:
        """
        Generate B2MML Material Information.

        Args:
            materials: List of material definitions

        Returns:
            B2MML XML string
        """
        root = self._create_root("MaterialInformation")

        for mat in materials:
            mat_def = ET.SubElement(root, "MaterialDefinition")
            self._add_element(mat_def, "ID", mat.get("id", ""))
            self._add_element(mat_def, "Description", mat.get("description", ""))

            if mat.get("material_class_id"):
                self._add_element(mat_def, "MaterialClassID", mat["material_class_id"])

            for prop in mat.get("properties", []):
                prop_elem = ET.SubElement(mat_def, "MaterialDefinitionProperty")
                self._add_element(prop_elem, "ID", prop.get("id", ""))
                value_elem = ET.SubElement(prop_elem, "Value")
                self._add_element(value_elem, "ValueString", str(prop.get("value", "")))
                if prop.get("unit_of_measure"):
                    self._add_element(value_elem, "UnitOfMeasure", prop["unit_of_measure"])

        return self._to_string(root)

    def generate_equipment_information(
        self,
        equipment: List[Dict[str, Any]]
    ) -> str:
        """
        Generate B2MML Equipment Information.

        Args:
            equipment: List of equipment definitions

        Returns:
            B2MML XML string
        """
        root = self._create_root("EquipmentInformation")

        for eq in equipment:
            eq_elem = ET.SubElement(root, "Equipment")
            self._add_element(eq_elem, "ID", eq.get("id", ""))
            self._add_element(eq_elem, "Description", eq.get("description", ""))

            if eq.get("equipment_level"):
                self._add_element(eq_elem, "EquipmentLevel", eq["equipment_level"])

            for prop in eq.get("properties", []):
                prop_elem = ET.SubElement(eq_elem, "EquipmentProperty")
                self._add_element(prop_elem, "ID", prop.get("id", ""))
                value_elem = ET.SubElement(prop_elem, "Value")
                self._add_element(value_elem, "ValueString", str(prop.get("value", "")))

            for cap in eq.get("capabilities", []):
                cap_elem = ET.SubElement(eq_elem, "EquipmentCapability")
                self._add_element(cap_elem, "CapabilityType", cap.get("type", ""))
                self._add_element(cap_elem, "Reason", cap.get("reason", ""))

        return self._to_string(root)

    def generate_production_performance(
        self,
        performance_id: str,
        work_responses: List[Dict[str, Any]]
    ) -> str:
        """
        Generate B2MML Production Performance.

        Args:
            performance_id: Performance identifier
            work_responses: List of work responses

        Returns:
            B2MML XML string
        """
        root = self._create_root("ProductionPerformance")

        self._add_element(root, "ID", performance_id)
        self._add_element(root, "PublishedDate", datetime.utcnow().isoformat() + "Z")

        for wr in work_responses:
            wr_elem = ET.SubElement(root, "ProductionResponse")
            self._add_element(wr_elem, "ID", wr.get("id", ""))
            self._add_element(wr_elem, "ProductionRequestID", wr.get("request_id", ""))

            # Segment responses
            for seg in wr.get("segments", []):
                seg_elem = ET.SubElement(wr_elem, "SegmentResponse")
                self._add_element(seg_elem, "ID", seg.get("id", ""))
                self._add_element(seg_elem, "ProductSegmentID", seg.get("segment_id", ""))

                # Production data
                for data in seg.get("production_data", []):
                    data_elem = ET.SubElement(seg_elem, "ProductionData")
                    self._add_element(data_elem, "ID", data.get("id", ""))
                    value_elem = ET.SubElement(data_elem, "Value")
                    self._add_element(value_elem, "ValueString", str(data.get("value", "")))
                    if data.get("unit"):
                        self._add_element(value_elem, "UnitOfMeasure", data["unit"])

        return self._to_string(root)

    def _create_root(self, element_name: str) -> ET.Element:
        """Create root element with namespaces."""
        attribs = {
            "xmlns": self.B2MML_NS,
            "{%s}xmlns" % self.XSI_NS: "xsi"
        }

        if self.config.include_schema_location:
            attribs["{%s}schemaLocation" % self.XSI_NS] = \
                f"{self.B2MML_NS} {self.config.schema_location}"

        return ET.Element(element_name, attribs)

    def _add_element(
        self,
        parent: ET.Element,
        name: str,
        value: Optional[str]
    ) -> Optional[ET.Element]:
        """Add a child element if value is not None."""
        if value is not None:
            elem = ET.SubElement(parent, name)
            elem.text = str(value)
            return elem
        return None

    def _add_operations_request(
        self,
        parent: ET.Element,
        request: Dict[str, Any]
    ) -> ET.Element:
        """Add Operations Request to parent."""
        req_elem = ET.SubElement(parent, "OperationsRequest")

        self._add_element(req_elem, "ID", request.get("id"))
        self._add_element(req_elem, "Description", request.get("description"))
        self._add_element(req_elem, "Priority", str(request.get("priority", 3)))

        if request.get("requested_start"):
            self._add_element(req_elem, "RequestedStartTime",
                            request["requested_start"].isoformat() + "Z"
                            if isinstance(request["requested_start"], datetime)
                            else request["requested_start"])

        for seg in request.get("segment_requirements", []):
            self._add_segment_requirement(req_elem, seg)

        return req_elem

    def _add_segment_requirement(
        self,
        parent: ET.Element,
        segment: Dict[str, Any]
    ) -> ET.Element:
        """Add Segment Requirement to parent."""
        seg_elem = ET.SubElement(parent, "SegmentRequirement")

        self._add_element(seg_elem, "ID", segment.get("id"))
        self._add_element(seg_elem, "ProcessSegmentID", segment.get("process_segment_id"))
        self._add_element(seg_elem, "Description", segment.get("description"))

        # Material requirements
        for mat in segment.get("material_requirements", []):
            mat_elem = ET.SubElement(seg_elem, "MaterialRequirement")
            self._add_element(mat_elem, "MaterialDefinitionID", mat.get("material_id"))
            self._add_element(mat_elem, "MaterialUse", mat.get("use", "Consumed"))

            if mat.get("quantity"):
                qty_elem = ET.SubElement(mat_elem, "Quantity")
                self._add_element(qty_elem, "QuantityString", str(mat["quantity"]))
                if mat.get("unit"):
                    self._add_element(qty_elem, "UnitOfMeasure", mat["unit"])

        # Equipment requirements
        for eq in segment.get("equipment_requirements", []):
            eq_elem = ET.SubElement(seg_elem, "EquipmentRequirement")
            self._add_element(eq_elem, "EquipmentID", eq.get("equipment_id"))
            self._add_element(eq_elem, "EquipmentUse", eq.get("use", "Primary"))

        # Parameters
        for param in segment.get("parameters", []):
            param_elem = ET.SubElement(seg_elem, "SegmentParameter")
            self._add_element(param_elem, "ID", param.get("id"))
            value_elem = ET.SubElement(param_elem, "Value")
            self._add_element(value_elem, "ValueString", str(param.get("value")))

        return seg_elem

    def _add_segment_response(
        self,
        parent: ET.Element,
        segment: Dict[str, Any]
    ) -> ET.Element:
        """Add Segment Response to parent."""
        seg_elem = ET.SubElement(parent, "SegmentResponse")

        self._add_element(seg_elem, "ID", segment.get("id"))
        self._add_element(seg_elem, "ProcessSegmentID", segment.get("process_segment_id"))

        # Actual start/end
        if segment.get("actual_start"):
            self._add_element(seg_elem, "ActualStartTime",
                            segment["actual_start"].isoformat() + "Z"
                            if isinstance(segment["actual_start"], datetime)
                            else segment["actual_start"])
        if segment.get("actual_end"):
            self._add_element(seg_elem, "ActualEndTime",
                            segment["actual_end"].isoformat() + "Z"
                            if isinstance(segment["actual_end"], datetime)
                            else segment["actual_end"])

        # Material actuals
        for mat in segment.get("material_actuals", []):
            mat_elem = ET.SubElement(seg_elem, "MaterialActual")
            self._add_element(mat_elem, "MaterialDefinitionID", mat.get("material_id"))
            self._add_element(mat_elem, "MaterialUse", mat.get("use", "Consumed"))

            if mat.get("quantity"):
                qty_elem = ET.SubElement(mat_elem, "Quantity")
                self._add_element(qty_elem, "QuantityString", str(mat["quantity"]))
                if mat.get("unit"):
                    self._add_element(qty_elem, "UnitOfMeasure", mat["unit"])

        # Segment data
        for data in segment.get("segment_data", []):
            data_elem = ET.SubElement(seg_elem, "SegmentData")
            self._add_element(data_elem, "ID", data.get("id"))
            value_elem = ET.SubElement(data_elem, "Value")
            self._add_element(value_elem, "ValueString", str(data.get("value")))

        return seg_elem

    def _to_string(self, root: ET.Element) -> str:
        """Convert element to string."""
        rough_string = ET.tostring(root, encoding='unicode')

        if self.config.pretty_print:
            reparsed = minidom.parseString(rough_string)
            return reparsed.toprettyxml(indent="  ")

        return rough_string

    def save_to_file(self, xml_string: str, filename: str) -> None:
        """Save XML to file."""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(xml_string)
        logger.info(f"Saved B2MML to {filename}")

    def parse_from_file(self, filename: str) -> ET.Element:
        """Parse B2MML from file."""
        tree = ET.parse(filename)
        return tree.getroot()

    def parse_from_string(self, xml_string: str) -> ET.Element:
        """Parse B2MML from string."""
        return ET.fromstring(xml_string)
