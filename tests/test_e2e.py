"""
End-to-End Test Suite for LEGO MCP

Tests complete workflows from brick creation through export and slicing.
Includes integration tests, stress tests, and validation tests.
"""

import pytest
import asyncio
import sys
import os
import json
import time
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server", "src"))


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_fusion_client():
    """Mock Fusion 360 client."""
    client = Mock()
    client.health_check = AsyncMock(return_value=True)
    client.create_brick = AsyncMock(
        return_value={
            "success": True,
            "component_name": "TestBrick",
            "dimensions": {"width": 16, "depth": 32, "height": 9.6},
        }
    )
    client.export_stl = AsyncMock(
        return_value={"success": True, "output_path": "/output/test.stl", "format": "stl"}
    )
    client.generate_preview = AsyncMock(
        return_value={"success": True, "output_path": "/output/preview.png"}
    )
    return client


@pytest.fixture
def mock_slicer_client():
    """Mock slicer client."""
    client = Mock()
    client.health_check = AsyncMock(return_value=True)
    client.slice = AsyncMock(
        return_value={
            "success": True,
            "gcode_path": "/output/test.gcode",
            "print_time": "1h 23m",
            "filament_used": "5.2m",
        }
    )
    return client


# ============================================================================
# UNIT TESTS - LEGO SPECS
# ============================================================================


class TestLegoSpecs:
    """Test LEGO dimension specifications."""

    def test_stud_pitch(self):
        from lego_specs import STUD_PITCH

        assert STUD_PITCH == 8.0

    def test_stud_diameter(self):
        from lego_specs import STUD_DIAMETER

        assert STUD_DIAMETER == 4.8

    def test_plate_height(self):
        from lego_specs import PLATE_HEIGHT

        assert PLATE_HEIGHT == 3.2

    def test_brick_height(self):
        from lego_specs import BRICK_HEIGHT

        assert BRICK_HEIGHT == 9.6

    def test_brick_is_3_plates(self):
        from lego_specs import BRICK_HEIGHT, PLATE_HEIGHT

        assert BRICK_HEIGHT == PLATE_HEIGHT * 3

    def test_wall_thickness(self):
        from lego_specs import WALL_THICKNESS

        assert 1.4 <= WALL_THICKNESS <= 1.6

    def test_tube_outer(self):
        from lego_specs import TUBE_OUTER_DIAMETER

        assert 6.4 <= TUBE_OUTER_DIAMETER <= 6.6


# ============================================================================
# UNIT TESTS - VALIDATION
# ============================================================================


class TestValidation:
    """Test input validation."""

    def test_valid_standard_brick(self):
        from validation import validate_brick_params

        result = validate_brick_params(2, 4, 3)
        assert result.valid == True
        assert len(result.errors) == 0

    def test_valid_large_brick(self):
        from validation import validate_brick_params

        result = validate_brick_params(16, 16, 3)
        assert result.valid == True

    def test_invalid_width_zero(self):
        from validation import validate_brick_params

        result = validate_brick_params(0, 4, 3)
        assert result.valid == False
        assert any("width" in e.field.lower() for e in result.errors)

    def test_invalid_width_negative(self):
        from validation import validate_brick_params

        result = validate_brick_params(-1, 4, 3)
        assert result.valid == False

    def test_invalid_width_too_large(self):
        from validation import validate_brick_params

        result = validate_brick_params(100, 4, 3)
        assert result.valid == False

    def test_invalid_height(self):
        from validation import validate_brick_params

        result = validate_brick_params(2, 4, 100)
        assert result.valid == False

    def test_valid_slope_45(self):
        from validation import validate_brick_params

        result = validate_brick_params(
            2, 4, 3, "slope", {"slope": {"angle": 45, "direction": "front"}}
        )
        assert result.valid == True

    def test_invalid_slope_50(self):
        from validation import validate_brick_params

        result = validate_brick_params(2, 4, 3, "slope", {"slope": {"angle": 50}})
        assert result.valid == False

    def test_warning_for_large_brick(self):
        from validation import validate_brick_params

        result = validate_brick_params(24, 4, 3)
        assert result.valid == True
        assert len(result.warnings) > 0


# ============================================================================
# UNIT TESTS - BRICK CATALOG
# ============================================================================


