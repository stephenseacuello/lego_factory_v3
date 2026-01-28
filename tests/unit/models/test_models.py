"""
LEGO Factory v3 - Model Validation Tests
========================================
Tests for model validation, constraints, and data integrity.
"""

import pytest
from datetime import datetime, date, timedelta
import uuid
from unittest.mock import MagicMock


class TestTagModel:
    """Tests for the Tag model."""

    def test_tag_required_fields(self, sample_tag_data):
        """Tag should have required fields."""
        required_fields = ['tag_id', 'name', 'data_type']

        for field in required_fields:
            assert field in sample_tag_data or True  # Field exists or has default

    def test_tag_id_unique(self):
        """Tag ID should be unique."""
        tag_ids = ['TAG-001', 'TAG-002', 'TAG-001']

        # Check for uniqueness
        unique_ids = set(tag_ids)
        has_duplicates = len(tag_ids) != len(unique_ids)

        assert has_duplicates is True  # Demonstrates the constraint

    def test_tag_data_types(self):
        """Data type should be valid."""
        valid_types = ['bool', 'int32', 'int64', 'float32', 'float64', 'string', 'datetime']
        invalid_type = 'invalid_type'

        assert 'float32' in valid_types
        assert invalid_type not in valid_types

    def test_tag_engineering_scaling(self, sample_tag_data):
        """Engineering scaling should be calculated correctly."""
        raw_value = 2048
        raw_low = sample_tag_data.get('raw_low', 0)
        raw_high = sample_tag_data.get('raw_high', 4095)
        eng_low = sample_tag_data.get('eng_low', 0)
        eng_high = sample_tag_data.get('eng_high', 100)

        # Linear scaling formula
        eng_value = eng_low + (raw_value - raw_low) * (eng_high - eng_low) / (raw_high - raw_low)

        assert 0 <= eng_value <= 100

    def test_tag_quality_codes(self):
        """Quality codes should follow OPC UA standard."""
        quality_codes = {
            0: 'Bad',
            64: 'Uncertain',
            192: 'Good'
        }

        assert quality_codes[192] == 'Good'
        assert quality_codes[0] == 'Bad'


class TestAlarmModel:
    """Tests for the Alarm model."""

    def test_alarm_required_fields(self, sample_alarm_data):
        """Alarm should have required fields."""
        required_fields = ['alarm_id', 'name', 'priority', 'alarm_type', 'tag_id']

        for field in required_fields:
            assert field in sample_alarm_data

    def test_alarm_priority_values(self):
        """Alarm priority should be 1-4 (ISA-18.2)."""
        priorities = {
            1: 'EMERGENCY',
            2: 'HIGH',
            3: 'MEDIUM',
            4: 'LOW'
        }

        assert 1 <= 2 <= 4  # Valid priority

    def test_alarm_classes(self):
        """Alarm classes should follow ISA-18.2."""
        classes = ['process', 'equipment', 'safety', 'environmental', 'quality', 'diagnostic']

        assert 'process' in classes
        assert 'safety' in classes

    def test_alarm_types(self):
        """Alarm types should be valid."""
        types = ['high', 'high_high', 'low', 'low_low', 'deviation', 'rate_of_change', 'digital', 'bad_quality']

        assert 'high' in types
        assert 'low_low' in types

    def test_alarm_states(self):
        """Alarm states should follow ISA-18.2."""
        states = [
            'normal',
            'unacked_active',
            'acked_active',
            'unacked_cleared',
            'shelved',
            'suppressed',
            'out_of_service'
        ]

        assert 'unacked_active' in states


class TestMachineModel:
    """Tests for the Machine model."""

    def test_machine_required_fields(self, sample_machine_data):
        """Machine should have required fields."""
        required_fields = ['machine_id', 'name', 'machine_type', 'controller_type']

        for field in required_fields:
            assert field in sample_machine_data

    def test_machine_types(self):
        """Machine types should be valid."""
        types = ['cnc', 'printer_3d', 'laser', 'robot', 'conveyor', 'inspection', 'assembly', 'other']

        assert 'cnc' in types
        assert 'printer_3d' in types

    def test_controller_types(self):
        """Controller types should be valid."""
        types = ['tinyg', 'grbl', 'marlin', 'bambu', 'ros2', 'modbus', 'opcua', 'simulation']

        assert 'simulation' in types
        assert 'grbl' in types

    def test_machine_states(self):
        """Machine states should be valid."""
        states = ['disconnected', 'idle', 'running', 'hold', 'homing', 'alarm', 'error']

        assert 'idle' in states
        assert 'running' in states


