"""
Unit tests for CMMS Asset Service.

Tests asset CRUD operations, meter management, hierarchy, and status tracking.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from services.cmms.asset_service import AssetService, get_asset_service


class TestAssetService:
    """Tests for AssetService database operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock database session."""
        session = Mock()
        session.add = Mock()
        session.flush = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def service(self, mock_session):
        """Create an AssetService with mock session."""
        return AssetService(mock_session)

    # Asset CRUD Tests
    def test_create_asset_minimal(self, service, mock_session):
        """Test creating an asset with minimal data."""
        with patch('models.cmms.assets.Asset') as MockAsset:
            mock_asset = Mock()
            mock_asset.to_dict.return_value = {'asset_id': 'AST-12345678', 'name': 'Test Motor'}
            MockAsset.return_value = mock_asset
            result = service.create_asset({'name': 'Test Motor'})
            mock_session.add.assert_called_once()
            assert result['name'] == 'Test Motor'

    def test_create_asset_full_data(self, service, mock_session):
        """Test creating an asset with all fields."""
        with patch('models.cmms.assets.Asset') as MockAsset:
            mock_asset = Mock()
            mock_asset.to_dict.return_value = {'asset_id': 'AST-CUSTOM01', 'criticality': 'critical'}
            MockAsset.return_value = mock_asset
            result = service.create_asset({
                'asset_id': 'AST-CUSTOM01', 'name': 'Motor', 'criticality': 'critical'
            })
            assert result['criticality'] == 'critical'

    def test_get_asset_found(self, service, mock_session):
        """Test getting an existing asset."""
        mock_asset = Mock()
        mock_asset.to_dict.return_value = {'asset_id': 'AST-001', 'name': 'Test Asset'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset
        result = service.get_asset('AST-001')
        assert result['asset_id'] == 'AST-001'

    def test_get_asset_not_found(self, service, mock_session):
        """Test getting a non-existent asset."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.get_asset('NONEXISTENT')
        assert result is None

    def test_get_assets_no_filters(self, service, mock_session):
        """Test getting assets without filters."""
        mock_assets = [Mock(to_dict=Mock(return_value={'asset_id': f'AST-00{i}'})) for i in range(2)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_assets
        mock_session.query.return_value = mock_query
        result = service.get_assets()
        assert len(result) == 2

    def test_get_assets_with_filters(self, service, mock_session):
        """Test getting assets with status and pagination filters."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        service.get_assets(status='operational', limit=10, offset=5)
        mock_query.offset.assert_called_with(5)
        mock_query.limit.assert_called_with(10)

    def test_update_asset_success(self, service, mock_session):
        """Test updating an existing asset."""
        mock_asset = Mock()
        mock_asset.to_dict.return_value = {'asset_id': 'AST-001', 'name': 'Updated'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset
        result = service.update_asset('AST-001', {'name': 'Updated'})
        assert result['name'] == 'Updated'
        mock_session.flush.assert_called_once()

    def test_update_asset_not_found(self, service, mock_session):
        """Test updating a non-existent asset."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.update_asset('NONEXISTENT', {'name': 'Updated'})
        assert result is None

    def test_update_status_success(self, service, mock_session):
        """Test updating asset status."""
        mock_asset = Mock()
        mock_asset.to_dict.return_value = {'asset_id': 'AST-001', 'status': 'maintenance'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_asset
        result = service.update_status('AST-001', 'maintenance', 'user_001')
        assert result['status'] == 'maintenance'

    def test_update_status_not_found(self, service, mock_session):
        """Test updating status of non-existent asset."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.update_status('NONEXISTENT', 'maintenance')
        assert result is None

    # Asset Class Tests
    def test_create_asset_class(self, service, mock_session):
        """Test creating an asset class."""
        with patch('models.cmms.assets.AssetClass') as MockClass:
            mock_class = Mock()
            mock_class.to_dict.return_value = {'code': 'MOTOR', 'name': 'Electric Motors'}
            MockClass.return_value = mock_class
            result = service.create_asset_class({'code': 'MOTOR', 'name': 'Electric Motors'})
            mock_session.add.assert_called_once()
            assert result['code'] == 'MOTOR'

    def test_get_asset_classes(self, service, mock_session):
        """Test getting all asset classes."""
        mock_classes = [Mock(to_dict=Mock(return_value={'code': 'MOTOR'}))]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = mock_classes
        mock_session.query.return_value = mock_query
        result = service.get_asset_classes()
        assert len(result) == 1

    def test_get_asset_classes_empty(self, service, mock_session):
        """Test getting asset classes when none exist."""
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        result = service.get_asset_classes()
        assert result == []

    # Meter Management Tests
    def test_create_meter_success(self, service, mock_session):
        """Test creating a meter for an asset."""
        mock_asset = Mock(id=1)
        mock_meter = Mock()
        mock_meter.to_dict.return_value = {'meter_id': 'MTR-001', 'name': 'Runtime Hours'}
        with patch('models.cmms.assets.Meter') as MockMeter:
            MockMeter.return_value = mock_meter
            mock_session.query.return_value.filter.return_value.first.return_value = mock_asset
            result = service.create_meter('AST-001', {'name': 'Runtime Hours'})
            assert result['name'] == 'Runtime Hours'

    def test_create_meter_asset_not_found(self, service, mock_session):
        """Test creating a meter for non-existent asset."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.create_meter('NONEXISTENT', {'name': 'Test'})
        assert result is None

    def test_get_meters_success(self, service, mock_session):
        """Test getting meters for an asset."""
        mock_asset = Mock(id=1)
        mock_meters = [Mock(to_dict=Mock(return_value={'meter_id': 'MTR-001'}))]
        with patch.object(service.session, 'query') as mock_q:
            mock_q.return_value.filter.return_value.first.return_value = mock_asset
            mock_q.return_value.filter.return_value.all.return_value = mock_meters
            result = service.get_meters('AST-001')
            assert len(result) == 1

    def test_get_meters_asset_not_found(self, service, mock_session):
        """Test getting meters for non-existent asset."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.get_meters('NONEXISTENT')
        assert result == []

    # Meter Reading Tests
    def test_record_meter_reading_success(self, service, mock_session):
        """Test recording a meter reading."""
        mock_meter = Mock(id=1, last_reading=100.0, rollover_value=None,
                          critical_threshold=None, warning_threshold=None)
        mock_reading = Mock()
        mock_reading.to_dict.return_value = {'reading_value': 150.0, 'delta': 50.0}
        with patch('models.cmms.assets.MeterReading') as MockReading:
            MockReading.return_value = mock_reading
            mock_session.query.return_value.filter.return_value.first.return_value = mock_meter
            result = service.record_meter_reading('MTR-001', 150.0)
            assert result is not None
            mock_session.add.assert_called_once()

    def test_record_meter_reading_not_found(self, service, mock_session):
        """Test recording reading for non-existent meter."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.record_meter_reading('NONEXISTENT', 100.0)
        assert result is None

    def test_get_meter_readings_success(self, service, mock_session):
        """Test getting meter readings."""
        mock_meter = Mock(id=1)
        mock_readings = [Mock(to_dict=Mock(return_value={'reading_value': 150.0}))]
        with patch.object(service.session, 'query') as mock_q:
            mock_q.return_value.filter.return_value.first.return_value = mock_meter
            mock_q.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = mock_readings
            result = service.get_meter_readings('MTR-001')
            assert len(result) == 1

    def test_get_meter_readings_not_found(self, service, mock_session):
        """Test getting readings for non-existent meter."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.get_meter_readings('NONEXISTENT')
        assert result == []

    # Hierarchy Tests
    def test_get_asset_hierarchy_with_root(self, service, mock_session):
        """Test getting hierarchy from a root asset."""
        mock_child = Mock(is_deleted=False, child_assets=[])
        mock_child.to_dict.return_value = {'asset_id': 'AST-002'}
        mock_root = Mock(is_deleted=False, child_assets=[mock_child])
        mock_root.to_dict.return_value = {'asset_id': 'AST-001'}
        mock_session.query.return_value.filter.return_value.first.return_value = mock_root
        result = service.get_asset_hierarchy('AST-001')
        assert len(result) >= 1

    def test_get_asset_hierarchy_root_not_found(self, service, mock_session):
        """Test getting hierarchy when root not found."""
        mock_session.query.return_value.filter.return_value.first.return_value = None
        result = service.get_asset_hierarchy('NONEXISTENT')
        assert result == []

    def test_get_asset_hierarchy_all_roots(self, service, mock_session):
        """Test getting all root assets."""
        mock_assets = [Mock(is_deleted=False, child_assets=[], to_dict=Mock(return_value={'asset_id': 'AST-001'}))]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_assets
        mock_session.query.return_value = mock_query
        result = service.get_asset_hierarchy()
        assert len(result) == 1

    # Status Summary Tests
    def test_get_assets_by_status_summary(self, service, mock_session):
        """Test getting asset count by status."""
        mock_status = Mock(value='operational')
        mock_results = [Mock(status=mock_status, __getitem__=lambda s, i: 10 if i == 1 else None)]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = mock_results
        mock_session.query.return_value = mock_query
        result = service.get_assets_by_status_summary()
        assert isinstance(result, dict)

    # Factory Function Tests
    def test_get_asset_service_with_session(self):
        """Test getting service with provided session."""
        mock_session = Mock()
        service = get_asset_service(mock_session)
        assert isinstance(service, AssetService)
        assert service.session == mock_session

    def test_get_asset_service_without_session(self):
        """Test getting service without session uses context manager."""
        with patch('services.cmms.asset_service.get_db_session') as mock_get_db:
            mock_session = Mock()
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_session)
            mock_get_db.return_value.__exit__ = Mock(return_value=False)
            service = get_asset_service()
            assert isinstance(service, AssetService)
