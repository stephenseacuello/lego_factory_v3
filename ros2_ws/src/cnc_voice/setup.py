from setuptools import find_packages, setup
import os
from glob import glob
package_name = 'cnc_voice'
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
    description='Voice control for CNC machines', license='MIT',
    entry_points={'console_scripts': [
        'voice_controller = cnc_voice.voice_controller:main',
    ]},
)
