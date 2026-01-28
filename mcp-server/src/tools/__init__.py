"""
LEGO MCP Tools Package

This package contains all MCP tool definitions and handlers:
- brick_tools: Brick creation and catalog browsing
- export_tools: STL, STEP, 3MF export
- milling_tools: CNC machining operations
- printing_tools: 3D printing G-code generation
"""

from .brick_tools import (
    BRICK_TOOLS,
    list_brick_catalog,
    get_brick_details,
    create_custom_brick,
    create_standard_brick,
    create_plate_brick,
    create_tile_brick,
    create_slope_brick_helper,
    create_technic_brick_helper,
    get_full_catalog_stats,
)

from .export_tools import (
    EXPORT_TOOLS,
    export_stl,
    export_step,
    export_3mf,
    export_batch,
    list_export_formats,
)

from .milling_tools import (
    MILLING_TOOLS,
    generate_brick_operations,
    calculate_speeds_feeds,
    list_machines,
    list_tools,
    LEGO_TOOL_LIBRARY,
    MACHINES,
)

from .printing_tools import (
    PRINTING_TOOLS,
    generate_print_config,
    estimate_print_time,
    create_batch_print_job,
    list_printers,
    list_materials,
    get_lego_print_settings,
    PRINTER_LIBRARY,
    MATERIAL_LIBRARY,
    QUALITY_PRESETS,
)

# Combine all tool definitions
ALL_TOOLS = {}
ALL_TOOLS.update(BRICK_TOOLS)
ALL_TOOLS.update(EXPORT_TOOLS)
ALL_TOOLS.update(MILLING_TOOLS)
ALL_TOOLS.update(PRINTING_TOOLS)
