"""
Unit tests for Sales Service.

Tests quote creation, order management, shipments, and reporting.
"""

import pytest
from datetime import date, datetime
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal

from services.erp.sales_service import SalesService, get_sales_service


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    return session


@pytest.fixture
def service(mock_session):
    """Create a SalesService with mock session."""
    return SalesService(mock_session)


@pytest.fixture
def mock_customer():
    """Create a mock customer."""
    customer = Mock()
    customer.id = 1
    customer.partner_id = "CUST-001"
    customer.payment_terms = Mock(value="net_30")
    customer.salesperson_id = 10
    return customer


@pytest.fixture
def mock_item():
    """Create a mock item."""
    item = Mock()
    item.id = 100
    item.item_id = "ITEM-001"
    item.name = "Test Item"
    item.base_uom = "EA"
    item.list_price = Decimal("99.99")
    item.standard_cost = Decimal("50.00")
    return item


class TestQuoteOperations:
    """Tests for quote-related operations."""

    def test_create_quote_success(self, service, mock_session, mock_customer):
        """Test successful quote creation."""
        # Mock customer lookup
        mock_session.query.return_value.filter.return_value.first.return_value = mock_customer

        # Mock the _recalculate_quote_totals method to avoid issues with mock quote
        with patch.object(service, '_recalculate_quote_totals'):
            result = service.create_quote({"customer_id": "CUST-001"})

        # The service adds a quote object to session
        mock_session.add.assert_called()
        mock_session.flush.assert_called()

    def test_create_quote_customer_not_found(self, service, mock_session):
        """Test quote creation with invalid customer."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="Customer CUST-999 not found"):
            service.create_quote({"customer_id": "CUST-999"})

    def test_add_quote_line_success(self, service, mock_session, mock_item):
        """Test adding a line to a quote."""
        # Create mock quote with required attributes
        mock_quote = Mock()
        mock_quote.id = 1
        mock_quote.lines = []

        # Configure session.query to return quote first, then item
        mock_session.query.return_value.filter.return_value.first.side_effect = [mock_quote, mock_item]

        # Mock the _recalculate_quote_totals method
        with patch.object(service, '_recalculate_quote_totals'):
            result = service.add_quote_line("QT-001", {"item_id": "ITEM-001", "quantity": 10})

        # Verify session interactions
        mock_session.add.assert_called()
        mock_session.flush.assert_called()

    def test_add_quote_line_quote_not_found(self, service, mock_session):
        """Test adding line when quote not found returns None."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.add_quote_line("QT-INVALID", {"item_id": "ITEM-001", "quantity": 10})
        assert result is None

    def test_add_quote_line_item_not_found(self, service, mock_session):
        """Test adding line when item not found returns None."""
        mock_quote = Mock()
        mock_quote.id = 1
        mock_quote.lines = []
        # First call returns quote, second returns None (item not found)
        mock_session.query.return_value.filter.return_value.first.side_effect = [mock_quote, None]
        result = service.add_quote_line("QT-001", {"item_id": "ITEM-INVALID", "quantity": 10})
        assert result is None


