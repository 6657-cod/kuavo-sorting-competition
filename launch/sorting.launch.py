from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='kuavo_sorting', executable='vision_node', output='screen'),
        Node(package='kuavo_sorting', executable='robot_node', output='screen'),
        Node(package='kuavo_sorting', executable='sorting_node', output='screen'),
    ])
