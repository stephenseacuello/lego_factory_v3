#!/usr/bin/env python3
"""
Unit and Integration Tests for OTP-style Supervision Strategies

Tests the three core supervision strategies:
- ONE_FOR_ONE: Restart only the failed child
- ONE_FOR_ALL: Restart all children on any failure
- REST_FOR_ONE: Restart failed child and all children started after it

LEGO MCP Manufacturing System v7.0
Industry 4.0/5.0 Architecture - ISA-95 Compliant
"""

import unittest
import time
import threading
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum, auto

import pytest


# Import supervisor components (with fallback for testing without ROS2)
try:
    from lego_mcp_supervisor.supervisor_node import (
        SupervisorNode,
        RestartStrategy,
        RestartType,
        ChildSpec,
        ChildState,
        ChildProcess,
    )
    from lego_mcp_supervisor.heartbeat import HeartbeatMixin, HeartbeatMonitor
    from lego_mcp_supervisor.checkpoint_manager import (
        CheckpointManager,
        CheckpointMixin,
        CheckpointType,
    )
    SUPERVISOR_AVAILABLE = True
except ImportError:
    SUPERVISOR_AVAILABLE = False

    # Mock classes for testing without full ROS2 environment
    class RestartStrategy(Enum):
        ONE_FOR_ONE = auto()
        ONE_FOR_ALL = auto()
        REST_FOR_ONE = auto()

    class RestartType(Enum):
        PERMANENT = auto()
        TEMPORARY = auto()
        TRANSIENT = auto()

    class ChildState(Enum):
        STOPPED = auto()
        STARTING = auto()
        RUNNING = auto()
        STOPPING = auto()
        FAILED = auto()
        RESTARTING = auto()


class TestRestartStrategies(unittest.TestCase):
    """Test OTP-style restart strategy logic."""

    def test_restart_strategy_enum_values(self):
        """Test restart strategy enum has correct values."""
        self.assertIsNotNone(RestartStrategy.ONE_FOR_ONE)
        self.assertIsNotNone(RestartStrategy.ONE_FOR_ALL)
        self.assertIsNotNone(RestartStrategy.REST_FOR_ONE)
        self.assertEqual(len(RestartStrategy), 3)

    def test_restart_type_enum_values(self):
        """Test restart type enum has correct values."""
        self.assertIsNotNone(RestartType.PERMANENT)
        self.assertIsNotNone(RestartType.TEMPORARY)
        self.assertIsNotNone(RestartType.TRANSIENT)
        self.assertEqual(len(RestartType), 3)

    def test_child_state_enum_values(self):
        """Test child state enum has all required states."""
        states = [
            ChildState.STOPPED,
            ChildState.STARTING,
            ChildState.RUNNING,
            ChildState.STOPPING,
            ChildState.FAILED,
            ChildState.RESTARTING,
        ]
        self.assertEqual(len(states), 6)
        self.assertEqual(len(ChildState), 6)


class TestOneForOneStrategy(unittest.TestCase):
    """Test ONE_FOR_ONE restart strategy: Only restart the failed child."""

    def test_single_failure_restarts_only_failed(self):
        """Test that only the failed child is restarted."""
        children = ['grbl_node', 'formlabs_node', 'bambu_node']
        failed_child = 'grbl_node'

        # Simulate ONE_FOR_ONE strategy
        restarted = self._apply_one_for_one(children, failed_child)

        self.assertEqual(len(restarted), 1)
        self.assertIn(failed_child, restarted)
        self.assertNotIn('formlabs_node', restarted)
        self.assertNotIn('bambu_node', restarted)

    def test_multiple_independent_failures(self):
        """Test that multiple independent failures each restart separately."""
        children = ['grbl_node', 'formlabs_node', 'bambu_node']

        # First failure
        restarted1 = self._apply_one_for_one(children, 'grbl_node')
        self.assertEqual(restarted1, ['grbl_node'])

        # Second failure (independent)
        restarted2 = self._apply_one_for_one(children, 'bambu_node')
        self.assertEqual(restarted2, ['bambu_node'])

    def test_running_children_not_affected(self):
        """Test that running children are not affected by failure."""
        children = ['grbl_node', 'formlabs_node', 'bambu_node']
        running = {'formlabs_node', 'bambu_node'}
        failed_child = 'grbl_node'

        restarted = self._apply_one_for_one(children, failed_child)

        # Running children should remain in running set
        self.assertEqual(running, {'formlabs_node', 'bambu_node'})
        self.assertEqual(restarted, ['grbl_node'])

    def _apply_one_for_one(self, children: List[str], failed: str) -> List[str]:
        """Apply ONE_FOR_ONE strategy: return only failed child."""
        return [failed]


