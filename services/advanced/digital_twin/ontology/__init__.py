"""
Digital Twin Ontology Services - ISO 23247 Compliant.

This module provides semantic modeling for manufacturing digital twins
following the ISO 23247 Digital Twin Manufacturing Framework.

Components:
- ManufacturingOntology: OWL ontology for manufacturing concepts
- OntologyMapper: RDF/SPARQL integration for semantic queries
- KnowledgeGraph: Neo4j-based knowledge graph for entity relationships

Standards Compliance:
- ISO 23247-1: Overview and general principles
- ISO 23247-2: Reference architecture
- ISO 23247-3: Digital representation
- ISO 23247-4: Information exchange

Research Value:
- Semantic interoperability for Industry 4.0
- Knowledge-based reasoning for manufacturing
- Formal ontology for LEGO brick production
"""

from .manufacturing_ontology import ManufacturingOntology, OntologyClass, OntologyProperty
from .ontology_mapper import OntologyMapper, SPARQLQuery, RDFTriple
from .knowledge_graph import KnowledgeGraph, GraphNode, GraphEdge

__all__ = [
    'ManufacturingOntology',
    'OntologyClass',
    'OntologyProperty',
    'OntologyMapper',
    'SPARQLQuery',
    'RDFTriple',
    'KnowledgeGraph',
    'GraphNode',
    'GraphEdge',
]
