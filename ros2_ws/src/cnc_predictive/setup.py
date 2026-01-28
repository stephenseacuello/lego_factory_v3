from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'cnc_predictive'

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
        (os.path.join('share', package_name, 'models'), glob('models/*.pkl') + glob('models/*.json')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='CNC SCADA Team',
    maintainer_email='cnc@example.com',
    description='ML-based predictive maintenance for CNC machines',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'predictive_node = cnc_predictive.predictive_node:main',
            'tool_wear_monitor = cnc_predictive.tool_wear_monitor:main',
            'anomaly_detector = cnc_predictive.anomaly_detector:main',
            'model_trainer = cnc_predictive.model_trainer:main',
            'unity_prediction_publisher = cnc_predictive.unity_prediction_publisher:main',
        ],
    },
)
