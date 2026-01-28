#!/usr/bin/env python3
"""
LEGO MCP Micro-ROS Agent Launcher

Manages micro-ROS agent processes for ESP32-based Alvik AGVs.
Supports multiple transport modes:
- Serial (USB connection)
- WiFi UDP
- WiFi TCP

LEGO MCP Manufacturing System v7.0
"""

import json
import subprocess
import time
import os
import signal
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup

from std_msgs.msg import String
from std_srvs.srv import Trigger


class TransportMode(Enum):
    """Micro-ROS transport modes."""
    SERIAL = "serial"
    UDP = "udp"
    TCP = "tcp"


@dataclass
class AgentConfig:
    """Configuration for a micro-ROS agent."""
    agent_id: str
    transport: TransportMode
    # Serial config
    serial_port: Optional[str] = None
    baud_rate: int = 115200
    # Network config
    host: Optional[str] = None
    port: int = 8888
    # Process management
    process: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    started_at: Optional[float] = None


class MicroROSAgentLauncher(Node):
    """
    Manages micro-ROS agent processes for connecting ESP32 devices.

    Each Alvik AGV connects via WiFi UDP to a micro-ROS agent,
    which bridges messages to the ROS2 network.
    """

    def __init__(self):
        super().__init__('microros_agent_launcher')

        # Parameters
        self.declare_parameter('default_transport', 'udp')
        self.declare_parameter('udp_port_base', 8888)
        self.declare_parameter('serial_baud_rate', 115200)
        self.declare_parameter('agent_executable', 'micro_ros_agent')

        self.default_transport = TransportMode(
            self.get_parameter('default_transport').value
        )
        self.udp_port_base = self.get_parameter('udp_port_base').value
        self.baud_rate = self.get_parameter('serial_baud_rate').value
        self.agent_executable = self.get_parameter('agent_executable').value

        # Active agents
        self.agents: Dict[str, AgentConfig] = {}
        self.port_counter = 0

        self.cb_group = ReentrantCallbackGroup()

        # Publishers
        self.status_pub = self.create_publisher(
            String, '/microros/agent_status', 10
        )

        # Subscribers
        self.create_subscription(
            String, '/microros/launch_agent',
            self._on_launch_request, 10,
            callback_group=self.cb_group
        )
        self.create_subscription(
            String, '/microros/stop_agent',
            self._on_stop_request, 10,
            callback_group=self.cb_group
        )

        # Services
        self.create_service(
            Trigger, '/microros/list_agents',
            self._srv_list_agents, callback_group=self.cb_group
        )
        self.create_service(
            Trigger, '/microros/stop_all',
            self._srv_stop_all, callback_group=self.cb_group
        )

        # Timer to monitor agents
        self.monitor_timer = self.create_timer(
            5.0, self._monitor_agents, callback_group=self.cb_group
        )

        # Timer to publish status
        self.status_timer = self.create_timer(
            1.0, self._publish_status, callback_group=self.cb_group
        )

        self.get_logger().info('Micro-ROS Agent Launcher initialized')

    def launch_agent_udp(self, agent_id: str, port: int = None) -> bool:
        """Launch a micro-ROS agent with UDP transport."""
        if agent_id in self.agents:
            self.get_logger().warn(f'Agent {agent_id} already running')
            return False

        if port is None:
            port = self.udp_port_base + self.port_counter
            self.port_counter += 1

        config = AgentConfig(
            agent_id=agent_id,
            transport=TransportMode.UDP,
            port=port,
        )

        return self._start_agent(config)

    def launch_agent_serial(self, agent_id: str, serial_port: str) -> bool:
        """Launch a micro-ROS agent with serial transport."""
        if agent_id in self.agents:
            self.get_logger().warn(f'Agent {agent_id} already running')
            return False

        config = AgentConfig(
            agent_id=agent_id,
            transport=TransportMode.SERIAL,
            serial_port=serial_port,
            baud_rate=self.baud_rate,
        )

        return self._start_agent(config)

    def _start_agent(self, config: AgentConfig) -> bool:
        """Start a micro-ROS agent process."""
        try:
            # Build command based on transport
            if config.transport == TransportMode.UDP:
                cmd = [
                    self.agent_executable,
                    'udp4',
                    '--port', str(config.port),
                ]
            elif config.transport == TransportMode.SERIAL:
                cmd = [
                    self.agent_executable,
                    'serial',
                    '--dev', config.serial_port,
                    '-b', str(config.baud_rate),
                ]
            elif config.transport == TransportMode.TCP:
                cmd = [
                    self.agent_executable,
                    'tcp4',
                    '--port', str(config.port),
                ]
            else:
                self.get_logger().error(f'Unknown transport: {config.transport}')
                return False

            # Add verbose flag for debugging
            cmd.append('-v6')

            # Start process
            self.get_logger().info(f'Starting agent: {" ".join(cmd)}')

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,  # Create new process group
            )

            config.process = process
            config.pid = process.pid
            config.started_at = time.time()

            self.agents[config.agent_id] = config

            self.get_logger().info(
                f'Launched agent {config.agent_id} (PID: {config.pid}, '
                f'transport: {config.transport.value})'
            )

            return True

        except FileNotFoundError:
            self.get_logger().error(
                f'micro_ros_agent not found. Install with: '
                f'sudo apt install ros-$ROS_DISTRO-micro-ros-agent'
            )
            return False
        except Exception as e:
            self.get_logger().error(f'Failed to start agent: {e}')
            return False

    def stop_agent(self, agent_id: str) -> bool:
        """Stop a micro-ROS agent."""
        if agent_id not in self.agents:
            return False

        config = self.agents[agent_id]

        if config.process:
            try:
                # Send SIGTERM to process group
                os.killpg(os.getpgid(config.pid), signal.SIGTERM)
                config.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if needed
                os.killpg(os.getpgid(config.pid), signal.SIGKILL)
            except Exception as e:
                self.get_logger().error(f'Error stopping agent: {e}')

        del self.agents[agent_id]
        self.get_logger().info(f'Stopped agent {agent_id}')
        return True

    def stop_all_agents(self):
        """Stop all running agents."""
        for agent_id in list(self.agents.keys()):
            self.stop_agent(agent_id)

    def _on_launch_request(self, msg: String):
        """Handle agent launch request."""
        try:
            data = json.loads(msg.data)
            agent_id = data.get('agent_id')
            transport = TransportMode(data.get('transport', 'udp'))

            if transport == TransportMode.UDP:
                self.launch_agent_udp(agent_id, data.get('port'))
            elif transport == TransportMode.SERIAL:
                self.launch_agent_serial(agent_id, data.get('serial_port'))

        except (json.JSONDecodeError, ValueError) as e:
            self.get_logger().error(f'Invalid launch request: {e}')

    def _on_stop_request(self, msg: String):
        """Handle agent stop request."""
        try:
            data = json.loads(msg.data)
            agent_id = data.get('agent_id')
            if agent_id:
                self.stop_agent(agent_id)
        except json.JSONDecodeError:
            pass

    def _monitor_agents(self):
        """Monitor running agents and restart if needed."""
        for agent_id, config in list(self.agents.items()):
            if config.process:
                poll = config.process.poll()
                if poll is not None:
                    # Process has terminated
                    self.get_logger().warn(
                        f'Agent {agent_id} terminated (exit code: {poll})'
                    )
                    # Remove from agents
                    del self.agents[agent_id]

    def _publish_status(self):
        """Publish agent status."""
        status = {
            'timestamp': time.time(),
            'agent_count': len(self.agents),
            'agents': {
                agent_id: {
                    'transport': config.transport.value,
                    'port': config.port,
                    'serial_port': config.serial_port,
                    'pid': config.pid,
                    'uptime_seconds': time.time() - config.started_at if config.started_at else 0,
                }
                for agent_id, config in self.agents.items()
            },
        }

        msg = String()
        msg.data = json.dumps(status)
        self.status_pub.publish(msg)

    def _srv_list_agents(self, request, response):
        """Service to list running agents."""
        agent_list = [
            {
                'agent_id': agent_id,
                'transport': config.transport.value,
                'pid': config.pid,
            }
            for agent_id, config in self.agents.items()
        ]
        response.success = True
        response.message = json.dumps(agent_list)
        return response

    def _srv_stop_all(self, request, response):
        """Service to stop all agents."""
        count = len(self.agents)
        self.stop_all_agents()
        response.success = True
        response.message = f'Stopped {count} agents'
        return response

    def destroy_node(self):
        """Clean up when shutting down."""
        self.stop_all_agents()
        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)
    node = MicroROSAgentLauncher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
