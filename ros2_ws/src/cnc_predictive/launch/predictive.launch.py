#!/usr/bin/env python3
"""Launch file for predictive maintenance nodes"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Get package directory
    pkg_dir = get_package_share_directory('cnc_predictive')
    config_file = os.path.join(pkg_dir, 'config', 'predictive_params.yaml')

    # Launch arguments
    enable_ml_arg = DeclareLaunchArgument(
        'enable_ml',
        default_value='true',
        description='Enable ML models'
    )

    # Nodes
    predictive_node = Node(
        package='cnc_predictive',
        executable='predictive_node',
        name='predictive_maintenance_node',
        parameters=[config_file],
        output='screen'
    )

    tool_wear_node = Node(
        package='cnc_predictive',
        executable='tool_wear_monitor',
        name='tool_wear_monitor',
        parameters=[config_file],
        output='screen'
    )

    anomaly_node = Node(
        package='cnc_predictive',
        executable='anomaly_detector',
        name='anomaly_detector',
        parameters=[config_file],
        output='screen'
    )

    trainer_node = Node(
        package='cnc_predictive',
        executable='model_trainer',
        name='model_trainer',
        parameters=[config_file],
        output='screen'
    )

    return LaunchDescription([
        enable_ml_arg,
        predictive_node,
        tool_wear_node,
        anomaly_node,
        trainer_node,
    ])
