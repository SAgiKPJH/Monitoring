# -*- coding: utf-8 -*-
"""ROS2(rclpy) 노드 — 15_rdk_x5_runtime/monitoring.py 를 노드 안에서 실행하고 알람/상태를 토픽으로 발행.

monitoring.py 는 그대로(수정 없음). 감지·관찰 판정·Slack/Grafana 알람은 전부 monitoring 이 하고,
이 노드는 (1) alarm.send 를 감싸 성공한 알람을 /baby_monitor/alarm (std_msgs/String, JSON) 으로도 발행,
(2) 1초마다 /baby_monitor/status (JSON 하트비트) 발행만 추가한다.
파라미터 runtime_dir: 15_rdk_x5_runtime 경로 (기본: env BABY_MONITOR_DIR, 없으면 /home/sunrise/JJU/Monitoring).
"""
import json
import os
import sys
import threading
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


def find_runtime_dir():
    """런타임 폴더(monitoring.py 가 있는 곳) 기본값: env BABY_MONITOR_DIR → 이 파일 상위 탐색(ros2_ws 가 런타임 폴더 안에
    있으므로 install/·src/ 어느 쪽에서 실행돼도 찾음) → /home/sunrise/JJU/Monitoring."""
    env = os.environ.get("BABY_MONITOR_DIR")
    if env:
        return env
    for p in Path(__file__).resolve().parents:
        if (p / "monitoring.py").is_file():
            return str(p)
    return "/home/sunrise/JJU/Monitoring"                    # 보드 작업 폴더(기본)


class MonitorNode(Node):
    def __init__(self):
        super().__init__("baby_monitor")
        self.declare_parameter("runtime_dir", find_runtime_dir())
        rd = self.get_parameter("runtime_dir").get_parameter_value().string_value
        if not os.path.isfile(os.path.join(rd, "monitoring.py")):
            raise RuntimeError(f"runtime_dir 에 monitoring.py 없음: {rd}  (파라미터 runtime_dir 또는 env BABY_MONITOR_DIR)")
        sys.path.insert(0, rd)
        import monitoring as M                     # .env 로드·BACKEND 선택은 monitoring 이 수행
        self.M = M
        self.pub_alarm = self.create_publisher(String, "baby_monitor/alarm", 10)
        self.pub_status = self.create_publisher(String, "baby_monitor/status", 10)
        self._n_alarm, self._t0 = 0, time.time()

        orig_send = M.alarm.send                   # monitoring 은 매 호출 alarm.send 를 조회 → 래핑이 그대로 먹힘

        def send(text, key="", cooldown=None, tags=None, image=None):
            ok = orig_send(text, key=key, cooldown=cooldown, tags=tags, image=image)
            if ok:
                self._n_alarm += 1
                self.pub_alarm.publish(String(data=json.dumps(
                    {"key": key, "text": text, "tags": tags or [], "ts": time.time()}, ensure_ascii=False)))
                self.get_logger().warn(f"ALARM[{key}] {text}")
            return ok
        M.alarm.send = send

        self.get_logger().info(f"runtime_dir={rd}  BACKEND={M.BACKEND}  → monitoring.main() 스레드 시작")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.create_timer(1.0, self._heartbeat)

    def _run(self):
        try:
            rc = self.M.main()                     # 무한 루프. 반환하면(모델/스트림 오류 등) 노드도 종료
            self.get_logger().error(f"monitoring.main() 종료 rc={rc}")
        except Exception as e:                     # noqa: BLE001
            self.get_logger().error(f"monitoring 예외: {e!r}")
        rclpy.try_shutdown()

    def _heartbeat(self):
        self.pub_status.publish(String(data=json.dumps({
            "alive": self._thread.is_alive(), "uptime_s": round(time.time() - self._t0),
            "alarms": self._n_alarm, "backend": self.M.BACKEND})))


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = MonitorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
