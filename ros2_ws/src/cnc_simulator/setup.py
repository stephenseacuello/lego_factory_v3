import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'cnc_simulator'

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
    description='CNC Machine Simulator - TinyG/GRBL status publisher',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'machine_publisher = cnc_simulator.machine_publisher:main',
            'machine_subscriber = cnc_simulator.machine_subscriber:main',
            'jog_commander = cnc_simulator.jog_commander:main',
            'sensor_simulator = cnc_simulator.sensor_simulator:main',
            'sensor_bridge = cnc_simulator.sensor_bridge:main',
        ],
    },
)
