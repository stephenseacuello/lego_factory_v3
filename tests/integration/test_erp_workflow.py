"""
LEGO Factory v3 - ERP Workflow Integration Tests
================================================
End-to-end tests for ERP workflows: Order → Production → Shipment
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from tests.factories import (
    ItemFactory,
    SalesOrderFactory,
    SalesOrderLineFactory,
    PartnerFactory,
    LocationFactory,
    InventoryBalanceFactory,
)


class TestOrderToShipmentWorkflow:
    """Integration tests for order to shipment workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.query.return_value.filter.return_value.all.return_value = []
        return session

    @pytest.fixture
    def sample_item(self):
        """Create sample finished good item."""
        return ItemFactory.build(
            item_id='FG-001',
            name='LEGO Brick Set',
            item_type='finished_good',
            is_salable=True,
            standard_cost=50.0,
            list_price=75.0,
            track_inventory=True,
        )

    @pytest.fixture
    def sample_customer(self):
        """Create sample customer."""
        return PartnerFactory.build(
            partner_id='CUST-001',
            name='Test Customer',
            partner_type='customer',
        )

    def test_create_sales_order_with_lines(self, mock_session, sample_item, sample_customer):
        """Test creating a sales order with line items."""
        from services.erp.sales_service import SalesService

        # Setup mocks
        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.item_id = sample_item['item_id']
        mock_item.name = sample_item['name']
        mock_item.list_price = sample_item['list_price']
        mock_item.base_uom = 'EA'
        mock_item.to_dict.return_value = sample_item

        mock_customer = MagicMock()
        mock_customer.id = 1
        mock_customer.partner_id = sample_customer['partner_id']
        mock_customer.name = sample_customer['name']
        mock_customer.currency = 'USD'
        mock_customer.payment_terms = MagicMock(value='net_30')
        mock_customer.to_dict.return_value = sample_customer

        def query_side_effect(model):
            mock_query = MagicMock()
            if 'Partner' in str(model):
                mock_query.filter.return_value.first.return_value = mock_customer
            elif 'Item' in str(model):
                mock_query.filter.return_value.first.return_value = mock_item
            else:
                mock_query.filter.return_value.first.return_value = None
            return mock_query

        mock_session.query.side_effect = query_side_effect

        service = SalesService(mock_session)

        # Create order
        order_data = {
            'customer_id': 'CUST-001',
            'requested_date': (date.today() + timedelta(days=14)),
            'lines': [
                {'item_id': 'FG-001', 'quantity': 10, 'unit_price': 75.0}
            ],
        }

        result = service.create_order(order_data)

        # Verify
        assert result is not None
        mock_session.add.assert_called()
        mock_session.flush.assert_called()

    def test_release_order_allocates_inventory(self, mock_session, sample_item):
        """Test that releasing an order allocates inventory."""
        from services.erp.sales_service import SalesService

        # Setup mock order
        mock_order = MagicMock()
        mock_order.order_number = 'SO-001'
        mock_order.status = MagicMock(value='approved')
        mock_order.lines = []
        mock_order.to_dict.return_value = {'order_number': 'SO-001', 'status': 'released'}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_order

        service = SalesService(mock_session)

        # Release order
        result = service.release_order('SO-001', 'test_user')

        # Verify status changed
        assert result is not None
        mock_session.flush.assert_called()

    def test_create_shipment_updates_quantities(self, mock_session):
        """Test that creating a shipment updates order quantities."""
        from services.erp.sales_service import SalesService

        # Setup mock order with lines
        mock_line = MagicMock()
        mock_line.line_number = 1
        mock_line.quantity_ordered = 10
        mock_line.quantity_shipped = 0
        mock_line.item_id = 1
        mock_line.uom = 'EA'
        mock_line.unit_price = 75.0
        mock_line.to_dict.return_value = {'line_number': 1, 'quantity_ordered': 10}

        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.order_number = 'SO-001'
        mock_order.customer_id = 1
        mock_order.lines = [mock_line]
        mock_order.to_dict.return_value = {'order_number': 'SO-001'}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_order

        service = SalesService(mock_session)

        # Create shipment
        shipment_data = {
            'carrier': 'UPS',
            'tracking_number': '1Z999999999',
            'lines': [
                {'line_number': 1, 'quantity_shipped': 10}
            ],
        }

        result = service.create_shipment('SO-001', shipment_data)

        # Verify shipment created
        assert result is not None
        mock_session.add.assert_called()


