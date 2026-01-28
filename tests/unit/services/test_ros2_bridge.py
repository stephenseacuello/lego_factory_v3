"""
Unit tests for ROS2 Bridge Service.

Tests WebSocket communication with rosbridge for robot control.
"""

import pytest
import json
import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from services.robotics.ros2_bridge import (
    ConnectionState,
    ROS2Topic,
    ROS2Service,
    ROS2Bridge,
    get_ros2_bridge,
)


class TestConnectionState:
    """Tests for ConnectionState enum."""

    def test_connection_states(self):
        """Test that all connection states are defined."""
        assert ConnectionState.DISCONNECTED.value == 'disconnected'
        assert ConnectionState.CONNECTING.value == 'connecting'
        assert ConnectionState.CONNECTED.value == 'connected'
        assert ConnectionState.ERROR.value == 'error'


class TestROS2Topic:
    """Tests for ROS2Topic dataclass."""

    def test_create_topic(self):
        """Test creating a topic subscription."""
        callback = Mock()
        topic = ROS2Topic(
            name='/robot/joint_states',
            msg_type='sensor_msgs/JointState',
            callback=callback,
            queue_size=10
        )

        assert topic.name == '/robot/joint_states'
        assert topic.msg_type == 'sensor_msgs/JointState'
        assert topic.callback is callback
        assert topic.queue_size == 10

    def test_default_queue_size(self):
        """Test default queue size."""
        topic = ROS2Topic(
            name='/test',
            msg_type='std_msgs/String',
            callback=Mock()
        )

        assert topic.queue_size == 10


class TestROS2Service:
    """Tests for ROS2Service dataclass."""

    def test_create_service(self):
        """Test creating a service definition."""
        service = ROS2Service(
            name='/robot/move_to',
            srv_type='robot_interfaces/MoveTo'
        )

        assert service.name == '/robot/move_to'
        assert service.srv_type == 'robot_interfaces/MoveTo'


class TestROS2Bridge:
    """Tests for ROS2Bridge class."""

    @pytest.fixture
    def bridge(self):
        """Create a fresh bridge for testing."""
        ROS2Bridge._instance = None
        bridge = ROS2Bridge("localhost", 9090)
        bridge._simulation_mode = True  # Use simulation mode for tests
        return bridge

    def test_singleton_pattern(self):
        """Test that ROS2Bridge is a singleton."""
        ROS2Bridge._instance = None
        b1 = ROS2Bridge()
        b2 = ROS2Bridge()

        assert b1 is b2

    def test_initial_state(self, bridge):
        """Test initial connection state."""
        assert bridge.state == ConnectionState.DISCONNECTED

    def test_url_format(self, bridge):
        """Test WebSocket URL format."""
        assert bridge.url == "ws://localhost:9090"

    def test_connect_simulation_mode(self, bridge):
        """Test connecting in simulation mode."""
        bridge._simulation_mode = True
        result = bridge.connect()

        assert result is True
        assert bridge.state == ConnectionState.CONNECTED
        assert bridge.is_connected is True

    def test_disconnect(self, bridge):
        """Test disconnecting."""
        bridge._state = ConnectionState.CONNECTED
        bridge.disconnect()

        assert bridge.state == ConnectionState.DISCONNECTED

    def test_subscribe(self, bridge):
        """Test subscribing to a topic."""
        callback = Mock()
        bridge.subscribe('/robot/state', 'std_msgs/String', callback)

        assert '/robot/state' in bridge._subscriptions
        assert bridge._subscriptions['/robot/state'].callback is callback

    def test_unsubscribe(self, bridge):
        """Test unsubscribing from a topic."""
        callback = Mock()
        bridge.subscribe('/robot/state', 'std_msgs/String', callback)
        bridge.unsubscribe('/robot/state')

        assert '/robot/state' not in bridge._subscriptions

    def test_publish_simulation_mode(self, bridge):
        """Test publishing in simulation mode."""
        bridge._simulation_mode = True
        bridge._state = ConnectionState.CONNECTED

        # Should not raise
        bridge.publish('/cmd_vel', 'geometry_msgs/Twist', {'linear': {'x': 0.5}})

    def test_publish_not_connected(self, bridge):
        """Test publishing when not connected."""
        bridge._simulation_mode = False
        bridge._state = ConnectionState.DISCONNECTED

        # Should log warning but not raise
        bridge.publish('/cmd_vel', 'geometry_msgs/Twist', {})

    def test_call_service_simulation_mode(self, bridge):
        """Test calling a service in simulation mode."""
        bridge._simulation_mode = True
        bridge._state = ConnectionState.CONNECTED

        result = bridge.call_service(
            '/robot/home',
            'std_srvs/Trigger',
            {}
        )

        assert result is not None
        assert result.get('success') is True

    def test_call_service_not_connected(self, bridge):
        """Test calling service when not connected."""
        bridge._simulation_mode = False
        bridge._state = ConnectionState.DISCONNECTED

        result = bridge.call_service('/robot/home', 'std_srvs/Trigger', {})
        assert result is None

    def test_status_callback(self, bridge):
        """Test status change callbacks."""
        callback = Mock()
        bridge.on_status_change(callback)

        # Trigger status change
        bridge._state = ConnectionState.CONNECTED
        bridge._notify_status()

        callback.assert_called_once_with(ConnectionState.CONNECTED)

    def test_get_robot_state_simulation(self, bridge):
        """Test getting robot state in simulation mode."""
        bridge._simulation_mode = True
        bridge._state = ConnectionState.CONNECTED

        state = bridge.get_robot_state("xarm_001")

        assert state is not None
        assert state['robot_id'] == "xarm_001"
        assert state['connected'] is True
        assert 'position' in state
        assert 'joints' in state


