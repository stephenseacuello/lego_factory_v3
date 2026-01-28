#!/usr/bin/env python3
"""
LEGO MCP Factory Simulation Launch File

Launches complete factory simulation including:
- Gazebo world with factory cell
- Simulated equipment (GRBL CNC, Laser, Formlabs SLA)
- Robot simulators for Niryo Ned2 and xArm 6 Lite

LEGO MCP Manufacturing System v7.0
"""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    GroupAction,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)

from launch_ros.actions import Node, PushRosNamespace


def generate_launch_description():
    # Get package directories
    pkg_simulation = get_package_share_directory('lego_mcp_simulation')
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')

    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    gui = LaunchConfiguration('gui', default='true')
    headless = LaunchConfiguration('headless', default='false')
    world_file = LaunchConfiguration('world', default=os.path.join(
        pkg_simulation, 'worlds', 'lego_factory.world'
    ))
    verbose = LaunchConfiguration('verbose', default='false')

    # Equipment simulation parameters
    simulate_cnc = LaunchConfiguration('simulate_cnc', default='true')
    simulate_laser = LaunchConfiguration('simulate_laser', default='true')
    simulate_formlabs = LaunchConfiguration('simulate_formlabs', default='true')
    simulate_delays = LaunchConfiguration('simulate_delays', default='true')

    # Declare launch arguments
    declare_args = [
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
            description='Use simulation time'
        ),
        DeclareLaunchArgument(
            'gui',
            default_value='true',
            description='Launch Gazebo GUI'
        ),
        DeclareLaunchArgument(
            'headless',
            default_value='false',
            description='Run Gazebo headless (no rendering)'
        ),
        DeclareLaunchArgument(
            'world',
            default_value=os.path.join(pkg_simulation, 'worlds', 'lego_factory.world'),
            description='World file to load'
        ),
        DeclareLaunchArgument(
            'verbose',
            default_value='false',
            description='Verbose Gazebo output'
        ),
        DeclareLaunchArgument(
            'simulate_cnc',
            default_value='true',
            description='Launch simulated CNC'
        ),
        DeclareLaunchArgument(
            'simulate_laser',
            default_value='true',
            description='Launch simulated laser'
        ),
        DeclareLaunchArgument(
            'simulate_formlabs',
            default_value='true',
            description='Launch simulated Formlabs printer'
        ),
        DeclareLaunchArgument(
            'simulate_delays',
            default_value='true',
            description='Simulate realistic timing delays'
        ),
    ]

    # Gazebo server
    gazebo_server = ExecuteProcess(
        cmd=['gzserver', '--verbose', world_file,
             '-s', 'libgazebo_ros_init.so',
             '-s', 'libgazebo_ros_factory.so'],
        output='screen',
        condition=IfCondition(verbose),
    )

    gazebo_server_quiet = ExecuteProcess(
        cmd=['gzserver', world_file,
             '-s', 'libgazebo_ros_init.so',
             '-s', 'libgazebo_ros_factory.so'],
        output='screen',
        condition=UnlessCondition(verbose),
    )

    # Gazebo client (GUI)
    gazebo_client = ExecuteProcess(
        cmd=['gzclient'],
        output='screen',
        condition=IfCondition(gui),
    )

    # TinyG CNC Simulator
    cnc_simulator = Node(
        package='lego_mcp_simulation',
        executable='grbl_simulator',
        name='grbl_cnc_sim',
        namespace='lego_mcp',
        parameters=[{
            'use_sim_time': use_sim_time,
            'machine_type': 'tinyg',
            'machine_name': 'cnc',
            'max_feedrate': 5000.0,
            'max_travel_x': 300.0,
            'max_travel_y': 200.0,
            'max_travel_z': 100.0,
            'simulate_delays': simulate_delays,
        }],
        output='screen',
        condition=IfCondition(simulate_cnc),
    )

    # MKS Laser Simulator
    laser_simulator = Node(
        package='lego_mcp_simulation',
        executable='grbl_simulator',
        name='grbl_laser_sim',
        namespace='lego_mcp',
        parameters=[{
            'use_sim_time': use_sim_time,
            'machine_type': 'grbl',
            'machine_name': 'laser',
            'max_feedrate': 10000.0,
            'max_travel_x': 350.0,
            'max_travel_y': 350.0,
            'max_travel_z': 50.0,
            'simulate_delays': simulate_delays,
        }],
        output='screen',
        condition=IfCondition(simulate_laser),
    )

    # Formlabs SLA Simulator
    formlabs_simulator = Node(
        package='lego_mcp_simulation',
        executable='formlabs_simulator',
        name='formlabs_sim',
        namespace='lego_mcp',
        parameters=[{
            'use_sim_time': use_sim_time,
            'printer_name': 'formlabs',
            'printer_model': 'Form 3+',
            'serial_number': 'SIM-FORM-001',
            'layer_time_s': 0.5 if simulate_delays == 'false' else 8.0,
            'heating_time_s': 1.0 if simulate_delays == 'false' else 300.0,
            'filling_time_s': 0.5 if simulate_delays == 'false' else 60.0,
            'simulate_failures': False,
        }],
        output='screen',
        condition=IfCondition(simulate_formlabs),
    )

    # Static transforms for equipment positions
    static_tf_publisher = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='world_to_table_tf',
        arguments=['0.6', '0.4', '0.75', '0', '0', '0', 'world', 'worktable'],
    )

    ned2_base_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='ned2_base_tf',
        arguments=['0.1', '0.4', '0.77', '0', '0', '0', 'world', 'ned2_base_link'],
    )

    xarm_base_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='xarm_base_tf',
        arguments=['1.1', '0.4', '0.77', '0', '0', '3.14159', 'world', 'xarm_base_link'],
    )

    formlabs_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='formlabs_tf',
        arguments=['-0.4', '0.4', '0', '0', '0', '0', 'world', 'formlabs_link'],
    )

    cnc_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='cnc_tf',
        arguments=['0.6', '-0.3', '0', '0', '0', '0', 'world', 'cnc_link'],
    )

    laser_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='laser_tf',
        arguments=['0.6', '1.1', '0', '0', '0', '0', 'world', 'laser_link'],
    )

    # Simulation status publisher
    sim_status_node = Node(
        package='lego_mcp_simulation',
        executable='simulation_status',
        name='simulation_status',
        namespace='lego_mcp',
        parameters=[{
            'use_sim_time': use_sim_time,
        }],
        output='screen',
    )

    return LaunchDescription([
        *declare_args,

        # Gazebo
        gazebo_server,
        gazebo_server_quiet,
        gazebo_client,

        # Static TFs (launch immediately)
        static_tf_publisher,
        ned2_base_tf,
        xarm_base_tf,
        formlabs_tf,
        cnc_tf,
        laser_tf,

        # Equipment simulators (delayed to let Gazebo start)
        TimerAction(
            period=3.0,
            actions=[
                cnc_simulator,
                laser_simulator,
                formlabs_simulator,
            ]
        ),
    ])
