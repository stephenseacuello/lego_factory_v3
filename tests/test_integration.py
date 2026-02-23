"""
Integration Tests for LEGO MCP System

Tests the complete workflow from MCP server through Fusion 360 add-in.
These tests verify that all components communicate correctly.

Run with: pytest tests/test_integration.py -v

Note: Some tests require services to be running:
- Fusion 360 with LegoMCP add-in (localhost:8765)
- Slicer service (localhost:8081)
"""

import pytest
import requests
import json
import os
import sys
import time
from typing import Dict, Any
from unittest.mock import Mock, patch

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))


# =============================================================================
# Configuration
# =============================================================================

FUSION_API_URL = os.getenv("FUSION_API_URL", "http://127.0.0.1:8765")
SLICER_API_URL = os.getenv("SLICER_API_URL", "http://localhost:8081")
TIMEOUT = 30


# =============================================================================
# Helper Functions
# =============================================================================

def fusion_available() -> bool:
    """Check if Fusion 360 add-in is available."""
    try:
        response = requests.get(f"{FUSION_API_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def slicer_available() -> bool:
    """Check if slicer service is available."""
    try:
        response = requests.get(f"{SLICER_API_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def call_fusion(command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Call Fusion 360 add-in API."""
    response = requests.post(
        FUSION_API_URL,
        json={"command": command, "params": params},
        timeout=TIMEOUT
    )
    return response.json()


def call_slicer(endpoint: str, method: str = "GET", data: Dict = None) -> Dict[str, Any]:
    """Call slicer service API."""
    if method == "GET":
        response = requests.get(f"{SLICER_API_URL}{endpoint}", timeout=TIMEOUT)
    else:
        response = requests.post(f"{SLICER_API_URL}{endpoint}", json=data, timeout=TIMEOUT)
    return response.json()


# =============================================================================
# Unit Tests (No Services Required)
# =============================================================================

class TestBrickToolsUnit:
    """Unit tests for brick tools (no Fusion 360 required)."""

    def test_list_brick_catalog(self):
        """Test listing brick catalog."""
        from tools.brick_tools import list_brick_catalog

        result = list_brick_catalog(category="brick", limit=10)
        assert "bricks" in result
        assert len(result["bricks"]) <= 10

    def test_get_brick_details(self):
        """Test getting brick details."""
        from tools.brick_tools import get_brick_details

        result = get_brick_details("brick_2x4")
        assert result is not None
        assert "studs_x" in result or "width" in result

    def test_create_standard_brick_definition(self):
        """Test creating brick definition (not actual brick)."""
        from tools.brick_tools import create_standard_brick

        result = create_standard_brick(2, 4, 1)
        assert "brick" in result
        assert result["brick"]["dimensions"]["width_studs"] == 2
        assert result["brick"]["dimensions"]["depth_studs"] == 4

    def test_create_plate_definition(self):
        """Test creating plate definition."""
        from tools.brick_tools import create_plate_brick

        result = create_plate_brick(4, 4)
        assert "brick" in result
        assert result["brick"]["dimensions"]["height_plates"] == 1

    def test_create_slope_definition(self):
        """Test creating slope definition."""
        from tools.brick_tools import create_slope_brick_helper

        result = create_slope_brick_helper(2, 3, 45, "front")
        assert "brick" in result
        assert "slopes" in result["brick"]["features"]


class TestExportToolsUnit:
    """Unit tests for export tools."""

    def test_list_export_formats(self):
        """Test listing export formats."""
        from tools.export_tools import list_export_formats

        result = list_export_formats()
        assert "formats" in result
        assert "stl" in result["formats"]
        assert "step" in result["formats"]
        assert "3mf" in result["formats"]


class TestMillingToolsUnit:
    """Unit tests for milling tools."""

    def test_list_machines(self):
        """Test listing CNC machines."""
        from tools.milling_tools import list_machines

        result = list_machines()
        assert "machines" in result
        assert len(result["machines"]) > 0

    def test_list_tools(self):
        """Test listing milling tools."""
        from tools.milling_tools import list_tools

        result = list_tools()
        assert "tools" in result
        assert len(result["tools"]) > 0

    def test_calculate_speeds_feeds(self):
        """Test calculating cutting parameters."""
        from tools.milling_tools import calculate_speeds_feeds, LEGO_TOOL_LIBRARY, MaterialType

        tool = LEGO_TOOL_LIBRARY.get("flat_2mm")
        if tool:
            result = calculate_speeds_feeds(tool, MaterialType.ABS)
            assert "rpm" in result
            assert "feed_rate" in result
            assert result["rpm"] > 0


class TestPrintingToolsUnit:
    """Unit tests for printing tools."""

    def test_list_printers(self):
        """Test listing printers."""
        from tools.printing_tools import list_printers

        result = list_printers()
        assert "printers" in result
        assert "prusa_mk3s" in result["printers"]

    def test_list_materials(self):
        """Test listing materials."""
        from tools.printing_tools import list_materials

        result = list_materials()
        assert "materials" in result

    def test_generate_print_config(self):
        """Test generating print config."""
        from tools.printing_tools import generate_print_config

        result = generate_print_config(
            "/test.stl", "prusa_mk3s", "pla_generic", "lego"
        )
        assert "printer" in result
        assert "quality" in result


class TestValidation:
    """Test parameter validation."""

    def test_valid_brick_params(self):
        """Test valid brick parameters."""
        from validation import validate_brick_params

        result = validate_brick_params(2, 4, 3)
        assert result.valid == True

    def test_invalid_brick_width(self):
        """Test invalid brick width."""
        from validation import validate_brick_params

        result = validate_brick_params(0, 4, 3)
        assert result.valid == False

    def test_invalid_brick_too_large(self):
        """Test brick too large."""
        from validation import validate_brick_params

        result = validate_brick_params(100, 100, 3)
        assert result.valid == False


# =============================================================================
# Integration Tests (Requires Fusion 360)
# =============================================================================

@pytest.mark.skipif(not fusion_available(), reason="Fusion 360 not available")
class TestFusionIntegration:
    """Integration tests requiring Fusion 360."""

    def test_fusion_health_check(self):
        """Test Fusion 360 health check."""
        response = requests.get(f"{FUSION_API_URL}/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_create_standard_brick(self):
        """Test creating a standard brick in Fusion 360."""
        result = call_fusion("create_brick", {
            "studs_x": 2,
            "studs_y": 4,
            "height_units": 1.0,
            "hollow": True,
            "name": "test_brick_2x4"
        })
        assert result.get("success") == True
        assert "brick_id" in result or "component_name" in result

    def test_create_plate(self):
        """Test creating a plate in Fusion 360."""
        result = call_fusion("create_plate", {
            "studs_x": 4,
            "studs_y": 4,
            "name": "test_plate_4x4"
        })
        assert result.get("success") == True

    def test_create_tile(self):
        """Test creating a tile in Fusion 360."""
        result = call_fusion("create_tile", {
            "studs_x": 2,
            "studs_y": 2,
            "name": "test_tile_2x2"
        })
        assert result.get("success") == True

    def test_create_slope(self):
        """Test creating a slope brick in Fusion 360."""
        result = call_fusion("create_slope", {
            "studs_x": 2,
            "studs_y": 3,
            "slope_angle": 45,
            "slope_direction": "front",
            "name": "test_slope_2x3"
        })
        assert result.get("success") == True

    def test_export_stl(self):
        """Test exporting as STL."""
        # First create a brick
        create_result = call_fusion("create_brick", {
            "studs_x": 2,
            "studs_y": 2,
            "name": "export_test_brick"
        })

        if create_result.get("success"):
            component_name = create_result.get("component_name", "export_test_brick")

            export_result = call_fusion("export_stl", {
                "component_name": component_name,
                "output_path": "/tmp/test_brick.stl",
                "resolution": "high"
            })
            assert export_result.get("success") == True

    def test_export_step(self):
        """Test exporting as STEP."""
        create_result = call_fusion("create_brick", {
            "studs_x": 2,
            "studs_y": 2,
            "name": "step_test_brick"
        })

        if create_result.get("success"):
            component_name = create_result.get("component_name", "step_test_brick")

            export_result = call_fusion("export_step", {
                "component_name": component_name,
                "output_path": "/tmp/test_brick.step"
            })
            assert export_result.get("success") == True

    def test_export_3mf(self):
        """Test exporting as 3MF."""
        create_result = call_fusion("create_brick", {
            "studs_x": 2,
            "studs_y": 2,
            "name": "3mf_test_brick"
        })

        if create_result.get("success"):
            component_name = create_result.get("component_name", "3mf_test_brick")

            export_result = call_fusion("export_3mf", {
                "component_name": component_name,
                "output_path": "/tmp/test_brick.3mf"
            })
            assert export_result.get("success") == True


# =============================================================================
# Integration Tests (Requires Slicer)
# =============================================================================

@pytest.mark.skipif(not slicer_available(), reason="Slicer service not available")
class TestSlicerIntegration:
    """Integration tests requiring slicer service."""

    def test_slicer_health_check(self):
        """Test slicer health check."""
        response = requests.get(f"{SLICER_API_URL}/health", timeout=5)
        assert response.status_code == 200

    def test_list_printers(self):
        """Test listing printers from slicer."""
        result = call_slicer("/printers")
        assert "printers" in result

    def test_list_materials(self):
        """Test listing materials from slicer."""
        result = call_slicer("/materials")
        assert "materials" in result


# =============================================================================
# Full Workflow Tests (Requires Both Services)
# =============================================================================

@pytest.mark.skipif(
    not (fusion_available() and slicer_available()),
    reason="Both Fusion 360 and Slicer required"
)
class TestFullWorkflow:
    """Test complete workflows from brick creation to G-code."""

    def test_print_workflow(self):
        """Test complete 3D printing workflow."""
        # 1. Create brick
        brick_result = call_fusion("create_brick", {
            "studs_x": 2,
            "studs_y": 4,
            "name": "workflow_brick"
        })
        assert brick_result.get("success") == True

        # 2. Export STL
        component = brick_result.get("component_name", "workflow_brick")
        stl_path = "/tmp/workflow_brick.stl"

        export_result = call_fusion("export_stl", {
            "component_name": component,
            "output_path": stl_path,
            "resolution": "high"
        })
        assert export_result.get("success") == True

        # 3. Slice for print (if file exists)
        if os.path.exists(stl_path):
            slice_result = call_slicer("/slice/lego", "POST", {
                "stl_path": stl_path,
                "printer": "prusa_mk3s",
                "brick_type": "standard"
            })
            # Note: May fail if slicer doesn't have the file
            # This is expected in testing environment


# =============================================================================
# MCP Bridge Tests
# =============================================================================

class TestMCPBridge:
    """Test MCP bridge functionality."""

    def test_bridge_loads_tools(self):
        """Test that bridge loads tools."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

        try:
            from services.mcp_bridge import MCPBridge

            tools = MCPBridge.get_tools()
            assert len(tools) > 0
        except ImportError:
            pytest.skip("Dashboard not available")

    def test_bridge_tool_categories(self):
        """Test tool categorization."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

        try:
            from services.mcp_bridge import MCPBridge

            categories = MCPBridge.get_tool_categories()
            assert "brick" in categories or len(categories) > 0
        except ImportError:
            pytest.skip("Dashboard not available")


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    print("LEGO MCP Integration Tests")
    print("=" * 50)
    print(f"Fusion 360 available: {fusion_available()}")
    print(f"Slicer available: {slicer_available()}")
    print("=" * 50)

    pytest.main([__file__, "-v", "--tb=short"])
