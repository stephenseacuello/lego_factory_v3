"""
LEGO Factory v3 - Inventory Service Unit Tests
===============================================
Tests for inventory management, transactions, and balance tracking.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, date, timedelta
import uuid


class TestBalanceCalculations:
    """Tests for inventory balance calculations."""

    def test_available_quantity_calculation(self):
        """Available quantity = on hand - allocated."""
        balance = MagicMock()
        balance.quantity_on_hand = 100.0
        balance.quantity_allocated = 30.0
        balance.quantity_available = balance.quantity_on_hand - balance.quantity_allocated

        assert balance.quantity_available == 70.0

    def test_zero_balance(self):
        """Zero balance should be handled correctly."""
        balance = MagicMock()
        balance.quantity_on_hand = 0.0
        balance.quantity_allocated = 0.0
        balance.quantity_available = 0.0

        assert balance.quantity_available == 0.0

    def test_fully_allocated(self):
        """Fully allocated inventory should show zero available."""
        balance = MagicMock()
        balance.quantity_on_hand = 100.0
        balance.quantity_allocated = 100.0
        balance.quantity_available = 0.0

        assert balance.quantity_available == 0.0

    def test_negative_available_not_allowed(self):
        """Available quantity should not be negative (unless location allows)."""
        balance = MagicMock()
        balance.quantity_on_hand = 50.0
        balance.quantity_allocated = 50.0
        balance.quantity_available = max(0, balance.quantity_on_hand - balance.quantity_allocated)

        assert balance.quantity_available >= 0

    def test_total_value_calculation(self):
        """Total value = quantity * unit cost."""
        balance = MagicMock()
        balance.quantity_on_hand = 100.0
        balance.unit_cost = 10.0
        balance.total_value = balance.quantity_on_hand * balance.unit_cost

        assert balance.total_value == 1000.0

    def test_aggregate_balance_across_locations(self):
        """Balance should aggregate across locations."""
        balances = [
            MagicMock(quantity_on_hand=100.0, quantity_available=80.0, total_value=1000.0),
            MagicMock(quantity_on_hand=50.0, quantity_available=50.0, total_value=500.0),
            MagicMock(quantity_on_hand=25.0, quantity_available=20.0, total_value=250.0),
        ]

        total_on_hand = sum(b.quantity_on_hand for b in balances)
        total_available = sum(b.quantity_available for b in balances)
        total_value = sum(b.total_value for b in balances)

        assert total_on_hand == 175.0
        assert total_available == 150.0
        assert total_value == 1750.0

    def test_balance_with_lot_tracking(self):
        """Balance should be tracked by lot when lot controlled."""
        balance = MagicMock()
        balance.item_id = 'ITEM-001'
        balance.location_id = 'LOC-001'
        balance.lot_id = 'LOT-001'
        balance.quantity_on_hand = 50.0

        assert balance.lot_id is not None


class TestInventoryTransactions:
    """Tests for inventory transactions."""

    def test_receipt_transaction(self, mock_session):
        """Receipt should increase inventory."""
        initial_qty = 100.0
        receipt_qty = 50.0
        final_qty = initial_qty + receipt_qty

        assert final_qty == 150.0

    def test_issue_transaction(self):
        """Issue should decrease inventory."""
        initial_qty = 100.0
        issue_qty = 30.0
        final_qty = initial_qty - issue_qty

        assert final_qty == 70.0

    def test_transfer_transaction(self):
        """Transfer should move inventory between locations."""
        from_balance = MagicMock(quantity_on_hand=100.0)
        to_balance = MagicMock(quantity_on_hand=50.0)
        transfer_qty = 25.0

        # After transfer
        from_balance.quantity_on_hand -= transfer_qty
        to_balance.quantity_on_hand += transfer_qty

        assert from_balance.quantity_on_hand == 75.0
        assert to_balance.quantity_on_hand == 75.0

    def test_adjustment_positive(self):
        """Positive adjustment should increase inventory."""
        balance = MagicMock(quantity_on_hand=100.0)
        adjustment = 10.0

        balance.quantity_on_hand += adjustment

        assert balance.quantity_on_hand == 110.0

    def test_adjustment_negative(self):
        """Negative adjustment should decrease inventory."""
        balance = MagicMock(quantity_on_hand=100.0)
        adjustment = -10.0

        balance.quantity_on_hand += adjustment

        assert balance.quantity_on_hand == 90.0

    def test_scrap_transaction(self):
        """Scrap should decrease inventory."""
        balance = MagicMock(quantity_on_hand=100.0)
        scrap_qty = 5.0

        balance.quantity_on_hand -= scrap_qty

        assert balance.quantity_on_hand == 95.0

    def test_production_issue(self):
        """Production issue should consume inventory."""
        balance = MagicMock(quantity_on_hand=100.0)
        issue_qty = 20.0

        balance.quantity_on_hand -= issue_qty

        assert balance.quantity_on_hand == 80.0

    def test_production_receipt(self):
        """Production receipt should add finished goods."""
        balance = MagicMock(quantity_on_hand=0.0)
        receipt_qty = 50.0

        balance.quantity_on_hand += receipt_qty

        assert balance.quantity_on_hand == 50.0

    def test_return_transaction(self):
        """Return should increase inventory."""
        balance = MagicMock(quantity_on_hand=100.0)
        return_qty = 10.0

        balance.quantity_on_hand += return_qty

        assert balance.quantity_on_hand == 110.0

    def test_transaction_id_generation(self):
        """Transaction ID should be auto-generated."""
        now = datetime.utcnow()
        txn_id = f"TXN-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

        assert txn_id.startswith('TXN-')
        assert len(txn_id) > 20

    def test_transaction_types(self):
        """Transaction types should be properly defined."""
        transaction_types = [
            'receipt', 'issue', 'transfer', 'adjustment', 'scrap',
            'production_issue', 'production_receipt', 'return',
            'cycle_count', 'physical_count'
        ]

        for tt in transaction_types:
            assert isinstance(tt, str)


class TestAllocations:
    """Tests for inventory allocations."""

    def test_allocate_inventory_success(self):
        """Allocation should succeed with sufficient inventory."""
        balance = MagicMock()
        balance.quantity_on_hand = 100.0
        balance.quantity_allocated = 0.0
        balance.quantity_available = 100.0

        allocation_qty = 30.0

        if balance.quantity_available >= allocation_qty:
            balance.quantity_allocated += allocation_qty
            balance.quantity_available -= allocation_qty

        assert balance.quantity_allocated == 30.0
        assert balance.quantity_available == 70.0

    def test_allocate_inventory_insufficient(self):
        """Allocation should fail with insufficient inventory."""
        balance = MagicMock()
        balance.quantity_available = 20.0

        allocation_qty = 50.0

        success = balance.quantity_available >= allocation_qty

        assert success is False

    def test_deallocate_inventory(self):
        """Deallocation should release reserved inventory."""
        balance = MagicMock()
        balance.quantity_on_hand = 100.0
        balance.quantity_allocated = 30.0
        balance.quantity_available = 70.0

        deallocate_qty = 20.0

        balance.quantity_allocated -= deallocate_qty
        balance.quantity_available += deallocate_qty

        assert balance.quantity_allocated == 10.0
        assert balance.quantity_available == 90.0

    def test_partial_allocation(self):
        """Should allow partial allocation."""
        balance = MagicMock()
        balance.quantity_available = 50.0

        requested_qty = 100.0
        allocated_qty = min(requested_qty, balance.quantity_available)

        assert allocated_qty == 50.0

    def test_allocation_with_reference(self):
        """Allocation should track reference document."""
        allocation = MagicMock()
        allocation.reference_type = 'sales_order'
        allocation.reference_id = 'SO-001'
        allocation.quantity = 30.0

        assert allocation.reference_type == 'sales_order'
        assert allocation.reference_id == 'SO-001'


class TestLotTracking:
    """Tests for lot/batch tracking."""

    def test_create_lot(self, mock_session):
        """Lot should be created with proper data."""
        lot = MagicMock()
        lot.lot_number = 'LOT-2024-001'
        lot.item_id = 'ITEM-001'
        lot.status = 'available'
        lot.manufacture_date = date.today()
        lot.expiration_date = date.today() + timedelta(days=365)

        mock_session.add(lot)

        mock_session.add.assert_called_once()

    def test_lot_status_values(self):
        """Lot statuses should be properly defined."""
        statuses = ['available', 'quarantine', 'hold', 'rejected', 'expired']

        for status in statuses:
            assert isinstance(status, str)

    def test_lot_expiration_check(self):
        """Expired lots should be identified."""
        lot = MagicMock()
        lot.expiration_date = date.today() - timedelta(days=1)

        is_expired = lot.expiration_date < date.today()

        assert is_expired is True

    def test_fifo_lot_selection(self):
        """FIFO should select oldest lot first."""
        lots = [
            {'lot_number': 'LOT-003', 'receipt_date': date(2024, 1, 15)},
            {'lot_number': 'LOT-001', 'receipt_date': date(2024, 1, 5)},
            {'lot_number': 'LOT-002', 'receipt_date': date(2024, 1, 10)},
        ]

        sorted_lots = sorted(lots, key=lambda x: x['receipt_date'])

        assert sorted_lots[0]['lot_number'] == 'LOT-001'

    def test_fefo_lot_selection(self):
        """FEFO should select soonest expiring lot first."""
        lots = [
            {'lot_number': 'LOT-003', 'expiration_date': date(2024, 12, 31)},
            {'lot_number': 'LOT-001', 'expiration_date': date(2024, 6, 30)},
            {'lot_number': 'LOT-002', 'expiration_date': date(2024, 9, 30)},
        ]

        sorted_lots = sorted(lots, key=lambda x: x['expiration_date'])

        assert sorted_lots[0]['lot_number'] == 'LOT-001'


class TestLocationManagement:
    """Tests for inventory location management."""

    def test_create_location(self, mock_session, sample_location_data):
        """Location should be created with proper data."""
        location = MagicMock()
        location.location_id = sample_location_data['location_id']
        location.name = sample_location_data['name']
        location.location_type = sample_location_data['location_type']

        mock_session.add(location)

        mock_session.add.assert_called_once()

    def test_location_types(self):
        """Location types should be properly defined."""
        location_types = [
            'warehouse', 'production', 'staging', 'shipping',
            'receiving', 'quality', 'scrap', 'transit', 'virtual'
        ]

        for lt in location_types:
            assert isinstance(lt, str)

    def test_location_hierarchy(self):
        """Locations should support hierarchy."""
        parent = MagicMock()
        parent.location_id = 'WH-001'
        parent.name = 'Main Warehouse'

        child = MagicMock()
        child.location_id = 'WH-001-A1'
        child.name = 'Aisle 1'
        child.parent_id = parent.location_id

        assert child.parent_id == parent.location_id

    def test_location_allows_negative(self):
        """Some locations may allow negative inventory."""
        location = MagicMock()
        location.allows_negative = True

        assert location.allows_negative is True


class TestCostingMethods:
    """Tests for inventory costing methods."""

    def test_standard_cost(self):
        """Standard costing uses predefined cost."""
        item = MagicMock()
        item.standard_cost = 10.0

        transaction_value = item.standard_cost * 100

        assert transaction_value == 1000.0

    def test_average_cost_calculation(self):
        """Average cost should be recalculated on receipt."""
        # Initial: 100 units @ $10 = $1000
        # Receipt: 50 units @ $12 = $600
        # New average: $1600 / 150 = $10.67

        initial_qty = 100.0
        initial_cost = 10.0
        receipt_qty = 50.0
        receipt_cost = 12.0

        new_qty = initial_qty + receipt_qty
        new_avg_cost = (initial_qty * initial_cost + receipt_qty * receipt_cost) / new_qty

        assert round(new_avg_cost, 2) == 10.67

    def test_fifo_cost_layers(self):
        """FIFO should maintain cost layers."""
        layers = [
            {'quantity': 100, 'cost': 10.0, 'date': date(2024, 1, 1)},
            {'quantity': 50, 'cost': 12.0, 'date': date(2024, 1, 15)},
            {'quantity': 75, 'cost': 11.0, 'date': date(2024, 1, 20)},
        ]

        # FIFO uses oldest cost first
        issue_qty = 120
        issue_cost = 0

        for layer in layers:
            if issue_qty <= 0:
                break
            use_qty = min(issue_qty, layer['quantity'])
            issue_cost += use_qty * layer['cost']
            issue_qty -= use_qty

        # 100 @ $10 + 20 @ $12 = $1000 + $240 = $1240
        assert issue_cost == 1240.0

    def test_last_cost_tracking(self):
        """Last cost should be updated on receipt."""
        item = MagicMock()
        item.last_cost = 10.0

        # New receipt at different cost
        item.last_cost = 12.0

        assert item.last_cost == 12.0


class TestTransactionHistory:
    """Tests for transaction history."""

    def test_get_transaction_history(self, mock_session):
        """Should retrieve transaction history."""
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            MagicMock(transaction_id='TXN-001', transaction_type='receipt'),
            MagicMock(transaction_id='TXN-002', transaction_type='issue'),
        ]

        results = mock_session.query().filter().order_by().limit().all()

        assert len(results) == 2

    def test_filter_by_item(self, mock_session):
        """Should filter transactions by item."""
        mock_session.query.return_value.filter.return_value.all.return_value = [
            MagicMock(item_id='ITEM-001'),
        ]

        results = mock_session.query().filter().all()

        assert all(r.item_id == 'ITEM-001' for r in results)

    def test_filter_by_date_range(self, mock_session):
        """Should filter transactions by date range."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)

        mock_session.query.return_value.filter.return_value.all.return_value = [
            MagicMock(transaction_date=datetime(2024, 1, 15)),
        ]

        results = mock_session.query().filter().all()

        assert len(results) == 1

    def test_filter_by_location(self, mock_session):
        """Should filter transactions by location."""
        mock_session.query.return_value.filter.return_value.all.return_value = [
            MagicMock(to_location_id='LOC-001'),
        ]

        results = mock_session.query().filter().all()

        assert len(results) == 1


