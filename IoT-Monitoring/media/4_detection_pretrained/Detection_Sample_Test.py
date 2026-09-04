#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\4_detection_pretrained
#   ..\.venv\Scripts\python.exe Detection_Sample_Test.py        # 학습 이미지 5개 랜덤 추론
#   ..\.venv\Scripts\python.exe Detection_Sample_Test.py 10     # 개수 지정
#   결과: out_sample\ 에 박스+골격 그린 이미지 + 콘솔 요약
# ─────────────────────────────────────────────────────────────
r"""Detection_Sample_Test.py — 학습 이미지 중 N개 랜덤으로 감지+포즈 추론.
실행 로직은 src/app.py 공유. 아래 [설정] 만 고치면 됩니다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ══════════════════════ 설정 ══════════════════════
SRC_DIR = r"D:\carved\yolo_baby\images"                       # 학습에 쓴 이미지 폴더
DET_MODEL   = r"D:\carved\yolo_baby_output\best\model.pth"    # 파인튜닝 baby (학습 결과 확인용)
DET_CLASSES = None                                            # baby 단일 클래스 → 전체
POSE_MODEL  = "yolo11n-pose.pt"
CONF = 0.20
N_SAMPLES = 5
# ═══════════════════════════════════════════════════

from src.app import run_sample  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_sample(
        sys.argv[1:], src_dir=SRC_DIR, det_model=DET_MODEL, pose_model=POSE_MODEL,
        det_classes=DET_CLASSES, conf=CONF, n_samples=N_SAMPLES))
