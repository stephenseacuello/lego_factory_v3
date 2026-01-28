"""
Launch file for Fleet Manager.

Launches fleet management node with configurable parameters.

Usage:
    ros2 launch cnc_fleet fleet.launch.py
    ros2 launch cnc_fleet fleet.launch.py heartbeat_timeout:=15.0
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for fleet management."""

    # Get package share directory
    pkg_share = get_package_share_directory('cnc_fleet')
    config_file = os.path.join(pkg_share, 'config', 'fleet_capabilities.yaml')

    # Launch arguments
    heartbeat_timeout_arg = DeclareLaunchArgument(
        'heartbeat_timeout',
        default_value='10.0',
        description='Seconds before machine considered offline'
    )

    default_strategy_arg = DeclareLaunchArgument(
        'default_strategy',
        default_value='1',
        description='Default dispatch strategy (0=RR, 1=LEAST_LOADED, 2=HIGHEST_OEE, 3=SHORTEST_Q, 4=MANUAL)'
    )

    # Fleet Manager Node
    fleet_manager_node = Node(
        package='cnc_fleet',
        executable='fleet_manager',
        name='fleet_manager',
        parameters=[
            config_file,
            {
                'heartbeat_timeout': LaunchConfiguration('heartbeat_timeout'),
                'default_strategy': LaunchConfiguration('default_strategy'),
            }
        ],
        output='screen',
        emulate_tty=True,
    )

    return LaunchDescription([
        heartbeat_timeout_arg,
        default_strategy_arg,
        fleet_manager_node,
    ])
