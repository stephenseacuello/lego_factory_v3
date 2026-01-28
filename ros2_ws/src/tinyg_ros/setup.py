import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'tinyg_ros'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools', 'pyserial'],
    zip_safe=True,
    maintainer='CNC SCADA Team',
    maintainer_email='cnc@example.com',
    description='ROS 2 interface for TinyG CNC controllers',
    license='MIT',
    entry_points={
        'console_scripts': [
            'tinyg_node = tinyg_ros.tinyg_node:main',
            'tinyg_simulator = tinyg_ros.tinyg_simulator:main',
        ],
    },
)