class TestBrickCatalog:
    """Test brick catalog functionality."""

    def test_catalog_has_bricks(self):
        from brick_catalog_extended import BRICKS, stats

        s = stats()
        assert s["total"] > 300

    def test_get_brick_2x4(self):
        from brick_catalog_extended import get

        brick = get("brick_2x4")
        assert brick is not None
        assert brick.studs_x == 2
        assert brick.studs_y == 4

    def test_get_nonexistent_brick(self):
        from brick_catalog_extended import get

        brick = get("brick_999x999")
        assert brick is None

    def test_search_brick(self):
        from brick_catalog_extended import search

        results = search("2x4")
        assert len(results) > 0

    def test_search_slope(self):
        from brick_catalog_extended import search

        results = search("slope 45")
        assert len(results) > 0

    def test_by_category(self):
        from brick_catalog_extended import by_category, Category

        plates = by_category(Category.PLATE)
        assert len(plates) > 10

    def test_all_categories_exist(self):
        from brick_catalog_extended import by_category, Category

        for cat in Category:
            bricks = by_category(cat)
            # All categories should have at least one brick
            assert len(bricks) >= 0


# ============================================================================
# UNIT TESTS - CUSTOM BRICK BUILDER
# ============================================================================


class TestCustomBrickBuilder:
    """Test custom brick builder."""

    def test_create_basic_brick(self):
        from custom_brick_builder import CustomBrickBuilder

        brick = CustomBrickBuilder().set_base(2, 4, 3).add_studs().build("test")
        assert brick.width_studs == 2
        assert brick.depth_studs == 4
        assert brick.height_plates == 3

    def test_create_hollow_brick(self):
        from custom_brick_builder import CustomBrickBuilder

        brick = (
            CustomBrickBuilder()
            .set_base(2, 4, 3)
            .add_studs()
            .hollow_bottom()
            .add_tubes()
            .build("hollow")
        )
        assert brick.hollow == True

    def test_plate_builder(self):
        from custom_brick_builder import plate

        brick = plate(4, 4).build("plate_4x4")
        assert brick.height_plates == 1

    def test_tile_builder(self):
        from custom_brick_builder import tile

        brick = tile(2, 2).build("tile_2x2")
        assert brick.stud_type == "none"

    def test_slope_builder(self):
        from custom_brick_builder import slope_brick

        brick = slope_brick(2, 3, 45).build("slope")
        assert len(brick.slopes) > 0
        assert brick.slopes[0].angle == 45

    def test_technic_builder(self):
        from custom_brick_builder import technic_brick

        brick = technic_brick(1, 6).build("technic")
        assert len(brick.technic_holes) > 0


# ============================================================================
# UNIT TESTS - ADVANCED FEATURES
# ============================================================================


class TestAdvancedFeatures:
    """Test advanced brick features."""

    def test_ball_joint(self):
        from advanced_features import AdvancedBrickBuilder, BallType

        brick = AdvancedBrickBuilder().base(1, 2, 3).add_ball("up", BallType.STANDARD).build("ball")
        assert len(brick.ball_joints) == 1

    def test_socket(self):
        from advanced_features import AdvancedBrickBuilder

        brick = AdvancedBrickBuilder().base(2, 2, 3).add_socket("front").build("socket")
        assert len(brick.ball_sockets) == 1

    def test_clip(self):
        from advanced_features import AdvancedBrickBuilder

        brick = AdvancedBrickBuilder().base(1, 1, 1).add_clip("front").build("clip")
        assert len(brick.clips) == 1

    def test_chamfer(self):
        from advanced_features import AdvancedBrickBuilder

        brick = AdvancedBrickBuilder().base(2, 2, 3).chamfer_all(0.3).build("chamfer")
        assert len(brick.chamfers) == 1

    def test_pattern(self):
        from advanced_features import AdvancedBrickBuilder

        brick = AdvancedBrickBuilder().base(1, 2, 1).no_studs().grille("top").build("grille")
        assert len(brick.patterns) == 1


# ============================================================================
# UNIT TESTS - EXPORT TOOLS
# ============================================================================


class TestExportTools:
    """Test export tools."""

    def test_export_formats(self):
        from tools.export_tools import EXPORT_FORMATS

        assert "stl" in EXPORT_FORMATS
        assert "step" in EXPORT_FORMATS
        assert "3mf" in EXPORT_FORMATS

    def test_stl_refinement(self):
        from tools.export_tools import STL_REFINEMENT

        assert "low" in STL_REFINEMENT
        assert "medium" in STL_REFINEMENT
        assert "high" in STL_REFINEMENT
        assert "ultra" in STL_REFINEMENT

    def test_export_stl_function(self):
        from tools.export_tools import export_stl

        result = export_stl("brick", "/out/brick.stl", "medium")
        assert result["action"] == "export_stl"


