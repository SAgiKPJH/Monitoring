#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\2_classification_labeling
#   ..\..\.venv\Scripts\python.exe build_dataset_multilabel.py
#   → labels.csv(멀티라벨) 를 **단일 멀티라벨 모델용** dataset(images + 멀티핫 labels.csv) 로 조립
#     → 3_classification_training\dataset_ml\
# ─────────────────────────────────────────────────────────────
r"""labels.csv(멀티라벨) → **단일 멀티라벨 모델용** 데이터셋 조립.

속성별 이진(build_dataset.py)과 달리, 크롭 1장에 여러 속성을 동시에 다는 멀티핫 라벨로 만든다.
출력: dataset_ml\images\<크롭> + dataset_ml\labels.csv(file, <타깃 속성들 0/1>).
학습 대상 속성만(뒤통수·None 은 얼굴 판별 불가라 크롭째 제외) 포함.
"""
import csv
import shutil
from pathlib import Path

from grid_io import load_labels
from grid_label import ATTR_NAMES

HERE = Path(__file__).resolve().parent
CROPS = HERE.parent / "1_baby_face_dataset_collect" / "crops"
CSV = HERE / "labels.csv"
OUT = HERE.parent / "3_classification_training" / "dataset_ml"
GATE = ["back_head", "none"]                                  # 하나라도 참이면 크롭 제외
TARGETS = [a for a in ATTR_NAMES if a not in GATE]           # eyes_open·mouth_open·mouth_covered·frown


def main() -> int:
    labels = load_labels(CSV, ATTR_NAMES)
    if not labels:
        print(f"labels.csv 없음: {CSV}\n먼저 grid_label.py 로 라벨링하세요.")
        return 1
    usable = {n: v for n, v in labels.items()
              if v.get("labeled") and not any(v.get(g) for g in GATE)}
    if not usable:
        print("학습 가능한 크롭 없음(라벨완료·뒤통수/None 제외 후 0개).")
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    imgs = OUT / "images"
    imgs.mkdir(parents=True, exist_ok=True)

    rows, counts = [], {a: 0 for a in TARGETS}
    for name, v in usable.items():
        src = CROPS / name
        if not src.exists():
            continue
        shutil.copy(src, imgs / name)
        rows.append([name, *[v.get(a, 0) for a in TARGETS]])
        for a in TARGETS:
            counts[a] += bool(v.get(a))
    with open(OUT / "labels.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file", *TARGETS])
        w.writerows(rows)

    print(f"멀티라벨 데이터셋 {len(rows)}장 → {OUT}")
    print(f"  타깃 속성: {TARGETS}")
    for a in TARGETS:
        print(f"  {a:14s} 양성 {counts[a]}/{len(rows)}")
    print("다음: ..\\3_classification_training\\run_training_multilabel.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
