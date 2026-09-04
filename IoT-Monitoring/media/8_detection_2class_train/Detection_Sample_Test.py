#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\8_detection_2class_train
#   ..\.venv\Scripts\python.exe Detection_Sample_Test.py        # 학습 이미지 5개 랜덤 추론
#   ..\.venv\Scripts\python.exe Detection_Sample_Test.py 10     # 개수 지정
#   결과: out_sample\ 에 박스(baby·baby_face)+골격 이미지 + 콘솔 요약
# ─────────────────────────────────────────────────────────────
r"""Detection_Sample_Test.py — 학습된 2클래스 모델로 학습 이미지 N개 랜덤 추론.
구현(src)은 ..\4_detection_pretrained 를 재사용. 아래 [설정] 만 고치면 됩니다."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "4_detection_pretrained"))

# ══════════════════════ 설정 (학습 모델) ══════════════════════
SRC_DIR = os.path.join(_HERE, "dataset", "images")               # 학습에 쓴 이미지 (이 폴더 dataset)
# DET_MODEL   = os.path.join(_HERE, "output", "best", "model.pth")  # 파인튜닝 baby+baby_face (nc=2)
DET_MODEL   = os.path.join(_HERE, "output", "60", "model.pth")  # 파인튜닝 baby+baby_face (nc=2)
DET_CLASSES = None                                               # 2클래스 전체
POSE_MODEL  = "yolo11n-pose.pt"
CONF = 0.20
N_SAMPLES = 5
# ═════════════════════════════════════════════════════════════

from src.app import run_sample  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_sample(
        sys.argv[1:], src_dir=SRC_DIR, det_model=DET_MODEL, pose_model=POSE_MODEL,
        det_classes=DET_CLASSES, conf=CONF, n_samples=N_SAMPLES))
