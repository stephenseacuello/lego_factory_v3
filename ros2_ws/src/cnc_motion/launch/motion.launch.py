#!/usr/bin/env python3
"""Launch file for motion planning nodes"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_dir = get_package_share_directory('cnc_motion')
    config_file = os.path.join(pkg_dir, 'config', 'motion_params.yaml')

    collision_node = Node(
        package='cnc_motion',
        executable='collision_detector',
        name='collision_detector',
        parameters=[config_file],
        output='screen'
    )

    path_planner_node = Node(
        package='cnc_motion',
        executable='path_planner',
        name='path_planner',
        parameters=[config_file],
        output='screen'
    )

    validator_node = Node(
        package='cnc_motion',
        executable='gcode_validator',
        name='gcode_validator',
        parameters=[config_file],
        output='screen'
    )

    return LaunchDescription([
        collision_node,
        path_planner_node,
        validator_node,
    ])
