# -*- coding: utf-8 -*-
"""ros2 launch baby_monitor monitor.launch.py [runtime_dir:=/path/to/runtime]

runtime_dir 기본값: env BABY_MONITOR_DIR → 이 launch 파일의 상위 폴더 중 monitoring.py 가 있는 곳(ros2_ws 가 런타임 폴더
안에 있으므로 자동으로 찾힘) → /home/sunrise/JJU/Monitoring.
"""
import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _find_runtime_dir():
    env = os.environ.get("BABY_MONITOR_DIR")
    if env:
        return env
    for p in Path(__file__).resolve().parents:
        if (p / "monitoring.py").is_file():
            return str(p)
    return "/home/sunrise/JJU/Monitoring"                    # 보드 작업 폴더(기본)


def generate_launch_description():
    default_dir = _find_runtime_dir()
    return LaunchDescription([
        DeclareLaunchArgument("runtime_dir", default_value=default_dir,
                              description="15_rdk_x5_runtime 폴더 경로(monitoring.py·models·.env)"),
        Node(
            package="baby_monitor",
            executable="monitor_node",
            name="baby_monitor",
            output="screen",
            emulate_tty=True,
            parameters=[{"runtime_dir": LaunchConfiguration("runtime_dir")}],
        ),
    ])