class TestROS2BridgeMessageHandling:
    """Tests for ROS2Bridge message handling."""

    @pytest.fixture
    def bridge(self):
        ROS2Bridge._instance = None
        bridge = ROS2Bridge()
        bridge._simulation_mode = False
        return bridge

    def test_on_open(self, bridge):
        """Test WebSocket open handler."""
        bridge._state = ConnectionState.CONNECTING

        # Add a subscription to re-subscribe on connect
        bridge._subscriptions['/test'] = ROS2Topic(
            name='/test',
            msg_type='std_msgs/String',
            callback=Mock()
        )

        bridge._on_open(Mock())

        assert bridge.state == ConnectionState.CONNECTED

    def test_on_message_publish(self, bridge):
        """Test handling incoming publish message."""
        callback = Mock()
        bridge._subscriptions['/robot/state'] = ROS2Topic(
            name='/robot/state',
            msg_type='std_msgs/String',
            callback=callback
        )

        message = json.dumps({
            'op': 'publish',
            'topic': '/robot/state',
            'msg': {'data': 'test'}
        })

        bridge._on_message(Mock(), message)

        callback.assert_called_once_with({'data': 'test'})

    def test_on_message_service_response(self, bridge):
        """Test handling service response."""
        event = threading.Event()
        bridge._service_events['call_service:1'] = event
        bridge._service_results['call_service:1'] = None

        message = json.dumps({
            'op': 'service_response',
            'id': 'call_service:1',
            'values': {'success': True}
        })

        bridge._on_message(Mock(), message)

        assert bridge._service_results['call_service:1'] == {'success': True}
        assert event.is_set()

    def test_on_message_invalid_json(self, bridge):
        """Test handling invalid JSON message."""
        # Should not raise
        bridge._on_message(Mock(), "not valid json")

    def test_on_error(self, bridge):
        """Test WebSocket error handler."""
        bridge._on_error(Mock(), Exception("Test error"))

        assert bridge.state == ConnectionState.ERROR

    def test_on_close(self, bridge):
        """Test WebSocket close handler."""
        bridge._state = ConnectionState.CONNECTED
        bridge._on_close(Mock(), 1000, "Normal closure")

        assert bridge.state == ConnectionState.DISCONNECTED


class TestGetROS2Bridge:
    """Tests for get_ros2_bridge function."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton before each test."""
        import services.robotics.ros2_bridge as module
        # Reset both the module-level and class-level singletons
        module._ros2_bridge = None
        module.ROS2Bridge._instance = None
        yield
        module._ros2_bridge = None
        module.ROS2Bridge._instance = None

    def test_get_ros2_bridge_default(self):
        """Test getting bridge with default settings."""
        import services.robotics.ros2_bridge as module
        bridge = module.get_ros2_bridge()

        assert bridge is not None
        assert bridge.host == "localhost"
        assert bridge.port == 9090

    def test_get_ros2_bridge_custom(self):
        """Test getting bridge with custom settings."""
        import services.robotics.ros2_bridge as module
        bridge = module.get_ros2_bridge(host="192.168.1.100", port=9091)

        assert bridge.host == "192.168.1.100"
        assert bridge.port == 9091

    def test_get_ros2_bridge_singleton(self):
        """Test that get_ros2_bridge returns singleton."""
        import services.robotics.ros2_bridge as module
        b1 = module.get_ros2_bridge()
        b2 = module.get_ros2_bridge()

        assert b1 is b2


class TestROS2Integration:
    """Tests for ROS2 integration scenarios."""

    @pytest.fixture
    def bridge(self):
        ROS2Bridge._instance = None
        bridge = ROS2Bridge()
        bridge._simulation_mode = True
        bridge._state = ConnectionState.CONNECTED
        return bridge

    def test_robot_move_workflow(self, bridge):
        """Test complete robot move workflow."""
        # 1. Check robot state
        state = bridge.get_robot_state("xarm_001")
        assert state['connected'] is True

        # 2. Call move service
        result = bridge.call_service(
            '/xarm_001/move_to',
            'xarm_msgs/srv/MoveCartesian',
            {'x': 0.3, 'y': 0.0, 'z': 0.2}
        )
        assert result is not None
        assert result.get('success') is True

    def test_sensor_subscription(self, bridge):
        """Test subscribing to sensor data."""
        received_data = []

        def callback(msg):
            received_data.append(msg)

        bridge.subscribe('/robot/joint_states', 'sensor_msgs/JointState', callback)

        # Simulate receiving a message
        message = json.dumps({
            'op': 'publish',
            'topic': '/robot/joint_states',
            'msg': {'position': [0.0, 0.5, 1.0, 0.0, 0.0, 0.0]}
        })
        bridge._on_message(Mock(), message)

        assert len(received_data) == 1
        assert received_data[0]['position'] == [0.0, 0.5, 1.0, 0.0, 0.0, 0.0]
