#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\13_pose_train
#   ..\.venv\Scripts\python.exe 2_build_data.py
#   → dataset\ 를 train/val 로 나누고 data.yaml + train.txt/val.txt 생성 (3_run_training 전 단계)
#   비율/시드 변경:  --val 0.2  --seed 0
# ─────────────────────────────────────────────────────────────
r"""dataset\(images·labels 평면) → data.yaml + train/val 리스트 생성.

1_pose_correct.py 가 dataset\images, dataset\labels 에 저장한 YOLO-pose 라벨을
**clip(=같은 영상) 단위**로 train/val 분할(프레임 누수 방지)하고 ultralytics 학습용
data.yaml + train.txt/val.txt 를 만든다. 이미지/라벨 파일은 그대로 두고 리스트만
갱신하므로, 1_pose_correct 로 라벨을 더 추가한 뒤 다시 실행하면 그대로 반영된다.
빈 라벨(.txt)=배경 negative 도 학습에 포함(오탐 감소).
"""
import argparse
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "3_detection_labeling_tool" / "pose_label_tool"))
from pose_format import FLIP_IDX, NUM_KPTS  # noqa: E402  (17 keypoint · 좌우반전 인덱스)

VAL_RATIO = 0.2                              # 검증 비율(clip 기준)
SEED = 0


def _clip_of(stem):
    return stem.rsplit("_f", 1)[0]           # '{영상}_f0000' → '{영상}'


def main() -> int:
    ap = argparse.ArgumentParser(description="pose dataset → data.yaml + train/val split")
    ap.add_argument("--dataset", default=str(HERE / "dataset"), help="images/labels 있는 폴더")
    ap.add_argument("--val", type=float, default=VAL_RATIO, help="검증 비율(0~1, clip 기준)")
    ap.add_argument("--seed", type=int, default=SEED, help="분할 셔플 시드")
    args = ap.parse_args()

    root = Path(args.dataset)
    img_dir, lbl_dir = root / "images", root / "labels"
    if not img_dir.is_dir() or not lbl_dir.is_dir():
        print(f"[에러] {img_dir} 또는 {lbl_dir} 없음 — 먼저 1_pose_correct.py 로 라벨 생성")
        return 1

    pairs = [img for img in sorted(img_dir.glob("*.jpg"))
             if (lbl_dir / f"{img.stem}.txt").exists()]        # 라벨 있는 이미지만(빈 txt 포함)
    if not pairs:
        print(f"[에러] 라벨(.txt) 있는 이미지 없음: {lbl_dir}")
        return 1

    clips = {}                                                  # clip 단위 그룹 → 누수 방지
    for img in pairs:
        clips.setdefault(_clip_of(img.stem), []).append(img)
    keys = sorted(clips)
    random.Random(args.seed).shuffle(keys)
    n_val = round(len(keys) * args.val) if len(keys) > 1 else 0
    val_keys = set(keys[:n_val])
    train = [p for k in keys if k not in val_keys for p in clips[k]]
    val = [p for k in val_keys for p in clips[k]]
    if not val:
        print("[경고] val 이 비었습니다(클립이 1개거나 --val 이 너무 작음). train 만으로 학습됩니다.")

    (root / "train.txt").write_text("\n".join(str(p.resolve()) for p in train) + "\n", encoding="utf-8")
    (root / "val.txt").write_text(("\n".join(str(p.resolve()) for p in val) + "\n") if val else "", encoding="utf-8")

    flip = ", ".join(str(i) for i in FLIP_IDX)
    (root / "data.yaml").write_text(
        "# 자동 생성: 2_build_data.py — 재구성하려면 다시 실행(덮어씀)\n"
        f"path: {root.resolve()}\n"
        "train: train.txt\n"
        f"val: {'val.txt' if val else 'train.txt'}\n\n"
        f"kpt_shape: [{NUM_KPTS}, 3]   # (x, y, visible)\n"
        f"flip_idx: [{flip}]   # 좌우반전 증강용 keypoint 매핑\n\n"
        "names:\n"
        "  0: baby\n",
        encoding="utf-8")

    print(f"완료 → {root / 'data.yaml'}")
    print(f"  clip {len(keys)}개 · 이미지 {len(pairs)}장 → train {len(train)} / val {len(val)}")
    print("  다음: 3_run_training.py 로 학습")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
