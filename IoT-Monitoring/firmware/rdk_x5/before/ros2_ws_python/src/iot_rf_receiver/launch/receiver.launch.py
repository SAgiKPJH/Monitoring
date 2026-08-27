from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='iot_rf_receiver',
            executable='receiver',
            name='rf_receiver',
            output='screen',
            emulate_tty=True,
        ),
    ])
