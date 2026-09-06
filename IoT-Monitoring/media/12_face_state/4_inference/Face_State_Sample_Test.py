#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\4_inference
#   ..\..\.venv\Scripts\python.exe Face_State_Sample_Test.py               # carved-08 클립에서
#   ..\..\.venv\Scripts\python.exe Face_State_Sample_Test.py --n-clips 30
#   창(라벨툴처럼): a/d ±1프레임 · w/s ±1초 · 트랙바(프레임 슬라이더) · n/p 클립 · r 랜덤 · space 저장 · q 종료
#   각 프레임에 baby·baby_face 감지 + baby_face 상태를 오버레이(원본에서 감지·크롭)
# ─────────────────────────────────────────────────────────────
r"""mp4 클립(라벨링 때와 동일 소스)에서 프레임을 떠서 → baby·baby_face 감지(8 모델) →
baby_face 크롭 → 얼굴상태 멀티라벨 추론 → 결과 오버레이 저장(out_sample\).

라이브 스트림이 아니라 **클립 파일**을 그때그때 읽어 처리한다. 감지기는 4_detection_pretrained 재사용,
얼굴상태는 3단계 output_ml_<net>. (실시간 창은 Face_State_Live_Test.py)
"""
import argparse
import random
import sys
from pathlib import Path

import cv2
import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1] / "4_detection_pretrained"))

from face_state import load_face_state, predict            # noqa: E402
from src.inference import load_detector                    # noqa: E402

DEFAULT_SRCS = [r"D:\carved-08\Cut", r"D:\carved\Cut"]
DET_MODEL = str(_HERE.parents[1] / "8_detection_2class_train" / "output" / "60" / "model.pth")
FACE_MODEL_DIR = _HERE.parent / "3_classification_training" / "output_ml_mobilenet_v2"
BABY_CLASS, FACE_CLASS = 0, 1        # 8 모델: 0=baby, 1=baby_face
SCALE = 0.6                          # 표시 축소(감지·크롭은 원본에서)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _render(frame, r, model, meta, args, title):
    """원본 프레임 감지 결과 r + baby_face 상태를 축소 이미지에 오버레이(감지·크롭은 원본)."""
    show = cv2.resize(frame, None, fx=SCALE, fy=SCALE) if SCALE != 1 else frame.copy()
    for b in (r.boxes or []):
        cls, cf = int(b.cls), float(b.conf)
        x1, y1, x2, y2 = (float(v) for v in b.xyxy[0])
        sx1, sy1, sx2, sy2 = int(x1 * SCALE), int(y1 * SCALE), int(x2 * SCALE), int(y2 * SCALE)
        if cls == FACE_CLASS:
            mw, mh = (x2 - x1) * args.margin, (y2 - y1) * args.margin
            crop = frame[max(0, int(y1 - mh)):int(y2 + mh), max(0, int(x1 - mw)):int(x2 + mw)]
            cv2.rectangle(show, (sx1, sy1), (sx2, sy2), (255, 0, 255), 2)
            if crop.size:
                st = predict(model, meta, crop, args.thr)
                yy = sy1 + 2
                for a, (p, on) in st.items():
                    yy += 15
                    cv2.putText(show, f"{a[:9]}:{p:.2f}", (sx2 + 4, yy), FONT, 0.42,
                                (0, 230, 0) if on else (150, 150, 150), 1)
        else:
            cv2.rectangle(show, (sx1, sy1), (sx2, sy2), (0, 255, 0), 2)
        cv2.putText(show, f"{'baby_face' if cls == FACE_CLASS else 'baby'} {cf:.2f}",
                    (sx1, max(sy1 - 5, 12)), FONT, 0.45,
                    (255, 0, 255) if cls == FACE_CLASS else (0, 255, 0), 1)
    cv2.putText(show, title, (8, 20), FONT, 0.5, (0, 255, 255), 2)
    cv2.putText(show, "a/d:+-1f  w/s:+-1s  n/p:clip  space:save  q:quit",
                (8, show.shape[0] - 10), FONT, 0.45, (200, 200, 200), 1)
    return show


