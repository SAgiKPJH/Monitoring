"""실시간 창 — 스트림을 1/scale 축소해 감지+포즈 오버레이 표시.

키: q 종료 · s 스크린샷(out/) · d 감지 토글 · p 포즈 토글
"""
import time
from pathlib import Path

import cv2

from .inference import infer, draw


def run(cap, how, det, pose, *, scale=0.5, conf=0.20, classes=None, out_dir="out"):
    print(f"소스: {how}")
    out = Path(out_dir)
    out.mkdir(exist_ok=True)
    show_det = show_pose = True
    n = miss = 0
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            miss += 1
            if miss > 90:                       # 초반 mid-GOP·일시 끊김 견딤
                print("[정보] 스트림 종료/끊김")
                break
            continue
        miss = 0
        frame = cv2.resize(frame, None, fx=scale, fy=scale)
        t1 = time.time()
        det_r, pose_r = infer(det if show_det else None, pose if show_pose else None,
                              frame, conf, classes)
        ms = (time.time() - t1) * 1000
        vis = frame.copy()
        n_det = draw(vis, det_r, pose_r)
        n += 1
        fps = n / max(time.time() - t0, 1e-3)
        cv2.putText(vis, f"det:{n_det} infer:{ms:.0f}ms fps:{fps:.1f} "
                         "[d]et [p]ose [s]ave [q]uit",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
        cv2.imshow("baby live (det+pose)", vis)
        k = cv2.waitKey(1) & 0xFF
        if k in (ord("q"), 27):
            break
        elif k == ord("s"):
            cv2.imwrite(str(out / f"shot_{int(time.time())}.jpg"), vis)
            print("저장:", out.resolve())
        elif k == ord("d"):
            show_det = not show_det
        elif k == ord("p"):
            show_pose = not show_pose
    cap.release()
    cv2.destroyAllWindows()
    print(f"처리 {n}프레임")
