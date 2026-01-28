from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'cnc_fleet'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='CNC SCADA Team',
    maintainer_email='cnc@example.com',
    description='Fleet management for multi-machine CNC factory',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'fleet_manager = cnc_fleet.fleet_manager_node:main',
        ],
    },
)
