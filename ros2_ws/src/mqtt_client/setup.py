import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'mqtt_client'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools', 'paho-mqtt'],
    zip_safe=True,
    maintainer='CNC SCADA Team',
    maintainer_email='cnc@example.com',
    description='Bidirectional MQTT-ROS 2 bridge for Flask SCADA integration',
    license='MIT',
    entry_points={
        'console_scripts': [
            'mqtt_bridge = mqtt_client.mqtt_bridge_node:main',
        ],
    },
)
