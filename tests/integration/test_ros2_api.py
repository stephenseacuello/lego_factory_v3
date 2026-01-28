"""
LEGO Factory v3 - ROS2 API Integration Tests
=============================================
Tests for ROS2 robotics API endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.integration
class TestROS2RobotsAPI:
    """Test ROS2 robot management endpoints."""

    def test_list_robots(self, client):
        """Test listing available robots."""
        response = client.get('/api/v1/ros2/robots')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, (list, dict))

    def test_get_robot_state(self, client):
        """Test getting specific robot state."""
        response = client.get('/api/v1/ros2/robots/niryo_ned2_1/state')
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert 'status' in data or 'state' in data

    @patch('services.robotics.ros2_bridge.get_ros2_bridge')
    def test_robot_move(self, mock_bridge, client):
        """Test robot move command."""
        mock_instance = MagicMock()
        mock_instance.is_connected = True
        mock_instance.publish = MagicMock()
        mock_bridge.return_value = mock_instance

        move_data = {
            'pose': {'x': 0.3, 'y': 0.0, 'z': 0.2, 'roll': 0, 'pitch': 0, 'yaw': 0},
            'speed': 0.5,
            'motion_type': 'joint',
        }
        response = client.post('/api/v1/ros2/robots/niryo_ned2_1/move', json=move_data)
        assert response.status_code in [200, 503]

    @patch('services.robotics.ros2_bridge.get_ros2_bridge')
    def test_robot_joint_move(self, mock_bridge, client):
        """Test robot joint move command."""
        mock_instance = MagicMock()
        mock_instance.is_connected = True
        mock_instance.publish = MagicMock()
        mock_bridge.return_value = mock_instance

        joint_data = {
            'positions': [0.0, 0.3, -0.5, 0.0, 0.2, 0.0],
            'speed': 0.5,
        }
        response = client.post('/api/v1/ros2/robots/niryo_ned2_1/joints', json=joint_data)
        assert response.status_code in [200, 503]


@pytest.mark.integration
class TestROS2TasksAPI:
    """Test ROS2 task management endpoints."""

    def test_list_tasks(self, client):
        """Test listing robot tasks."""
        response = client.get('/api/v1/ros2/tasks')
        assert response.status_code == 200

    def test_create_task(self, client):
        """Test creating a robot task."""
        task_data = {
            'task_type': 'pick_place',
            'robot_id': 'niryo_ned2_1',
            'parameters': {
                'pick_pose': {'x': 0.3, 'y': 0.1, 'z': 0.05},
                'place_pose': {'x': 0.4, 'y': -0.1, 'z': 0.05},
            },
        }
        response = client.post('/api/v1/ros2/tasks', json=task_data)
        assert response.status_code in [200, 201, 202]

    def test_get_task_status(self, client):
        """Test getting task status."""
        response = client.get('/api/v1/ros2/tasks/task_123')
        assert response.status_code in [200, 404]

    def test_cancel_task(self, client):
        """Test canceling a task."""
        response = client.delete('/api/v1/ros2/tasks/task_123')
        assert response.status_code in [200, 204, 404]


@pytest.mark.integration
class TestROS2GripperAPI:
    """Test ROS2 gripper control endpoints."""

    def test_gripper_open(self, client):
        """Test opening gripper."""
        response = client.post('/api/v1/ros2/robots/niryo_ned2_1/gripper/open')
        assert response.status_code in [200, 202, 503]

    def test_gripper_close(self, client):
        """Test closing gripper."""
        response = client.post('/api/v1/ros2/robots/niryo_ned2_1/gripper/close')
        assert response.status_code in [200, 202, 503]


@pytest.mark.integration
class TestROS2ConnectionAPI:
    """Test ROS2 connection management."""

    def test_connection_status(self, client):
        """Test ROS2 bridge connection status."""
        response = client.get('/api/v1/ros2/status')
        assert response.status_code == 200
        data = response.get_json()
        assert 'connected' in data or 'status' in data

    def test_reconnect(self, client):
        """Test ROS2 bridge reconnection."""
        response = client.post('/api/v1/ros2/reconnect')
        assert response.status_code in [200, 202, 503]
