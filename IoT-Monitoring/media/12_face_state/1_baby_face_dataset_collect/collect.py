#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\1_baby_face_dataset_collect
#   ..\..\.venv\Scripts\python.exe collect.py --n-clips 200      # carved-08 클립에서 얼굴 크롭 수집
#   ..\..\.venv\Scripts\python.exe collect.py --src <이미지폴더> --images   # 이미지 폴더에서 수집
#   → crops\ 에 얼굴 크롭 저장 후, grid_label.py 로 눈/입 라벨링
# ─────────────────────────────────────────────────────────────
r"""baby_face 감지 → 크롭 수집 (auto-label 의 얼굴 박스를 잘라 모으는 것과 동일).

8의 2클래스 모델로 baby_face(1)를 감지하고, **얼굴 박스만 여유(margin) 두고 크롭**해 crops\ 에 저장.
너무 작은 얼굴은 건너뛴다(눈/입 판별 불가). 모델 로더는 4_detection_pretrained 재사용.
"""
import argparse
import os
import random
import sys
from pathlib import Path

import cv2

MEDIA = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MEDIA / "4_detection_pretrained"))

DEFAULT_MODEL = str(MEDIA / "8_detection_2class_train" / "output" / "60" / "model.pth")
DEFAULT_SRCS = [r"D:\carved-08\Cut", r"D:\carved\Cut"]
FACE_CLASS = 1                       # 2클래스 모델: 0=baby, 1=baby_face
FRAME_FRACS = [0.1, 0.5, 0.9]        # 클립당 추출 지점(비율)


def _crop(frame, box, margin):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    mx, my = (x2 - x1) * margin, (y2 - y1) * margin
    x1, y1 = max(0, int(x1 - mx)), max(0, int(y1 - my))
    x2, y2 = min(w, int(x2 + mx)), min(h, int(y2 + my))
    return frame[y1:y2, x1:x2] if x2 > x1 and y2 > y1 else None


def _faces(model, frame, args):
    r = model.predict(frame, conf=args.conf, classes=[FACE_CLASS], imgsz=640, verbose=False)[0]
    out = []
    for b in (r.boxes or []):
        c = _crop(frame, [float(v) for v in b.xyxy[0]], args.margin)
        if c is not None and min(c.shape[:2]) >= args.min_size:
            out.append(c)
    return out


def _frames(path):
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    res = []
    for fr in FRAME_FRACS:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(total * fr)))
        ok, f = cap.read()
        if ok and f is not None:
            res.append((int(total * fr), f))
    cap.release()
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="baby_face 크롭 수집")
    ap.add_argument("--src", default=next((s for s in DEFAULT_SRCS if Path(s).is_dir()), DEFAULT_SRCS[0]))
    ap.add_argument("--images", action="store_true", help="src 를 이미지 폴더로 취급(클립 아님)")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "crops"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--n-clips", type=int, default=200, help="처리 클립/이미지 수 (0=전체)")
    ap.add_argument("--conf", type=float, default=0.5, help="baby_face 채택 conf")
    ap.add_argument("--margin", type=float, default=0.25, help="박스 확장 비율(얼굴 여유)")
    ap.add_argument("--min-size", type=int, default=48, help="이보다 작은 얼굴(px)은 버림")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    try:
        from src.inference import load_detector
    except ImportError:
        print("ultralytics/4_detection_pretrained 필요")
        return 1
    if not Path(args.model).exists():
        print(f"모델 없음: {args.model} — 먼저 8_detection_2class_train 학습")
        return 1

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    exts = (".jpg", ".jpeg", ".png", ".bmp")
    items = ([p for p in sorted(Path(args.src).glob("*")) if p.suffix.lower() in exts]
             if args.images else sorted(Path(args.src).glob("*.mp4")))
    random.seed(args.seed)
    random.shuffle(items)
    if args.n_clips > 0:
        items = items[: args.n_clips]
    print(f"src={args.src} ({'이미지' if args.images else '클립'}) {len(items)}개 → {out}")

    model = load_detector(args.model)
    n = 0
    for it in items:
        frames = [(0, cv2.imread(str(it)))] if args.images else _frames(it)
        for idx, fr in frames:
            if fr is None:
                continue
            for i, crop in enumerate(_faces(model, fr, args)):
                cv2.imwrite(str(out / f"{it.stem}_f{idx:04d}_{i}.jpg"), crop)
                n += 1
    print(f"\n얼굴 크롭 {n}개 저장 → {out}\n다음: grid_label.py 로 눈/입 라벨링")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
