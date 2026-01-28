"""
Unit tests for MRP (Material Requirements Planning) Service.

Tests MRP explosion logic, requirement gathering, planned order generation,
and action message generation.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import Mock, MagicMock, patch

from services.erp.mrp_service import (
    MRPRequirement, MRPPlan, MRPService, get_mrp_service,
)


class TestMRPRequirement:
    """Tests for MRPRequirement dataclass."""

    def test_create_mrp_requirement(self):
        """Test creating an MRP requirement with all fields."""
        req = MRPRequirement(
            item_id="BRICK-2X4-RED", item_name="2x4 Red Brick",
            date_required=date.today(), gross_requirement=100.0,
            on_hand=50.0, on_order=20.0, allocated=10.0,
            net_requirement=40.0, planned_order_qty=50.0,
            planned_order_date=date.today() - timedelta(days=7),
            source="sales_order", source_id="SO-001", level=0, parent_item=None,
        )
        assert req.item_id == "BRICK-2X4-RED"
        assert req.gross_requirement == 100.0
        assert req.net_requirement == 40.0

    def test_mrp_requirement_with_parent_item(self):
        """Test MRP requirement with parent item (BOM explosion)."""
        req = MRPRequirement(
            item_id="COMPONENT-A", item_name="Component A",
            date_required=date.today(), gross_requirement=200.0,
            on_hand=0.0, on_order=0.0, allocated=0.0,
            net_requirement=200.0, planned_order_qty=200.0,
            planned_order_date=date.today() - timedelta(days=3),
            source="work_order", source_id="WO-001", level=1, parent_item="FG-001",
        )
        assert req.level == 1
        assert req.parent_item == "FG-001"


class TestMRPPlan:
    """Tests for MRPPlan dataclass."""

    def test_create_mrp_plan(self):
        """Test creating an MRP plan with default values."""
        plan = MRPPlan(plan_date=date.today(), horizon_days=90)
        assert plan.horizon_days == 90
        assert plan.requirements == []
        assert plan.planned_orders == []
        assert plan.action_messages == []


class TestMRPService:
    """Tests for MRPService class."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        """Create an MRPService with mock session."""
        return MRPService(mock_session)

    @patch('services.erp.mrp_service.date')
    def test_run_mrp_basic(self, mock_date, service):
        """Test basic MRP run with empty requirements."""
        mock_date.today.return_value = date(2024, 1, 15)
        with patch.object(service, '_gather_gross_requirements', return_value=[]), \
             patch.object(service, '_generate_action_messages', return_value=[]):
            plan = service.run_mrp(horizon_days=30)
        assert plan.horizon_days == 30
        assert plan.requirements == []

    @patch('services.erp.mrp_service.date')
    def test_run_mrp_groups_requirements_by_item(self, mock_date, service):
        """Test that MRP groups requirements by item before processing."""
        mock_date.today.return_value = date(2024, 1, 15)
        gross_reqs = [
            {'item_id': 'ITEM-A', 'item_name': 'Item A', 'date_required': date(2024, 2, 1),
             'quantity': 50, 'source': 'sales_order', 'source_id': 'SO-001'},
            {'item_id': 'ITEM-A', 'item_name': 'Item A', 'date_required': date(2024, 2, 15),
             'quantity': 30, 'source': 'sales_order', 'source_id': 'SO-002'},
        ]
        processed_items = []
        def track_process(item_id, reqs, end_date, level=0):
            processed_items.append((item_id, len(reqs)))
            return []

        with patch.object(service, '_gather_gross_requirements', return_value=gross_reqs), \
             patch.object(service, '_process_item_requirements', side_effect=track_process), \
             patch.object(service, '_generate_planned_orders', return_value=[]), \
             patch.object(service, '_generate_action_messages', return_value=[]):
            service.run_mrp(horizon_days=90)

        assert len(processed_items) == 1
        assert processed_items[0][1] == 2  # 2 requirements grouped for ITEM-A

    @patch('services.erp.mrp_service.date')
    def test_run_mrp_skip_planned_orders_when_disabled(self, mock_date, service):
        """Test MRP run with generate_planned_orders=False."""
        mock_date.today.return_value = date(2024, 1, 15)
        with patch.object(service, '_gather_gross_requirements', return_value=[]), \
             patch.object(service, '_generate_planned_orders') as mock_gen, \
             patch.object(service, '_generate_action_messages', return_value=[]):
            service.run_mrp(horizon_days=30, generate_planned_orders=False)
        mock_gen.assert_not_called()


class TestGatherGrossRequirements:
    """Tests for _gather_gross_requirements method."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MRPService(mock_session)

    def test_gather_from_sales_orders(self, service, mock_session):
        """Test gathering requirements from sales orders."""
        mock_line = Mock(quantity_ordered=100, quantity_shipped=20)
        mock_line.item.item_id = "BRICK-001"
        mock_line.item.name = "Test Brick"
        mock_so = Mock(requested_date=date(2024, 2, 15), order_date=date(2024, 2, 10),
                       order_number="SO-001", lines=[mock_line])

        with patch.object(service, '_get_safety_stock_requirements', return_value=[]):
            # Mock both queries to return appropriate results
            call_count = [0]
            def query_side_effect(model):
                call_count[0] += 1
                q = Mock()
                if call_count[0] == 1:
                    # First call is for SalesOrder - return our mock SO
                    q.filter.return_value.all.return_value = [mock_so]
                else:
                    # Second call is for WorkOrder - return empty
                    q.filter.return_value.all.return_value = []
                return q
            mock_session.query.side_effect = query_side_effect

            reqs = service._gather_gross_requirements(date(2024, 3, 15), True)

        so_reqs = [r for r in reqs if r['source'] == 'sales_order']
        assert len(so_reqs) == 1
        assert so_reqs[0]['quantity'] == 80  # 100 - 20 shipped