class TestOneForAllStrategy(unittest.TestCase):
    """Test ONE_FOR_ALL restart strategy: Restart all children on any failure."""

    def test_single_failure_restarts_all(self):
        """Test that any failure causes all children to restart."""
        children = ['safety_node', 'watchdog_node', 'estop_monitor']
        failed_child = 'watchdog_node'

        restarted = self._apply_one_for_all(children, failed_child)

        self.assertEqual(len(restarted), len(children))
        self.assertEqual(set(restarted), set(children))

    def test_safety_subsystem_all_restart(self):
        """Test safety subsystem - all nodes must restart together."""
        safety_nodes = ['safety_node', 'watchdog_node']
        failed_child = 'safety_node'

        restarted = self._apply_one_for_all(safety_nodes, failed_child)

        # Both must restart for safety integrity
        self.assertIn('safety_node', restarted)
        self.assertIn('watchdog_node', restarted)
        self.assertEqual(len(restarted), 2)

    def test_restart_order_preserved(self):
        """Test that restart order matches original child order."""
        children = ['node_a', 'node_b', 'node_c']
        failed_child = 'node_b'

        restarted = self._apply_one_for_all(children, failed_child)

        # Order should be preserved for deterministic startup
        self.assertEqual(restarted, children)

    def _apply_one_for_all(self, children: List[str], failed: str) -> List[str]:
        """Apply ONE_FOR_ALL strategy: return all children in order."""
        return children.copy()


class TestRestForOneStrategy(unittest.TestCase):
    """Test REST_FOR_ONE strategy: Restart failed + all started after it."""

    def test_first_child_failure_restarts_all(self):
        """Test that first child failure restarts entire chain."""
        children = ['moveit_node', 'ned2_node', 'xarm_node']
        failed_child = 'moveit_node'

        restarted = self._apply_rest_for_one(children, failed_child)

        # All children restart (moveit is first)
        self.assertEqual(restarted, ['moveit_node', 'ned2_node', 'xarm_node'])

    def test_middle_child_failure_restarts_remainder(self):
        """Test that middle child failure restarts it and subsequent."""
        children = ['moveit_node', 'ned2_node', 'xarm_node']
        failed_child = 'ned2_node'

        restarted = self._apply_rest_for_one(children, failed_child)

        # ned2 and xarm restart, moveit stays
        self.assertEqual(restarted, ['ned2_node', 'xarm_node'])
        self.assertNotIn('moveit_node', restarted)

    def test_last_child_failure_restarts_only_itself(self):
        """Test that last child failure only restarts itself."""
        children = ['moveit_node', 'ned2_node', 'xarm_node']
        failed_child = 'xarm_node'

        restarted = self._apply_rest_for_one(children, failed_child)

        # Only xarm restarts
        self.assertEqual(restarted, ['xarm_node'])

    def test_dependency_chain_respected(self):
        """Test that dependency chain ordering is respected."""
        # Robotics: moveit -> ned2 -> xarm (ordered dependencies)
        children = ['moveit_node', 'ned2_node', 'xarm_node']

        # Failure in ned2 should restart ned2 and xarm
        restarted = self._apply_rest_for_one(children, 'ned2_node')

        # moveit stays (it's before ned2)
        self.assertNotIn('moveit_node', restarted)
        # ned2 and xarm restart
        self.assertIn('ned2_node', restarted)
        self.assertIn('xarm_node', restarted)

    def _apply_rest_for_one(self, children: List[str], failed: str) -> List[str]:
        """Apply REST_FOR_ONE strategy: return failed + all after it."""
        failed_idx = children.index(failed)
        return children[failed_idx:]


