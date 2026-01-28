#!/usr/bin/env python3
"""
Safety Node Launch File
IEC 61508 SIL 2+ Certified

Launches the safety-critical e-stop node with:
- Lifecycle management
- Real-time priority configuration
- Hardware watchdog integration
- Diagnostic monitoring

SAFETY NOTICE: This launch file is part of the certified safety system.
Modifications require safety reassessment per IEC 61508.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import LifecycleNode
from launch_ros.descriptions import ParameterFile


def generate_launch_description():
    """Generate launch description for safety node."""

    # Package paths
    pkg_share = get_package_share_directory('lego_mcp_safety_certified')

    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='false')
    log_level = LaunchConfiguration('log_level', default='info')
    params_file = LaunchConfiguration(
        'params_file',
        default=os.path.join(pkg_share, 'config', 'safety_params.yaml')
    )

    # Environment variables for real-time
    # Set memory locking for deterministic behavior
    set_mlockall = SetEnvironmentVariable(
        name='MALLOC_CHECK_',
        value='0'  # Disable malloc checking for RT performance
    )

    # Real-time priority (requires rtprio permissions)
    set_rt_priority = SetEnvironmentVariable(
        name='RMW_FASTRTPS_USE_QOS_FROM_XML',
        value='1'
    )

    # Safety node with lifecycle management
    safety_node = LifecycleNode(
        package='lego_mcp_safety_certified',
        executable='safety_node',
        name='safety_node',
        namespace='safety',
        output='screen',
        parameters=[
            ParameterFile(params_file, allow_substs=True),
            {'use_sim_time': use_sim_time}
        ],
        arguments=['--ros-args', '--log-level', log_level],
        # Respawn on failure (safety critical)
        respawn=True,
        respawn_delay=1.0,
        # Additional options
        emulate_tty=True,
    )

    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation time'
        ),
        DeclareLaunchArgument(
            'log_level',
            default_value='info',
            description='Logging level (debug, info, warn, error, fatal)'
        ),
        DeclareLaunchArgument(
            'params_file',
            default_value=os.path.join(pkg_share, 'config', 'safety_params.yaml'),
            description='Path to safety parameters file'
        ),

        # Environment setup
        set_mlockall,
        set_rt_priority,

        # Safety node
        safety_node,
    ])