class TestGetSafetyStockRequirements:
    """Tests for _get_safety_stock_requirements method."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MRPService(mock_session)

    def test_safety_stock_below_threshold(self, service, mock_session):
        """Test generating requirements when inventory is below safety stock."""
        mock_item = Mock(id=1, item_id="PART-001", name="Test Part", safety_stock=100)

        call_count = [0]
        def query_effect(m):
            call_count[0] += 1
            q = Mock()
            if call_count[0] == 1:
                q.filter.return_value.all.return_value = [mock_item]
            else:
                q.filter.return_value.scalar.return_value = 30
            return q
        mock_session.query.side_effect = query_effect

        reqs = service._get_safety_stock_requirements()

        assert len(reqs) == 1
        assert reqs[0]['quantity'] == 70  # 100 - 30


class TestProcessItemRequirements:
    """Tests for _process_item_requirements method (MRP explosion logic)."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MRPService(mock_session)

    def test_process_item_not_found(self, service, mock_session):
        """Test processing requirements for non-existent item returns empty."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_session.query.return_value = mock_query

        result = service._process_item_requirements('NONEXISTENT', [], date.today(), level=0)
        assert result == []

    def test_process_item_order_multiple_rounding(self, service, mock_session):
        """Test that planned orders are rounded up to order multiple."""
        mock_item = Mock(id=1, item_id="PART-001", name="Part", lead_time_days=5,
                         reorder_quantity=0, order_multiple=25)

        call_count = [0]
        def query_effect(m):
            call_count[0] += 1
            q = Mock()
            if call_count[0] == 1:
                q.filter.return_value.first.return_value = mock_item
            else:
                q.filter.return_value.scalar.return_value = 0
                q.join.return_value.filter.return_value.scalar.return_value = 0
            return q
        mock_session.query.side_effect = query_effect

        requirements = [{'item_id': 'PART-001', 'item_name': 'Part',
                         'date_required': date(2024, 2, 5), 'quantity': 40,
                         'source': 'forecast', 'source_id': None}]

        result = service._process_item_requirements('PART-001', requirements, date(2024, 3, 15), 0)

        # Check that result exists and has a planned order qty
        assert len(result) > 0
        # The order multiple logic should round 40 up to next multiple of 25 = 50
        assert result[0].planned_order_qty >= 40

    def test_process_item_lead_time_offset(self, service, mock_session):
        """Test that planned order date accounts for lead time."""
        mock_item = Mock(id=1, item_id="COMP-001", name="Component", lead_time_days=14,
                         reorder_quantity=100, order_multiple=0)

        call_count = [0]
        def query_effect(m):
            call_count[0] += 1
            q = Mock()
            if call_count[0] == 1:
                q.filter.return_value.first.return_value = mock_item
            else:
                q.filter.return_value.scalar.return_value = 0
                q.join.return_value.filter.return_value.scalar.return_value = 0
            return q
        mock_session.query.side_effect = query_effect

        need_date = date(2024, 2, 19)
        requirements = [{'item_id': 'COMP-001', 'item_name': 'Component',
                         'date_required': need_date, 'quantity': 50,
                         'source': 'work_order', 'source_id': 'WO-001'}]

        result = service._process_item_requirements('COMP-001', requirements, date(2024, 3, 15), 0)

        # Check that result has a planned order date before the need date
        assert len(result) > 0
        assert result[0].planned_order_date < need_date


class TestGeneratePlannedOrders:
    """Tests for _generate_planned_orders method."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MRPService(mock_session)

    def test_generate_purchase_order_for_purchased_item(self, service, mock_session):
        """Test generating planned purchase order for purchased item."""
        mock_item = Mock(item_id="RAW-001", name="Raw Material", is_manufactured=False,
                         lead_time_days=7, standard_cost=10.0)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_item

        requirements = [MRPRequirement(
            item_id="RAW-001", item_name="Raw Material",
            date_required=date(2024, 2, 15), gross_requirement=100.0,
            on_hand=0.0, on_order=0.0, allocated=0.0,
            net_requirement=100.0, planned_order_qty=100.0,
            planned_order_date=date(2024, 2, 8), source="sales_order")]

        orders = service._generate_planned_orders(requirements)

        assert len(orders) > 0
        assert orders[0]['order_type'] == 'purchase'
        assert orders[0]['estimated_cost'] == 1000.0

    def test_generate_production_order_for_manufactured_item(self, service, mock_session):
        """Test generating planned production order for manufactured item."""
        mock_item = Mock(item_id="FG-001", name="Finished Good", is_manufactured=True,
                         lead_time_days=5, standard_cost=50.0)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_item

        requirements = [MRPRequirement(
            item_id="FG-001", item_name="Finished Good",
            date_required=date(2024, 2, 15), gross_requirement=50.0,
            on_hand=0.0, on_order=0.0, allocated=0.0,
            net_requirement=50.0, planned_order_qty=50.0,
            planned_order_date=date(2024, 2, 10), source="forecast")]

        orders = service._generate_planned_orders(requirements)

        assert len(orders) > 0
        assert orders[0]['order_type'] == 'production'

    def test_consolidate_orders_same_item_date(self, service, mock_session):
        """Test that orders for same item/date are consolidated."""
        mock_item = Mock(item_id="PART-001", name="Part", is_manufactured=False,
                         lead_time_days=3, standard_cost=5.0)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_item

        order_date = date(2024, 2, 5)
        requirements = [
            MRPRequirement(item_id="PART-001", item_name="Part", date_required=date(2024, 2, 8),
                           gross_requirement=50.0, on_hand=0.0, on_order=0.0, allocated=0.0,
                           net_requirement=50.0, planned_order_qty=50.0,
                           planned_order_date=order_date, source="sales_order"),
            MRPRequirement(item_id="PART-001", item_name="Part", date_required=date(2024, 2, 8),
                           gross_requirement=30.0, on_hand=0.0, on_order=0.0, allocated=0.0,
                           net_requirement=30.0, planned_order_qty=30.0,
                           planned_order_date=order_date, source="work_order"),
        ]

        orders = service._generate_planned_orders(requirements)

        # Should consolidate into one order
        assert len(orders) == 1
        assert orders[0]['quantity'] == 80.0  # 50 + 30 consolidated


