"""
PrusaSlicer HTTP API Service

Provides a REST API for slicing STL files using PrusaSlicer CLI.
Optimized for LEGO brick printing with appropriate profiles.
Works on both x64 and ARM64 (Apple Silicon).
"""

import os
import subprocess
import json
import re
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


app = FastAPI(
    title="LEGO Slicer Service",
    description="PrusaSlicer-based G-code generation for LEGO bricks",
    version="2.0.0",
)

# Directories
TEMP_DIR = Path("/tmp/slicer")
TEMP_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_SOURCE_DIR = Path("/app/profiles_source")  # Read-only source profiles
OUTPUT_DIR = Path("/output/gcode/3dprint")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# === Models ===


class SliceRequest(BaseModel):
    """Request to slice an STL file."""

    stl_path: str = Field(..., description="Path to input STL file")
    printer: str = Field("generic", description="Printer profile name")
    material: str = Field("pla", description="Material type")
    quality: str = Field("fine", description="Print quality preset")
    infill_percent: int = Field(20, ge=0, le=100, description="Infill percentage")
    output_filename: Optional[str] = Field(None, description="Custom output filename")


class SliceResponse(BaseModel):
    """Response from slicing operation."""

    success: bool
    path: str = ""
    estimated_time_min: float = 0
    filament_meters: float = 0
    filament_grams: float = 0
    layer_height_mm: float = 0
    layer_count: int = 0
    error: str = ""


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str
    engine: str
    engine_available: bool


# === Quality Presets ===

QUALITY_PRESETS = {
    "draft": {"layer_height": 0.30, "wall_count": 2, "top_layers": 3, "bottom_layers": 2},
    "normal": {"layer_height": 0.20, "wall_count": 3, "top_layers": 4, "bottom_layers": 3},
    "fine": {"layer_height": 0.15, "wall_count": 3, "top_layers": 5, "bottom_layers": 4},
    "ultra": {"layer_height": 0.10, "wall_count": 4, "top_layers": 6, "bottom_layers": 5},
    # LEGO-optimized preset
    "lego": {"layer_height": 0.12, "wall_count": 3, "top_layers": 5, "bottom_layers": 4},
}

# Material-specific settings
MATERIAL_SETTINGS = {
    "pla": {"temp_extruder": 215, "temp_bed": 60, "fan_speed": 100},
    "petg": {"temp_extruder": 240, "temp_bed": 85, "fan_speed": 50},
    "abs": {"temp_extruder": 255, "temp_bed": 100, "fan_speed": 0},
    "asa": {"temp_extruder": 260, "temp_bed": 105, "fan_speed": 0},
}


# === Helper Functions ===


def is_prusaslicer_available() -> bool:
    """Check if PrusaSlicer CLI is available."""
    try:
        result = subprocess.run(
            ["prusa-slicer", "--help"], capture_output=True, text=True, timeout=10
        )
        # --help returns exit code 0 and contains "PrusaSlicer"
        return "PrusaSlicer" in result.stdout or "PrusaSlicer" in result.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def get_prusaslicer_version() -> str:
    """Get PrusaSlicer version."""
    try:
        result = subprocess.run(
            ["prusa-slicer", "--help"], capture_output=True, text=True, timeout=10
        )
        # Parse version from output like "PrusaSlicer-2.9.2+..."
        combined = result.stdout + result.stderr
        version_match = re.search(r"PrusaSlicer[- ]*([\d.]+)", combined)
        if version_match:
            return version_match.group(1)
    except Exception:
        pass
    return "unknown"


def load_printer_profile(printer: str) -> dict:
    """Load printer-specific settings from profile JSON files."""
    profiles_dir = PROFILES_SOURCE_DIR if PROFILES_SOURCE_DIR.exists() else Path("/app/profiles")

    # Try to load printer-specific profile
    profile_files = [
        profiles_dir / f"{printer}.json",
        profiles_dir / f"lego_{printer}.json",
    ]

    for profile_path in profile_files:
        if profile_path.exists():
            try:
                with open(profile_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_path}: {e}")

    # Return empty dict if no profile found
    return {}