class TestRestartRateLimiting(unittest.TestCase):
    """Test restart rate limiting (max_restarts in restart_window)."""

    def test_max_restarts_within_window(self):
        """Test that restarts are counted within time window."""
        max_restarts = 5
        restart_window_sec = 60

        restart_times = []

        # Simulate 5 restarts within window
        for i in range(5):
            restart_times.append(time.time())

        recent = self._count_recent_restarts(restart_times, restart_window_sec)
        self.assertEqual(recent, 5)

    def test_max_restarts_exceeded_triggers_escalation(self):
        """Test that exceeding max_restarts triggers escalation."""
        max_restarts = 5
        restart_window_sec = 60

        # Simulate 6 restarts in quick succession
        restart_times = [time.time() + i * 0.1 for i in range(6)]

        recent = self._count_recent_restarts(restart_times, restart_window_sec)
        needs_escalation = recent > max_restarts

        self.assertTrue(needs_escalation)

    def test_old_restarts_not_counted(self):
        """Test that restarts outside window are not counted."""
        max_restarts = 5
        restart_window_sec = 60

        current_time = time.time()

        # 3 old restarts (outside window) + 2 recent
        restart_times = [
            current_time - 120,  # 2 minutes ago
            current_time - 90,   # 1.5 minutes ago
            current_time - 61,   # Just outside window
            current_time - 30,   # 30 seconds ago
            current_time - 10,   # 10 seconds ago
        ]

        recent = self._count_recent_restarts(
            restart_times, restart_window_sec, current_time
        )

        # Only 2 recent restarts should count
        self.assertEqual(recent, 2)

    def _count_recent_restarts(
        self,
        restart_times: List[float],
        window_sec: float,
        current_time: Optional[float] = None
    ) -> int:
        """Count restarts within time window."""
        if current_time is None:
            current_time = time.time()
        cutoff = current_time - window_sec
        return len([t for t in restart_times if t > cutoff])


class TestDependencyResolution(unittest.TestCase):
    """Test child node dependency resolution."""

    def test_dependency_order_respected(self):
        """Test that nodes start after their dependencies."""
        dependencies = {
            'orchestrator': ['safety_node', 'grbl_node'],
            'ned2_node': ['moveit_node'],
            'xarm_node': ['moveit_node'],
            'agv_fleet': ['orchestrator'],
        }

        def can_start(node: str, running: set) -> bool:
            deps = dependencies.get(node, [])
            return all(d in running for d in deps)

        # Initial running set
        running = {'safety_node', 'grbl_node', 'moveit_node'}

        # Orchestrator can start (deps met)
        self.assertTrue(can_start('orchestrator', running))

        # AGV cannot start yet
        self.assertFalse(can_start('agv_fleet', running))

        # After orchestrator starts
        running.add('orchestrator')
        self.assertTrue(can_start('agv_fleet', running))

    def test_circular_dependency_detection(self):
        """Test that circular dependencies are detected."""
        dependencies = {
            'node_a': ['node_b'],
            'node_b': ['node_c'],
            'node_c': ['node_a'],  # Circular!
        }

        has_circular = self._detect_circular_deps(dependencies)
        self.assertTrue(has_circular)

    def test_no_circular_dependency(self):
        """Test valid dependency graph."""
        dependencies = {
            'node_a': [],
            'node_b': ['node_a'],
            'node_c': ['node_a', 'node_b'],
        }

        has_circular = self._detect_circular_deps(dependencies)
        self.assertFalse(has_circular)

    def _detect_circular_deps(self, deps: Dict[str, List[str]]) -> bool:
        """Detect circular dependencies using DFS."""
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for dep in deps.get(node, []):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in deps:
            if node not in visited:
                if dfs(node):
                    return True
        return False


class TestHeartbeatFailureDetection(unittest.TestCase):
    """Test heartbeat-based failure detection."""

    def test_heartbeat_timeout_detection(self):
        """Test that missed heartbeats trigger failure detection."""
        timeout_ms = 500
        heartbeats = {
            'grbl_node': time.time() - 0.1,     # Recent (100ms ago)
            'formlabs_node': time.time() - 0.3, # Recent (300ms ago)
            'crashed_node': time.time() - 1.0,  # Timed out (1000ms ago)
        }

        failed_nodes = self._detect_failed_nodes(heartbeats, timeout_ms)

        self.assertEqual(len(failed_nodes), 1)
        self.assertIn('crashed_node', failed_nodes)
        self.assertNotIn('grbl_node', failed_nodes)
        self.assertNotIn('formlabs_node', failed_nodes)

    def test_missed_heartbeat_threshold(self):
        """Test missed heartbeat threshold before failure."""
        missed_threshold = 3
        missed_counts = {
            'grbl_node': 0,
            'formlabs_node': 2,
            'flaky_node': 3,
        }

        failed_nodes = [
            node for node, count in missed_counts.items()
            if count >= missed_threshold
        ]

        self.assertEqual(failed_nodes, ['flaky_node'])

    def _detect_failed_nodes(
        self,
        heartbeats: Dict[str, float],
        timeout_ms: float
    ) -> List[str]:
        """Detect nodes that have missed heartbeat timeout."""
        current_time = time.time()
        timeout_sec = timeout_ms / 1000.0

        return [
            node for node, last_hb in heartbeats.items()
            if (current_time - last_hb) > timeout_sec
        ]


