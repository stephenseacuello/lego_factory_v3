from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'cnc_oee'

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
    description='OEE calculation for CNC machines',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'oee_aggregator = cnc_oee.oee_aggregator_node:main',
            'job_simulator = cnc_oee.job_simulator:main',
        ],
    },
)
