#!/usr/bin/env python3
"""
Robotics Launch File - Robot Arms and MoveIt2 Integration

Launches robotics subsystem including:
- Niryo Ned2 robot arm
- xArm 6 Lite robot arm
- MoveIt2 motion planning
- Assembly coordinator

LEGO MCP Manufacturing System v7.0
Industry 4.0/5.0 Architecture - ISA-95 Level 2 (Supervisory)

Usage:
    # Full robotics with MoveIt2
    ros2 launch lego_mcp_bringup robotics.launch.py

    # Simulation mode
    ros2 launch lego_mcp_bringup robotics.launch.py use_sim:=true

    # Single robot only
    ros2 launch lego_mcp_bringup robotics.launch.py enable_ned2:=true enable_xarm:=false
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    GroupAction,
    TimerAction,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, LifecycleNode
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate the robotics launch description."""

    # ========================================
    # Launch Arguments
    # ========================================
    declare_use_sim = DeclareLaunchArgument(
        'use_sim',
        default_value='true',
        description='Use simulation mode'
    )

    declare_enable_ned2 = DeclareLaunchArgument(
        'enable_ned2',
        default_value='true',
        description='Enable Niryo Ned2 robot arm'
    )

    declare_enable_xarm = DeclareLaunchArgument(
        'enable_xarm',
        default_value='true',
        description='Enable xArm 6 Lite robot arm'
    )

    declare_enable_moveit = DeclareLaunchArgument(
        'enable_moveit',
        default_value='true',
        description='Enable MoveIt2 motion planning'
    )

    declare_enable_assembly = DeclareLaunchArgument(
        'enable_assembly',
        default_value='true',
        description='Enable assembly coordinator'
    )

    # ========================================
    # MoveIt2 Configuration (Phase 1)
    # ========================================
    moveit_group = GroupAction(
        condition=IfCondition(LaunchConfiguration('enable_moveit')),
        actions=[
            LogInfo(msg='Starting MoveIt2 motion planning...'),

            # MoveIt2 move_group node
            Node(
                package='lego_mcp_moveit_config',
                executable='move_group',
                name='move_group',
                namespace='lego_mcp',
                parameters=[{
                    'use_sim': LaunchConfiguration('use_sim'),
                    'planning_scene_monitor/publish_planning_scene': True,
                    'planning_scene_monitor/publish_geometry_updates': True,
                    'planning_scene_monitor/publish_state_updates': True,
                }],
                output='screen',
            ),
        ]
    )

    # ========================================
    # Niryo Ned2 Robot Arm (Phase 2)
    # ========================================
    ned2_group = TimerAction(
        period=3.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_ned2')),
                actions=[
                    LogInfo(msg='Starting Niryo Ned2 robot arm...'),

                    LifecycleNode(
                        package='niryo_ned2_ros2',
                        executable='ned2_node_lifecycle',
                        name='ned2_node',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'robot_ip': '192.168.1.50',
                            'gripper_type': 'standard',
                            'workspace_id': 'assembly_station_1',
                        }],
                        output='screen',
                    ),

                    # Ned2 gripper controller
                    Node(
                        package='niryo_ned2_ros2',
                        executable='gripper_controller',
                        name='ned2_gripper',
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
    # xArm 6 Lite Robot Arm (Phase 3)
    # ========================================
    xarm_group = TimerAction(
        period=6.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_xarm')),
                actions=[
                    LogInfo(msg='Starting xArm 6 Lite robot arm...'),

                    LifecycleNode(
                        package='xarm_ros2',
                        executable='xarm_node_lifecycle',
                        name='xarm_node',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'robot_ip': '192.168.1.51',
                            'dof': 6,
                            'report_type': 'rich',
                            'workspace_id': 'assembly_station_2',
                        }],
                        output='screen',
                    ),

                    # xArm gripper controller
                    Node(
                        package='xarm_ros2',
                        executable='xarm_gripper_node',
                        name='xarm_gripper',
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
    # Assembly Coordinator (Phase 4)
    # ========================================
    assembly_group = TimerAction(
        period=10.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_assembly')),
                actions=[
                    LogInfo(msg='Starting assembly coordinator...'),

                    Node(
                        package='lego_mcp_orchestrator',
                        executable='moveit_assembly_node.py',
                        name='assembly_coordinator',
                        namespace='lego_mcp',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'assembly_timeout_sec': 300.0,
                            'max_retry_attempts': 3,
                            'pick_approach_distance': 0.1,
                            'place_approach_distance': 0.05,
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Robot State Publisher
    # ========================================
    robot_state_group = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        namespace='lego_mcp',
        parameters=[{
            'use_sim_time': LaunchConfiguration('use_sim'),
        }],
        output='screen',
    )

    return LaunchDescription([
        # Arguments
        declare_use_sim,
        declare_enable_ned2,
        declare_enable_xarm,
        declare_enable_moveit,
        declare_enable_assembly,

        # Banner
        LogInfo(msg=''),
        LogInfo(msg='========================================'),
        LogInfo(msg='  LEGO MCP Robotics Subsystem'),
        LogInfo(msg='  MoveIt2 + Ned2 + xArm'),
        LogInfo(msg='========================================'),
        LogInfo(msg=''),

        # Phased startup
        robot_state_group,
        moveit_group,
        ned2_group,
        xarm_group,
        assembly_group,

        # Completion
        TimerAction(
            period=12.0,
            actions=[
                LogInfo(msg='Robotics subsystem startup complete'),
            ]
        ),
    ])
