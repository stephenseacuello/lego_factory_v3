"""
Export Tools - STL, STEP, 3MF Export Functionality

Handles all CAD file export operations with multiple format support.
"""

from typing import Dict, Any, List, Optional
import os
import json
from datetime import datetime


# ============================================================================
# EXPORT FORMATS
# ============================================================================

EXPORT_FORMATS = {
    "stl": {
        "extension": ".stl",
        "name": "STL (Stereolithography)",
        "description": "Standard 3D printing format",
        "options": {
            "binary": True,  # Binary vs ASCII
            "refinement": "medium",  # low, medium, high, ultra
        },
    },
    "step": {
        "extension": ".step",
        "name": "STEP (Standard for Exchange of Product Data)",
        "description": "CAD exchange format, preserves geometry",
        "options": {},
    },
    "3mf": {
        "extension": ".3mf",
        "name": "3MF (3D Manufacturing Format)",
        "description": "Modern 3D printing format with metadata",
        "options": {
            "include_materials": True,
            "include_colors": True,
        },
    },
    "obj": {
        "extension": ".obj",
        "name": "OBJ (Wavefront)",
        "description": "Universal 3D format",
        "options": {
            "include_mtl": True,
        },
    },
    "iges": {
        "extension": ".iges",
        "name": "IGES (Initial Graphics Exchange Specification)",
        "description": "Legacy CAD exchange format",
        "options": {},
    },
    "f3d": {
        "extension": ".f3d",
        "name": "Fusion 360 Archive",
        "description": "Native Fusion 360 format with full history",
        "options": {},
    },
}

# Refinement level mappings for STL
STL_REFINEMENT = {
    "low": {
        "surface_deviation": 0.1,  # mm
        "normal_deviation": 30,  # degrees
        "max_edge_length": 2.0,  # mm
        "aspect_ratio": 10.0,
    },
    "medium": {
        "surface_deviation": 0.05,
        "normal_deviation": 15,
        "max_edge_length": 1.0,
        "aspect_ratio": 5.0,
    },
    "high": {
        "surface_deviation": 0.02,
        "normal_deviation": 10,
        "max_edge_length": 0.5,
        "aspect_ratio": 3.0,
    },
    "ultra": {
        "surface_deviation": 0.01,
        "normal_deviation": 5,
        "max_edge_length": 0.25,
        "aspect_ratio": 2.0,
    },
}


# ============================================================================
# EXPORT FUNCTIONS
# ============================================================================


def export_stl(
    component_name: str, output_path: str, refinement: str = "medium", binary: bool = True
) -> Dict[str, Any]:
    """
    Export a component to STL format.

    Args:
        component_name: Name of the Fusion 360 component to export
        output_path: Full path for output file
        refinement: Quality level (low, medium, high, ultra)
        binary: True for binary STL, False for ASCII

    Returns:
        Export result with file info
    """
    if refinement not in STL_REFINEMENT:
        refinement = "medium"

    settings = STL_REFINEMENT[refinement]

    return {
        "action": "export_stl",
        "component": component_name,
        "output_path": output_path,
        "format": "stl",
        "settings": {
            "binary": binary,
            "surface_deviation": settings["surface_deviation"],
            "normal_deviation": settings["normal_deviation"],
            "max_edge_length": settings["max_edge_length"],
            "aspect_ratio": settings["aspect_ratio"],
        },
    }


def export_step(component_name: str, output_path: str) -> Dict[str, Any]:
    """
    Export a component to STEP format.

    Args:
        component_name: Name of the component
        output_path: Full path for output file

    Returns:
        Export result
    """
    return {
        "action": "export_step",
        "component": component_name,
        "output_path": output_path,
        "format": "step",
        "settings": {},
    }


def export_3mf(
    component_name: str,
    output_path: str,
    include_materials: bool = True,
    include_colors: bool = True,
) -> Dict[str, Any]:
    """
    Export to 3MF format with optional metadata.

    Args:
        component_name: Name of the component
        output_path: Full path for output file
        include_materials: Include material definitions
        include_colors: Include color information

    Returns:
        Export result
    """
    return {
        "action": "export_3mf",
        "component": component_name,
        "output_path": output_path,
        "format": "3mf",
        "settings": {"include_materials": include_materials, "include_colors": include_colors},
    }


def export_obj(component_name: str, output_path: str, include_mtl: bool = True) -> Dict[str, Any]:
    """
    Export to OBJ format.

    Args:
        component_name: Name of the component
        output_path: Full path for output file
        include_mtl: Include material library file

    Returns:
        Export result
    """
    return {
        "action": "export_obj",
        "component": component_name,
        "output_path": output_path,
        "format": "obj",
        "settings": {"include_mtl": include_mtl},
    }


def export_batch(
    components: List[str], output_dir: str, formats: List[str] = ["stl"]
) -> Dict[str, Any]:
    """
    Export multiple components in multiple formats.

    Args:
        components: List of component names
        output_dir: Output directory
        formats: List of format names (stl, step, 3mf, obj)

    Returns:
        Batch export results
    """
    exports = []

    for component in components:
        for fmt in formats:
            if fmt not in EXPORT_FORMATS:
                continue

            ext = EXPORT_FORMATS[fmt]["extension"]
            filename = f"{component}{ext}"
            output_path = os.path.join(output_dir, filename)

            exports.append({"component": component, "format": fmt, "output_path": output_path})

    return {"action": "export_batch", "exports": exports, "total": len(exports)}


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

EXPORT_TOOLS = {
    "export_stl": {
        "description": """Export a LEGO brick to STL format for 3D printing.

Quality levels:
- low: Fast export, suitable for previews
- medium: Good balance of quality and file size (default)
- high: High detail for final prints
- ultra: Maximum detail for precision printing""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_name": {
                    "type": "string",
                    "description": "Name of the brick component to export",
                },
                "output_path": {"type": "string", "description": "Full path for output STL file"},
                "refinement": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "ultra"],
                    "default": "medium",
                    "description": "Mesh quality level",
                },
                "binary": {
                    "type": "boolean",
                    "default": True,
                    "description": "Use binary format (smaller files)",
                },
            },
            "required": ["component_name", "output_path"],
        },
    },
    "export_step": {
        "description": "Export to STEP format for CAD interchange. Preserves exact geometry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_name": {
                    "type": "string",
                    "description": "Name of the component to export",
                },
                "output_path": {"type": "string", "description": "Full path for output STEP file"},
            },
            "required": ["component_name", "output_path"],
        },
    },
    "export_3mf": {
        "description": "Export to 3MF format with full material and color support.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "component_name": {
                    "type": "string",
                    "description": "Name of the component to export",
                },
                "output_path": {"type": "string", "description": "Full path for output 3MF file"},
                "include_materials": {"type": "boolean", "default": True},
                "include_colors": {"type": "boolean", "default": True},
            },
            "required": ["component_name", "output_path"],
        },
    },
    "export_batch": {
        "description": "Export multiple bricks in multiple formats at once.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of component names to export",
                },
                "output_dir": {"type": "string", "description": "Output directory for all exports"},
                "formats": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["stl", "step", "3mf", "obj"]},
                    "default": ["stl"],
                    "description": "List of formats to export",
                },
            },
            "required": ["components", "output_dir"],
        },
    },
    "list_export_formats": {
        "description": "List all available export formats and their options.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}


def list_export_formats() -> Dict[str, Any]:
    """List all available export formats."""
    return {"formats": EXPORT_FORMATS, "stl_refinement_levels": list(STL_REFINEMENT.keys())}
