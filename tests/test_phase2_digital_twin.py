"""
Phase 2: Digital Twin System Tests

Comprehensive tests for inventory, vision, builds, and workspace services.
"""

import pytest
import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "shared"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp-server", "src"))


class TestInventoryManager:
    """Tests for the inventory management system."""

    @pytest.fixture
    def inventory(self):
        """Create a fresh inventory manager for each test."""
        from dashboard.services.inventory import InventoryManager

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        inv = InventoryManager(storage_path=temp_path)
        yield inv

        # Cleanup
        try:
            os.unlink(temp_path)
        except:
            pass

    def test_add_brick(self, inventory):
        """Test adding bricks to inventory."""
        item = inventory.add_brick(brick_id="brick_2x4", quantity=5, color="red", category="brick")

        assert item.brick_id == "brick_2x4"
        assert item.quantity == 5
        assert item.color == "red"

    def test_add_same_brick_increases_quantity(self, inventory):
        """Test that adding same brick+color increases quantity."""
        inventory.add_brick("brick_2x4", quantity=5, color="red")
        inventory.add_brick("brick_2x4", quantity=3, color="red")

        item = inventory.get_item("brick_2x4", "red")
        assert item.quantity == 8

    def test_different_colors_separate_items(self, inventory):
        """Test that different colors are separate items."""
        inventory.add_brick("brick_2x4", quantity=5, color="red")
        inventory.add_brick("brick_2x4", quantity=3, color="blue")

        red = inventory.get_item("brick_2x4", "red")
        blue = inventory.get_item("brick_2x4", "blue")

        assert red.quantity == 5
        assert blue.quantity == 3

    def test_remove_brick(self, inventory):
        """Test removing bricks."""
        inventory.add_brick("brick_2x4", quantity=5, color="red")

        success = inventory.remove_brick("brick_2x4", "red", 2)
        assert success

        item = inventory.get_item("brick_2x4", "red")
        assert item.quantity == 3

    def test_remove_all_deletes_item(self, inventory):
        """Test that removing all bricks deletes the item."""
        inventory.add_brick("brick_2x4", quantity=5, color="red")
        inventory.remove_brick("brick_2x4", "red", 5)

        item = inventory.get_item("brick_2x4", "red")
        assert item is None

    def test_remove_too_many_fails(self, inventory):
        """Test that removing more than available fails."""
        inventory.add_brick("brick_2x4", quantity=5, color="red")

        success = inventory.remove_brick("brick_2x4", "red", 10)
        assert not success

        item = inventory.get_item("brick_2x4", "red")
        assert item.quantity == 5

    def test_statistics(self, inventory):
        """Test collection statistics."""
        inventory.add_brick("brick_2x4", quantity=10, color="red", category="brick")
        inventory.add_brick("brick_2x2", quantity=5, color="blue", category="brick")
        inventory.add_brick("plate_4x4", quantity=3, color="white", category="plate")

        stats = inventory.get_statistics()

        assert stats.total_pieces == 18
        assert stats.unique_types == 2  # brick_2x4 and brick_2x2 are same type
        assert stats.unique_colors == 3
        assert "brick" in stats.categories
        assert "plate" in stats.categories

    def test_filter_by_category(self, inventory):
        """Test filtering inventory by category."""
        inventory.add_brick("brick_2x4", quantity=10, color="red", category="brick")
        inventory.add_brick("plate_4x4", quantity=3, color="white", category="plate")

        bricks = inventory.get_inventory(category="brick")
        plates = inventory.get_inventory(category="plate")

        assert len(bricks) == 1
        assert len(plates) == 1

    def test_filter_by_color(self, inventory):
        """Test filtering inventory by color."""
        inventory.add_brick("brick_2x4", quantity=10, color="red")
        inventory.add_brick("brick_2x2", quantity=5, color="red")
        inventory.add_brick("plate_4x4", quantity=3, color="blue")

        red_items = inventory.get_inventory(color="red")
        assert len(red_items) == 2

    def test_search(self, inventory):
        """Test searching inventory."""
        inventory.add_brick("brick_2x4", quantity=10, color="red")
        inventory.add_brick("technic_beam_5", quantity=5, color="blue")

        results = inventory.get_inventory(search="technic")
        assert len(results) == 1
        assert results[0].brick_id == "technic_beam_5"

    def test_check_parts(self, inventory):
        """Test checking parts for a build."""
        inventory.add_brick("brick_2x4", quantity=10, color="red")
        inventory.add_brick("brick_2x2", quantity=5, color="blue")

        parts = [
            {"brick_id": "brick_2x4", "color": "red", "quantity": 5},
            {"brick_id": "brick_2x2", "color": "blue", "quantity": 3},
            {"brick_id": "plate_4x4", "color": "white", "quantity": 2},
        ]

        result = inventory.check_parts(parts)

        assert not result["can_build"]
        assert len(result["have"]) == 2
        assert len(result["missing"]) == 1

    def test_export_import_csv(self, inventory):
        """Test CSV export and import."""
        inventory.add_brick("brick_2x4", quantity=10, color="red")
        inventory.add_brick("brick_2x2", quantity=5, color="blue")

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name

        try:
            inventory.export_csv(csv_path)

            # Create new inventory and import
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                new_inv = inventory.__class__(storage_path=f.name)

            count = new_inv.import_csv(csv_path)
            assert count == 2

            stats = new_inv.get_statistics()
            assert stats.total_pieces == 15
        finally:
            os.unlink(csv_path)


