import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'cnc_diagnostics'

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
    description='CNC Machine Diagnostics and Health Monitoring',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'diagnostics_node = cnc_diagnostics.diagnostics_node:main',
            'sensor_monitor = cnc_diagnostics.sensor_monitor:main',
            'machine_monitor = cnc_diagnostics.machine_monitor:main',
        ],
    },
)
