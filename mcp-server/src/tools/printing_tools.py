"""
3D Printing Tools - Slicing and G-code Generation

Complete 3D printing functionality for LEGO brick manufacturing.
Supports multiple slicers, printers, materials, and quality presets.
"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
import os
import json


# ============================================================================
# ENUMS
# ============================================================================


class SlicerType(Enum):
    """Supported slicer software."""

    PRUSASLICER = "prusaslicer"
    CURA = "cura"
    ORCASLICER = "orcaslicer"
    SUPERSLICER = "superslicer"
    BAMBU_STUDIO = "bambu_studio"
    SIMPLIFY3D = "simplify3d"


class MaterialType(Enum):
    """Filament material types."""

    PLA = "pla"
    PETG = "petg"
    ABS = "abs"
    ASA = "asa"
    TPU = "tpu"
    NYLON = "nylon"
    PC = "polycarbonate"
    PLA_CF = "pla_cf"
    PETG_CF = "petg_cf"


class QualityPreset(Enum):
    """Print quality presets."""

    DRAFT = "draft"  # Fast, low quality (0.3mm)
    NORMAL = "normal"  # Standard quality (0.2mm)
    QUALITY = "quality"  # High quality (0.15mm)
    ULTRA = "ultra"  # Ultra quality (0.1mm)
    LEGO_OPTIMAL = "lego"  # Optimized for LEGO fit (0.12mm)


# ============================================================================
# PRINTER DEFINITIONS
# ============================================================================


@dataclass
class PrinterProfile:
    """3D printer profile."""

    name: str
    manufacturer: str
    model: str

    # Build volume (mm)
    bed_x: float
    bed_y: float
    bed_z: float
    bed_shape: str = "rectangular"  # rectangular, circular

    # Nozzle
    nozzle_diameter: float = 0.4

    # Heated bed
    has_heated_bed: bool = True
    max_bed_temp: int = 110

    # Enclosure
    has_enclosure: bool = False

    # Features
    has_abl: bool = True  # Auto bed leveling
    has_direct_drive: bool = False
    has_dual_extruder: bool = False

    # Speed limits (mm/s)
    max_print_speed: int = 200
    max_travel_speed: int = 300

    # Filament diameter
    filament_diameter: float = 1.75


# Printer library
PRINTER_LIBRARY = {
    "prusa_mk3s": PrinterProfile(
        "Prusa MK3S+",
        "Prusa Research",
        "MK3S+",
        250,
        210,
        210,
        has_abl=True,
        has_direct_drive=False,
        max_print_speed=200,
    ),
    "prusa_mk4": PrinterProfile(
        "Prusa MK4",
        "Prusa Research",
        "MK4",
        250,
        210,
        220,
        has_abl=True,
        has_direct_drive=True,
        max_print_speed=300,
    ),
    "prusa_xl": PrinterProfile(
        "Prusa XL",
        "Prusa Research",
        "XL",
        360,
        360,
        360,
        has_abl=True,
        has_direct_drive=True,
        max_print_speed=350,
    ),
    "ender3_v2": PrinterProfile(
        "Ender 3 V2",
        "Creality",
        "Ender 3 V2",
        220,
        220,
        250,
        has_abl=False,
        has_direct_drive=False,
        max_print_speed=150,
    ),
    "ender3_s1": PrinterProfile(
        "Ender 3 S1",
        "Creality",
        "Ender 3 S1",
        220,
        220,
        270,
        has_abl=True,
        has_direct_drive=True,
        max_print_speed=200,
    ),
    "bambu_x1c": PrinterProfile(
        "Bambu Lab X1 Carbon",
        "Bambu Lab",
        "X1 Carbon",
        256,
        256,
        256,
        has_abl=True,
        has_direct_drive=True,
        has_enclosure=True,
        max_print_speed=500,
    ),
    "bambu_p1s": PrinterProfile(
        "Bambu Lab P1S",
        "Bambu Lab",
        "P1S",
        256,
        256,
        256,
        has_abl=True,
        has_direct_drive=True,
        has_enclosure=True,
        max_print_speed=500,
    ),
    "bambu_a1": PrinterProfile(
        "Bambu Lab A1",
        "Bambu Lab",
        "A1",
        256,
        256,
        256,
        has_abl=True,
        has_direct_drive=True,
        max_print_speed=400,
    ),
    "voron_2.4": PrinterProfile(
        "Voron 2.4",
        "Voron Design",
        "2.4",
        350,
        350,
        350,
        has_abl=True,
        has_direct_drive=True,
        has_enclosure=True,
        max_print_speed=500,
    ),
    "voron_0.2": PrinterProfile(
        "Voron 0.2",
        "Voron Design",
        "0.2",
        120,
        120,
        120,
        has_abl=True,
        has_direct_drive=True,
        has_enclosure=True,
        max_print_speed=300,
    ),
    "ratrig_vcore3": PrinterProfile(
        "RatRig V-Core 3",
        "RatRig",
        "V-Core 3",
        300,
        300,
        300,
        has_abl=True,
        has_direct_drive=True,
        max_print_speed=400,
    ),
    "anycubic_kobra2": PrinterProfile(
        "Anycubic Kobra 2",
        "Anycubic",
        "Kobra 2",
        220,
        220,
        250,
        has_abl=True,
        has_direct_drive=True,
        max_print_speed=300,
    ),
    "qidi_xmax3": PrinterProfile(
        "QIDI X-Max 3",
        "QIDI Tech",
        "X-Max 3",
        325,
        325,
        315,
        has_abl=True,
        has_direct_drive=True,
        has_enclosure=True,
        max_print_speed=400,
    ),
    "flashforge_adventurer": PrinterProfile(
        "FlashForge Adventurer 5M Pro",
        "FlashForge",
        "Adventurer 5M Pro",
        220,
        220,
        220,
        has_abl=True,
        has_direct_drive=True,
        has_enclosure=True,
        max_print_speed=400,
    ),
}


# ============================================================================
# MATERIAL PROFILES
# ============================================================================


@dataclass
class MaterialProfile:
    """Filament material profile."""

    name: str
    type: MaterialType

    # Temperatures
    nozzle_temp: int
    bed_temp: int

    # Optional temperatures
    nozzle_temp_first_layer: Optional[int] = None
    bed_temp_first_layer: Optional[int] = None

    # Cooling
    min_fan_speed: int = 35
    max_fan_speed: int = 100
    bridge_fan_speed: int = 100
    disable_fan_first_layers: int = 1

    # Retraction
    retract_length: float = 0.8
    retract_speed: int = 35
    retract_lift_z: float = 0.4

    # Flow adjustments
    extrusion_multiplier: float = 1.0

    # Enclosure requirement
    needs_enclosure: bool = False

    # Notes
    notes: str = ""


MATERIAL_LIBRARY = {
    "pla_generic": MaterialProfile(
        "Generic PLA",
        MaterialType.PLA,
        215,
        60,
        nozzle_temp_first_layer=220,
        bed_temp_first_layer=65,
        min_fan_speed=100,
        max_fan_speed=100,
    ),
    "pla_prusament": MaterialProfile(
        "Prusament PLA",
        MaterialType.PLA,
        215,
        60,
        nozzle_temp_first_layer=215,
        bed_temp_first_layer=60,
        min_fan_speed=100,
        max_fan_speed=100,
        notes="High quality PLA with tight tolerances",
    ),
    "petg_generic": MaterialProfile(
        "Generic PETG",
        MaterialType.PETG,
        240,
        85,
        nozzle_temp_first_layer=245,
        bed_temp_first_layer=90,
        min_fan_speed=50,
        max_fan_speed=50,
        retract_length=1.0,
    ),
    "petg_prusament": MaterialProfile(
        "Prusament PETG",
        MaterialType.PETG,
        240,
        85,
        min_fan_speed=30,
        max_fan_speed=50,
        retract_length=1.0,
    ),
    "abs_generic": MaterialProfile(
        "Generic ABS",
        MaterialType.ABS,
        255,
        100,
        nozzle_temp_first_layer=260,
        bed_temp_first_layer=100,
        min_fan_speed=0,
        max_fan_speed=30,
        needs_enclosure=True,
        notes="Requires enclosure to prevent warping",
    ),
    "asa_generic": MaterialProfile(
        "Generic ASA",
        MaterialType.ASA,
        260,
        100,
        min_fan_speed=0,
        max_fan_speed=30,
        needs_enclosure=True,
        notes="UV resistant, good for outdoor use",
    ),
    "tpu_generic": MaterialProfile(
        "Generic TPU",
        MaterialType.TPU,
        230,
        50,
        min_fan_speed=100,
        max_fan_speed=100,
        retract_length=0.4,
        notes="Flexible, reduce speed significantly",
    ),
    "nylon_generic": MaterialProfile(
        "Generic Nylon",
        MaterialType.NYLON,
        260,
        90,
        min_fan_speed=0,
        max_fan_speed=30,
        needs_enclosure=True,
        notes="Hygroscopic - keep dry",
    ),
    "pla_cf": MaterialProfile(
        "PLA-CF (Carbon Fiber)",
        MaterialType.PLA_CF,
        230,
        60,
        min_fan_speed=100,
        max_fan_speed=100,
        notes="Use hardened nozzle",
    ),
    "petg_cf": MaterialProfile(
        "PETG-CF (Carbon Fiber)",
        MaterialType.PETG_CF,
        250,
        85,
        min_fan_speed=30,
        max_fan_speed=50,
        notes="Use hardened nozzle",
    ),
}


# ============================================================================
# QUALITY PRESETS FOR LEGO
# ============================================================================


@dataclass
class QualitySettings:
    """Print quality settings."""

    name: str
    preset: QualityPreset

    # Layer settings
    layer_height: float
    first_layer_height: float

    # Perimeters
    perimeters: int = 3
    top_solid_layers: int = 5
    bottom_solid_layers: int = 4

    # Infill
    infill_density: float = 20
    infill_pattern: str = "grid"  # grid, gyroid, honeycomb, cubic

    # Speed (mm/s)
    print_speed: int = 60
    first_layer_speed: int = 20
    perimeter_speed: int = 45
    infill_speed: int = 80
    travel_speed: int = 150

    # Support
    support_density: float = 15
    support_pattern: str = "grid"


QUALITY_PRESETS = {
    QualityPreset.DRAFT: QualitySettings(
        "Draft",
        QualityPreset.DRAFT,
        0.3,
        0.3,
        perimeters=2,
        top_solid_layers=3,
        bottom_solid_layers=3,
        infill_density=15,
        print_speed=100,
    ),
    QualityPreset.NORMAL: QualitySettings(
        "Normal",
        QualityPreset.NORMAL,
        0.2,
        0.2,
        perimeters=3,
        top_solid_layers=4,
        bottom_solid_layers=4,
        infill_density=20,
        print_speed=60,
    ),
    QualityPreset.QUALITY: QualitySettings(
        "Quality",
        QualityPreset.QUALITY,
        0.15,
        0.2,
        perimeters=3,
        top_solid_layers=5,
        bottom_solid_layers=5,
        infill_density=25,
        print_speed=50,
    ),
    QualityPreset.ULTRA: QualitySettings(
        "Ultra",
        QualityPreset.ULTRA,
        0.1,
        0.15,
        perimeters=4,
        top_solid_layers=6,
        bottom_solid_layers=6,
        infill_density=30,
        print_speed=40,
    ),
    QualityPreset.LEGO_OPTIMAL: QualitySettings(
        "LEGO Optimal",
        QualityPreset.LEGO_OPTIMAL,
        0.12,
        0.2,
        perimeters=3,
        top_solid_layers=6,
        bottom_solid_layers=5,
        infill_density=25,
        infill_pattern="grid",
        print_speed=45,
        perimeter_speed=35,
    ),
}


# ============================================================================
# LEGO-SPECIFIC PRINT SETTINGS
# ============================================================================


def get_lego_print_settings(
    brick_type: str, quality: QualityPreset = QualityPreset.LEGO_OPTIMAL
) -> Dict[str, Any]:
    """
    Get optimized print settings for LEGO bricks.

    Stud fit is critical - settings are tuned for accurate dimensions.
    """
    base_settings = QUALITY_PRESETS.get(quality, QUALITY_PRESETS[QualityPreset.LEGO_OPTIMAL])

    settings = {
        "layer_height": base_settings.layer_height,
        "first_layer_height": base_settings.first_layer_height,
        "perimeters": base_settings.perimeters,
        "top_solid_layers": base_settings.top_solid_layers,
        "bottom_solid_layers": base_settings.bottom_solid_layers,
        "infill_density": base_settings.infill_density,
        "infill_pattern": base_settings.infill_pattern,
        "print_speed": base_settings.print_speed,
        # LEGO-specific overrides
        "external_perimeter_extrusion_width": 0.45,  # Slightly wider for strength
        "perimeter_extrusion_width": 0.45,
        "infill_extrusion_width": 0.45,
        "solid_infill_extrusion_width": 0.45,
        "top_infill_extrusion_width": 0.4,
        # Dimensional accuracy
        "xy_size_compensation": -0.05,  # Slight inward to ensure fit
        "elephant_foot_compensation": 0.1,
        # Seam position for aesthetics
        "seam_position": "rear",
        # Overhangs - studs can be tricky
        "overhangs": True,
        "bridge_speed": 30,
        # Avoid stringing on studs
        "retract_before_travel": True,
        "wipe_before_retract": True,
    }

    # Brick-type specific adjustments
    if brick_type == "technic":
        settings["perimeters"] = 4  # More walls for hole strength
        settings["infill_density"] = 30
    elif brick_type == "slope":
        settings["perimeters"] = 3
        settings["support_enabled"] = True
        settings["support_angle"] = 50
    elif brick_type == "tile":
        settings["top_solid_layers"] = 8  # More top layers for smooth finish
        settings["ironing"] = True

    return settings


# ============================================================================
# SLICING FUNCTIONS
# ============================================================================


def generate_print_config(
    stl_path: str,
    printer: str,
    material: str,
    quality: str = "lego",
    brick_type: str = "standard",
    output_gcode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate complete print configuration for a LEGO brick.

    Args:
        stl_path: Path to STL file
        printer: Printer profile name
        material: Material profile name
        quality: Quality preset name
        brick_type: Type of brick for optimizations
        output_gcode: Output G-code path (optional)

    Returns:
        Complete print configuration
    """
    printer_profile = PRINTER_LIBRARY.get(printer)
    material_profile = MATERIAL_LIBRARY.get(material)

    if not printer_profile:
        return {"error": f"Unknown printer: {printer}"}
    if not material_profile:
        return {"error": f"Unknown material: {material}"}

    # Get quality preset
    quality_enum = QualityPreset.LEGO_OPTIMAL
    for q in QualityPreset:
        if q.value == quality:
            quality_enum = q
            break

    # Get LEGO-specific settings
    lego_settings = get_lego_print_settings(brick_type, quality_enum)
    quality_settings = QUALITY_PRESETS.get(
        quality_enum, QUALITY_PRESETS[QualityPreset.LEGO_OPTIMAL]
    )

    # Check material compatibility
    warnings = []
    if material_profile.needs_enclosure and not printer_profile.has_enclosure:
        warnings.append(f"{material_profile.name} requires an enclosure for best results")

    config = {
        "stl_path": stl_path,
        "output_gcode": output_gcode or stl_path.replace(".stl", ".gcode"),
        "printer": {
            "name": printer_profile.name,
            "bed_size": [printer_profile.bed_x, printer_profile.bed_y, printer_profile.bed_z],
            "nozzle_diameter": printer_profile.nozzle_diameter,
        },
        "material": {
            "name": material_profile.name,
            "type": material_profile.type.value,
            "nozzle_temp": material_profile.nozzle_temp,
            "bed_temp": material_profile.bed_temp,
            "nozzle_temp_first_layer": material_profile.nozzle_temp_first_layer
            or material_profile.nozzle_temp,
            "bed_temp_first_layer": material_profile.bed_temp_first_layer
            or material_profile.bed_temp,
            "fan_speed": {
                "min": material_profile.min_fan_speed,
                "max": material_profile.max_fan_speed,
                "bridge": material_profile.bridge_fan_speed,
            },
            "retraction": {
                "length": material_profile.retract_length,
                "speed": material_profile.retract_speed,
                "lift_z": material_profile.retract_lift_z,
            },
        },
        "quality": {
            "preset": quality_settings.name,
            "layer_height": lego_settings["layer_height"],
            "first_layer_height": lego_settings["first_layer_height"],
            "perimeters": lego_settings["perimeters"],
            "top_layers": lego_settings["top_solid_layers"],
            "bottom_layers": lego_settings["bottom_solid_layers"],
            "infill_density": lego_settings["infill_density"],
            "infill_pattern": lego_settings["infill_pattern"],
        },
        "speeds": {
            "print": quality_settings.print_speed,
            "first_layer": quality_settings.first_layer_speed,
            "perimeter": quality_settings.perimeter_speed,
            "infill": quality_settings.infill_speed,
            "travel": quality_settings.travel_speed,
        },
        "lego_optimizations": {
            "xy_compensation": lego_settings["xy_size_compensation"],
            "elephant_foot_compensation": lego_settings["elephant_foot_compensation"],
            "seam_position": lego_settings["seam_position"],
        },
        "warnings": warnings,
        "brick_type": brick_type,
    }

    return config