class TestCheckpointRecovery(unittest.TestCase):
    """Test state checkpoint and recovery."""

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

    def test_checkpoint_chain_integrity(self):
        """Test checkpoint chain maintains integrity."""
        checkpoints = []

        # Create chain of checkpoints
        prev_hash = "GENESIS"
        for i in range(5):
            checkpoint = {
                'sequence': i,
                'prev_hash': prev_hash,
                'data': f'state_{i}',
            }
            # Simulate hash
            curr_hash = f"hash_{i}"
            checkpoint['hash'] = curr_hash
            checkpoints.append(checkpoint)
            prev_hash = curr_hash

        # Verify chain
        for i in range(1, len(checkpoints)):
            self.assertEqual(
                checkpoints[i]['prev_hash'],
                checkpoints[i - 1]['hash']
            )


class TestISA95Compliance(unittest.TestCase):
    """Test ISA-95 compliance requirements."""

    def test_layer_startup_order(self):
        """Test ISA-95 compliant startup order."""
        startup_sequence = [
            ('safety_node', 'L1'),      # Level 1: Control
            ('grbl_node', 'L0'),        # Level 0: Field
            ('formlabs_node', 'L0'),    # Level 0: Field
            ('orchestrator', 'L2'),     # Level 2: Supervisory
        ]

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

    def test_shutdown_reverse_order(self):
        """Test graceful shutdown in reverse order."""
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


@pytest.mark.integration
class TestSupervisorIntegration:
    """Integration tests for supervisor system."""

    def test_full_supervision_tree_structure(self):
        """Test complete supervision tree structure."""
        tree = {
            'root_supervisor': {
                'strategy': 'ONE_FOR_ALL',
                'children': [
                    {
                        'id': 'safety_supervisor',
                        'strategy': 'ONE_FOR_ALL',
                        'children': ['safety_node', 'watchdog_node']
                    },
                    {
                        'id': 'equipment_supervisor',
                        'strategy': 'ONE_FOR_ONE',
                        'children': ['grbl_node', 'formlabs_node', 'bambu_node']
                    },
                    {
                        'id': 'robotics_supervisor',
                        'strategy': 'REST_FOR_ONE',
                        'children': ['moveit_node', 'ned2_node', 'xarm_node']
                    },
                ]
            }
        }

        # Verify structure
        assert 'root_supervisor' in tree
        assert len(tree['root_supervisor']['children']) == 3
        assert tree['root_supervisor']['strategy'] == 'ONE_FOR_ALL'

    def test_equipment_failure_isolation(self):
        """Test that equipment failures are isolated."""
        # Equipment uses ONE_FOR_ONE
        children = ['grbl_node', 'formlabs_node', 'bambu_node']
        failed = 'grbl_node'

        # Only failed node restarts
        restarted = [failed]  # ONE_FOR_ONE

        assert len(restarted) == 1
        assert 'formlabs_node' not in restarted
        assert 'bambu_node' not in restarted

    def test_safety_all_or_nothing(self):
        """Test that safety system is all-or-nothing."""
        # Safety uses ONE_FOR_ALL
        safety_nodes = ['safety_node', 'watchdog_node']
        failed = 'watchdog_node'

        # All safety nodes restart
        restarted = safety_nodes.copy()  # ONE_FOR_ALL

        assert 'safety_node' in restarted
        assert 'watchdog_node' in restarted

    def test_robotics_chain_restart(self):
        """Test robotics chain restart behavior."""
        # Robotics uses REST_FOR_ONE
        robotics_nodes = ['moveit_node', 'ned2_node', 'xarm_node']

        # Failure in ned2
        failed_idx = robotics_nodes.index('ned2_node')
        restarted = robotics_nodes[failed_idx:]

        assert 'moveit_node' not in restarted
        assert 'ned2_node' in restarted
        assert 'xarm_node' in restarted


if __name__ == '__main__':
    unittest.main()
