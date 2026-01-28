"""
LEGO Factory v3 - SCADA Models Unit Tests
=========================================
"""

import pytest
from datetime import datetime


class TestMachineModel:
    """Tests for Machine model."""

    def test_create_machine(self, db_session, sample_machine_data):
        """Test creating a new machine."""
        from models.scada.machines import Machine

        machine = Machine(**sample_machine_data)
        db_session.add(machine)
        db_session.flush()

        assert machine.id is not None
        assert machine.machine_id == 'test_machine_001'
        assert machine.name == 'Test Machine'
        assert machine.enabled is True

    def test_machine_to_dict(self, db_session, sample_machine_data):
        """Test machine serialization."""
        from models.scada.machines import Machine

        machine = Machine(**sample_machine_data)
        db_session.add(machine)
        db_session.flush()

        data = machine.to_dict()

        assert 'machine_id' in data
        assert 'current_state' in data
        assert data['machine_id'] == 'test_machine_001'

    def test_machine_default_values(self, db_session, sample_machine_data):
        """Test machine default values."""
        from models.scada.machines import Machine, MachineState

        machine = Machine(**sample_machine_data)
        db_session.add(machine)
        db_session.flush()

        assert machine.position_x == 0.0
        assert machine.position_y == 0.0
        assert machine.position_z == 0.0
        assert machine.spindle_rpm == 0.0
        assert machine.feed_override == 100.0


class TestTagModel:
    """Tests for Tag model."""

    def test_create_tag(self, db_session):
        """Test creating a tag."""
        from models.scada.tags import Tag, TagDataType, TagCategory

        tag = Tag(
            tag_id='test.temperature',
            name='Test Temperature',
            data_type=TagDataType.FLOAT,
            category=TagCategory.ANALOG,
            unit='°C',
        )
        db_session.add(tag)
        db_session.flush()

        assert tag.id is not None
        assert tag.tag_id == 'test.temperature'


class TestAlarmModel:
    """Tests for Alarm model."""

    def test_create_alarm(self, db_session):
        """Test creating an alarm definition."""
        from models.scada.alarms import AlarmDefinition, AlarmPriority, AlarmClass, AlarmType

        alarm = AlarmDefinition(
            alarm_id='ALM-TEST-001',
            name='Test Alarm',
            alarm_type=AlarmType.HIGH,
            priority=AlarmPriority.HIGH,
            alarm_class=AlarmClass.PROCESS,
            setpoint=100.0,
            message='Test alarm triggered',
        )
        db_session.add(alarm)
        db_session.flush()

        assert alarm.id is not None
        assert alarm.alarm_id == 'ALM-TEST-001'
        assert alarm.priority == AlarmPriority.HIGH


class TestRecipeModel:
    """Tests for Recipe model."""

    def test_create_recipe(self, db_session):
        """Test creating a master recipe."""
        from models.scada.recipes import MasterRecipe, RecipeStatus, RecipeType

        recipe = MasterRecipe(
            recipe_id='RCP-TEST-001',
            name='Test Recipe',
            product_id='test_product',
            recipe_type=RecipeType.PRODUCTION,
            version='1.0',
            status=RecipeStatus.DRAFT,
            operations=[
                {'sequence': 10, 'name': 'Step 1'},
                {'sequence': 20, 'name': 'Step 2'},
            ],
            parameters={'temp': 200, 'speed': 100},
        )
        db_session.add(recipe)
        db_session.flush()

        assert recipe.id is not None
        assert recipe.recipe_id == 'RCP-TEST-001'
        assert len(recipe.operations) == 2
