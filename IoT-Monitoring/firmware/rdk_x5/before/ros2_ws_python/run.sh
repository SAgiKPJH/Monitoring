#!/usr/bin/env bash
# IoT RF 수신 rclpy 노드를 ROS 2로 실행. systemd(iot-rf-receiver.service)에서 호출.
set -e
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"     # 이 스크립트가 있는 ros2_iot_ws 디렉터리

if   [ -f /opt/tros/humble/setup.bash ]; then source /opt/tros/humble/setup.bash
elif [ -f /opt/tros/setup.bash ];        then source /opt/tros/setup.bash
elif [ -f /opt/ros/humble/setup.bash ];  then source /opt/ros/humble/setup.bash
else echo "ROS 2 setup.bash 를 못 찾음 (경로 확인)"; exit 1
fi

source "$WS/install/setup.bash"
exec ros2 launch iot_rf_receiver receiver.launch.py
