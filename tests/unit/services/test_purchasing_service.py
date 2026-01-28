"""Unit tests for Purchasing Service - requisition, PO management, goods receipt."""
import pytest
from datetime import date, datetime
from unittest.mock import Mock, patch, MagicMock
from enum import Enum

from services.erp.purchasing_service import PurchasingService, get_purchasing_service


class MockRequisitionStatus(Enum):
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    APPROVED = 'approved'


class MockPurchaseOrderStatus(Enum):
    DRAFT = 'draft'
    APPROVED = 'approved'
    SENT = 'sent'
    ACKNOWLEDGED = 'acknowledged'
    PARTIALLY_RECEIVED = 'partially_received'
    RECEIVED = 'received'


class MockReceiptStatus(Enum):
    PENDING = 'pending'
    COMPLETED = 'completed'


class TestPurchasingServiceInit:
    """Tests for PurchasingService initialization."""

    def test_init_with_session(self):
        """Test service initialization with session."""
        mock_session = Mock()
        assert PurchasingService(mock_session).session == mock_session

    def test_get_purchasing_service_with_session(self):
        """Test getting service with provided session."""
        assert isinstance(get_purchasing_service(Mock()), PurchasingService)


class TestRequisitionWorkflow:
    """Tests for purchase requisition operations."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return PurchasingService(mock_session)

    def test_create_requisition_success(self, service, mock_session):
        """Test creating a requisition successfully."""
        with patch('models.erp.purchasing.PurchaseRequisition') as MockReq, \
             patch('models.erp.purchasing.RequisitionStatus', MockRequisitionStatus):
            mock_req = Mock()
            mock_req.requisition_number = 'REQ-001'
            mock_req.to_dict.return_value = {'requisition_number': 'REQ-001'}
            MockReq.return_value = mock_req

            result = service.create_requisition({'requested_by': 'user_001'})

            assert result['requisition_number'] == 'REQ-001'
            mock_session.add.assert_called_once()
            mock_session.flush.assert_called()

    def test_add_requisition_line_success(self, service, mock_session):
        """Test adding a line to a requisition."""
        # Create mock requisition
        mock_requisition = Mock()
        mock_requisition.id = 1
        mock_requisition.lines = []
        mock_requisition.estimated_total = 0

        # Create mock item
        mock_item = Mock()
        mock_item.id = 10
        mock_item.name = 'Brick'
        mock_item.base_uom = 'EA'
        mock_item.standard_cost = 0.05

        # Setup query chain to return requisition first, then item
        def query_side_effect(model):
            query_mock = Mock()
            filter_mock = Mock()
            query_mock.filter.return_value = filter_mock
            # Use a list to track calls
            if not hasattr(query_side_effect, 'call_count'):
                query_side_effect.call_count = 0
            query_side_effect.call_count += 1
            if query_side_effect.call_count == 1:
                filter_mock.first.return_value = mock_requisition
            else:
                filter_mock.first.return_value = mock_item
            return query_mock

        mock_session.query.side_effect = query_side_effect

        with patch('models.erp.purchasing.PurchaseRequisition'), \
             patch('models.erp.purchasing.PurchaseRequisitionLine') as MockLine, \
             patch('models.erp.items.Item'):
            mock_line = Mock()
            mock_line.quantity = 1000
            mock_line.estimated_unit_cost = 0.05
            mock_line.estimated_total = 50.0
            mock_line.to_dict.return_value = {'quantity': 1000}
            MockLine.return_value = mock_line

            result = service.add_requisition_line('REQ-001', {'item_id': 'X', 'quantity': 1000})

            assert result['quantity'] == 1000

    def test_add_requisition_line_not_found(self, service, mock_session):
        """Test adding line when requisition or item not found."""
        # Both queries return None
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.add_requisition_line('X', {'item_id': 'X', 'quantity': 10})

        assert result is None


class TestPurchaseOrderManagement:
    """Tests for purchase order operations."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return PurchasingService(mock_session)

    def test_create_purchase_order_success(self, service, mock_session):
        """Test creating a purchase order successfully."""
        # Create mock vendor
        mock_vendor = Mock()
        mock_vendor.id = 1
        mock_vendor.payment_terms = Mock(value='net_30')

        # Query returns vendor
        mock_session.query.return_value.filter.return_value.first.return_value = mock_vendor

        with patch('models.erp.purchasing.PurchaseOrder') as MockPO, \
             patch('models.erp.purchasing.PurchaseOrderStatus', MockPurchaseOrderStatus), \
             patch('models.erp.partners.Partner'):
            mock_po = Mock()
            mock_po.po_number = 'PO-001'
            mock_po.lines = []
            mock_po.subtotal = 0
            mock_po.tax_amount = 0
            mock_po.discount_amount = 0
            mock_po.freight_amount = 0
            mock_po.total = 0
            mock_po.to_dict.return_value = {'po_number': 'PO-001'}
            MockPO.return_value = mock_po

            result = service.create_purchase_order({'vendor_id': 'V1'})

            assert result['po_number'] == 'PO-001'

    def test_create_purchase_order_vendor_not_found(self, service, mock_session):
        """Test creating PO when vendor not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match='Vendor X not found'):
            service.create_purchase_order({'vendor_id': 'X'})

    def test_add_po_line_success(self, service, mock_session):
        """Test adding a line to a purchase order."""
        # Create mock PO
        mock_po = Mock()
        mock_po.id = 1
        mock_po.lines = []
        mock_po.subtotal = 0
        mock_po.tax_amount = 0
        mock_po.discount_amount = 0
        mock_po.freight_amount = 0

        # Create mock item
        mock_item = Mock()
        mock_item.id = 10
        mock_item.name = 'Brick'
        mock_item.base_uom = 'EA'
        mock_item.standard_cost = 0.05

        # Setup query chain to return PO first, then item
        call_count = [0]

        def query_side_effect(model):
            query_mock = Mock()
            filter_mock = Mock()
            query_mock.filter.return_value = filter_mock
            call_count[0] += 1
            if call_count[0] == 1:
                filter_mock.first.return_value = mock_po
            else:
                filter_mock.first.return_value = mock_item
            return query_mock

        mock_session.query.side_effect = query_side_effect

        with patch('models.erp.purchasing.PurchaseOrder'), \
             patch('models.erp.purchasing.PurchaseOrderLine') as MockLine, \
             patch('models.erp.items.Item'):
            mock_line = Mock()
            mock_line.line_number = 1
            mock_line.quantity_ordered = 5000
            mock_line.unit_price = 0.05
            mock_line.discount_percent = 0
            mock_line.line_total = 250.0
            mock_line.tax_amount = 0
            mock_line.to_dict.return_value = {'line_number': 1}
            MockLine.return_value = mock_line

            result = service.add_po_line('PO-001', {'item_id': 'X', 'quantity': 5000})

            assert result is not None

    def test_add_po_line_not_found(self, service, mock_session):
        """Test adding line when PO not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.add_po_line('X', {'item_id': 'X', 'quantity': 10})

        assert result is None

    def test_get_purchase_order_success(self, service, mock_session):
        """Test getting a purchase order."""
        mock_line = Mock()
        mock_line.to_dict.return_value = {'line_number': 1}

        mock_vendor = Mock()
        mock_vendor.to_dict.return_value = {'name': 'Supplier'}

        mock_po = Mock()
        mock_po.to_dict.return_value = {'po_number': 'PO-001'}
        mock_po.lines = [mock_line]
        mock_po.vendor = mock_vendor

        mock_session.query.return_value.filter.return_value.first.return_value = mock_po

        result = service.get_purchase_order('PO-001')

        assert result['po_number'] == 'PO-001'
        assert 'lines' in result
        assert 'vendor' in result

    def test_get_purchase_order_not_found(self, service, mock_session):
        """Test getting non-existent purchase order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.get_purchase_order('X')

        assert result is None

    def test_get_purchase_orders_with_filters(self, service, mock_session):
        """Test getting purchase orders with filters."""
        mock_po = Mock()
        mock_po.to_dict.return_value = {'po_number': 'PO-001'}

        mock_vendor = Mock()
        mock_vendor.id = 1

        # Build a chainable mock query
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_po]
        mock_query.first.return_value = mock_vendor

        mock_session.query.return_value = mock_query

        with patch('models.erp.purchasing.PurchaseOrder') as MockPO, \
             patch('models.erp.purchasing.PurchaseOrderStatus', MockPurchaseOrderStatus), \
             patch('models.erp.partners.Partner'):
            MockPO.is_deleted = False
            MockPO.vendor_id = 1
            MockPO.status = 'approved'
            MockPO.order_date = Mock()
            MockPO.order_date.desc.return_value = 'desc'

            result = service.get_purchase_orders(vendor_id='V1', status='approved', limit=50)

            assert len(result) == 1


class TestPOApprovalWorkflow:
    """Tests for PO approval and sending workflow."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return PurchasingService(mock_session)

    def test_approve_po_success(self, service, mock_session):
        """Test approving a purchase order."""
        mock_po = Mock()
        mock_po.to_dict.return_value = {'status': 'approved'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_po

        with patch('models.erp.purchasing.PurchaseOrder'), \
             patch('models.erp.purchasing.PurchaseOrderStatus', MockPurchaseOrderStatus):
            result = service.approve_po('PO-001', 'approver')

            assert result is not None
            assert mock_po.approved_by == 'approver'
            assert mock_po.status == MockPurchaseOrderStatus.APPROVED

    def test_approve_po_not_found(self, service, mock_session):
        """Test approving non-existent PO."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.approve_po('X', 'user')

        assert result is None

    def test_send_po_success(self, service, mock_session):
        """Test sending an approved PO."""
        mock_po = Mock()
        mock_po.status = MockPurchaseOrderStatus.APPROVED
        mock_po.to_dict.return_value = {'status': 'sent'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_po

        with patch('models.erp.purchasing.PurchaseOrder'), \
             patch('models.erp.purchasing.PurchaseOrderStatus', MockPurchaseOrderStatus):
            result = service.send_po('PO-001', 'sender')

            assert result is not None
            assert mock_po.status == MockPurchaseOrderStatus.SENT

    def test_send_po_not_approved(self, service, mock_session):
        """Test sending a non-approved PO returns None."""
        mock_po = Mock()
        mock_po.status = MockPurchaseOrderStatus.DRAFT  # Not approved
        mock_session.query.return_value.filter.return_value.first.return_value = mock_po

        with patch('models.erp.purchasing.PurchaseOrderStatus', MockPurchaseOrderStatus):
            result = service.send_po('PO-001', 'sender')

            assert result is None


class TestGoodsReceipt:
    """Tests for goods receipt operations."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return PurchasingService(mock_session)

    def test_receive_goods_full_receipt(self, service, mock_session):
        """Test receiving full order for a PO."""
        mock_po_line = Mock()
        mock_po_line.line_number = 1
        mock_po_line.item_id = 10
        mock_po_line.uom = 'EA'
        mock_po_line.unit_price = 0.05
        mock_po_line.quantity_ordered = 1000
        mock_po_line.quantity_received = 0
        mock_po_line.quantity_rejected = 0

        mock_po = Mock()
        mock_po.id = 1
        mock_po.vendor_id = 1
        mock_po.lines = [mock_po_line]
        mock_po.quantity_received = 0

        mock_session.query.return_value.filter.return_value.first.return_value = mock_po

        with patch('models.erp.purchasing.PurchaseOrder'), \
             patch('models.erp.purchasing.Receipt') as MockReceipt, \
             patch('models.erp.purchasing.ReceiptLine'), \
             patch('models.erp.purchasing.ReceiptStatus', MockReceiptStatus), \
             patch('models.erp.purchasing.PurchaseOrderStatus', MockPurchaseOrderStatus), \
             patch('models.erp.inventory.Lot'):
            mock_receipt = Mock()
            mock_receipt.id = 1
            mock_receipt.receipt_date = date.today()
            mock_receipt.to_dict.return_value = {'receipt_number': 'RCV-001'}
            MockReceipt.return_value = mock_receipt

            result = service.receive_goods('PO-001', {'lines': [{'line_number': 1, 'quantity_received': 1000}]})

            assert result is not None
            assert mock_po.status == MockPurchaseOrderStatus.RECEIVED

    def test_receive_goods_partial(self, service, mock_session):
        """Test partial goods receipt."""
        mock_po_line = Mock()
        mock_po_line.line_number = 1
        mock_po_line.item_id = 10
        mock_po_line.uom = 'EA'
        mock_po_line.unit_price = 0.05
        mock_po_line.quantity_ordered = 1000
        mock_po_line.quantity_received = 0
        mock_po_line.quantity_rejected = 0

        mock_po = Mock()
        mock_po.id = 1
        mock_po.vendor_id = 1
        mock_po.lines = [mock_po_line]
        mock_po.quantity_received = 0

        mock_session.query.return_value.filter.return_value.first.return_value = mock_po

        with patch('models.erp.purchasing.PurchaseOrder'), \
             patch('models.erp.purchasing.Receipt') as MockReceipt, \
             patch('models.erp.purchasing.ReceiptLine'), \
             patch('models.erp.purchasing.ReceiptStatus', MockReceiptStatus), \
             patch('models.erp.purchasing.PurchaseOrderStatus', MockPurchaseOrderStatus), \
             patch('models.erp.inventory.Lot'):
            mock_receipt = Mock()
            mock_receipt.id = 1
            mock_receipt.receipt_date = date.today()
            mock_receipt.to_dict.return_value = {'receipt_number': 'RCV-001'}
            MockReceipt.return_value = mock_receipt

            result = service.receive_goods('PO-001', {'lines': [{'line_number': 1, 'quantity_received': 500}]})

            assert result is not None
            assert mock_po.status == MockPurchaseOrderStatus.PARTIALLY_RECEIVED

    def test_receive_goods_po_not_found(self, service, mock_session):
        """Test goods receipt when PO not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None

        result = service.receive_goods('X', {'lines': []})

        assert result is None


class TestOpenPOReport:
    """Tests for open PO report generation."""

    @pytest.fixture
    def mock_session(self):
        return Mock()

    @pytest.fixture
    def service(self, mock_session):
        return PurchasingService(mock_session)

    def test_get_open_po_report(self, service, mock_session):
        """Test getting open PO report."""
        # Create mock queries for count and sum
        mock_count_query = Mock()
        mock_count_query.filter.return_value = mock_count_query
        mock_count_query.scalar.return_value = 15

        mock_sum_query = Mock()
        mock_sum_query.filter.return_value = mock_sum_query
        mock_sum_query.scalar.return_value = 25000.50

        mock_session.query.side_effect = [mock_count_query, mock_sum_query]

        with patch('models.erp.purchasing.PurchaseOrder') as MockPO, \
             patch('models.erp.purchasing.PurchaseOrderStatus', MockPurchaseOrderStatus):
            MockPO.id = 1
            MockPO.status = Mock()
            MockPO.status.in_ = Mock(return_value=True)
            MockPO.is_deleted = False
            MockPO.total = 25000.50

            result = service.get_open_po_report()

            assert result['open_pos'] == 15
            assert result['total_value'] == 25000.50
            assert 'as_of_date' in result

    def test_get_open_po_report_empty(self, service, mock_session):
        """Test open PO report with no open POs."""
        # Create mock queries for count and sum
        mock_count_query = Mock()
        mock_count_query.filter.return_value = mock_count_query
        mock_count_query.scalar.return_value = 0

        mock_sum_query = Mock()
        mock_sum_query.filter.return_value = mock_sum_query
        mock_sum_query.scalar.return_value = None

        mock_session.query.side_effect = [mock_count_query, mock_sum_query]

        with patch('models.erp.purchasing.PurchaseOrder') as MockPO, \
             patch('models.erp.purchasing.PurchaseOrderStatus', MockPurchaseOrderStatus):
            MockPO.id = 1
            MockPO.status = Mock()
            MockPO.status.in_ = Mock(return_value=True)
            MockPO.is_deleted = False
            MockPO.total = 0

            result = service.get_open_po_report()

            assert result['open_pos'] == 0
            assert result['total_value'] == 0.0
