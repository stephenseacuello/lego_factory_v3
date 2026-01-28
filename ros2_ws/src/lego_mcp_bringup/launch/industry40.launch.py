#!/usr/bin/env python3
"""
LEGO MCP Industry 4.0/5.0 Launch Configuration

Complete manufacturing system with:
- Digital Twin synchronization
- OEE metrics collection
- Production scheduling
- Full traceability
- Quality inspection
- AGV fleet management
- Equipment discovery
- Supervision tree

LEGO MCP Manufacturing System v7.0
ISA-95 Compliant Architecture
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    TimerAction,
    RegisterEventHandler,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessStart
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate Industry 4.0/5.0 launch description."""

    # Declare arguments
    declare_namespace = DeclareLaunchArgument(
        'namespace',
        default_value='lego_mcp',
        description='Top-level namespace'
    )

    declare_use_sim = DeclareLaunchArgument(
        'use_sim',
        default_value='true',
        description='Use simulation mode'
    )

    declare_enable_twin = DeclareLaunchArgument(
        'enable_digital_twin',
        default_value='true',
        description='Enable digital twin synchronization'
    )

    declare_enable_scheduler = DeclareLaunchArgument(
        'enable_scheduler',
        default_value='true',
        description='Enable production scheduler'
    )

    declare_enable_traceability = DeclareLaunchArgument(
        'enable_traceability',
        default_value='true',
        description='Enable traceability/digital thread'
    )

    declare_enable_agv = DeclareLaunchArgument(
        'enable_agv',
        default_value='true',
        description='Enable AGV fleet management'
    )

    declare_enable_inspection = DeclareLaunchArgument(
        'enable_inspection',
        default_value='true',
        description='Enable inspection action server'
    )

    declare_enable_supervision = DeclareLaunchArgument(
        'enable_supervision',
        default_value='true',
        description='Enable OTP-style supervision'
    )

    declare_scheduler_algorithm = DeclareLaunchArgument(
        'scheduler_algorithm',
        default_value='hybrid',
        description='Scheduling algorithm: fifo, spt, edd, priority, hybrid'
    )

    declare_sync_rate = DeclareLaunchArgument(
        'twin_sync_rate',
        default_value='10.0',
        description='Digital twin sync rate (Hz)'
    )

    # Get configurations
    namespace = LaunchConfiguration('namespace')
    use_sim = LaunchConfiguration('use_sim')
    enable_twin = LaunchConfiguration('enable_digital_twin')
    enable_scheduler = LaunchConfiguration('enable_scheduler')
    enable_traceability = LaunchConfiguration('enable_traceability')
    enable_agv = LaunchConfiguration('enable_agv')
    enable_inspection = LaunchConfiguration('enable_inspection')
    enable_supervision = LaunchConfiguration('enable_supervision')
    scheduler_algorithm = LaunchConfiguration('scheduler_algorithm')
    sync_rate = LaunchConfiguration('twin_sync_rate')

    # ========== PHASE 1: Core Infrastructure ==========

    # Equipment Registry - Must start first
    equipment_registry_node = Node(
        package='lego_mcp_discovery',
        executable='equipment_registry_node.py',
        name='equipment_registry',
        namespace=namespace,
        parameters=[{
            'scan_interval_sec': 30.0,
            'offline_threshold_sec': 60.0,
            'enable_network_scan': False,
        }],
        output='screen',
    )

    # Heartbeat Monitor - For supervision
    heartbeat_monitor_node = Node(
        package='lego_mcp_supervisor',
        executable='heartbeat_monitor_node.py',
        name='heartbeat_monitor',
        namespace=namespace,
        parameters=[{
            'timeout_ms': 5000,
            'check_interval_ms': 1000,
            'missed_threshold': 3,
        }],
        output='screen',
        condition=IfCondition(enable_supervision),
    )

    # ========== PHASE 2: Digital Twin & Metrics ==========

    # Digital Twin Node
    digital_twin_node = Node(
        package='lego_mcp_orchestrator',
        executable='digital_twin_node.py',
        name='digital_twin',
        namespace=namespace,
        parameters=[{
            'twin_id': 'lego_mcp_factory_twin',
            'factory_cell_id': 'CELL-001',
            'sync_rate_hz': sync_rate,
            'oee_calculation_interval_sec': 60.0,
            'state_history_size': 1000,
            'enable_pinn_predictions': False,
        }],
        output='screen',
        condition=IfCondition(enable_twin),
    )

    # ========== PHASE 3: Production Management ==========

    # Production Scheduler
    production_scheduler_node = Node(
        package='lego_mcp_orchestrator',
        executable='production_scheduler_node.py',
        name='production_scheduler',
        namespace=namespace,
        parameters=[{
            'algorithm': scheduler_algorithm,
            'reschedule_interval_sec': 30.0,
            'lookahead_horizon_sec': 3600.0,
            'max_jobs_in_schedule': 100,
            'enable_preemption': False,
        }],
        output='screen',
        condition=IfCondition(enable_scheduler),
    )

    # Work Order Executor
    work_order_executor_node = Node(
        package='lego_mcp_orchestrator',
        executable='work_order_executor.py',
        name='work_order_executor',
        namespace=namespace,
        parameters=[{
            'feedback_rate_hz': 2.0,
            'operation_timeout_sec': 3600.0,
            'quality_gate_enabled': True,
            'material_tracking_enabled': True,
        }],
        output='screen',
    )

    # Traceability Node
    traceability_node = Node(
        package='lego_mcp_orchestrator',
        executable='traceability_node.py',
        name='traceability',
        namespace=namespace,
        parameters=[{
            'storage_backend': 'memory',
            'enable_hash_chain': True,
            'enable_signatures': False,
            'retention_days': 2555,  # 7 years
            'serial_prefix': 'LEGO-MCP',
        }],
        output='screen',
        condition=IfCondition(enable_traceability),
    )

    # ========== PHASE 4: Quality & Inspection ==========

    # Inspection Action Server
    inspection_server_node = Node(
        package='lego_mcp_orchestrator',
        executable='inspection_action_server.py',
        name='inspection_server',
        namespace=namespace,
        parameters=[{
            'feedback_rate_hz': 5.0,
            'measurement_timeout_sec': 30.0,
            'enable_ai_detection': True,
            'camera_topic': '/vision/image_raw',
        }],
        output='screen',
        condition=IfCondition(enable_inspection),
    )

    # ========== PHASE 5: Material Handling ==========

    # AGV Dispatcher
    agv_dispatcher_node = Node(
        package='lego_mcp_orchestrator',
        executable='agv_dispatcher.py',
        name='agv_dispatcher',
        namespace=namespace,
        parameters=[{
            'feedback_rate_hz': 10.0,
            'max_velocity_ms': 0.5,
            'position_tolerance_m': 0.05,
            'orientation_tolerance_rad': 0.1,
            'battery_low_threshold': 20.0,
            'enable_traffic_management': True,
        }],
        output='screen',
        condition=IfCondition(enable_agv),
    )

    # ========== PHASE 6: Equipment Simulators (if sim mode) ==========

    # GRBL CNC Simulator
    grbl_simulator = Node(
        package='lego_mcp_simulation',
        executable='grbl_simulator',
        name='grbl_simulator',
        namespace=namespace,
        parameters=[{
            'machine_type': 'tinyg',
            'machine_name': 'grbl_cnc',
            'simulate_delays': True,
        }],
        output='screen',
        condition=IfCondition(use_sim),
    )

    # Formlabs SLA Simulator
    formlabs_simulator = Node(
        package='lego_mcp_simulation',
        executable='formlabs_simulator',
        name='formlabs_simulator',
        namespace=namespace,
        parameters=[{
            'printer_name': 'formlabs_sla',
            'layer_time_s': 2.0,
            'heating_time_s': 30.0,
            'filling_time_s': 10.0,
        }],
        output='screen',
        condition=IfCondition(use_sim),
    )

    # Bambu FDM Simulator
    bambu_simulator = Node(
        package='lego_mcp_simulation',
        executable='bambu_simulator',
        name='bambu_simulator',
        namespace=namespace,
        parameters=[{
            'printer_name': 'bambu_fdm',
            'simulate_ams': True,
        }],
        output='screen',
        condition=IfCondition(use_sim),
    )

    # ========== PHASE 7: Supervision (delayed start) ==========

    # OTP Supervisor - starts after other nodes
    supervisor_node = TimerAction(
        period=5.0,  # Wait 5 seconds for other nodes
        actions=[
            Node(
                package='lego_mcp_supervisor',
                executable='supervisor_node.py',
                name='root_supervisor',
                namespace=namespace,
                parameters=[{
                    'config_file': PathJoinSubstitution([
                        FindPackageShare('lego_mcp_supervisor'),
                        'config',
                        'supervision_tree.yaml'
                    ]),
                }],
                output='screen',
            )
        ],
        condition=IfCondition(enable_supervision),
    )

    # ========== Build Launch Description ==========

    return LaunchDescription([
        # Arguments
        declare_namespace,
        declare_use_sim,
        declare_enable_twin,
        declare_enable_scheduler,
        declare_enable_traceability,
        declare_enable_agv,
        declare_enable_inspection,
        declare_enable_supervision,
        declare_scheduler_algorithm,
        declare_sync_rate,

        # Phase 1: Infrastructure
        equipment_registry_node,
        heartbeat_monitor_node,

        # Phase 2: Digital Twin
        digital_twin_node,

        # Phase 3: Production
        production_scheduler_node,
        work_order_executor_node,
        traceability_node,

        # Phase 4: Quality
        inspection_server_node,

        # Phase 5: Material Handling
        agv_dispatcher_node,

        # Phase 6: Simulators (conditional)
        grbl_simulator,
        formlabs_simulator,
        bambu_simulator,

        # Phase 7: Supervision
        supervisor_node,
    ])
