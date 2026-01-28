#!/usr/bin/env python3
"""
Unity Scheduler Bridge Node
============================
ROS2 node that bridges scheduling data between Flask SCADA and Unity clients.

Subscribes to:
- /scheduler/updates (ScheduleUpdate)
- MQTT: cnc/schedule/#

Publishes to:
- /unity/schedule (UnitySchedule)
- MQTT: cnc/{machine_id}/unity/schedule

Features:
- Real-time schedule updates to Unity
- Job assignment notifications
- Gantt chart data formatting
- Drag-drop schedule change handling
- OR-Tools optimization triggers

Author: Flask CNC SCADA System
"""

import json
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

# Standard ROS2 messages
from std_msgs.msg import String

# MQTT client
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ScheduledJob:
    """Job in the schedule."""
    job_id: str
    part_number: str
    quantity: int
    machine_id: str
    start_time: str  # ISO format
    end_time: str    # ISO format
    status: str      # pending, running, completed, paused
    priority: int
    progress: float
    operator: str = ""
    notes: str = ""


@dataclass
class MachineSchedule:
    """Schedule for a single machine."""
    machine_id: str
    machine_name: str
    status: str  # online, offline, maintenance
    utilization: float
    jobs: List[ScheduledJob] = field(default_factory=list)


@dataclass
class UnitySchedulePayload:
    """Complete schedule payload for Unity."""
    timestamp: str
    plant_id: str
    machines: List[MachineSchedule] = field(default_factory=list)
    pending_jobs: List[ScheduledJob] = field(default_factory=list)
    optimization_available: bool = False


# =============================================================================
# Unity Scheduler Bridge Node
# =============================================================================

