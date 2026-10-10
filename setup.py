from setuptools import setup
from glob import glob
import os

package_name = 'kuavo_sorting'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    tests_require=['pytest'],
    python_requires='>=3.10',
    maintainer='student_team',
    maintainer_email='team@example.com',
    description='ROS 2 simulated sorting demo for Kuavo competition preparation',
    license='Apache-2.0',
    entry_points={'console_scripts': [
        'vision_node = kuavo_sorting.vision_node:main',
        'robot_node = kuavo_sorting.robot_node:main',
        'sorting_node = kuavo_sorting.sorting_node:main',
        'task_client = kuavo_sorting.task_client:main',
    ]},
)
