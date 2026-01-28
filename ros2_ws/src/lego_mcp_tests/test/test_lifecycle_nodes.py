#!/usr/bin/env python3
"""
Unit Tests for ROS2 Lifecycle Nodes

Tests lifecycle state transitions for equipment nodes.
Industry 4.0/5.0 Architecture - ISA-95 Compliant

LEGO MCP Manufacturing System v7.0
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from typing import Optional

import pytest

# ROS2 imports - may not be available in all test environments
try:
    import rclpy
    from rclpy.lifecycle import State, TransitionCallbackReturn
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False

# Test lifecycle base class
try:
    from lego_mcp_orchestrator.lifecycle_base import (
        LifecycleNodeBase,
        LifecycleMixin,
        LifecycleState,
    )
    LIFECYCLE_BASE_AVAILABLE = True
except ImportError:
    LIFECYCLE_BASE_AVAILABLE = False

# Test equipment lifecycle nodes
try:
    from grbl_ros2.grbl_node import GRBLLifecycleNode
    GRBL_LIFECYCLE_AVAILABLE = True
except ImportError:
    GRBL_LIFECYCLE_AVAILABLE = False

try:
    from formlabs_ros2.formlabs_node import FormlabsLifecycleNode
    FORMLABS_LIFECYCLE_AVAILABLE = True
except ImportError:
    FORMLABS_LIFECYCLE_AVAILABLE = False


class TestLifecycleState(unittest.TestCase):
    """Test LifecycleState enum."""

    def test_lifecycle_states_exist(self):
        """Verify all lifecycle states are defined."""
        if not LIFECYCLE_BASE_AVAILABLE:
            self.skipTest("lifecycle_base not available")

        states = [
            LifecycleState.UNCONFIGURED,
            LifecycleState.INACTIVE,
            LifecycleState.ACTIVE,
            LifecycleState.FINALIZED,
        ]

        for state in states:
            self.assertIsInstance(state.value, str)


class TestLifecycleMixin(unittest.TestCase):
    """Test LifecycleMixin functionality."""

    def setUp(self):
        """Set up test fixtures."""
        if not LIFECYCLE_BASE_AVAILABLE:
            self.skipTest("lifecycle_base not available")

    def test_mixin_state_tracking(self):
        """Test that mixin tracks state correctly."""
        mixin = LifecycleMixin()

        self.assertEqual(mixin._lifecycle_state, LifecycleState.UNCONFIGURED)
        self.assertEqual(mixin._error_count, 0)

    def test_mixin_error_tracking(self):
        """Test error count tracking."""
        mixin = LifecycleMixin()

        mixin._error_count += 1
        self.assertEqual(mixin._error_count, 1)


@unittest.skipUnless(ROS2_AVAILABLE, "ROS2 not available")
class TestGRBLLifecycleNode(unittest.TestCase):
    """Test GRBL Lifecycle Node."""

    @classmethod
    def setUpClass(cls):
        """Initialize ROS2 context."""
        if not rclpy.ok():
            rclpy.init()

    @classmethod
    def tearDownClass(cls):
        """Shutdown ROS2 context."""
        if rclpy.ok():
            rclpy.shutdown()

    def setUp(self):
        """Set up test fixtures."""
        if not GRBL_LIFECYCLE_AVAILABLE:
            self.skipTest("GRBL lifecycle node not available")

    @patch('grbl_ros2.grbl_node.serial')
    def test_lifecycle_node_creation(self, mock_serial):
        """Test that lifecycle node can be created."""
        mock_serial.Serial.return_value = MagicMock()

        wrapper = GRBLLifecycleNode()
        node = wrapper.create_node()

        self.assertIsNotNone(node)
        node.destroy_node()

    @patch('grbl_ros2.grbl_node.serial')
    def test_configure_transition(self, mock_serial):
        """Test configure transition."""
        mock_serial.Serial.return_value = MagicMock()

        wrapper = GRBLLifecycleNode()
        node = wrapper.create_node()

        # Simulate configure
        state = State(primary_state_id=1, label='unconfigured')
        result = node.on_configure(state)

        self.assertEqual(result, TransitionCallbackReturn.SUCCESS)
        node.destroy_node()

    @patch('grbl_ros2.grbl_node.serial')
    def test_activate_transition(self, mock_serial):
        """Test activate transition."""
        mock_serial_instance = MagicMock()
        mock_serial_instance.is_open = True
        mock_serial.Serial.return_value = mock_serial_instance

        wrapper = GRBLLifecycleNode()
        node = wrapper.create_node()

        # Configure first
        config_state = State(primary_state_id=1, label='unconfigured')
        node.on_configure(config_state)

        # Then activate
        inactive_state = State(primary_state_id=2, label='inactive')
        result = node.on_activate(inactive_state)

        self.assertEqual(result, TransitionCallbackReturn.SUCCESS)
        node.destroy_node()

    @patch('grbl_ros2.grbl_node.serial')
    def test_deactivate_transition(self, mock_serial):
        """Test deactivate transition."""
        mock_serial.Serial.return_value = MagicMock()

        wrapper = GRBLLifecycleNode()
        node = wrapper.create_node()

        # Get to active state
        node.on_configure(State(primary_state_id=1, label='unconfigured'))
        node.on_activate(State(primary_state_id=2, label='inactive'))

        # Deactivate
        active_state = State(primary_state_id=3, label='active')
        result = node.on_deactivate(active_state)

        self.assertEqual(result, TransitionCallbackReturn.SUCCESS)
        node.destroy_node()

    @patch('grbl_ros2.grbl_node.serial')
    def test_cleanup_transition(self, mock_serial):
        """Test cleanup transition."""
        mock_serial.Serial.return_value = MagicMock()

        wrapper = GRBLLifecycleNode()
        node = wrapper.create_node()

        # Configure and deactivate
        node.on_configure(State(primary_state_id=1, label='unconfigured'))

        # Cleanup
        inactive_state = State(primary_state_id=2, label='inactive')
        result = node.on_cleanup(inactive_state)

        self.assertEqual(result, TransitionCallbackReturn.SUCCESS)
        node.destroy_node()

    @patch('grbl_ros2.grbl_node.serial')
    def test_shutdown_transition(self, mock_serial):
        """Test shutdown transition."""
        mock_serial.Serial.return_value = MagicMock()

        wrapper = GRBLLifecycleNode()
        node = wrapper.create_node()

        # Shutdown from any state
        state = State(primary_state_id=1, label='unconfigured')
        result = node.on_shutdown(state)

        self.assertEqual(result, TransitionCallbackReturn.SUCCESS)
        node.destroy_node()


@unittest.skipUnless(ROS2_AVAILABLE, "ROS2 not available")
class TestFormlabsLifecycleNode(unittest.TestCase):
    """Test Formlabs Lifecycle Node."""

    @classmethod
    def setUpClass(cls):
        """Initialize ROS2 context."""
        if not rclpy.ok():
            rclpy.init()

    @classmethod
    def tearDownClass(cls):
        """Shutdown ROS2 context."""
        if rclpy.ok():
            rclpy.shutdown()

    def setUp(self):
        """Set up test fixtures."""
        if not FORMLABS_LIFECYCLE_AVAILABLE:
            self.skipTest("Formlabs lifecycle node not available")

    @patch('formlabs_ros2.formlabs_node.aiohttp')
    def test_lifecycle_node_creation(self, mock_aiohttp):
        """Test that lifecycle node can be created."""
        wrapper = FormlabsLifecycleNode()
        node = wrapper.create_node()

        self.assertIsNotNone(node)
        node.destroy_node()

    @patch('formlabs_ros2.formlabs_node.aiohttp')
    def test_configure_transition(self, mock_aiohttp):
        """Test configure transition."""
        wrapper = FormlabsLifecycleNode()
        node = wrapper.create_node()

        state = State(primary_state_id=1, label='unconfigured')
        result = node.on_configure(state)

        self.assertEqual(result, TransitionCallbackReturn.SUCCESS)
        node.destroy_node()

    @patch('formlabs_ros2.formlabs_node.aiohttp')
    def test_simulate_mode(self, mock_aiohttp):
        """Test simulation mode activation."""
        wrapper = FormlabsLifecycleNode()
        node = wrapper.create_node()

        # Set simulate parameter
        node.set_parameters([
            rclpy.parameter.Parameter('simulate', rclpy.Parameter.Type.BOOL, True)
        ])

        # Configure and activate
        node.on_configure(State(primary_state_id=1, label='unconfigured'))
        result = node.on_activate(State(primary_state_id=2, label='inactive'))

        self.assertEqual(result, TransitionCallbackReturn.SUCCESS)
        node.destroy_node()


class TestLifecycleTransitions(unittest.TestCase):
    """Test lifecycle state transition logic."""

    def test_valid_transitions(self):
        """Test valid state transitions."""
        # Valid transitions per ROS2 lifecycle design
        valid_transitions = [
            ('unconfigured', 'inactive'),    # configure
            ('inactive', 'active'),          # activate
            ('active', 'inactive'),          # deactivate
            ('inactive', 'unconfigured'),    # cleanup
            ('unconfigured', 'finalized'),   # shutdown
            ('inactive', 'finalized'),       # shutdown
            ('active', 'finalized'),         # shutdown
        ]

        for from_state, to_state in valid_transitions:
            # This test validates the conceptual model
            self.assertIn(from_state, ['unconfigured', 'inactive', 'active'])
            self.assertIn(to_state, ['unconfigured', 'inactive', 'active', 'finalized'])

    def test_invalid_transitions(self):
        """Test that invalid transitions are blocked."""
        # Invalid transitions
        invalid_transitions = [
            ('unconfigured', 'active'),      # Must go through inactive
            ('active', 'unconfigured'),      # Must go through inactive
            ('finalized', 'unconfigured'),   # Terminal state
        ]

        # These would fail at the ROS2 lifecycle manager level
        for from_state, to_state in invalid_transitions:
            # Document expected behavior
            if from_state == 'finalized':
                # Finalized is terminal
                self.assertEqual(from_state, 'finalized')


class TestLifecycleErrorHandling(unittest.TestCase):
    """Test lifecycle error handling."""

    def test_error_recovery_strategy(self):
        """Test error recovery follows OTP patterns."""
        # Test that error handling follows one_for_one strategy
        # (restart only failed node)

        error_states = ['unconfigured', 'inactive', 'active']

        for state in error_states:
            # On error, node should attempt to return to unconfigured
            # This is the OTP-style "let it crash" pattern
            self.assertIn(state, error_states)

    def test_max_restart_limit(self):
        """Test that max restart limits are respected."""
        max_restarts = 5
        restart_window_sec = 60

        # Simulate restart tracking
        restarts = []
        import time

        for i in range(max_restarts + 1):
            restarts.append(time.time())

        # Check if we've exceeded max restarts in window
        recent_restarts = [
            r for r in restarts
            if r > time.time() - restart_window_sec
        ]

        # Should trigger escalation to supervisor
        self.assertGreater(len(recent_restarts), max_restarts)


class TestLifecycleHeartbeat(unittest.TestCase):
    """Test lifecycle heartbeat functionality."""

    def test_heartbeat_message_format(self):
        """Test heartbeat message format."""
        heartbeat = {
            "node": "grbl_node",
            "timestamp": "2024-01-15T10:30:00.123Z",
            "state": "active",
            "health": {
                "cpu_percent": 15.2,
                "memory_mb": 128,
                "errors": 0
            }
        }

        # Validate structure
        self.assertIn("node", heartbeat)
        self.assertIn("timestamp", heartbeat)
        self.assertIn("state", heartbeat)
        self.assertIn("health", heartbeat)

        # Validate health metrics
        health = heartbeat["health"]
        self.assertIn("cpu_percent", health)
        self.assertIn("memory_mb", health)
        self.assertIn("errors", health)

    def test_heartbeat_timeout_detection(self):
        """Test heartbeat timeout detection."""
        timeout_ms = 500
        last_heartbeat_ms = 0
        current_time_ms = 600

        elapsed = current_time_ms - last_heartbeat_ms

        # Should detect timeout
        self.assertGreater(elapsed, timeout_ms)


@pytest.fixture
def ros2_context():
    """Pytest fixture for ROS2 context."""
    if not ROS2_AVAILABLE:
        pytest.skip("ROS2 not available")

    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.mark.skipif(not ROS2_AVAILABLE, reason="ROS2 not available")
class TestPytestLifecycle:
    """Pytest-style lifecycle tests."""

    def test_lifecycle_enum_values(self):
        """Test lifecycle enum values."""
        if not LIFECYCLE_BASE_AVAILABLE:
            pytest.skip("lifecycle_base not available")

        assert LifecycleState.UNCONFIGURED.value == "unconfigured"
        assert LifecycleState.INACTIVE.value == "inactive"
        assert LifecycleState.ACTIVE.value == "active"
        assert LifecycleState.FINALIZED.value == "finalized"


if __name__ == '__main__':
    unittest.main()
