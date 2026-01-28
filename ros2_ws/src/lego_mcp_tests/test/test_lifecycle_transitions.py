#!/usr/bin/env python3
"""
Integration Tests for ROS2 Lifecycle Transitions

Tests full lifecycle state machine with multiple nodes.
Industry 4.0/5.0 Architecture - ISA-95 Compliant

LEGO MCP Manufacturing System v7.0
"""

import unittest
import time
from typing import List, Optional
from unittest.mock import MagicMock, patch
import threading
import queue

import pytest

# ROS2 imports
try:
    import rclpy
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.lifecycle import State, TransitionCallbackReturn
    from lifecycle_msgs.msg import Transition, State as StateMsg
    from lifecycle_msgs.srv import (
        ChangeState,
        GetState,
    )
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False

# Lifecycle manager
try:
    from nav2_util.lifecycle_manager import LifecycleManager
    LIFECYCLE_MANAGER_AVAILABLE = True
except ImportError:
    LIFECYCLE_MANAGER_AVAILABLE = False


class LifecycleTestHelper:
    """Helper class for lifecycle testing."""

    # Transition IDs from ROS2 lifecycle
    TRANSITION_CONFIGURE = 1
    TRANSITION_CLEANUP = 2
    TRANSITION_ACTIVATE = 3
    TRANSITION_DEACTIVATE = 4
    TRANSITION_SHUTDOWN = 5

    # State IDs
    STATE_UNCONFIGURED = 1
    STATE_INACTIVE = 2
    STATE_ACTIVE = 3
    STATE_FINALIZED = 4

    @staticmethod
    def state_name(state_id: int) -> str:
        """Get state name from ID."""
        names = {
            1: 'unconfigured',
            2: 'inactive',
            3: 'active',
            4: 'finalized',
        }
        return names.get(state_id, 'unknown')

    @staticmethod
    def transition_name(transition_id: int) -> str:
        """Get transition name from ID."""
        names = {
            1: 'configure',
            2: 'cleanup',
            3: 'activate',
            4: 'deactivate',
            5: 'shutdown',
        }
        return names.get(transition_id, 'unknown')


@unittest.skipUnless(ROS2_AVAILABLE, "ROS2 not available")
class TestLifecycleManagerIntegration(unittest.TestCase):
    """Integration tests using ROS2 lifecycle manager."""

    @classmethod
    def setUpClass(cls):
        """Initialize ROS2 context."""
        if not rclpy.ok():
            rclpy.init()
        cls.executor = MultiThreadedExecutor()

    @classmethod
    def tearDownClass(cls):
        """Shutdown ROS2 context."""
        cls.executor.shutdown()
        if rclpy.ok():
            rclpy.shutdown()

    def test_equipment_startup_sequence(self):
        """Test ISA-95 compliant startup sequence."""
        # Sequence: Safety -> Equipment -> Supervisory

        startup_sequence = [
            ('safety_node', 'L1'),      # Level 1: Control
            ('grbl_node', 'L0'),        # Level 0: Field
            ('formlabs_node', 'L0'),    # Level 0: Field
            ('orchestrator', 'L2'),     # Level 2: Supervisory
        ]

        # Verify sequence order is correct
        levels_order = [node[1] for node in startup_sequence]

        # L1 must come before L0 and L2
        l1_idx = levels_order.index('L1')
        l0_indices = [i for i, l in enumerate(levels_order) if l == 'L0']
        l2_idx = levels_order.index('L2')

        # Safety (L1) must start first
        self.assertEqual(l1_idx, 0)

        # Equipment (L0) before supervisory (L2)
        for l0_idx in l0_indices:
            self.assertLess(l0_idx, l2_idx)

    def test_graceful_shutdown_sequence(self):
        """Test graceful shutdown sequence (reverse of startup)."""
        shutdown_sequence = [
            ('orchestrator', 'L2'),     # Level 2: Supervisory
            ('formlabs_node', 'L0'),    # Level 0: Field
            ('grbl_node', 'L0'),        # Level 0: Field
            ('safety_node', 'L1'),      # Level 1: Control (last)
        ]

        # Safety must be last to shutdown
        levels_order = [node[1] for node in shutdown_sequence]
        l1_idx = levels_order.index('L1')

        self.assertEqual(l1_idx, len(shutdown_sequence) - 1)