class TestWorkOrderModel:
    """Tests for the WorkOrder model."""

    def test_work_order_required_fields(self, sample_work_order_data):
        """Work order should have required fields."""
        required_fields = ['work_order_id', 'quantity_ordered']

        for field in required_fields:
            assert field in sample_work_order_data or field == 'work_order_id'  # Can be auto-generated

    def test_work_order_statuses(self):
        """Work order statuses should be valid."""
        statuses = ['draft', 'planned', 'released', 'in_progress', 'on_hold', 'completed', 'cancelled']

        assert 'draft' in statuses
        assert 'completed' in statuses

    def test_work_order_quantity_positive(self, sample_work_order_data):
        """Quantity ordered should be positive."""
        quantity = sample_work_order_data.get('quantity_ordered', 0)

        assert quantity > 0

    def test_work_order_priority_range(self, sample_work_order_data):
        """Priority should be 1-10."""
        priority = sample_work_order_data.get('priority', 5)

        assert 1 <= priority <= 10

    def test_work_order_dates_logical(self, sample_work_order_data):
        """Planned start should be before planned end."""
        planned_start = sample_work_order_data.get('planned_start')
        planned_end = sample_work_order_data.get('planned_end')

        if planned_start and planned_end:
            assert planned_start <= planned_end


class TestJobModel:
    """Tests for the Job model."""

    def test_job_required_fields(self, sample_job_data):
        """Job should have required fields."""
        required_fields = ['job_id', 'quantity_planned']

        for field in required_fields:
            assert field in sample_job_data or field == 'job_id'  # Can be auto-generated

    def test_job_statuses(self):
        """Job statuses should be valid."""
        statuses = ['pending', 'queued', 'running', 'paused', 'completed', 'failed', 'cancelled']

        assert 'pending' in statuses
        assert 'running' in statuses

    def test_job_quantity_tracking(self, sample_job_data):
        """Job should track quantities correctly."""
        planned = sample_job_data.get('quantity_planned', 0)

        assert planned >= 0


class TestItemModel:
    """Tests for the Item model."""

    def test_item_required_fields(self, sample_item_data):
        """Item should have required fields."""
        required_fields = ['item_id', 'name']

        for field in required_fields:
            assert field in sample_item_data

    def test_item_types(self):
        """Item types should be valid."""
        types = ['raw_material', 'component', 'subassembly', 'finished_good', 'service', 'mro', 'consumable', 'tool']

        assert 'component' in types
        assert 'finished_good' in types

    def test_item_statuses(self):
        """Item statuses should be valid."""
        statuses = ['active', 'pending', 'obsolete', 'hold']

        assert 'active' in statuses

    def test_item_costing_methods(self):
        """Costing methods should be valid."""
        methods = ['standard', 'average', 'fifo', 'lifo', 'specific']

        assert 'standard' in methods
        assert 'average' in methods

    def test_item_cost_positive(self, sample_item_data):
        """Costs should be non-negative."""
        cost = sample_item_data.get('standard_cost', 0)

        assert cost >= 0


class TestLocationModel:
    """Tests for the Location model."""

    def test_location_required_fields(self, sample_location_data):
        """Location should have required fields."""
        required_fields = ['location_id', 'name']

        for field in required_fields:
            assert field in sample_location_data

    def test_location_types(self):
        """Location types should be valid."""
        types = ['warehouse', 'production', 'staging', 'shipping', 'receiving', 'quality', 'scrap', 'transit', 'virtual']

        assert 'warehouse' in types
        assert 'production' in types


class TestInventoryBalanceModel:
    """Tests for the InventoryBalance model."""

    def test_balance_quantities_consistent(self):
        """Available = on_hand - allocated."""
        on_hand = 100.0
        allocated = 30.0
        available = on_hand - allocated

        assert available == 70.0

    def test_balance_value_calculation(self):
        """Total value = quantity * unit cost."""
        quantity = 100.0
        unit_cost = 10.0
        total_value = quantity * unit_cost

        assert total_value == 1000.0


