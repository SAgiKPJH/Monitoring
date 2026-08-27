from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='rdk_rf_receiver',
            executable='rf_receiver_node',
            name='rf_receiver',
            output='screen',
            emulate_tty=True,
        ),
    ])
