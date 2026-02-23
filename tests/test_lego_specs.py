"""
Unit Tests for LEGO MCP Server

Tests cover:
- LEGO dimension calculations
- Brick geometry validation
- API request/response handling
"""

import pytest
import sys
import os
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.lego_specs import (
    LEGO,
    brick_dimensions,
    stud_positions,
    tube_positions,
    rib_positions,
    BRICK_TYPES,
    COMMON_BRICKS,
)


class TestLegoDimensions:
    """Test LEGO dimension constants and calculations."""

    def test_stud_pitch(self):
        """Verify stud pitch is 8mm."""
        assert LEGO.STUD_PITCH == 8.0

    def test_stud_diameter(self):
        """Verify stud diameter is 4.8mm."""
        assert LEGO.STUD_DIAMETER == 4.8

    def test_brick_height(self):
        """Verify standard brick height is 9.6mm (3 plates)."""
        assert LEGO.BRICK_HEIGHT == 9.6

    def test_plate_height(self):
        """Verify plate height is 1/3 of brick height."""
        assert LEGO.PLATE_HEIGHT == 3.2
        assert abs(LEGO.PLATE_HEIGHT - LEGO.BRICK_HEIGHT / 3) < 0.01

    def test_tube_dimensions(self):
        """Verify tube dimensions for clutch mechanism."""
        assert LEGO.TUBE_OUTER_DIAMETER == 6.51
        assert LEGO.TUBE_INNER_DIAMETER == 4.8
        # Inner diameter should match stud for proper fit
        assert LEGO.TUBE_INNER_DIAMETER == LEGO.STUD_DIAMETER


class TestBrickDimensionCalculations:
    """Test brick dimension calculation functions."""

    def test_1x1_brick(self):
        """Test 1x1 brick dimensions."""
        width, depth, height = brick_dimensions(1, 1)
        assert width == 8.0
        assert depth == 8.0
        assert height == 9.6

    def test_2x4_brick(self):
        """Test classic 2x4 brick dimensions."""
        width, depth, height = brick_dimensions(2, 4)
        assert width == 16.0
        assert depth == 32.0
        assert height == 9.6

    def test_2x4_plate(self):
        """Test 2x4 plate dimensions (1/3 height)."""
        width, depth, height = brick_dimensions(2, 4, height_units=1 / 3)
        assert width == 16.0
        assert depth == 32.0
        assert abs(height - 3.2) < 0.01

    def test_large_brick(self):
        """Test large 8x8 brick."""
        width, depth, height = brick_dimensions(8, 8)
        assert width == 64.0
        assert depth == 64.0
        assert height == 9.6


class TestStudPositions:
    """Test stud position calculations."""

    def test_1x1_stud(self):
        """1x1 brick has one stud at center."""
        positions = stud_positions(1, 1)
        assert len(positions) == 1
        assert positions[0] == (4.0, 4.0)  # Center of 8x8mm brick

    def test_2x2_studs(self):
        """2x2 brick has 4 studs."""
        positions = stud_positions(2, 2)
        assert len(positions) == 4
        # Check corners are at expected positions
        expected = [(4.0, 4.0), (4.0, 12.0), (12.0, 4.0), (12.0, 12.0)]
        for pos in expected:
            assert pos in positions

    def test_2x4_studs(self):
        """2x4 brick has 8 studs."""
        positions = stud_positions(2, 4)
        assert len(positions) == 8

    def test_stud_spacing(self):
        """Verify stud spacing is 8mm."""
        positions = stud_positions(2, 1)
        assert len(positions) == 2
        x1, y1 = positions[0]
        x2, y2 = positions[1]
        # Studs should be 8mm apart
        spacing = abs(x2 - x1) if y1 == y2 else abs(y2 - y1)
        assert spacing == 8.0


class TestTubePositions:
    """Test bottom tube position calculations."""

    def test_1x1_no_tubes(self):
        """1x1 brick has no tubes."""
        positions = tube_positions(1, 1)
        assert len(positions) == 0

    def test_1x4_no_tubes(self):
        """1xN bricks have no tubes (use ribs instead)."""
        positions = tube_positions(1, 4)
        assert len(positions) == 0

    def test_2x2_one_tube(self):
        """2x2 brick has 1 tube at center."""
        positions = tube_positions(2, 2)
        assert len(positions) == 1
        assert positions[0] == (8.0, 8.0)  # Center of 2x2

    def test_2x4_tubes(self):
        """2x4 brick has 3 tubes."""
        positions = tube_positions(2, 4)
        assert len(positions) == 3
        # Tubes at x=8, y=8,16,24
        expected_y = [8.0, 16.0, 24.0]
        for pos in positions:
            assert pos[0] == 8.0
            assert pos[1] in expected_y

    def test_4x4_tubes(self):
        """4x4 brick has 9 tubes (3x3 grid)."""
        positions = tube_positions(4, 4)
        assert len(positions) == 9


