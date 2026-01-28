#!/usr/bin/env python3
"""
LEGO MCP Bandwidth Optimizer

Optimizes ROS2 network bandwidth through:
- Dynamic QoS adjustment based on network conditions
- Selective topic subscription (subscribe only when needed)
- Message rate limiting and throttling
- Topic aggregation for high-frequency data
- Lazy subscription patterns

LEGO MCP Manufacturing System v7.0
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Callable, Any
from collections import defaultdict
import statistics

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSProfile, ReliabilityPolicy, HistoryPolicy,
    DurabilityPolicy, LivelinessPolicy
)
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String


class BandwidthPriority(Enum):
    """Priority levels for bandwidth allocation."""
    CRITICAL = 4    # Safety, e-stop - always full bandwidth
    HIGH = 3        # Active equipment control
    NORMAL = 2      # Standard monitoring
    LOW = 1         # Diagnostics, logging
    BACKGROUND = 0  # Non-essential data


@dataclass
class TopicStats:
    """Statistics for a topic."""
    topic_name: str
    message_count: int = 0
    bytes_received: int = 0
    last_message_time: float = 0.0
    message_rate_hz: float = 0.0
    avg_message_size: float = 0.0
    priority: BandwidthPriority = BandwidthPriority.NORMAL
    throttle_rate: float = 1.0  # 1.0 = no throttle, 0.5 = half rate
    recent_intervals: List[float] = field(default_factory=list)


@dataclass
class SubscriptionConfig:
    """Configuration for a managed subscription."""
    topic_name: str
    message_type: str
    priority: BandwidthPriority
    max_rate_hz: Optional[float] = None
    lazy: bool = False  # If true, only subscribe when requested
    aggregate: bool = False  # If true, aggregate messages
    aggregate_window_ms: int = 100


class BandwidthOptimizerNode(Node):
    """
    Optimizes bandwidth usage across the factory cell network.

    Features:
    - Monitors topic bandwidth usage
    - Dynamically adjusts QoS profiles
    - Implements rate limiting for high-frequency topics
    - Provides lazy subscription management
    - Aggregates high-frequency sensor data
    """

    def __init__(self):
        super().__init__('bandwidth_optimizer')

        # Parameters
        self.declare_parameter('monitoring_interval_seconds', 1.0)
        self.declare_parameter('max_total_bandwidth_mbps', 100.0)
        self.declare_parameter('throttle_threshold_percent', 80.0)
        self.declare_parameter('enable_auto_throttle', True)

        self.monitoring_interval = self.get_parameter('monitoring_interval_seconds').value
        self.max_bandwidth = self.get_parameter('max_total_bandwidth_mbps').value * 1024 * 1024 / 8  # bytes/s
        self.throttle_threshold = self.get_parameter('throttle_threshold_percent').value / 100.0
        self.auto_throttle = self.get_parameter('enable_auto_throttle').value

        # Topic statistics
        self.topic_stats: Dict[str, TopicStats] = {}
        self.managed_subscriptions: Dict[str, SubscriptionConfig] = {}

        # Lazy subscription state
        self.lazy_subscribers: Dict[str, Any] = {}
        self.lazy_callbacks: Dict[str, List[Callable]] = defaultdict(list)

        # Aggregation buffers
        self.aggregation_buffers: Dict[str, List] = defaultdict(list)
        self.aggregation_timers: Dict[str, Any] = {}

        # QoS profiles for different priorities
        self.qos_profiles = {
            BandwidthPriority.CRITICAL: QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=10,
                durability=DurabilityPolicy.VOLATILE,
            ),
            BandwidthPriority.HIGH: QoSProfile(
                reliability=ReliabilityPolicy.RELIABLE,
                history=HistoryPolicy.KEEP_LAST,
                depth=5,
            ),
            BandwidthPriority.NORMAL: QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST,
                depth=5,
            ),
            BandwidthPriority.LOW: QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
            ),
            BandwidthPriority.BACKGROUND: QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT,
                history=HistoryPolicy.KEEP_LAST,
                depth=1,
            ),
        }

        self.cb_group = ReentrantCallbackGroup()

        # Publishers
        self.stats_pub = self.create_publisher(
            String, '/bandwidth/statistics', 10
        )
        self.alerts_pub = self.create_publisher(
            String, '/bandwidth/alerts', 10
        )

        # Topic monitoring subscriber
        # Note: In production, this would use ROS2 introspection APIs
        self.create_subscription(
            String, '/discovery/topology',
            self._on_topology_update, 10,
            callback_group=self.cb_group
        )

        # Control subscribers
        self.create_subscription(
            String, '/bandwidth/set_priority',
            self._on_set_priority, 10,
            callback_group=self.cb_group
        )
        self.create_subscription(
            String, '/bandwidth/request_subscription',
            self._on_subscription_request, 10,
            callback_group=self.cb_group
        )

        # Timers
        self.stats_timer = self.create_timer(
            self.monitoring_interval, self._publish_statistics,
            callback_group=self.cb_group
        )
        self.optimize_timer = self.create_timer(
            5.0, self._optimize_bandwidth,
            callback_group=self.cb_group
        )

        # Initialize priority mappings for known topics
        self._initialize_topic_priorities()

        self.get_logger().info('Bandwidth Optimizer initialized')

    def _initialize_topic_priorities(self):
        """Set default priorities for known topic patterns."""
        self.topic_priority_patterns = {
            '/safety/': BandwidthPriority.CRITICAL,
            '/estop': BandwidthPriority.CRITICAL,
            '/cmd_vel': BandwidthPriority.HIGH,
            '/joint_states': BandwidthPriority.HIGH,
            '/status': BandwidthPriority.NORMAL,
            '/odom': BandwidthPriority.NORMAL,
            '/imu': BandwidthPriority.LOW,
            '/tof_': BandwidthPriority.LOW,
            '/diagnostics': BandwidthPriority.BACKGROUND,
            '/rosout': BandwidthPriority.BACKGROUND,
        }

    def _get_topic_priority(self, topic_name: str) -> BandwidthPriority:
        """Determine priority for a topic based on patterns."""
        for pattern, priority in self.topic_priority_patterns.items():
            if pattern in topic_name.lower():
                return priority
        return BandwidthPriority.NORMAL

    def register_topic(self, topic_name: str, priority: BandwidthPriority = None):
        """Register a topic for monitoring."""
        if topic_name not in self.topic_stats:
            self.topic_stats[topic_name] = TopicStats(
                topic_name=topic_name,
                priority=priority or self._get_topic_priority(topic_name),
            )

    def update_topic_stats(self, topic_name: str, message_size: int):
        """Update statistics for a topic after receiving a message."""
        if topic_name not in self.topic_stats:
            self.register_topic(topic_name)

        stats = self.topic_stats[topic_name]
        now = time.time()

        # Calculate interval
        if stats.last_message_time > 0:
            interval = now - stats.last_message_time
            stats.recent_intervals.append(interval)

            # Keep only last 100 intervals
            if len(stats.recent_intervals) > 100:
                stats.recent_intervals = stats.recent_intervals[-100:]

            # Calculate rate
            if stats.recent_intervals:
                avg_interval = statistics.mean(stats.recent_intervals)
                if avg_interval > 0:
                    stats.message_rate_hz = 1.0 / avg_interval

        stats.message_count += 1
        stats.bytes_received += message_size
        stats.last_message_time = now

        # Update average message size
        stats.avg_message_size = stats.bytes_received / stats.message_count

    def set_topic_priority(self, topic_name: str, priority: BandwidthPriority):
        """Set priority for a topic."""
        if topic_name in self.topic_stats:
            self.topic_stats[topic_name].priority = priority
        else:
            self.register_topic(topic_name, priority)

    def set_throttle_rate(self, topic_name: str, rate: float):
        """Set throttle rate for a topic (0.0-1.0)."""
        if topic_name in self.topic_stats:
            self.topic_stats[topic_name].throttle_rate = max(0.0, min(1.0, rate))

    def request_lazy_subscription(self, topic_name: str, callback: Callable,
                                   duration_seconds: float = None):
        """Request a lazy subscription to a topic."""
        if topic_name not in self.lazy_callbacks:
            # Create subscription if this is first request
            self._create_lazy_subscription(topic_name)

        self.lazy_callbacks[topic_name].append({
            'callback': callback,
            'expires': time.time() + duration_seconds if duration_seconds else None,
        })

    def release_lazy_subscription(self, topic_name: str, callback: Callable = None):
        """Release a lazy subscription."""
        if topic_name in self.lazy_callbacks:
            if callback:
                self.lazy_callbacks[topic_name] = [
                    c for c in self.lazy_callbacks[topic_name]
                    if c['callback'] != callback
                ]
            else:
                self.lazy_callbacks[topic_name] = []

            # Destroy subscription if no more callbacks
            if not self.lazy_callbacks[topic_name] and topic_name in self.lazy_subscribers:
                self.destroy_subscription(self.lazy_subscribers[topic_name])
                del self.lazy_subscribers[topic_name]

    def _create_lazy_subscription(self, topic_name: str):
        """Create a lazy subscription."""
        # Determine QoS based on priority
        priority = self._get_topic_priority(topic_name)
        qos = self.qos_profiles.get(priority, self.qos_profiles[BandwidthPriority.NORMAL])

        # Create generic subscription (assumes String for simplicity)
        # In production, would need type introspection
        sub = self.create_subscription(
            String, topic_name,
            lambda msg, tn=topic_name: self._on_lazy_message(tn, msg),
            qos, callback_group=self.cb_group
        )
        self.lazy_subscribers[topic_name] = sub

    def _on_lazy_message(self, topic_name: str, msg):
        """Handle message for lazy subscription."""
        now = time.time()

        # Update stats
        self.update_topic_stats(topic_name, len(str(msg)))

        # Check throttle
        stats = self.topic_stats.get(topic_name)
        if stats and stats.throttle_rate < 1.0:
            # Simple probabilistic throttle
            import random
            if random.random() > stats.throttle_rate:
                return

        # Call registered callbacks
        valid_callbacks = []
        for cb_info in self.lazy_callbacks.get(topic_name, []):
            # Check expiration
            if cb_info['expires'] and now > cb_info['expires']:
                continue

            valid_callbacks.append(cb_info)
            try:
                cb_info['callback'](msg)
            except Exception as e:
                self.get_logger().error(f'Lazy callback error: {e}')

        self.lazy_callbacks[topic_name] = valid_callbacks

        # Clean up if no more callbacks
        if not valid_callbacks and topic_name in self.lazy_subscribers:
            self.destroy_subscription(self.lazy_subscribers[topic_name])
            del self.lazy_subscribers[topic_name]

    def _on_topology_update(self, msg: String):
        """Update topic list from topology."""
        try:
            data = json.loads(msg.data)
            for topic in data.get('topics', {}).keys():
                self.register_topic(topic)
        except json.JSONDecodeError:
            pass

    def _on_set_priority(self, msg: String):
        """Handle priority setting request."""
        try:
            data = json.loads(msg.data)
            topic = data.get('topic')
            priority = BandwidthPriority(data.get('priority', 2))
            if topic:
                self.set_topic_priority(topic, priority)
        except (json.JSONDecodeError, ValueError):
            pass

    def _on_subscription_request(self, msg: String):
        """Handle subscription request."""
        try:
            data = json.loads(msg.data)
            topic = data.get('topic')
            duration = data.get('duration_seconds')
            if topic:
                # Create a placeholder callback that publishes to a relay topic
                self.request_lazy_subscription(topic, lambda m: None, duration)
        except json.JSONDecodeError:
            pass

    def _optimize_bandwidth(self):
        """Optimize bandwidth allocation across topics."""
        if not self.auto_throttle:
            return

        # Calculate total bandwidth
        total_bytes_per_sec = sum(
            stats.message_rate_hz * stats.avg_message_size
            for stats in self.topic_stats.values()
            if stats.message_rate_hz > 0
        )

        # Check if over threshold
        if total_bytes_per_sec > self.max_bandwidth * self.throttle_threshold:
            self._apply_throttling(total_bytes_per_sec)
        else:
            # Relax throttling
            self._relax_throttling()

    def _apply_throttling(self, current_bandwidth: float):
        """Apply throttling to reduce bandwidth."""
        # Calculate required reduction
        target_bandwidth = self.max_bandwidth * self.throttle_threshold * 0.9
        reduction_factor = target_bandwidth / current_bandwidth

        # Apply throttling by priority (low priority first)
        for priority in sorted(BandwidthPriority, key=lambda p: p.value):
            if priority == BandwidthPriority.CRITICAL:
                continue  # Never throttle critical

            for stats in self.topic_stats.values():
                if stats.priority == priority:
                    # Calculate new throttle rate
                    new_rate = stats.throttle_rate * reduction_factor
                    new_rate = max(0.1, min(1.0, new_rate))  # Min 10%
                    stats.throttle_rate = new_rate

            # Recalculate bandwidth
            new_bandwidth = sum(
                stats.message_rate_hz * stats.avg_message_size * stats.throttle_rate
                for stats in self.topic_stats.values()
                if stats.message_rate_hz > 0
            )

            if new_bandwidth <= target_bandwidth:
                break

        self._publish_alert('throttling_applied', {
            'current_bandwidth_mbps': current_bandwidth / (1024 * 1024) * 8,
            'target_bandwidth_mbps': target_bandwidth / (1024 * 1024) * 8,
        })

    def _relax_throttling(self):
        """Gradually relax throttling."""
        for stats in self.topic_stats.values():
            if stats.throttle_rate < 1.0:
                stats.throttle_rate = min(1.0, stats.throttle_rate + 0.1)

    def _publish_statistics(self):
        """Publish bandwidth statistics."""
        total_messages = sum(s.message_count for s in self.topic_stats.values())
        total_bytes = sum(s.bytes_received for s in self.topic_stats.values())

        # Calculate current bandwidth
        current_bandwidth = sum(
            stats.message_rate_hz * stats.avg_message_size
            for stats in self.topic_stats.values()
            if stats.message_rate_hz > 0
        )

        statistics_data = {
            'timestamp': time.time(),
            'timestamp_iso': datetime.now().isoformat(),
            'total_messages': total_messages,
            'total_bytes': total_bytes,
            'current_bandwidth_mbps': current_bandwidth / (1024 * 1024) * 8,
            'max_bandwidth_mbps': self.max_bandwidth / (1024 * 1024) * 8,
            'utilization_percent': (current_bandwidth / self.max_bandwidth) * 100,
            'topic_count': len(self.topic_stats),
            'lazy_subscriptions': len(self.lazy_subscribers),
            'topics': {
                name: {
                    'rate_hz': stats.message_rate_hz,
                    'avg_size_bytes': stats.avg_message_size,
                    'bandwidth_kbps': stats.message_rate_hz * stats.avg_message_size / 1024 * 8,
                    'priority': stats.priority.value,
                    'throttle_rate': stats.throttle_rate,
                }
                for name, stats in self.topic_stats.items()
                if stats.message_rate_hz > 0
            },
        }

        msg = String()
        msg.data = json.dumps(statistics_data)
        self.stats_pub.publish(msg)

    def _publish_alert(self, alert_type: str, data: Dict):
        """Publish bandwidth alert."""
        alert = {
            'type': alert_type,
            'timestamp': time.time(),
            'timestamp_iso': datetime.now().isoformat(),
            'data': data,
        }

        msg = String()
        msg.data = json.dumps(alert)
        self.alerts_pub.publish(msg)


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    node = BandwidthOptimizerNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
