"""
LEGO MCP Factory Cell Launch File
Launches all equipment nodes, orchestrator, and rosbridge for full production.
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, GroupAction
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Get package directories
    bringup_dir = get_package_share_directory('lego_mcp_bringup')

    # Launch arguments
    use_sim = LaunchConfiguration('use_sim', default='false')
    use_ned2 = LaunchConfiguration('use_ned2', default='true')
    use_xarm = LaunchConfiguration('use_xarm', default='true')
    use_cnc = LaunchConfiguration('use_cnc', default='true')
    use_laser = LaunchConfiguration('use_laser', default='true')
    use_formlabs = LaunchConfiguration('use_formlabs', default='true')
    use_coastrunner = LaunchConfiguration('use_coastrunner', default='true')
    enable_moveit = LaunchConfiguration('enable_moveit', default='true')

    # Declare launch arguments
    declare_use_sim = DeclareLaunchArgument(
        'use_sim',
        default_value='false',
        description='Use simulation instead of real hardware'
    )

    declare_use_ned2 = DeclareLaunchArgument(
        'use_ned2',
        default_value='true',
        description='Launch Niryo Ned2 robot'
    )

    declare_use_xarm = DeclareLaunchArgument(
        'use_xarm',
        default_value='true',
        description='Launch xArm 6 Lite robot'
    )

    declare_use_cnc = DeclareLaunchArgument(
        'use_cnc',
        default_value='true',
        description='Launch TinyG Bantam CNC'
    )

    declare_use_laser = DeclareLaunchArgument(
        'use_laser',
        default_value='true',
        description='Launch MKS Laser Engraver'
    )

    declare_use_formlabs = DeclareLaunchArgument(
        'use_formlabs',
        default_value='true',
        description='Launch Formlabs SLA printer'
    )

    declare_use_coastrunner = DeclareLaunchArgument(
        'use_coastrunner',
        default_value='true',
        description='Launch Coastrunner CR-1'
    )

    declare_enable_moveit = DeclareLaunchArgument(
        'enable_moveit',
        default_value='true',
        description='Enable MoveIt2 motion planning'
    )

    # Configuration files
    cell_layout_config = os.path.join(bringup_dir, 'config', 'cell_layout.yaml')
    equipment_params = os.path.join(bringup_dir, 'config', 'equipment_params.yaml')

    # ==========================================================================
    # CORE NODES
    # ==========================================================================

    # Safety node (always required)
    safety_node = Node(
        package='lego_mcp_safety',
        executable='safety_node',
        name='safety_node',
        parameters=[equipment_params],
        output='screen',
        emulate_tty=True,
    )

    # Main orchestrator
    orchestrator_node = Node(
        package='lego_mcp_orchestrator',
        executable='orchestrator_node',
        name='lego_mcp_orchestrator',
        parameters=[
            cell_layout_config,
            equipment_params,
        ],
        output='screen',
        emulate_tty=True,
    )

    # Digital twin sync node
    twin_sync_node = Node(
        package='lego_mcp_orchestrator',
        executable='twin_sync_node',
        name='twin_sync',
        parameters=[equipment_params],
        output='screen',
    )

    # AR guidance publisher
    ar_publisher_node = Node(
        package='lego_mcp_orchestrator',
        executable='ar_publisher_node',
        name='ar_publisher',
        output='screen',
    )

    # ==========================================================================
    # ROSBRIDGE (for Flask integration)
    # ==========================================================================

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

    # TF2 web republisher for AR
    tf2_web_republisher = Node(
        package='tf2_web_republisher',
        executable='tf2_web_republisher',
        name='tf2_web_republisher',
        output='screen',
    )

    # ==========================================================================
    # ROBOT ARMS
    # ==========================================================================

    # Niryo Ned2
    ned2_group = GroupAction(
        condition=IfCondition(use_ned2),
        actions=[
            PushRosNamespace('ned2'),
            # In production, would include ned2_driver launch here
            # For now, use our custom node
            Node(
                package='lego_mcp_orchestrator',
                executable='robot_interface_node',
                name='ned2_interface',
                parameters=[equipment_params],
                remappings=[
                    ('joint_states', '/ned2/joint_states'),
                    ('gripper/command', '/ned2/gripper/command'),
                ],
                output='screen',
            ),
        ]
    )

    # xArm 6 Lite
    xarm_group = GroupAction(
        condition=IfCondition(use_xarm),
        actions=[
            PushRosNamespace('xarm'),
            Node(
                package='lego_mcp_orchestrator',
                executable='robot_interface_node',
                name='xarm_interface',
                parameters=[equipment_params],
                remappings=[
                    ('joint_states', '/xarm/joint_states'),
                    ('gripper/command', '/xarm/gripper/command'),
                ],
                output='screen',
            ),
        ]
    )

    # ==========================================================================
    # GRBL EQUIPMENT (CNC, Laser)
    # ==========================================================================

    # TinyG Bantam CNC
    cnc_node = Node(
        condition=IfCondition(use_cnc),
        package='grbl_ros2',
        executable='tinyg_node',
        name='bantam_cnc',
        namespace='cnc',
        parameters=[equipment_params],
        output='screen',
    )

    # MKS Laser Engraver
    laser_node = Node(
        condition=IfCondition(use_laser),
        package='grbl_ros2',
        executable='grbl_node',
        name='mks_laser',
        namespace='laser',
        parameters=[equipment_params],
        output='screen',
    )

    # Coastrunner CR-1
    coastrunner_node = Node(
        condition=IfCondition(use_coastrunner),
        package='grbl_ros2',
        executable='grbl_node',
        name='coastrunner',
        namespace='coastrunner',
        parameters=[equipment_params],
        output='screen',
    )

    # ==========================================================================
    # 3D PRINTERS
    # ==========================================================================

    # Formlabs SLA
    formlabs_node = Node(
        condition=IfCondition(use_formlabs),
        package='formlabs_ros2',
        executable='formlabs_node',
        name='formlabs_printer',
        namespace='formlabs',
        parameters=[equipment_params],
        output='screen',
    )

    # ==========================================================================
    # VISION SYSTEM
    # ==========================================================================

    vision_node = Node(
        package='lego_mcp_vision',
        executable='camera_node',
        name='vision_system',
        namespace='vision',
        parameters=[equipment_params],
        output='screen',
    )

    quality_feedback_node = Node(
        package='lego_mcp_orchestrator',
        executable='quality_feedback_node',
        name='quality_feedback',
        output='screen',
    )

    # ==========================================================================
    # FAILURE RECOVERY
    # ==========================================================================

    failure_detector_node = Node(
        package='lego_mcp_orchestrator',
        executable='failure_detector_node',
        name='failure_detector',
        output='screen',
    )

    recovery_engine_node = Node(
        package='lego_mcp_orchestrator',
        executable='recovery_engine_node',
        name='recovery_engine',
        output='screen',
    )

    # ==========================================================================
    # MOVEIT2 (Motion Planning)
    # ==========================================================================

    # MoveIt2 launch would be included here
    # moveit_launch = IncludeLaunchDescription(
    #     PythonLaunchDescriptionSource([
    #         FindPackageShare('lego_mcp_moveit_config'),
    #         '/launch/move_group.launch.py'
    #     ]),
    #     condition=IfCondition(enable_moveit),
    # )

    # ==========================================================================
    # ASSEMBLE LAUNCH DESCRIPTION
    # ==========================================================================

    return LaunchDescription([
        # Arguments
        declare_use_sim,
        declare_use_ned2,
        declare_use_xarm,
        declare_use_cnc,
        declare_use_laser,
        declare_use_formlabs,
        declare_use_coastrunner,
        declare_enable_moveit,

        # Core nodes
        safety_node,
        orchestrator_node,
        twin_sync_node,
        ar_publisher_node,

        # Communication bridge
        rosbridge_node,
        # tf2_web_republisher,  # Uncomment when tf2_web_republisher is available

        # Equipment nodes
        ned2_group,
        xarm_group,
        cnc_node,
        laser_node,
        coastrunner_node,
        formlabs_node,

        # Vision and quality
        vision_node,
        quality_feedback_node,

        # Failure handling
        failure_detector_node,
        recovery_engine_node,

        # MoveIt2
        # moveit_launch,
    ])
