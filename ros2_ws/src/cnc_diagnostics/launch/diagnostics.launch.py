"""
CNC Diagnostics Launch File.

Launches health monitoring and diagnostics nodes:
- Diagnostics Aggregator (main node)
- Sensor Monitor (optional)
- Machine Monitor (optional)

Usage:
    ros2 launch cnc_diagnostics diagnostics.launch.py
    ros2 launch cnc_diagnostics diagnostics.launch.py with_sensor_monitor:=true
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():
    """Generate launch description for diagnostics nodes."""

    # Get package share directory for config files
    pkg_share = get_package_share_directory('cnc_diagnostics')
    config_file = os.path.join(pkg_share, 'config', 'diagnostics_params.yaml')

    # Launch arguments
    with_sensor_monitor_arg = DeclareLaunchArgument(
        'with_sensor_monitor',
        default_value='true',
        description='Include sensor monitoring node'
    )

    with_machine_monitor_arg = DeclareLaunchArgument(
        'with_machine_monitor',
        default_value='true',
        description='Include machine monitoring node'
    )

    # Main diagnostics aggregator node
    diagnostics_node = Node(
        package='cnc_diagnostics',
        executable='diagnostics_node',
        name='cnc_diagnostics',
        output='screen',
        parameters=[config_file]
    )

    # Optional sensor monitor
    sensor_monitor_group = GroupAction(
        condition=IfCondition(LaunchConfiguration('with_sensor_monitor')),
        actions=[
            Node(
                package='cnc_diagnostics',
                executable='sensor_monitor',
                name='sensor_monitor',
                output='screen',
                parameters=[config_file]
            )
        ]
    )

    # Optional machine monitor
    machine_monitor_group = GroupAction(
        condition=IfCondition(LaunchConfiguration('with_machine_monitor')),
        actions=[
            Node(
                package='cnc_diagnostics',
                executable='machine_monitor',
                name='machine_monitor',
                output='screen',
                parameters=[config_file]
            )
        ]
    )

    return LaunchDescription([
        # Arguments
        with_sensor_monitor_arg,
        with_machine_monitor_arg,

        # Nodes
        diagnostics_node,
        sensor_monitor_group,
        machine_monitor_group,
    ])
