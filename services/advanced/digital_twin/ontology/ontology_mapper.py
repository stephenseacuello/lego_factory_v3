"""
Ontology Mapper - RDF/SPARQL Integration for Manufacturing Digital Twins.

This module provides semantic data mapping and querying capabilities:
- RDF triple generation from manufacturing data
- SPARQL query execution for semantic queries
- Data transformation between ontology and application models

Standards:
- RDF 1.1: Resource Description Framework
- SPARQL 1.1: Query Language for RDF
- JSON-LD: JSON Linked Data format

Research Value:
- Semantic interoperability for Industry 4.0
- Knowledge-based manufacturing queries
- Linked data for supply chain integration
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple, Union, Generator
from enum import Enum
from datetime import datetime
import json
import re
import logging
from abc import ABC, abstractmethod

from .manufacturing_ontology import (
    ManufacturingOntology,
    OntologyClass,
    OntologyProperty,
    OntologyIndividual,
    OntologyIRI
)

logger = logging.getLogger(__name__)


# =============================================================================
# RDF Core Types
# =============================================================================

class RDFTermType(Enum):
    """Types of RDF terms."""
    IRI = "iri"
    BLANK_NODE = "blank_node"
    LITERAL = "literal"


@dataclass
class RDFTerm:
    """Base class for RDF terms."""
    term_type: RDFTermType
    value: str

    def to_ntriples(self) -> str:
        """Convert to N-Triples format."""
        if self.term_type == RDFTermType.IRI:
            return f"<{self.value}>"
        elif self.term_type == RDFTermType.BLANK_NODE:
            return f"_:{self.value}"
        else:
            return f'"{self.value}"'


@dataclass
class RDFLiteral(RDFTerm):
    """RDF Literal with optional datatype or language tag."""
    datatype: Optional[str] = None
    language: Optional[str] = None

    def __post_init__(self):
        self.term_type = RDFTermType.LITERAL

    def to_ntriples(self) -> str:
        """Convert to N-Triples format with datatype/language."""
        escaped = self.value.replace('\\', '\\\\').replace('"', '\\"')
        if self.language:
            return f'"{escaped}"@{self.language}'
        elif self.datatype:
            return f'"{escaped}"^^<{self.datatype}>'
        else:
            return f'"{escaped}"'


@dataclass
class RDFIRI(RDFTerm):
    """RDF IRI (Internationalized Resource Identifier)."""

    def __post_init__(self):
        self.term_type = RDFTermType.IRI


@dataclass
class RDFBlankNode(RDFTerm):
    """RDF Blank Node (anonymous node)."""

    def __post_init__(self):
        self.term_type = RDFTermType.BLANK_NODE


@dataclass
class RDFTriple:
    """
    RDF Triple (Statement).

    The fundamental unit of RDF data:
    - Subject: The entity being described
    - Predicate: The property/relationship
    - Object: The value or related entity
    """
    subject: RDFTerm
    predicate: RDFTerm
    obj: RDFTerm  # 'object' is reserved in Python

    def to_ntriples(self) -> str:
        """Convert to N-Triples format."""
        return f"{self.subject.to_ntriples()} {self.predicate.to_ntriples()} {self.obj.to_ntriples()} ."

    def to_tuple(self) -> Tuple[str, str, str]:
        """Convert to tuple format."""
        return (self.subject.value, self.predicate.value, self.obj.value)


# =============================================================================
# SPARQL Query Types
# =============================================================================

class SPARQLQueryType(Enum):
    """Types of SPARQL queries."""
    SELECT = "SELECT"
    CONSTRUCT = "CONSTRUCT"
    ASK = "ASK"
    DESCRIBE = "DESCRIBE"


@dataclass
class SPARQLVariable:
    """SPARQL query variable."""
    name: str

    def __str__(self) -> str:
        return f"?{self.name}"


@dataclass
class SPARQLTriplePattern:
    """SPARQL triple pattern for WHERE clauses."""
    subject: Union[SPARQLVariable, str]
    predicate: Union[SPARQLVariable, str]
    obj: Union[SPARQLVariable, str]

    def to_sparql(self, prefixes: Dict[str, str] = None) -> str:
        """Convert to SPARQL pattern."""
        def format_term(term):
            if isinstance(term, SPARQLVariable):
                return str(term)
            elif term.startswith('http://') or term.startswith('https://'):
                return f"<{term}>"
            else:
                return term

        return f"{format_term(self.subject)} {format_term(self.predicate)} {format_term(self.obj)}"


@dataclass
class SPARQLFilter:
    """SPARQL FILTER expression."""
    expression: str

    def to_sparql(self) -> str:
        return f"FILTER ({self.expression})"


@dataclass
class SPARQLQuery:
    """
    SPARQL Query builder and representation.

    Supports:
    - SELECT queries with projections
    - WHERE clause with triple patterns
    - FILTER expressions
    - OPTIONAL patterns
    - ORDER BY, LIMIT, OFFSET
    """
    query_type: SPARQLQueryType
    prefixes: Dict[str, str] = field(default_factory=dict)
    select_variables: List[SPARQLVariable] = field(default_factory=list)
    where_patterns: List[Union[SPARQLTriplePattern, SPARQLFilter]] = field(default_factory=list)
    optional_patterns: List[List[SPARQLTriplePattern]] = field(default_factory=list)
    order_by: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    distinct: bool = False

    def add_prefix(self, prefix: str, namespace: str) -> 'SPARQLQuery':
        """Add a namespace prefix."""
        self.prefixes[prefix] = namespace
        return self

    def add_variable(self, name: str) -> 'SPARQLQuery':
        """Add a SELECT variable."""
        self.select_variables.append(SPARQLVariable(name))
        return self

    def add_pattern(
        self,
        subject: Union[str, SPARQLVariable],
        predicate: Union[str, SPARQLVariable],
        obj: Union[str, SPARQLVariable]
    ) -> 'SPARQLQuery':
        """Add a triple pattern to WHERE clause."""
        if isinstance(subject, str) and not subject.startswith('?'):
            subject = subject if subject.startswith('http') or ':' in subject else f":{subject}"
        if isinstance(predicate, str) and not predicate.startswith('?'):
            predicate = predicate if predicate.startswith('http') or ':' in predicate else f":{predicate}"
        if isinstance(obj, str) and not obj.startswith('?'):
            obj = obj if obj.startswith('http') or ':' in obj else f":{obj}"

        self.where_patterns.append(SPARQLTriplePattern(subject, predicate, obj))
        return self

    def add_filter(self, expression: str) -> 'SPARQLQuery':
        """Add a FILTER expression."""
        self.where_patterns.append(SPARQLFilter(expression))
        return self

    def add_optional(self, patterns: List[Tuple[str, str, str]]) -> 'SPARQLQuery':
        """Add OPTIONAL patterns."""
        optional = [
            SPARQLTriplePattern(s, p, o)
            for s, p, o in patterns
        ]
        self.optional_patterns.append(optional)
        return self

    def set_order_by(self, variable: str, descending: bool = False) -> 'SPARQLQuery':
        """Set ORDER BY clause."""
        self.order_by = f"{'DESC' if descending else 'ASC'}(?{variable})"
        return self

    def set_limit(self, limit: int) -> 'SPARQLQuery':
        """Set LIMIT clause."""
        self.limit = limit
        return self

    def set_offset(self, offset: int) -> 'SPARQLQuery':
        """Set OFFSET clause."""
        self.offset = offset
        return self

    def set_distinct(self, distinct: bool = True) -> 'SPARQLQuery':
        """Set DISTINCT modifier."""
        self.distinct = distinct
        return self

    def to_sparql(self) -> str:
        """Generate SPARQL query string."""
        lines = []

        # Prefixes
        for prefix, ns in self.prefixes.items():
            lines.append(f"PREFIX {prefix}: <{ns}>")

        if lines:
            lines.append("")

        # SELECT clause
        if self.query_type == SPARQLQueryType.SELECT:
            distinct = "DISTINCT " if self.distinct else ""
            if self.select_variables:
                vars_str = " ".join(str(v) for v in self.select_variables)
                lines.append(f"SELECT {distinct}{vars_str}")
            else:
                lines.append(f"SELECT {distinct}*")

        elif self.query_type == SPARQLQueryType.ASK:
            lines.append("ASK")

        elif self.query_type == SPARQLQueryType.CONSTRUCT:
            lines.append("CONSTRUCT { ?s ?p ?o }")

        # WHERE clause
        lines.append("WHERE {")
        for pattern in self.where_patterns:
            if isinstance(pattern, SPARQLTriplePattern):
                lines.append(f"  {pattern.to_sparql()} .")
            else:
                lines.append(f"  {pattern.to_sparql()}")

        # OPTIONAL patterns
        for optional in self.optional_patterns:
            lines.append("  OPTIONAL {")
            for pattern in optional:
                lines.append(f"    {pattern.to_sparql()} .")
            lines.append("  }")

        lines.append("}")

        # ORDER BY
        if self.order_by:
            lines.append(f"ORDER BY {self.order_by}")

        # LIMIT
        if self.limit is not None:
            lines.append(f"LIMIT {self.limit}")

        # OFFSET
        if self.offset is not None:
            lines.append(f"OFFSET {self.offset}")

        return "\n".join(lines)


# =============================================================================
# SPARQL Query Result
# =============================================================================

@dataclass
class SPARQLResult:
    """Result of a SPARQL query execution."""
    variables: List[str]
    bindings: List[Dict[str, Any]]
    execution_time_ms: float = 0.0

    def __iter__(self):
        return iter(self.bindings)

    def __len__(self):
        return len(self.bindings)

    def to_dataframe(self):
        """Convert to pandas DataFrame (if available)."""
        try:
            import pandas as pd
            return pd.DataFrame(self.bindings)
        except ImportError:
            logger.warning("pandas not available, returning dict list")
            return self.bindings


# =============================================================================
# Ontology Mapper
# =============================================================================

class OntologyMapper:
    """
    Maps manufacturing data to RDF and executes SPARQL queries.

    Provides:
    - Data-to-RDF transformation
    - SPARQL query building and execution
    - Semantic search and reasoning
    """

    # Standard prefixes
    STANDARD_PREFIXES = {
        'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'owl': 'http://www.w3.org/2002/07/owl#',
        'xsd': 'http://www.w3.org/2001/XMLSchema#',
        'lego': 'http://lego-mcp.org/ontology/manufacturing#',
        'iso23247': 'http://iso.org/23247/ontology#',
    }

    # XSD datatype mappings
    XSD_DATATYPES = {
        'int': 'http://www.w3.org/2001/XMLSchema#integer',
        'integer': 'http://www.w3.org/2001/XMLSchema#integer',
        'float': 'http://www.w3.org/2001/XMLSchema#float',
        'double': 'http://www.w3.org/2001/XMLSchema#double',
        'decimal': 'http://www.w3.org/2001/XMLSchema#decimal',
        'string': 'http://www.w3.org/2001/XMLSchema#string',
        'boolean': 'http://www.w3.org/2001/XMLSchema#boolean',
        'date': 'http://www.w3.org/2001/XMLSchema#date',
        'datetime': 'http://www.w3.org/2001/XMLSchema#dateTime',
        'time': 'http://www.w3.org/2001/XMLSchema#time',
    }

    def __init__(self, ontology: ManufacturingOntology):
        self.ontology = ontology
        self._triple_store: List[RDFTriple] = []
        self._blank_node_counter = 0

    # -------------------------------------------------------------------------
    # RDF Triple Generation
    # -------------------------------------------------------------------------

    def create_iri(self, local_name: str, namespace: str = None) -> RDFIRI:
        """Create an RDF IRI."""
        ns = namespace or self.ontology.LEGO_NS
        return RDFIRI(value=f"{ns}#{local_name}")

    def create_literal(
        self,
        value: Any,
        datatype: str = None,
        language: str = None
    ) -> RDFLiteral:
        """Create an RDF literal with appropriate datatype."""
        str_value = str(value)

        if datatype:
            dt = self.XSD_DATATYPES.get(datatype, datatype)
            return RDFLiteral(value=str_value, datatype=dt)

        # Auto-detect datatype
        if isinstance(value, bool):
            return RDFLiteral(value=str(value).lower(), datatype=self.XSD_DATATYPES['boolean'])
        elif isinstance(value, int):
            return RDFLiteral(value=str_value, datatype=self.XSD_DATATYPES['integer'])
        elif isinstance(value, float):
            return RDFLiteral(value=str_value, datatype=self.XSD_DATATYPES['double'])
        elif isinstance(value, datetime):
            return RDFLiteral(value=value.isoformat(), datatype=self.XSD_DATATYPES['datetime'])
        else:
            if language:
                return RDFLiteral(value=str_value, language=language)
            return RDFLiteral(value=str_value, datatype=self.XSD_DATATYPES['string'])

    def create_blank_node(self) -> RDFBlankNode:
        """Create a new blank node."""
        self._blank_node_counter += 1
        return RDFBlankNode(value=f"b{self._blank_node_counter}")

    def create_triple(
        self,
        subject: Union[str, RDFTerm],
        predicate: Union[str, RDFTerm],
        obj: Union[str, RDFTerm, Any]
    ) -> RDFTriple:
        """Create an RDF triple and add to store."""
        # Convert strings to IRIs
        if isinstance(subject, str):
            subject = self.create_iri(subject)
        if isinstance(predicate, str):
            predicate = self.create_iri(predicate)
        if isinstance(obj, str) and (obj.startswith('http://') or obj.startswith('https://')):
            obj = RDFIRI(value=obj)
        elif not isinstance(obj, RDFTerm):
            obj = self.create_literal(obj)

        triple = RDFTriple(subject=subject, predicate=predicate, obj=obj)
        self._triple_store.append(triple)
        return triple

    # -------------------------------------------------------------------------
    # Manufacturing Data Mapping
    # -------------------------------------------------------------------------

    def map_brick(self, brick_data: Dict[str, Any]) -> List[RDFTriple]:
        """
        Map LEGO brick data to RDF triples.

        Args:
            brick_data: Dictionary with brick properties:
                - id: Unique identifier
                - type: Brick type (standard, plate, tile, etc.)
                - width: Width in studs
                - length: Length in studs
                - height_ratio: Height as ratio of standard brick
                - color: Color name
                - material: Material type

        Returns:
            List of generated RDF triples
        """
        triples = []
        brick_id = brick_data.get('id', f"brick_{datetime.now().timestamp()}")
        brick_iri = self.create_iri(brick_id)

        # Type assertion
        brick_type = brick_data.get('type', 'LegoBrick')
        type_class = self.ontology.get_class(brick_type) or self.ontology.get_class('LegoBrick')
        triples.append(self.create_triple(
            brick_iri,
            RDFIRI(value=f"{self.STANDARD_PREFIXES['rdf']}type"),
            RDFIRI(value=str(type_class.iri))
        ))

        # Dimensions
        if 'width' in brick_data:
            triples.append(self.create_triple(
                brick_iri,
                self.create_iri('dimensionX'),
                self.create_literal(brick_data['width'], 'integer')
            ))

        if 'length' in brick_data:
            triples.append(self.create_triple(
                brick_iri,
                self.create_iri('dimensionY'),
                self.create_literal(brick_data['length'], 'integer')
            ))

        if 'height_ratio' in brick_data:
            triples.append(self.create_triple(
                brick_iri,
                self.create_iri('heightRatio'),
                self.create_literal(brick_data['height_ratio'], 'float')
            ))

        # Color
        if 'color' in brick_data:
            triples.append(self.create_triple(
                brick_iri,
                self.create_iri('hasColor'),
                self.create_literal(brick_data['color'])
            ))

        # Material
        if 'material' in brick_data:
            material_iri = self.create_iri(brick_data['material'])
            triples.append(self.create_triple(
                brick_iri,
                self.create_iri('usesMaterial'),
                material_iri
            ))

        # Stud count
        if 'width' in brick_data and 'length' in brick_data:
            stud_count = brick_data['width'] * brick_data['length']
            triples.append(self.create_triple(
                brick_iri,
                self.create_iri('studCount'),
                self.create_literal(stud_count, 'integer')
            ))

        return triples

    def map_process(self, process_data: Dict[str, Any]) -> List[RDFTriple]:
        """
        Map manufacturing process data to RDF triples.

        Args:
            process_data: Dictionary with process properties:
                - id: Process identifier
                - type: Process type (FDMPrinting, CNCMilling, etc.)
                - equipment_id: Equipment used
                - start_time: Process start timestamp
                - end_time: Process end timestamp
                - parameters: Process parameters dict

        Returns:
            List of generated RDF triples
        """
        triples = []
        process_id = process_data.get('id', f"process_{datetime.now().timestamp()}")
        process_iri = self.create_iri(process_id)

        # Type
        process_type = process_data.get('type', 'ManufacturingProcess')
        type_class = self.ontology.get_class(process_type) or self.ontology.get_class('ManufacturingProcess')
        triples.append(self.create_triple(
            process_iri,
            RDFIRI(value=f"{self.STANDARD_PREFIXES['rdf']}type"),
            RDFIRI(value=str(type_class.iri))
        ))

        # Equipment
        if 'equipment_id' in process_data:
            equipment_iri = self.create_iri(process_data['equipment_id'])
            triples.append(self.create_triple(
                process_iri,
                self.create_iri('usesEquipment'),
                equipment_iri
            ))

        # Time bounds
        if 'start_time' in process_data:
            triples.append(self.create_triple(
                process_iri,
                self.create_iri('startTime'),
                self.create_literal(process_data['start_time'], 'datetime')
            ))

        if 'end_time' in process_data:
            triples.append(self.create_triple(
                process_iri,
                self.create_iri('endTime'),
                self.create_literal(process_data['end_time'], 'datetime')
            ))

        # Parameters as blank node
        if 'parameters' in process_data:
            params_bn = self.create_blank_node()
            triples.append(self.create_triple(
                process_iri,
                self.create_iri('hasParameters'),
                params_bn
            ))
            for key, value in process_data['parameters'].items():
                triples.append(self.create_triple(
                    params_bn,
                    self.create_iri(key),
                    self.create_literal(value)
                ))

        return triples

    def map_quality_event(self, quality_data: Dict[str, Any]) -> List[RDFTriple]:
        """
        Map quality inspection data to RDF triples.

        Args:
            quality_data: Dictionary with quality properties:
                - id: Inspection identifier
                - product_id: Product inspected
                - type: Inspection type
                - result: Pass/Fail
                - defects: List of detected defects
                - measurements: Measurement values

        Returns:
            List of generated RDF triples
        """
        triples = []
        inspection_id = quality_data.get('id', f"inspection_{datetime.now().timestamp()}")
        inspection_iri = self.create_iri(inspection_id)

        # Type
        inspection_type = quality_data.get('type', 'QualityInspection')
        type_class = self.ontology.get_class(inspection_type) or self.ontology.get_class('QualityInspection')
        triples.append(self.create_triple(
            inspection_iri,
            RDFIRI(value=f"{self.STANDARD_PREFIXES['rdf']}type"),
            RDFIRI(value=str(type_class.iri))
        ))

        # Product link
        if 'product_id' in quality_data:
            product_iri = self.create_iri(quality_data['product_id'])
            triples.append(self.create_triple(
                inspection_iri,
                self.create_iri('inspectsProduct'),
                product_iri
            ))

        # Result
        if 'result' in quality_data:
            triples.append(self.create_triple(
                inspection_iri,
                self.create_iri('inspectionResult'),
                self.create_literal(quality_data['result'])
            ))

        # Defects
        for defect in quality_data.get('defects', []):
            defect_bn = self.create_blank_node()
            defect_type = defect.get('type', 'Defect')
            defect_class = self.ontology.get_class(defect_type) or self.ontology.get_class('Defect')

            triples.append(self.create_triple(
                inspection_iri,
                self.create_iri('foundDefect'),
                defect_bn
            ))
            triples.append(self.create_triple(
                defect_bn,
                RDFIRI(value=f"{self.STANDARD_PREFIXES['rdf']}type"),
                RDFIRI(value=str(defect_class.iri))
            ))
            if 'severity' in defect:
                triples.append(self.create_triple(
                    defect_bn,
                    self.create_iri('severity'),
                    self.create_literal(defect['severity'])
                ))

        # Measurements
        for name, value in quality_data.get('measurements', {}).items():
            triples.append(self.create_triple(
                inspection_iri,
                self.create_iri(f'measurement_{name}'),
                self.create_literal(value, 'float')
            ))

        return triples

    def map_sustainability(self, sustainability_data: Dict[str, Any]) -> List[RDFTriple]:
        """
        Map sustainability data to RDF triples.

        Args:
            sustainability_data: Dictionary with:
                - id: Event identifier
                - process_id: Related process
                - carbon_kg: CO2 emissions in kg
                - energy_kwh: Energy consumed in kWh
                - waste_kg: Material waste in kg

        Returns:
            List of generated RDF triples
        """
        triples = []
        event_id = sustainability_data.get('id', f"sustainability_{datetime.now().timestamp()}")
        event_iri = self.create_iri(event_id)

        # Carbon footprint
        if 'carbon_kg' in sustainability_data:
            carbon_bn = self.create_blank_node()
            triples.append(self.create_triple(
                event_iri,
                self.create_iri('hasEnvironmentalImpact'),
                carbon_bn
            ))
            triples.append(self.create_triple(
                carbon_bn,
                RDFIRI(value=f"{self.STANDARD_PREFIXES['rdf']}type"),
                self.create_iri('CarbonFootprint')
            ))
            triples.append(self.create_triple(
                carbon_bn,
                self.create_iri('carbonEmission'),
                self.create_literal(sustainability_data['carbon_kg'], 'float')
            ))

        # Energy consumption
        if 'energy_kwh' in sustainability_data:
            energy_bn = self.create_blank_node()
            triples.append(self.create_triple(
                event_iri,
                self.create_iri('hasEnvironmentalImpact'),
                energy_bn
            ))
            triples.append(self.create_triple(
                energy_bn,
                RDFIRI(value=f"{self.STANDARD_PREFIXES['rdf']}type"),
                self.create_iri('EnergyConsumption')
            ))
            triples.append(self.create_triple(
                energy_bn,
                self.create_iri('energyConsumed'),
                self.create_literal(sustainability_data['energy_kwh'], 'float')
            ))

        # Material waste
        if 'waste_kg' in sustainability_data:
            waste_bn = self.create_blank_node()
            triples.append(self.create_triple(
                event_iri,
                self.create_iri('hasEnvironmentalImpact'),
                waste_bn
            ))
            triples.append(self.create_triple(
                waste_bn,
                RDFIRI(value=f"{self.STANDARD_PREFIXES['rdf']}type"),
                self.create_iri('MaterialWaste')
            ))
            triples.append(self.create_triple(
                waste_bn,
                self.create_iri('wasteAmount'),
                self.create_literal(sustainability_data['waste_kg'], 'float')
            ))

        # Process link
        if 'process_id' in sustainability_data:
            process_iri = self.create_iri(sustainability_data['process_id'])
            triples.append(self.create_triple(
                process_iri,
                self.create_iri('hasEnvironmentalImpact'),
                event_iri
            ))

        return triples

    # -------------------------------------------------------------------------
    # SPARQL Query Building
    # -------------------------------------------------------------------------

    def create_query(self, query_type: SPARQLQueryType = SPARQLQueryType.SELECT) -> SPARQLQuery:
        """Create a new SPARQL query with standard prefixes."""
        query = SPARQLQuery(query_type=query_type)
        for prefix, ns in self.STANDARD_PREFIXES.items():
            query.add_prefix(prefix, ns)
        return query

    def query_bricks_by_type(self, brick_type: str) -> SPARQLQuery:
        """Query all bricks of a specific type."""
        query = self.create_query()
        query.add_variable('brick')
        query.add_variable('width')
        query.add_variable('length')
        query.add_variable('color')

        type_iri = f"lego:{brick_type}"
        query.add_pattern('?brick', 'rdf:type', type_iri)
        query.add_optional([
            ('?brick', 'lego:dimensionX', '?width'),
        ])
        query.add_optional([
            ('?brick', 'lego:dimensionY', '?length'),
        ])
        query.add_optional([
            ('?brick', 'lego:hasColor', '?color'),
        ])

        return query

    def query_defective_products(self) -> SPARQLQuery:
        """Query products with defects."""
        query = self.create_query()
        query.add_variable('product')
        query.add_variable('defect')
        query.add_variable('defectType')
        query.add_variable('severity')

        query.add_pattern('?inspection', 'lego:inspectsProduct', '?product')
        query.add_pattern('?inspection', 'lego:foundDefect', '?defect')
        query.add_pattern('?defect', 'rdf:type', '?defectType')
        query.add_optional([
            ('?defect', 'lego:severity', '?severity'),
        ])

        return query

    def query_sustainability_by_process(self, process_id: str = None) -> SPARQLQuery:
        """Query sustainability metrics, optionally filtered by process."""
        query = self.create_query()
        query.add_variable('process')
        query.add_variable('carbon')
        query.add_variable('energy')

        if process_id:
            process_iri = f"lego:{process_id}"
            query.add_pattern(process_iri, 'lego:hasEnvironmentalImpact', '?impact')
        else:
            query.add_pattern('?process', 'lego:hasEnvironmentalImpact', '?impact')

        query.add_optional([
            ('?impact', 'lego:carbonEmission', '?carbon'),
        ])
        query.add_optional([
            ('?impact', 'lego:energyConsumed', '?energy'),
        ])

        return query

    def query_digital_twins(self) -> SPARQLQuery:
        """Query all digital twin entities and their physical counterparts."""
        query = self.create_query()
        query.add_variable('physical')
        query.add_variable('twin')
        query.add_variable('type')

        query.add_pattern('?physical', 'iso23247:hasDigitalTwin', '?twin')
        query.add_pattern('?physical', 'rdf:type', '?type')

        return query

    # -------------------------------------------------------------------------
    # In-Memory Query Execution
    # -------------------------------------------------------------------------

    def execute_query(self, query: SPARQLQuery) -> SPARQLResult:
        """
        Execute a SPARQL query against in-memory triple store.

        Note: This is a simplified implementation for demonstration.
        Production use should integrate with a proper triple store
        like Apache Jena, RDF4J, or GraphDB.
        """
        start_time = datetime.now()

        # Parse query patterns
        results = []
        bindings = [{}]  # Start with empty binding

        for pattern in query.where_patterns:
            if isinstance(pattern, SPARQLTriplePattern):
                new_bindings = []
                for binding in bindings:
                    matches = self._match_pattern(pattern, binding)
                    new_bindings.extend(matches)
                bindings = new_bindings

            elif isinstance(pattern, SPARQLFilter):
                bindings = [
                    b for b in bindings
                    if self._evaluate_filter(pattern.expression, b)
                ]

        # Apply DISTINCT
        if query.distinct:
            seen = set()
            unique_bindings = []
            for b in bindings:
                key = tuple(sorted(b.items()))
                if key not in seen:
                    seen.add(key)
                    unique_bindings.append(b)
            bindings = unique_bindings

        # Apply ORDER BY (simplified)
        if query.order_by:
            # Extract variable name from ASC(?var) or DESC(?var)
            match = re.match(r'(ASC|DESC)\(\?(\w+)\)', query.order_by)
            if match:
                direction, var = match.groups()
                reverse = direction == 'DESC'
                bindings.sort(key=lambda b: b.get(var, ''), reverse=reverse)

        # Apply OFFSET
        if query.offset:
            bindings = bindings[query.offset:]

        # Apply LIMIT
        if query.limit:
            bindings = bindings[:query.limit]

        # Project variables
        if query.select_variables:
            var_names = [v.name for v in query.select_variables]
            bindings = [
                {k: v for k, v in b.items() if k in var_names}
                for b in bindings
            ]

        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        return SPARQLResult(
            variables=[v.name for v in query.select_variables] if query.select_variables else list(bindings[0].keys()) if bindings else [],
            bindings=bindings,
            execution_time_ms=execution_time
        )

    def _match_pattern(
        self,
        pattern: SPARQLTriplePattern,
        binding: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Match a triple pattern against the store."""
        results = []

        for triple in self._triple_store:
            new_binding = binding.copy()
            match = True

            # Match subject
            if isinstance(pattern.subject, SPARQLVariable):
                var_name = pattern.subject.name
                if var_name in binding:
                    if binding[var_name] != triple.subject.value:
                        match = False
                else:
                    new_binding[var_name] = triple.subject.value
            else:
                if not self._term_matches(pattern.subject, triple.subject):
                    match = False

            # Match predicate
            if match and isinstance(pattern.predicate, SPARQLVariable):
                var_name = pattern.predicate.name
                if var_name in binding:
                    if binding[var_name] != triple.predicate.value:
                        match = False
                else:
                    new_binding[var_name] = triple.predicate.value
            elif match:
                if not self._term_matches(pattern.predicate, triple.predicate):
                    match = False

            # Match object
            if match and isinstance(pattern.obj, SPARQLVariable):
                var_name = pattern.obj.name
                if var_name in binding:
                    if binding[var_name] != triple.obj.value:
                        match = False
                else:
                    new_binding[var_name] = triple.obj.value
            elif match:
                if not self._term_matches(pattern.obj, triple.obj):
                    match = False

            if match:
                results.append(new_binding)

        return results

    def _term_matches(self, pattern_term: str, triple_term: RDFTerm) -> bool:
        """Check if a pattern term matches a triple term."""
        pattern_value = pattern_term
        if pattern_value.startswith('<') and pattern_value.endswith('>'):
            pattern_value = pattern_value[1:-1]

        # Handle prefixed IRIs
        for prefix, ns in self.STANDARD_PREFIXES.items():
            if pattern_value.startswith(f"{prefix}:"):
                pattern_value = pattern_value.replace(f"{prefix}:", f"{ns}")
                break

        return pattern_value == triple_term.value

    def _evaluate_filter(self, expression: str, binding: Dict[str, Any]) -> bool:
        """Evaluate a FILTER expression (simplified)."""
        # Replace variables with values
        expr = expression
        for var, value in binding.items():
            expr = expr.replace(f"?{var}", repr(value))

        try:
            return eval(expr)
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------

    def export_ntriples(self) -> str:
        """Export triple store to N-Triples format."""
        return '\n'.join(t.to_ntriples() for t in self._triple_store)

    def export_turtle(self) -> str:
        """Export triple store to Turtle format (simplified)."""
        lines = []

        # Prefixes
        for prefix, ns in self.STANDARD_PREFIXES.items():
            lines.append(f"@prefix {prefix}: <{ns}> .")
        lines.append("")

        # Group triples by subject
        subjects: Dict[str, List[RDFTriple]] = {}
        for triple in self._triple_store:
            subj = triple.subject.value
            if subj not in subjects:
                subjects[subj] = []
            subjects[subj].append(triple)

        # Output grouped triples
        for subj, triples in subjects.items():
            lines.append(f"<{subj}>")
            for i, triple in enumerate(triples):
                pred = triple.predicate.to_ntriples()
                obj = triple.obj.to_ntriples()
                separator = ";" if i < len(triples) - 1 else "."
                lines.append(f"    {pred} {obj} {separator}")
            lines.append("")

        return '\n'.join(lines)

    def export_jsonld(self) -> Dict[str, Any]:
        """Export triple store to JSON-LD format."""
        context = {prefix: ns for prefix, ns in self.STANDARD_PREFIXES.items()}

        # Build graph
        graph = {}
        for triple in self._triple_store:
            subj = triple.subject.value
            if subj not in graph:
                graph[subj] = {"@id": subj}

            pred = triple.predicate.value
            obj_value = triple.obj.value

            if triple.obj.term_type == RDFTermType.IRI:
                obj_data = {"@id": obj_value}
            else:
                obj_data = obj_value

            if pred in graph[subj]:
                if isinstance(graph[subj][pred], list):
                    graph[subj][pred].append(obj_data)
                else:
                    graph[subj][pred] = [graph[subj][pred], obj_data]
            else:
                graph[subj][pred] = obj_data

        return {
            "@context": context,
            "@graph": list(graph.values())
        }

    def get_triple_count(self) -> int:
        """Get the number of triples in the store."""
        return len(self._triple_store)

    def clear(self):
        """Clear all triples from the store."""
        self._triple_store.clear()
        self._blank_node_counter = 0
