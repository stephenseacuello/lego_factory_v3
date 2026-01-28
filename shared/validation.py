"""
Input Validation for LEGO Brick Parameters

Validates brick dimensions, features, and parameters before creation.
Provides clear error messages for invalid inputs.
"""

from typing import Dict, Any, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum


# ============================================================================
# LEGO DIMENSION CONSTRAINTS
# ============================================================================


class LegoConstraints:
    """Valid ranges for LEGO brick dimensions."""

    # Stud dimensions (units)
    MIN_STUDS = 1
    MAX_STUDS = 48  # Largest standard baseplate

    # Height (in plate units: 3 plates = 1 brick)
    MIN_HEIGHT_PLATES = 1
    MAX_HEIGHT_PLATES = 36  # ~12 bricks tall

    # Common valid dimensions
    COMMON_WIDTHS = [1, 2, 3, 4, 6, 8, 10, 12, 16]
    COMMON_DEPTHS = [1, 2, 3, 4, 6, 8, 10, 12, 16]
    COMMON_HEIGHTS = [1, 3, 6, 9, 12]  # plate, brick, 2-brick, 3-brick, 4-brick

    # Slope angles (degrees)
    VALID_SLOPE_ANGLES = [18, 25, 33, 45, 65, 75]

    # Technic hole spacing (must be on stud grid)
    TECHNIC_HOLE_Z_CENTER = 0.5  # Centered in brick height

    # Wall thickness limits
    MIN_WALL_THICKNESS = 0.5
    MAX_WALL_THICKNESS = 3.0
    DEFAULT_WALL_THICKNESS = 1.5

    # Tolerance limits
    MIN_TOLERANCE = 0.0
    MAX_TOLERANCE = 0.5
    DEFAULT_TOLERANCE = 0.1


# ============================================================================
# VALIDATION RESULTS
# ============================================================================


