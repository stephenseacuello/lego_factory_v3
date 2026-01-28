#!/usr/bin/env python3
"""
Full Simulation Launch File - Complete simulated manufacturing system

Launches the entire LEGO MCP manufacturing system in simulation mode:
- Simulated equipment (GRBL CNC, Formlabs SLA, Bambu FDM)
- OTP-style supervision with fault injection capability
- Gazebo factory environment (optional)
- Digital twin visualization
- Chaos testing support

LEGO MCP Manufacturing System v7.0
Industry 4.0/5.0 Architecture - ISA-95 Compliant

Usage:
    # Basic simulation
    ros2 launch lego_mcp_simulation full_simulation.launch.py

    # With Gazebo visualization
    ros2 launch lego_mcp_simulation full_simulation.launch.py use_gazebo:=true

    # With chaos testing enabled
    ros2 launch lego_mcp_simulation full_simulation.launch.py enable_chaos:=true
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    GroupAction,
    TimerAction,
    LogInfo,
    SetEnvironmentVariable,
    ExecuteProcess,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    Command,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate full simulation launch description."""

    # Package directories
    simulation_pkg = get_package_share_directory('lego_mcp_simulation')
    bringup_pkg = get_package_share_directory('lego_mcp_bringup')
    supervisor_pkg = get_package_share_directory('lego_mcp_supervisor')

    # ========================================
    # Launch Arguments
    # ========================================

    declare_use_gazebo = DeclareLaunchArgument(
        'use_gazebo',
        default_value='false',
        description='Launch Gazebo visualization'
    )

    declare_enable_supervision = DeclareLaunchArgument(
        'enable_supervision',
        default_value='true',
        description='Enable OTP supervision tree'
    )

    declare_enable_chaos = DeclareLaunchArgument(
        'enable_chaos',
        default_value='false',
        description='Enable chaos testing controller'
    )

    declare_headless = DeclareLaunchArgument(
        'headless',
        default_value='false',
        description='Run in headless mode (no GUI)'
    )

    declare_sim_speed = DeclareLaunchArgument(
        'sim_speed',
        default_value='1.0',
        description='Simulation speed multiplier'
    )

    # ========================================
    # Gazebo Simulation (Optional)
    # ========================================
    gazebo_group = GroupAction(
        condition=IfCondition(LaunchConfiguration('use_gazebo')),
        actions=[
            LogInfo(msg='Starting Gazebo factory simulation...'),

            IncludeLaunchDescription(
                PythonLaunchDescriptionSource([
                    simulation_pkg, '/launch/gazebo_factory.launch.py'
                ]),
                launch_arguments={
                    'headless': LaunchConfiguration('headless'),
                }.items()
            ),
        ]
    )

    # ========================================
    # Simulated Equipment (ISA-95 L0)
    # ========================================
    equipment_sim_group = GroupAction(
        actions=[
            LogInfo(msg='========================================'),
            LogInfo(msg='  Starting Simulated Equipment (L0)'),
            LogInfo(msg='========================================'),

            # Simulated GRBL CNC/Laser
            Node(
                package='lego_mcp_simulation',
                executable='grbl_simulator',
                name='grbl_simulator',
                namespace='lego_mcp/sim',
                parameters=[{
                    'sim_speed': LaunchConfiguration('sim_speed'),
                    'enable_faults': True,
                    'fault_probability': 0.001,  # 0.1% chance per operation
                }],
                output='screen',
            ),

            # Simulated Formlabs SLA
            Node(
                package='lego_mcp_simulation',
                executable='formlabs_simulator',
                name='formlabs_simulator',
                namespace='lego_mcp/sim',
                parameters=[{
                    'sim_speed': LaunchConfiguration('sim_speed'),
                    'enable_faults': True,
                    'fault_probability': 0.001,
                }],
                output='screen',
            ),

            # Simulated Bambu FDM
            Node(
                package='lego_mcp_simulation',
                executable='bambu_simulator',
                name='bambu_simulator',
                namespace='lego_mcp/sim',
                parameters=[{
                    'sim_speed': LaunchConfiguration('sim_speed'),
                    'enable_faults': True,
                    'fault_probability': 0.001,
                }],
                output='screen',
            ),
        ]
    )

    # ========================================
    # Supervision Tree
    # ========================================
    supervision_group = TimerAction(
        period=2.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_supervision')),
                actions=[
                    LogInfo(msg='========================================'),
                    LogInfo(msg='  Starting Supervision Tree'),
                    LogInfo(msg='========================================'),

                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource([
                            supervisor_pkg, '/launch/supervision.launch.py'
                        ]),
                        launch_arguments={
                            'use_sim': 'true',
                            'enable_safety': 'true',
                            'enable_equipment': 'true',
                            'enable_robotics': 'false',
                            'enable_agv': 'false',
                        }.items()
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Safety Simulator
    # ========================================
    safety_sim_group = TimerAction(
        period=3.0,
        actions=[
            LogInfo(msg='Starting simulated safety system...'),

            Node(
                package='lego_mcp_safety',
                executable='safety_node',
                name='safety_node',
                namespace='lego_mcp',
                parameters=[{
                    'use_sim': True,
                    'estop_pin': 17,
                    'watchdog_pin': 27,
                }],
                output='screen',
            ),
        ]
    )

    # ========================================
    # Chaos Testing Controller (Optional)
    # ========================================
    chaos_group = TimerAction(
        period=10.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_chaos')),
                actions=[
                    LogInfo(msg='========================================'),
                    LogInfo(msg='  Starting Chaos Testing Controller'),
                    LogInfo(msg='  WARNING: Fault injection enabled!'),
                    LogInfo(msg='========================================'),

                    Node(
                        package='lego_mcp_chaos',
                        executable='chaos_controller',
                        name='chaos_controller',
                        namespace='lego_mcp/chaos',
                        parameters=[{
                            'enable_safety_zone_protection': True,
                            'max_concurrent_faults': 2,
                            'auto_cleanup_on_error': True,
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Simulated Orchestrator
    # ========================================
    orchestrator_group = TimerAction(
        period=8.0,
        actions=[
            LogInfo(msg='Starting simulated orchestrator...'),

            Node(
                package='lego_mcp_orchestrator',
                executable='orchestrator_node',
                name='orchestrator',
                namespace='lego_mcp',
                parameters=[{
                    'use_sim': True,
                    'job_queue_size': 100,
                }],
                output='screen',
            ),
        ]
    )

    # ========================================
    # Digital Twin State Publisher
    # ========================================
    twin_publisher = TimerAction(
        period=5.0,
        actions=[
            LogInfo(msg='Starting digital twin state publisher...'),

            Node(
                package='lego_mcp_orchestrator',
                executable='twin_publisher',
                name='twin_publisher',
                namespace='lego_mcp',
                parameters=[{
                    'publish_rate': 10.0,  # 10 Hz
                }],
                output='screen',
            ),
        ]
    )

    # ========================================
    # Startup Complete
    # ========================================
    startup_complete = TimerAction(
        period=15.0,
        actions=[
            LogInfo(msg=''),
            LogInfo(msg='========================================'),
            LogInfo(msg='  LEGO MCP Full Simulation Started'),
            LogInfo(msg='========================================'),
            LogInfo(msg=''),
            LogInfo(msg='  Simulated Equipment:'),
            LogInfo(msg='    - GRBL CNC/Laser'),
            LogInfo(msg='    - Formlabs SLA'),
            LogInfo(msg='    - Bambu FDM'),
            LogInfo(msg=''),
            LogInfo(msg='  Supervision: /lego_mcp/supervision/*'),
            LogInfo(msg='  Equipment: /lego_mcp/sim/*'),
            LogInfo(msg=''),
            LogInfo(msg='  Dashboard: http://localhost:5000'),
            LogInfo(msg=''),
            LogInfo(msg='========================================'),
        ]
    )

    return LaunchDescription([
        # Environment
        SetEnvironmentVariable('RCUTILS_COLORIZED_OUTPUT', '1'),

        # Arguments
        declare_use_gazebo,
        declare_enable_supervision,
        declare_enable_chaos,
        declare_headless,
        declare_sim_speed,

        # Banner
        LogInfo(msg=''),
        LogInfo(msg='╔══════════════════════════════════════════════════╗'),
        LogInfo(msg='║   LEGO MCP Full Simulation System v7.0          ║'),
        LogInfo(msg='║   Industry 4.0/5.0 Simulation Environment       ║'),
        LogInfo(msg='╚══════════════════════════════════════════════════╝'),
        LogInfo(msg=''),

        # Launch groups
        gazebo_group,
        equipment_sim_group,
        supervision_group,
        safety_sim_group,
        orchestrator_group,
        twin_publisher,
        chaos_group,

        # Completion
        startup_complete,
    ])
