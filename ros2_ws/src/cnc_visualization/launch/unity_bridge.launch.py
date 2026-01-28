"""
Unity Bridge Launch File
========================
Launches the Unity state publisher for digital twin visualization.

Usage:
    ros2 launch cnc_visualization unity_bridge.launch.py
    ros2 launch cnc_visualization unity_bridge.launch.py machine_id:=cnc-2 publish_rate_hz:=30

Author: Flask CNC SCADA System
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Declare launch arguments
    machine_id_arg = DeclareLaunchArgument(
        'machine_id',
        default_value='cnc-1',
        description='Machine identifier for Unity state publishing'
    )

    publish_rate_arg = DeclareLaunchArgument(
        'publish_rate_hz',
        default_value='60.0',
        description='State publishing rate in Hz (default: 60 for smooth animation)'
    )

    mqtt_enabled_arg = DeclareLaunchArgument(
        'mqtt_enabled',
        default_value='true',
        description='Enable MQTT publishing to Flask SCADA'
    )

    mqtt_host_arg = DeclareLaunchArgument(
        'mqtt_host',
        default_value='localhost',
        description='MQTT broker hostname'
    )

    mqtt_port_arg = DeclareLaunchArgument(
        'mqtt_port',
        default_value='1883',
        description='MQTT broker port'
    )

    quality_timeout_arg = DeclareLaunchArgument(
        'quality_timeout_s',
        default_value='1.0',
        description='Timeout before quality score degrades (seconds)'
    )

    # Unity State Publisher Node
    unity_state_publisher = Node(
        package='cnc_visualization',
        executable='unity_state_publisher',
        name='unity_state_publisher',
        output='screen',
        parameters=[{
            'machine_id': LaunchConfiguration('machine_id'),
            'publish_rate_hz': LaunchConfiguration('publish_rate_hz'),
            'mqtt_enabled': LaunchConfiguration('mqtt_enabled'),
            'mqtt_host': LaunchConfiguration('mqtt_host'),
            'mqtt_port': LaunchConfiguration('mqtt_port'),
            'quality_timeout_s': LaunchConfiguration('quality_timeout_s'),
        }],
        remappings=[
            # Remap topics if needed
            # ('/machine/status', '/cnc_1/status'),
        ]
    )

    return LaunchDescription([
        # Launch arguments
        machine_id_arg,
        publish_rate_arg,
        mqtt_enabled_arg,
        mqtt_host_arg,
        mqtt_port_arg,
        quality_timeout_arg,

        # Nodes
        unity_state_publisher,
    ])