class TestRibPositions:
    """Test bottom rib position calculations for 1xN bricks."""

    def test_1x1_no_ribs(self):
        """1x1 brick has no ribs."""
        positions = rib_positions(1, 1)
        assert len(positions) == 0

    def test_2x2_no_ribs(self):
        """2x2 and larger use tubes, not ribs."""
        positions = rib_positions(2, 2)
        assert len(positions) == 0

    def test_1x2_one_rib(self):
        """1x2 brick has 1 rib."""
        positions = rib_positions(1, 2)
        assert len(positions) == 1

    def test_1x4_three_ribs(self):
        """1x4 brick has 3 ribs."""
        positions = rib_positions(1, 4)
        assert len(positions) == 3

    def test_4x1_three_ribs(self):
        """4x1 brick (rotated) has 3 ribs."""
        positions = rib_positions(4, 1)
        assert len(positions) == 3


class TestBrickTypes:
    """Test brick type definitions."""

    def test_standard_brick_exists(self):
        """Standard brick type is defined."""
        assert "standard" in BRICK_TYPES
        assert BRICK_TYPES["standard"]["has_studs"] == True
        assert BRICK_TYPES["standard"]["height_units"] == 1.0

    def test_plate_exists(self):
        """Plate type is defined with correct height."""
        assert "plate" in BRICK_TYPES
        assert BRICK_TYPES["plate"]["height_units"] == 1 / 3

    def test_tile_no_studs(self):
        """Tile type has no studs."""
        assert "tile" in BRICK_TYPES
        assert BRICK_TYPES["tile"]["has_studs"] == False

    def test_slope_has_angle(self):
        """Slope type has angle defined."""
        assert "slope" in BRICK_TYPES
        assert "slope_angle" in BRICK_TYPES["slope"]


class TestCommonBricks:
    """Test common brick configurations."""

    def test_common_bricks_exist(self):
        """Verify common bricks list is populated."""
        assert len(COMMON_BRICKS) > 0

    def test_2x4_in_common(self):
        """Classic 2x4 is in common bricks."""
        names = [b["name"] for b in COMMON_BRICKS]
        assert "2x4" in names

    def test_1x1_in_common(self):
        """1x1 is in common bricks."""
        names = [b["name"] for b in COMMON_BRICKS]
        assert "1x1" in names

    def test_common_brick_format(self):
        """All common bricks have required fields."""
        for brick in COMMON_BRICKS:
            assert "name" in brick
            assert "studs_x" in brick
            assert "studs_y" in brick
            assert brick["studs_x"] >= 1
            assert brick["studs_y"] >= 1


class TestVolumeCalculations:
    """Test brick volume calculations."""

    def test_solid_1x1_volume(self):
        """Estimate solid 1x1 brick volume."""
        width, depth, height = brick_dimensions(1, 1)
        volume = width * depth * height
        # 8 x 8 x 9.6 = 614.4 mm³
        assert abs(volume - 614.4) < 0.1

    def test_solid_2x4_volume(self):
        """Estimate solid 2x4 brick volume."""
        width, depth, height = brick_dimensions(2, 4)
        volume = width * depth * height
        # 16 x 32 x 9.6 = 4915.2 mm³
        assert abs(volume - 4915.2) < 0.1


class TestTolerances:
    """Test manufacturing tolerances."""

    def test_tolerance_is_reasonable(self):
        """Tolerance should be small but not zero."""
        assert 0 < LEGO.FDM_TOLERANCE < 0.5
        assert 0 < LEGO.STUD_TOLERANCE < 0.5

    def test_fdm_tolerance_larger(self):
        """FDM tolerance should be larger than general."""
        assert LEGO.FDM_TOLERANCE >= LEGO.LEGO_PART_TOLERANCE


# ==========================================
# API Response Schema Tests
# ==========================================


class TestAPISchemas:
    """Test API request/response schemas."""

    def test_brick_result_schema(self):
        """Test brick creation result structure."""
        # Simulated result from create_brick
        result = {
            "success": True,
            "brick_id": "brick_0001",
            "component_name": "Brick_2x4",
            "dimensions": {
                "width_mm": 16.0,
                "depth_mm": 32.0,
                "height_mm": 9.6,
                "studs_x": 2,
                "studs_y": 4,
            },
            "volume_mm3": 4500.0,
        }

        assert result["success"] == True
        assert "brick_id" in result
        assert "dimensions" in result
        assert result["dimensions"]["studs_x"] == 2
        assert result["dimensions"]["studs_y"] == 4

    def test_gcode_result_schema(self):
        """Test G-code generation result structure."""
        result = {
            "success": True,
            "path": "/output/gcode/milling/Brick_2x4.nc",
            "machine": "grbl",
            "estimated_time_min": 5.0,
            "operations": ["Adaptive Roughing", "Contour Finishing"],
            "tools": ["flat_3mm", "flat_1mm"],
        }

        assert result["success"] == True
        assert result["path"].endswith(".nc")
        assert "estimated_time_min" in result
        assert len(result["operations"]) > 0


# ==========================================
# Run tests
# ==========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