class TestQuoteToOrderConversion:
    """Tests for quote-to-order conversion workflow."""

    def test_convert_quote_to_order_success(self, service, mock_session):
        """Test successful quote to order conversion."""
        # Create a mock quote with ACCEPTED status
        mock_quote = Mock()
        mock_quote.id = 1
        mock_quote.customer_id = 1
        mock_quote.lines = []
        mock_quote.currency = "USD"
        mock_quote.exchange_rate = 1.0
        mock_quote.subtotal = Decimal("1000")
        mock_quote.discount_amount = 0
        mock_quote.tax_amount = 0
        mock_quote.freight_amount = 0
        mock_quote.total = Decimal("1000")
        mock_quote.requested_date = date.today()
        mock_quote.price_list_id = None
        mock_quote.ship_to_address_id = None
        mock_quote.shipping_method = "Ground"
        mock_quote.payment_terms = "net_30"
        mock_quote.customer_po = "PO-123"
        mock_quote.salesperson_id = 10
        mock_quote.notes = ""

        # Import the actual QuoteStatus to set the correct status
        from models.erp.sales import QuoteStatus
        mock_quote.status = QuoteStatus.ACCEPTED

        mock_session.query.return_value.filter.return_value.first.return_value = mock_quote

        result = service.convert_quote_to_order("QT-001")

        assert result is not None
        mock_session.add.assert_called()
        mock_session.flush.assert_called()
        # Verify quote status was changed to CONVERTED
        assert mock_quote.status == QuoteStatus.CONVERTED

    def test_convert_quote_not_found(self, service, mock_session):
        """Test conversion fails for nonexistent quote."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.convert_quote_to_order("QT-INVALID")
        assert result is None

    def test_convert_quote_not_accepted(self, service, mock_session):
        """Test conversion fails for non-accepted quote."""
        from models.erp.sales import QuoteStatus
        mock_quote = Mock()
        mock_quote.status = QuoteStatus.DRAFT  # Not ACCEPTED

        mock_session.query.return_value.filter.return_value.first.return_value = mock_quote
        result = service.convert_quote_to_order("QT-001")
        assert result is None


class TestOrderManagement:
    """Tests for order management operations."""

    def test_create_order_success(self, service, mock_session, mock_customer):
        """Test successful order creation."""
        mock_session.query.return_value.filter.return_value.first.return_value = mock_customer

        # Mock the _recalculate_order_totals method
        with patch.object(service, '_recalculate_order_totals'):
            result = service.create_order({"customer_id": "CUST-001"})

        mock_session.add.assert_called()
        mock_session.flush.assert_called()

    def test_create_order_customer_not_found(self, service, mock_session):
        """Test order creation with invalid customer."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(ValueError, match="Customer CUST-999 not found"):
            service.create_order({"customer_id": "CUST-999"})

    def test_add_order_line_success(self, service, mock_session, mock_item):
        """Test adding a line to an order."""
        mock_order = Mock()
        mock_order.id = 1
        mock_order.lines = []

        mock_session.query.return_value.filter.return_value.first.side_effect = [mock_order, mock_item]

        with patch.object(service, '_recalculate_order_totals'):
            result = service.add_order_line("SO-001", {"item_id": "ITEM-001", "quantity": 5})

        mock_session.add.assert_called()
        mock_session.flush.assert_called()

    def test_add_order_line_order_not_found(self, service, mock_session):
        """Test adding line returns None when order not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.add_order_line("SO-INVALID", {"item_id": "ITEM-001", "quantity": 5})
        assert result is None

    def test_add_order_line_item_not_found(self, service, mock_session):
        """Test adding line returns None when item not found."""
        mock_order = Mock()
        mock_order.id = 1
        mock_order.lines = []
        mock_session.query.return_value.filter.return_value.first.side_effect = [mock_order, None]
        result = service.add_order_line("SO-001", {"item_id": "ITEM-INVALID", "quantity": 5})
        assert result is None

    def test_get_order_success(self, service, mock_session):
        """Test retrieving an order."""
        mock_order = Mock()
        mock_order.lines = []
        mock_order.customer = Mock()
        mock_order.to_dict.return_value = {"order_number": "SO-001"}
        mock_order.customer.to_dict.return_value = {"name": "Test Customer"}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_order

        result = service.get_order("SO-001")

        assert result is not None
        assert result["order_number"] == "SO-001"
        assert "customer" in result
        assert result["customer"]["name"] == "Test Customer"

    def test_get_order_not_found(self, service, mock_session):
        """Test retrieving nonexistent order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.get_order("SO-INVALID")
        assert result is None

    def test_get_orders_with_filters(self, service, mock_session):
        """Test retrieving orders with filters."""
        mock_orders = [
            Mock(to_dict=Mock(return_value={"order_number": "SO-001"})),
            Mock(to_dict=Mock(return_value={"order_number": "SO-002"})),
        ]
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_orders
        mock_session.query.return_value = mock_query

        result = service.get_orders(
            customer_id="CUST-001",
            status="draft",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31)
        )

        assert len(result) == 2
        assert result[0]["order_number"] == "SO-001"
        assert result[1]["order_number"] == "SO-002"

    def test_get_orders_empty_result(self, service, mock_session):
        """Test retrieving orders with no matches."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query

        result = service.get_orders()
        assert result == []


class TestOrderRelease:
    """Tests for order release functionality."""

    def test_release_order_success(self, service, mock_session):
        """Test successful order release."""
        from models.erp.sales import SalesOrderStatus

        mock_order = Mock()
        mock_order.status = SalesOrderStatus.APPROVED
        mock_order.to_dict.return_value = {"order_number": "SO-001", "status": "RELEASED"}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_order

        result = service.release_order("SO-001", "user_001")

        assert result is not None
        assert result["status"] == "RELEASED"
        assert mock_order.status == SalesOrderStatus.RELEASED
        assert mock_order.updated_by == "user_001"
        mock_session.flush.assert_called()

    def test_release_order_not_found(self, service, mock_session):
        """Test releasing fails for nonexistent order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.release_order("SO-INVALID")
        assert result is None

    def test_release_order_wrong_status(self, service, mock_session):
        """Test releasing fails for non-approved order."""
        from models.erp.sales import SalesOrderStatus

        mock_order = Mock()
        mock_order.status = SalesOrderStatus.DRAFT  # Not APPROVED
        mock_session.query.return_value.filter.return_value.first.return_value = mock_order

        result = service.release_order("SO-001")
        assert result is None


