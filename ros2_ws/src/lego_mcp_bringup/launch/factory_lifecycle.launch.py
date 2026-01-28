"""
LEGO MCP Factory Cell Lifecycle Launch File

Launches all equipment nodes with ROS2 Lifecycle management for deterministic
startup/shutdown ordering. Uses lifecycle_manager for coordinated state transitions.

Industry 4.0/5.0 Architecture - ISA-95 Compliant Layered Startup:
1. Safety nodes (L1) - Must be active before any equipment
2. Equipment nodes (L0) - Hardware interfaces
3. Supervisory nodes (L2) - Orchestrator, AGV fleet
4. SCADA bridges (L3) - Optional MES/OPC UA integration

Each lifecycle node transitions through: unconfigured -> inactive -> active
"""

import os
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    EmitEvent,
    RegisterEventHandler,
    TimerAction,
    LogInfo,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessStart
from launch.events import matches_action
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node, LifecycleNode, PushRosNamespace
from launch_ros.events.lifecycle import ChangeState
from launch_ros.event_handlers import OnStateTransition
from lifecycle_msgs.msg import Transition
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description with lifecycle-managed nodes."""

    # Get package directories
    bringup_dir = get_package_share_directory('lego_mcp_bringup')

    # ===========================================================================
    # LAUNCH ARGUMENTS
    # ===========================================================================

    use_sim = LaunchConfiguration('use_sim', default='true')
    use_ned2 = LaunchConfiguration('use_ned2', default='false')
    use_xarm = LaunchConfiguration('use_xarm', default='false')
    use_cnc = LaunchConfiguration('use_cnc', default='false')
    use_laser = LaunchConfiguration('use_laser', default='false')
    use_formlabs = LaunchConfiguration('use_formlabs', default='false')
    enable_supervisor = LaunchConfiguration('enable_supervisor', default='true')
    enable_scada = LaunchConfiguration('enable_scada', default='false')
    auto_configure = LaunchConfiguration('auto_configure', default='true')
    auto_activate = LaunchConfiguration('auto_activate', default='true')

    # Declare arguments
    declare_arguments = [
        DeclareLaunchArgument(
            'use_sim',
            default_value='true',
            description='Use simulation mode (no real hardware)'
        ),
        DeclareLaunchArgument(
            'use_ned2',
            default_value='false',
            description='Launch Niryo Ned2 robot'
        ),
        DeclareLaunchArgument(
            'use_xarm',
            default_value='false',
            description='Launch xArm 6 Lite robot'
        ),
        DeclareLaunchArgument(
            'use_cnc',
            default_value='false',
            description='Launch CNC equipment nodes'
        ),
        DeclareLaunchArgument(
            'use_laser',
            default_value='false',
            description='Launch laser equipment nodes'
        ),
        DeclareLaunchArgument(
            'use_formlabs',
            default_value='false',
            description='Launch Formlabs SLA printer'
        ),
        DeclareLaunchArgument(
            'enable_supervisor',
            default_value='true',
            description='Enable OTP-style supervisor node'
        ),
        DeclareLaunchArgument(
            'enable_scada',
            default_value='false',
            description='Enable SCADA/MES bridges (OPC UA, MTConnect)'
        ),
        DeclareLaunchArgument(
            'auto_configure',
            default_value='true',
            description='Automatically configure lifecycle nodes on startup'
        ),
        DeclareLaunchArgument(
            'auto_activate',
            default_value='true',
            description='Automatically activate lifecycle nodes after configure'
        ),
    ]

    # Configuration files
    equipment_params = os.path.join(bringup_dir, 'config', 'equipment_params.yaml')

    # ===========================================================================
    # LAYER 1: SAFETY NODES (MUST START FIRST)
    # ISA-95 Level 1 - Control
    # ===========================================================================

    safety_lifecycle_node = LifecycleNode(
        package='lego_mcp_safety',
        executable='safety_node.py',
        name='safety_lifecycle_node',
        namespace='safety',
        parameters=[{
            'simulation_mode': use_sim,
            'watchdog_timeout_ms': 500,
            'heartbeat_sources': ['orchestrator'],
        }],
        output='screen',
        emulate_tty=True,
    )

    # Event handler: Configure safety node on start
    configure_safety = RegisterEventHandler(
        OnProcessStart(
            target_action=safety_lifecycle_node,
            on_start=[
                LogInfo(msg="Safety lifecycle node starting - configuring..."),
                TimerAction(
                    period=1.0,
                    actions=[
                        EmitEvent(
                            event=ChangeState(
                                lifecycle_node_matcher=matches_action(safety_lifecycle_node),
                                transition_id=Transition.TRANSITION_CONFIGURE,
                            )
                        ),
                    ],
                ),
            ],
        ),
        condition=IfCondition(auto_configure),
    )

    # Event handler: Activate safety node after configure
    activate_safety = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=safety_lifecycle_node,
            goal_state='inactive',
            entities=[
                LogInfo(msg="Safety node configured - activating..."),
                TimerAction(
                    period=0.5,
                    actions=[
                        EmitEvent(
                            event=ChangeState(
                                lifecycle_node_matcher=matches_action(safety_lifecycle_node),
                                transition_id=Transition.TRANSITION_ACTIVATE,
                            )
                        ),
                    ],
                ),
            ],
        ),
        condition=IfCondition(auto_activate),
    )

    # ===========================================================================
    # LAYER 2: ORCHESTRATOR (LIFECYCLE-MANAGED)
    # ISA-95 Level 2 - Supervisory
    # ===========================================================================

    orchestrator_lifecycle_node = LifecycleNode(
        package='lego_mcp_orchestrator',
        executable='orchestrator_lifecycle_node.py',
        name='lego_mcp_orchestrator',
        namespace='',
        parameters=[{
            'auto_start_dispatch': True,
            'heartbeat_rate_hz': 10.0,
            'dispatch_rate_hz': 1.0,
        }],
        output='screen',
        emulate_tty=True,
    )

    # Configure orchestrator after safety is active
    configure_orchestrator = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=safety_lifecycle_node,
            goal_state='active',
            entities=[
                LogInfo(msg="Safety active - configuring orchestrator..."),
                TimerAction(
                    period=1.0,
                    actions=[
                        EmitEvent(
                            event=ChangeState(
                                lifecycle_node_matcher=matches_action(orchestrator_lifecycle_node),
                                transition_id=Transition.TRANSITION_CONFIGURE,
                            )
                        ),
                    ],
                ),
            ],
        ),
        condition=IfCondition(auto_configure),
    )

    # Activate orchestrator after configure
    activate_orchestrator = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=orchestrator_lifecycle_node,
            goal_state='inactive',
            entities=[
                LogInfo(msg="Orchestrator configured - activating..."),
                TimerAction(
                    period=0.5,
                    actions=[
                        EmitEvent(
                            event=ChangeState(
                                lifecycle_node_matcher=matches_action(orchestrator_lifecycle_node),
                                transition_id=Transition.TRANSITION_ACTIVATE,
                            )
                        ),
                    ],
                ),
            ],
        ),
        condition=IfCondition(auto_activate),
    )

    # ===========================================================================
    # LAYER 2: OTP-STYLE SUPERVISOR
    # ===========================================================================

    supervisor_node = Node(
        condition=IfCondition(enable_supervisor),
        package='lego_mcp_supervisor',
        executable='supervisor_node.py',
        name='lego_mcp_supervisor',
        parameters=[{
            'strategy': 'ONE_FOR_ONE',
            'max_restarts': 3,
            'restart_window': 60.0,
            'heartbeat_timeout': 5.0,
            'check_interval': 1.0,
        }],
        output='screen',
    )

    # ===========================================================================
    # LAYER 0: EQUIPMENT NODES (NON-LIFECYCLE FOR NOW)
    # ISA-95 Level 0 - Field Devices
    # ===========================================================================

    # CNC Node
    cnc_node = Node(
        condition=IfCondition(use_cnc),
        package='grbl_ros2',
        executable='tinyg_node.py',
        name='bantam_cnc',
        namespace='cnc',
        parameters=[equipment_params],
        output='screen',
    )

    # Laser Node
    laser_node = Node(
        condition=IfCondition(use_laser),
        package='grbl_ros2',
        executable='grbl_node.py',
        name='mks_laser',
        namespace='laser',
        parameters=[equipment_params],
        output='screen',
    )

    # Formlabs SLA
    formlabs_node = Node(
        condition=IfCondition(use_formlabs),
        package='formlabs_ros2',
        executable='formlabs_node.py',
        name='formlabs_printer',
        namespace='formlabs',
        parameters=[equipment_params],
        output='screen',
    )

    # ===========================================================================
    # SUPPORT NODES
    # ===========================================================================

    # ROS Bridge for Flask integration
    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=[{
            'port': 9090,
            'address': '0.0.0.0',
        }],
        output='screen',
    )

    # Failure detector
    failure_detector_node = Node(
        package='lego_mcp_orchestrator',
        executable='failure_detector_node.py',
        name='failure_detector',
        output='screen',
    )

    # Recovery engine
    recovery_engine_node = Node(
        package='lego_mcp_orchestrator',
        executable='recovery_engine_node.py',
        name='recovery_engine',
        output='screen',
    )

    # ===========================================================================
    # LAUNCH DESCRIPTION
    # ===========================================================================

    return LaunchDescription([
        # Arguments
        *declare_arguments,

        # Startup log
        LogInfo(msg="=== LEGO MCP Factory Cell (Lifecycle Mode) ==="),
        LogInfo(msg="Starting with deterministic ISA-95 layered startup..."),

        # LAYER 1: Safety (first)
        safety_lifecycle_node,
        configure_safety,
        activate_safety,

        # LAYER 2: Orchestrator (after safety)
        orchestrator_lifecycle_node,
        configure_orchestrator,
        activate_orchestrator,

        # LAYER 2: Supervisor
        supervisor_node,

        # LAYER 0: Equipment (start in parallel after orchestrator)
        cnc_node,
        laser_node,
        formlabs_node,

        # Support nodes
        rosbridge_node,
        failure_detector_node,
        recovery_engine_node,

        # Final log
        LogInfo(msg="=== Factory cell launch sequence initiated ==="),
    ])
