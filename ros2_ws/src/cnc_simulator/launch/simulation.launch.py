"""
Simulation Launch File for CNC Factory.

Launches all simulation nodes for testing without physical hardware:
- TinyG Simulator
- GRBL Simulator
- Sensor Simulator
- Sensor Bridge (IMU → SensorReading)
- MQTT Bridge (optional)

Usage:
    ros2 launch cnc_simulator simulation.launch.py
    ros2 launch cnc_simulator simulation.launch.py with_mqtt:=true
"""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description for CNC simulation stack."""

    # Launch arguments
    with_mqtt_arg = DeclareLaunchArgument(
        'with_mqtt',
        default_value='false',
        description='Include MQTT bridge (requires running broker)'
    )

    tinyg_machine_id_arg = DeclareLaunchArgument(
        'tinyg_machine_id',
        default_value='tinyg_sim_001',
        description='TinyG simulator machine ID'
    )

    grbl_machine_id_arg = DeclareLaunchArgument(
        'grbl_machine_id',
        default_value='grbl_sim_001',
        description='GRBL simulator machine ID'
    )

    mqtt_broker_arg = DeclareLaunchArgument(
        'mqtt_broker',
        default_value='localhost',
        description='MQTT broker hostname'
    )

    # ==========================================================================
    # TinyG Simulator Node
    # ==========================================================================
    tinyg_simulator_node = Node(
        package='tinyg_ros',
        executable='tinyg_simulator',
        name='tinyg_simulator',
        output='screen',
        parameters=[{
            'machine_id': LaunchConfiguration('tinyg_machine_id'),
            'publish_rate': 10.0,
        }],
        remappings=[
            # Default topics are fine
        ]
    )

    # ==========================================================================
    # GRBL Simulator Node
    # ==========================================================================
    grbl_simulator_node = Node(
        package='grbl_ros',
        executable='grbl_simulator',
        name='grbl_simulator',
        output='screen',
        parameters=[{
            'machine_id': LaunchConfiguration('grbl_machine_id'),
            'publish_rate': 10.0,
        }],
        remappings=[
            # Default topics are fine
        ]
    )

    # ==========================================================================
    # Sensor Simulator Node
    # ==========================================================================
    sensor_simulator_node = Node(
        package='cnc_simulator',
        executable='sensor_simulator',
        name='sensor_simulator',
        output='screen',
        parameters=[{
            'publish_rate': 50.0,  # 50 Hz like micro-ROS ESP32
            'sensor_id': 'sim_imu_001',
        }]
    )

    # ==========================================================================
    # Sensor Bridge Node (converts generic sensor_msgs to cnc_interfaces)
    # ==========================================================================
    sensor_bridge_node = Node(
        package='cnc_simulator',
        executable='sensor_bridge',
        name='sensor_bridge',
        output='screen',
        parameters=[{
            'imu_topic': '/sensors/imu',
            'temp_topic': '/sensors/temperature',
            'output_topic': '/sensors/raw',
        }]
    )

    # ==========================================================================
    # MQTT Bridge Node (optional)
    # ==========================================================================
    mqtt_bridge_group = GroupAction(
        condition=IfCondition(LaunchConfiguration('with_mqtt')),
        actions=[
            Node(
                package='mqtt_client',
                executable='mqtt_bridge',
                name='mqtt_bridge',
                output='screen',
                parameters=[{
                    'broker_host': LaunchConfiguration('mqtt_broker'),
                    'broker_port': 1883,
                    'client_id': 'ros2_sim_bridge',
                }]
            )
        ]
    )

    return LaunchDescription([
        # Arguments
        with_mqtt_arg,
        tinyg_machine_id_arg,
        grbl_machine_id_arg,
        mqtt_broker_arg,

        # Simulator Nodes
        tinyg_simulator_node,
        grbl_simulator_node,
        sensor_simulator_node,
        sensor_bridge_node,

        # Optional MQTT Bridge
        mqtt_bridge_group,
    ])
