"""
LEGO Factory v3 - API Integration Tests
=======================================
"""

import pytest
import json


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns healthy status."""
        response = client.get('/health')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'status' in data
        assert data['status'] in ['healthy', 'degraded']


class TestSCADAAPI:
    """Tests for SCADA API endpoints."""

    def test_list_machines(self, client):
        """Test listing machines."""
        response = client.get('/api/scada/machines')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'machines' in data or isinstance(data, list)

    def test_get_active_alarms(self, client):
        """Test getting active alarms."""
        response = client.get('/api/scada/alarms/active')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'alarms' in data or 'count' in data


class TestMESAPI:
    """Tests for MES API endpoints."""

    def test_list_work_orders(self, client):
        """Test listing work orders."""
        response = client.get('/api/mes/work-orders')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'work_orders' in data or 'count' in data

    def test_list_jobs(self, client):
        """Test listing jobs."""
        response = client.get('/api/mes/jobs')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'jobs' in data or 'count' in data

    def test_get_oee(self, client):
        """Test getting OEE metrics."""
        response = client.get('/api/mes/oee')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'overall_oee' in data or 'oee' in data

    def test_list_recipes(self, client):
        """Test listing recipes."""
        response = client.get('/api/mes/recipes')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'recipes' in data or isinstance(data, list)


class TestERPAPI:
    """Tests for ERP API endpoints."""

    def test_list_customers(self, client):
        """Test listing customers."""
        response = client.get('/api/erp/customers')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'customers' in data or 'count' in data

    def test_list_sales_orders(self, client):
        """Test listing sales orders."""
        response = client.get('/api/erp/sales-orders')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'orders' in data or 'count' in data

    def test_list_items(self, client):
        """Test listing inventory items."""
        response = client.get('/api/erp/items')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'items' in data or 'count' in data


class TestLEGOAPI:
    """Tests for LEGO API endpoints."""

    def test_get_catalog(self, client):
        """Test getting brick catalog."""
        response = client.get('/api/lego/catalog')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'bricks' in data or 'catalog' in data

    def test_get_dimensions(self, client):
        """Test getting brick dimensions."""
        response = client.get('/api/lego/dimensions/2x4')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'width_mm' in data or 'dimensions' in data or 'dimensions_mm' in data

    def test_get_colors(self, client):
        """Test getting LEGO colors."""
        response = client.get('/api/lego/colors')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'colors' in data
        assert 'count' in data

    def test_list_designs(self, client):
        """Test listing brick designs."""
        response = client.get('/api/lego/designs')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'designs' in data or isinstance(data, list)


class TestQMSAPI:
    """Tests for QMS API endpoints."""

    def test_list_documents(self, client):
        """Test listing documents."""
        response = client.get('/api/qms/documents')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'documents' in data or 'count' in data

    def test_list_ncrs(self, client):
        """Test listing NCRs."""
        response = client.get('/api/qms/ncrs')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'ncrs' in data or 'count' in data


class TestMLAPI:
    """Tests for ML API endpoints."""

    def test_ml_status(self, client):
        """Test ML status endpoint."""
        response = client.get('/api/ml/status')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'available' in data


class TestMCPAPI:
    """Tests for MCP API endpoints."""

    def test_list_tools(self, client):
        """Test listing MCP tools."""
        response = client.get('/api/mcp/tools')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'tools' in data or 'count' in data


class TestUnityAPI:
    """Tests for Unity Digital Twin API endpoints."""

    def test_get_scene(self, client):
        """Test getting scene state."""
        response = client.get('/api/unity/scene')
        assert response.status_code == 200

        data = json.loads(response.data)
        # Scene should return some state data
        assert isinstance(data, dict)

    def test_get_entities(self, client):
        """Test getting entities."""
        response = client.get('/api/unity/entities')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'entities' in data or isinstance(data, list)


class TestROS2API:
    """Tests for ROS2 Robotics API endpoints."""

    def test_bridge_status(self, client):
        """Test ROS2 bridge status."""
        response = client.get('/api/ros2/bridge/status')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'connected' in data or 'status' in data

    def test_list_robots(self, client):
        """Test listing robots."""
        response = client.get('/api/ros2/robots')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'robots' in data or isinstance(data, list)

    def test_orchestrator_status(self, client):
        """Test cell orchestrator status."""
        response = client.get('/api/ros2/orchestrator/status')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, dict)

    def test_list_cells(self, client):
        """Test listing factory cells."""
        response = client.get('/api/ros2/cells')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert 'cells' in data or isinstance(data, list)