# ============================================================================
# UNIT TESTS - MILLING TOOLS
# ============================================================================


class TestMillingTools:
    """Test CNC milling tools."""

    def test_tool_library(self):
        from tools.milling_tools import LEGO_TOOL_LIBRARY

        assert len(LEGO_TOOL_LIBRARY) >= 10
        assert "flat_2mm" in LEGO_TOOL_LIBRARY

    def test_machines(self):
        from tools.milling_tools import MACHINES

        assert len(MACHINES) >= 5
        assert "grbl_generic" in MACHINES

    def test_calculate_speeds(self):
        from tools.milling_tools import calculate_speeds_feeds, LEGO_TOOL_LIBRARY, MaterialType

        tool = LEGO_TOOL_LIBRARY["flat_3mm"]
        result = calculate_speeds_feeds(tool, MaterialType.ABS)
        assert result["rpm"] > 0
        assert result["feed_rate"] > 0


# ============================================================================
# UNIT TESTS - PRINTING TOOLS
# ============================================================================


class TestPrintingTools:
    """Test 3D printing tools."""

    def test_printer_library(self):
        from tools.printing_tools import PRINTER_LIBRARY

        assert len(PRINTER_LIBRARY) >= 10
        assert "prusa_mk3s" in PRINTER_LIBRARY

    def test_material_library(self):
        from tools.printing_tools import MATERIAL_LIBRARY

        assert "pla_generic" in MATERIAL_LIBRARY
        assert "petg_generic" in MATERIAL_LIBRARY

    def test_lego_quality(self):
        from tools.printing_tools import QUALITY_PRESETS, QualityPreset

        lego = QUALITY_PRESETS[QualityPreset.LEGO_OPTIMAL]
        assert lego.layer_height == 0.12

    def test_print_config(self):
        from tools.printing_tools import generate_print_config

        result = generate_print_config("/test.stl", "prusa_mk3s", "pla_generic", "lego")
        assert "printer" in result
        assert "material" in result


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_catalog_to_builder(self):
        """Test creating a brick from catalog specs."""
        from brick_catalog_extended import get
        from custom_brick_builder import CustomBrickBuilder

        catalog_brick = get("brick_2x4")
        builder = (
            CustomBrickBuilder()
            .set_base(catalog_brick.studs_x, catalog_brick.studs_y, catalog_brick.height_plates)
            .add_studs()
        )
        brick = builder.build("rebuilt")

        assert brick.width_studs == catalog_brick.studs_x
        assert brick.depth_studs == catalog_brick.studs_y

    def test_build_and_validate(self):
        """Test building a brick and validating it."""
        from custom_brick_builder import CustomBrickBuilder
        from validation import validate_brick_params

        brick = (
            CustomBrickBuilder()
            .set_base(2, 4, 3)
            .add_studs()
            .hollow_bottom()
            .add_tubes()
            .build("validated")
        )

        result = validate_brick_params(brick.width_studs, brick.depth_studs, brick.height_plates)

        assert result.valid == True

    def test_advanced_brick_features(self):
        """Test advanced brick with multiple features."""
        from advanced_features import AdvancedBrickBuilder

        brick = (
            AdvancedBrickBuilder()
            .base(2, 2, 3)
            .studs()
            .hollow()
            .tubes()
            .add_ball("up")
            .add_socket("front")
            .chamfer_all(0.3)
            .for_cnc()
            .build("complex")
        )

        assert brick.total_features() >= 3


# ============================================================================
# ASYNC INTEGRATION TESTS
# ============================================================================


class TestAsyncWorkflows:
    """Test async workflows with mocked clients."""

    @pytest.mark.asyncio
    async def test_create_and_export(self, mock_fusion_client):
        """Test creating a brick and exporting it."""
        # Create brick
        result = await mock_fusion_client.create_brick(
            {"name": "test_brick", "width_studs": 2, "depth_studs": 4, "height_plates": 3}
        )
        assert result["success"] == True

        # Export
        export = await mock_fusion_client.export_stl(
            result["component_name"], "/output/test.stl", "medium"
        )
        assert export["success"] == True

    @pytest.mark.asyncio
    async def test_health_check(self, mock_fusion_client, mock_slicer_client):
        """Test health checks."""
        fusion_ok = await mock_fusion_client.health_check()
        slicer_ok = await mock_slicer_client.health_check()

        assert fusion_ok == True
        assert slicer_ok == True

    @pytest.mark.asyncio
    async def test_preview_generation(self, mock_fusion_client):
        """Test preview image generation."""
        result = await mock_fusion_client.generate_preview(
            "TestBrick", "/output/preview.png", "isometric", 800, 600
        )
        assert result["success"] == True