def create_prusa_ini(quality: dict, material: dict, infill: int, printer: str = "generic") -> Path:
    """Create a PrusaSlicer INI config for LEGO brick printing."""

    # Load printer-specific overrides
    printer_profile = load_printer_profile(printer)

    # Apply printer-specific dimensional accuracy if available
    dim_accuracy = printer_profile.get("dimensional_accuracy", {})
    xy_comp = dim_accuracy.get("xy_compensation", -0.08)
    elephant_foot = dim_accuracy.get("elephant_foot_compensation", 0.15)

    # Apply printer-specific speeds if available
    speed_overrides = printer_profile.get("speed_overrides", {})
    outer_wall_speed = speed_overrides.get("outer_wall_speed", 30)
    inner_wall_speed = speed_overrides.get("inner_wall_speed", 40)
    infill_speed_val = speed_overrides.get("sparse_infill_speed", 60)
    first_layer_speed = speed_overrides.get("first_layer_speed", 20)

    # Check if Bambu printer (uses different G-code flavor)
    is_bambu = "bambu" in printer.lower()
    gcode_flavor = "klipper" if is_bambu else "marlin"

    # PrusaSlicer uses INI format
    config_lines = [
        "# PrusaSlicer config for LEGO bricks",
        f"# Generated by LEGO MCP Slicer Service for {printer}",
        "",
        "# Layer settings",
        f"layer_height = {quality['layer_height']}",
        f"first_layer_height = {quality['layer_height'] * 1.2:.2f}",
        "",
        "# Perimeters/walls",
        f"perimeters = {quality['wall_count']}",
        f"top_solid_layers = {quality['top_layers']}",
        f"bottom_solid_layers = {quality['bottom_layers']}",
        "",
        "# Infill",
        f"fill_density = {infill}%",
        "fill_pattern = grid",
        "",
        "# Temperature",
        f"temperature = {material['temp_extruder']}",
        f"first_layer_temperature = {material['temp_extruder'] + 5}",
        f"bed_temperature = {material['temp_bed']}",
        f"first_layer_bed_temperature = {material['temp_bed'] + 5}",
        "",
        "# Fan",
        f"max_fan_speed = {material['fan_speed']}",
        f"min_fan_speed = {material['fan_speed']}",
        "disable_fan_first_layers = 1",
        "",
        "# Speed (mm/s) - tuned for LEGO precision",
        f"perimeter_speed = {inner_wall_speed}",
        f"external_perimeter_speed = {outer_wall_speed}",
        f"infill_speed = {infill_speed_val}",
        f"solid_infill_speed = {int(infill_speed_val * 0.8)}",
        f"top_solid_infill_speed = {int(outer_wall_speed)}",
        f"first_layer_speed = {first_layer_speed}",
        "travel_speed = 150",
        "",
        "# Retraction",
        "retract_length = 0.8",
        "retract_speed = 45",
        "",
        "# Nozzle",
        "nozzle_diameter = 0.4",
        "extrusion_width = 0.45",
        "",
        "# Quality for LEGO - external perimeters first for clean finish",
        "external_perimeters_first = 1",
        "infill_first = 0",
        "",
        "# Skirt for adhesion check",
        "skirts = 3",
        "skirt_distance = 3",
        "skirt_height = 1",
        "",
        "# Support disabled for standard bricks",
        "support_material = 0",
        "",
        "# XY compensation for LEGO tolerance (slight shrink)",
        f"xy_size_compensation = {xy_comp}",
        f"elephant_foot_compensation = {elephant_foot}",
        "",
        "# G-code flavor",
        f"gcode_flavor = {gcode_flavor}",
        "",
        "# Start/End G-code",
        "start_gcode = G28 ; Home all axes\\nG1 Z5 F3000 ; Lift nozzle",
        "end_gcode = M104 S0 ; Turn off extruder\\nM140 S0 ; Turn off bed\\nG28 X0 Y0 ; Home X/Y\\nM84 ; Disable steppers",
    ]

    config_path = TEMP_DIR / f"lego_config_{printer}.ini"
    with open(config_path, "w") as f:
        f.write("\n".join(config_lines))

    return config_path


