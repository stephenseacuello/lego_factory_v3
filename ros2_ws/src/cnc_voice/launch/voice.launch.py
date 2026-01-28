"""Voice control launch file."""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    pkg_dir = get_package_share_directory('cnc_voice')

    config_file = LaunchConfiguration('config_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'config_file',
            default_value=os.path.join(pkg_dir, 'config', 'voice_params.yaml'),
            description='Path to voice configuration file'
        ),

        Node(
            package='cnc_voice',
            executable='voice_controller',
            name='voice_controller_node',
            parameters=[config_file],
            output='screen',
            emulate_tty=True,
        ),
    ])
