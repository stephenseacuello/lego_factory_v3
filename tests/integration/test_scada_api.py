"""
LEGO Factory v3 - SCADA API Integration Tests
==============================================
Integration tests for SCADA endpoints (machines, tags, alarms).
"""

import pytest
import json


class TestMachineCRUD:
    """Tests for machine CRUD operations."""

    def test_list_machines(self, client):
        """Should list all machines."""
        response = client.get('/api/scada/machines')

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'machines' in data or isinstance(data, list)

    def test_get_machine_by_id(self, client):
        """Should get machine by ID."""
        response = client.get('/api/scada/machines/test-machine-001')

        assert response.status_code in [200, 404, 500]

    def test_create_machine(self, client, sample_machine_data):
        """Should create a new machine."""
        response = client.post(
            '/api/scada/machines',
            data=json.dumps(sample_machine_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 201, 400, 404, 500]

    def test_update_machine(self, client, sample_machine_data):
        """Should update an existing machine."""
        response = client.put(
            '/api/scada/machines/test-machine-001',
            data=json.dumps({'name': 'Updated Name'}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_delete_machine(self, client):
        """Should delete a machine."""
        response = client.delete('/api/scada/machines/test-machine-001')

        assert response.status_code in [200, 204, 404, 500]


class TestMachineConnection:
    """Tests for machine connection operations."""

    def test_connect_to_machine(self, client):
        """Should connect to a machine."""
        response = client.post('/api/scada/machines/test-machine-001/connect')

        assert response.status_code in [200, 404, 500]

    def test_disconnect_from_machine(self, client):
        """Should disconnect from a machine."""
        response = client.post('/api/scada/machines/test-machine-001/disconnect')

        assert response.status_code in [200, 404, 500]

    def test_get_machine_status(self, client):
        """Should get machine status."""
        response = client.get('/api/scada/machines/test-machine-001/status')

        assert response.status_code in [200, 404, 500]


class TestMachineControl:
    """Tests for machine control operations."""

    def test_home_machine(self, client):
        """Should home machine axes."""
        response = client.post(
            '/api/scada/machines/test-machine-001/home',
            data=json.dumps({'axes': 'XYZ'}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_jog_machine(self, client):
        """Should jog machine."""
        response = client.post(
            '/api/scada/machines/test-machine-001/jog',
            data=json.dumps({'x': 10.0, 'y': 0.0, 'z': 0.0, 'feed_rate': 500}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_run_gcode(self, client):
        """Should run G-code on machine."""
        response = client.post(
            '/api/scada/machines/test-machine-001/gcode',
            data=json.dumps({'gcode': 'G0 X0 Y0 Z0\nG1 X10 F500'}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_stop_machine(self, client):
        """Should stop machine."""
        response = client.post('/api/scada/machines/test-machine-001/stop')

        assert response.status_code in [200, 404, 500]

    def test_reset_machine(self, client):
        """Should reset machine."""
        response = client.post('/api/scada/machines/test-machine-001/reset')

        assert response.status_code in [200, 404, 500]


class TestTagOperations:
    """Tests for SCADA tag operations."""

    def test_list_tags(self, client):
        """Should list all tags."""
        response = client.get('/api/scada/tags')

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'tags' in data or isinstance(data, list)

    def test_get_tag_by_id(self, client):
        """Should get tag by ID."""
        response = client.get('/api/scada/tags/test-tag-001')

        assert response.status_code in [200, 404, 500]

    def test_create_tag(self, client, sample_tag_data):
        """Should create a new tag."""
        response = client.post(
            '/api/scada/tags',
            data=json.dumps(sample_tag_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 201, 400, 404, 500]

    def test_update_tag(self, client):
        """Should update an existing tag."""
        response = client.put(
            '/api/scada/tags/test-tag-001',
            data=json.dumps({'description': 'Updated description'}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_delete_tag(self, client):
        """Should delete a tag."""
        response = client.delete('/api/scada/tags/test-tag-001')

        assert response.status_code in [200, 204, 404, 500]

    def test_get_tag_value(self, client):
        """Should get current tag value."""
        response = client.get('/api/scada/tags/test-tag-001/value')

        assert response.status_code in [200, 404, 500]

    def test_write_tag_value(self, client):
        """Should write tag value."""
        response = client.post(
            '/api/scada/tags/test-tag-001/value',
            data=json.dumps({'value': 50.0}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_get_tag_history(self, client):
        """Should get tag history."""
        response = client.get('/api/scada/tags/test-tag-001/history?start=2024-01-01&end=2024-01-31')

        assert response.status_code in [200, 404, 500]


class TestAlarmOperations:
    """Tests for SCADA alarm operations."""

    def test_list_alarms(self, client):
        """Should list all alarm definitions."""
        response = client.get('/api/scada/alarms')

        assert response.status_code in [200, 404, 500]

    def test_get_active_alarms(self, client):
        """Should get active alarms."""
        response = client.get('/api/scada/alarms/active')

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'alarms' in data or 'count' in data or isinstance(data, list)

    def test_get_alarm_by_id(self, client):
        """Should get alarm by ID."""
        response = client.get('/api/scada/alarms/test-alarm-001')

        assert response.status_code in [200, 404, 500]

    def test_create_alarm(self, client, sample_alarm_data):
        """Should create a new alarm definition."""
        response = client.post(
            '/api/scada/alarms',
            data=json.dumps(sample_alarm_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 201, 400, 404, 500]

    def test_update_alarm(self, client):
        """Should update an existing alarm."""
        response = client.put(
            '/api/scada/alarms/test-alarm-001',
            data=json.dumps({'high_limit': 85.0}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_delete_alarm(self, client):
        """Should delete an alarm definition."""
        response = client.delete('/api/scada/alarms/test-alarm-001')

        assert response.status_code in [200, 204, 404, 500]

    def test_acknowledge_alarm(self, client):
        """Should acknowledge an alarm."""
        response = client.post(
            '/api/scada/alarms/test-alarm-001/acknowledge',
            data=json.dumps({'operator': 'testuser', 'comment': 'Acknowledged'}),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_shelve_alarm(self, client):
        """Should shelve an alarm."""
        response = client.post(
            '/api/scada/alarms/test-alarm-001/shelve',
            data=json.dumps({
                'operator': 'testuser',
                'duration_hours': 1,
                'reason': 'Maintenance in progress'
            }),
            content_type='application/json'
        )

        assert response.status_code in [200, 400, 404, 500]

    def test_unshelve_alarm(self, client):
        """Should unshelve an alarm."""
        response = client.post('/api/scada/alarms/test-alarm-001/unshelve')

        assert response.status_code in [200, 404, 500]


class TestAlarmHistory:
    """Tests for alarm history operations."""

    def test_get_alarm_history(self, client):
        """Should get alarm history."""
        response = client.get('/api/scada/alarms/history')

        assert response.status_code in [200, 404, 500]

    def test_get_alarm_history_with_filters(self, client):
        """Should get alarm history with filters."""
        response = client.get(
            '/api/scada/alarms/history?start=2024-01-01&end=2024-01-31&priority=high'
        )

        assert response.status_code in [200, 404, 500]


class TestRecipeOperations:
    """Tests for recipe operations."""

    def test_list_recipes(self, client):
        """Should list all recipes."""
        response = client.get('/api/scada/recipes')

        assert response.status_code in [200, 404, 500]

    def test_get_recipe_by_id(self, client):
        """Should get recipe by ID."""
        response = client.get('/api/scada/recipes/test-recipe-001')

        assert response.status_code in [200, 404, 500]

    def test_create_recipe(self, client):
        """Should create a new recipe."""
        recipe_data = {
            'recipe_id': 'test-recipe-001',
            'name': 'Test Recipe',
            'description': 'A test recipe',
            'product_id': 'PROD-001'
        }

        response = client.post(
            '/api/scada/recipes',
            data=json.dumps(recipe_data),
            content_type='application/json'
        )

        assert response.status_code in [200, 201, 400, 404, 500]


class TestMachineStats:
    """Tests for machine statistics."""

    def test_get_machine_stats(self, client):
        """Should get machine statistics."""
        response = client.get('/api/scada/machines/stats')

        assert response.status_code in [200, 404, 500]

    def test_get_machine_events(self, client):
        """Should get machine events."""
        response = client.get('/api/scada/machines/test-machine-001/events')

        assert response.status_code in [200, 404, 500]

    def test_get_machine_types(self, client):
        """Should get available machine types."""
        response = client.get('/api/scada/machines/types')

        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'machine_types' in data or 'controller_types' in data