class UnitySchedulerBridge(Node):
    """
    ROS2 node that formats and publishes schedule data for Unity clients.

    Converts internal schedule format to Unity-friendly JSON with
    Gantt chart data, drag-drop support, and real-time updates.
    """

    def __init__(self):
        super().__init__('unity_scheduler_bridge')

        # Parameters
        self.declare_parameter('plant_id', 'plant-1')
        self.declare_parameter('mqtt_enabled', True)
        self.declare_parameter('mqtt_host', 'localhost')
        self.declare_parameter('mqtt_port', 1883)
        self.declare_parameter('publish_rate_hz', 1.0)

        self.plant_id = self.get_parameter('plant_id').value
        self.mqtt_enabled = self.get_parameter('mqtt_enabled').value
        self.mqtt_host = self.get_parameter('mqtt_host').value
        self.mqtt_port = self.get_parameter('mqtt_port').value
        self.publish_rate_hz = self.get_parameter('publish_rate_hz').value

        # QoS
        self.reliable_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        # State
        self.machines: Dict[str, MachineSchedule] = {}
        self.pending_jobs: List[ScheduledJob] = []
        self.state_lock = threading.Lock()

        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        if self.mqtt_enabled and MQTT_AVAILABLE:
            self._init_mqtt()

        # Publishers
        self.schedule_pub = self.create_publisher(
            String,
            '/unity/schedule',
            self.reliable_qos
        )

        # Subscribers
        self.update_sub = self.create_subscription(
            String,
            '/scheduler/updates',
            self._on_schedule_update,
            self.reliable_qos
        )

        self.job_sub = self.create_subscription(
            String,
            '/scheduler/jobs',
            self._on_job_update,
            self.reliable_qos
        )

        self.machine_sub = self.create_subscription(
            String,
            '/scheduler/machines',
            self._on_machine_update,
            self.reliable_qos
        )

        # Publish timer
        period = 1.0 / self.publish_rate_hz
        self.publish_timer = self.create_timer(period, self._publish_schedule)

        self.get_logger().info(
            f'Unity Scheduler Bridge started for plant {self.plant_id}'
        )

    # -------------------------------------------------------------------------
    # MQTT
    # -------------------------------------------------------------------------

    def _init_mqtt(self) -> None:
        """Initialize MQTT client."""
        try:
            self.mqtt_client = mqtt.Client(
                client_id=f'unity_scheduler_bridge_{self.plant_id}',
                protocol=mqtt.MQTTv5
            )
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.connect_async(self.mqtt_host, self.mqtt_port)
            self.mqtt_client.loop_start()
        except Exception as e:
            self.get_logger().warn(f'MQTT init failed: {e}')
            self.mqtt_client = None

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        """Handle MQTT connection."""
        if rc == 0:
            client.subscribe('cnc/schedule/#', qos=1)
            client.subscribe('cnc/+/job/+', qos=1)
            self.get_logger().info('MQTT connected')

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle MQTT message."""
        try:
            data = json.loads(msg.payload.decode())
            topic_parts = msg.topic.split('/')

            if 'schedule' in topic_parts:
                self._handle_schedule_mqtt(data)
            elif 'job' in topic_parts:
                self._handle_job_mqtt(topic_parts, data)

        except Exception as e:
            self.get_logger().error(f'MQTT message error: {e}')

    def _handle_schedule_mqtt(self, data: Dict[str, Any]) -> None:
        """Handle schedule update from MQTT."""
        with self.state_lock:
            if 'machines' in data:
                for machine_data in data['machines']:
                    machine_id = machine_data.get('machine_id')
                    if machine_id:
                        self._update_machine(machine_id, machine_data)

            if 'pending_jobs' in data:
                self.pending_jobs = [
                    self._parse_job(j) for j in data['pending_jobs']
                ]

    def _handle_job_mqtt(self, topic_parts: List[str], data: Dict[str, Any]) -> None:
        """Handle job update from MQTT."""
        if len(topic_parts) >= 4:
            machine_id = topic_parts[1]
            job_id = topic_parts[3]

            with self.state_lock:
                if machine_id in self.machines:
                    self._update_job(machine_id, job_id, data)

    # -------------------------------------------------------------------------
    # ROS2 Callbacks
    # -------------------------------------------------------------------------

    def _on_schedule_update(self, msg: String) -> None:
        """Handle schedule update from ROS2."""
        try:
            data = json.loads(msg.data)
            self._handle_schedule_mqtt(data)
        except Exception as e:
            self.get_logger().error(f'Schedule update error: {e}')

    def _on_job_update(self, msg: String) -> None:
        """Handle job update from ROS2."""
        try:
            data = json.loads(msg.data)
            job = self._parse_job(data)

            with self.state_lock:
                machine_id = data.get('machine_id')
                if machine_id and machine_id in self.machines:
                    self._update_job(machine_id, job.job_id, data)

        except Exception as e:
            self.get_logger().error(f'Job update error: {e}')

    def _on_machine_update(self, msg: String) -> None:
        """Handle machine update from ROS2."""
        try:
            data = json.loads(msg.data)
            machine_id = data.get('machine_id')

            if machine_id:
                with self.state_lock:
                    self._update_machine(machine_id, data)

        except Exception as e:
            self.get_logger().error(f'Machine update error: {e}')

    # -------------------------------------------------------------------------
    # State Management
    # -------------------------------------------------------------------------

    def _parse_job(self, data: Dict[str, Any]) -> ScheduledJob:
        """Parse job from dictionary."""
        return ScheduledJob(
            job_id=data.get('job_id', ''),
            part_number=data.get('part_number', ''),
            quantity=data.get('quantity', 1),
            machine_id=data.get('machine_id', ''),
            start_time=data.get('start_time', ''),
            end_time=data.get('end_time', ''),
            status=data.get('status', 'pending'),
            priority=data.get('priority', 0),
            progress=data.get('progress', 0.0),
            operator=data.get('operator', ''),
            notes=data.get('notes', '')
        )

    def _update_machine(self, machine_id: str, data: Dict[str, Any]) -> None:
        """Update machine state."""
        if machine_id not in self.machines:
            self.machines[machine_id] = MachineSchedule(
                machine_id=machine_id,
                machine_name=data.get('machine_name', machine_id),
                status='offline',
                utilization=0.0,
                jobs=[]
            )

        machine = self.machines[machine_id]
        machine.status = data.get('status', machine.status)
        machine.utilization = data.get('utilization', machine.utilization)

        if 'jobs' in data:
            machine.jobs = [self._parse_job(j) for j in data['jobs']]

    def _update_job(self, machine_id: str, job_id: str, data: Dict[str, Any]) -> None:
        """Update job in machine schedule."""
        if machine_id not in self.machines:
            return

        machine = self.machines[machine_id]

        # Find and update job
        for i, job in enumerate(machine.jobs):
            if job.job_id == job_id:
                machine.jobs[i] = self._parse_job({**asdict(job), **data})
                return

        # Job not found, add it
        machine.jobs.append(self._parse_job(data))

    # -------------------------------------------------------------------------
    # Publishing
    # -------------------------------------------------------------------------

    def _publish_schedule(self) -> None:
        """Publish current schedule to Unity."""
        with self.state_lock:
            payload = UnitySchedulePayload(
                timestamp=datetime.utcnow().isoformat() + 'Z',
                plant_id=self.plant_id,
                machines=list(self.machines.values()),
                pending_jobs=self.pending_jobs,
                optimization_available=len(self.pending_jobs) > 0
            )

        # Convert to Unity-friendly format
        unity_data = self._format_for_unity(payload)

        # Publish to ROS2
        msg = String()
        msg.data = json.dumps(unity_data)
        self.schedule_pub.publish(msg)

        # Publish to MQTT
        if self.mqtt_client and self.mqtt_client.is_connected():
            self.mqtt_client.publish(
                f'cnc/{self.plant_id}/unity/schedule',
                msg.data,
                qos=0
            )

    def _format_for_unity(self, payload: UnitySchedulePayload) -> Dict[str, Any]:
        """Format schedule data for Unity Gantt chart."""
        # Calculate time range
        now = datetime.utcnow()
        timeline_start = now - timedelta(hours=2)
        timeline_end = now + timedelta(hours=24)

        # Build Gantt data
        gantt_items = []

        for machine in payload.machines:
            for job in machine.jobs:
                gantt_items.append({
                    'id': f'{machine.machine_id}_{job.job_id}',
                    'job_id': job.job_id,
                    'machine_id': machine.machine_id,
                    'part_number': job.part_number,
                    'start': job.start_time,
                    'end': job.end_time,
                    'status': job.status,
                    'progress': job.progress,
                    'priority': job.priority,
                    'color': self._get_status_color(job.status),
                    'draggable': job.status == 'pending',
                    'resizable': job.status == 'pending'
                })

        # Build machine tracks
        tracks = []
        for machine in payload.machines:
            tracks.append({
                'id': machine.machine_id,
                'name': machine.machine_name,
                'status': machine.status,
                'utilization': machine.utilization,
                'color': self._get_machine_color(machine.status)
            })

        return {
            'type': 'schedule',
            'timestamp': payload.timestamp,
            'plant_id': payload.plant_id,
            'timeline': {
                'start': timeline_start.isoformat() + 'Z',
                'end': timeline_end.isoformat() + 'Z',
                'now': now.isoformat() + 'Z'
            },
            'tracks': tracks,
            'items': gantt_items,
            'pending_jobs': [asdict(j) for j in payload.pending_jobs],
            'actions': {
                'optimize': payload.optimization_available,
                'add_job': True,
                'reschedule': True
            }
        }

    def _get_status_color(self, status: str) -> str:
        """Get color for job status."""
        colors = {
            'pending': '#808080',     # Gray
            'running': '#4CAF50',     # Green
            'completed': '#2196F3',   # Blue
            'paused': '#FFC107',      # Yellow
            'error': '#F44336',       # Red
        }
        return colors.get(status, '#808080')

    def _get_machine_color(self, status: str) -> str:
        """Get color for machine status."""
        colors = {
            'online': '#4CAF50',      # Green
            'offline': '#9E9E9E',     # Gray
            'maintenance': '#FF9800', # Orange
            'error': '#F44336',       # Red
        }
        return colors.get(status, '#9E9E9E')

    def destroy_node(self):
        """Clean up on shutdown."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        super().destroy_node()


# =============================================================================
# Main
# =============================================================================

def main(args=None):
    rclpy.init(args=args)

    node = UnitySchedulerBridge()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