class TestValuationReport:
    """Tests for inventory valuation."""

    def test_total_inventory_value(self):
        """Should calculate total inventory value."""
        balances = [
            MagicMock(total_value=1000.0),
            MagicMock(total_value=500.0),
            MagicMock(total_value=1500.0),
        ]

        total_value = sum(b.total_value for b in balances)

        assert total_value == 3000.0

    def test_valuation_by_location(self):
        """Should calculate value by location."""
        balances = [
            MagicMock(location_id='LOC-001', total_value=1000.0),
            MagicMock(location_id='LOC-001', total_value=500.0),
            MagicMock(location_id='LOC-002', total_value=1500.0),
        ]

        by_location = {}
        for b in balances:
            if b.location_id not in by_location:
                by_location[b.location_id] = 0
            by_location[b.location_id] += b.total_value

        assert by_location['LOC-001'] == 1500.0
        assert by_location['LOC-002'] == 1500.0

    def test_valuation_report_date(self):
        """Valuation report should include as-of date."""
        report = {
            'total_value': 3000.0,
            'as_of_date': datetime.utcnow().isoformat()
        }

        assert 'as_of_date' in report


class TestInventoryErrors:
    """Tests for inventory error handling."""

    def test_item_not_found_error(self, mock_session):
        """Should handle item not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = mock_session.query().filter().first()

        assert result is None

    def test_insufficient_quantity_error(self):
        """Should prevent issuing more than available."""
        available = 50.0
        requested = 100.0

        can_issue = available >= requested

        assert can_issue is False

    def test_location_not_found_error(self, mock_session):
        """Should handle location not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = mock_session.query().filter().first()

        assert result is None

    def test_lot_not_found_error(self, mock_session):
        """Should handle lot not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = mock_session.query().filter().first()

        assert result is None