class TestWorkspaceState:
    """Tests for workspace state tracking."""

    @pytest.fixture
    def workspace(self):
        """Create a fresh workspace manager."""
        from dashboard.services.inventory import WorkspaceStateManager

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        ws = WorkspaceStateManager(storage_path=temp_path)
        yield ws

        try:
            os.unlink(temp_path)
        except:
            pass

    def test_add_detection(self, workspace):
        """Test adding detections to workspace."""
        detections = [
            {
                "brick_id": "brick_2x4",
                "brick_name": "Brick 2x4",
                "color": "red",
                "color_rgb": (201, 26, 9),
                "confidence": 0.95,
                "center": (100, 100),
                "bbox": (50, 50, 150, 150),
                "grid_position": "A1",
            }
        ]

        result = workspace.update_from_detections(detections)

        assert len(result["added"]) == 1
        assert result["count"] == 1

    def test_update_existing_detection(self, workspace):
        """Test updating an existing brick."""
        detection = {
            "brick_id": "brick_2x4",
            "brick_name": "Brick 2x4",
            "color": "red",
            "color_rgb": (201, 26, 9),
            "confidence": 0.95,
            "center": (100, 100),
            "bbox": (50, 50, 150, 150),
            "grid_position": "A1",
        }

        # Add first detection
        workspace.update_from_detections([detection])

        # Update with same position
        detection["confidence"] = 0.98
        result = workspace.update_from_detections([detection])

        assert len(result["added"]) == 0
        assert len(result["updated"]) == 1
        assert result["count"] == 1

    def test_pixel_to_grid(self, workspace):
        """Test pixel to grid conversion."""
        # Top-left should be A1
        grid = workspace.pixel_to_grid(0, 0)
        assert grid == "A1"

        # Middle should be around D4
        config = workspace.get_config()
        mid_x = (config.roi_x1 + config.roi_x2) // 2
        mid_y = (config.roi_y1 + config.roi_y2) // 2
        grid = workspace.pixel_to_grid(mid_x, mid_y)
        assert grid[0] in "DEFG"  # Around middle columns

    def test_clear_workspace(self, workspace):
        """Test clearing workspace."""
        detection = {
            "brick_id": "brick_2x4",
            "brick_name": "Brick 2x4",
            "color": "red",
            "color_rgb": (201, 26, 9),
            "confidence": 0.95,
            "center": (100, 100),
            "bbox": (50, 50, 150, 150),
            "grid_position": "A1",
        }

        workspace.update_from_detections([detection])
        assert len(workspace.get_current_bricks()) == 1

        workspace.clear()
        assert len(workspace.get_current_bricks()) == 0


