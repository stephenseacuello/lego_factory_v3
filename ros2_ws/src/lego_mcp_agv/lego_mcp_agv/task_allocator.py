#!/usr/bin/env python3
"""
LEGO MCP AGV Task Allocator

Intelligent task allocation for AGV fleet using multiple strategies:
- Nearest neighbor assignment
- Load balancing
- Battery-aware allocation
- Priority-based allocation
- Auction-based multi-AGV coordination

LEGO MCP Manufacturing System v7.0
"""

import json
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
import heapq

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String


class AllocationStrategy(Enum):
    """Task allocation strategies."""
    NEAREST = "nearest"          # Assign to nearest AGV
    LOAD_BALANCE = "load_balance"  # Balance tasks across AGVs
    BATTERY_AWARE = "battery_aware"  # Consider battery levels
    AUCTION = "auction"          # Auction-based allocation
    HYBRID = "hybrid"            # Combine multiple strategies


@dataclass
class AGVBid:
    """Bid from an AGV for a task."""
    agv_id: str
    task_id: str
    cost: float  # Lower is better
    estimated_time: float
    battery_after: float
    timestamp: float


class TaskAllocatorNode(Node):
    """
    Intelligent task allocation for AGV fleet.

    Uses multiple allocation strategies to optimize:
    - Total travel distance
    - Task completion time
    - Battery usage
    - Fleet utilization
    """

    def __init__(self):
        super().__init__('task_allocator')

        # Parameters
        self.declare_parameter('strategy', 'hybrid')
        self.declare_parameter('auction_timeout_ms', 500)
        self.declare_parameter('distance_weight', 0.4)
        self.declare_parameter('battery_weight', 0.3)
        self.declare_parameter('load_weight', 0.3)

        self.strategy = AllocationStrategy(self.get_parameter('strategy').value)
        self.auction_timeout = self.get_parameter('auction_timeout_ms').value / 1000.0
        self.distance_weight = self.get_parameter('distance_weight').value
        self.battery_weight = self.get_parameter('battery_weight').value
        self.load_weight = self.get_parameter('load_weight').value

        # State
        self.agv_states: Dict[str, dict] = {}
        self.pending_auctions: Dict[str, List[AGVBid]] = {}
        self.task_assignments: Dict[str, str] = {}  # task_id -> agv_id

        self.cb_group = ReentrantCallbackGroup()

        # Subscribers
        self.create_subscription(
            String, '/fleet/status',
            self._on_fleet_status, 10,
            callback_group=self.cb_group
        )
        self.create_subscription(
            String, '/task_allocator/bid',
            self._on_agv_bid, 10,
            callback_group=self.cb_group
        )
        self.create_subscription(
            String, '/task_allocator/request',
            self._on_allocation_request, 10,
            callback_group=self.cb_group
        )

        # Publishers
        self.allocation_pub = self.create_publisher(
            String, '/task_allocator/allocation', 10
        )
        self.bid_request_pub = self.create_publisher(
            String, '/task_allocator/bid_request', 10
        )

        self.get_logger().info(f'Task Allocator initialized with {self.strategy.value} strategy')

    def _on_fleet_status(self, msg: String):
        """Update AGV states from fleet status."""
        try:
            data = json.loads(msg.data)
            self.agv_states = data.get('agvs', {})
        except json.JSONDecodeError:
            pass

    def _on_allocation_request(self, msg: String):
        """Handle task allocation request."""
        try:
            data = json.loads(msg.data)
            task_id = data.get('task_id')
            task_type = data.get('task_type')
            source = data.get('source')
            destination = data.get('destination')
            priority = data.get('priority', 2)

            if self.strategy == AllocationStrategy.AUCTION:
                self._start_auction(task_id, data)
            else:
                allocation = self._allocate_task(data)
                self._publish_allocation(allocation)

        except json.JSONDecodeError:
            pass

    def _on_agv_bid(self, msg: String):
        """Handle bid from AGV in auction."""
        try:
            data = json.loads(msg.data)
            bid = AGVBid(
                agv_id=data['agv_id'],
                task_id=data['task_id'],
                cost=data['cost'],
                estimated_time=data['estimated_time'],
                battery_after=data['battery_after'],
                timestamp=time.time(),
            )

            task_id = bid.task_id
            if task_id not in self.pending_auctions:
                self.pending_auctions[task_id] = []

            self.pending_auctions[task_id].append(bid)

        except (json.JSONDecodeError, KeyError):
            pass

    def _allocate_task(self, task: dict) -> dict:
        """Allocate a task using the configured strategy."""
        available_agvs = self._get_available_agvs()

        if not available_agvs:
            return {
                'task_id': task.get('task_id'),
                'assigned_agv': None,
                'error': 'No available AGVs',
            }

        if self.strategy == AllocationStrategy.NEAREST:
            agv_id = self._allocate_nearest(task, available_agvs)
        elif self.strategy == AllocationStrategy.LOAD_BALANCE:
            agv_id = self._allocate_load_balance(task, available_agvs)
        elif self.strategy == AllocationStrategy.BATTERY_AWARE:
            agv_id = self._allocate_battery_aware(task, available_agvs)
        elif self.strategy == AllocationStrategy.HYBRID:
            agv_id = self._allocate_hybrid(task, available_agvs)
        else:
            agv_id = available_agvs[0]

        self.task_assignments[task.get('task_id')] = agv_id

        return {
            'task_id': task.get('task_id'),
            'assigned_agv': agv_id,
            'strategy': self.strategy.value,
        }

    def _get_available_agvs(self) -> List[str]:
        """Get list of available AGVs."""
        available = []
        for agv_id, state in self.agv_states.items():
            if (state.get('state') in ['idle', 'moving'] and
                state.get('battery', 100) > 20 and
                state.get('online', False) and
                state.get('current_task') is None):
                available.append(agv_id)
        return available

    def _allocate_nearest(self, task: dict, available_agvs: List[str]) -> str:
        """Allocate to nearest AGV."""
        dest = task.get('destination_pose', {})
        dest_x = dest.get('x', 0)
        dest_y = dest.get('y', 0)

        # If there's a source, use that as target for initial approach
        source = task.get('source_pose')
        if source:
            target_x = source.get('x', dest_x)
            target_y = source.get('y', dest_y)
        else:
            target_x, target_y = dest_x, dest_y

        best_agv = None
        best_distance = float('inf')

        for agv_id in available_agvs:
            state = self.agv_states.get(agv_id, {})
            pos = state.get('position', {})
            agv_x = pos.get('x', 0)
            agv_y = pos.get('y', 0)

            distance = math.sqrt((target_x - agv_x)**2 + (target_y - agv_y)**2)

            if distance < best_distance:
                best_distance = distance
                best_agv = agv_id

        return best_agv or available_agvs[0]

    def _allocate_load_balance(self, task: dict, available_agvs: List[str]) -> str:
        """Allocate to AGV with fewest recent tasks."""
        # Count recent assignments per AGV
        task_counts = {agv_id: 0 for agv_id in available_agvs}

        for assigned_agv in self.task_assignments.values():
            if assigned_agv in task_counts:
                task_counts[assigned_agv] += 1

        # Return AGV with lowest count
        return min(task_counts.keys(), key=lambda x: task_counts[x])

    def _allocate_battery_aware(self, task: dict, available_agvs: List[str]) -> str:
        """Allocate considering battery levels."""
        # Calculate estimated battery usage for task
        dest = task.get('destination_pose', {})
        source = task.get('source_pose')

        best_agv = None
        best_score = float('inf')

        for agv_id in available_agvs:
            state = self.agv_states.get(agv_id, {})
            battery = state.get('battery', 100)
            pos = state.get('position', {})

            # Estimate distance
            if source:
                dist = (math.sqrt((source['x'] - pos.get('x', 0))**2 +
                                  (source['y'] - pos.get('y', 0))**2) +
                        math.sqrt((dest.get('x', 0) - source['x'])**2 +
                                  (dest.get('y', 0) - source['y'])**2))
            else:
                dist = math.sqrt((dest.get('x', 0) - pos.get('x', 0))**2 +
                                 (dest.get('y', 0) - pos.get('y', 0))**2)

            # Estimate battery usage (rough: 1% per 0.5m)
            battery_usage = dist * 2

            # Score: prefer AGVs that will still have good battery after task
            remaining_battery = battery - battery_usage

            if remaining_battery < 15:
                score = float('inf')  # Don't use if battery will be too low
            else:
                # Balance distance and battery preservation
                score = dist / remaining_battery

            if score < best_score:
                best_score = score
                best_agv = agv_id

        return best_agv or available_agvs[0]

    def _allocate_hybrid(self, task: dict, available_agvs: List[str]) -> str:
        """Hybrid allocation using weighted scoring."""
        dest = task.get('destination_pose', {})
        source = task.get('source_pose')
        priority = task.get('priority', 2)

        scored_agvs = []

        for agv_id in available_agvs:
            state = self.agv_states.get(agv_id, {})
            battery = state.get('battery', 100)
            pos = state.get('position', {})

            # Calculate distance score (normalized)
            if source:
                dist = (math.sqrt((source['x'] - pos.get('x', 0))**2 +
                                  (source['y'] - pos.get('y', 0))**2) +
                        math.sqrt((dest.get('x', 0) - source['x'])**2 +
                                  (dest.get('y', 0) - source['y'])**2))
            else:
                dist = math.sqrt((dest.get('x', 0) - pos.get('x', 0))**2 +
                                 (dest.get('y', 0) - pos.get('y', 0))**2)

            distance_score = min(dist / 2.0, 1.0)  # Normalize to 0-1

            # Battery score (higher battery = better score)
            battery_score = 1.0 - (battery / 100.0)

            # Load score (fewer tasks = better)
            task_count = sum(1 for t, a in self.task_assignments.items() if a == agv_id)
            load_score = min(task_count / 5.0, 1.0)

            # Weighted combination
            total_score = (
                self.distance_weight * distance_score +
                self.battery_weight * battery_score +
                self.load_weight * load_score
            )

            # Priority boost for urgent tasks
            if priority >= 3:
                total_score *= (1.0 - 0.1 * (priority - 2))

            scored_agvs.append((agv_id, total_score))

        # Return AGV with lowest score
        scored_agvs.sort(key=lambda x: x[1])
        return scored_agvs[0][0] if scored_agvs else available_agvs[0]

    def _start_auction(self, task_id: str, task: dict):
        """Start an auction for a task."""
        self.pending_auctions[task_id] = []

        # Publish bid request
        bid_request = {
            'task_id': task_id,
            'task': task,
            'deadline': time.time() + self.auction_timeout,
        }

        msg = String()
        msg.data = json.dumps(bid_request)
        self.bid_request_pub.publish(msg)

        # Schedule auction resolution
        self.create_timer(
            self.auction_timeout,
            lambda: self._resolve_auction(task_id),
            callback_group=self.cb_group
        )

    def _resolve_auction(self, task_id: str):
        """Resolve an auction and assign task."""
        if task_id not in self.pending_auctions:
            return

        bids = self.pending_auctions.pop(task_id)

        if not bids:
            self.get_logger().warn(f'No bids received for task {task_id}')
            return

        # Select winning bid (lowest cost)
        winning_bid = min(bids, key=lambda b: b.cost)

        self.task_assignments[task_id] = winning_bid.agv_id

        allocation = {
            'task_id': task_id,
            'assigned_agv': winning_bid.agv_id,
            'strategy': 'auction',
            'winning_cost': winning_bid.cost,
            'bid_count': len(bids),
        }

        self._publish_allocation(allocation)
        self.get_logger().info(
            f'Auction resolved: {task_id} -> {winning_bid.agv_id} (cost: {winning_bid.cost:.2f})'
        )

    def _publish_allocation(self, allocation: dict):
        """Publish task allocation result."""
        msg = String()
        msg.data = json.dumps(allocation)
        self.allocation_pub.publish(msg)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    node = TaskAllocatorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
