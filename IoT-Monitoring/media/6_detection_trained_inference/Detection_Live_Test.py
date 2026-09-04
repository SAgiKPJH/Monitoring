#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\6_detection_trained_inference
#   ..\.venv\Scripts\python.exe Detection_Live_Test.py          # 실시간 창 (기본)
#   ..\.venv\Scripts\python.exe Detection_Live_Test.py shot 30  # 창 없이 30프레임 → out\
#   창 키: d/p 감지·포즈 토글 · s 스크린샷 · q 종료
# ─────────────────────────────────────────────────────────────
r"""Detection_Live_Test.py — 학습된 baby 모델로 go2rtc 실시간 스트림 추론.
구현(src)은 ..\4_detection_pretrained 를 재사용(복붙 없음). 아래 [설정] 만 고치면 됩니다."""
import os
import sys

# 4_detection_pretrained/src 재사용 — 자체 src 없음
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "4_detection_pretrained"))

# ══════════════════════ 설정 (학습 모델) ══════════════════════
STREAM_URL = r"http://172.30.1.42:1984/stream.html?src=camera1"   # go2rtc
DET_MODEL   = r"D:\Code\Monitoring\IoT-Monitoring\media\5_detection_train\output\best\model.pth"        # 파인튜닝 baby (state_dict/.pt/.onnx)
DET_CLASSES = None                                               # baby 단일 클래스 → 전체
POSE_MODEL = "yolo11n-pose.pt"                                    # COCO 포즈 (참고용)
SCALE = 0.5
CONF  = 0.20
MODE  = "live"
SHOT_FRAMES = 20
# ═════════════════════════════════════════════════════════════

from src.app import run_live  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_live(
        sys.argv[1:], stream_url=STREAM_URL, det_model=DET_MODEL, pose_model=POSE_MODEL,
        det_classes=DET_CLASSES, scale=SCALE, conf=CONF, mode=MODE, shot_frames=SHOT_FRAMES))