class TestBuildPlanner:
    """Tests for build planning system."""

    @pytest.fixture
    def planner(self):
        """Create a fresh build planner."""
        from dashboard.services.builds import BuildPlanner

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = f.name

        bp = BuildPlanner(storage_path=temp_path)
        yield bp

        try:
            os.unlink(temp_path)
        except:
            pass

    def test_create_build(self, planner):
        """Test creating a build."""
        build = planner.create_build(
            name="Test Castle",
            parts=[
                {"brick_id": "brick_2x4", "color": "red", "quantity": 10},
                {"brick_id": "brick_2x2", "color": "blue", "quantity": 5},
            ],
            description="A test castle",
        )

        assert build.name == "Test Castle"
        assert build.total_parts == 15
        assert len(build.parts) == 2

    def test_get_build(self, planner):
        """Test retrieving a build."""
        build = planner.create_build(
            name="Test", parts=[{"brick_id": "brick_2x4", "color": "red", "quantity": 1}]
        )

        retrieved = planner.get_build(build.id)
        assert retrieved.name == "Test"

    def test_delete_build(self, planner):
        """Test deleting a build."""
        build = planner.create_build(
            name="Test", parts=[{"brick_id": "brick_2x4", "color": "red", "quantity": 1}]
        )

        success = planner.delete_build(build.id)
        assert success

        retrieved = planner.get_build(build.id)
        assert retrieved is None

    def test_shopping_list(self, planner):
        """Test generating shopping list."""
        build = planner.create_build(
            name="Test",
            parts=[
                {"brick_id": "brick_2x4", "color": "red", "quantity": 10},
                {"brick_id": "brick_2x2", "color": "blue", "quantity": 5},
            ],
        )

        shopping = planner.generate_shopping_list(build.id)

        assert shopping["build_name"] == "Test"
        assert shopping["total_pieces"] == 15

    def test_export_build(self, planner):
        """Test exporting a build."""
        build = planner.create_build(
            name="Test", parts=[{"brick_id": "brick_2x4", "color": "red", "quantity": 5}]
        )

        # JSON export
        json_export = planner.export_build(build.id, "json")
        data = json.loads(json_export)
        assert data["name"] == "Test"

        # CSV export
        csv_export = planner.export_build(build.id, "csv")
        assert "brick_2x4" in csv_export


class TestVisionDetector:
    """Tests for vision detection system."""

    def test_color_classifier(self):
        """Test LEGO color classification."""
        from dashboard.services.vision import LegoColorClassifier

        classifier = LegoColorClassifier()
        colors = classifier.get_all_colors()

        assert "red" in colors
        assert "blue" in colors
        assert len(colors) >= 30

    def test_detector_info(self):
        """Test detector initialization."""
        from dashboard.services.vision import get_detector

        detector = get_detector()
        info = detector.get_info()

        assert "backend" in info
        assert "confidence_threshold" in info

    def test_mock_detection(self):
        """Test mock detector returns detections."""
        from dashboard.services.vision import LegoDetector, DetectionBackend
        import numpy as np

        detector = LegoDetector(backend=DetectionBackend.MOCK)

        # Create a fake frame
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        detections = detector.detect(frame)

        assert len(detections) > 0
        assert all(hasattr(d, "brick_id") for d in detections)
        assert all(hasattr(d, "confidence") for d in detections)