def parse_gcode_stats(gcode_path: Path) -> dict:
    """Parse G-code file for print statistics."""
    stats = {"time_min": 0, "filament_m": 0, "filament_g": 0, "layers": 0}

    try:
        with open(gcode_path, "r") as f:
            content = f.read()

            # PrusaSlicer format: ; estimated printing time (normal mode) = 1h 2m 3s
            time_match = re.search(r"; estimated printing time.*?=\s*((?:\d+h\s*)?(?:\d+m\s*)?(?:\d+s)?)", content)
            if time_match:
                time_str = time_match.group(1)
                total_min = 0
                hours = re.search(r"(\d+)h", time_str)
                mins = re.search(r"(\d+)m", time_str)
                secs = re.search(r"(\d+)s", time_str)
                if hours:
                    total_min += int(hours.group(1)) * 60
                if mins:
                    total_min += int(mins.group(1))
                if secs:
                    total_min += int(secs.group(1)) / 60
                stats["time_min"] = total_min

            # Filament used: ; filament used [mm] = 1234.56
            filament_mm_match = re.search(r"; filament used \[mm\]\s*=\s*([\d.]+)", content)
            if filament_mm_match:
                stats["filament_m"] = float(filament_mm_match.group(1)) / 1000
                # Estimate grams (PLA ~1.24 g/cm³, 1.75mm filament)
                stats["filament_g"] = stats["filament_m"] * 2.98

            # Layer count from G-code
            layer_matches = re.findall(r";LAYER:(\d+)", content)
            if layer_matches:
                stats["layers"] = max(int(x) for x in layer_matches) + 1

    except FileNotFoundError:
        logger.warning(f"G-code file not found: {gcode_path}")
    except Exception as e:
        logger.warning(f"Error parsing G-code stats from {gcode_path}: {e}")

    return stats


