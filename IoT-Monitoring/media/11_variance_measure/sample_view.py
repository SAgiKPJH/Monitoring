#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\11_variance_measure
#   ..\.venv\Scripts\python.exe sample_view.py --n 100 --interval 1   # 1초마다 비교
#   ..\.venv\Scripts\python.exe sample_view.py --interval 5           # 5초마다 비교
#   창: [video] 영상 · [YDIF data] 측정값  (두 창 분리)
#   키: n/p 다음/이전 클립 · space 일시정지 · [ ] mean-/+ · , . max-/+ · q 종료
# ─────────────────────────────────────────────────────────────
r"""11_variance_measure/sample_view.py — 샘플 클립을 창에서 하나씩 보며 변화량(YDIF) 확인.

프레임-투-프레임(실시간)은 값이 미세해 읽기 어려워, **interval 초 간격(1초/5초)으로 비교**한다.
클립에서 interval 간격 표본만 뽑아(필요한 프레임만 디코드 → 부하↓) 연속 표본 간 YDIF 계산.
**영상 창과 데이터(측정값) 창을 분리**해 표시하고, 표본을 슬라이드쇼로 넘긴다.
"""
import argparse
import random
import time
from pathlib import Path

import cv2
import numpy as np

from variance import classify, summarize, to_gray_small, ydif

DEFAULT_SRCS = [r"D:\carved-08\Cut", r"D:\carved\Cut"]
RESIZE_W, RESIZE_H = 80, 45  # 320, 180   # 변화량 계산 + 영상 표시 resize (H=0이면 비율유지)
VIEW_SCALE = 3                       # 영상 창 표시 배율(리사이즈 이미지 확대; 1=원 resize 크기)
INTERVAL_SEC = 1.0                   # 기본 비교 간격(초). CLI --interval 로 1/5 등
DWELL_SEC = 0.8                      # 표본 한 장을 화면에 보여주는 시간(초)
IGNORE_RECT = (0.0, 0.0, 0.30, 0.10) # 계산 제외 영역 비율(x1,y1,x2,y2) — 좌상단 타임스탬프 숫자. None=없음
TH_MEAN = 2.0                        # STATIC 판정: meanYDIF(구간 평균 변화) < TH_MEAN 이고
TH_MAX = float("inf")                #             maxYDIF(구간 최대 변화) < TH_MAX 이면 정적
#   TH_MAX=inf → max 조건 비활성(오직 mean 으로 판정). 스파이크도 보려면 2~5 등 유한값으로.
WIN_VIDEO = "11 sample (video)"
WIN_DATA = "11 sample (YDIF data)"
F = cv2.FONT_HERSHEY_SIMPLEX


def _resize_view(frame):
    h, w = frame.shape[:2]
    if RESIZE_H and RESIZE_H > 0:
        return cv2.resize(frame, (RESIZE_W, RESIZE_H))
    if w > RESIZE_W:
        return cv2.resize(frame, (RESIZE_W, max(1, int(h * RESIZE_W / w))))
    return frame.copy()


def _sample_frames(path, interval):
    """interval 초 간격 표본 프레임(BGR)만 디코드해 반환."""
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    fps = fps if fps > 0 else 15.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    step = max(1, int(round(fps * interval)))
    frames, f = [], 0
    while f < total:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, fr = cap.read()
        if not ok or fr is None:
            break
        frames.append(fr)
        f += step
    cap.release()
    return frames


def _spark(vals, w, h, th, pos):
    img = np.full((h, w, 3), 30, np.uint8)
    if len(vals) >= 2:
        m = max(max(vals), th * 1.5, 1e-3)
        pts = [(int(i * (w - 1) / (len(vals) - 1)), int((h - 1) - min(v, m) / m * (h - 1)))
               for i, v in enumerate(vals)]
        cv2.polylines(img, [np.array(pts, np.int32)], False, (0, 255, 255), 1)
        y = int((h - 1) - min(th, m) / m * (h - 1))
        cv2.line(img, (0, y), (w - 1, y), (60, 60, 255), 1)
        if 0 <= pos < len(vals):
            x = int(pos * (w - 1) / (len(vals) - 1))
            cv2.line(img, (x, 0), (x, h - 1), (255, 255, 255), 1)
    return img


def _data_panel(idx, total, name, j, nframes, interval, cur, mean_y, max_y, state, thr, vals):
    W, H = 470, 300
    p = np.full((H, W, 3), 25, np.uint8)
    col = (0, 200, 0) if state == "STATIC" else (0, 165, 255)
    cv2.putText(p, f"[{idx + 1}/{total}] {name[:34]}", (12, 26), F, 0.5, (200, 200, 200), 1)
    cv2.putText(p, f"sample {j + 1}/{nframes}  compare @{interval:.0f}s", (12, 50), F, 0.5, (200, 200, 200), 1)
    cv2.putText(p, f"YDIF now: {cur:6.2f}", (12, 92), F, 0.8, (0, 255, 255), 2)
    cv2.putText(p, f"clip mean: {mean_y:6.2f}    max: {max_y:6.2f}", (12, 124), F, 0.6, (0, 255, 255), 1)
    cv2.putText(p, f"[{state}]", (12, 168), F, 0.9, col, 2)
    cv2.putText(p, f"TH  mean < {thr['mean']:.2f}    max < {thr['max']:.2f}", (12, 200), F, 0.55, col, 1)
    cv2.putText(p, "[ ] mean-/+   , . max-/+   space:pause   n/p:clip   q:quit",
                (12, 226), F, 0.42, (180, 180, 180), 1)
    sp = _spark(vals, W - 24, 46, thr["mean"], max(0, j - 1))
    p[H - 56:H - 10, 12:12 + sp.shape[1]] = sp
    return p


