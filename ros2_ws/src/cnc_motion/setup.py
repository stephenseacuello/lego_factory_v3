from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'cnc_motion'

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
    description='Collision detection and path planning for CNC machines',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'collision_detector = cnc_motion.collision_detector:main',
            'path_planner = cnc_motion.path_planner:main',
            'gcode_validator = cnc_motion.gcode_validator:main',
        ],
    },
)