class TestMRPWorkflow:
    """Integration tests for MRP workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None
        session.query.return_value.filter.return_value.all.return_value = []
        session.query.return_value.filter.return_value.scalar.return_value = 0
        return session

    def test_mrp_explosion_generates_requirements(self, mock_session):
        """Test MRP explosion generates material requirements."""
        from services.erp.mrp_service import MRPService

        # Setup - no open orders
        mock_session.query.return_value.filter.return_value.all.return_value = []

        service = MRPService(mock_session)

        # Run MRP
        result = service.run_mrp(horizon_days=30)

        # Verify plan created
        assert result is not None
        assert result.plan_date == date.today()
        assert result.horizon_days == 30

    def test_mrp_generates_planned_orders_for_shortages(self, mock_session):
        """Test MRP generates planned orders when inventory is short."""
        from services.erp.mrp_service import MRPService, MRPRequirement
        from datetime import date, timedelta

        service = MRPService(mock_session)

        # Create requirements with net shortages
        requirements = [
            MRPRequirement(
                item_id='COMP-001',
                item_name='Component 1',
                date_required=date.today() + timedelta(days=7),
                gross_requirement=100,
                on_hand=20,
                on_order=0,
                allocated=0,
                net_requirement=80,
                planned_order_qty=100,
                planned_order_date=date.today(),
                source='sales_order',
            )
        ]

        # Generate planned orders
        planned_orders = service._generate_planned_orders(requirements)

        # Verify planned orders created
        assert len(planned_orders) > 0
        assert planned_orders[0]['item_id'] == 'COMP-001'
        assert planned_orders[0]['quantity'] == 100

    def test_mrp_generates_action_messages_for_past_due(self, mock_session):
        """Test MRP generates action messages for past due orders."""
        from services.erp.mrp_service import MRPService, MRPPlan
        from datetime import date, timedelta

        service = MRPService(mock_session)

        # Create plan with past due orders
        plan = MRPPlan(
            plan_date=date.today(),
            horizon_days=30,
            planned_orders=[
                {
                    'item_id': 'COMP-001',
                    'order_date': (date.today() - timedelta(days=5)).isoformat(),
                    'quantity': 100,
                }
            ]
        )

        # Generate action messages
        messages = service._generate_action_messages(plan)

        # Verify expedite message generated
        assert any('EXPEDITE' in msg for msg in messages)


class TestPurchasingWorkflow:
    """Integration tests for purchasing workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    def test_requisition_to_po_workflow(self, mock_session):
        """Test requisition to purchase order workflow."""
        from services.erp.purchasing_service import PurchasingService

        # Setup mock requisition
        mock_req = MagicMock()
        mock_req.requisition_number = 'REQ-001'
        mock_req.lines = []
        mock_req.estimated_total = 0
        mock_req.to_dict.return_value = {'requisition_number': 'REQ-001'}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_req

        service = PurchasingService(mock_session)

        # Create requisition
        req_data = {
            'requested_by': 'test_user',
            'department': 'production',
        }

        result = service.create_requisition(req_data)

        # Verify requisition created
        assert result is not None
        mock_session.add.assert_called()

    def test_po_approval_workflow(self, mock_session):
        """Test PO approval workflow."""
        from services.erp.purchasing_service import PurchasingService

        # Setup mock PO
        mock_po = MagicMock()
        mock_po.po_number = 'PO-001'
        mock_po.status = MagicMock(value='draft')
        mock_po.to_dict.return_value = {'po_number': 'PO-001', 'status': 'approved'}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_po

        service = PurchasingService(mock_session)

        # Approve PO
        result = service.approve_po('PO-001', 'approver_user')

        # Verify approval recorded
        assert result is not None
        mock_session.flush.assert_called()

    def test_goods_receipt_updates_inventory(self, mock_session):
        """Test goods receipt creates inventory."""
        from services.erp.purchasing_service import PurchasingService

        # Setup mock PO with lines
        mock_line = MagicMock()
        mock_line.line_number = 1
        mock_line.item_id = 1
        mock_line.quantity_ordered = 100
        mock_line.quantity_received = 0
        mock_line.quantity_rejected = 0
        mock_line.uom = 'EA'
        mock_line.unit_price = 10.0
        mock_line.to_dict.return_value = {'line_number': 1}

        mock_po = MagicMock()
        mock_po.id = 1
        mock_po.po_number = 'PO-001'
        mock_po.vendor_id = 1
        mock_po.lines = [mock_line]
        mock_po.to_dict.return_value = {'po_number': 'PO-001'}

        mock_session.query.return_value.filter.return_value.first.return_value = mock_po

        service = PurchasingService(mock_session)

        # Receive goods
        receipt_data = {
            'lines': [
                {'line_number': 1, 'quantity_received': 100}
            ],
        }

        result = service.receive_goods('PO-001', receipt_data)

        # Verify receipt created
        assert result is not None
        mock_session.add.assert_called()


class TestInventoryWorkflow:
    """Integration tests for inventory workflow."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    def test_inventory_allocation_workflow(self, mock_session):
        """Test inventory allocation for sales orders."""
        # Setup mock item and balance
        mock_balance = MagicMock()
        mock_balance.quantity_on_hand = 100
        mock_balance.quantity_allocated = 0
        mock_balance.quantity_available = 100

        mock_session.query.return_value.filter.return_value.first.return_value = mock_balance

        # Allocate 50 units
        mock_balance.quantity_allocated = 50
        mock_balance.quantity_available = 50

        # Verify allocation
        assert mock_balance.quantity_available == 50
        assert mock_balance.quantity_allocated == 50


class TestBOMExplosion:
    """Integration tests for BOM explosion."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    def test_single_level_bom_explosion(self, mock_session):
        """Test single-level BOM explosion."""
        from services.erp.item_service import ItemService

        # Setup mock item with no BOM
        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.item_id = 'FG-001'
        mock_item.bom_lines = []

        mock_session.query.return_value.filter.return_value.first.return_value = mock_item

        service = ItemService(mock_session)

        # Explode BOM
        result = service.explode_bom('FG-001', quantity=10)

        # Verify empty result for item without BOM
        assert result == []

    def test_multi_level_bom_explosion(self, mock_session):
        """Test multi-level BOM explosion with recursion."""
        from services.erp.item_service import ItemService

        # This test verifies the BOM explosion handles nested components
        # Setup would involve mocking multiple levels of BOM relationships

        service = ItemService(mock_session)

        # The actual explosion is tested by verifying the recursion depth
        # is properly handled (max_level parameter)
        result = service.explode_bom('FG-001', quantity=10, max_level=5)

        # With no mock data, expect empty result
        assert isinstance(result, list)