@dataclass
class ValidationError:
    """A single validation error."""

    field: str
    message: str
    value: Any = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validation check."""

    valid: bool
    errors: List[ValidationError]
    warnings: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "errors": [
                {
                    "field": e.field,
                    "message": e.message,
                    "value": e.value,
                    "suggestion": e.suggestion,
                }
                for e in self.errors
            ],
            "warnings": self.warnings,
        }


# ============================================================================
# VALIDATORS
# ============================================================================


def validate_stud_dimension(
    value: Any, field_name: str, min_val: int = None, max_val: int = None
) -> Optional[ValidationError]:
    """
    Validate a stud dimension (width or depth).

    Args:
        value: The value to validate
        field_name: Name of the field for error messages
        min_val: Minimum allowed value (default: MIN_STUDS)
        max_val: Maximum allowed value (default: MAX_STUDS)

    Returns:
        ValidationError if invalid, None if valid
    """
    min_val = min_val or LegoConstraints.MIN_STUDS
    max_val = max_val or LegoConstraints.MAX_STUDS

    # Check type
    if not isinstance(value, (int, float)):
        return ValidationError(
            field=field_name,
            message=f"{field_name} must be a number",
            value=value,
            suggestion=f"Use an integer between {min_val} and {max_val}",
        )

    # Convert to int
    value = int(value)

    # Check range
    if value < min_val:
        return ValidationError(
            field=field_name,
            message=f"{field_name} is too small",
            value=value,
            suggestion=f"Minimum value is {min_val}",
        )

    if value > max_val:
        return ValidationError(
            field=field_name,
            message=f"{field_name} is too large",
            value=value,
            suggestion=f"Maximum value is {max_val}",
        )

    return None


def validate_height_plates(
    value: Any, field_name: str = "height_plates"
) -> Optional[ValidationError]:
    """Validate height in plate units."""
    return validate_stud_dimension(
        value, field_name, LegoConstraints.MIN_HEIGHT_PLATES, LegoConstraints.MAX_HEIGHT_PLATES
    )


def validate_slope_angle(angle: Any) -> Optional[ValidationError]:
    """Validate slope angle."""
    if not isinstance(angle, (int, float)):
        return ValidationError(
            field="slope_angle",
            message="Slope angle must be a number",
            value=angle,
            suggestion=f"Use one of: {LegoConstraints.VALID_SLOPE_ANGLES}",
        )

    angle = float(angle)

    if angle not in LegoConstraints.VALID_SLOPE_ANGLES:
        closest = min(LegoConstraints.VALID_SLOPE_ANGLES, key=lambda x: abs(x - angle))
        return ValidationError(
            field="slope_angle",
            message=f"Invalid slope angle: {angle}°",
            value=angle,
            suggestion=f"Did you mean {closest}°? Valid angles: {LegoConstraints.VALID_SLOPE_ANGLES}",
        )

    return None


def validate_direction(
    direction: str, valid_directions: List[str] = None
) -> Optional[ValidationError]:
    """Validate direction string."""
    if valid_directions is None:
        valid_directions = ["front", "back", "left", "right"]

    if not isinstance(direction, str):
        return ValidationError(
            field="direction",
            message="Direction must be a string",
            value=direction,
            suggestion=f"Use one of: {valid_directions}",
        )

    direction = direction.lower()

    if direction not in valid_directions:
        return ValidationError(
            field="direction",
            message=f"Invalid direction: {direction}",
            value=direction,
            suggestion=f"Use one of: {valid_directions}",
        )

    return None


def validate_position(
    position: Tuple[float, float], max_x: int, max_y: int, field_name: str = "position"
) -> Optional[ValidationError]:
    """Validate a position tuple (x, y)."""
    if not isinstance(position, (list, tuple)):
        return ValidationError(
            field=field_name, message="Position must be a list or tuple of [x, y]", value=position
        )

    if len(position) < 2:
        return ValidationError(
            field=field_name, message="Position must have at least 2 values [x, y]", value=position
        )

    x, y = position[0], position[1]

    if x < 0 or x >= max_x:
        return ValidationError(
            field=field_name,
            message=f"X position {x} is out of range [0, {max_x-1}]",
            value=position,
        )

    if y < 0 or y >= max_y:
        return ValidationError(
            field=field_name,
            message=f"Y position {y} is out of range [0, {max_y-1}]",
            value=position,
        )

    return None


def validate_stud_positions(
    positions: List[Tuple[int, int]], width: int, depth: int
) -> List[ValidationError]:
    """Validate a list of stud positions."""
    errors = []

    if not isinstance(positions, list):
        errors.append(
            ValidationError(
                field="stud_positions", message="Stud positions must be a list", value=positions
            )
        )
        return errors

    for i, pos in enumerate(positions):
        error = validate_position(pos, width, depth, f"stud_positions[{i}]")
        if error:
            errors.append(error)

    return errors


def validate_technic_holes(
    holes: List[Dict], width: int, depth: int, height_plates: int
) -> List[ValidationError]:
    """Validate Technic hole configurations."""
    errors = []

    if not isinstance(holes, list):
        errors.append(
            ValidationError(
                field="technic_holes", message="Technic holes must be a list", value=holes
            )
        )
        return errors

    valid_axes = ["x", "y", "z"]
    valid_types = ["pin", "axle", "pin_axle"]

    for i, hole in enumerate(holes):
        if not isinstance(hole, dict):
            errors.append(
                ValidationError(
                    field=f"technic_holes[{i}]", message="Each hole must be an object", value=hole
                )
            )
            continue

        # Validate axis
        axis = hole.get("axis", "x")
        if axis not in valid_axes:
            errors.append(
                ValidationError(
                    field=f"technic_holes[{i}].axis",
                    message=f"Invalid axis: {axis}",
                    value=axis,
                    suggestion=f"Use one of: {valid_axes}",
                )
            )

        # Validate hole type
        hole_type = hole.get("type", "pin")
        if hole_type not in valid_types:
            errors.append(
                ValidationError(
                    field=f"technic_holes[{i}].type",
                    message=f"Invalid hole type: {hole_type}",
                    value=hole_type,
                    suggestion=f"Use one of: {valid_types}",
                )
            )

    return errors


# ============================================================================
# MAIN VALIDATION FUNCTION
# ============================================================================


def validate_brick_params(
    width_studs: int,
    depth_studs: int,
    height_plates: int = 3,
    brick_type: str = "standard",
    features: Dict[str, Any] = None,
) -> ValidationResult:
    """
    Validate all brick parameters.

    Args:
        width_studs: Width in stud units
        depth_studs: Depth in stud units
        height_plates: Height in plate units
        brick_type: Type of brick
        features: Additional features dictionary

    Returns:
        ValidationResult with errors and warnings
    """
    errors = []
    warnings = []

    # Validate dimensions
    err = validate_stud_dimension(width_studs, "width_studs")
    if err:
        errors.append(err)

    err = validate_stud_dimension(depth_studs, "depth_studs")
    if err:
        errors.append(err)

    err = validate_height_plates(height_plates)
    if err:
        errors.append(err)

    # Validate brick type
    valid_types = ["standard", "plate", "tile", "slope", "technic", "round", "custom"]
    if brick_type.lower() not in valid_types:
        errors.append(
            ValidationError(
                field="brick_type",
                message=f"Invalid brick type: {brick_type}",
                value=brick_type,
                suggestion=f"Use one of: {valid_types}",
            )
        )

    # Validate features if provided
    if features:
        # Validate stud positions
        if "stud_positions" in features:
            errors.extend(
                validate_stud_positions(features["stud_positions"], width_studs, depth_studs)
            )

        # Validate Technic holes
        if "technic_holes" in features:
            errors.extend(
                validate_technic_holes(
                    features["technic_holes"], width_studs, depth_studs, height_plates
                )
            )

        # Validate slope
        if "slope" in features:
            slope = features["slope"]
            if isinstance(slope, dict):
                if "angle" in slope:
                    err = validate_slope_angle(slope["angle"])
                    if err:
                        errors.append(err)

                if "direction" in slope:
                    err = validate_direction(slope["direction"])
                    if err:
                        errors.append(err)

        # Validate wall thickness
        if "wall_thickness" in features:
            wt = features["wall_thickness"]
            if not isinstance(wt, (int, float)):
                errors.append(
                    ValidationError(
                        field="wall_thickness", message="Wall thickness must be a number", value=wt
                    )
                )
            elif wt < LegoConstraints.MIN_WALL_THICKNESS:
                errors.append(
                    ValidationError(
                        field="wall_thickness",
                        message=f"Wall thickness {wt}mm is too thin",
                        value=wt,
                        suggestion=f"Minimum is {LegoConstraints.MIN_WALL_THICKNESS}mm",
                    )
                )
            elif wt > LegoConstraints.MAX_WALL_THICKNESS:
                warnings.append(
                    f"Wall thickness {wt}mm is thicker than standard ({LegoConstraints.DEFAULT_WALL_THICKNESS}mm)"
                )

    # Add warnings for unusual dimensions
    if width_studs > 16:
        warnings.append(f"Width of {width_studs} studs is larger than standard bricks")

    if depth_studs > 16:
        warnings.append(f"Depth of {depth_studs} studs is larger than standard bricks")

    if height_plates > 12:
        warnings.append(f"Height of {height_plates} plates is taller than standard bricks")

    # Check for tube compatibility
    if width_studs >= 2 and depth_studs >= 2:
        pass  # Can have tubes
    elif width_studs == 1 or depth_studs == 1:
        pass  # Will have ribs instead

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_and_return(
    width_studs: int,
    depth_studs: int,
    height_plates: int = 3,
    brick_type: str = "standard",
    features: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Validate parameters and return result dict.

    Returns a dictionary with:
    - "valid": bool
    - "errors": list of error messages
    - "warnings": list of warnings
    """
    result = validate_brick_params(width_studs, depth_studs, height_plates, brick_type, features)
    return result.to_dict()


