#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\2_classification_labeling
#   ..\..\.venv\Scripts\python.exe build_dataset.py
#   → labels.csv(멀티라벨) 를 **속성별 이진 ImageFolder** 로 조립 → 3_classification_training\
# ─────────────────────────────────────────────────────────────
r"""labels.csv(멀티라벨) → 학습용 **속성별 이진 데이터셋** 조립.

CNN_Training_Standard 는 단일라벨(폴더=클래스)이라, 멀티라벨을 **속성마다 2클래스(0/1)** 로 편다.
속성별로 `3_classification_training\dataset_<attr>\{0_no_<attr>, 1_<attr>}\` 생성.
뒤통수(back_head)·None 은 얼굴 판별 불가라 학습 데이터에서 제외.
"""
import shutil
from pathlib import Path

from grid_io import load_labels
from grid_label import ATTR_NAMES

HERE = Path(__file__).resolve().parent
CROPS = HERE.parent / "1_baby_face_dataset_collect" / "crops"
CSV = HERE / "labels.csv"
OUT_ROOT = HERE.parent / "3_classification_training"
GATE = ["back_head", "none"]                              # 하나라도 참이면 학습 제외
TRAINABLE = [a for a in ATTR_NAMES if a not in GATE]      # eyes_open·mouth_open·mouth_covered·frown


def main() -> int:
    labels = load_labels(CSV, ATTR_NAMES)
    if not labels:
        print(f"labels.csv 없음: {CSV}\n먼저 grid_label.py 로 라벨링하세요.")
        return 1
    done = {n: v for n, v in labels.items() if v.get("labeled")}
    usable = {n: v for n, v in done.items() if not any(v.get(g) for g in GATE)}
    print(f"라벨완료 {len(done)} · 학습가능(뒤통수/None 제외) {len(usable)}")

    for attr in TRAINABLE:
        out = OUT_ROOT / f"dataset_{attr}"
        if out.exists():
            shutil.rmtree(out)
        pos = neg = 0
        for name, v in usable.items():
            src = CROPS / name
            if not src.exists():
                continue
            cls = f"1_{attr}" if v.get(attr) else f"0_no_{attr}"
            d = out / cls
            d.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, d / name)
            pos += bool(v.get(attr))
            neg += not v.get(attr)
        print(f"  {attr:14s} → dataset_{attr}\\  (1:{pos} / 0:{neg})")

    print("\n다음: ..\\3_classification_training\\run_training.py --dataset_path .\\dataset_eyes_open  (속성별로)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