class TestDashboardRoutes:
    """Tests for dashboard routes."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from dashboard.app import create_app

        app = create_app("testing")
        with app.test_client() as client:
            yield client

    def test_workspace_route(self, client):
        """Test workspace page loads."""
        response = client.get("/workspace/")
        assert response.status_code == 200
        assert b"Workspace" in response.data

    def test_scan_route(self, client):
        """Test scan page loads."""
        response = client.get("/scan/")
        assert response.status_code == 200
        assert b"Scan" in response.data

    def test_collection_route(self, client):
        """Test collection page loads."""
        response = client.get("/collection/")
        assert response.status_code == 200
        assert b"Collection" in response.data

    def test_builds_route(self, client):
        """Test builds page loads."""
        response = client.get("/builds/")
        assert response.status_code == 200
        assert b"Build" in response.data

    def test_insights_route(self, client):
        """Test insights page loads."""
        response = client.get("/insights/")
        assert response.status_code == 200
        assert b"Insights" in response.data

    def test_collection_add_api(self, client):
        """Test adding to collection via API."""
        response = client.post(
            "/collection/add",
            json={"brick_id": "brick_2x4", "color": "red", "quantity": 5},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"]

    def test_collection_stats_api(self, client):
        """Test collection stats API."""
        response = client.get("/collection/stats")

        assert response.status_code == 200
        data = response.get_json()
        assert "total_pieces" in data

    def test_build_create_api(self, client):
        """Test creating a build via API."""
        response = client.post(
            "/builds/create",
            json={
                "name": "Test Build",
                "parts": [{"brick_id": "brick_2x4", "color": "red", "quantity": 5}],
            },
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"]
        assert data["build"]["name"] == "Test Build"

    def test_insights_stats_api(self, client):
        """Test insights stats API."""
        response = client.get("/insights/stats")

        assert response.status_code == 200
        data = response.get_json()
        assert "total_pieces" in data


class TestIntegration:
    """Integration tests for the complete workflow."""

    def test_full_workflow(self):
        """Test complete scanning and building workflow."""
        from dashboard.services.inventory import InventoryManager
        from dashboard.services.builds import BuildPlanner

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            inv_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            build_path = f.name

        try:
            # 1. Add bricks to inventory (simulating scan)
            inventory = InventoryManager(storage_path=inv_path)
            inventory.add_brick("brick_2x4", quantity=20, color="red")
            inventory.add_brick("brick_2x2", quantity=10, color="blue")
            inventory.add_brick("plate_4x4", quantity=5, color="white")

            # 2. Create a build
            planner = BuildPlanner(storage_path=build_path)
            build = planner.create_build(
                name="Simple House",
                parts=[
                    {"brick_id": "brick_2x4", "color": "red", "quantity": 15},
                    {"brick_id": "brick_2x2", "color": "blue", "quantity": 8},
                    {"brick_id": "slope_45_2x2", "color": "red", "quantity": 4},  # Don't have this
                ],
            )

            # 3. Check if we can build it
            # Note: check_build uses the global inventory, so we need to mock or
            # use the same instance. For now, manually check parts.
            parts_check = inventory.check_parts(
                [
                    {"brick_id": "brick_2x4", "color": "red", "quantity": 15},
                    {"brick_id": "brick_2x2", "color": "blue", "quantity": 8},
                    {"brick_id": "slope_45_2x2", "color": "red", "quantity": 4},
                ]
            )

            # 4. Verify results
            assert not parts_check["can_build"]  # Missing slopes
            assert len(parts_check["have"]) == 2
            assert len(parts_check["missing"]) == 1
            assert parts_check["missing"][0]["brick_id"] == "slope_45_2x2"

            # 5. Add missing parts
            inventory.add_brick("slope_45_2x2", quantity=4, color="red")

            # 6. Check again
            parts_check = inventory.check_parts(
                [
                    {"brick_id": "brick_2x4", "color": "red", "quantity": 15},
                    {"brick_id": "brick_2x2", "color": "blue", "quantity": 8},
                    {"brick_id": "slope_45_2x2", "color": "red", "quantity": 4},
                ]
            )

            assert parts_check["can_build"]

        finally:
            os.unlink(inv_path)
            os.unlink(build_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
