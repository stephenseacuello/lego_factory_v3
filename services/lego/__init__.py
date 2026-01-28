"""
LEGO Factory v3 - LEGO Services
===============================
Services for LEGO brick design, catalog, slicing, and manufacturing.
"""

from services.lego.lego_specs import (
    LEGO,
    LegoStandard,
    ManufacturingProcess,
    WorkCenterType,
    MANUFACTURING_TOLERANCES,
    MATERIAL_PROPERTIES,
    BRICK_TYPES,
    COMMON_BRICKS,
    brick_dimensions,
    brick_dimensions_with_clearance,
    stud_positions,
    tube_positions,
    calculate_volume,
    calculate_weight,
)

from services.lego.brick_catalog import (
    BrickCategory,
    StudType,
    BottomType,
    BrickDefinition,
    BRICK_CATALOG,
    get_brick,
    search_bricks,
    list_categories,
    list_tags,
    get_catalog_stats,
)

from services.lego.slicer_client import (
    SlicerClient,
    SlicerEngine,
    JobStatus,
    ModelAnalysis,
    SliceJob,
    SliceResult,
    SlicerServiceError,
    get_slicer_client,
)

__all__ = [
    # Specs
    'LEGO',
    'LegoStandard',
    'ManufacturingProcess',
    'WorkCenterType',
    'MANUFACTURING_TOLERANCES',
    'MATERIAL_PROPERTIES',
    'BRICK_TYPES',
    'COMMON_BRICKS',
    'brick_dimensions',
    'brick_dimensions_with_clearance',
    'stud_positions',
    'tube_positions',
    'calculate_volume',
    'calculate_weight',
    # Catalog
    'BrickCategory',
    'StudType',
    'BottomType',
    'BrickDefinition',
    'BRICK_CATALOG',
    'get_brick',
    'search_bricks',
    'list_categories',
    'list_tags',
    'get_catalog_stats',
    # Slicer
    'SlicerClient',
    'SlicerEngine',
    'JobStatus',
    'ModelAnalysis',
    'SliceJob',
    'SliceResult',
    'SlicerServiceError',
    'get_slicer_client',
]
