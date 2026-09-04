#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\7_auto_labeling
#   ..\.venv\Scripts\python.exe auto_label.py --n-clips 100      # 랜덤 100클립 (권장 시작값)
#   ..\.venv\Scripts\python.exe auto_label.py                    # 랜덤 200클립 (기본)
#   ..\.venv\Scripts\python.exe auto_label.py --n-clips 0        # 전체 클립 (0=무제한)
#   ..\.venv\Scripts\python.exe auto_label.py --conf 0.5         # 채택 문턱 조정
#
#   모델 = 우리가 학습한 baby 모델 (5_detection_train\output\best\model.pth) — 기본값, 지정 불필요
#   ..\.venv\Scripts\python.exe auto_label.py --n-clips 100 --model ..\5_detection_train\output\best\model.pth
#   입력 = carved-08\Cut (영상당 첫·중간 2프레임) · 출력 = 이 폴더 dataset\ (7_auto_labeling\dataset) 에 합침
#   검수 = 이 폴더 _preview_auto\ 몽타주 → 잘못된 라벨은 dataset\images|labels 에서 삭제
# ─────────────────────────────────────────────────────────────
"""우리가 학습한 baby 모델로 아기 의사라벨 자동 생성 — 영상당 2프레임(첫·중간).

지정한 클립 폴더(기본 carved-08\\Cut)를 훑어 각 영상의 **첫 프레임과 중간 프레임**에
파인튜닝 baby 모델(5_detection_train\\output\\best\\model.pth)을 돌려 아기를 잡고,
면적 필터를 통과한 것만 YOLO 라벨(class 0=baby)로 저장한다(반자동 pseudo-label 확장).
출력은 이 폴더의 dataset\\(7_auto_labeling\\dataset)에 합쳐진다(증분·이미 라벨된 클립 제외).
모델 로더는 4_detection_pretrained\\src\\inference.load_detector 재사용. BGR 그대로 저장.
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
                    / "5_detection_train" / "output" / "best" / "model.pth")
FRAME_FRACS = [0.0, 0.5]        # 영상당: 첫 프레임(0), 중간 프레임(0.5)


def _detect_save(model, fr, stem, out, args):
    """한 프레임 감지+저장. 채택 시 (manifest_row, montage_tile), 아니면 None."""
    h, w = fr.shape[:2]
    r = model.predict(fr, conf=args.conf, verbose=False)[0]   # baby 단일 클래스
    boxes = []
    for b in (r.boxes or []):
        x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
        area = (x2 - x1) * (y2 - y1) / (w * h)
        if args.min_area <= area <= args.max_area:
            boxes.append((x1, y1, x2, y2, float(b.conf)))
    if not boxes:
        return None
    cv2.imwrite(str(out / "images" / f"{stem}.jpg"), fr)
    with open(out / "labels" / f"{stem}.txt", "w") as f:
        for x1, y1, x2, y2, _ in boxes:
            f.write(f"0 {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
                    f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}\n")
    vis = fr.copy()
    for x1, y1, x2, y2, cf in boxes:
        cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)
        cv2.putText(vis, f"{cf:.2f}", (int(x1), max(int(y1) - 8, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    cv2.putText(vis, stem[:28], (8, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    return ([f"{stem}.jpg", len(boxes), round(max(b[4] for b in boxes), 3)],
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
            w.writerow(["file", "n_boxes", "top_conf"])
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="person 의사라벨 자동 생성 (영상당 2프레임)")
    ap.add_argument("--src", default=next((s for s in DEFAULT_SRCS if Path(s).is_dir()), DEFAULT_SRCS[0]))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "dataset"),
                    help="의사라벨 저장 폴더 (기본: 이 폴더의 dataset — 7_auto_labeling\\dataset)")
    ap.add_argument("--model", default=TRAINED_MODEL, help="라벨 공장 (기본: 학습한 baby 모델)")
    ap.add_argument("--n-clips", type=int, default=200, help="처리 클립 수 (0=전체)")
    ap.add_argument("--conf", type=float, default=0.4, help="채택 최소 conf")
    ap.add_argument("--min-area", type=float, default=0.01)
    ap.add_argument("--max-area", type=float, default=0.45, help="상한 (근접 어른 몸통 배제)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--review", default="", help="검수 몽타주/manifest 폴더 (기본: 이 폴더)")
    args = ap.parse_args()

    try:
        from src.inference import load_detector          # 4_detection_pretrained/src
    except ImportError:
        print("ultralytics/4_detection_pretrained 가 필요합니다:  pip install ultralytics")
        return 1
    if not Path(args.model).exists():
        print(f"학습 모델이 없습니다: {args.model}\n먼저 5_detection_train\\run_training.py 로 학습하세요.")
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

    model = load_detector(args.model)                    # baby .pth → ultralytics YOLO
    rows, tiles, n_clip, n_frame = [], [], 0, 0
    for clip in clips:
        got = False
        for idx, fr in _frames(clip):
            res = _detect_save(model, fr, f"{clip.stem}_f{idx:04d}auto", out, args)
            if res:
                rows.append(res[0])
                tiles.append(res[1])
                n_frame += 1
                got = True
        n_clip += 1
        if got and n_clip % 50 == 0:
            print(f"  클립 {n_clip}/{len(clips)} · 라벨 {n_frame}장")

    _write_review(review, tiles, rows)
    print(f"\n의사라벨 {n_frame}장 저장 → {out}\\images|labels (접미사 'auto')")
    print(f"검수: {review}\\_preview_auto\\ 몽타주 확인 — 잘못된 것은 {out}\\images|labels 에서 삭제")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
