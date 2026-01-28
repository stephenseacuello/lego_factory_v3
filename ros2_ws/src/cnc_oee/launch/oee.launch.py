"""Launch file for OEE aggregation system."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    # Get package share directory
    pkg_share = get_package_share_directory('cnc_oee')
    config_file = os.path.join(pkg_share, 'config', 'oee_params.yaml')

    # Launch arguments
    enable_job_sim_arg = DeclareLaunchArgument(
        'enable_job_simulator',
        default_value='true',
        description='Enable job event simulator for testing'
    )

    prometheus_port_arg = DeclareLaunchArgument(
        'prometheus_port',
        default_value='9100',
        description='Port for Prometheus metrics endpoint'
    )

    # OEE Aggregator node
    oee_aggregator_node = Node(
        package='cnc_oee',
        executable='oee_aggregator',
        name='oee_aggregator',
        parameters=[
            config_file,
            {'prometheus_port': LaunchConfiguration('prometheus_port')}
        ],
        output='screen'
    )

    # Job Simulator node (optional - for testing)
    job_simulator_node = Node(
        package='cnc_oee',
        executable='job_simulator',
        name='job_simulator',
        parameters=[config_file],
        output='screen',
        condition=IfCondition(
            LaunchConfiguration('enable_job_simulator')
        )
    )

    return LaunchDescription([
        enable_job_sim_arg,
        prometheus_port_arg,
        oee_aggregator_node,
        job_simulator_node,
    ])