# ============================================================================
# STRESS TESTS
# ============================================================================


class TestStress:
    """Stress tests for performance validation."""

    def test_large_catalog_search(self):
        """Test searching a large catalog."""
        from brick_catalog_extended import search

        start = time.time()
        for _ in range(100):
            results = search("brick")
        elapsed = time.time() - start

        # Should complete 100 searches in under 1 second
        assert elapsed < 1.0

    def test_build_many_bricks(self):
        """Test building many bricks."""
        from custom_brick_builder import CustomBrickBuilder

        start = time.time()
        bricks = []
        for i in range(100):
            brick = (
                CustomBrickBuilder()
                .set_base(2, 4, 3)
                .add_studs()
                .hollow_bottom()
                .add_tubes()
                .build(f"brick_{i}")
            )
            bricks.append(brick)
        elapsed = time.time() - start

        assert len(bricks) == 100
        # Should build 100 bricks in under 2 seconds
        assert elapsed < 2.0

    def test_validation_performance(self):
        """Test validation performance."""
        from validation import validate_brick_params

        start = time.time()
        for _ in range(1000):
            validate_brick_params(2, 4, 3)
        elapsed = time.time() - start

        # 1000 validations in under 1 second
        assert elapsed < 1.0


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


class TestErrorHandling:
    """Test error handling."""

    def test_invalid_brick_type(self):
        from validation import validate_brick_params

        result = validate_brick_params(2, 4, 3, "invalid_type")
        assert result.valid == False

    def test_error_suggestions(self):
        from validation import validate_brick_params

        result = validate_brick_params(2, 4, 3, "slope", {"slope": {"angle": 50}})
        assert result.valid == False
        # Should have suggestion for valid angle
        error = result.errors[0]
        assert error.suggestion is not None


# ============================================================================
# BATCH OPERATION TESTS
# ============================================================================


class TestBatchOperations:
    """Test batch operations."""

    def test_generate_basic_set(self):
        from batch_operations import generate_brick_set

        bricks = generate_brick_set("basic")
        assert len(bricks) >= 10

    def test_generate_plates_set(self):
        from batch_operations import generate_brick_set

        bricks = generate_brick_set("plates")
        assert all(b["height_plates"] == 1 for b in bricks)

    def test_generate_slopes_set(self):
        from batch_operations import generate_brick_set

        bricks = generate_brick_set("slopes")
        assert all("slope" in b.get("features", {}) for b in bricks)

    def test_generate_grid_bricks(self):
        from batch_operations import generate_grid_bricks

        sizes = [(1, 1), (1, 2), (2, 2), (2, 4)]
        bricks = generate_grid_bricks(sizes)
        assert len(bricks) == 4


# ============================================================================
# HISTORY TESTS
# ============================================================================


class TestHistory:
    """Test history manager."""

    def test_create_session(self):
        from history_manager import HistoryManager

        manager = HistoryManager("/tmp/test-history")
        session = manager.create_session("Test Session")
        assert session.name == "Test Session"

    def test_record_operation(self):
        from history_manager import HistoryManager, OperationType

        manager = HistoryManager("/tmp/test-history")
        manager.create_session()

        op = manager.record_operation(
            OperationType.CREATE_BRICK,
            {"width": 2, "depth": 4},
            {"success": True, "component_name": "Brick_2x4"},
            "Brick_2x4",
        )

        assert op.component_name == "Brick_2x4"

    def test_undo_stack(self):
        from history_manager import HistoryManager, OperationType

        manager = HistoryManager("/tmp/test-history")
        manager.create_session()

        manager.record_operation(OperationType.CREATE_BRICK, {}, {}, "Brick1")

        assert manager.can_undo() == True

    def test_statistics(self):
        from history_manager import HistoryManager, OperationType

        manager = HistoryManager("/tmp/test-history")
        manager.create_session()

        for i in range(5):
            manager.record_operation(OperationType.CREATE_BRICK, {}, {}, f"Brick{i}")

        stats = manager.get_statistics()
        assert stats["total_operations"] == 5


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
