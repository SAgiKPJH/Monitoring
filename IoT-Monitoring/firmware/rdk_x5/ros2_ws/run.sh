#!/usr/bin/env bash
# RDK X5 RF 수신기(ROS 2 C++ 노드)를 실행. systemd(rf-receiver.service)에서 호출됨.
# 자기 위치를 기준으로 워크스페이스를 찾으므로 어디에 두든 동작.
set -e
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"     # 이 스크립트가 있는 ros2_ws 디렉터리

# ROS 2 환경 (tros 우선, 없으면 ros humble)
if   [ -f /opt/tros/humble/setup.bash ]; then source /opt/tros/humble/setup.bash
elif [ -f /opt/tros/setup.bash ];        then source /opt/tros/setup.bash
elif [ -f /opt/ros/humble/setup.bash ];  then source /opt/ros/humble/setup.bash
else echo "ROS 2 setup.bash 를 못 찾음 (경로 확인)"; exit 1
fi

# ros2 launch 는 실행마다 ~/.ros/log/<타임스탬프>/ 를 새로 만든다.
# systemd 가 반복 재시작하면 쌓여서 디스크를 채우므로 3일 지난 것은 정리한다.
find "$HOME/.ros/log" -maxdepth 1 -mindepth 1 -type d -mtime +3 -exec rm -rf {} + 2>/dev/null || true

source "$WS/install/setup.bash"
exec ros2 launch rdk_rf_receiver receiver.launch.py
