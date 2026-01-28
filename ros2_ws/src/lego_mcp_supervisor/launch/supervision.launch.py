#!/usr/bin/env python3
"""
OTP-style Supervision Tree Launch File

Launches the hierarchical supervision tree for fault-tolerant manufacturing.
Industry 4.0/5.0 Architecture - ISA-95 Compliant

LEGO MCP Manufacturing System v7.0

Supervision Hierarchy:
    RootSupervisor (one_for_all)
    ├── SafetySupervisor (one_for_all)
    │   ├── safety_node [lifecycle]
    │   └── watchdog_node
    ├── EquipmentSupervisor (one_for_one)
    │   ├── grbl_node [lifecycle]
    │   ├── formlabs_node [lifecycle]
    │   └── bambu_node [lifecycle]
    ├── RoboticsSupervisor (rest_for_one)
    │   ├── moveit_node
    │   ├── ned2_node [lifecycle]
    │   └── xarm_node [lifecycle]
    ├── AGVSupervisor (one_for_one)
    │   ├── agv_fleet_node [lifecycle]
    │   └── alvik_agents
    └── OrchestratorSupervisor (one_for_one)
        └── orchestrator_node [lifecycle]
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    GroupAction,
    TimerAction,
    LogInfo,
    OpaqueFunction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, LifecycleNode
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate the supervision tree launch description."""

    # Package paths
    supervisor_pkg = get_package_share_directory('lego_mcp_supervisor')
    safety_pkg = get_package_share_directory('lego_mcp_safety')
    bringup_pkg = get_package_share_directory('lego_mcp_bringup')

    # Configuration file path
    config_file = os.path.join(supervisor_pkg, 'config', 'supervision_tree.yaml')

    # Launch arguments
    declare_config_arg = DeclareLaunchArgument(
        'config_file',
        default_value=config_file,
        description='Path to supervision tree configuration YAML'
    )

    declare_enable_safety_arg = DeclareLaunchArgument(
        'enable_safety',
        default_value='true',
        description='Enable safety supervisor subsystem'
    )

    declare_enable_equipment_arg = DeclareLaunchArgument(
        'enable_equipment',
        default_value='true',
        description='Enable equipment supervisor subsystem'
    )

    declare_enable_robotics_arg = DeclareLaunchArgument(
        'enable_robotics',
        default_value='false',
        description='Enable robotics supervisor subsystem'
    )

    declare_enable_agv_arg = DeclareLaunchArgument(
        'enable_agv',
        default_value='false',
        description='Enable AGV supervisor subsystem'
    )

    declare_enable_checkpoints_arg = DeclareLaunchArgument(
        'enable_checkpoints',
        default_value='true',
        description='Enable state checkpointing for recovery'
    )

    declare_heartbeat_timeout_arg = DeclareLaunchArgument(
        'heartbeat_timeout_ms',
        default_value='500',
        description='Heartbeat timeout in milliseconds'
    )

    declare_max_restarts_arg = DeclareLaunchArgument(
        'max_restarts',
        default_value='5',
        description='Maximum restart attempts before escalation'
    )

    declare_use_sim_arg = DeclareLaunchArgument(
        'use_sim',
        default_value='false',
        description='Use simulation mode (no real hardware)'
    )

    # Root Supervisor Node
    root_supervisor_node = Node(
        package='lego_mcp_supervisor',
        executable='supervisor_node',
        name='root_supervisor',
        namespace='lego_mcp/supervision',
        parameters=[{
            'config_file': LaunchConfiguration('config_file'),
            'supervisor_id': 'root_supervisor',
            'strategy': 'ONE_FOR_ALL',
            'max_restarts': LaunchConfiguration('max_restarts'),
            'restart_window_sec': 300.0,
            'heartbeat_timeout_ms': LaunchConfiguration('heartbeat_timeout_ms'),
            'enable_checkpoints': LaunchConfiguration('enable_checkpoints'),
        }],
        output='screen',
        emulate_tty=True,
    )

    # Safety Supervisor (Phase 1 - Immediate)
    safety_supervisor_group = GroupAction(
        condition=IfCondition(LaunchConfiguration('enable_safety')),
        actions=[
            LogInfo(msg='[Supervision] Starting Safety Supervisor (L1 Control)...'),

            Node(
                package='lego_mcp_supervisor',
                executable='supervisor_node',
                name='safety_supervisor',
                namespace='lego_mcp/supervision',
                parameters=[{
                    'supervisor_id': 'safety_supervisor',
                    'strategy': 'ONE_FOR_ALL',
                    'max_restarts': 5,
                    'restart_window_sec': 60.0,
                    'parent_supervisor': 'root_supervisor',
                }],
                output='screen',
            ),

            # Safety node (lifecycle)
            LifecycleNode(
                package='lego_mcp_safety',
                executable='safety_node',
                name='safety_node',
                namespace='lego_mcp',
                parameters=[{
                    'estop_pin': 17,
                    'watchdog_pin': 27,
                    'watchdog_timeout_ms': 100,
                    'use_sim': LaunchConfiguration('use_sim'),
                }],
                output='screen',
            ),
        ]
    )

    # Equipment Supervisor (Phase 2 - After Safety, 3s delay)
    equipment_supervisor_group = TimerAction(
        period=3.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_equipment')),
                actions=[
                    LogInfo(msg='[Supervision] Starting Equipment Supervisor (L0 Field)...'),

                    Node(
                        package='lego_mcp_supervisor',
                        executable='supervisor_node',
                        name='equipment_supervisor',
                        namespace='lego_mcp/supervision',
                        parameters=[{
                            'supervisor_id': 'equipment_supervisor',
                            'strategy': 'ONE_FOR_ONE',
                            'max_restarts': 10,
                            'restart_window_sec': 120.0,
                            'parent_supervisor': 'root_supervisor',
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # Robotics Supervisor (Phase 3 - After Equipment, 6s delay)
    robotics_supervisor_group = TimerAction(
        period=6.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_robotics')),
                actions=[
                    LogInfo(msg='[Supervision] Starting Robotics Supervisor (L2 Supervisory)...'),

                    Node(
                        package='lego_mcp_supervisor',
                        executable='supervisor_node',
                        name='robotics_supervisor',
                        namespace='lego_mcp/supervision',
                        parameters=[{
                            'supervisor_id': 'robotics_supervisor',
                            'strategy': 'REST_FOR_ONE',
                            'max_restarts': 5,
                            'restart_window_sec': 120.0,
                            'parent_supervisor': 'root_supervisor',
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # AGV Supervisor (Phase 3 - After Equipment, 6s delay)
    agv_supervisor_group = TimerAction(
        period=6.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_agv')),
                actions=[
                    LogInfo(msg='[Supervision] Starting AGV Supervisor (L2 Supervisory)...'),

                    Node(
                        package='lego_mcp_supervisor',
                        executable='supervisor_node',
                        name='agv_supervisor',
                        namespace='lego_mcp/supervision',
                        parameters=[{
                            'supervisor_id': 'agv_supervisor',
                            'strategy': 'ONE_FOR_ONE',
                            'max_restarts': 10,
                            'restart_window_sec': 180.0,
                            'parent_supervisor': 'root_supervisor',
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # Orchestrator Supervisor (Phase 4 - After all, 10s delay)
    orchestrator_supervisor_group = TimerAction(
        period=10.0,
        actions=[
            LogInfo(msg='[Supervision] Starting Orchestrator Supervisor (L2 Supervisory)...'),

            Node(
                package='lego_mcp_supervisor',
                executable='supervisor_node',
                name='orchestrator_supervisor',
                namespace='lego_mcp/supervision',
                parameters=[{
                    'supervisor_id': 'orchestrator_supervisor',
                    'strategy': 'ONE_FOR_ONE',
                    'max_restarts': 5,
                    'restart_window_sec': 120.0,
                    'parent_supervisor': 'root_supervisor',
                }],
                output='screen',
            ),
        ]
    )

    # Heartbeat Monitor Node
    heartbeat_monitor_node = Node(
        package='lego_mcp_supervisor',
        executable='heartbeat_monitor',
        name='heartbeat_monitor',
        namespace='lego_mcp/supervision',
        parameters=[{
            'timeout_ms': LaunchConfiguration('heartbeat_timeout_ms'),
            'check_interval_ms': 100,
            'missed_threshold': 3,
        }],
        output='screen',
    )

    return LaunchDescription([
        # Launch arguments
        declare_config_arg,
        declare_enable_safety_arg,
        declare_enable_equipment_arg,
        declare_enable_robotics_arg,
        declare_enable_agv_arg,
        declare_enable_checkpoints_arg,
        declare_heartbeat_timeout_arg,
        declare_max_restarts_arg,
        declare_use_sim_arg,

        # Startup message
        LogInfo(msg='========================================'),
        LogInfo(msg='  LEGO MCP Supervision Tree Starting'),
        LogInfo(msg='  OTP-style Fault Tolerance'),
        LogInfo(msg='  ISA-95 Compliant Architecture'),
        LogInfo(msg='========================================'),

        # Root supervisor first
        root_supervisor_node,

        # Phase 1: Safety (immediate)
        safety_supervisor_group,

        # Phase 2: Equipment (3s delay)
        equipment_supervisor_group,

        # Phase 3: Robotics & AGV (6s delay)
        robotics_supervisor_group,
        agv_supervisor_group,

        # Phase 4: Orchestrator (10s delay)
        orchestrator_supervisor_group,

        # Heartbeat monitor (after 2s)
        TimerAction(
            period=2.0,
            actions=[heartbeat_monitor_node]
        ),

        # Final startup message
        TimerAction(
            period=12.0,
            actions=[
                LogInfo(msg='========================================'),
                LogInfo(msg='  Supervision Tree Initialization Complete'),
                LogInfo(msg='========================================'),
            ]
        ),
    ])
