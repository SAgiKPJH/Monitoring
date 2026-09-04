#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\4_detection_pretrained
#   ..\.venv\Scripts\python.exe Detection_Live_Test.py          # 실시간 창 (기본)
#   ..\.venv\Scripts\python.exe Detection_Live_Test.py shot 30  # 창 없이 30프레임 추론→out\ 저장
#   창 키: d/p 감지·포즈 토글 · s 스크린샷 · q 종료
# ─────────────────────────────────────────────────────────────
r"""Detection_Live_Test.py — go2rtc 실시간 스트림 추론 (사전학습 person + 포즈).
실행 로직은 src/app.py 공유. 아래 [설정] 만 고치면 됩니다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ══════════════════════ 설정 ══════════════════════
STREAM_URL = r"http://172.30.1.42:1984/stream.html?src=camera1"   # go2rtc (stream.mp4 실시간 자동)
DET_MODEL   = "yolo11m.pt"        # 사전학습 COCO. 이름만 주면 자동 다운로드
DET_CLASSES = [0]                 # 0=person (COCO). 전체는 None
POSE_MODEL = "yolo11n-pose.pt"    # COCO 포즈 (참고용)
SCALE = 0.5      # 입력 1/2 축소
CONF  = 0.20     # 감지 임계
MODE  = "live"   # "live" 실시간 창 / "shot" N프레임 캡처→저장
SHOT_FRAMES = 20
# ═══════════════════════════════════════════════════

from src.app import run_live  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_live(
        sys.argv[1:], stream_url=STREAM_URL, det_model=DET_MODEL, pose_model=POSE_MODEL,
        det_classes=DET_CLASSES, scale=SCALE, conf=CONF, mode=MODE, shot_frames=SHOT_FRAMES))
