from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='rdk_rf_receiver',
            executable='rdk_rf_receiver',
            name='rf_receiver',
            output='screen',
            emulate_tty=True,   # 노드 stdout 로그가 화면에 바로 보이게
            # 디버그(idle 하트비트) 보려면:  arguments=['-d'],
        ),
    ])
