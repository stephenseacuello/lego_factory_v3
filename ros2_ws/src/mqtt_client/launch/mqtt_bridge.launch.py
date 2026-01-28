"""Launch file for MQTT-ROS 2 bridge."""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description for mqtt_bridge."""

    # Get package share directory
    pkg_share = get_package_share_directory('mqtt_client')

    # Declare launch arguments
    broker_host_arg = DeclareLaunchArgument(
        'broker_host',
        default_value='localhost',
        description='MQTT broker hostname'
    )

    broker_port_arg = DeclareLaunchArgument(
        'broker_port',
        default_value='1883',
        description='MQTT broker port'
    )

    client_id_arg = DeclareLaunchArgument(
        'client_id',
        default_value='ros2_mqtt_bridge',
        description='MQTT client ID'
    )

    # MQTT Bridge Node
    mqtt_bridge_node = Node(
        package='mqtt_client',
        executable='mqtt_bridge',
        name='mqtt_bridge',
        output='screen',
        parameters=[{
            'broker_host': LaunchConfiguration('broker_host'),
            'broker_port': LaunchConfiguration('broker_port'),
            'client_id': LaunchConfiguration('client_id'),
        }],
        remappings=[
            # Add any topic remappings here
        ]
    )

    return LaunchDescription([
        broker_host_arg,
        broker_port_arg,
        client_id_arg,
        mqtt_bridge_node,
    ])
