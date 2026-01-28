"""
LEGO MCP Simulation Launch File
Launches simulated equipment for testing without hardware.
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Get package directories
    bringup_dir = get_package_share_directory('lego_mcp_bringup')

    # Configuration files
    cell_layout_config = os.path.join(bringup_dir, 'config', 'cell_layout.yaml')
    equipment_params = os.path.join(bringup_dir, 'config', 'equipment_params.yaml')

    # Launch arguments
    use_rviz = LaunchConfiguration('use_rviz', default='true')

    declare_use_rviz = DeclareLaunchArgument(
        'use_rviz',
        default_value='true',
        description='Launch RViz for visualization'
    )

    # ==========================================================================
    # SIMULATED EQUIPMENT NODES
    # ==========================================================================

    # Simulated Niryo Ned2
    sim_ned2_node = Node(
        package='lego_mcp_simulation',
        executable='robot_simulator',
        name='ned2_sim',
        namespace='ned2',
        parameters=[{
            'robot_type': 'ned2',
            'joint_count': 6,
            'simulation_rate': 100.0,
        }],
        output='screen',
    )

    # Simulated xArm
    sim_xarm_node = Node(
        package='lego_mcp_simulation',
        executable='robot_simulator',
        name='xarm_sim',
        namespace='xarm',
        parameters=[{
            'robot_type': 'xarm_lite6',
            'joint_count': 6,
            'simulation_rate': 100.0,
        }],
        output='screen',
    )

    # Simulated GRBL CNC
    sim_cnc_node = Node(
        package='lego_mcp_simulation',
        executable='grbl_simulator',
        name='cnc_sim',
        namespace='cnc',
        parameters=[{
            'machine_type': 'tinyg',
            'x_max': 150.0,
            'y_max': 120.0,
            'z_max': 50.0,
        }],
        output='screen',
    )

    # Simulated Laser
    sim_laser_node = Node(
        package='lego_mcp_simulation',
        executable='grbl_simulator',
        name='laser_sim',
        namespace='laser',
        parameters=[{
            'machine_type': 'grbl_laser',
            'x_max': 300.0,
            'y_max': 300.0,
            'has_laser': True,
        }],
        output='screen',
    )

    # Simulated Formlabs
    sim_formlabs_node = Node(
        package='lego_mcp_simulation',
        executable='formlabs_simulator',
        name='formlabs_sim',
        namespace='formlabs',
        parameters=[{
            'simulation_speed': 10.0,  # 10x speed for testing
        }],
        output='screen',
    )

    # ==========================================================================
    # CORE SIMULATION NODES
    # ==========================================================================

    # Safety node (in simulation mode)
    safety_node = Node(
        package='lego_mcp_safety',
        executable='safety_node',
        name='safety_node',
        parameters=[{
            'simulation_mode': True,
            'estop_gpio_pin': -1,  # Disable GPIO in simulation
        }],
        output='screen',
    )

    # Orchestrator
    orchestrator_node = Node(
        package='lego_mcp_orchestrator',
        executable='orchestrator_node',
        name='lego_mcp_orchestrator',
        parameters=[
            cell_layout_config,
            equipment_params,
            {'simulation_mode': True},
        ],
        output='screen',
    )

    # Twin sync
    twin_sync_node = Node(
        package='lego_mcp_orchestrator',
        executable='twin_sync_node',
        name='twin_sync',
        parameters=[{'simulation_mode': True}],
        output='screen',
    )

    # Rosbridge for Flask
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

    # Simulated vision (returns mock detections)
    sim_vision_node = Node(
        package='lego_mcp_simulation',
        executable='vision_simulator',
        name='vision_sim',
        namespace='vision',
        parameters=[{
            'defect_probability': 0.05,  # 5% chance of defect
        }],
        output='screen',
    )

    # ==========================================================================
    # VISUALIZATION
    # ==========================================================================

    # RViz for visualization
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', os.path.join(bringup_dir, 'config', 'simulation.rviz')],
        output='screen',
    )

    # ==========================================================================
    # ASSEMBLE LAUNCH DESCRIPTION
    # ==========================================================================

    return LaunchDescription([
        declare_use_rviz,

        # Simulated equipment
        sim_ned2_node,
        sim_xarm_node,
        sim_cnc_node,
        sim_laser_node,
        sim_formlabs_node,
        sim_vision_node,

        # Core nodes
        safety_node,
        orchestrator_node,
        twin_sync_node,
        rosbridge_node,

        # Visualization
        # rviz_node,  # Uncomment when rviz config is created
    ])
