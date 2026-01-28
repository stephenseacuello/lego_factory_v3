from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'cnc_visualization'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'urdf'), glob('urdf/*.urdf')),
        (os.path.join('share', package_name, 'meshes'), glob('meshes/*.stl') + glob('meshes/*.dae')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='CNC SCADA Team',
    maintainer_email='cnc@example.com',
    description='Digital twin visualization for CNC machines',
    license='MIT',
    entry_points={
        'console_scripts': [
            'digital_twin_node = cnc_visualization.digital_twin_node:main',
            'toolpath_visualizer = cnc_visualization.toolpath_visualizer:main',
            'foxglove_bridge = cnc_visualization.foxglove_bridge:main',
            'unity_state_publisher = cnc_visualization.unity_state_publisher:main',
        ],
    },
)
