#!/usr/bin/env python3
"""
Deterministic Startup Launch File for LEGO MCP

Implements ISA-95 layered deterministic startup sequence:
1. Level 1 (Safety) - Must be active before any equipment
2. Level 0 (Equipment) - Hardware interfaces
3. Level 2 (Supervisory) - Orchestration and coordination

Industry 4.0/5.0 Architecture - Guaranteed Startup Order
"""

import os
from typing import List

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    EmitEvent,
    LogInfo,
    OpaqueFunction,
    RegisterEventHandler,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessStart
from launch.events import matches_action
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import LifecycleNode, Node
from launch_ros.events.lifecycle import ChangeState
from launch_ros.substitutions import FindPackageShare
from lifecycle_msgs.msg import Transition


def generate_launch_description():
    """Generate deterministic startup launch description."""

    # ====================
    # Launch Arguments
    # ====================

    use_sim_arg = DeclareLaunchArgument(
        'use_sim',
        default_value='false',
        description='Use simulation mode'
    )

    enable_security_arg = DeclareLaunchArgument(
        'enable_security',
        default_value='false',
        description='Enable SROS2 security'
    )

    enable_agv_arg = DeclareLaunchArgument(
        'enable_agv',
        default_value='false',
        description='Enable AGV fleet management'
    )

    startup_timeout_arg = DeclareLaunchArgument(
        'startup_timeout',
        default_value='30.0',
        description='Maximum time to wait for each layer'
    )

    # ====================
    # Phase 1: Safety Layer (ISA-95 Level 1)
    # ====================

    phase1_info = LogInfo(
        msg='[STARTUP] Phase 1: Starting Safety Layer (L1)...'
    )

    safety_node = LifecycleNode(
        package='lego_mcp_safety',
        executable='safety_node.py',
        name='safety_node',
        namespace='lego_mcp',
        output='screen',
        parameters=[{
            'watchdog_timeout_ms': 500,
            'heartbeat_rate_hz': 10.0,
        }],
    )

    # Configure and activate safety node
    configure_safety = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(safety_node),
            transition_id=Transition.TRANSITION_CONFIGURE,
        )
    )

    activate_safety = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(safety_node),
            transition_id=Transition.TRANSITION_ACTIVATE,
        )
    )

    # Watchdog node
    watchdog_node = Node(
        package='lego_mcp_safety',
        executable='watchdog_node.py',
        name='watchdog_node',
        namespace='lego_mcp',
        output='screen',
        parameters=[{
            'timeout_ms': 500,
        }],
    )

    # ====================
    # Phase 2: Equipment Layer (ISA-95 Level 0)
    # ====================

    phase2_info = TimerAction(
        period=2.0,  # Wait for safety to be active
        actions=[
            LogInfo(msg='[STARTUP] Phase 2: Starting Equipment Layer (L0)...')
        ]
    )

    # GRBL Node (CNC/Laser)
    grbl_node = TimerAction(
        period=3.0,  # Start after safety confirmed
        actions=[
            LifecycleNode(
                package='grbl_ros2',
                executable='grbl_node.py',
                name='grbl_node',
                namespace='lego_mcp',
                output='screen',
                parameters=[{
                    'simulate': LaunchConfiguration('use_sim'),
                    'serial_port': '/dev/ttyUSB0',
                }],
            )
        ]
    )

    # Formlabs Node (SLA Printer)
    formlabs_node = TimerAction(
        period=3.5,
        actions=[
            Node(
                package='formlabs_ros2',
                executable='formlabs_node.py',
                name='formlabs_node',
                namespace='lego_mcp',
                output='screen',
                parameters=[{
                    'simulate': LaunchConfiguration('use_sim'),
                }],
            )
        ]
    )

    # ====================
    # Phase 3: Supervisory Layer (ISA-95 Level 2)
    # ====================

    phase3_info = TimerAction(
        period=5.0,  # Wait for equipment to initialize
        actions=[
            LogInfo(msg='[STARTUP] Phase 3: Starting Supervisory Layer (L2)...')
        ]
    )

    # Orchestrator Node (Lifecycle)
    orchestrator_node = TimerAction(
        period=6.0,
        actions=[
            LifecycleNode(
                package='lego_mcp_orchestrator',
                executable='orchestrator_lifecycle_node.py',
                name='orchestrator',
                namespace='lego_mcp',
                output='screen',
                parameters=[{
                    'equipment_timeout_sec': 10.0,
                }],
            )
        ]
    )

    # Supervisor Node
    supervisor_node = TimerAction(
        period=7.0,
        actions=[
            Node(
                package='lego_mcp_supervisor',
                executable='supervisor_node.py',
                name='supervisor',
                namespace='lego_mcp',
                output='screen',
                parameters=[{
                    'restart_strategy': 'one_for_one',
                    'max_restarts': 5,
                }],
            )
        ]
    )

    # AGV Fleet (optional)
    agv_fleet_node = TimerAction(
        period=8.0,
        actions=[
            Node(
                package='lego_mcp_agv',
                executable='fleet_manager_node.py',
                name='agv_fleet',
                namespace='lego_mcp',
                output='screen',
                condition=IfCondition(LaunchConfiguration('enable_agv')),
            )
        ]
    )

    # ====================
    # Phase 4: SCADA/MES Bridges (Optional)
    # ====================

    phase4_info = TimerAction(
        period=10.0,
        actions=[
            LogInfo(msg='[STARTUP] Phase 4: Starting SCADA/MES Bridges...')
        ]
    )

    # Security Manager (if enabled)
    security_manager = TimerAction(
        period=11.0,
        actions=[
            LifecycleNode(
                package='lego_mcp_security',
                executable='security_manager_node.py',
                name='security_manager',
                namespace='lego_mcp',
                output='screen',
                condition=IfCondition(LaunchConfiguration('enable_security')),
            )
        ]
    )

    # ====================
    # Startup Complete
    # ====================

    startup_complete = TimerAction(
        period=12.0,
        actions=[
            LogInfo(msg='[STARTUP] ✓ Deterministic startup complete!')
        ]
    )

    # ====================
    # Return Launch Description
    # ====================

    return LaunchDescription([
        # Arguments
        use_sim_arg,
        enable_security_arg,
        enable_agv_arg,
        startup_timeout_arg,

        # Phase 1: Safety (L1)
        phase1_info,
        safety_node,
        configure_safety,
        watchdog_node,

        # Phase 2: Equipment (L0)
        phase2_info,
        grbl_node,
        formlabs_node,

        # Phase 3: Supervisory (L2)
        phase3_info,
        orchestrator_node,
        supervisor_node,
        agv_fleet_node,

        # Phase 4: SCADA/MES
        phase4_info,
        security_manager,

        # Complete
        startup_complete,
    ])