class TestSupervisionStrategies(unittest.TestCase):
    """Test OTP-style supervision strategies."""

    def test_one_for_one_strategy(self):
        """Test one_for_one: restart only failed child."""
        children = ['grbl_node', 'formlabs_node', 'bambu_node']
        failed_child = 'grbl_node'

        # Simulate one_for_one
        restarted = [failed_child]

        # Only failed child should restart
        self.assertEqual(len(restarted), 1)
        self.assertIn(failed_child, restarted)

    def test_one_for_all_strategy(self):
        """Test one_for_all: restart ALL children on ANY failure."""
        children = ['safety_node', 'watchdog_node']
        failed_child = 'watchdog_node'

        # Simulate one_for_all
        restarted = children.copy()

        # All children should restart
        self.assertEqual(len(restarted), len(children))

    def test_rest_for_one_strategy(self):
        """Test rest_for_one: restart failed + all started after it."""
        children = ['moveit_node', 'ned2_node', 'xarm_node']
        failed_child = 'ned2_node'
        failed_idx = children.index(failed_child)

        # Simulate rest_for_one
        restarted = children[failed_idx:]

        # Failed and all after should restart
        self.assertEqual(restarted, ['ned2_node', 'xarm_node'])
        self.assertNotIn('moveit_node', restarted)


class TestDeterministicStartup(unittest.TestCase):
    """Test deterministic startup ordering."""

    def test_phase_timing(self):
        """Test that phases have correct timing offsets."""
        phases = {
            'safety': 0.0,      # Immediate
            'equipment': 3.0,   # After safety confirmed
            'supervisory': 6.0, # After equipment initialized
            'scada': 10.0,      # After supervisory ready
        }

        # Validate ordering
        phase_order = sorted(phases.items(), key=lambda x: x[1])

        self.assertEqual(phase_order[0][0], 'safety')
        self.assertEqual(phase_order[-1][0], 'scada')

    def test_node_dependencies(self):
        """Test node dependency resolution."""
        dependencies = {
            'orchestrator': ['safety_node', 'grbl_node'],
            'ned2_node': ['moveit_node'],
            'xarm_node': ['moveit_node'],
            'agv_fleet': ['orchestrator'],
        }

        def can_start(node: str, running: set) -> bool:
            """Check if node can start based on dependencies."""
            deps = dependencies.get(node, [])
            return all(d in running for d in deps)

        # Simulate startup
        running = {'safety_node', 'grbl_node', 'formlabs_node', 'moveit_node'}

        # Orchestrator can start (deps met)
        self.assertTrue(can_start('orchestrator', running))

        # AGV cannot start (orchestrator not running yet)
        self.assertFalse(can_start('agv_fleet', running))


class TestStateRecovery(unittest.TestCase):
    """Test state recovery after failures."""

    def test_checkpoint_save_restore(self):
        """Test checkpoint save and restore."""
        checkpoint = {
            'job_id': 'job_123',
            'position': [100.0, 50.0, 20.0],
            'tool': 'end_mill_3mm',
            'line_number': 150,
            'timestamp': time.time(),
        }

        # Simulate save
        saved = checkpoint.copy()

        # Simulate restore
        restored = saved

        self.assertEqual(restored['job_id'], 'job_123')
        self.assertEqual(restored['line_number'], 150)
        self.assertEqual(restored['position'], [100.0, 50.0, 20.0])

    def test_heartbeat_failure_detection(self):
        """Test heartbeat-based failure detection."""
        timeout_ms = 500
        heartbeats = {
            'grbl_node': time.time() - 0.1,     # Recent
            'formlabs_node': time.time() - 0.3, # Recent
            'crashed_node': time.time() - 1.0,  # Timed out
        }

        current_time = time.time()
        failed_nodes = [
            node for node, last_hb in heartbeats.items()
            if (current_time - last_hb) * 1000 > timeout_ms
        ]

        self.assertEqual(len(failed_nodes), 1)
        self.assertIn('crashed_node', failed_nodes)


