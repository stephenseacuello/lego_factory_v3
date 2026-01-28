"""
LEGO Factory v3 - ERP/QMS/CMMS API Integration Tests
====================================================
Tests for ERP, QMS, and CMMS API endpoints.
"""

import pytest
from datetime import datetime, timedelta


@pytest.mark.integration
class TestERPInventoryAPI:
    """Test ERP inventory management endpoints."""

    def test_list_inventory(self, client):
        """Test listing inventory items."""
        response = client.get('/api/v1/erp/inventory')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, (list, dict))

    def test_get_item(self, client):
        """Test getting specific inventory item."""
        response = client.get('/api/v1/erp/inventory/LEGO-2x4-RED')
        assert response.status_code in [200, 404]

    def test_update_inventory(self, client):
        """Test updating inventory quantity."""
        data = {
            'item_id': 'LEGO-2x4-RED',
            'quantity_change': 100,
            'reason': 'Production receipt',
        }
        response = client.post('/api/v1/erp/inventory/adjust', json=data)
        assert response.status_code in [200, 202]


@pytest.mark.integration
class TestERPSalesAPI:
    """Test ERP sales order endpoints."""

    def test_list_sales_orders(self, client):
        """Test listing sales orders."""
        response = client.get('/api/v1/erp/sales-orders')
        assert response.status_code == 200

    def test_create_sales_order(self, client):
        """Test creating a sales order."""
        data = {
            'customer_id': 'CUST-001',
            'lines': [
                {'item_id': 'LEGO-2x4-RED', 'quantity': 100},
                {'item_id': 'LEGO-2x4-BLUE', 'quantity': 50},
            ],
            'due_date': (datetime.utcnow() + timedelta(days=14)).isoformat(),
        }
        response = client.post('/api/v1/erp/sales-orders', json=data)
        assert response.status_code in [200, 201]

    def test_get_sales_order(self, client):
        """Test getting a sales order."""
        response = client.get('/api/v1/erp/sales-orders/SO-001')
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestERPMRPAPI:
    """Test ERP Material Requirements Planning endpoints."""

    def test_run_mrp(self, client):
        """Test running MRP calculation."""
        data = {
            'horizon_days': 30,
            'include_safety_stock': True,
        }
        response = client.post('/api/v1/erp/mrp/run', json=data)
        assert response.status_code in [200, 202]

    def test_mrp_suggestions(self, client):
        """Test getting MRP suggestions."""
        response = client.get('/api/v1/erp/mrp/suggestions')
        assert response.status_code == 200


@pytest.mark.integration
class TestQMSDocumentAPI:
    """Test QMS document management endpoints."""

    def test_list_documents(self, client):
        """Test listing QMS documents."""
        response = client.get('/api/v1/qms/documents')
        assert response.status_code == 200

    def test_create_document(self, client):
        """Test creating a QMS document."""
        data = {
            'title': 'Work Instruction - Brick Molding',
            'document_type': 'work_instruction',
            'content': 'Step 1: ...',
            'revision': '1.0',
        }
        response = client.post('/api/v1/qms/documents', json=data)
        assert response.status_code in [200, 201]


@pytest.mark.integration
class TestQMSNCRAPI:
    """Test QMS Non-Conformance Report endpoints."""

    def test_list_ncrs(self, client):
        """Test listing NCRs."""
        response = client.get('/api/v1/qms/ncrs')
        assert response.status_code == 200

    def test_create_ncr(self, client):
        """Test creating an NCR."""
        data = {
            'title': 'Dimensional deviation on brick batch',
            'description': 'Batch LOT-001 has bricks 0.5mm oversize',
            'severity': 'minor',
            'affected_items': ['LEGO-2x4-RED'],
            'quantity_affected': 50,
        }
        response = client.post('/api/v1/qms/ncrs', json=data)
        assert response.status_code in [200, 201]

    def test_update_ncr_status(self, client):
        """Test updating NCR status."""
        data = {'status': 'investigating'}
        response = client.patch('/api/v1/qms/ncrs/NCR-001/status', json=data)
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestQMSCAPAAPI:
    """Test QMS Corrective/Preventive Action endpoints."""

    def test_list_capas(self, client):
        """Test listing CAPAs."""
        response = client.get('/api/v1/qms/capas')
        assert response.status_code == 200

    def test_create_capa(self, client):
        """Test creating a CAPA."""
        data = {
            'title': 'Correct mold temperature control',
            'type': 'corrective',
            'related_ncr': 'NCR-001',
            'root_cause': 'Temperature controller calibration drift',
            'action_plan': 'Recalibrate controller and add quarterly checks',
        }
        response = client.post('/api/v1/qms/capas', json=data)
        assert response.status_code in [200, 201]


