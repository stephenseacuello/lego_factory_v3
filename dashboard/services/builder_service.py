"""
Builder Service

Handles brick creation, validation, and custom brick building.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import asdict

# Add shared path if not already there
SHARED_PATH = Path(__file__).parent.parent.parent / "shared"
if str(SHARED_PATH) not in sys.path:
    sys.path.insert(0, str(SHARED_PATH))

# Import from shared modules
try:
    from custom_brick_builder import (
        CustomBrickBuilder,
        brick,
        plate,
        tile,
        slope_brick,
        technic_brick,
    )
    from validation import validate_brick_params, ValidationResult
    from lego_specs import (
        STUD_PITCH,
        STUD_DIAMETER,
        PLATE_HEIGHT,
        BRICK_HEIGHT,
        WALL_THICKNESS,
        STUD_HEIGHT,
    )

    BUILDER_AVAILABLE = True
except ImportError as e:
    print(f"Builder imports failed: {e}")
    BUILDER_AVAILABLE = False

# Fallback specs if imports fail
FALLBACK_SPECS = {
    "stud_pitch": 8.0,
    "stud_diameter": 4.8,
    "stud_height": 1.7,
    "plate_height": 3.2,
    "brick_height": 9.6,
    "wall_thickness": 1.5,
}


class BuilderService:
    """Service for creating and validating custom bricks."""

    # Valid brick types
    BRICK_TYPES = [
        {"id": "standard", "name": "Standard Brick", "height_plates": 3},
        {"id": "plate", "name": "Plate", "height_plates": 1},
        {"id": "tile", "name": "Tile (No Studs)", "height_plates": 1},
        {"id": "slope_45", "name": "Slope 45°", "height_plates": 3},
        {"id": "slope_33", "name": "Slope 33°", "height_plates": 3},
        {"id": "slope_65", "name": "Slope 65°", "height_plates": 3},
        {"id": "technic", "name": "Technic (with holes)", "height_plates": 3},
        {"id": "double", "name": "Double Height", "height_plates": 6},
    ]

    # Valid slope angles
    SLOPE_ANGLES = [18, 25, 33, 45, 65, 75]

    # Valid slope directions
    SLOPE_DIRECTIONS = ["front", "back", "left", "right"]

    @staticmethod
    def get_brick_types() -> List[Dict[str, Any]]:
        """Get available brick types."""
        return BuilderService.BRICK_TYPES

    @staticmethod
    def get_slope_angles() -> List[int]:
        """Get valid slope angles."""
        return BuilderService.SLOPE_ANGLES

    @staticmethod
    def get_slope_directions() -> List[str]:
        """Get valid slope directions."""
        return BuilderService.SLOPE_DIRECTIONS

    @staticmethod
    def validate_params(
        width_studs: int,
        depth_studs: int,
        height_plates: int,
        brick_type: str = "standard",
        features: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Validate brick parameters.

        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []

        # Basic validation (works even without shared module)
        if width_studs < 1:
            errors.append({"field": "width_studs", "message": "Width must be at least 1 stud", "suggestion": "Use 1-16 studs"})
        elif width_studs > 48:
            errors.append({"field": "width_studs", "message": "Width exceeds maximum (48)", "suggestion": "Use 1-48 studs"})

        if depth_studs < 1:
            errors.append({"field": "depth_studs", "message": "Depth must be at least 1 stud", "suggestion": "Use 1-16 studs"})
        elif depth_studs > 48:
            errors.append({"field": "depth_studs", "message": "Depth exceeds maximum (48)", "suggestion": "Use 1-48 studs"})

        if height_plates < 1:
            errors.append({"field": "height_plates", "message": "Height must be at least 1 plate", "suggestion": "Use 1-36 plates"})
        elif height_plates > 36:
            errors.append({"field": "height_plates", "message": "Height exceeds maximum (36)", "suggestion": "Use 1-36 plates"})

        # Warnings for unusual dimensions
        if width_studs > 16:
            warnings.append({"field": "width_studs", "message": f"Large width ({width_studs}) - may affect print quality", "suggestion": None})
        if depth_studs > 16:
            warnings.append({"field": "depth_studs", "message": f"Large depth ({depth_studs}) - may affect print quality", "suggestion": None})

        # Brick type validation
        valid_types = ["standard", "plate", "tile", "slope_45", "slope_33", "slope_65", "technic", "double"]
        if brick_type not in valid_types and not brick_type.startswith("slope"):
            warnings.append({"field": "brick_type", "message": f"Unknown brick type: {brick_type}", "suggestion": "Using as standard brick"})

        # Use shared validation if available for more detailed checks
        if BUILDER_AVAILABLE:
            try:
                result = validate_brick_params(
                    width_studs, depth_studs, height_plates, brick_type, features
                )
                # Merge errors and warnings from shared module
                for e in result.errors:
                    errors.append({"field": e.field, "message": e.message, "suggestion": e.suggestion})
                for w in result.warnings:
                    warnings.append({"field": w.field, "message": w.message, "suggestion": w.suggestion})
            except Exception as ex:
                # If shared validation fails, continue with basic validation
                pass

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    @staticmethod
    def compute_dimensions(
        width_studs: int, depth_studs: int, height_plates: int
    ) -> Dict[str, float]:
        """Compute actual dimensions in mm."""
        if BUILDER_AVAILABLE:
            stud_pitch = STUD_PITCH
            plate_height = PLATE_HEIGHT
        else:
            # Use fallback values
            stud_pitch = FALLBACK_SPECS["stud_pitch"]
            plate_height = FALLBACK_SPECS["plate_height"]

        width_mm = width_studs * stud_pitch
        depth_mm = depth_studs * stud_pitch
        height_mm = height_plates * plate_height

        # Approximate volume (simplified box minus hollow)
        outer_volume = width_mm * depth_mm * height_mm
        wall = 1.5  # Approximate wall thickness
        inner_volume = max(0, (width_mm - 2 * wall) * (depth_mm - 2 * wall) * (height_mm - wall))
        volume = outer_volume - inner_volume * 0.8  # 80% hollow

        return {
            "width_mm": round(width_mm, 2),
            "depth_mm": round(depth_mm, 2),
            "height_mm": round(height_mm, 2),
            "volume_mm3": round(volume, 1),
            "stud_count": width_studs * depth_studs,
            "weight_g": round(volume * 0.00105, 2),  # ABS density ~1.05 g/cm³
        }

    @staticmethod
    def build_brick_definition(
        name: str,
        width_studs: int,
        depth_studs: int,
        height_plates: int,
        brick_type: str = "standard",
        color: str = None,
        hollow: bool = True,
        studs: bool = True,
        tubes: bool = True,
        slope_angle: int = None,
        slope_direction: str = "front",
        technic_holes: bool = False,
        technic_axis: str = "x",
        chamfers: bool = False,
    ) -> Dict[str, Any]:
        """
        Build a complete brick definition for creation.

        Returns:
            Brick definition dict ready for MCP tool
        """
        definition = {
            "name": name,
            "width_studs": width_studs,
            "depth_studs": depth_studs,
            "height_plates": height_plates,
            "color": color,
            "features": {
                "hollow": hollow,
                "studs": studs and brick_type != "tile",
                "tubes": tubes and width_studs >= 2 and depth_studs >= 2,
            },
        }

        # Handle brick type specifics
        if brick_type == "tile":
            definition["features"]["studs"] = False

        elif brick_type.startswith("slope"):
            angle = slope_angle or int(brick_type.split("_")[1]) if "_" in brick_type else 45
            definition["features"]["slope"] = {"angle": angle, "direction": slope_direction}

        elif brick_type == "technic":
            definition["features"]["technic_holes"] = [
                {"axis": technic_axis, "type": "pin", "positions": list(range(depth_studs))}
            ]

        if chamfers:
            definition["features"]["chamfers"] = {"size": 0.3, "edges": "all"}

        # Add computed dimensions
        definition["dimensions"] = BuilderService.compute_dimensions(
            width_studs, depth_studs, height_plates
        )

        return definition

    @staticmethod
    def create_brick(definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a brick (returns definition for MCP tool to execute).

        This doesn't actually create in Fusion 360 - that's done via MCP.
        Returns the prepared definition.
        """
        # Validate first
        validation = BuilderService.validate_params(
            definition["width_studs"],
            definition["depth_studs"],
            definition["height_plates"],
            definition.get("brick_type", "standard"),
            definition.get("features"),
        )

        if not validation["valid"]:
            return {"success": False, "error": "Validation failed", "validation": validation}

        return {
            "success": True,
            "definition": definition,
            "action": "create_brick",
            "message": f"Ready to create {definition['name']}",
        }

    @staticmethod
    def get_presets() -> List[Dict[str, Any]]:
        """Get preset brick configurations."""
        return [
            {
                "id": "basic_2x4",
                "name": "Basic 2x4 Brick",
                "params": {
                    "width_studs": 2,
                    "depth_studs": 4,
                    "height_plates": 3,
                    "brick_type": "standard",
                },
            },
            {
                "id": "plate_4x4",
                "name": "4x4 Plate",
                "params": {
                    "width_studs": 4,
                    "depth_studs": 4,
                    "height_plates": 1,
                    "brick_type": "plate",
                },
            },
            {
                "id": "tile_2x2",
                "name": "2x2 Tile",
                "params": {
                    "width_studs": 2,
                    "depth_studs": 2,
                    "height_plates": 1,
                    "brick_type": "tile",
                },
            },
            {
                "id": "slope_45_2x3",
                "name": "45° Slope 2x3",
                "params": {
                    "width_studs": 2,
                    "depth_studs": 3,
                    "height_plates": 3,
                    "brick_type": "slope_45",
                    "slope_angle": 45,
                },
            },
            {
                "id": "technic_1x8",
                "name": "Technic 1x8",
                "params": {
                    "width_studs": 1,
                    "depth_studs": 8,
                    "height_plates": 3,
                    "brick_type": "technic",
                },
            },
        ]

    @staticmethod
    def get_lego_specs() -> Dict[str, float]:
        """Get LEGO dimension specifications."""
        if BUILDER_AVAILABLE:
            return {
                "stud_pitch": STUD_PITCH,
                "stud_diameter": STUD_DIAMETER,
                "stud_height": STUD_HEIGHT,
                "plate_height": PLATE_HEIGHT,
                "brick_height": BRICK_HEIGHT,
                "wall_thickness": WALL_THICKNESS,
            }
        else:
            return FALLBACK_SPECS.copy()


# Singleton instance
builder_service = BuilderService()