# === Endpoints ===


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and PrusaSlicer availability."""
    engine_available = is_prusaslicer_available()
    version = get_prusaslicer_version() if engine_available else "not installed"

    return HealthResponse(
        status="ok" if engine_available else "degraded",
        service="LEGO Slicer Service",
        version="2.0.0",
        engine=f"PrusaSlicer {version}",
        engine_available=engine_available,
    )


@app.get("/printers")
async def list_printers():
    """List available printer profiles."""
    printers = [
        "generic",
        "prusa_mk3s", "prusa_mk4", "prusa_mini",
        "bambu_p1s", "bambu_x1c", "bambu_a1",
        "ender3", "ender3_v2",
        "voron_24",
    ]
    return {"printers": printers}


@app.get("/profiles")
async def list_profiles():
    """
    List available printer profiles with details (alias for /printers).

    Returns all available printer profiles with their settings.
    """
    printers = [
        "generic",
        "prusa_mk3s", "prusa_mk4", "prusa_mini",
        "bambu_p1s", "bambu_x1c", "bambu_a1",
        "ender3", "ender3_v2",
        "voron_24",
    ]

    # Load profile details if available
    profiles = {}
    for printer in printers:
        profile_data = load_printer_profile(printer)
        profiles[printer] = {
            "name": printer,
            "description": profile_data.get("description", f"{printer} printer profile"),
            "has_custom_settings": bool(profile_data),
        }

    return {
        "profiles": printers,
        "details": profiles,
        "qualities": list(QUALITY_PRESETS.keys()),
        "materials": list(MATERIAL_SETTINGS.keys()),
    }


@app.get("/materials")
async def list_materials():
    """List available material profiles."""
    return {"materials": list(MATERIAL_SETTINGS.keys()), "settings": MATERIAL_SETTINGS}


@app.get("/qualities")
async def list_qualities():
    """List available quality presets."""
    return {"qualities": list(QUALITY_PRESETS.keys()), "settings": QUALITY_PRESETS}


class LegoSliceRequest(BaseModel):
    """Request to slice a LEGO brick STL file with optimized settings."""

    stl_path: str = Field(..., description="Path to input STL file")
    printer: str = Field("generic", description="Printer profile name")
    brick_type: str = Field("standard", description="LEGO brick type")
    output_path: Optional[str] = Field(None, description="Custom output path")


@app.post("/slice/lego", response_model=SliceResponse)
async def slice_lego_stl(request: LegoSliceRequest):
    """
    Slice a LEGO brick STL with optimized settings.

    Uses LEGO-optimized quality preset with settings tuned for LEGO dimensions.
    """
    # Convert to standard slice request with LEGO-optimized settings
    standard_request = SliceRequest(
        stl_path=request.stl_path,
        printer=request.printer,
        material="pla",  # PLA is best for LEGO
        quality="lego",  # LEGO-optimized quality preset
        infill_percent=20,  # 20% infill for bricks
        output_filename=request.output_path.split("/")[-1] if request.output_path else None,
    )
    return await slice_stl(standard_request)


@app.post("/slice", response_model=SliceResponse)
async def slice_stl(request: SliceRequest):
    """
    Slice an STL file and generate G-code.

    Uses PrusaSlicer CLI with LEGO-optimized settings.
    """
    # Validate input file
    stl_path = Path(request.stl_path)
    if not stl_path.exists():
        raise HTTPException(404, f"STL file not found: {request.stl_path}")

    # Check if PrusaSlicer is available
    if not is_prusaslicer_available():
        return SliceResponse(
            success=False,
            error="PrusaSlicer not available. Please check installation.",
        )

    # Get quality settings
    quality = QUALITY_PRESETS.get(request.quality, QUALITY_PRESETS["fine"])
    material = MATERIAL_SETTINGS.get(request.material, MATERIAL_SETTINGS["pla"])

    # Create config file with printer-specific settings
    config_path = create_prusa_ini(quality, material, request.infill_percent, request.printer)

    # Determine output path
    if request.output_filename:
        output_name = request.output_filename
    else:
        base_name = stl_path.stem
        output_name = f"{base_name}_{request.printer}_{request.quality}.gcode"

    output_path = OUTPUT_DIR / output_name

    # Build PrusaSlicer command
    # prusa-slicer --load config.ini -g -o output.gcode input.stl
    cmd = [
        "prusa-slicer",
        "--load", str(config_path),
        "-g",  # Export G-code (short form of --gcode)
        "-o", str(output_path),
        str(stl_path),
    ]

    logger.info(f"Running: {' '.join(cmd)}")

    try:
        # Run PrusaSlicer
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error(f"PrusaSlicer failed: {error_msg}")
            return SliceResponse(success=False, error=f"PrusaSlicer failed: {error_msg}")

        if not output_path.exists():
            return SliceResponse(success=False, error="G-code file was not created")

        # Parse G-code for statistics
        stats = parse_gcode_stats(output_path)

        return SliceResponse(
            success=True,
            path=str(output_path),
            estimated_time_min=stats.get("time_min", 0),
            filament_meters=stats.get("filament_m", 0),
            filament_grams=stats.get("filament_g", 0),
            layer_height_mm=quality["layer_height"],
            layer_count=stats.get("layers", 0),
        )

    except subprocess.TimeoutExpired:
        return SliceResponse(success=False, error="Slicing timed out (>5 minutes)")
    except Exception as e:
        logger.exception("Error during slicing")
        return SliceResponse(success=False, error=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8766)
