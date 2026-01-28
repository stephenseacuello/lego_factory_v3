#!/usr/bin/env python3
"""
LEGO MCP AGV Fleet Launch File

Launches the complete AGV fleet management system:
- Fleet manager node
- Task allocator node
- AGV simulators (for testing)
- Micro-ROS agent launcher

LEGO MCP Manufacturing System v7.0
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    # Launch arguments
    simulation_arg = DeclareLaunchArgument(
        'simulation',
        default_value='true',
        description='Run in simulation mode'
    )

    num_agvs_arg = DeclareLaunchArgument(
        'num_agvs',
        default_value='2',
        description='Number of AGVs to simulate'
    )

    enable_nav2_arg = DeclareLaunchArgument(
        'enable_nav2',
        default_value='false',
        description='Enable Nav2 navigation stack'
    )

    allocation_strategy_arg = DeclareLaunchArgument(
        'allocation_strategy',
        default_value='hybrid',
        description='Task allocation strategy (nearest, load_balance, battery_aware, hybrid)'
    )

    # Fleet manager node
    fleet_manager = Node(
        package='lego_mcp_agv',
        executable='fleet_manager_node.py',
        name='fleet_manager',
        namespace='lego_mcp',
        parameters=[{
            'max_agvs': 10,
            'task_timeout_seconds': 300.0,
            'low_battery_threshold': 20.0,
            'auto_charge_threshold': 30.0,
        }],
        output='screen',
    )

    # Task allocator node
    task_allocator = Node(
        package='lego_mcp_agv',
        executable='task_allocator_node.py',
        name='task_allocator',
        namespace='lego_mcp',
        parameters=[{
            'strategy': LaunchConfiguration('allocation_strategy'),
            'auction_timeout_ms': 500,
            'distance_weight': 0.4,
            'battery_weight': 0.3,
            'load_weight': 0.3,
        }],
        output='screen',
    )

    # Simulated AGVs (only in simulation mode)
    agv_simulators = GroupAction(
        condition=IfCondition(LaunchConfiguration('simulation')),
        actions=[
            Node(
                package='lego_mcp_agv',
                executable='agv_simulator_node.py',
                name='alvik_sim_01',
                namespace='lego_mcp',
                parameters=[{
                    'agv_id': 'alvik_01',
                    'initial_x': -0.6,
                    'initial_y': 0.0,
                    'initial_theta': 0.0,
                }],
                output='screen',
            ),
            Node(
                package='lego_mcp_agv',
                executable='agv_simulator_node.py',
                name='alvik_sim_02',
                namespace='lego_mcp',
                parameters=[{
                    'agv_id': 'alvik_02',
                    'initial_x': -0.6,
                    'initial_y': 0.3,
                    'initial_theta': 0.0,
                }],
                output='screen',
            ),
        ],
    )

    # Micro-ROS agent launcher (for real hardware)
    microros_launcher = GroupAction(
        condition=IfCondition(
            PythonExpression(["not ", LaunchConfiguration('simulation')])
        ),
        actions=[
            Node(
                package='lego_mcp_microros',
                executable='microros_agent_launcher_node.py',
                name='microros_launcher',
                namespace='lego_mcp',
                parameters=[{
                    'default_transport': 'udp',
                    'udp_port_base': 8888,
                }],
                output='screen',
            ),
        ],
    )

    return LaunchDescription([
        simulation_arg,
        num_agvs_arg,
        enable_nav2_arg,
        allocation_strategy_arg,
        fleet_manager,
        task_allocator,
        agv_simulators,
        microros_launcher,
    ])
