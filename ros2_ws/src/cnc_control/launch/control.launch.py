"""
CNC Control Launch File.

Launches machine control services and action servers:
- Machine Service (Home, Jog, E-Stop)
- G-code Action Server (long-running execution)

Usage:
    ros2 launch cnc_control control.launch.py
    ros2 launch cnc_control control.launch.py machine_id:=grbl_001
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for CNC control nodes."""

    # Launch arguments
    machine_id_arg = DeclareLaunchArgument(
        'machine_id',
        default_value='tinyg_001',
        description='Machine identifier for control services'
    )

    enable_recording_arg = DeclareLaunchArgument(
        'enable_recording',
        default_value='false',
        description='Enable rosbag recording during G-code execution'
    )

    bag_output_dir_arg = DeclareLaunchArgument(
        'bag_output_dir',
        default_value='/ros2_ws/bags',
        description='Directory for rosbag recordings'
    )

    # Machine Service Node (Home, Jog, E-Stop)
    machine_service_node = Node(
        package='cnc_control',
        executable='machine_service',
        name='machine_service',
        output='screen',
        parameters=[{
            'machine_id': LaunchConfiguration('machine_id'),
        }]
    )

    # G-code Action Server
    gcode_action_server_node = Node(
        package='cnc_control',
        executable='gcode_action_server',
        name='gcode_action_server',
        output='screen',
        parameters=[{
            'machine_id': LaunchConfiguration('machine_id'),
            'enable_recording': LaunchConfiguration('enable_recording'),
            'bag_output_dir': LaunchConfiguration('bag_output_dir'),
        }]
    )

    return LaunchDescription([
        # Arguments
        machine_id_arg,
        enable_recording_arg,
        bag_output_dir_arg,

        # Nodes
        machine_service_node,
        gcode_action_server_node,
    ])
