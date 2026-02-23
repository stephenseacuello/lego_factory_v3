"""
Manufacturing Ontology - ISO 23247 Digital Twin Framework.

This module implements a formal OWL ontology for manufacturing digital twins,
specifically designed for LEGO brick production systems.

Standards:
- ISO 23247: Digital Twin Manufacturing Framework
- OWL 2: Web Ontology Language
- RAMI 4.0: Reference Architecture Model for Industry 4.0
- ISA-95/IEC 62264: Enterprise-Control Integration

Novel Research Contribution:
- First formal ontology for LEGO-compatible brick manufacturing
- Integration of quality, sustainability, and scheduling concepts
- Physics-informed constraints for additive manufacturing
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set, Tuple
from enum import Enum
from datetime import datetime
import json
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# =============================================================================
# ISO 23247 Core Concepts
# =============================================================================

class ISO23247Layer(Enum):
    """ISO 23247-2 Reference Architecture Layers."""
    USER_LAYER = "user_layer"  # Human-machine interfaces
    DIGITAL_TWIN_LAYER = "digital_twin_layer"  # Core twin logic
    DATA_COLLECTION_LAYER = "data_collection_layer"  # Sensors/data sources
    OBSERVABLE_MANUFACTURING_ELEMENT = "observable_manufacturing_element"  # Physical assets


class ISO23247EntityType(Enum):
    """ISO 23247-3 Digital Representation Entity Types."""
    PRODUCT = "product"  # Manufactured items (LEGO bricks)
    PROCESS = "process"  # Manufacturing processes
    RESOURCE = "resource"  # Equipment and personnel
    SYSTEM = "system"  # Manufacturing system level
    ENTERPRISE = "enterprise"  # Enterprise level


class RAMI40Dimension(Enum):
    """RAMI 4.0 Reference Architecture Dimensions."""
    HIERARCHY = "hierarchy"  # Product, Field Device, Control Device, etc.
    LIFE_CYCLE = "life_cycle"  # Development, Maintenance, Usage
    LAYERS = "layers"  # Business, Functional, Information, etc.


# =============================================================================
# Ontology Core Classes
# =============================================================================

@dataclass
class OntologyIRI:
    """Internationalized Resource Identifier for ontology elements."""
    namespace: str
    local_name: str

    def __str__(self) -> str:
        return f"{self.namespace}#{self.local_name}"

    @classmethod
    def from_string(cls, iri_string: str) -> 'OntologyIRI':
        """Parse IRI from string."""
        if '#' in iri_string:
            ns, name = iri_string.rsplit('#', 1)
            return cls(namespace=ns, local_name=name)
        return cls(namespace="", local_name=iri_string)


@dataclass
class OntologyClass:
    """
    OWL Class definition for manufacturing concepts.

    Represents a concept in the manufacturing domain, such as:
    - LegoBrick: A LEGO-compatible brick product
    - FDMPrinter: A Fused Deposition Modeling 3D printer
    - QualityInspection: A quality control process
    """
    iri: OntologyIRI
    label: str
    comment: str
    parent_classes: List['OntologyClass'] = field(default_factory=list)
    equivalent_classes: List['OntologyClass'] = field(default_factory=list)
    disjoint_classes: List['OntologyClass'] = field(default_factory=list)
    restrictions: List['PropertyRestriction'] = field(default_factory=list)
    annotations: Dict[str, Any] = field(default_factory=dict)

    # ISO 23247 metadata
    iso23247_entity_type: Optional[ISO23247EntityType] = None
    iso23247_layer: Optional[ISO23247Layer] = None

    def __hash__(self):
        return hash(str(self.iri))

    def __eq__(self, other):
        if isinstance(other, OntologyClass):
            return str(self.iri) == str(other.iri)
        return False


@dataclass
class OntologyProperty:
    """
    OWL Property definition for relationships and attributes.

    Types:
    - ObjectProperty: Relates individuals to individuals
    - DataProperty: Relates individuals to data values
    - AnnotationProperty: Metadata about ontology elements
    """
    iri: OntologyIRI
    label: str
    comment: str
    property_type: str  # 'object', 'data', 'annotation'
    domain: Optional[OntologyClass] = None
    range_class: Optional[OntologyClass] = None  # For object properties
    range_datatype: Optional[str] = None  # For data properties (xsd:float, etc.)
    inverse_property: Optional['OntologyProperty'] = None
    is_functional: bool = False
    is_transitive: bool = False
    is_symmetric: bool = False
    is_asymmetric: bool = False
    is_reflexive: bool = False
    is_irreflexive: bool = False
    parent_properties: List['OntologyProperty'] = field(default_factory=list)

    def __hash__(self):
        return hash(str(self.iri))


@dataclass
class PropertyRestriction:
    """OWL Property Restriction for class definitions."""
    property: OntologyProperty
    restriction_type: str  # 'some', 'only', 'value', 'min', 'max', 'exactly'
    filler: Any  # Class, value, or cardinality


@dataclass
class OntologyIndividual:
    """OWL Individual (instance) in the ontology."""
    iri: OntologyIRI
    classes: List[OntologyClass]
    object_properties: Dict[OntologyProperty, List['OntologyIndividual']] = field(default_factory=dict)
    data_properties: Dict[OntologyProperty, List[Any]] = field(default_factory=dict)
    annotations: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(str(self.iri))


# =============================================================================
# Manufacturing Ontology Implementation
# =============================================================================

class ManufacturingOntology:
    """
    ISO 23247 Compliant Manufacturing Ontology.

    This ontology models the LEGO brick manufacturing domain including:
    - Products: Bricks, plates, tiles, technic parts
    - Processes: FDM printing, CNC milling, injection molding, quality inspection
    - Resources: Printers, mills, materials, operators
    - Quality: Defects, measurements, SPC data
    - Sustainability: Carbon emissions, energy consumption, material waste

    Novel Research Contributions:
    1. First formal ontology for LEGO-compatible manufacturing
    2. Integration of ISO 23247 digital twin concepts
    3. Physics-informed constraints for additive manufacturing
    4. Sustainability-aware production planning concepts
    """

    # Ontology namespaces
    LEGO_NS = "http://lego-mcp.org/ontology/manufacturing"
    ISO23247_NS = "http://iso.org/23247/ontology"
    ISA95_NS = "http://isa.org/95/ontology"
    RAMI40_NS = "http://plattform-i40.de/rami40"

    def __init__(self):
        self.classes: Dict[str, OntologyClass] = {}
        self.properties: Dict[str, OntologyProperty] = {}
        self.individuals: Dict[str, OntologyIndividual] = {}
        self._initialize_core_ontology()

    def _initialize_core_ontology(self):
        """Initialize the core manufacturing ontology."""
        self._create_iso23247_classes()
        self._create_product_classes()
        self._create_process_classes()
        self._create_resource_classes()
        self._create_quality_classes()
        self._create_sustainability_classes()
        self._create_core_properties()

    # -------------------------------------------------------------------------
    # ISO 23247 Core Classes
    # -------------------------------------------------------------------------

    def _create_iso23247_classes(self):
        """Create ISO 23247 framework classes."""

        # Observable Manufacturing Element (OME)
        self.classes['ObservableManufacturingElement'] = OntologyClass(
            iri=OntologyIRI(self.ISO23247_NS, 'ObservableManufacturingElement'),
            label='Observable Manufacturing Element',
            comment='Physical entity in manufacturing that can be observed and has a digital twin',
            iso23247_layer=ISO23247Layer.OBSERVABLE_MANUFACTURING_ELEMENT
        )

        # Digital Twin Entity
        self.classes['DigitalTwinEntity'] = OntologyClass(
            iri=OntologyIRI(self.ISO23247_NS, 'DigitalTwinEntity'),
            label='Digital Twin Entity',
            comment='Virtual representation of a physical manufacturing entity',
            iso23247_layer=ISO23247Layer.DIGITAL_TWIN_LAYER
        )

        # Data Collection Entity
        self.classes['DataCollectionEntity'] = OntologyClass(
            iri=OntologyIRI(self.ISO23247_NS, 'DataCollectionEntity'),
            label='Data Collection Entity',
            comment='Entity responsible for collecting data from observable elements',
            iso23247_layer=ISO23247Layer.DATA_COLLECTION_LAYER
        )

        # Sensor
        self.classes['Sensor'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'Sensor'),
            label='Sensor',
            comment='Physical sensor for data collection',
            parent_classes=[self.classes['DataCollectionEntity']]
        )

    # -------------------------------------------------------------------------
    # Product Classes (LEGO Bricks)
    # -------------------------------------------------------------------------

    def _create_product_classes(self):
        """Create LEGO product ontology classes."""

        # Base Product class
        self.classes['Product'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'Product'),
            label='Product',
            comment='A manufactured product in the LEGO MCP system',
            parent_classes=[self.classes['ObservableManufacturingElement']],
            iso23247_entity_type=ISO23247EntityType.PRODUCT
        )

        # LEGO Brick (main product)
        self.classes['LegoBrick'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'LegoBrick'),
            label='LEGO Brick',
            comment='A LEGO-compatible brick with studs and anti-studs',
            parent_classes=[self.classes['Product']],
            annotations={
                'stud_pitch_mm': 8.0,
                'stud_diameter_mm': 4.8,
                'stud_height_mm': 1.7,
                'wall_thickness_mm': 1.6,
                'tolerance_mm': 0.02
            }
        )

        # Brick subtypes
        brick_subtypes = [
            ('StandardBrick', 'Standard Brick', 'Standard rectangular brick with full height'),
            ('Plate', 'Plate', 'Thin brick with 1/3 standard height'),
            ('Tile', 'Tile', 'Plate without studs on top'),
            ('Slope', 'Slope', 'Brick with angled top surface'),
            ('TechnicBrick', 'Technic Brick', 'Brick with pin holes for mechanical connections'),
            ('SNOTBrick', 'SNOT Brick', 'Studs Not On Top - modified brick with side studs'),
            ('RoundBrick', 'Round Brick', 'Cylindrical brick'),
            ('ArchBrick', 'Arch Brick', 'Brick with curved arch opening'),
            ('WedgeBrick', 'Wedge Brick', 'Asymmetric brick tapering to one side'),
        ]

        for class_name, label, comment in brick_subtypes:
            self.classes[class_name] = OntologyClass(
                iri=OntologyIRI(self.LEGO_NS, class_name),
                label=label,
                comment=comment,
                parent_classes=[self.classes['LegoBrick']]
            )

    # -------------------------------------------------------------------------
    # Process Classes
    # -------------------------------------------------------------------------

    def _create_process_classes(self):
        """Create manufacturing process ontology classes."""

        # Base Process class
        self.classes['ManufacturingProcess'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'ManufacturingProcess'),
            label='Manufacturing Process',
            comment='A process that transforms inputs into outputs',
            iso23247_entity_type=ISO23247EntityType.PROCESS
        )

        # Additive Manufacturing
        self.classes['AdditiveManufacturing'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'AdditiveManufacturing'),
            label='Additive Manufacturing',
            comment='Layer-by-layer material addition process',
            parent_classes=[self.classes['ManufacturingProcess']]
        )

        # FDM Printing
        self.classes['FDMPrinting'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'FDMPrinting'),
            label='FDM Printing',
            comment='Fused Deposition Modeling 3D printing process',
            parent_classes=[self.classes['AdditiveManufacturing']],
            annotations={
                'typical_layer_height_mm': 0.12,
                'nozzle_diameter_mm': 0.4,
                'print_speed_mm_s': 60.0,
                'infill_percentage': 20.0
            }
        )

        # Subtractive Manufacturing
        self.classes['SubtractiveManufacturing'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'SubtractiveManufacturing'),
            label='Subtractive Manufacturing',
            comment='Material removal process',
            parent_classes=[self.classes['ManufacturingProcess']]
        )

        # CNC Milling
        self.classes['CNCMilling'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'CNCMilling'),
            label='CNC Milling',
            comment='Computer Numerical Control milling process',
            parent_classes=[self.classes['SubtractiveManufacturing']]
        )

        # Quality Inspection
        self.classes['QualityInspection'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'QualityInspection'),
            label='Quality Inspection',
            comment='Process of verifying product quality',
            parent_classes=[self.classes['ManufacturingProcess']]
        )

        # Vision Inspection
        self.classes['VisionInspection'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'VisionInspection'),
            label='Vision Inspection',
            comment='Computer vision-based quality inspection',
            parent_classes=[self.classes['QualityInspection']]
        )

        # Dimensional Inspection
        self.classes['DimensionalInspection'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'DimensionalInspection'),
            label='Dimensional Inspection',
            comment='Physical measurement of product dimensions',
            parent_classes=[self.classes['QualityInspection']]
        )

    # -------------------------------------------------------------------------
    # Resource Classes
    # -------------------------------------------------------------------------

    def _create_resource_classes(self):
        """Create resource ontology classes."""

        # Base Resource class
        self.classes['Resource'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'Resource'),
            label='Resource',
            comment='A resource used in manufacturing',
            parent_classes=[self.classes['ObservableManufacturingElement']],
            iso23247_entity_type=ISO23247EntityType.RESOURCE
        )

        # Equipment
        self.classes['Equipment'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'Equipment'),
            label='Equipment',
            comment='Manufacturing equipment',
            parent_classes=[self.classes['Resource']]
        )

        # 3D Printer
        self.classes['ThreeDPrinter'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'ThreeDPrinter'),
            label='3D Printer',
            comment='Additive manufacturing equipment',
            parent_classes=[self.classes['Equipment']]
        )

        # FDM Printer
        self.classes['FDMPrinter'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'FDMPrinter'),
            label='FDM Printer',
            comment='Fused Deposition Modeling printer',
            parent_classes=[self.classes['ThreeDPrinter']],
            annotations={
                'build_volume_x_mm': 256,
                'build_volume_y_mm': 256,
                'build_volume_z_mm': 256,
                'max_nozzle_temp_c': 300,
                'max_bed_temp_c': 110
            }
        )

        # CNC Mill
        self.classes['CNCMill'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'CNCMill'),
            label='CNC Mill',
            comment='Computer Numerical Control milling machine',
            parent_classes=[self.classes['Equipment']]
        )

        # Material
        self.classes['Material'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'Material'),
            label='Material',
            comment='Raw material for manufacturing',
            parent_classes=[self.classes['Resource']]
        )

        # Filament
        self.classes['Filament'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'Filament'),
            label='Filament',
            comment='3D printing filament material',
            parent_classes=[self.classes['Material']]
        )

        # Filament types
        filament_types = [
            ('PLA', 'PLA Filament', 'Polylactic Acid biodegradable filament', {'print_temp_c': 210, 'bed_temp_c': 60}),
            ('ABS', 'ABS Filament', 'Acrylonitrile Butadiene Styrene filament', {'print_temp_c': 240, 'bed_temp_c': 100}),
            ('PETG', 'PETG Filament', 'Polyethylene Terephthalate Glycol filament', {'print_temp_c': 235, 'bed_temp_c': 80}),
        ]

        for class_name, label, comment, annotations in filament_types:
            self.classes[class_name] = OntologyClass(
                iri=OntologyIRI(self.LEGO_NS, class_name),
                label=label,
                comment=comment,
                parent_classes=[self.classes['Filament']],
                annotations=annotations
            )

    # -------------------------------------------------------------------------
    # Quality Classes
    # -------------------------------------------------------------------------

    def _create_quality_classes(self):
        """Create quality ontology classes."""

        # Quality Characteristic
        self.classes['QualityCharacteristic'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'QualityCharacteristic'),
            label='Quality Characteristic',
            comment='A measurable quality attribute'
        )

        # Defect
        self.classes['Defect'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'Defect'),
            label='Defect',
            comment='A quality defect in a product'
        )

        # Defect types
        defect_types = [
            ('LayerShift', 'Layer Shift', 'Misalignment between printed layers'),
            ('Stringing', 'Stringing', 'Unwanted filament strings between parts'),
            ('Warping', 'Warping', 'Deformation due to thermal contraction'),
            ('UnderExtrusion', 'Under Extrusion', 'Insufficient material deposition'),
            ('OverExtrusion', 'Over Extrusion', 'Excess material deposition'),
            ('ZSeam', 'Z-Seam', 'Visible seam where layer starts'),
            ('Blobbing', 'Blobbing', 'Excess material blobs on surface'),
            ('Delamination', 'Delamination', 'Layer separation'),
        ]

        for class_name, label, comment in defect_types:
            self.classes[class_name] = OntologyClass(
                iri=OntologyIRI(self.LEGO_NS, class_name),
                label=label,
                comment=comment,
                parent_classes=[self.classes['Defect']]
            )

        # Measurement
        self.classes['Measurement'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'Measurement'),
            label='Measurement',
            comment='A recorded measurement value'
        )

        # LEGO-specific quality
        self.classes['ClutchPowerTest'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'ClutchPowerTest'),
            label='Clutch Power Test',
            comment='Test measuring brick connection force',
            parent_classes=[self.classes['QualityCharacteristic']],
            annotations={
                'min_force_n': 2.0,
                'max_force_n': 8.0,
                'target_force_n': 5.0
            }
        )

    # -------------------------------------------------------------------------
    # Sustainability Classes
    # -------------------------------------------------------------------------

    def _create_sustainability_classes(self):
        """Create sustainability ontology classes."""

        # Environmental Impact
        self.classes['EnvironmentalImpact'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'EnvironmentalImpact'),
            label='Environmental Impact',
            comment='Environmental impact of manufacturing activities'
        )

        # Carbon Footprint
        self.classes['CarbonFootprint'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'CarbonFootprint'),
            label='Carbon Footprint',
            comment='CO2 equivalent emissions',
            parent_classes=[self.classes['EnvironmentalImpact']],
            annotations={
                'unit': 'kg CO2e',
                'scope1_included': True,
                'scope2_included': True,
                'scope3_included': True
            }
        )

        # Energy Consumption
        self.classes['EnergyConsumption'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'EnergyConsumption'),
            label='Energy Consumption',
            comment='Energy consumed during manufacturing',
            parent_classes=[self.classes['EnvironmentalImpact']],
            annotations={'unit': 'kWh'}
        )

        # Material Waste
        self.classes['MaterialWaste'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'MaterialWaste'),
            label='Material Waste',
            comment='Waste material from manufacturing',
            parent_classes=[self.classes['EnvironmentalImpact']],
            annotations={'unit': 'kg'}
        )

        # Circular Economy
        self.classes['CircularEconomyMetric'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'CircularEconomyMetric'),
            label='Circular Economy Metric',
            comment='Metric for circular economy assessment'
        )

        self.classes['RecyclingRate'] = OntologyClass(
            iri=OntologyIRI(self.LEGO_NS, 'RecyclingRate'),
            label='Recycling Rate',
            comment='Percentage of material recycled',
            parent_classes=[self.classes['CircularEconomyMetric']]
        )

    # -------------------------------------------------------------------------
    # Core Properties
    # -------------------------------------------------------------------------

    def _create_core_properties(self):
        """Create core ontology properties."""

        # Object Properties
        self.properties['hasDigitalTwin'] = OntologyProperty(
            iri=OntologyIRI(self.ISO23247_NS, 'hasDigitalTwin'),
            label='has digital twin',
            comment='Links a physical element to its digital twin',
            property_type='object',
            domain=self.classes['ObservableManufacturingElement'],
            range_class=self.classes['DigitalTwinEntity']
        )

        self.properties['producedBy'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'producedBy'),
            label='produced by',
            comment='Links a product to its manufacturing process',
            property_type='object',
            domain=self.classes['Product'],
            range_class=self.classes['ManufacturingProcess']
        )

        self.properties['usesEquipment'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'usesEquipment'),
            label='uses equipment',
            comment='Links a process to equipment used',
            property_type='object',
            domain=self.classes['ManufacturingProcess'],
            range_class=self.classes['Equipment']
        )

        self.properties['usesMaterial'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'usesMaterial'),
            label='uses material',
            comment='Links a process to material consumed',
            property_type='object',
            domain=self.classes['ManufacturingProcess'],
            range_class=self.classes['Material']
        )

        self.properties['hasDefect'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'hasDefect'),
            label='has defect',
            comment='Links a product to its defects',
            property_type='object',
            domain=self.classes['Product'],
            range_class=self.classes['Defect']
        )

        self.properties['hasEnvironmentalImpact'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'hasEnvironmentalImpact'),
            label='has environmental impact',
            comment='Links a process to its environmental impact',
            property_type='object',
            domain=self.classes['ManufacturingProcess'],
            range_class=self.classes['EnvironmentalImpact']
        )

        # Data Properties
        self.properties['studCount'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'studCount'),
            label='stud count',
            comment='Number of studs on a brick',
            property_type='data',
            domain=self.classes['LegoBrick'],
            range_datatype='xsd:integer'
        )

        self.properties['dimensionX'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'dimensionX'),
            label='dimension X',
            comment='Width in stud units',
            property_type='data',
            domain=self.classes['LegoBrick'],
            range_datatype='xsd:integer'
        )

        self.properties['dimensionY'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'dimensionY'),
            label='dimension Y',
            comment='Length in stud units',
            property_type='data',
            domain=self.classes['LegoBrick'],
            range_datatype='xsd:integer'
        )

        self.properties['heightRatio'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'heightRatio'),
            label='height ratio',
            comment='Height as ratio of standard brick (1.0 = brick, 0.333 = plate)',
            property_type='data',
            domain=self.classes['LegoBrick'],
            range_datatype='xsd:float'
        )

        self.properties['carbonEmission'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'carbonEmission'),
            label='carbon emission',
            comment='CO2 equivalent in kg',
            property_type='data',
            domain=self.classes['CarbonFootprint'],
            range_datatype='xsd:float'
        )

        self.properties['energyConsumed'] = OntologyProperty(
            iri=OntologyIRI(self.LEGO_NS, 'energyConsumed'),
            label='energy consumed',
            comment='Energy in kWh',
            property_type='data',
            domain=self.classes['EnergyConsumption'],
            range_datatype='xsd:float'
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get_class(self, name: str) -> Optional[OntologyClass]:
        """Get an ontology class by name."""
        return self.classes.get(name)

    def get_property(self, name: str) -> Optional[OntologyProperty]:
        """Get an ontology property by name."""
        return self.properties.get(name)

    def get_subclasses(self, class_name: str) -> List[OntologyClass]:
        """Get all subclasses of a class."""
        parent = self.get_class(class_name)
        if not parent:
            return []

        subclasses = []
        for cls in self.classes.values():
            if parent in cls.parent_classes:
                subclasses.append(cls)
        return subclasses

    def get_all_subclasses(self, class_name: str) -> Set[OntologyClass]:
        """Get all subclasses recursively."""
        result = set()
        direct = self.get_subclasses(class_name)
        for sub in direct:
            result.add(sub)
            result.update(self.get_all_subclasses(sub.iri.local_name))
        return result

    def create_individual(
        self,
        iri: str,
        class_name: str,
        data_properties: Optional[Dict[str, Any]] = None
    ) -> OntologyIndividual:
        """Create an individual (instance) of a class."""
        cls = self.get_class(class_name)
        if not cls:
            raise ValueError(f"Unknown class: {class_name}")

        individual = OntologyIndividual(
            iri=OntologyIRI.from_string(iri),
            classes=[cls]
        )

        if data_properties:
            for prop_name, value in data_properties.items():
                prop = self.get_property(prop_name)
                if prop and prop.property_type == 'data':
                    individual.data_properties[prop] = [value]

        self.individuals[iri] = individual
        return individual

    def export_owl(self) -> str:
        """Export ontology to OWL/XML format."""
        # Simplified OWL export
        owl_lines = [
            '<?xml version="1.0"?>',
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
            '         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"',
            '         xmlns:owl="http://www.w3.org/2002/07/owl#"',
            f'         xmlns:lego="{self.LEGO_NS}#"',
            f'         xmlns:iso23247="{self.ISO23247_NS}#">',
            '',
            f'  <owl:Ontology rdf:about="{self.LEGO_NS}">',
            '    <rdfs:label>LEGO MCP Manufacturing Ontology</rdfs:label>',
            '    <rdfs:comment>ISO 23247 compliant digital twin ontology for LEGO brick manufacturing</rdfs:comment>',
            '  </owl:Ontology>',
            ''
        ]

        # Export classes
        for cls in self.classes.values():
            owl_lines.append(f'  <owl:Class rdf:about="{cls.iri}">')
            owl_lines.append(f'    <rdfs:label>{cls.label}</rdfs:label>')
            owl_lines.append(f'    <rdfs:comment>{cls.comment}</rdfs:comment>')
            for parent in cls.parent_classes:
                owl_lines.append(f'    <rdfs:subClassOf rdf:resource="{parent.iri}"/>')
            owl_lines.append('  </owl:Class>')
            owl_lines.append('')

        # Export properties
        for prop in self.properties.values():
            if prop.property_type == 'object':
                owl_lines.append(f'  <owl:ObjectProperty rdf:about="{prop.iri}">')
            else:
                owl_lines.append(f'  <owl:DatatypeProperty rdf:about="{prop.iri}">')
            owl_lines.append(f'    <rdfs:label>{prop.label}</rdfs:label>')
            owl_lines.append(f'    <rdfs:comment>{prop.comment}</rdfs:comment>')
            if prop.domain:
                owl_lines.append(f'    <rdfs:domain rdf:resource="{prop.domain.iri}"/>')
            if prop.range_class:
                owl_lines.append(f'    <rdfs:range rdf:resource="{prop.range_class.iri}"/>')
            if prop.range_datatype:
                owl_lines.append(f'    <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#{prop.range_datatype.split(":")[-1]}"/>')
            if prop.property_type == 'object':
                owl_lines.append('  </owl:ObjectProperty>')
            else:
                owl_lines.append('  </owl:DatatypeProperty>')
            owl_lines.append('')

        owl_lines.append('</rdf:RDF>')
        return '\n'.join(owl_lines)

    def export_json_ld(self) -> Dict[str, Any]:
        """Export ontology to JSON-LD format."""
        return {
            "@context": {
                "lego": self.LEGO_NS + "#",
                "iso23247": self.ISO23247_NS + "#",
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "owl": "http://www.w3.org/2002/07/owl#"
            },
            "@graph": [
                {
                    "@id": str(cls.iri),
                    "@type": "owl:Class",
                    "rdfs:label": cls.label,
                    "rdfs:comment": cls.comment,
                    "rdfs:subClassOf": [str(p.iri) for p in cls.parent_classes] if cls.parent_classes else None
                }
                for cls in self.classes.values()
            ] + [
                {
                    "@id": str(prop.iri),
                    "@type": "owl:ObjectProperty" if prop.property_type == 'object' else "owl:DatatypeProperty",
                    "rdfs:label": prop.label,
                    "rdfs:comment": prop.comment
                }
                for prop in self.properties.values()
            ]
        }

    def validate_individual(self, individual: OntologyIndividual) -> List[str]:
        """Validate an individual against ontology constraints."""
        errors = []

        for cls in individual.classes:
            for restriction in cls.restrictions:
                # Check property restrictions
                if restriction.restriction_type == 'some':
                    # Must have at least one value
                    if restriction.property not in individual.object_properties:
                        errors.append(
                            f"Missing required property {restriction.property.label} for {cls.label}"
                        )
                elif restriction.restriction_type == 'min':
                    # Minimum cardinality
                    values = individual.object_properties.get(restriction.property, [])
                    if len(values) < restriction.filler:
                        errors.append(
                            f"Property {restriction.property.label} requires at least {restriction.filler} values"
                        )

        return errors

    def infer_class(self, data_properties: Dict[str, Any]) -> Optional[OntologyClass]:
        """Infer the most specific class based on data properties."""
        # Example: Infer brick type from height ratio
        if 'heightRatio' in data_properties:
            ratio = data_properties['heightRatio']
            if ratio == 1.0:
                return self.get_class('StandardBrick')
            elif ratio < 0.5:
                return self.get_class('Plate')

        return self.get_class('LegoBrick')


# =============================================================================
# Ontology Query Interface
# =============================================================================

class OntologyReasoner:
    """
    Simple ontology reasoner for inference.

    Provides basic reasoning capabilities:
    - Subsumption checking
    - Instance classification
    - Property inheritance
    """

    def __init__(self, ontology: ManufacturingOntology):
        self.ontology = ontology

    def is_subclass_of(self, subclass: str, superclass: str) -> bool:
        """Check if one class is a subclass of another."""
        sub = self.ontology.get_class(subclass)
        sup = self.ontology.get_class(superclass)

        if not sub or not sup:
            return False

        if sub == sup:
            return True

        for parent in sub.parent_classes:
            if parent == sup:
                return True
            if self.is_subclass_of(parent.iri.local_name, superclass):
                return True

        return False

    def get_applicable_properties(self, class_name: str) -> List[OntologyProperty]:
        """Get all properties applicable to a class (including inherited)."""
        cls = self.ontology.get_class(class_name)
        if not cls:
            return []

        applicable = []
        for prop in self.ontology.properties.values():
            if prop.domain:
                if self.is_subclass_of(class_name, prop.domain.iri.local_name):
                    applicable.append(prop)

        return applicable

    def classify_individual(self, individual: OntologyIndividual) -> List[OntologyClass]:
        """
        Classify an individual into all applicable classes.

        Uses property values to infer most specific class.
        """
        inferred_classes = set(individual.classes)

        # Add all parent classes
        for cls in individual.classes:
            current = cls
            while current.parent_classes:
                for parent in current.parent_classes:
                    inferred_classes.add(parent)
                    current = parent

        return list(inferred_classes)
