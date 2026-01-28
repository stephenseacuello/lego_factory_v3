#!/usr/bin/env python3
"""
Cloud Sync Node - Multi-site data synchronization

Synchronizes machine status, jobs, and metrics across multiple factory sites
using cloud MQTT or direct site-to-site communication.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import json
import hashlib
from typing import Dict, Set
from datetime import datetime

from std_msgs.msg import String
from cnc_interfaces.msg import CloudSync, MachineStatus, OeeMetrics, Alarm
from cnc_interfaces.srv import CloudBroadcast


class CloudSyncNode(Node):
    """Multi-site synchronization node"""

    def __init__(self):
        super().__init__('cloud_sync')

        # Parameters
        self.declare_parameter('site_id', 'site_001')
        self.declare_parameter('site_name', 'Main Factory')
        self.declare_parameter('region', 'us-west')
        self.declare_parameter('sync_interval', 5.0)
        self.declare_parameter('cloud_broker', 'mqtt://cloud.example.com:8883')

        self.site_id = self.get_parameter('site_id').value
        self.site_name = self.get_parameter('site_name').value
        self.region = self.get_parameter('region').value
        self.sync_interval = self.get_parameter('sync_interval').value

        # Sync state
        self.sequence = 0
        self.pending_acks: Dict[str, CloudSync] = {}
        self.known_sites: Set[str] = {self.site_id}

        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST, depth=10)

        # Subscribers for local data
        self.status_sub = self.create_subscription(
            MachineStatus, '/machine/status', self.status_callback, qos)
        self.oee_sub = self.create_subscription(
            OeeMetrics, '/kpi/oee', self.oee_callback, qos)
        self.alarm_sub = self.create_subscription(
            Alarm, '/system/alarms', self.alarm_callback, qos)

        # Cloud subscribers
        self.cloud_sub = self.create_subscription(
            CloudSync, '/cloud/incoming', self.cloud_callback, qos)

        # Publishers
        self.cloud_pub = self.create_publisher(CloudSync, '/cloud/outgoing', qos)
        self.status_out = self.create_publisher(MachineStatus, '/cloud/status', qos)

        # Service
        self.broadcast_srv = self.create_service(
            CloudBroadcast, '/cloud/broadcast', self.broadcast_callback)

        # Periodic sync timer
        self.sync_timer = self.create_timer(self.sync_interval, self.sync_callback)

        self.get_logger().info(f'Cloud Sync started for site: {self.site_id}')

    def create_sync_message(self, sync_type: int, payload: dict) -> CloudSync:
        """Create cloud sync message"""
        msg = CloudSync()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.site_id = self.site_id
        msg.site_name = self.site_name
        msg.region = self.region
        msg.sync_type = sync_type
        msg.payload_json = json.dumps(payload)
        msg.payload_size = len(msg.payload_json)
        msg.payload_hash = hashlib.sha256(msg.payload_json.encode()).hexdigest()[:16]
        msg.sync_id = f"{self.site_id}_{self.sequence}"
        msg.sequence_number = self.sequence
        msg.origin_timestamp = msg.header.stamp
        self.sequence += 1
        return msg

    def status_callback(self, msg: MachineStatus):
        """Sync machine status to cloud"""
        payload = {
            'machine_id': msg.machine_id,
            'state': msg.state,
            'position': {'x': msg.wpos_x, 'y': msg.wpos_y, 'z': msg.wpos_z},
            'spindle_speed': msg.spindle_speed,
            'feed_rate': msg.feed_rate,
        }
        sync = self.create_sync_message(CloudSync.SYNC_STATUS, payload)
        self.cloud_pub.publish(sync)

    def oee_callback(self, msg: OeeMetrics):
        """Sync OEE metrics to cloud"""
        payload = {
            'machine_id': msg.machine_id,
            'oee': msg.oee,
            'availability': msg.availability,
            'performance': msg.performance,
            'quality': msg.quality,
        }
        sync = self.create_sync_message(CloudSync.SYNC_METRICS, payload)
        sync.bandwidth_priority = CloudSync.BANDWIDTH_NORMAL
        self.cloud_pub.publish(sync)

    def alarm_callback(self, msg: Alarm):
        """Sync alarms to cloud (high priority)"""
        payload = {
            'machine_id': msg.machine_id,
            'alarm_code': msg.alarm_code,
            'message': msg.message,
            'severity': msg.severity,
        }
        sync = self.create_sync_message(CloudSync.SYNC_ALERT, payload)
        sync.bandwidth_priority = CloudSync.BANDWIDTH_CRITICAL
        self.cloud_pub.publish(sync)

    def cloud_callback(self, msg: CloudSync):
        """Process incoming cloud messages"""
        if msg.site_id == self.site_id:
            return  # Ignore our own messages

        self.known_sites.add(msg.site_id)
        msg.received_timestamp = self.get_clock().now().to_msg()

        try:
            payload = json.loads(msg.payload_json)

            if msg.sync_type == CloudSync.SYNC_STATUS:
                # Republish as local status for monitoring
                status = MachineStatus()
                status.machine_id = f"{msg.site_id}/{payload['machine_id']}"
                status.state = payload.get('state', 0)
                self.status_out.publish(status)

            self.get_logger().debug(
                f"Received {msg.sync_type} from {msg.site_id}")

        except json.JSONDecodeError:
            self.get_logger().warn(f"Invalid JSON from {msg.site_id}")

    def sync_callback(self):
        """Periodic sync heartbeat"""
        payload = {
            'heartbeat': True,
            'site_name': self.site_name,
            'region': self.region,
            'known_sites': list(self.known_sites),
        }
        sync = self.create_sync_message(CloudSync.SYNC_STATUS, payload)
        sync.bandwidth_priority = CloudSync.BANDWIDTH_LOW
        self.cloud_pub.publish(sync)

    def broadcast_callback(self, request, response):
        """Handle broadcast service request"""
        try:
            payload = json.loads(request.payload_json)
            sync = self.create_sync_message(request.sync_type, payload)
            sync.destination_sites = list(request.destination_sites)
            sync.bandwidth_priority = request.bandwidth_priority

            self.cloud_pub.publish(sync)

            response.success = True
            response.message = "Broadcast sent"
            response.sync_id = sync.sync_id
            response.acknowledged_sites = []  # Would be populated async

        except Exception as e:
            response.success = False
            response.message = str(e)

        return response


def main(args=None):
    rclpy.init(args=args)
    node = CloudSyncNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