class TestShipmentCreation:
    """Tests for shipment creation."""

    def test_create_shipment_success(self, service, mock_session):
        """Test successful shipment creation and quantity update."""
        mock_order_line = Mock()
        mock_order_line.line_number = 1
        mock_order_line.id = 10
        mock_order_line.item_id = 100
        mock_order_line.uom = "EA"
        mock_order_line.quantity_shipped = 0

        mock_order = Mock()
        mock_order.id = 1
        mock_order.lines = [mock_order_line]

        mock_session.query.return_value.filter.return_value.first.return_value = mock_order

        result = service.create_shipment("SO-001", {
            "carrier": "UPS",
            "lines": [{"line_number": 1, "quantity": 5}]
        })

        assert result is not None
        assert mock_order_line.quantity_shipped == 5
        mock_session.add.assert_called()
        mock_session.flush.assert_called()

    def test_create_shipment_order_not_found(self, service, mock_session):
        """Test shipment creation for nonexistent order."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.create_shipment("SO-INVALID", {"carrier": "UPS"})
        assert result is None

    def test_create_shipment_line_not_found(self, service, mock_session):
        """Test shipment creation when order line is not found."""
        mock_order = Mock()
        mock_order.id = 1
        mock_order.lines = []  # No lines

        mock_session.query.return_value.filter.return_value.first.return_value = mock_order

        result = service.create_shipment("SO-001", {
            "carrier": "UPS",
            "lines": [{"line_number": 1, "quantity": 5}]  # Line 1 doesn't exist
        })

        # Shipment should still be created, just without lines
        assert result is not None


class TestOpenOrdersReport:
    """Tests for open orders reporting."""

    def test_get_open_orders_report(self, service, mock_session):
        """Test getting open orders report with orders."""
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [10, 50000.00]

        result = service.get_open_orders_report()

        assert result["open_orders"] == 10
        assert result["total_value"] == 50000.00
        assert "as_of_date" in result

    def test_get_open_orders_report_no_orders(self, service, mock_session):
        """Test open orders report with no orders."""
        mock_session.query.return_value.filter.return_value.scalar.side_effect = [0, None]

        result = service.get_open_orders_report()

        assert result["open_orders"] == 0
        assert result["total_value"] == 0.0
        assert "as_of_date" in result


class TestGetSalesServiceFactory:
    """Tests for get_sales_service factory function."""

    def test_get_sales_service_with_session(self):
        """Test factory with provided session."""
        mock_session = Mock()
        result = get_sales_service(mock_session)
        assert isinstance(result, SalesService)
        assert result.session is mock_session

    def test_get_sales_service_without_session(self):
        """Test factory without session uses context manager."""
        with patch("services.erp.sales_service.get_db_session") as mock_get_db:
            mock_context = MagicMock()
            mock_session = Mock()
            mock_context.__enter__ = Mock(return_value=mock_session)
            mock_context.__exit__ = Mock(return_value=False)
            mock_get_db.return_value = mock_context

            result = get_sales_service()

            assert isinstance(result, SalesService)
            mock_get_db.assert_called_once()


class TestRecalculateTotals:
    """Tests for total recalculation methods."""

    def test_recalculate_quote_totals(self, service, mock_session):
        """Test quote totals recalculation."""
        mock_line1 = Mock(line_total=Decimal("100.00"), tax_amount=Decimal("10.00"))
        mock_line2 = Mock(line_total=Decimal("200.00"), tax_amount=Decimal("20.00"))

        mock_quote = Mock()
        mock_quote.lines = [mock_line1, mock_line2]
        mock_quote.discount_amount = Decimal("0")
        mock_quote.freight_amount = Decimal("15.00")

        service._recalculate_quote_totals(mock_quote)

        assert mock_quote.subtotal == Decimal("300.00")
        assert mock_quote.tax_amount == Decimal("30.00")
        assert mock_quote.total == Decimal("345.00")  # 300 - 0 + 30 + 15
        mock_session.flush.assert_called()

    def test_recalculate_order_totals(self, service, mock_session):
        """Test order totals recalculation."""
        mock_line1 = Mock(line_total=Decimal("150.00"), tax_amount=Decimal("15.00"))
        mock_line2 = Mock(line_total=Decimal("250.00"), tax_amount=None)

        mock_order = Mock()
        mock_order.lines = [mock_line1, mock_line2]
        mock_order.discount_amount = Decimal("25.00")
        mock_order.freight_amount = Decimal("20.00")

        service._recalculate_order_totals(mock_order)

        assert mock_order.subtotal == Decimal("400.00")
        assert mock_order.tax_amount == Decimal("15.00")
        assert mock_order.total == Decimal("410.00")  # 400 - 25 + 15 + 20
        mock_session.flush.assert_called()
