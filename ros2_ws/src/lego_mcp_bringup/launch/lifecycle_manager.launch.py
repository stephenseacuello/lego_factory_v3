#!/usr/bin/env python3
"""
ROS2 Lifecycle Manager Launch File

Manages lifecycle state transitions for all lifecycle-managed nodes.
Provides coordinated startup, shutdown, and recovery operations.

Industry 4.0/5.0 Architecture - ISA-95 Compliant

LEGO MCP Manufacturing System v7.0

Usage:
    ros2 launch lego_mcp_bringup lifecycle_manager.launch.py

    # With specific nodes
    ros2 launch lego_mcp_bringup lifecycle_manager.launch.py \
        managed_nodes:="['safety_node', 'grbl_node']"

    # With auto-start disabled
    ros2 launch lego_mcp_bringup lifecycle_manager.launch.py \
        autostart:=false
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    EmitEvent,
    RegisterEventHandler,
    LogInfo,
    TimerAction,
    OpaqueFunction,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessStart, OnProcessExit
from launch.events import Shutdown
from launch.substitutions import (
    LaunchConfiguration,
    PythonExpression,
)
from launch_ros.actions import Node, LifecycleNode
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from lifecycle_msgs.msg import Transition


def generate_launch_description():
    """Generate the lifecycle manager launch description."""

    # Launch arguments
    declare_autostart_arg = DeclareLaunchArgument(
        'autostart',
        default_value='true',
        description='Automatically transition nodes to active state'
    )

    declare_bond_timeout_arg = DeclareLaunchArgument(
        'bond_timeout',
        default_value='10.0',
        description='Bond timeout for lifecycle manager'
    )

    declare_attempt_respawn_arg = DeclareLaunchArgument(
        'attempt_respawn_reconnection',
        default_value='true',
        description='Attempt to reconnect after node failure'
    )

    declare_managed_nodes_arg = DeclareLaunchArgument(
        'managed_nodes',
        default_value="['safety_node', 'grbl_node', 'formlabs_node', 'bambu_node', 'orchestrator']",
        description='List of lifecycle nodes to manage'
    )

    declare_startup_timeout_arg = DeclareLaunchArgument(
        'startup_timeout',
        default_value='30.0',
        description='Timeout for node startup transitions'
    )

    declare_shutdown_timeout_arg = DeclareLaunchArgument(
        'shutdown_timeout',
        default_value='10.0',
        description='Timeout for node shutdown transitions'
    )

    declare_use_sim_arg = DeclareLaunchArgument(
        'use_sim',
        default_value='false',
        description='Use simulation mode'
    )

    # Lifecycle Manager Node
    # This node manages the lifecycle transitions of all managed nodes
    lifecycle_manager_node = Node(
        package='lego_mcp_orchestrator',
        executable='lifecycle_manager',
        name='lifecycle_manager',
        namespace='lego_mcp',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'autostart': LaunchConfiguration('autostart'),
            'bond_timeout': LaunchConfiguration('bond_timeout'),
            'attempt_respawn_reconnection': LaunchConfiguration('attempt_respawn_reconnection'),
            'node_names': LaunchConfiguration('managed_nodes'),
            'startup_timeout': LaunchConfiguration('startup_timeout'),
            'shutdown_timeout': LaunchConfiguration('shutdown_timeout'),
            # ISA-95 compliant transition order
            'transition_order': [
                # Level 1 - Control (Safety first)
                'safety_node',
                # Level 0 - Field (Equipment)
                'grbl_node',
                'formlabs_node',
                'bambu_node',
                # Level 2 - Supervisory
                'orchestrator',
            ],
            # Transition delays between nodes (seconds)
            'transition_delays': {
                'safety_node': 0.0,      # Immediate
                'grbl_node': 2.0,        # After safety
                'formlabs_node': 2.0,    # Parallel with grbl
                'bambu_node': 2.0,       # Parallel with grbl
                'orchestrator': 5.0,     # After equipment
            },
        }],
    )

    # Lifecycle State Monitor
    # Monitors state transitions and publishes diagnostics
    lifecycle_monitor_node = Node(
        package='lego_mcp_orchestrator',
        executable='lifecycle_monitor',
        name='lifecycle_monitor',
        namespace='lego_mcp',
        output='screen',
        parameters=[{
            'monitored_nodes': LaunchConfiguration('managed_nodes'),
            'publish_rate': 1.0,  # Hz
            'diagnostics_topic': '/lego_mcp/diagnostics/lifecycle',
        }],
    )

    # Service Bridge Node
    # Provides service interface for external lifecycle control
    lifecycle_service_bridge = Node(
        package='lego_mcp_orchestrator',
        executable='lifecycle_service_bridge',
        name='lifecycle_service_bridge',
        namespace='lego_mcp',
        output='screen',
        parameters=[{
            'managed_nodes': LaunchConfiguration('managed_nodes'),
            # Service names
            'configure_all_service': '/lego_mcp/lifecycle/configure_all',
            'activate_all_service': '/lego_mcp/lifecycle/activate_all',
            'deactivate_all_service': '/lego_mcp/lifecycle/deactivate_all',
            'cleanup_all_service': '/lego_mcp/lifecycle/cleanup_all',
            'shutdown_all_service': '/lego_mcp/lifecycle/shutdown_all',
            # Per-node services
            'configure_node_service': '/lego_mcp/lifecycle/configure_node',
            'activate_node_service': '/lego_mcp/lifecycle/activate_node',
            'deactivate_node_service': '/lego_mcp/lifecycle/deactivate_node',
            'get_state_service': '/lego_mcp/lifecycle/get_state',
        }],
    )

    return LaunchDescription([
        # Launch arguments
        declare_autostart_arg,
        declare_bond_timeout_arg,
        declare_attempt_respawn_arg,
        declare_managed_nodes_arg,
        declare_startup_timeout_arg,
        declare_shutdown_timeout_arg,
        declare_use_sim_arg,

        # Startup message
        LogInfo(msg='=========================================='),
        LogInfo(msg='  LEGO MCP Lifecycle Manager Starting'),
        LogInfo(msg='  ROS2 Lifecycle State Management'),
        LogInfo(msg='=========================================='),

        # Core lifecycle manager (immediate start)
        lifecycle_manager_node,

        # Lifecycle monitor (start after 2s)
        TimerAction(
            period=2.0,
            actions=[
                LogInfo(msg='[Lifecycle] Starting lifecycle monitor...'),
                lifecycle_monitor_node,
            ]
        ),

        # Service bridge (start after 3s)
        TimerAction(
            period=3.0,
            actions=[
                LogInfo(msg='[Lifecycle] Starting service bridge...'),
                lifecycle_service_bridge,
            ]
        ),

        # Ready message
        TimerAction(
            period=5.0,
            actions=[
                LogInfo(msg='=========================================='),
                LogInfo(msg='  Lifecycle Manager Ready'),
                LogInfo(msg='  Services available:'),
                LogInfo(msg='    /lego_mcp/lifecycle/configure_all'),
                LogInfo(msg='    /lego_mcp/lifecycle/activate_all'),
                LogInfo(msg='    /lego_mcp/lifecycle/deactivate_all'),
                LogInfo(msg='=========================================='),
            ]
        ),
    ])


def configure_node(node_name: str) -> ChangeState:
    """Create a ChangeState event to configure a node."""
    return ChangeState(
        lifecycle_node_matcher=lambda n: n.node_name == node_name,
        transition_id=Transition.TRANSITION_CONFIGURE,
    )


def activate_node(node_name: str) -> ChangeState:
    """Create a ChangeState event to activate a node."""
    return ChangeState(
        lifecycle_node_matcher=lambda n: n.node_name == node_name,
        transition_id=Transition.TRANSITION_ACTIVATE,
    )


def deactivate_node(node_name: str) -> ChangeState:
    """Create a ChangeState event to deactivate a node."""
    return ChangeState(
        lifecycle_node_matcher=lambda n: n.node_name == node_name,
        transition_id=Transition.TRANSITION_DEACTIVATE,
    )


def cleanup_node(node_name: str) -> ChangeState:
    """Create a ChangeState event to cleanup a node."""
    return ChangeState(
        lifecycle_node_matcher=lambda n: n.node_name == node_name,
        transition_id=Transition.TRANSITION_CLEANUP,
    )
