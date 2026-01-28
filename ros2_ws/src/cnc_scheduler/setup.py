from setuptools import find_packages, setup
import os
from glob import glob
package_name = 'cnc_scheduler'
setup(
    name=package_name, version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'], zip_safe=True,
    maintainer='CNC SCADA Team', maintainer_email='cnc@example.com',
    description='Job scheduling for CNC machines', license='MIT',
    entry_points={'console_scripts': [
        'scheduler_node = cnc_scheduler.scheduler_node:main',
        'queue_manager = cnc_scheduler.queue_manager:main',
        'unity_scheduler_bridge = cnc_scheduler.unity_scheduler_bridge:main',
    ]},
)