# ============================================================================
# QUICK VALIDATORS
# ============================================================================


def is_valid_brick_size(width: int, depth: int, height_plates: int = 3) -> bool:
    """Quick check if brick size is valid."""
    return (
        LegoConstraints.MIN_STUDS <= width <= LegoConstraints.MAX_STUDS
        and LegoConstraints.MIN_STUDS <= depth <= LegoConstraints.MAX_STUDS
        and LegoConstraints.MIN_HEIGHT_PLATES <= height_plates <= LegoConstraints.MAX_HEIGHT_PLATES
    )


def is_valid_slope_angle(angle: float) -> bool:
    """Quick check if slope angle is valid."""
    return angle in LegoConstraints.VALID_SLOPE_ANGLES


def is_common_brick_size(width: int, depth: int) -> bool:
    """Check if this is a common/standard brick size."""
    return width in LegoConstraints.COMMON_WIDTHS and depth in LegoConstraints.COMMON_DEPTHS


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Test validation
    print("Testing validation...")

    # Valid brick
    result = validate_brick_params(2, 4, 3)
    print(f"2x4 brick: valid={result.valid}, errors={len(result.errors)}")

    # Invalid brick (too large)
    result = validate_brick_params(100, 4, 3)
    print(
        f"100x4 brick: valid={result.valid}, errors={result.errors[0].message if result.errors else 'none'}"
    )

    # Brick with invalid slope
    result = validate_brick_params(2, 4, 3, "slope", {"slope": {"angle": 50}})
    print(
        f"2x4 slope 50°: valid={result.valid}, errors={result.errors[0].message if result.errors else 'none'}"
    )

    # Valid slope brick
    result = validate_brick_params(2, 4, 3, "slope", {"slope": {"angle": 45, "direction": "front"}})
    print(f"2x4 slope 45°: valid={result.valid}, warnings={result.warnings}")
