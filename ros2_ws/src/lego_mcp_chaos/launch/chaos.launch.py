#!/usr/bin/env python3
"""
LEGO MCP Chaos Testing Launch File

Launches chaos engineering nodes:
- Chaos Controller (fault injection, scenario execution)

SAFETY WARNING:
This launch file should ONLY be used in test/staging environments.
Never deploy chaos testing nodes in production without explicit approval.

Industry 4.0/5.0 Architecture - Resilience Testing
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, RegisterEventHandler, LogInfo
from launch.events import matches_action
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression, PathJoinSubstitution
from launch_ros.actions import LifecycleNode
from launch_ros.events.lifecycle import ChangeState
from launch_ros.substitutions import FindPackageShare
from lifecycle_msgs.msg import Transition


def generate_launch_description():
    """Generate launch description for chaos testing nodes."""

    # Declare launch arguments
    config_path_arg = DeclareLaunchArgument(
        'config_path',
        default_value=PathJoinSubstitution([
            FindPackageShare('lego_mcp_chaos'),
            'config',
            'chaos_scenarios.yaml'
        ]),
        description='Path to chaos scenarios config'
    )

    safety_protection_arg = DeclareLaunchArgument(
        'enable_safety_zone_protection',
        default_value='true',
        description='Protect safety zone from fault injection'
    )

    max_faults_arg = DeclareLaunchArgument(
        'max_concurrent_faults',
        default_value='2',
        description='Maximum concurrent fault injections'
    )

    auto_cleanup_arg = DeclareLaunchArgument(
        'auto_cleanup_on_error',
        default_value='true',
        description='Automatically cleanup on errors'
    )

    status_rate_arg = DeclareLaunchArgument(
        'status_rate',
        default_value='1.0',
        description='Status publish rate (Hz)'
    )

    # Safety confirmation argument
    i_understand_arg = DeclareLaunchArgument(
        'i_understand_this_is_for_testing',
        default_value='false',
        description='Explicit confirmation that this is for testing only'
    )

    # Warning message
    warning_message = LogInfo(
        msg='[CHAOS] WARNING: Launching chaos testing infrastructure. '
            'Only use in test environments!'
    )

    # Chaos Controller Node (Lifecycle)
    chaos_controller_node = LifecycleNode(
        package='lego_mcp_chaos',
        executable='chaos_controller_node.py',
        name='chaos_controller',
        namespace='lego_mcp',
        output='screen',
        parameters=[{
            'config_path': LaunchConfiguration('config_path'),
            'enable_safety_zone_protection': LaunchConfiguration('enable_safety_zone_protection'),
            'max_concurrent_faults': LaunchConfiguration('max_concurrent_faults'),
            'auto_cleanup_on_error': LaunchConfiguration('auto_cleanup_on_error'),
            'status_rate': LaunchConfiguration('status_rate'),
        }],
        # Only launch if user explicitly confirms
        condition=IfCondition(LaunchConfiguration('i_understand_this_is_for_testing')),
    )

    # Event handler to configure the node
    configure_chaos_controller = RegisterEventHandler(
        event_handler=EmitEvent(
            event=ChangeState(
                lifecycle_node_matcher=matches_action(chaos_controller_node),
                transition_id=Transition.TRANSITION_CONFIGURE,
            )
        ),
        condition=IfCondition(LaunchConfiguration('i_understand_this_is_for_testing')),
    )

    return LaunchDescription([
        # Arguments
        config_path_arg,
        safety_protection_arg,
        max_faults_arg,
        auto_cleanup_arg,
        status_rate_arg,
        i_understand_arg,

        # Warning
        warning_message,

        # Nodes (conditional on safety flag)
        chaos_controller_node,

        # Lifecycle transitions
        configure_chaos_controller,
    ])