def show_clip(path, idx, total, thr, interval):
    frames = _sample_frames(path, interval)
    if not frames:
        return "next"
    grays = [to_gray_small(f, RESIZE_W, RESIZE_H) for f in frames]
    vals = [ydif(grays[k - 1], grays[k], IGNORE_RECT) for k in range(1, len(grays))]
    mean_y, max_y = summarize(vals)
    j, paused, last = 0, False, 0.0
    while True:
        state = classify(mean_y, max_y, thr["mean"], thr["max"])
        cur = vals[j - 1] if j > 0 else 0.0
        small = _resize_view(frames[j])                      # ── 영상 창 ──
        video = (small if VIEW_SCALE == 1 else
                 cv2.resize(small, None, fx=VIEW_SCALE, fy=VIEW_SCALE, interpolation=cv2.INTER_NEAREST))
        if IGNORE_RECT:                                      # 무시영역 표시(초록)
            vh, vw = video.shape[:2]
            cv2.rectangle(video, (int(IGNORE_RECT[0] * vw), int(IGNORE_RECT[1] * vh)),
                          (int(IGNORE_RECT[2] * vw), int(IGNORE_RECT[3] * vh)), (0, 255, 0), 1)
        cv2.imshow(WIN_VIDEO, video)
        cv2.imshow(WIN_DATA, _data_panel(idx, total, path.name, j, len(frames),  # ── 데이터 창 ──
                                         interval, cur, mean_y, max_y, state, thr, vals))
        k = cv2.waitKey(30) & 0xFF
        if (cv2.getWindowProperty(WIN_VIDEO, cv2.WND_PROP_VISIBLE) < 1
                or cv2.getWindowProperty(WIN_DATA, cv2.WND_PROP_VISIBLE) < 1
                or k in (ord("q"), 27)):
            return "quit"
        if k == ord("n"):
            return "next"
        if k == ord("p"):
            return "prev"
        if k == ord(" "):
            paused = not paused
        elif k == ord("["):
            thr["mean"] = max(0.0, round(thr["mean"] - 0.02, 3))
        elif k == ord("]"):
            thr["mean"] = round(thr["mean"] + 0.02, 3)
        elif k == ord(","):
            thr["max"] = max(0.0, round(thr["max"] - 0.5, 2))
        elif k == ord("."):
            thr["max"] = round(thr["max"] + 0.5, 2)
        now = time.time()
        if not paused and now - last > DWELL_SEC:
            j = (j + 1) % len(frames)
            last = now


def main() -> int:
    ap = argparse.ArgumentParser(description="샘플 클립을 창에서 하나씩 보며 변화량 확인")
    ap.add_argument("--src", default=next((s for s in DEFAULT_SRCS if Path(s).is_dir()), DEFAULT_SRCS[0]))
    ap.add_argument("--n", type=int, default=100, help="볼 클립 수 (0=전체)")
    ap.add_argument("--interval", type=float, default=INTERVAL_SEC, help="비교 간격(초): 1, 5 등")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--th-mean", type=float, default=TH_MEAN)
    ap.add_argument("--th-max", type=float, default=TH_MAX)
    args = ap.parse_args()

    clips = sorted(Path(args.src).glob("*.mp4"))
    if not clips:
        print(f"[에러] 클립 없음: {args.src}")
        return 1
    random.seed(args.seed)
    random.shuffle(clips)
    if args.n > 0:
        clips = clips[: args.n]
    print(f"{len(clips)}개 클립 · {args.interval:.0f}초 간격 비교 — n/p 이동, q 종료")

    cv2.namedWindow(WIN_VIDEO, cv2.WINDOW_AUTOSIZE)
    cv2.namedWindow(WIN_DATA, cv2.WINDOW_AUTOSIZE)
    try:
        cv2.moveWindow(WIN_VIDEO, 60, 90)
        cv2.moveWindow(WIN_DATA, 60 + RESIZE_W * VIEW_SCALE + 40, 90)
    except cv2.error:
        pass

    thr = {"mean": args.th_mean, "max": args.th_max}
    i = 0
    while 0 <= i < len(clips):
        act = show_clip(clips[i], i, len(clips), thr, args.interval)
        if act == "quit":
            break
        i = max(0, min(i + (1 if act == "next" else -1 if act == "prev" else 0), len(clips) - 1))
    cv2.destroyAllWindows()
    print(f"최종 임계: mean<{thr['mean']} & max<{thr['max']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
