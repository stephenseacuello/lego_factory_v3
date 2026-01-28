#!/usr/bin/env python3
"""
Full System Launch File - Complete LEGO MCP Manufacturing System

Launches the entire Industry 4.0/5.0 manufacturing system including:
- OTP-style supervision tree with fault tolerance
- Safety systems (ISA-95 Level 1)
- Equipment nodes (ISA-95 Level 0)
- Orchestration (ISA-95 Level 2)
- Digital twin integration
- Vision and quality systems

LEGO MCP Manufacturing System v7.0
Industry 4.0/5.0 Architecture - ISA-95 Compliant

Usage:
    # Full system with all features
    ros2 launch lego_mcp_bringup full_system.launch.py

    # Simulation mode (no real hardware)
    ros2 launch lego_mcp_bringup full_system.launch.py use_sim:=true

    # Without robotics
    ros2 launch lego_mcp_bringup full_system.launch.py enable_robotics:=false

    # With security enabled
    ros2 launch lego_mcp_bringup full_system.launch.py enable_security:=true
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
)
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    EnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, LifecycleNode, PushRosNamespace
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate the full system launch description."""

    # Package directories
    bringup_pkg = get_package_share_directory('lego_mcp_bringup')
    supervisor_pkg = get_package_share_directory('lego_mcp_supervisor')
    safety_pkg = get_package_share_directory('lego_mcp_safety')
    security_pkg = get_package_share_directory('lego_mcp_security')

    # ========================================
    # Launch Arguments
    # ========================================

    # Simulation mode
    declare_use_sim = DeclareLaunchArgument(
        'use_sim',
        default_value='false',
        description='Use simulation mode (no real hardware)'
    )

    # Feature toggles
    declare_enable_safety = DeclareLaunchArgument(
        'enable_safety',
        default_value='true',
        description='Enable safety subsystem (ISA-95 L1)'
    )

    declare_enable_equipment = DeclareLaunchArgument(
        'enable_equipment',
        default_value='true',
        description='Enable equipment nodes (ISA-95 L0)'
    )

    declare_enable_robotics = DeclareLaunchArgument(
        'enable_robotics',
        default_value='false',
        description='Enable robotics subsystem'
    )

    declare_enable_agv = DeclareLaunchArgument(
        'enable_agv',
        default_value='false',
        description='Enable AGV fleet subsystem'
    )

    declare_enable_vision = DeclareLaunchArgument(
        'enable_vision',
        default_value='true',
        description='Enable computer vision subsystem'
    )

    declare_enable_supervision = DeclareLaunchArgument(
        'enable_supervision',
        default_value='true',
        description='Enable OTP-style supervision tree'
    )

    declare_enable_security = DeclareLaunchArgument(
        'enable_security',
        default_value='false',
        description='Enable SROS2 security (IEC 62443)'
    )

    declare_enable_scada = DeclareLaunchArgument(
        'enable_scada',
        default_value='false',
        description='Enable SCADA/MES protocol bridges (OPC UA, MTConnect, Sparkplug B)'
    )

    # Supervision parameters
    declare_heartbeat_timeout = DeclareLaunchArgument(
        'heartbeat_timeout_ms',
        default_value='500',
        description='Heartbeat timeout in milliseconds'
    )

    declare_max_restarts = DeclareLaunchArgument(
        'max_restarts',
        default_value='5',
        description='Maximum restart attempts before escalation'
    )

    # ========================================
    # Phase 1: Supervision Tree (OTP-style)
    # ========================================
    supervision_group = GroupAction(
        condition=IfCondition(LaunchConfiguration('enable_supervision')),
        actions=[
            LogInfo(msg='========================================'),
            LogInfo(msg='  Phase 1: Starting Supervision Tree'),
            LogInfo(msg='========================================'),

            IncludeLaunchDescription(
                PythonLaunchDescriptionSource([
                    supervisor_pkg, '/launch/supervision.launch.py'
                ]),
                launch_arguments={
                    'enable_safety': LaunchConfiguration('enable_safety'),
                    'enable_equipment': LaunchConfiguration('enable_equipment'),
                    'enable_robotics': LaunchConfiguration('enable_robotics'),
                    'enable_agv': LaunchConfiguration('enable_agv'),
                    'heartbeat_timeout_ms': LaunchConfiguration('heartbeat_timeout_ms'),
                    'max_restarts': LaunchConfiguration('max_restarts'),
                    'use_sim': LaunchConfiguration('use_sim'),
                }.items()
            ),
        ]
    )

    # ========================================
    # Phase 2: Safety Systems (ISA-95 L1)
    # ========================================
    safety_group = TimerAction(
        period=2.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_safety')),
                actions=[
                    LogInfo(msg='========================================'),
                    LogInfo(msg='  Phase 2: Starting Safety Systems (L1)'),
                    LogInfo(msg='========================================'),

                    LifecycleNode(
                        package='lego_mcp_safety',
                        executable='safety_node',
                        name='safety_node',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'estop_pin': 17,
                            'watchdog_pin': 27,
                            'watchdog_timeout_ms': 100,
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Phase 3: Equipment Nodes (ISA-95 L0)
    # ========================================
    equipment_group = TimerAction(
        period=5.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_equipment')),
                actions=[
                    LogInfo(msg='========================================'),
                    LogInfo(msg='  Phase 3: Starting Equipment (L0)'),
                    LogInfo(msg='========================================'),

                    # GRBL CNC/Laser node
                    LifecycleNode(
                        package='grbl_ros2',
                        executable='grbl_node_lifecycle',
                        name='grbl_node',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'serial_port': '/dev/ttyUSB0',
                            'baud_rate': 115200,
                        }],
                        output='screen',
                    ),

                    # Formlabs SLA node
                    LifecycleNode(
                        package='formlabs_ros2',
                        executable='formlabs_node_lifecycle',
                        name='formlabs_node',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'api_url': 'http://localhost:9000',
                        }],
                        output='screen',
                    ),

                    # Bambu FDM node
                    LifecycleNode(
                        package='bambu_ros2',
                        executable='bambu_node_lifecycle',
                        name='bambu_node',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'mqtt_host': '192.168.1.100',
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Phase 4: Vision Systems
    # ========================================
    vision_group = TimerAction(
        period=8.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_vision')),
                actions=[
                    LogInfo(msg='========================================'),
                    LogInfo(msg='  Phase 4: Starting Vision Systems'),
                    LogInfo(msg='========================================'),

                    Node(
                        package='lego_mcp_vision',
                        executable='vision_node',
                        name='vision_node',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'camera_index': 0,
                            'enable_defect_detection': True,
                        }],
                        output='screen',
                    ),

                    Node(
                        package='lego_mcp_calibration',
                        executable='calibration_node',
                        name='calibration_node',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Phase 5: Orchestration (ISA-95 L2)
    # ========================================
    orchestration_group = TimerAction(
        period=12.0,
        actions=[
            LogInfo(msg='========================================'),
            LogInfo(msg='  Phase 5: Starting Orchestration (L2)'),
            LogInfo(msg='========================================'),

            LifecycleNode(
                package='lego_mcp_orchestrator',
                executable='orchestrator_lifecycle',
                name='orchestrator',
                namespace='lego_mcp',
                parameters=[{
                    'use_sim': LaunchConfiguration('use_sim'),
                    'job_queue_size': 100,
                    'max_concurrent_jobs': 5,
                }],
                output='screen',
            ),
        ]
    )

    # ========================================
    # Phase 6: Robotics (Optional)
    # ========================================
    robotics_group = TimerAction(
        period=15.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_robotics')),
                actions=[
                    LogInfo(msg='========================================'),
                    LogInfo(msg='  Phase 6: Starting Robotics'),
                    LogInfo(msg='========================================'),

                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource([
                            bringup_pkg, '/launch/robotics.launch.py'
                        ]),
                        launch_arguments={
                            'use_sim': LaunchConfiguration('use_sim'),
                        }.items(),
                        condition=IfCondition(LaunchConfiguration('enable_robotics'))
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Phase 7: AGV Fleet (Optional)
    # ========================================
    agv_group = TimerAction(
        period=18.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_agv')),
                actions=[
                    LogInfo(msg='========================================'),
                    LogInfo(msg='  Phase 7: Starting AGV Fleet'),
                    LogInfo(msg='========================================'),

                    Node(
                        package='lego_mcp_agv',
                        executable='fleet_manager',
                        name='agv_fleet',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'fleet_size': 4,
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Phase 8: Security (Optional - IEC 62443)
    # ========================================
    security_group = TimerAction(
        period=3.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_security')),
                actions=[
                    LogInfo(msg='========================================'),
                    LogInfo(msg='  Phase 8: Starting Security (IEC 62443)'),
                    LogInfo(msg='========================================'),

                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource([
                            security_pkg, '/launch/security.launch.py'
                        ]),
                        launch_arguments={
                            'keystore_path': '/etc/lego_mcp/keystore',
                            'enable_intrusion_detection': 'true',
                        }.items()
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Phase 9: SCADA/MES Bridges (Optional)
    # ========================================
    scada_group = TimerAction(
        period=22.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_scada')),
                actions=[
                    LogInfo(msg='========================================'),
                    LogInfo(msg='  Phase 9: Starting SCADA/MES Bridges'),
                    LogInfo(msg='========================================'),

                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource([
                            bringup_pkg, '/launch/scada_bridges.launch.py'
                        ]),
                        launch_arguments={
                            'use_sim': LaunchConfiguration('use_sim'),
                            'enable_opcua': 'true',
                            'enable_mtconnect': 'true',
                            'enable_sparkplug': 'true',
                        }.items()
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Startup Complete Message
    # ========================================
    startup_complete = TimerAction(
        period=25.0,
        actions=[
            LogInfo(msg=''),
            LogInfo(msg='========================================'),
            LogInfo(msg='  LEGO MCP Full System Started'),
            LogInfo(msg='  Industry 4.0/5.0 Manufacturing'),
            LogInfo(msg='  ISA-95 Compliant Architecture'),
            LogInfo(msg='========================================'),
            LogInfo(msg=''),
            LogInfo(msg='  Dashboard: http://localhost:5000'),
            LogInfo(msg='  ROS2 Topics: ros2 topic list'),
            LogInfo(msg='  Supervision: /lego_mcp/supervision/*'),
            LogInfo(msg=''),
            LogInfo(msg='========================================'),
        ]
    )

    return LaunchDescription([
        # Environment
        SetEnvironmentVariable('RCUTILS_COLORIZED_OUTPUT', '1'),

        # Launch arguments
        declare_use_sim,
        declare_enable_safety,
        declare_enable_equipment,
        declare_enable_robotics,
        declare_enable_agv,
        declare_enable_vision,
        declare_enable_supervision,
        declare_enable_security,
        declare_enable_scada,
        declare_heartbeat_timeout,
        declare_max_restarts,

        # Banner
        LogInfo(msg=''),
        LogInfo(msg='╔══════════════════════════════════════════════════╗'),
        LogInfo(msg='║     LEGO MCP Full Manufacturing System v7.0     ║'),
        LogInfo(msg='║     Industry 4.0/5.0 - ISA-95 Compliant         ║'),
        LogInfo(msg='╚══════════════════════════════════════════════════╝'),
        LogInfo(msg=''),

        # Phased startup
        supervision_group,
        security_group,
        safety_group,
        equipment_group,
        vision_group,
        orchestration_group,
        robotics_group,
        agv_group,
        scada_group,

        # Completion message
        startup_complete,
    ])
