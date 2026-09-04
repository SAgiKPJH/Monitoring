"""단발 추론 — 스트림에서 N프레임 캡처 → 감지+포즈 → 오버레이 저장(창 없이).

라이브 창 없이 "추론 한번 돌려보기" 용. 결과는 out/shot_NNNN.jpg + 콘솔 요약.
"""
import time
from pathlib import Path

import cv2

from .inference import infer, draw


def run(cap, how, det, pose, *, scale=0.5, conf=0.20, classes=None, frames=20, out_dir="out"):
    print(f"소스: {how}")
    out = Path(out_dir)
    out.mkdir(exist_ok=True)
    saved = miss = hit = 0
    while saved < frames:
        ok, frame = cap.read()
        if not ok or frame is None:
            miss += 1
            if miss > 120:
                print("[정보] 프레임 수신 실패로 중단")
                break
            continue
        miss = 0
        frame = cv2.resize(frame, None, fx=scale, fy=scale)
        t1 = time.time()
        det_r, pose_r = infer(det, pose, frame, conf, classes)
        ms = (time.time() - t1) * 1000
        vis = frame.copy()
        n_det = draw(vis, det_r, pose_r)
        saved += 1
        hit += n_det > 0
        top = 0.0
        if det_r is not None and det_r.boxes is not None and len(det_r.boxes):
            top = float(det_r.boxes.conf.max())
        cv2.imwrite(str(out / f"shot_{saved:04d}.jpg"), vis)
        print(f"  {saved}/{frames}  det {n_det} (최고 {top:.2f})  infer {ms:.0f}ms")
    cap.release()
    print(f"\n완료 — {saved}프레임 중 {hit}프레임 검출 · 결과: {out.resolve()}")
