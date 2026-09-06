#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\10_auto_labeling_2class
#   ..\.venv\Scripts\python.exe auto_label.py --n-clips 100      # 랜덤 100클립 (권장 시작값)
#   ..\.venv\Scripts\python.exe auto_label.py --n-clips 0        # 전체 클립 (0=무제한)
#   ..\.venv\Scripts\python.exe auto_label.py --conf 0.5         # 채택 문턱 조정
#
#   모델 = 학습한 2클래스 모델 (8_detection_2class_train\output\60\model.pth) — 기본값
#     best 로 바꾸려면: --model ..\8_detection_2class_train\output\best\model.pth
#   입력 = carved-08\Cut (영상당 첫·중간 2프레임) · 출력 = 이 폴더 dataset\ (baby 0 · baby_face 1)
#   검수 = 이 폴더 _preview_auto\ 몽타주 → 잘못된 라벨은 dataset\images|labels 에서 삭제
# ─────────────────────────────────────────────────────────────
#
# ..\.venv\Scripts\python.exe auto_label.py --n-clips 100 --model ..\8_detection_2class_train\output\60\model.pth
#
"""학습한 2클래스 모델로 baby·baby_face 의사라벨 자동 생성 — 영상당 2프레임(첫·중간).

클립마다 첫·중간 프레임에 파인튜닝 2클래스 모델을 돌려 baby(0)·baby_face(1) 를 잡고,
채택된 박스를 **클래스 id 그대로** YOLO 라벨로 저장(반자동 pseudo-label 확장).
출력은 이 폴더 dataset\\(classes.txt 포함)에 합쳐진다(증분·이미 라벨된 클립 제외).
클래스 이름은 모델 model_info.json 에서 자동. 모델 로더는 4_detection_pretrained 재사용. BGR 유지.
"""
import argparse
import csv
import os
import random
import sys
from pathlib import Path

import cv2

# 학습 모델(.pth) 로더 재사용 — 4_detection_pretrained/src/inference.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "4_detection_pretrained"))

DEFAULT_SRCS = [r"D:\carved-08\Cut", r"D:\carved\Cut"]
TRAINED_MODEL = str(Path(__file__).resolve().parent.parent
                    / "8_detection_2class_train" / "output" / "60" / "model.pth")
FRAME_FRACS = [0.0, 0.5]        # 영상당: 첫 프레임(0), 중간 프레임(0.5)
CLASS_COLORS = [(0, 255, 0), (255, 0, 255), (0, 165, 255), (255, 255, 0)]  # BGR, 클래스별


