#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\11_variance_measure
#   ..\.venv\Scripts\python.exe live.py
#   키: q/ESC 종료 · s 스크린샷(out\) · [ ] TH_MEAN -/+ · , . TH_MAX -/+
# ─────────────────────────────────────────────────────────────
r"""11_variance_measure/live.py — go2rtc 실시간 스트림의 변화량(YDIF) 측정·표시.

정적일 때와 아기가 움직일 때의 YDIF 를 눈으로 보며 **적당한 threshold** 를 찾는 도구.
현재 YDIF·롤링 평균/최댓값·판정(STATIC/MOTION)·스파크라인을 오버레이하고, out\ydif_live.csv 로 기록.
스트림 수신은 4_detection_pretrained\src\stream_source 재사용.
"""
import csv
import os
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "4_detection_pretrained"))

from variance import classify, summarize, to_gray_small, ydif  # noqa: E402
from src.stream_source import open_source                      # noqa: E402

# ══════════════════════ 설정 ══════════════════════
STREAM_URL = r"http://172.30.1.42:1984/stream.html?src=camera1"
RESIZE_W   = 320          # 변화량 계산용 resize 폭 (지정)
RESIZE_H   = 0            # resize 높이 (0=비율유지, >0=고정 RESIZE_W×RESIZE_H)
WINDOW     = 200          # 롤링 통계/스파크라인 프레임 수 (≈8~13초)
TH_MEAN    = 2.0          # STATIC 판정: meanYDIF < TH_MEAN 이고
TH_MAX     = float("inf")  # maxYDIF < TH_MAX 이면 정적. inf=max 조건 비활성(오직 mean)
LOG_CSV    = True         # out\ydif_live.csv 로 기록
IGNORE_RECT = (0.0, 0.0, 0.30, 0.10)  # 계산 제외 영역 비율(x1,y1,x2,y2) — 좌상단 타임스탬프. None=없음
# ═══════════════════════════════════════════════════

_HERE = Path(__file__).resolve().parent


def _spark(vals, w, h, th):
    img = np.full((h, w, 3), 30, np.uint8)
    if len(vals) >= 2:
        m = max(max(vals), th * 1.5, 1e-3)
        pts = [(int(i * (w - 1) / (len(vals) - 1)), int((h - 1) - min(v, m) / m * (h - 1)))
               for i, v in enumerate(vals)]
        cv2.polylines(img, [np.array(pts, np.int32)], False, (0, 255, 255), 1)
        y = int((h - 1) - min(th, m) / m * (h - 1))
        cv2.line(img, (0, y), (w - 1, y), (60, 60, 255), 1)
    return img


def main():
    global TH_MEAN, TH_MAX
    print(f"stream = {STREAM_URL}\n변화량(YDIF) 측정 — resize={RESIZE_W}x{RESIZE_H or 'auto'} window={WINDOW}")
    cap, how = open_source(STREAM_URL)
    if cap is None:
        print(f"[에러] 스트림 열기 실패: {STREAM_URL} ({how})")
        return 1
    print("소스:", how)
    out = _HERE / "out"
    out.mkdir(exist_ok=True)
    writer = None
    if LOG_CSV:
        fcsv = open(out / "ydif_live.csv", "w", newline="", encoding="utf-8")
        writer = csv.writer(fcsv)
        writer.writerow(["time", "ydif", "mean", "max", "state"])

    vals = deque(maxlen=WINDOW)
    prev = None
    n = miss = 0
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            miss += 1
            if miss > 90:
                print("[정보] 스트림 종료/끊김")
                break
            continue
        miss = 0
        g = to_gray_small(frame, RESIZE_W, RESIZE_H)
        if prev is not None:
            v = ydif(prev, g, IGNORE_RECT)
            vals.append(v)
            mean_y, max_y = summarize(vals)
            state = classify(mean_y, max_y, TH_MEAN, TH_MAX)
            if writer:
                writer.writerow([f"{time.time():.2f}", f"{v:.3f}", f"{mean_y:.3f}",
                                 f"{max_y:.3f}", state])
            vis = frame.copy()
            if IGNORE_RECT:                                  # 무시영역 표시(초록)
                vh, vw = vis.shape[:2]
                cv2.rectangle(vis, (int(IGNORE_RECT[0] * vw), int(IGNORE_RECT[1] * vh)),
                              (int(IGNORE_RECT[2] * vw), int(IGNORE_RECT[3] * vh)), (0, 255, 0), 2)
            col = (0, 200, 0) if state == "STATIC" else (0, 165, 255)
            cv2.putText(vis, f"YDIF now:{v:5.2f}  mean:{mean_y:5.2f}  max:{max_y:5.2f}",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            cv2.putText(vis, f"[{state}]  TH mean<{TH_MEAN:.2f} & max<{TH_MAX:.2f}",
                        (10, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
            cv2.putText(vis, "[ ] mean -/+   , . max -/+   s shot   q quit",
                        (10, vis.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            sp = _spark(list(vals), min(360, vis.shape[1] - 20), 70, TH_MEAN)
            vis[70:70 + sp.shape[0], 10:10 + sp.shape[1]] = sp
            cv2.imshow("11 variance (YDIF)", vis)
        prev = g
        n += 1
        k = cv2.waitKey(1) & 0xFF
        if k in (ord("q"), 27):
            break
        elif k == ord("s"):
            cv2.imwrite(str(out / f"shot_{int(time.time())}.jpg"), frame)
            print("저장:", out.resolve())
        elif k == ord("["):
            TH_MEAN = max(0.0, round(TH_MEAN - 0.02, 3))
        elif k == ord("]"):
            TH_MEAN = round(TH_MEAN + 0.02, 3)
        elif k == ord(","):
            TH_MAX = max(0.0, round(TH_MAX - 0.5, 2))
        elif k == ord("."):
            TH_MAX = round(TH_MAX + 0.5, 2)
    cap.release()
    cv2.destroyAllWindows()
    if writer:
        fcsv.close()
        print(f"기록: {out / 'ydif_live.csv'}")
    print(f"처리 {n}프레임 · 최종 TH mean<{TH_MEAN} & max<{TH_MAX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
