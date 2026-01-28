import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'cnc_control'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='CNC SCADA Team',
    maintainer_email='cnc@example.com',
    description='CNC machine control services',
    license='MIT',
    entry_points={
        'console_scripts': [
            'machine_service = cnc_control.machine_service:main',
            'control_client = cnc_control.control_client:main',
            'gcode_action_server = cnc_control.gcode_action_server:main',
            'unity_command_handler = cnc_control.unity_command_handler:main',
        ],
    },
)