def estimate_print_time(
    volume_mm3: float,
    quality: QualityPreset = QualityPreset.LEGO_OPTIMAL,
    printer: str = "prusa_mk3s",
) -> Dict[str, Any]:
    """
    Estimate print time and material usage.

    Args:
        volume_mm3: Part volume in mm³
        quality: Quality preset
        printer: Printer profile name

    Returns:
        Time and material estimates
    """
    settings = QUALITY_PRESETS.get(quality, QUALITY_PRESETS[QualityPreset.LEGO_OPTIMAL])
    printer_profile = PRINTER_LIBRARY.get(printer, PRINTER_LIBRARY["prusa_mk3s"])

    # Layer height affects print time significantly
    layer_height = settings.layer_height
    print_speed = min(settings.print_speed, printer_profile.max_print_speed)

    # Rough estimation based on volume and speed
    # More accurate would require actual toolpath calculation
    extrusion_volume = volume_mm3 * 1.2  # Account for infill, perimeters, etc.

    # Estimate filament length (1.75mm diameter)
    filament_cross_section = 3.14159 * (1.75 / 2) ** 2
    filament_length_mm = extrusion_volume / filament_cross_section
    filament_length_m = filament_length_mm / 1000

    # Estimate weight (PLA density ~1.24 g/cm³)
    weight_g = (volume_mm3 / 1000) * 1.24 * 1.15  # 15% overhead

    # Estimate time (very rough)
    # Base time on extrusion volume and average speed
    avg_speed = (print_speed + settings.perimeter_speed) / 2
    time_minutes = (filament_length_mm / avg_speed) / 60

    # Add overhead for travel, retraction, etc.
    time_minutes *= 1.3

    hours = int(time_minutes // 60)
    minutes = int(time_minutes % 60)

    return {
        "estimated_time": f"{hours}h {minutes}m",
        "time_minutes": round(time_minutes),
        "filament_length_m": round(filament_length_m, 2),
        "filament_weight_g": round(weight_g, 1),
        "quality_preset": settings.name,
        "layer_height": layer_height,
        "note": "This is a rough estimate. Actual time depends on part geometry and slicer settings.",
    }


def create_batch_print_job(
    stl_files: List[str], printer: str, material: str, quality: str = "lego"
) -> Dict[str, Any]:
    """
    Create a batch print job for multiple bricks.

    Args:
        stl_files: List of STL file paths
        printer: Printer profile name
        material: Material profile name
        quality: Quality preset name

    Returns:
        Batch job configuration
    """
    printer_profile = PRINTER_LIBRARY.get(printer)
    if not printer_profile:
        return {"error": f"Unknown printer: {printer}"}

    jobs = []
    total_volume = 0

    for stl_path in stl_files:
        filename = os.path.basename(stl_path)
        config = generate_print_config(stl_path, printer, material, quality)

        if "error" not in config:
            jobs.append({"file": filename, "config": config})

    return {
        "batch_size": len(jobs),
        "printer": printer_profile.name,
        "material": material,
        "quality": quality,
        "jobs": jobs,
    }


# ============================================================================
# MCP TOOL DEFINITIONS
# ============================================================================

PRINTING_TOOLS = {
    "slice_for_print": {
        "description": """Generate G-code for 3D printing a LEGO brick STL file.

This tool calls the PrusaSlicer service to generate actual G-code
that can be sent directly to a 3D printer.

Supports LEGO-optimized settings that ensure:
- Accurate stud dimensions
- Proper fit tolerance
- Strong layer adhesion
- Optimized seam positioning

Returns the path to the generated G-code file.""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stl_path": {
                    "type": "string",
                    "description": "Path to the STL file to slice",
                },
                "output_path": {
                    "type": "string",
                    "description": "Path for the output G-code file (optional)",
                },
                "printer": {
                    "type": "string",
                    "enum": list(PRINTER_LIBRARY.keys()),
                    "default": "prusa_mk3s",
                    "description": "Printer profile to use",
                },
                "quality": {
                    "type": "string",
                    "enum": ["draft", "normal", "quality", "ultra", "lego"],
                    "default": "lego",
                    "description": "Quality preset (lego = LEGO-optimized)",
                },
                "material": {
                    "type": "string",
                    "enum": list(MATERIAL_LIBRARY.keys()),
                    "default": "pla",
                    "description": "Material type",
                },
                "brick_type": {
                    "type": "string",
                    "enum": ["standard", "plate", "tile", "slope", "technic"],
                    "default": "standard",
                    "description": "Brick type for LEGO-specific optimizations",
                },
            },
            "required": ["stl_path"],
        },
    },
    "generate_print_config": {
        "description": """Generate optimized 3D print configuration for a LEGO brick.

Includes:
- Printer-specific settings
- Material temperatures and retraction
- LEGO-optimized quality settings for proper stud fit
- Dimensional compensation for accuracy

Available printers: Prusa MK3S/MK4/XL, Ender 3, Bambu X1C/P1S/A1, Voron, and more.
Available materials: PLA, PETG, ABS, ASA, TPU, Nylon, CF-filled variants.
Quality presets: draft, normal, quality, ultra, lego (optimized for LEGO)""",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stl_path": {"type": "string", "description": "Path to STL file"},
                "printer": {
                    "type": "string",
                    "enum": list(PRINTER_LIBRARY.keys()),
                    "description": "Printer profile",
                },
                "material": {
                    "type": "string",
                    "enum": list(MATERIAL_LIBRARY.keys()),
                    "description": "Material profile",
                },
                "quality": {
                    "type": "string",
                    "enum": ["draft", "normal", "quality", "ultra", "lego"],
                    "default": "lego",
                    "description": "Quality preset",
                },
                "brick_type": {
                    "type": "string",
                    "enum": ["standard", "plate", "tile", "slope", "technic"],
                    "default": "standard",
                    "description": "Brick type for optimizations",
                },
            },
            "required": ["stl_path", "printer", "material"],
        },
    },
    "estimate_print_time": {
        "description": "Estimate print time and material usage for a brick.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "volume_mm3": {"type": "number", "description": "Part volume in cubic mm"},
                "quality": {
                    "type": "string",
                    "enum": ["draft", "normal", "quality", "ultra", "lego"],
                    "default": "lego",
                },
                "printer": {
                    "type": "string",
                    "enum": list(PRINTER_LIBRARY.keys()),
                    "default": "prusa_mk3s",
                },
            },
            "required": ["volume_mm3"],
        },
    },
    "list_printers": {
        "description": "List all available printer profiles.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "list_materials": {
        "description": "List all available material profiles.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "get_lego_settings": {
        "description": "Get LEGO-optimized print settings for a brick type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "brick_type": {
                    "type": "string",
                    "enum": ["standard", "plate", "tile", "slope", "technic"],
                    "default": "standard",
                },
                "quality": {
                    "type": "string",
                    "enum": ["draft", "normal", "quality", "ultra", "lego"],
                    "default": "lego",
                },
            },
        },
    },
    "create_batch_print": {
        "description": "Create a batch print job for multiple bricks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "stl_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of STL file paths",
                },
                "printer": {"type": "string", "enum": list(PRINTER_LIBRARY.keys())},
                "material": {"type": "string", "enum": list(MATERIAL_LIBRARY.keys())},
                "quality": {
                    "type": "string",
                    "enum": ["draft", "normal", "quality", "ultra", "lego"],
                    "default": "lego",
                },
            },
            "required": ["stl_files", "printer", "material"],
        },
    },
}


def list_printers() -> Dict[str, Any]:
    """List all printer profiles."""
    return {
        "printers": {
            name: {
                "name": p.name,
                "manufacturer": p.manufacturer,
                "bed_size": [p.bed_x, p.bed_y, p.bed_z],
                "features": {
                    "abl": p.has_abl,
                    "direct_drive": p.has_direct_drive,
                    "enclosure": p.has_enclosure,
                },
            }
            for name, p in PRINTER_LIBRARY.items()
        }
    }


def list_materials() -> Dict[str, Any]:
    """List all material profiles."""
    return {
        "materials": {
            name: {
                "name": m.name,
                "type": m.type.value,
                "nozzle_temp": m.nozzle_temp,
                "bed_temp": m.bed_temp,
                "needs_enclosure": m.needs_enclosure,
                "notes": m.notes,
            }
            for name, m in MATERIAL_LIBRARY.items()
        }
    }
