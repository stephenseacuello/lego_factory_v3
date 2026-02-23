"""
OPC UA Namespace Management

Manages namespace registration and node organization
for the LEGO MCP manufacturing information model.

Reference: IEC 62541-3 (Address Space Model)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class BuiltInType(Enum):
    """OPC UA Built-in Data Types."""
    BOOLEAN = 1
    SBYTE = 2
    BYTE = 3
    INT16 = 4
    UINT16 = 5
    INT32 = 6
    UINT32 = 7
    INT64 = 8
    UINT64 = 9
    FLOAT = 10
    DOUBLE = 11
    STRING = 12
    DATETIME = 13
    GUID = 14
    BYTESTRING = 15
    XMLELEMENT = 16
    NODEID = 17
    STATUSCODE = 19
    QUALIFIEDNAME = 20
    LOCALIZEDTEXT = 21


@dataclass
class TypeDefinition:
    """Type definition for custom data types."""
    name: str
    base_type: str
    fields: List[Dict[str, Any]] = field(default_factory=list)
    is_abstract: bool = False
    description: str = ""


@dataclass
class ObjectTypeDefinition:
    """Object type definition."""
    name: str
    base_type: str = "BaseObjectType"
    variables: List[Dict[str, Any]] = field(default_factory=list)
    methods: List[Dict[str, Any]] = field(default_factory=list)
    is_abstract: bool = False
    description: str = ""


@dataclass
class VariableTypeDefinition:
    """Variable type definition."""
    name: str
    base_type: str = "BaseDataVariableType"
    data_type: str = "Double"
    value_rank: int = -1  # Scalar
    is_abstract: bool = False
    description: str = ""


class OPCUANamespace:
    """
    OPC UA Namespace Manager.

    Manages:
    - Namespace registration
    - Type definitions
    - Information model organization
    - NodeSet2 XML generation

    Usage:
        >>> ns = OPCUANamespace("urn:lego-mcp:manufacturing")
        >>> ns.add_object_type("BrickPrinter", variables=[...])
        >>> xml = ns.generate_nodeset2_xml()
    """

    # Standard OPC UA namespaces
    UA_NAMESPACE = "http://opcfoundation.org/UA/"
    UA_NAMESPACE_INDEX = 0

    def __init__(self, uri: str, index: int = 1):
        """
        Initialize namespace.

        Args:
            uri: Namespace URI
            index: Namespace index (>= 1)
        """
        self.uri = uri
        self.index = index

        # Type registrations
        self._data_types: Dict[str, TypeDefinition] = {}
        self._object_types: Dict[str, ObjectTypeDefinition] = {}
        self._variable_types: Dict[str, VariableTypeDefinition] = {}

        # Node tracking
        self._node_counter = 1000
        self._nodes: Dict[str, Dict[str, Any]] = {}

        # Dependencies
        self._dependencies: Set[str] = set()

        logger.info(f"Namespace initialized: {uri} (index={index})")

    def add_data_type(
        self,
        name: str,
        base_type: str = "Structure",
        fields: Optional[List[Dict[str, Any]]] = None,
        is_abstract: bool = False,
        description: str = ""
    ) -> str:
        """
        Add a custom data type.

        Args:
            name: Type name
            base_type: Base type name
            fields: List of field definitions
            is_abstract: Is abstract type
            description: Type description

        Returns:
            Node ID string
        """
        type_def = TypeDefinition(
            name=name,
            base_type=base_type,
            fields=fields or [],
            is_abstract=is_abstract,
            description=description
        )

        self._data_types[name] = type_def
        node_id = self._allocate_node_id()
        self._nodes[name] = {
            "node_id": node_id,
            "type": "DataType",
            "definition": type_def
        }

        logger.debug(f"Added data type: {name}")
        return node_id

    def add_object_type(
        self,
        name: str,
        base_type: str = "BaseObjectType",
        variables: Optional[List[Dict[str, Any]]] = None,
        methods: Optional[List[Dict[str, Any]]] = None,
        is_abstract: bool = False,
        description: str = ""
    ) -> str:
        """
        Add an object type.

        Args:
            name: Type name
            base_type: Base type name
            variables: Variable definitions
            methods: Method definitions
            is_abstract: Is abstract type
            description: Type description

        Returns:
            Node ID string
        """
        type_def = ObjectTypeDefinition(
            name=name,
            base_type=base_type,
            variables=variables or [],
            methods=methods or [],
            is_abstract=is_abstract,
            description=description
        )

        self._object_types[name] = type_def
        node_id = self._allocate_node_id()
        self._nodes[name] = {
            "node_id": node_id,
            "type": "ObjectType",
            "definition": type_def
        }

        logger.debug(f"Added object type: {name}")
        return node_id

    def add_variable_type(
        self,
        name: str,
        base_type: str = "BaseDataVariableType",
        data_type: str = "Double",
        value_rank: int = -1,
        is_abstract: bool = False,
        description: str = ""
    ) -> str:
        """
        Add a variable type.

        Args:
            name: Type name
            base_type: Base type name
            data_type: Data type name
            value_rank: Value rank (-1 = scalar)
            is_abstract: Is abstract type
            description: Type description

        Returns:
            Node ID string
        """
        type_def = VariableTypeDefinition(
            name=name,
            base_type=base_type,
            data_type=data_type,
            value_rank=value_rank,
            is_abstract=is_abstract,
            description=description
        )

        self._variable_types[name] = type_def
        node_id = self._allocate_node_id()
        self._nodes[name] = {
            "node_id": node_id,
            "type": "VariableType",
            "definition": type_def
        }

        logger.debug(f"Added variable type: {name}")
        return node_id

    def add_dependency(self, namespace_uri: str) -> None:
        """
        Add a namespace dependency.

        Args:
            namespace_uri: Dependent namespace URI
        """
        self._dependencies.add(namespace_uri)

    def _allocate_node_id(self) -> str:
        """Allocate a new node ID."""
        node_id = f"ns={self.index};i={self._node_counter}"
        self._node_counter += 1
        return node_id

    def get_node_id(self, name: str) -> Optional[str]:
        """Get node ID by name."""
        node = self._nodes.get(name)
        return node["node_id"] if node else None

    def generate_nodeset2_xml(self) -> str:
        """
        Generate OPC UA NodeSet2 XML.

        Returns:
            XML string
        """
        xml_parts = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<UANodeSet xmlns="http://opcfoundation.org/UA/2011/03/UANodeSet.xsd"',
            '           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '           xmlns:xsd="http://www.w3.org/2001/XMLSchema">',
            '',
            '  <NamespaceUris>',
            f'    <Uri>{self.uri}</Uri>',
        ]

        for dep in sorted(self._dependencies):
            xml_parts.append(f'    <Uri>{dep}</Uri>')

        xml_parts.extend([
            '  </NamespaceUris>',
            '',
            '  <Aliases>',
            '    <Alias Alias="Boolean">i=1</Alias>',
            '    <Alias Alias="Int32">i=6</Alias>',
            '    <Alias Alias="UInt32">i=7</Alias>',
            '    <Alias Alias="Double">i=11</Alias>',
            '    <Alias Alias="String">i=12</Alias>',
            '    <Alias Alias="DateTime">i=13</Alias>',
            '    <Alias Alias="HasComponent">i=47</Alias>',
            '    <Alias Alias="HasProperty">i=46</Alias>',
            '    <Alias Alias="HasSubtype">i=45</Alias>',
            '    <Alias Alias="Organizes">i=35</Alias>',
            '  </Aliases>',
            '',
        ])

        # Generate DataType nodes
        for name, node_info in self._nodes.items():
            if node_info["type"] == "DataType":
                xml_parts.append(self._generate_data_type_xml(name, node_info))

        # Generate ObjectType nodes
        for name, node_info in self._nodes.items():
            if node_info["type"] == "ObjectType":
                xml_parts.append(self._generate_object_type_xml(name, node_info))

        # Generate VariableType nodes
        for name, node_info in self._nodes.items():
            if node_info["type"] == "VariableType":
                xml_parts.append(self._generate_variable_type_xml(name, node_info))

        xml_parts.append('</UANodeSet>')
        return '\n'.join(xml_parts)

    def _generate_data_type_xml(self, name: str, node_info: Dict) -> str:
        """Generate XML for a data type."""
        type_def = node_info["definition"]
        node_id = node_info["node_id"]

        lines = [
            f'  <UADataType NodeId="{node_id}" BrowseName="{self.index}:{name}">',
            f'    <DisplayName>{name}</DisplayName>',
        ]

        if type_def.description:
            lines.append(f'    <Description>{type_def.description}</Description>')

        # Add references
        lines.append('    <References>')
        lines.append(f'      <Reference ReferenceType="HasSubtype" IsForward="false">i=22</Reference>')
        lines.append('    </References>')

        # Add fields if structure
        if type_def.fields:
            lines.append('    <Definition Name="' + name + '">')
            for field in type_def.fields:
                lines.append(f'      <Field Name="{field["name"]}" DataType="{field.get("data_type", "String")}"/>')
            lines.append('    </Definition>')

        lines.append('  </UADataType>')
        return '\n'.join(lines)

    def _generate_object_type_xml(self, name: str, node_info: Dict) -> str:
        """Generate XML for an object type."""
        type_def = node_info["definition"]
        node_id = node_info["node_id"]

        is_abstract = 'true' if type_def.is_abstract else 'false'
        lines = [
            f'  <UAObjectType NodeId="{node_id}" BrowseName="{self.index}:{name}" IsAbstract="{is_abstract}">',
            f'    <DisplayName>{name}</DisplayName>',
        ]

        if type_def.description:
            lines.append(f'    <Description>{type_def.description}</Description>')

        lines.append('    <References>')
        lines.append('      <Reference ReferenceType="HasSubtype" IsForward="false">i=58</Reference>')
        lines.append('    </References>')

        lines.append('  </UAObjectType>')
        return '\n'.join(lines)

    def _generate_variable_type_xml(self, name: str, node_info: Dict) -> str:
        """Generate XML for a variable type."""
        type_def = node_info["definition"]
        node_id = node_info["node_id"]

        is_abstract = 'true' if type_def.is_abstract else 'false'
        lines = [
            f'  <UAVariableType NodeId="{node_id}" BrowseName="{self.index}:{name}" '
            f'DataType="{type_def.data_type}" ValueRank="{type_def.value_rank}" IsAbstract="{is_abstract}">',
            f'    <DisplayName>{name}</DisplayName>',
        ]

        if type_def.description:
            lines.append(f'    <Description>{type_def.description}</Description>')

        lines.append('    <References>')
        lines.append('      <Reference ReferenceType="HasSubtype" IsForward="false">i=63</Reference>')
        lines.append('    </References>')

        lines.append('  </UAVariableType>')
        return '\n'.join(lines)

    def get_info(self) -> Dict[str, Any]:
        """Get namespace information."""
        return {
            "uri": self.uri,
            "index": self.index,
            "data_type_count": len(self._data_types),
            "object_type_count": len(self._object_types),
            "variable_type_count": len(self._variable_types),
            "total_nodes": len(self._nodes),
            "dependencies": list(self._dependencies)
        }