@pytest.mark.integration
class TestQMSInspectionAPI:
    """Test QMS inspection endpoints."""

    def test_list_inspections(self, client):
        """Test listing inspections."""
        response = client.get('/api/v1/qms/inspections')
        assert response.status_code == 200

    def test_create_inspection(self, client):
        """Test creating an inspection."""
        data = {
            'work_order_id': 'WO-001',
            'inspection_type': 'first_article',
            'results': {
                'length': {'measured': 15.8, 'nominal': 15.8, 'tolerance': 0.1, 'pass': True},
                'width': {'measured': 7.8, 'nominal': 7.8, 'tolerance': 0.1, 'pass': True},
            },
        }
        response = client.post('/api/v1/qms/inspections', json=data)
        assert response.status_code in [200, 201]


@pytest.mark.integration
class TestCMMSAssetAPI:
    """Test CMMS asset management endpoints."""

    def test_list_assets(self, client):
        """Test listing assets."""
        response = client.get('/api/v1/cmms/assets')
        assert response.status_code == 200

    def test_get_asset(self, client):
        """Test getting specific asset."""
        response = client.get('/api/v1/cmms/assets/prusa_mk4_1')
        assert response.status_code in [200, 404]

    def test_update_asset_status(self, client):
        """Test updating asset status."""
        data = {'status': 'maintenance'}
        response = client.patch('/api/v1/cmms/assets/prusa_mk4_1/status', json=data)
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestCMMSMaintenanceAPI:
    """Test CMMS maintenance endpoints."""

    def test_list_work_orders(self, client):
        """Test listing maintenance work orders."""
        response = client.get('/api/v1/cmms/work-orders')
        assert response.status_code == 200

    def test_create_work_order(self, client):
        """Test creating a maintenance work order."""
        data = {
            'asset_id': 'prusa_mk4_1',
            'type': 'preventive',
            'priority': 3,
            'description': 'Monthly lubrication and cleaning',
            'scheduled_date': (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }
        response = client.post('/api/v1/cmms/work-orders', json=data)
        assert response.status_code in [200, 201]

    def test_complete_work_order(self, client):
        """Test completing a maintenance work order."""
        data = {
            'completion_notes': 'Lubrication complete, no issues found',
            'labor_hours': 0.5,
            'parts_used': [],
        }
        response = client.post('/api/v1/cmms/work-orders/MWO-001/complete', json=data)
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestCMMSPMScheduleAPI:
    """Test CMMS preventive maintenance schedule endpoints."""

    def test_list_pm_schedules(self, client):
        """Test listing PM schedules."""
        response = client.get('/api/v1/cmms/pm-schedules')
        assert response.status_code == 200

    def test_create_pm_schedule(self, client):
        """Test creating a PM schedule."""
        data = {
            'asset_id': 'prusa_mk4_1',
            'name': 'Monthly Lubrication',
            'frequency_days': 30,
            'tasks': ['Lubricate linear rails', 'Clean extruder'],
            'estimated_hours': 0.5,
        }
        response = client.post('/api/v1/cmms/pm-schedules', json=data)
        assert response.status_code in [200, 201]

    def test_upcoming_maintenance(self, client):
        """Test getting upcoming maintenance."""
        response = client.get('/api/v1/cmms/upcoming?days=30')
        assert response.status_code == 200
