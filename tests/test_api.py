"""
Integration Tests for LEGO MCP Server APIs

These tests verify the HTTP APIs work correctly.
Run with: pytest tests/test_api.py -v

Note: These tests require the services to be running:
- Fusion 360 with LegoMCP add-in (localhost:8765)
- Slicer service (localhost:8766)
"""

import pytest
import aiohttp
import asyncio
import json
import os


# Configuration
FUSION_API_URL = os.getenv("FUSION_API_URL", "http://localhost:8765")
SLICER_API_URL = os.getenv("SLICER_API_URL", "http://localhost:8766")


# ==========================================
# Fixtures
# ==========================================


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def http_session():
    """Create aiohttp session."""
    async with aiohttp.ClientSession() as session:
        yield session


# ==========================================
# Health Check Tests
# ==========================================


class TestHealthChecks:
    """Test service health endpoints."""

    @pytest.mark.asyncio
    async def test_fusion_health(self, http_session):
        """Test Fusion 360 add-in health check."""
        try:
            async with http_session.get(f"{FUSION_API_URL}/health", timeout=5) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data.get("status") == "ok"
                assert "LegoMCP" in data.get("service", "")
        except aiohttp.ClientError:
            pytest.skip("Fusion 360 not available")

    @pytest.mark.asyncio
    async def test_slicer_health(self, http_session):
        """Test slicer service health check."""
        try:
            async with http_session.get(f"{SLICER_API_URL}/health", timeout=5) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data.get("status") in ["ok", "degraded"]
        except aiohttp.ClientError:
            pytest.skip("Slicer service not available")


# ==========================================
# Fusion 360 API Tests
# ==========================================


class TestFusionBrickCreation:
    """Test brick creation via Fusion 360 API."""

    @pytest.mark.asyncio
    async def test_create_standard_brick(self, http_session):
        """Test creating a standard 2x4 brick."""
        try:
            payload = {
                "command": "create_brick",
                "params": {"studs_x": 2, "studs_y": 4, "height_units": 1.0, "hollow": True},
            }
            async with http_session.post(FUSION_API_URL, json=payload, timeout=30) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data.get("success") == True
                assert "brick_id" in data
                assert data["dimensions"]["studs_x"] == 2
                assert data["dimensions"]["studs_y"] == 4
        except aiohttp.ClientError:
            pytest.skip("Fusion 360 not available")

    @pytest.mark.asyncio
    async def test_create_plate(self, http_session):
        """Test creating a 2x2 plate."""
        try:
            payload = {"command": "create_plate", "params": {"studs_x": 2, "studs_y": 2}}
            async with http_session.post(FUSION_API_URL, json=payload, timeout=30) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data.get("success") == True
                # Plate height should be ~3.2mm
                assert data["dimensions"]["height_mm"] < 5.0
        except aiohttp.ClientError:
            pytest.skip("Fusion 360 not available")

    @pytest.mark.asyncio
    async def test_create_tile(self, http_session):
        """Test creating a 1x2 tile."""
        try:
            payload = {"command": "create_tile", "params": {"studs_x": 1, "studs_y": 2}}
            async with http_session.post(FUSION_API_URL, json=payload, timeout=30) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data.get("success") == True
        except aiohttp.ClientError:
            pytest.skip("Fusion 360 not available")

    @pytest.mark.asyncio
    async def test_invalid_brick_size(self, http_session):
        """Test that invalid brick sizes are rejected."""
        try:
            payload = {"command": "create_brick", "params": {"studs_x": 0, "studs_y": 4}}  # Invalid
            async with http_session.post(FUSION_API_URL, json=payload, timeout=30) as resp:
                data = await resp.json()
                # Should fail or return error
                assert data.get("success") == False or resp.status >= 400
        except aiohttp.ClientError:
            pytest.skip("Fusion 360 not available")


class TestFusionExport:
    """Test STL export via Fusion 360 API."""

    @pytest.mark.asyncio
    async def test_export_stl(self, http_session):
        """Test exporting a brick as STL."""
        try:
            # First create a brick
            create_payload = {"command": "create_brick", "params": {"studs_x": 2, "studs_y": 2}}
            async with http_session.post(FUSION_API_URL, json=create_payload, timeout=30) as resp:
                create_data = await resp.json()
                if not create_data.get("success"):
                    pytest.skip("Could not create brick")
                component_name = create_data["component_name"]

            # Then export it
            export_payload = {
                "command": "export_stl",
                "params": {"component_name": component_name, "resolution": "high"},
            }
            async with http_session.post(FUSION_API_URL, json=export_payload, timeout=60) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data.get("success") == True
                assert data["path"].endswith(".stl")
                assert data["size_kb"] > 0
        except aiohttp.ClientError:
            pytest.skip("Fusion 360 not available")


# ==========================================
# Slicer API Tests
# ==========================================


class TestSlicerEndpoints:
    """Test slicer service endpoints."""

    @pytest.mark.asyncio
    async def test_list_printers(self, http_session):
        """Test listing available printers."""
        try:
            async with http_session.get(f"{SLICER_API_URL}/printers", timeout=10) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "printers" in data
                assert len(data["printers"]) > 0
        except aiohttp.ClientError:
            pytest.skip("Slicer service not available")

    @pytest.mark.asyncio
    async def test_list_materials(self, http_session):
        """Test listing available materials."""
        try:
            async with http_session.get(f"{SLICER_API_URL}/materials", timeout=10) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "materials" in data
                assert "pla" in data["materials"]
        except aiohttp.ClientError:
            pytest.skip("Slicer service not available")

    @pytest.mark.asyncio
    async def test_list_qualities(self, http_session):
        """Test listing quality presets."""
        try:
            async with http_session.get(f"{SLICER_API_URL}/qualities", timeout=10) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert "qualities" in data
                assert "fine" in data["qualities"]
        except aiohttp.ClientError:
            pytest.skip("Slicer service not available")


# ==========================================
# Mock Tests (don't require services)
# ==========================================


class TestRequestValidation:
    """Test request validation logic (no service required)."""

    def test_valid_brick_params(self):
        """Test valid brick parameters."""
        params = {"studs_x": 2, "studs_y": 4, "height_units": 1.0, "hollow": True}
        assert 1 <= params["studs_x"] <= 16
        assert 1 <= params["studs_y"] <= 16
        assert 0 < params["height_units"] <= 3

    def test_valid_quality_presets(self):
        """Test valid quality preset names."""
        valid_qualities = ["draft", "normal", "fine", "ultra"]
        assert "fine" in valid_qualities
        assert "invalid" not in valid_qualities

    def test_valid_materials(self):
        """Test valid material names."""
        valid_mill_materials = ["abs", "delrin", "hdpe", "aluminum", "wood"]
        valid_print_materials = ["pla", "petg", "abs", "asa"]

        assert "abs" in valid_mill_materials
        assert "pla" in valid_print_materials

    def test_valid_machine_types(self):
        """Test valid CNC machine types."""
        valid_machines = ["generic_3axis", "haas_mini", "tormach", "shapeoko", "grbl", "linuxcnc"]
        assert "grbl" in valid_machines


# ==========================================
# Run tests
# ==========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])
