#!/usr/bin/env python3
"""
CNC Vision Launch File

Launches all vision nodes for computer vision-based monitoring.
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, EnvironmentVariable
from launch_ros.actions import Node, PushRosNamespace


def generate_launch_description():
    """Generate launch description for CNC Vision system."""

    # Declare launch arguments
    machine_id_arg = DeclareLaunchArgument(
        'machine_id',
        default_value='default',
        description='Machine identifier'
    )

    camera_device_arg = DeclareLaunchArgument(
        'camera_device',
        default_value='/dev/video0',
        description='Camera device path'
    )

    camera_device_id_arg = DeclareLaunchArgument(
        'camera_device_id',
        default_value='0',
        description='Camera device ID (integer)'
    )

    use_device_path_arg = DeclareLaunchArgument(
        'use_device_path',
        default_value='false',
        description='Use device path instead of ID'
    )

    roboflow_api_key_arg = DeclareLaunchArgument(
        'roboflow_api_key',
        default_value=EnvironmentVariable('ROBOFLOW_API_KEY', default_value=''),
        description='Roboflow API key'
    )

    inference_server_url_arg = DeclareLaunchArgument(
        'inference_server_url',
        default_value=EnvironmentVariable('ROBOFLOW_INFERENCE_URL', default_value='http://roboflow-inference:9001'),
        description='Roboflow inference server URL'
    )

    mqtt_host_arg = DeclareLaunchArgument(
        'mqtt_host',
        default_value=EnvironmentVariable('MQTT_BROKER_HOST', default_value='mosquitto'),
        description='MQTT broker host'
    )

    mqtt_port_arg = DeclareLaunchArgument(
        'mqtt_port',
        default_value=EnvironmentVariable('MQTT_BROKER_PORT', default_value='1883'),
        description='MQTT broker port'
    )

    enable_camera_arg = DeclareLaunchArgument(
        'enable_camera',
        default_value='true',
        description='Enable camera node (disable if using external camera driver)'
    )

    enable_safety_monitor_arg = DeclareLaunchArgument(
        'enable_safety_monitor',
        default_value='true',
        description='Enable safety monitoring with E-stop integration'
    )

    enable_estop_arg = DeclareLaunchArgument(
        'enable_estop_on_intrusion',
        default_value='true',
        description='Trigger E-stop on safety zone intrusion'
    )

    # Camera node (optional - can use v4l2_camera instead)
    camera_node = Node(
        package='cnc_vision',
        executable='camera_node.py',
        name='cnc_camera',
        parameters=[{
            'device': LaunchConfiguration('camera_device'),
            'device_id': LaunchConfiguration('camera_device_id'),
            'use_device_path': LaunchConfiguration('use_device_path'),
            'width': 1280,
            'height': 720,
            'fps': 30.0,
            'auto_exposure': True,
            'frame_id': 'camera',
        }],
        condition=IfCondition(LaunchConfiguration('enable_camera')),
        output='screen',
    )

    # Alternative: v4l2_camera driver
    # Uncomment this and set enable_camera=false to use v4l2_camera instead
    # v4l2_camera_node = Node(
    #     package='v4l2_camera',
    #     executable='v4l2_camera_node',
    #     name='v4l2_camera',
    #     parameters=[{
    #         'video_device': LaunchConfiguration('camera_device'),
    #         'image_size': [1280, 720],
    #         'camera_frame_id': 'camera',
    #     }],
    #     remappings=[('/image_raw', '/camera/image_raw')],
    # )

    # YOLO Inference node
    yolo_inference_node = Node(
        package='cnc_vision',
        executable='yolo_inference_node.py',
        name='yolo_inference',
        parameters=[{
            'machine_id': LaunchConfiguration('machine_id'),
            'camera_id': 'primary',
            'roboflow_api_key': LaunchConfiguration('roboflow_api_key'),
            'inference_server_url': LaunchConfiguration('inference_server_url'),
            'use_local_inference': True,
            'defect_model_id': 'cnc-defect-detection/1',
            'tool_wear_model_id': 'tool-wear-detection/1',
            'part_model_id': 'part-detection/1',
            'safety_model_id': 'hand-detection/1',
            'confidence_threshold': 0.7,
            'safety_confidence_threshold': 0.5,
            'inference_mode': 'continuous',
            'target_fps': 10,
            'save_detections': True,
            'save_path': '/ros2_ws/captures',
        }],
        output='screen',
    )

    # Safety monitor node
    safety_monitor_node = Node(
        package='cnc_vision',
        executable='safety_monitor_node.py',
        name='vision_safety_monitor',
        parameters=[{
            'machine_id': LaunchConfiguration('machine_id'),
            'enable_estop_on_intrusion': LaunchConfiguration('enable_estop_on_intrusion'),
            'warning_zone_threshold': 0.8,
            'critical_zone_threshold': 0.5,
            'consecutive_frames_for_alert': 3,
            'cooldown_seconds': 5.0,
            'safety_classes': ['hand', 'person', 'human', 'body'],
        }],
        condition=IfCondition(LaunchConfiguration('enable_safety_monitor')),
        output='screen',
    )

    # MQTT bridge node
    mqtt_bridge_node = Node(
        package='cnc_vision',
        executable='mqtt_bridge_node.py',
        name='vision_mqtt_bridge',
        parameters=[{
            'mqtt_host': LaunchConfiguration('mqtt_host'),
            'mqtt_port': LaunchConfiguration('mqtt_port'),
            'topic_prefix': 'cnc',
            'machine_id': LaunchConfiguration('machine_id'),
            'qos': 1,
            'publish_all_detections': True,
        }],
        output='screen',
    )

    return LaunchDescription([
        # Arguments
        machine_id_arg,
        camera_device_arg,
        camera_device_id_arg,
        use_device_path_arg,
        roboflow_api_key_arg,
        inference_server_url_arg,
        mqtt_host_arg,
        mqtt_port_arg,
        enable_camera_arg,
        enable_safety_monitor_arg,
        enable_estop_arg,

        # Nodes
        camera_node,
        yolo_inference_node,
        safety_monitor_node,
        mqtt_bridge_node,
    ])