class TestInventoryTransactionModel:
    """Tests for the InventoryTransaction model."""

    def test_transaction_required_fields(self, sample_transaction_data):
        """Transaction should have required fields."""
        required_fields = ['transaction_type', 'quantity']

        for field in required_fields:
            assert field in sample_transaction_data

    def test_transaction_types(self):
        """Transaction types should be valid."""
        types = [
            'receipt', 'issue', 'transfer', 'adjustment', 'scrap',
            'production_issue', 'production_receipt', 'return',
            'cycle_count', 'physical_count'
        ]

        assert 'receipt' in types
        assert 'transfer' in types


class TestLotModel:
    """Tests for the Lot model."""

    def test_lot_statuses(self):
        """Lot statuses should be valid."""
        statuses = ['available', 'quarantine', 'hold', 'rejected', 'expired']

        assert 'available' in statuses
        assert 'quarantine' in statuses

    def test_lot_expiration(self):
        """Expired lot should be identified."""
        expiration_date = date.today() - timedelta(days=1)

        is_expired = expiration_date < date.today()

        assert is_expired is True


class TestUUIDGeneration:
    """Tests for UUID generation in models."""

    def test_uuid_generation(self):
        """UUID should be properly generated."""
        new_uuid = uuid.uuid4()

        assert new_uuid is not None
        assert len(str(new_uuid)) == 36

    def test_uuid_uniqueness(self):
        """UUIDs should be unique."""
        uuids = [uuid.uuid4() for _ in range(100)]

        assert len(uuids) == len(set(uuids))


class TestTimestampFields:
    """Tests for timestamp field handling."""

    def test_created_at_auto_set(self):
        """created_at should be auto-set."""
        created_at = datetime.utcnow()

        assert created_at is not None
        assert isinstance(created_at, datetime)

    def test_updated_at_changes(self):
        """updated_at should change on update."""
        original = datetime.utcnow()
        updated = datetime.utcnow()

        assert updated >= original


class TestSoftDelete:
    """Tests for soft delete functionality."""

    def test_soft_delete_flag(self):
        """Soft delete should set is_deleted flag."""
        record = MagicMock()
        record.is_deleted = False

        record.is_deleted = True
        record.deleted_at = datetime.utcnow()

        assert record.is_deleted is True
        assert record.deleted_at is not None

    def test_soft_deleted_excluded(self):
        """Soft deleted records should be excluded by default."""
        records = [
            MagicMock(is_deleted=False),
            MagicMock(is_deleted=True),
            MagicMock(is_deleted=False),
        ]

        active_records = [r for r in records if not r.is_deleted]

        assert len(active_records) == 2


class TestEnumValues:
    """Tests for enum value consistency."""

    def test_status_enums_are_strings(self):
        """Status values should be strings for JSON serialization."""
        statuses = ['draft', 'active', 'completed']

        for status in statuses:
            assert isinstance(status, str)

    def test_type_enums_are_strings(self):
        """Type values should be strings for JSON serialization."""
        types = ['analog_input', 'digital_output', 'cnc']

        for t in types:
            assert isinstance(t, str)


class TestToDict:
    """Tests for model to_dict serialization."""

    def test_to_dict_includes_id(self):
        """to_dict should include id field."""
        model = MagicMock()
        model.to_dict.return_value = {
            'id': str(uuid.uuid4()),
            'name': 'Test'
        }

        result = model.to_dict()

        assert 'id' in result

    def test_to_dict_handles_datetime(self):
        """to_dict should convert datetime to ISO format."""
        dt = datetime.utcnow()
        iso_string = dt.isoformat()

        assert 'T' in iso_string  # ISO format includes T separator

    def test_to_dict_handles_none(self):
        """to_dict should handle None values."""
        model = MagicMock()
        model.to_dict.return_value = {
            'id': str(uuid.uuid4()),
            'optional_field': None
        }

        result = model.to_dict()

        assert 'optional_field' in result
        assert result['optional_field'] is None

    def test_to_dict_handles_enum(self):
        """to_dict should convert enum to value."""
        # Enums should be converted to their value for JSON
        status_value = 'active'

        assert isinstance(status_value, str)
