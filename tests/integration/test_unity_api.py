"""
LEGO Factory v3 - Unity Digital Twin API Integration Tests
==========================================================
Tests for Unity digital twin API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestUnityMachineAPI:
    """Test Unity machine state endpoints."""

    def test_list_machines(self, client):
        """Test listing machines in digital twin."""
        response = client.get('/api/v1/unity/machines')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, (list, dict))

    def test_get_machine_state(self, client):
        """Test getting specific machine state."""
        response = client.get('/api/v1/unity/machines/cnc_mill_1')
        assert response.status_code in [200, 404]

    def test_update_machine_state(self, client):
        """Test updating machine state in digital twin."""
        data = {
            'machine_id': 'cnc_mill_1',
            'position': {'x': 100.0, 'y': 50.0, 'z': 25.0},
            'state': 'running',
            'spindle_speed': 10000,
        }
        response = client.post('/api/v1/unity/machines/update', json=data)
        assert response.status_code in [200, 202]


@pytest.mark.integration
class TestUnityToolpathAPI:
    """Test Unity toolpath visualization endpoints."""

    def test_upload_toolpath(self, client):
        """Test uploading toolpath for visualization."""
        data = {
            'machine_id': 'cnc_mill_1',
            'gcode': 'G0 X0 Y0 Z10\nG1 X100 Y100 Z-5 F1000\n',
            'job_id': 'JOB-001',
        }
        response = client.post('/api/v1/unity/toolpath', json=data)
        assert response.status_code in [200, 201, 202]

    def test_clear_toolpath(self, client):
        """Test clearing toolpath visualization."""
        response = client.delete('/api/v1/unity/machines/cnc_mill_1/toolpath')
        assert response.status_code in [200, 204]


@pytest.mark.integration
class TestUnityAnimationAPI:
    """Test Unity animation control endpoints."""

    def test_play_animation(self, client):
        """Test starting machine animation."""
        data = {
            'animation': 'cycle_start',
            'speed': 1.0,
        }
        response = client.post('/api/v1/unity/machines/cnc_mill_1/animation', json=data)
        assert response.status_code in [200, 202]

    def test_pause_animation(self, client):
        """Test pausing animation."""
        response = client.post('/api/v1/unity/machines/cnc_mill_1/animation/pause')
        assert response.status_code in [200, 202, 404]


@pytest.mark.integration
class TestUnitySensorAPI:
    """Test Unity sensor visualization endpoints."""

    def test_update_sensor_display(self, client):
        """Test updating sensor readings in digital twin."""
        data = {
            'machine_id': 'cnc_mill_1',
            'sensors': {
                'spindle_load': 45.2,
                'coolant_temp': 22.5,
                'axis_x_pos': 150.0,
            }
        }
        response = client.post('/api/v1/unity/sensors', json=data)
        assert response.status_code in [200, 202]


@pytest.mark.integration
class TestUnityAlarmAPI:
    """Test Unity alarm visualization endpoints."""

    def test_show_alarm(self, client):
        """Test showing alarm in digital twin."""
        data = {
            'machine_id': 'cnc_mill_1',
            'alarm_type': 'warning',
            'message': 'Spindle load high',
        }
        response = client.post('/api/v1/unity/alarms', json=data)
        assert response.status_code in [200, 202]

    def test_clear_alarm(self, client):
        """Test clearing alarm visualization."""
        response = client.delete('/api/v1/unity/machines/cnc_mill_1/alarms')
        assert response.status_code in [200, 204]


@pytest.mark.integration
class TestUnityConnectionAPI:
    """Test Unity connection management."""

    def test_connection_status(self, client):
        """Test Unity bridge connection status."""
        response = client.get('/api/v1/unity/status')
        assert response.status_code == 200

    def test_sync_state(self, client):
        """Test full state synchronization."""
        response = client.post('/api/v1/unity/sync')
        assert response.status_code in [200, 202]
