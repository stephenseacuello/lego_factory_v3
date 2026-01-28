#!/usr/bin/env python3
"""
LEGO MCP MoveIt2 Move Group Launch File

Launches MoveIt2 move_group node for multi-robot planning.

LEGO MCP Manufacturing System v7.0
"""

import os
import yaml

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import (
    Command,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)

from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def load_yaml(package_name, file_path):
    """Load a YAML file from a ROS2 package."""
    package_path = get_package_share_directory(package_name)
    absolute_file_path = os.path.join(package_path, file_path)
    try:
        with open(absolute_file_path, 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        return {}


def generate_launch_description():
    # Get package directories
    pkg_moveit_config = get_package_share_directory('lego_mcp_moveit_config')

    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    use_rviz = LaunchConfiguration('use_rviz', default='true')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time'
    )

    declare_use_rviz = DeclareLaunchArgument(
        'use_rviz',
        default_value='true',
        description='Launch RViz2'
    )

    # Robot description from xacro
    robot_description_content = Command([
        FindExecutable(name='xacro'), ' ',
        os.path.join(pkg_moveit_config, 'urdf', 'lego_cell.urdf.xacro')
    ])

    robot_description = {'robot_description': ParameterValue(robot_description_content, value_type=str)}

    # SRDF
    robot_description_semantic_path = os.path.join(
        pkg_moveit_config, 'config', 'lego_cell.srdf'
    )
    with open(robot_description_semantic_path, 'r') as file:
        robot_description_semantic_content = file.read()

    robot_description_semantic = {
        'robot_description_semantic': robot_description_semantic_content
    }

    # Load configuration files
    kinematics_yaml = load_yaml('lego_mcp_moveit_config', 'config/kinematics.yaml')
    joint_limits_yaml = load_yaml('lego_mcp_moveit_config', 'config/joint_limits.yaml')
    ompl_planning_yaml = load_yaml('lego_mcp_moveit_config', 'config/ompl_planning.yaml')
    moveit_controllers_yaml = load_yaml('lego_mcp_moveit_config', 'config/moveit_controllers.yaml')

    # Planning configuration
    planning_pipeline = {
        'planning_pipelines': ['ompl'],
        'default_planning_pipeline': 'ompl',
        'ompl': ompl_planning_yaml,
    }

    # Trajectory execution configuration
    trajectory_execution = {
        'moveit_manage_controllers': True,
        'trajectory_execution.allowed_execution_duration_scaling': 1.2,
        'trajectory_execution.allowed_goal_duration_margin': 0.5,
        'trajectory_execution.allowed_start_tolerance': 0.01,
    }

    # Planning scene monitor configuration
    planning_scene_monitor = {
        'publish_planning_scene': True,
        'publish_geometry_updates': True,
        'publish_state_updates': True,
        'publish_transforms_updates': True,
    }

    # Move group node
    move_group_node = Node(
        package='moveit_ros_move_group',
        executable='move_group',
        output='screen',
        parameters=[
            robot_description,
            robot_description_semantic,
            kinematics_yaml,
            joint_limits_yaml,
            planning_pipeline,
            trajectory_execution,
            planning_scene_monitor,
            moveit_controllers_yaml,
            {'use_sim_time': use_sim_time},
        ],
    )

    # Robot state publisher
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[
            robot_description,
            {'use_sim_time': use_sim_time},
        ],
    )

    # Joint state publisher (for visualization without hardware)
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'source_list': ['/ned2/joint_states', '/xarm/joint_states']},
        ],
    )

    # RViz
    rviz_config_file = os.path.join(pkg_moveit_config, 'config', 'moveit.rviz')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config_file] if os.path.exists(rviz_config_file) else [],
        parameters=[
            robot_description,
            robot_description_semantic,
            kinematics_yaml,
            {'use_sim_time': use_sim_time},
        ],
        condition=IfCondition(use_rviz),
    )

    # Static transform for world frame
    static_tf_world = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_world',
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'world'],
    )

    return LaunchDescription([
        declare_use_sim_time,
        declare_use_rviz,
        static_tf_world,
        robot_state_publisher_node,
        joint_state_publisher_node,
        move_group_node,
        rviz_node,
    ])
