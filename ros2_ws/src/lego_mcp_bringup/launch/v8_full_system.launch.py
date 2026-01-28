#!/usr/bin/env python3
"""
LEGO MCP v8.0 Full System Launch File

Launches the complete DoD/ONR-class manufacturing system including:
- Safety-certified nodes (C++ MISRA compliant)
- Equipment control nodes
- Digital twin synchronization
- AI/ML inference nodes
- Command center integration
- Security monitoring

Author: LEGO MCP ROS2 Engineering
Reference: IEC 61508 SIL 2+
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    GroupAction,
    TimerAction,
    SetEnvironmentVariable,
    LogInfo,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import (
    LaunchConfiguration,
    PythonExpression,
    PathJoinSubstitution,
    EnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, SetParameter
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate the launch description for LEGO MCP v8.0."""

    # ==========================================================================
    # Launch Arguments
    # ==========================================================================

    # Environment
    declare_env_arg = DeclareLaunchArgument(
        'environment',
        default_value='production',
        description='Deployment environment (development, staging, production)'
    )

    # Safety features
    declare_safety_enabled_arg = DeclareLaunchArgument(
        'safety_enabled',
        default_value='true',
        description='Enable safety-certified nodes'
    )

    # Security features
    declare_security_enabled_arg = DeclareLaunchArgument(
        'security_enabled',
        default_value='true',
        description='Enable ROS2 security (SROS2)'
    )

    # Digital twin
    declare_twin_enabled_arg = DeclareLaunchArgument(
        'digital_twin_enabled',
        default_value='true',
        description='Enable PINN digital twin nodes'
    )

    # AI/ML
    declare_ai_enabled_arg = DeclareLaunchArgument(
        'ai_enabled',
        default_value='true',
        description='Enable AI/ML inference nodes'
    )

    # Simulation mode
    declare_simulation_arg = DeclareLaunchArgument(
        'simulation',
        default_value='false',
        description='Run in simulation mode (no real hardware)'
    )

    # Log level
    declare_log_level_arg = DeclareLaunchArgument(
        'log_level',
        default_value='INFO',
        description='Logging level'
    )

    # Get configurations
    environment = LaunchConfiguration('environment')
    safety_enabled = LaunchConfiguration('safety_enabled')
    security_enabled = LaunchConfiguration('security_enabled')
    digital_twin_enabled = LaunchConfiguration('digital_twin_enabled')
    ai_enabled = LaunchConfiguration('ai_enabled')
    simulation = LaunchConfiguration('simulation')
    log_level = LaunchConfiguration('log_level')

    # ==========================================================================
    # Environment Variables
    # ==========================================================================

    set_ros_domain = SetEnvironmentVariable(
        name='ROS_DOMAIN_ID',
        value=EnvironmentVariable('ROS_DOMAIN_ID', default_value='42')
    )

    set_rmw = SetEnvironmentVariable(
        name='RMW_IMPLEMENTATION',
        value='rmw_cyclonedds_cpp'
    )

    # ==========================================================================
    # Safety-Certified Nodes (IEC 61508 SIL 2+)
    # ==========================================================================

    safety_nodes = GroupAction(
        condition=IfCondition(safety_enabled),
        actions=[
            LogInfo(msg='Starting safety-certified nodes (SIL 2+)...'),

            # Dual-Channel E-Stop Node
            Node(
                package='lego_mcp_safety_certified',
                executable='safety_node',
                name='safety_node',
                namespace='safety',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'watchdog_timeout_ms': 50,
                    'dual_channel_enabled': True,
                    'cross_monitoring_enabled': True,
                    'sil_level': 2,
                }],
                respawn=True,
                respawn_delay=1.0,
                arguments=['--ros-args', '--log-level', log_level],
            ),

            # Safety Relay Controller
            Node(
                package='lego_mcp_safety_certified',
                executable='relay_controller',
                name='relay_controller',
                namespace='safety',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'relay_count': 4,
                    'fail_safe_mode': 'open',
                }],
                respawn=True,
                respawn_delay=0.5,
            ),

            # Watchdog Timer
            Node(
                package='lego_mcp_safety_certified',
                executable='watchdog_timer',
                name='watchdog_timer',
                namespace='safety',
                output='screen',
                parameters=[{
                    'timeout_ms': 100,
                    'monitored_nodes': [
                        'safety_node',
                        'relay_controller',
                        'equipment_controller',
                    ],
                }],
                respawn=True,
            ),
        ]
    )

    # ==========================================================================
    # Equipment Control Nodes
    # ==========================================================================

    equipment_nodes = GroupAction(
        actions=[
            LogInfo(msg='Starting equipment control nodes...'),

            # Equipment Controller
            Node(
                package='lego_mcp_equipment',
                executable='equipment_controller',
                name='equipment_controller',
                namespace='equipment',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'control_rate_hz': 100,
                }],
            ),

            # CNC Controller
            Node(
                package='lego_mcp_equipment',
                executable='cnc_controller',
                name='cnc_controller',
                namespace='equipment/cnc',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'spindle_max_rpm': 12000,
                    'feed_rate_max': 5000,
                }],
            ),

            # Robot Arm Controller
            Node(
                package='lego_mcp_equipment',
                executable='robot_arm_controller',
                name='robot_arm_controller',
                namespace='equipment/robot',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'arm_count': 2,
                    'motion_planner': 'RRTConnect',
                }],
            ),

            # 3D Printer Controller
            Node(
                package='lego_mcp_equipment',
                executable='printer_controller',
                name='printer_controller',
                namespace='equipment/printer',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'printer_type': 'fdm',
                }],
            ),

            # Injection Molding Controller
            Node(
                package='lego_mcp_equipment',
                executable='injection_controller',
                name='injection_controller',
                namespace='equipment/injection',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'max_pressure_bar': 2000,
                    'max_temp_celsius': 300,
                }],
            ),
        ]
    )

    # ==========================================================================
    # Digital Twin Nodes
    # ==========================================================================

    digital_twin_nodes = GroupAction(
        condition=IfCondition(digital_twin_enabled),
        actions=[
            LogInfo(msg='Starting digital twin nodes...'),

            # PINN Thermal Twin
            Node(
                package='lego_mcp_digital_twin',
                executable='pinn_thermal_node',
                name='pinn_thermal_node',
                namespace='twin',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'model_path': '/models/pinn/thermal',
                    'inference_device': 'cuda',
                    'update_rate_hz': 10,
                }],
            ),

            # PINN Structural Twin
            Node(
                package='lego_mcp_digital_twin',
                executable='pinn_structural_node',
                name='pinn_structural_node',
                namespace='twin',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'model_path': '/models/pinn/structural',
                }],
            ),

            # State Synchronizer
            Node(
                package='lego_mcp_digital_twin',
                executable='state_synchronizer',
                name='state_synchronizer',
                namespace='twin',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'sync_rate_hz': 100,
                    'drift_threshold': 0.01,
                }],
            ),

            # ISO 23247 OME Manager
            Node(
                package='lego_mcp_digital_twin',
                executable='ome_manager',
                name='ome_manager',
                namespace='twin',
                output='screen',
                parameters=[{
                    'ontology_path': '/config/twin_ontology.jsonld',
                }],
            ),
        ]
    )

    # ==========================================================================
    # AI/ML Nodes
    # ==========================================================================

    ai_nodes = GroupAction(
        condition=IfCondition(ai_enabled),
        actions=[
            LogInfo(msg='Starting AI/ML inference nodes...'),

            # Predictive Maintenance
            Node(
                package='lego_mcp_ai',
                executable='predictive_maintenance_node',
                name='predictive_maintenance',
                namespace='ai',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'model_path': '/models/predictive',
                    'prediction_horizon_hours': 168,
                }],
            ),

            # Quality Predictor
            Node(
                package='lego_mcp_ai',
                executable='quality_predictor_node',
                name='quality_predictor',
                namespace='ai',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'confidence_threshold': 0.85,
                }],
            ),

            # Anomaly Detector
            Node(
                package='lego_mcp_ai',
                executable='anomaly_detector_node',
                name='anomaly_detector',
                namespace='ai',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'sensitivity': 0.8,
                }],
            ),

            # Causal Discovery
            Node(
                package='lego_mcp_ai',
                executable='causal_discovery_node',
                name='causal_discovery',
                namespace='ai',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'algorithm': 'PC',
                    'alpha': 0.05,
                }],
            ),

            # AI Guardrails
            Node(
                package='lego_mcp_ai',
                executable='guardrails_node',
                name='guardrails',
                namespace='ai',
                output='screen',
                parameters=[{
                    'human_in_loop_threshold': 0.7,
                    'safety_filter_enabled': True,
                }],
            ),
        ]
    )

    # ==========================================================================
    # Quality Control Nodes
    # ==========================================================================

    quality_nodes = GroupAction(
        actions=[
            LogInfo(msg='Starting quality control nodes...'),

            # Vision Inspection
            Node(
                package='lego_mcp_quality',
                executable='vision_inspection_node',
                name='vision_inspection',
                namespace='quality',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'camera_count': 4,
                    'inference_device': 'cuda',
                }],
            ),

            # SPC Monitor
            Node(
                package='lego_mcp_quality',
                executable='spc_monitor_node',
                name='spc_monitor',
                namespace='quality',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'control_chart_type': 'XbarR',
                }],
            ),

            # Dimensional Measurement
            Node(
                package='lego_mcp_quality',
                executable='dimensional_node',
                name='dimensional_measurement',
                namespace='quality',
                output='screen',
                parameters=[{
                    'use_sim_time': simulation,
                    'tolerance_microns': 10,
                }],
            ),
        ]
    )

    # ==========================================================================
    # Bridge Nodes
    # ==========================================================================

    bridge_nodes = GroupAction(
        actions=[
            LogInfo(msg='Starting bridge nodes...'),

            # Dashboard Bridge
            Node(
                package='lego_mcp_bridge',
                executable='dashboard_bridge',
                name='dashboard_bridge',
                namespace='bridge',
                output='screen',
                parameters=[{
                    'dashboard_url': 'http://localhost:5000',
                    'websocket_enabled': True,
                }],
            ),

            # OPC-UA Bridge
            Node(
                package='lego_mcp_bridge',
                executable='opcua_bridge',
                name='opcua_bridge',
                namespace='bridge',
                output='screen',
                parameters=[{
                    'server_url': 'opc.tcp://localhost:4840',
                }],
            ),

            # MTConnect Adapter
            Node(
                package='lego_mcp_bridge',
                executable='mtconnect_adapter',
                name='mtconnect_adapter',
                namespace='bridge',
                output='screen',
                parameters=[{
                    'adapter_port': 7878,
                }],
            ),
        ]
    )

    # ==========================================================================
    # Security Monitoring (delayed start)
    # ==========================================================================

    security_nodes = TimerAction(
        period=5.0,  # Start 5 seconds after other nodes
        actions=[
            GroupAction(
                condition=IfCondition(security_enabled),
                actions=[
                    LogInfo(msg='Starting security monitoring nodes...'),

                    # Security Monitor
                    Node(
                        package='lego_mcp_security',
                        executable='security_monitor_node',
                        name='security_monitor',
                        namespace='security',
                        output='screen',
                        parameters=[{
                            'anomaly_detection_enabled': True,
                            'audit_logging_enabled': True,
                        }],
                    ),
                ]
            ),
        ]
    )

    # ==========================================================================
    # Launch Description
    # ==========================================================================

    return LaunchDescription([
        # Arguments
        declare_env_arg,
        declare_safety_enabled_arg,
        declare_security_enabled_arg,
        declare_twin_enabled_arg,
        declare_ai_enabled_arg,
        declare_simulation_arg,
        declare_log_level_arg,

        # Environment
        set_ros_domain,
        set_rmw,

        # Startup message
        LogInfo(msg='===== LEGO MCP v8.0 Full System Launch ====='),
        LogInfo(msg=['Environment: ', environment]),
        LogInfo(msg=['Safety Enabled: ', safety_enabled]),
        LogInfo(msg=['Digital Twin Enabled: ', digital_twin_enabled]),
        LogInfo(msg=['AI/ML Enabled: ', ai_enabled]),
        LogInfo(msg='============================================'),

        # Node groups (in startup order)
        safety_nodes,          # Safety first
        equipment_nodes,       # Equipment control
        quality_nodes,         # Quality monitoring
        digital_twin_nodes,    # Digital twin
        ai_nodes,              # AI/ML inference
        bridge_nodes,          # Integration bridges
        security_nodes,        # Security (delayed)
    ])