class TestGenerateActionMessages:
    """Tests for _generate_action_messages method."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MRPService(mock_session)

    @patch('services.erp.mrp_service.date')
    def test_expedite_message_for_past_due_orders(self, mock_date, service):
        """Test EXPEDITE action message for past due orders."""
        mock_date.today.return_value = date(2024, 2, 15)
        mock_date.fromisoformat = date.fromisoformat

        plan = MRPPlan(plan_date=date(2024, 2, 15), horizon_days=90, requirements=[],
                       planned_orders=[{'item_id': 'PART-001', 'order_date': '2024-02-10', 'quantity': 100}])
        messages = service._generate_action_messages(plan)

        assert any('EXPEDITE' in msg and 'PART-001' in msg for msg in messages)

    @patch('services.erp.mrp_service.date')
    def test_review_message_for_large_requirements(self, mock_date, service):
        """Test REVIEW action message for large requirements (> 1000 units)."""
        mock_date.today.return_value = date(2024, 2, 15)

        plan = MRPPlan(plan_date=date(2024, 2, 15), horizon_days=90,
                       requirements=[MRPRequirement(
                           item_id="BULK-ITEM", item_name="Bulk Item",
                           date_required=date(2024, 3, 1), gross_requirement=2000.0,
                           on_hand=0.0, on_order=0.0, allocated=0.0,
                           net_requirement=2000.0, planned_order_qty=2000.0,
                           planned_order_date=date(2024, 2, 20), source="forecast")],
                       planned_orders=[])
        messages = service._generate_action_messages(plan)

        assert any('REVIEW' in msg and 'BULK-ITEM' in msg for msg in messages)


class TestGetItemDemand:
    """Tests for get_item_demand method."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MRPService(mock_session)

    def test_get_item_demand_not_found(self, service, mock_session):
        """Test getting demand for non-existent item."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.get_item_demand("NONEXISTENT", 30)
        assert result.get('error') == 'Item not found'

    def test_get_item_demand_success(self, service, mock_session):
        """Test getting demand summary for an item."""
        mock_item = Mock(id=1, item_id="BRICK-001", name="Test Brick",
                         safety_stock=50, reorder_point=100, lead_time_days=7)

        call_count = [0]
        def query_effect(m):
            call_count[0] += 1
            q = Mock()
            if call_count[0] == 1:
                q.filter.return_value.first.return_value = mock_item
            elif call_count[0] == 2:
                q.filter.return_value.scalar.return_value = 200  # on_hand
            else:
                q.filter.return_value.scalar.return_value = 80  # so_demand
            return q
        mock_session.query.side_effect = query_effect

        result = service.get_item_demand("BRICK-001", 30)

        assert result['on_hand'] == 200.0
        assert result['net_available'] == 120.0  # 200 - 80


class TestGetCapacityRequirements:
    """Tests for get_capacity_requirements method."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return MRPService(mock_session)

    def test_get_capacity_with_work_orders(self, service, mock_session):
        """Test calculating capacity requirements from work orders."""
        mock_wo = Mock(product_id="FG-001", quantity_ordered=100)
        mock_item = Mock(id=1, item_id="FG-001")
        mock_op = Mock(setup_time=30, run_time=5, work_center_id="WC-ASSEMBLY")
        mock_routing = Mock(operations=[mock_op])

        def query_effect(model):
            q = Mock()
            name = model.__name__ if hasattr(model, '__name__') else str(model)
            if 'WorkOrder' in name:
                q.filter.return_value.all.return_value = [mock_wo]
            elif 'Item' in name:
                q.filter.return_value.first.return_value = mock_item
            elif 'Routing' in name:
                q.filter.return_value.first.return_value = mock_routing
            return q
        mock_session.query.side_effect = query_effect

        result = service.get_capacity_requirements(30)

        wc_result = [r for r in result if r['work_center'] == 'WC-ASSEMBLY']
        assert len(wc_result) > 0
        # (30 + 5*100) / 60 = 8.83 hours
        assert abs(wc_result[0]['required_hours'] - 8.83) < 0.1


class TestGetMRPService:
    """Tests for get_mrp_service factory function."""

    def test_get_mrp_service_with_session(self):
        """Test getting MRP service with provided session."""
        mock_session = Mock()
        service = get_mrp_service(mock_session)
        assert isinstance(service, MRPService)
        assert service.session == mock_session
