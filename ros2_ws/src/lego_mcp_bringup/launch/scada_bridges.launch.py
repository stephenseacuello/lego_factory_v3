#!/usr/bin/env python3
"""
SCADA/MES Bridge Launch File - Industrial Protocol Bridges

Launches SCADA/MES protocol bridges for enterprise integration:
- OPC UA Server (OPC 40501 CNC compliant)
- MTConnect Agent (ANSI/MTC1.4-2018)
- Sparkplug B Edge Node (Eclipse Sparkplug 3.0)
- MQTT Adapter for IoT integration

LEGO MCP Manufacturing System v7.0
Industry 4.0/5.0 Architecture - ISA-95 Level 3-4 Bridge

Usage:
    # All SCADA bridges
    ros2 launch lego_mcp_bringup scada_bridges.launch.py

    # OPC UA only
    ros2 launch lego_mcp_bringup scada_bridges.launch.py enable_mtconnect:=false enable_sparkplug:=false

    # Simulation mode
    ros2 launch lego_mcp_bringup scada_bridges.launch.py use_sim:=true
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    TimerAction,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate the SCADA bridges launch description."""

    # ========================================
    # Launch Arguments
    # ========================================
    declare_use_sim = DeclareLaunchArgument(
        'use_sim',
        default_value='false',
        description='Use simulation mode'
    )

    declare_enable_opcua = DeclareLaunchArgument(
        'enable_opcua',
        default_value='true',
        description='Enable OPC UA Server (OPC 40501 CNC)'
    )

    declare_enable_mtconnect = DeclareLaunchArgument(
        'enable_mtconnect',
        default_value='true',
        description='Enable MTConnect Agent (ANSI/MTC1.4-2018)'
    )

    declare_enable_sparkplug = DeclareLaunchArgument(
        'enable_sparkplug',
        default_value='true',
        description='Enable Sparkplug B Edge Node'
    )

    declare_enable_mqtt = DeclareLaunchArgument(
        'enable_mqtt',
        default_value='true',
        description='Enable MQTT Adapter for IoT'
    )

    # OPC UA Parameters
    declare_opcua_port = DeclareLaunchArgument(
        'opcua_port',
        default_value='4840',
        description='OPC UA Server port'
    )

    # MTConnect Parameters
    declare_mtconnect_port = DeclareLaunchArgument(
        'mtconnect_port',
        default_value='5000',
        description='MTConnect Agent HTTP port'
    )

    # Sparkplug/MQTT Parameters
    declare_mqtt_host = DeclareLaunchArgument(
        'mqtt_host',
        default_value='localhost',
        description='MQTT Broker hostname'
    )

    declare_mqtt_port = DeclareLaunchArgument(
        'mqtt_port',
        default_value='1883',
        description='MQTT Broker port'
    )

    declare_sparkplug_group = DeclareLaunchArgument(
        'sparkplug_group_id',
        default_value='lego_mcp',
        description='Sparkplug B Group ID'
    )

    declare_sparkplug_node = DeclareLaunchArgument(
        'sparkplug_edge_node_id',
        default_value='factory_floor',
        description='Sparkplug B Edge Node ID'
    )

    # ========================================
    # OPC UA Server (Phase 1)
    # ========================================
    opcua_group = GroupAction(
        condition=IfCondition(LaunchConfiguration('enable_opcua')),
        actions=[
            LogInfo(msg='Starting OPC UA Server (OPC 40501 CNC)...'),

            Node(
                package='lego_mcp_edge',
                executable='opcua_server_node',
                name='opcua_server',
                namespace='lego_mcp/scada',
                parameters=[{
                    'use_sim': LaunchConfiguration('use_sim'),
                    'endpoint_port': LaunchConfiguration('opcua_port'),
                    'namespace_uri': 'http://legomcp.dev/cnc',
                    'security_policy': 'Basic256Sha256',
                    'enable_cnc_model': True,
                    # OPC 40501 CNC nodes
                    'cnc_interface_enabled': True,
                    'cnc_axis_count': 3,
                    'cnc_spindle_enabled': True,
                }],
                output='screen',
            ),
        ]
    )

    # ========================================
    # MTConnect Agent (Phase 2)
    # ========================================
    mtconnect_group = TimerAction(
        period=3.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_mtconnect')),
                actions=[
                    LogInfo(msg='Starting MTConnect Agent (ANSI/MTC1.4-2018)...'),

                    Node(
                        package='lego_mcp_edge',
                        executable='mtconnect_agent_node',
                        name='mtconnect_agent',
                        namespace='lego_mcp/scada',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'http_port': LaunchConfiguration('mtconnect_port'),
                            'device_name': 'lego_mcp_factory',
                            'device_uuid': 'LEGO-MCP-001',
                            'buffer_size': 100000,
                            'enable_shdr': True,
                            # Equipment data items
                            'equipment_ids': ['grbl_cnc', 'formlabs_sla', 'bambu_fdm'],
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Sparkplug B Edge Node (Phase 3)
    # ========================================
    sparkplug_group = TimerAction(
        period=6.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_sparkplug')),
                actions=[
                    LogInfo(msg='Starting Sparkplug B Edge Node...'),

                    Node(
                        package='lego_mcp_edge',
                        executable='sparkplug_edge_node',
                        name='sparkplug_edge',
                        namespace='lego_mcp/scada',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'mqtt_host': LaunchConfiguration('mqtt_host'),
                            'mqtt_port': LaunchConfiguration('mqtt_port'),
                            'group_id': LaunchConfiguration('sparkplug_group_id'),
                            'edge_node_id': LaunchConfiguration('sparkplug_edge_node_id'),
                            'use_tls': False,
                            'publish_birth_on_connect': True,
                            'rebirth_debounce_ms': 5000,
                            # Device configuration
                            'devices': ['grbl_cnc', 'formlabs_sla', 'bambu_fdm', 'agv_fleet'],
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # ========================================
    # MQTT Adapter (Phase 4)
    # ========================================
    mqtt_group = TimerAction(
        period=8.0,
        actions=[
            GroupAction(
                condition=IfCondition(LaunchConfiguration('enable_mqtt')),
                actions=[
                    LogInfo(msg='Starting MQTT Adapter for IoT...'),

                    Node(
                        package='lego_mcp_edge',
                        executable='mqtt_adapter_node',
                        name='mqtt_adapter',
                        namespace='lego_mcp/scada',
                        parameters=[{
                            'use_sim': LaunchConfiguration('use_sim'),
                            'mqtt_host': LaunchConfiguration('mqtt_host'),
                            'mqtt_port': LaunchConfiguration('mqtt_port'),
                            'client_id': 'lego_mcp_ros2_bridge',
                            'qos': 1,
                            'retain': False,
                            # Topic mappings
                            'ros2_to_mqtt_topics': [
                                '/lego_mcp/equipment/status',
                                '/lego_mcp/production/jobs',
                                '/lego_mcp/safety/estop',
                                '/lego_mcp/analytics/oee',
                            ],
                            'mqtt_to_ros2_topics': [
                                'lego_mcp/commands/#',
                                'lego_mcp/config/#',
                            ],
                        }],
                        output='screen',
                    ),
                ]
            )
        ]
    )

    # ========================================
    # Protocol Bridge Coordinator
    # ========================================
    coordinator_group = TimerAction(
        period=10.0,
        actions=[
            LogInfo(msg='Starting SCADA Bridge Coordinator...'),

            Node(
                package='lego_mcp_edge',
                executable='scada_coordinator_node',
                name='scada_coordinator',
                namespace='lego_mcp/scada',
                parameters=[{
                    'use_sim': LaunchConfiguration('use_sim'),
                    'enable_opcua': LaunchConfiguration('enable_opcua'),
                    'enable_mtconnect': LaunchConfiguration('enable_mtconnect'),
                    'enable_sparkplug': LaunchConfiguration('enable_sparkplug'),
                    'enable_mqtt': LaunchConfiguration('enable_mqtt'),
                    'health_check_interval_sec': 30.0,
                    'reconnect_delay_sec': 5.0,
                }],
                output='screen',
            ),
        ]
    )

    return LaunchDescription([
        # Arguments
        declare_use_sim,
        declare_enable_opcua,
        declare_enable_mtconnect,
        declare_enable_sparkplug,
        declare_enable_mqtt,
        declare_opcua_port,
        declare_mtconnect_port,
        declare_mqtt_host,
        declare_mqtt_port,
        declare_sparkplug_group,
        declare_sparkplug_node,

        # Banner
        LogInfo(msg=''),
        LogInfo(msg='========================================'),
        LogInfo(msg='  LEGO MCP SCADA/MES Bridges'),
        LogInfo(msg='  OPC UA | MTConnect | Sparkplug B'),
        LogInfo(msg='========================================'),
        LogInfo(msg=''),

        # Phased startup
        opcua_group,
        mtconnect_group,
        sparkplug_group,
        mqtt_group,
        coordinator_group,

        # Completion
        TimerAction(
            period=12.0,
            actions=[
                LogInfo(msg=''),
                LogInfo(msg='========================================'),
                LogInfo(msg='  SCADA/MES Bridges Active'),
                LogInfo(msg=''),
                LogInfo(msg='  OPC UA: opc.tcp://localhost:4840'),
                LogInfo(msg='  MTConnect: http://localhost:5000'),
                LogInfo(msg='  Sparkplug: spBv1.0/lego_mcp/#'),
                LogInfo(msg='  MQTT: mqtt://localhost:1883'),
                LogInfo(msg='========================================'),
                LogInfo(msg=''),
            ]
        ),
    ])
