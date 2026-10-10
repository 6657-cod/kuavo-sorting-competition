"""Launch the simulation with explicit, typed Humble-compatible parameters."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    defaults = {
        'timeout_seconds': ('5.0', float),
        'max_retries': ('2', int),
        'action_seconds': ('0.7', float),
        'drop_first_attempts': ('0', int),
        'fail_first_attempts': ('0', int),
    }
    arguments = [DeclareLaunchArgument(name, default_value=default)
                 for name, (default, _) in defaults.items()]

    def parameters(*names):
        return {name: ParameterValue(LaunchConfiguration(name), value_type=defaults[name][1])
                for name in names}

    return LaunchDescription(arguments + [
        Node(package='kuavo_sorting', executable='vision_node', output='screen',
             parameters=[parameters('drop_first_attempts')]),
        Node(package='kuavo_sorting', executable='robot_node', output='screen',
             parameters=[parameters('action_seconds', 'fail_first_attempts')]),
        Node(package='kuavo_sorting', executable='sorting_node', output='screen',
             parameters=[parameters('timeout_seconds', 'max_retries')]),
    ])
