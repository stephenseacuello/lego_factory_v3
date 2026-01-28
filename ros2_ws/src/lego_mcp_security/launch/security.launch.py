#!/usr/bin/env python3
"""
LEGO MCP Security Launch File

Launches security management nodes:
- Security Manager (SROS2, zones, access control)
- Audit Pipeline (tamper-evident logging)

Industry 4.0/5.0 Architecture - ISA-95 Security Layer
"""

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, RegisterEventHandler
from launch.events import matches_action
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import LifecycleNode
from launch_ros.events.lifecycle import ChangeState
from launch_ros.substitutions import FindPackageShare
from lifecycle_msgs.msg import Transition


def generate_launch_description():
    """Generate launch description for security nodes."""

    # Declare launch arguments
    keystore_path_arg = DeclareLaunchArgument(
        'keystore_path',
        default_value='/tmp/lego_mcp_keystore',
        description='Path to SROS2 keystore'
    )

    audit_log_path_arg = DeclareLaunchArgument(
        'audit_log_path',
        default_value='/var/log/lego_mcp/security.log',
        description='Path to security audit log'
    )

    enable_ids_arg = DeclareLaunchArgument(
        'enable_intrusion_detection',
        default_value='true',
        description='Enable intrusion detection system'
    )

    heartbeat_rate_arg = DeclareLaunchArgument(
        'heartbeat_rate',
        default_value='1.0',
        description='Security status publish rate (Hz)'
    )

    # Security Manager Node (Lifecycle)
    security_manager_node = LifecycleNode(
        package='lego_mcp_security',
        executable='security_manager_node.py',
        name='security_manager',
        namespace='lego_mcp',
        output='screen',
        parameters=[{
            'keystore_path': LaunchConfiguration('keystore_path'),
            'audit_log_path': LaunchConfiguration('audit_log_path'),
            'enable_intrusion_detection': LaunchConfiguration('enable_intrusion_detection'),
            'heartbeat_rate': LaunchConfiguration('heartbeat_rate'),
        }],
    )

    # Audit Pipeline Node (Lifecycle)
    audit_pipeline_node = LifecycleNode(
        package='lego_mcp_security',
        executable='audit_pipeline_node.py',
        name='audit_pipeline',
        namespace='lego_mcp',
        output='screen',
        parameters=[{
            'log_path': LaunchConfiguration('audit_log_path'),
            'enable_hash_chain': True,
            'retention_days': 90,
        }],
    )

    # Event handlers to transition nodes through lifecycle
    # Configure security manager when launched
    configure_security_manager = RegisterEventHandler(
        event_handler=EmitEvent(
            event=ChangeState(
                lifecycle_node_matcher=matches_action(security_manager_node),
                transition_id=Transition.TRANSITION_CONFIGURE,
            )
        )
    )

    # Configure audit pipeline when launched
    configure_audit_pipeline = RegisterEventHandler(
        event_handler=EmitEvent(
            event=ChangeState(
                lifecycle_node_matcher=matches_action(audit_pipeline_node),
                transition_id=Transition.TRANSITION_CONFIGURE,
            )
        )
    )

    return LaunchDescription([
        # Arguments
        keystore_path_arg,
        audit_log_path_arg,
        enable_ids_arg,
        heartbeat_rate_arg,

        # Nodes
        security_manager_node,
        audit_pipeline_node,

        # Lifecycle transitions
        configure_security_manager,
        configure_audit_pipeline,
    ])