def _detect_save(model, fr, stem, out, args):
    """한 프레임 감지+저장(클래스 id 유지). 채택 시 (manifest_row, montage_tile), 아니면 None."""
    h, w = fr.shape[:2]
    r = model.predict(fr, conf=args.conf, verbose=False)[0]   # 2클래스 전체
    boxes = []
    for b in (r.boxes or []):
        x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
        area = (x2 - x1) * (y2 - y1) / (w * h)
        if args.min_area <= area <= args.max_area:
            boxes.append((x1, y1, x2, y2, int(b.cls), float(b.conf)))
    if not boxes:
        return None
    cv2.imwrite(str(out / "images" / f"{stem}.jpg"), fr)
    with open(out / "labels" / f"{stem}.txt", "w") as f:
        for x1, y1, x2, y2, cls, _ in boxes:
            f.write(f"{cls} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
                    f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}\n")
    vis = fr.copy()
    for x1, y1, x2, y2, cls, cf in boxes:
        col = CLASS_COLORS[cls % len(CLASS_COLORS)]
        cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), col, 3)
        cv2.putText(vis, f"{cls}:{cf:.2f}", (int(x1), max(int(y1) - 8, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, col, 2)
    cv2.putText(vis, stem[:28], (8, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    n_face = sum(1 for b in boxes if b[4] == 1)
    return ([f"{stem}.jpg", len(boxes), n_face, round(max(b[5] for b in boxes), 3)],
            cv2.resize(vis, (480, 270)))


def _frames(clip):
    """(frame_idx, image) 리스트 — 첫 프레임 + 중간 프레임."""
    cap = cv2.VideoCapture(str(clip))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    result = []
    for frac in FRAME_FRACS:
        idx = 0 if frac == 0 else max(int(total * frac), 0)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = cap.read()
        if ok and fr is not None:
            result.append((idx, fr))
    cap.release()
    return result


def _write_classes(out, model):
    """모델 클래스명으로 classes.txt 작성(id 순). OD_Training_Standard nc 결정용."""
    names = getattr(model, "names", {0: "baby", 1: "baby_face"})
    ordered = [names[i] for i in sorted(names)] if isinstance(names, dict) else list(names)
    (out / "classes.txt").write_text("\n".join(ordered) + "\n", encoding="utf-8")


def _write_review(review, tiles, rows):
    import numpy as np
    (review / "_preview_auto").mkdir(parents=True, exist_ok=True)
    for s in range(0, len(tiles), 49):
        grid, cols = tiles[s:s + 49], 7
        rows_n = -(-len(grid) // cols)
        sheet = np.zeros((rows_n * 270, cols * 480, 3), dtype="uint8")
        for i, t in enumerate(grid):
            sheet[i // cols * 270:(i // cols + 1) * 270, i % cols * 480:(i % cols + 1) * 480] = t
        cv2.imwrite(str(review / "_preview_auto" / f"preview_{s // 49:02d}.jpg"), sheet)
    mf = review / "auto_label_manifest.csv"
    new = not mf.exists()
    with open(mf, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["file", "n_boxes", "n_face", "top_conf"])
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="baby+baby_face 2클래스 의사라벨 자동 생성 (영상당 2프레임)")
    ap.add_argument("--src", default=next((s for s in DEFAULT_SRCS if Path(s).is_dir()), DEFAULT_SRCS[0]))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "dataset"),
                    help="의사라벨 저장 폴더 (기본: 이 폴더의 dataset)")
    ap.add_argument("--model", default=TRAINED_MODEL, help="라벨 공장 (기본: 8의 2클래스 60 모델)")
    ap.add_argument("--n-clips", type=int, default=200, help="처리 클립 수 (0=전체)")
    ap.add_argument("--conf", type=float, default=0.5, help="채택 최소 conf")
    ap.add_argument("--min-area", type=float, default=0.0, help="하한(작은 얼굴 허용 위해 0)")
    ap.add_argument("--max-area", type=float, default=0.9, help="상한 (과대 박스 배제)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--review", default="", help="검수 몽타주/manifest 폴더 (기본: 이 폴더)")
    args = ap.parse_args()

    try:
        from src.inference import load_detector          # 4_detection_pretrained/src
    except ImportError:
        print("ultralytics/4_detection_pretrained 가 필요합니다:  pip install ultralytics")
        return 1
    if not Path(args.model).exists():
        print(f"학습 모델이 없습니다: {args.model}\n먼저 8_detection_2class_train\\run_training.py 로 학습하세요.")
        return 1

    out = Path(args.out)
    review = Path(args.review) if args.review else Path(__file__).resolve().parent
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(exist_ok=True)

    done = {p.name.split("_f")[0] for p in (out / "images").glob("*.jpg")}
    clips = [c for c in sorted(Path(args.src).glob("*.mp4")) if c.stem not in done]
    random.seed(args.seed)
    random.shuffle(clips)
    if args.n_clips > 0:
        clips = clips[: args.n_clips]
    print(f"src={args.src}\n대상 {len(clips)}클립 × 2프레임 (이미 라벨된 클립 {len(done)} 제외) → {out}")

    model = load_detector(args.model)                    # 2클래스 .pth → ultralytics YOLO
    _write_classes(out, model)
    rows, tiles, n_clip, n_frame, n_face = [], [], 0, 0, 0
    for clip in clips:
        got = False
        for idx, fr in _frames(clip):
            res = _detect_save(model, fr, f"{clip.stem}_f{idx:04d}auto", out, args)
            if res:
                rows.append(res[0])
                tiles.append(res[1])
                n_frame += 1
                n_face += res[0][2]
                got = True
        n_clip += 1
        if got and n_clip % 50 == 0:
            print(f"  클립 {n_clip}/{len(clips)} · 라벨 {n_frame}장 (face {n_face})")

    _write_review(review, tiles, rows)
    print(f"\n의사라벨 {n_frame}장 저장 (baby_face 박스 {n_face}개) → {out}\\images|labels")
    print(f"검수: {review}\\_preview_auto\\ 몽타주 확인 — 잘못된 것은 {out}\\images|labels 에서 삭제")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