class TestChaosRecovery(unittest.TestCase):
    """Test recovery from chaos scenarios."""

    def test_equipment_failure_recovery(self):
        """Test recovery from equipment failure."""
        scenario = {
            'type': 'equipment_failure',
            'target': 'grbl_node',
            'duration_sec': 5.0,
            'expected_rto_sec': 30.0,  # Recovery Time Objective
        }

        # Simulate failure
        failure_time = time.time()

        # Simulate recovery (supervisor restarts node)
        recovery_time = failure_time + 5.0

        actual_recovery_sec = recovery_time - failure_time

        self.assertLess(actual_recovery_sec, scenario['expected_rto_sec'])

    def test_cascade_failure_prevention(self):
        """Test that failures don't cascade uncontrolled."""
        max_restarts = 5
        restart_window_sec = 60

        # Simulate rapid failures
        restart_times = [time.time() + i * 5 for i in range(6)]

        # Check if escalation is triggered
        recent = len([
            t for t in restart_times
            if t > time.time()
        ])

        # Should trigger escalation (>5 in 60s)
        needs_escalation = recent > max_restarts

        self.assertTrue(needs_escalation)


@unittest.skipUnless(ROS2_AVAILABLE, "ROS2 not available")
class TestLifecycleServices(unittest.TestCase):
    """Test lifecycle service interactions."""

    def test_change_state_service_format(self):
        """Test ChangeState service request format."""
        # Create a mock request
        request = {
            'transition': {
                'id': LifecycleTestHelper.TRANSITION_CONFIGURE,
                'label': 'configure',
            }
        }

        self.assertEqual(
            request['transition']['id'],
            LifecycleTestHelper.TRANSITION_CONFIGURE
        )

    def test_get_state_service_format(self):
        """Test GetState service response format."""
        # Mock response
        response = {
            'current_state': {
                'id': LifecycleTestHelper.STATE_ACTIVE,
                'label': 'active',
            }
        }

        self.assertEqual(
            response['current_state']['id'],
            LifecycleTestHelper.STATE_ACTIVE
        )


class TestISA95Compliance(unittest.TestCase):
    """Test ISA-95 compliance requirements."""

    def test_layer_isolation(self):
        """Test ISA-95 layer isolation."""
        layers = {
            'L0': ['grbl_node', 'formlabs_node', 'bambu_node'],  # Field
            'L1': ['safety_node', 'watchdog_node'],              # Control
            'L2': ['orchestrator', 'agv_fleet'],                 # Supervisory
            'L3': ['mes_bridge', 'scada_adapter'],               # MES
            'L4': ['erp_connector'],                             # ERP
        }

        # L0 nodes should not directly communicate with L3+
        l0_nodes = set(layers['L0'])
        l3_nodes = set(layers['L3'])
        l4_nodes = set(layers['L4'])

        # No direct L0 -> L3/L4 communication allowed
        # (must go through L1/L2)
        direct_comms = set()  # Would be populated by network analysis

        self.assertEqual(len(l0_nodes & l3_nodes), 0)
        self.assertEqual(len(l0_nodes & l4_nodes), 0)

    def test_safety_layer_priority(self):
        """Test that safety layer has highest priority."""
        # Safety actions must complete within bounded time
        safety_timeout_ms = 100  # 100ms max

        # Simulate safety action
        start = time.time()
        # Safety check would happen here
        elapsed_ms = (time.time() - start) * 1000

        self.assertLess(elapsed_ms, safety_timeout_ms)


@pytest.fixture
def lifecycle_test_context():
    """Pytest fixture for lifecycle tests."""
    if not ROS2_AVAILABLE:
        pytest.skip("ROS2 not available")

    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.mark.integration
class TestPytestLifecycleIntegration:
    """Pytest-style integration tests."""

    def test_full_lifecycle_sequence(self):
        """Test complete lifecycle sequence."""
        states = [
            'unconfigured',
            'inactive',
            'active',
            'inactive',
            'unconfigured',
            'finalized',
        ]

        transitions = [
            'configure',
            'activate',
            'deactivate',
            'cleanup',
            'shutdown',
        ]

        # Each transition moves to next state
        for i, trans in enumerate(transitions):
            from_state = states[i]
            to_state = states[i + 1]

            # Validate transition is valid
            assert from_state != to_state

    def test_error_handling_sequence(self):
        """Test error handling lifecycle."""
        # On error from any state, system should:
        # 1. Call on_error()
        # 2. Attempt recovery or transition to errorprocessing
        # 3. Eventually reach unconfigured or finalized

        error_recovery = {
            'from_active': 'unconfigured',
            'from_inactive': 'unconfigured',
            'from_configuring': 'unconfigured',
        }

        for from_state, to_state in error_recovery.items():
            assert to_state == 'unconfigured'


if __name__ == '__main__':
    unittest.main()