def main() -> int:
    ap = argparse.ArgumentParser(description="mp4 클립에서 baby_face 크롭 → 얼굴상태 추론")
    ap.add_argument("--src", default=next((s for s in DEFAULT_SRCS if Path(s).is_dir()), DEFAULT_SRCS[0]))
    ap.add_argument("--n-clips", type=int, default=20, help="처리 클립 수 (0=전체)")
    ap.add_argument("--conf", type=float, default=0.8, help="baby/baby_face 채택 conf")
    ap.add_argument("--margin", type=float, default=0.25, help="얼굴 박스 확장 비율")
    ap.add_argument("--thr", type=float, default=None, help="속성 on 임계(미지정=속성별 ATTR_THR)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if not (FACE_MODEL_DIR / "best.pth").exists():
        print(f"[에러] 얼굴상태 모델 없음: {FACE_MODEL_DIR}\\best.pth\n먼저 run_training_multilabel.py 학습")
        return 1
    if not Path(DET_MODEL).exists():
        print(f"[에러] 감지 모델 없음: {DET_MODEL}")
        return 1
    clips = sorted(Path(args.src).glob("*.mp4"))
    if not clips:
        print(f"[에러] 클립 없음: {args.src}")
        return 1
    random.seed(args.seed)
    random.shuffle(clips)
    if args.n_clips > 0:
        clips = clips[: args.n_clips]

    det = load_detector(DET_MODEL)
    model, meta = load_face_state(FACE_MODEL_DIR)
    print(f"src={args.src}  clips={len(clips)}  attrs={meta['attrs']}")
    out = _HERE / "out_sample"
    out.mkdir(exist_ok=True)

    win = "12 face-state sample (det + state)"
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
    TRACK = "frame"
    nav = {"seek": 0, "guard": False}                        # 트랙바 ↔ 루프 공유
    cv2.createTrackbar(TRACK, win, 0, 1,
                       lambda p: None if nav["guard"] else nav.__setitem__("seek", p))
    print("창 — a/d:±1f · w/s:±1s · 트랙바:프레임 · n/p:클립 · r:랜덤 · space:저장 · q/ESC:종료")
    saved, ci = 0, 0
    while 0 <= ci < len(clips):
        cap = cv2.VideoCapture(str(clips[ci]))
        fps = int((cap.get(cv2.CAP_PROP_FPS) or 15) or 15)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        if total <= 0:
            cap.release()
            ci += 1
            continue
        try:
            cv2.setTrackbarMax(TRACK, win, max(total - 1, 1))
        except cv2.error:
            pass
        nav["seek"] = 0
        fi, cur, show, dirty, act = -1, None, None, True, None
        while True:
            if nav["seek"] != fi:                            # 트랙바/키로 프레임 이동
                fi = max(0, min(nav["seek"], total - 1))
                cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
                ok, cur = cap.read()
                dirty = True
                nav["guard"] = True
                try:
                    cv2.setTrackbarPos(TRACK, win, fi)
                except cv2.error:
                    pass
                nav["guard"] = False
            if dirty and cur is not None:                    # 프레임 바뀔 때만 감지(비쌈)
                r = det.predict(cur, conf=args.conf, verbose=False)[0]
                show = _render(cur, r, model, meta, args,
                               f"{clips[ci].stem} [{ci + 1}/{len(clips)}] f{fi + 1}/{total}")
                dirty = False
            if show is not None:
                cv2.imshow(win, show)
            k = cv2.waitKey(30) & 0xFF
            if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                act = "quit"
                break
            if k == 255:
                continue
            if k in (ord("q"), 27):
                act = "quit"
                break
            if k == ord("n"):
                act = "next"
                break
            if k == ord("p"):
                act = "prev"
                break
            if k == ord("r"):
                act = "random"
                break
            if k == ord("d"):
                nav["seek"] = min(fi + 1, total - 1)
            elif k == ord("a"):
                nav["seek"] = max(fi - 1, 0)
            elif k == ord("w"):
                nav["seek"] = min(fi + fps, total - 1)
            elif k == ord("s"):
                nav["seek"] = max(fi - fps, 0)
            elif k == ord(" ") and show is not None:
                cv2.imwrite(str(out / f"det_state_{clips[ci].stem}_f{fi:04d}.jpg"), show)
                saved += 1
                print(f"  저장 {saved}: {clips[ci].stem} f{fi}")
        cap.release()
        if act == "quit":
            break
        if act == "random" and len(clips) > 1:               # r: 다른 랜덤 클립
            j = ci
            while j == ci:
                j = random.randrange(len(clips))
            ci = j
        else:
            ci = max(0, min(ci + (1 if act == "next" else -1), len(clips) - 1))
    cv2.destroyAllWindows()
    print(f"\n완료 — 저장 {saved}장 → {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
