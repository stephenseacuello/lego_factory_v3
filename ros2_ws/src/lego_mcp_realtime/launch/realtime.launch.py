#!/usr/bin/env python3
"""
LEGO MCP Real-Time Launch Configuration

Launches the real-time node with proper configuration for
deterministic manufacturing execution.

Reference: ROS2 Launch, IEC 61784-3
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate launch description for real-time node."""

    # Package directory
    pkg_share = FindPackageShare('lego_mcp_realtime')

    # Launch arguments
    use_sim = LaunchConfiguration('use_sim', default='false')
    log_level = LaunchConfiguration('log_level', default='info')
    rt_priority = LaunchConfiguration('rt_priority', default='80')
    enable_ptp = LaunchConfiguration('enable_ptp', default='true')
    ptp_interface = LaunchConfiguration('ptp_interface', default='eth0')

    # Config file path
    config_file = PathJoinSubstitution([
        pkg_share, 'config', 'realtime_params.yaml'
    ])

    return LaunchDescription([
        # Declare launch arguments
        DeclareLaunchArgument(
            'use_sim',
            default_value='false',
            description='Use simulation time'
        ),
        DeclareLaunchArgument(
            'log_level',
            default_value='info',
            description='Logging level (debug, info, warn, error)'
        ),
        DeclareLaunchArgument(
            'rt_priority',
            default_value='80',
            description='Real-time thread priority (1-99)'
        ),
        DeclareLaunchArgument(
            'enable_ptp',
            default_value='true',
            description='Enable IEEE 1588 PTP clock sync'
        ),
        DeclareLaunchArgument(
            'ptp_interface',
            default_value='eth0',
            description='Network interface for PTP'
        ),

        # Environment for RT
        SetEnvironmentVariable(
            'RMW_IMPLEMENTATION',
            'rmw_cyclonedds_cpp'
        ),
        SetEnvironmentVariable(
            'CYCLONEDDS_URI',
            PathJoinSubstitution([pkg_share, 'config', 'cyclonedds.xml'])
        ),

        # Real-time node
        Node(
            package='lego_mcp_realtime',
            executable='realtime_node',
            name='lego_mcp_realtime',
            namespace='lego_mcp',
            output='screen',
            parameters=[
                config_file,
                {
                    'use_sim_time': use_sim,
                    'realtime.rt_priority': rt_priority,
                    'ptp.enabled': enable_ptp,
                    'ptp.interface': ptp_interface,
                }
            ],
            arguments=['--ros-args', '--log-level', log_level],
            # Run with real-time capabilities
            # Requires: sudo setcap cap_sys_nice+ep /path/to/realtime_node
            prefix='',  # Could use 'chrt -f 80' if setcap not available
            respawn=True,
            respawn_delay=2.0,
        ),

        # WCET Monitor node (separate for isolation)
        Node(
            package='lego_mcp_realtime',
            executable='wcet_monitor_node',
            name='wcet_monitor',
            namespace='lego_mcp',
            output='screen',
            parameters=[config_file],
            arguments=['--ros-args', '--log-level', log_level],
        ),
    ])
