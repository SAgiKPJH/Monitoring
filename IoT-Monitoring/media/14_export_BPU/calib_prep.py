#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (PC, 이 폴더에서):
#   ..\.venv\Scripts\python.exe calib_prep.py --frames ..\13_pose_train\dataset\images --n 100
#   → calib\frames\*.jpg (640x640 letterbox, detection·pose 용) · calib\faces\*.jpg (128x128, face_state 용)
# ─────────────────────────────────────────────────────────────
r"""hb_mapper 캘리브레이션 이미지(jpg) 준비 — **런타임과 똑같은 전처리**로 만들어 INT8 양자화 정확도 확보.

- calib/frames/ : 프레임을 15_rdk_x5_runtime/src/yolo_post.letterbox 로 **640x640 letterbox**(회색 패딩) 한 것.
                  hb_mapper 의 preprocess_on 은 단순 resize 라 원본(1920x1080)을 주면 찌그러진 분포로 캘리브레이션됨 →
                  보드 입력(letterbox)과 어긋난다. 640x640 을 주면 resize 가 항등이라 분포가 일치.
                  **아기가 있는 프레임을 우선**(torch 검출기 conf≥0.5)으로 뽑아 실제 활성값 범위를 담고, 배경도 일부 섞는다.
- calib/faces/  : baby_face 크롭을 face_state 런타임과 같이 128x128 로 squash 리사이즈한 것.
"""
import argparse
import random
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
RDK = HERE.parent / "15_rdk_x5_runtime"
sys.path.insert(0, str(RDK))
from src.yolo_post import letterbox  # noqa: E402  (보드와 동일 letterbox)

FACE_CLASS, DET_CONF = 1, 0.5
BG_RATIO = 0.2                       # 배경(미검출) 프레임 비율


def main() -> int:
    ap = argparse.ArgumentParser(description="캘리브레이션 이미지 준비(런타임 동일 전처리)")
    ap.add_argument("--frames", default=str(HERE.parent / "13_pose_train" / "dataset" / "images"),
                    help="전체 프레임 jpg 폴더(카메라 원본 분포)")
    ap.add_argument("--n", type=int, default=100, help="프레임 수(640x640)")
    ap.add_argument("--faces", type=int, default=100, help="얼굴 크롭 목표 수(128x128)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    imgs = sorted(Path(args.frames).glob("*.jpg"))
    if not imgs:
        print(f"[에러] 이미지 없음: {args.frames}")
        return 1
    random.Random(args.seed).shuffle(imgs)
    det_pth = RDK / "models" / "detection.pth"
    if not det_pth.exists():                                   # 기존 calib/ 를 지우기 전에 먼저 확인
        print(f"[에러] {det_pth} 없음 — PC 용 torch 원본(8/output/60/model.pth)을 models/ 에 두세요")
        return 1
    from src.vision import load_detector                       # torch 검출기(PC)로 아기/얼굴 프레임 선별
    det = load_detector(str(det_pth))
    fr_dir, fc_dir = HERE / "calib" / "frames", HERE / "calib" / "faces"
    for d in (fr_dir, fc_dir):
        if d.exists():
            for f in d.glob("*"):
                f.unlink()
        d.mkdir(parents=True, exist_ok=True)
    n_baby, n_bg, n_face = 0, 0, 0
    max_bg = int(args.n * BG_RATIO)
    for p in imgs:
        if n_baby + n_bg >= args.n and n_face >= args.faces:
            break
        fr = cv2.imread(str(p))
        if fr is None:
            continue
        r = det.predict(fr, conf=DET_CONF, verbose=False)[0]
        boxes = list(r.boxes or [])
        has_baby = any(int(b.cls) != FACE_CLASS for b in boxes)
        if n_baby + n_bg < args.n and (has_baby or n_bg < max_bg):
            lb, _, _ = letterbox(fr, 640)                       # 런타임과 동일 입력
            cv2.imwrite(str(fr_dir / p.name), lb, [cv2.IMWRITE_JPEG_QUALITY, 95])
            if has_baby:
                n_baby += 1
            else:
                n_bg += 1
        for b in boxes:
            if int(b.cls) == FACE_CLASS and n_face < args.faces:
                x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
                crop = fr[max(0, y1):y2, max(0, x1):x2]
                if crop.size:
                    cv2.imwrite(str(fc_dir / f"{p.stem}_{n_face:03d}.jpg"),
                                cv2.resize(crop, (128, 128)), [cv2.IMWRITE_JPEG_QUALITY, 95])
                    n_face += 1
    print(f"frames: {n_baby + n_bg}장 (아기 {n_baby} · 배경 {n_bg}) 640x640 letterbox → {fr_dir}")
    print(f"faces : {n_face}장 128x128 → {fc_dir}" + ("" if n_face >= 20 else "  [경고] 너무 적음 — --frames 폴더를 늘리세요"))
    if n_baby < args.n * 0.5:
        print(f"[경고] 아기 포함 프레임이 {n_baby}장뿐 — 캘리브레이션이 배경 위주가 되면 점수 범위가 어긋날 수 있음. 아기 프레임 폴더를 --frames 로 주세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
