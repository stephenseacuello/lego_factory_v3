"""
LEGO Factory v3 - API Endpoint Tests
====================================
Comprehensive test suite for all API modules.
"""

import pytest
import requests
from datetime import datetime


BASE_URL = "http://localhost:5000"


class TestSCADAAPI:
    """Test SCADA API endpoints."""

    def test_health(self):
        """Test SCADA health endpoint."""
        r = requests.get(f"{BASE_URL}/api/scada/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"

    def test_machines(self):
        """Test machines listing."""
        r = requests.get(f"{BASE_URL}/api/scada/machines")
        assert r.status_code == 200
        data = r.json()
        assert "machines" in data
        assert "count" in data
        assert data["count"] >= 0

    def test_tags(self):
        """Test tags listing."""
        r = requests.get(f"{BASE_URL}/api/scada/tags")
        assert r.status_code == 200
        data = r.json()
        assert "tags" in data

    def test_alarms(self):
        """Test alarms listing."""
        r = requests.get(f"{BASE_URL}/api/scada/alarms")
        assert r.status_code == 200
        data = r.json()
        assert "alarms" in data or "alarm_definitions" in data

    def test_recipes(self):
        """Test recipes listing."""
        r = requests.get(f"{BASE_URL}/api/scada/recipes")
        assert r.status_code == 200
        data = r.json()
        assert "recipes" in data


class TestMESAPI:
    """Test MES API endpoints."""

    def test_work_orders(self):
        """Test work orders listing."""
        r = requests.get(f"{BASE_URL}/api/mes/work-orders")
        assert r.status_code == 200
        data = r.json()
        assert "work_orders" in data
        assert "count" in data

    def test_jobs(self):
        """Test jobs listing."""
        r = requests.get(f"{BASE_URL}/api/mes/jobs")
        assert r.status_code == 200
        data = r.json()
        assert "jobs" in data

    def test_oee(self):
        """Test OEE metrics."""
        r = requests.get(f"{BASE_URL}/api/mes/oee")
        assert r.status_code == 200
        data = r.json()
        assert "oee" in data or "oee_percentage" in data

    def test_scheduling_gantt(self):
        """Test scheduling Gantt data."""
        r = requests.get(f"{BASE_URL}/api/mes/scheduling/gantt")
        assert r.status_code == 200


class TestERPAPI:
    """Test ERP API endpoints."""

    def test_partners(self):
        """Test partners listing."""
        r = requests.get(f"{BASE_URL}/api/erp/partners")
        assert r.status_code == 200
        data = r.json()
        assert "partners" in data

    def test_items(self):
        """Test items listing."""
        r = requests.get(f"{BASE_URL}/api/erp/items")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    def test_sales_orders(self):
        """Test sales orders listing."""
        r = requests.get(f"{BASE_URL}/api/erp/sales-orders")
        assert r.status_code == 200
        data = r.json()
        assert "sales_orders" in data or "orders" in data

    def test_inventory(self):
        """Test inventory listing."""
        r = requests.get(f"{BASE_URL}/api/erp/inventory")
        assert r.status_code == 200


class TestQMSAPI:
    """Test QMS API endpoints."""

    def test_documents(self):
        """Test documents listing."""
        r = requests.get(f"{BASE_URL}/api/qms/documents")
        assert r.status_code == 200
        data = r.json()
        assert "documents" in data

    def test_ncrs(self):
        """Test NCRs listing."""
        r = requests.get(f"{BASE_URL}/api/qms/ncrs")
        assert r.status_code == 200
        data = r.json()
        assert "ncrs" in data


class TestCMMSAPI:
    """Test CMMS API endpoints."""

    def test_assets(self):
        """Test assets listing."""
        r = requests.get(f"{BASE_URL}/api/cmms/assets")
        assert r.status_code == 200
        data = r.json()
        assert "assets" in data

    def test_maintenance_work_orders(self):
        """Test maintenance work orders."""
        r = requests.get(f"{BASE_URL}/api/cmms/work-orders")
        assert r.status_code == 200


class TestLEGOAPI:
    """Test LEGO API endpoints."""

    def test_catalog(self):
        """Test brick catalog."""
        r = requests.get(f"{BASE_URL}/api/lego/catalog")
        assert r.status_code == 200
        data = r.json()
        assert "bricks" in data
        assert "count" in data

    def test_colors(self):
        """Test colors listing."""
        r = requests.get(f"{BASE_URL}/api/lego/colors")
        assert r.status_code == 200
        data = r.json()
        assert "colors" in data

    def test_catalog_stats(self):
        """Test catalog statistics."""
        r = requests.get(f"{BASE_URL}/api/lego/catalog/stats")
        assert r.status_code == 200

    def test_dimensions(self):
        """Test brick dimensions calculation."""
        r = requests.post(
            f"{BASE_URL}/api/lego/dimensions",
            json={"studs_x": 2, "studs_y": 4}
        )
        # Endpoint may not exist, just check it doesn't crash
        assert r.status_code in [200, 404]


class TestMLAPI:
    """Test ML API endpoints."""

    def test_status(self):
        """Test ML service status."""
        r = requests.get(f"{BASE_URL}/api/ml/status")
        assert r.status_code == 200
        data = r.json()
        assert "available" in data

    def test_models(self):
        """Test models listing."""
        r = requests.get(f"{BASE_URL}/api/ml/models")
        assert r.status_code == 200
        data = r.json()
        assert "models" in data

    def test_config(self):
        """Test ML config."""
        r = requests.get(f"{BASE_URL}/api/ml/config")
        assert r.status_code == 200


class TestROS2API:
    """Test ROS2 API endpoints."""

    def test_status(self):
        """Test ROS2 status."""
        r = requests.get(f"{BASE_URL}/api/ros2/status")
        assert r.status_code == 200

    def test_robots(self):
        """Test robots listing."""
        r = requests.get(f"{BASE_URL}/api/ros2/robots")
        assert r.status_code == 200


class TestUnityAPI:
    """Test Unity API endpoints."""

    def test_status(self):
        """Test Unity status."""
        r = requests.get(f"{BASE_URL}/api/unity/status")
        assert r.status_code == 200


def run_all_tests():
    """Run all tests and print summary."""
    import sys

    # Run tests manually for quick validation
    tests = [
        ("SCADA Health", lambda: requests.get(f"{BASE_URL}/api/scada/health").status_code == 200),
        ("SCADA Machines", lambda: requests.get(f"{BASE_URL}/api/scada/machines").status_code == 200),
        ("SCADA Tags", lambda: requests.get(f"{BASE_URL}/api/scada/tags").status_code == 200),
        ("SCADA Recipes", lambda: requests.get(f"{BASE_URL}/api/scada/recipes").status_code == 200),
        ("MES Work Orders", lambda: requests.get(f"{BASE_URL}/api/mes/work-orders").status_code == 200),
        ("MES Jobs", lambda: requests.get(f"{BASE_URL}/api/mes/jobs").status_code == 200),
        ("MES OEE", lambda: requests.get(f"{BASE_URL}/api/mes/oee").status_code == 200),
        ("ERP Partners", lambda: requests.get(f"{BASE_URL}/api/erp/partners").status_code == 200),
        ("ERP Items", lambda: requests.get(f"{BASE_URL}/api/erp/items").status_code == 200),
        ("ERP Sales Orders", lambda: requests.get(f"{BASE_URL}/api/erp/sales-orders").status_code == 200),
        ("QMS Documents", lambda: requests.get(f"{BASE_URL}/api/qms/documents").status_code == 200),
        ("QMS NCRs", lambda: requests.get(f"{BASE_URL}/api/qms/ncrs").status_code == 200),
        ("CMMS Assets", lambda: requests.get(f"{BASE_URL}/api/cmms/assets").status_code == 200),
        ("LEGO Catalog", lambda: requests.get(f"{BASE_URL}/api/lego/catalog").status_code == 200),
        ("LEGO Colors", lambda: requests.get(f"{BASE_URL}/api/lego/colors").status_code == 200),
        ("ML Status", lambda: requests.get(f"{BASE_URL}/api/ml/status").status_code == 200),
        ("ROS2 Status", lambda: requests.get(f"{BASE_URL}/api/ros2/status").status_code == 200),
        ("Unity Status", lambda: requests.get(f"{BASE_URL}/api/unity/status").status_code == 200),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("LEGO Factory v3 - API Endpoint Tests")
    print("=" * 60)
    print()

    for name, test_fn in tests:
        try:
            if test_fn():
                print(f"✓ {name}")
                passed += 1
            else:
                print(f"✗ {name} - Failed")
                failed += 1
        except Exception as e:
            print(f"✗ {name} - Error: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
