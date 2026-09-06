#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 1단계 — 알람 채널 테스트 (PC·보드 공통)
#   cd D:\Code\Monitoring\IoT-Monitoring\media\15_rdk_x5_runtime
#   ..\.venv\Scripts\python.exe 1_slack_send_test.py              # 스트림 1프레임 첨부(로컬 저장) + Slack/Grafana 전송
#   ..\.venv\Scripts\python.exe 1_slack_send_test.py --no-image   # 텍스트만
#   다음: 2_run_test.py → 3_gui_test.py → monitoring.py
# ─────────────────────────────────────────────────────────────
r""".env 의 SLACK_WEBHOOK(+GRAFANA_URL/TOKEN) 으로 테스트 알람 1건을 실제 전송해 채널을 확인한다.

쿨다운 무시(cooldown=0). 이미지는 스트림 1프레임(없으면 합성 이미지)을 alarms\ 에 저장하고 경로를 텍스트에 안내
(웹훅은 파일 첨부 불가 — 알람규칙.md). 모델은 로드하지 않는다.
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import monitoring as M  # noqa: E402  (.env 로드·alarm import 만; 모델 로드 X)
from monitoring import alarm  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="알람 채널(Slack/Grafana) 전송 테스트")
    ap.add_argument("--no-image", action="store_true", help="이미지 없이 텍스트만")
    ap.add_argument("--text", default="", help="보낼 문구(기본: 테스트 문구+시각)")
    args = ap.parse_args()

    print(f"SLACK_WEBHOOK : {'설정됨' if alarm.SLACK_WEBHOOK else '없음 → 콘솔만'}")
    print(f"GRAFANA       : {'설정됨' if (alarm.GRAFANA_URL and alarm.GRAFANA_TOKEN) else '없음'}")
    print(f"ALARM_COOLDOWN: {alarm.COOLDOWN:.0f}s (이 테스트는 무시)")

    img = None
    if not args.no_image:
        cap, how = M.open_source(M.STREAM_URL)
        if cap is not None:
            img = M.grab(cap)
            cap.release()
        if img is not None:
            print(f"이미지: 스트림 프레임 {img.shape[1]}x{img.shape[0]} ({how})")
        else:
            img = np.full((360, 640, 3), 40, np.uint8)
            cv2.putText(img, "baby-monitor alarm test", (60, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
            print(f"이미지: 합성(스트림 없음: {M.STREAM_URL})")

    text = args.text or f"[테스트] baby-monitor 알람 채널 확인 {time.strftime('%Y-%m-%d %H:%M:%S')}"
    ok = alarm.send(text, key="test", cooldown=0, tags=["baby-monitor", "test"], image=img)
    print("전송 결과:", "OK — Slack 채널/Grafana 주석을 확인하세요" if ok else "실패 또는 미설정 (위 로그 참고)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
