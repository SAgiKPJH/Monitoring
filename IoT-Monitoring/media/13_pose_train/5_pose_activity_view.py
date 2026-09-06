#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\13_pose_train
#   ..\.venv\Scripts\python.exe 5_pose_activity_view.py --n 100 --interval 1   # 1초마다 비교
#   ..\.venv\Scripts\python.exe 5_pose_activity_view.py --interval 5           # 5초마다 비교
#   창: [video] 영상+골격 · [activity data] 활동량 수치  (두 창 분리)
#   키: n/p 다음/이전 클립 · r 랜덤 클립 · space 일시정지 · [ ] mean-/+ · , . max-/+ · q 종료
# ─────────────────────────────────────────────────────────────
r"""13_pose_train/5 — 학습 pose 모델로 '아기가 얼마나 행동하는지'를 수치화(11_variance_measure 대응).

YDIF(픽셀 밝기차) 대신 **keypoint 이동량**(pose_motion)으로 활동량을 잰다.
interval 초 간격 표본만 뽑아 pose 추론 → 연속 표본 간 이동량 계산(부하↓).
**영상+골격 창**과 **활동량 데이터 창**을 분리 표시하고 표본을 슬라이드쇼로 넘긴다.
"""
import argparse
import os
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "4_detection_pretrained"))

from pose_motion import classify, kps_of, move, sample_frames, summarize  # noqa: E402
from src.inference import draw, load_pose                                 # noqa: E402

DEFAULT_SRC = r"D:\carved-08\Cut"
POSE_MODEL = os.path.join(_HERE, "output", "train_colab_442", "weights", "best.pt")
CONF = 0.20                          # pose 감지 conf
INTERVAL_SEC = 1.0                   # 기본 비교 간격(초). CLI --interval 로 1/5 등
DWELL_SEC = 0.8                      # 표본 한 장을 화면에 보여주는 시간(초)
VIEW_MAX_W, VIEW_MAX_H = 640, 480    # 영상 창 최대 표시 크기
MOVE_SCALE = 100.0                   # 이동량(대각선 비율)→ 퍼센트(%) 표시
TH_MEAN = 2.2                        # STATIC 판정: mean 이동%<TH_MEAN 이고 max<TH_MAX 이면 정적(=monitor 0.022)
TH_MAX = float("inf")                #   TH_MAX=inf → max 조건 비활성. 스파이크도 보려면 유한값.
WIN_VIDEO = "13 pose activity (video)"
WIN_DATA = "13 pose activity (data)"
F = cv2.FONT_HERSHEY_SIMPLEX


def _fit(frame):
    h, w = frame.shape[:2]
    s = min(1.0, VIEW_MAX_W / w, VIEW_MAX_H / h)
    return cv2.resize(frame, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1.0 else frame


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


def _data_panel(idx, total, name, j, nframes, interval, cur, mean_m, max_m, state, thr, vals):
    W, H = 470, 300
    p = np.full((H, W, 3), 25, np.uint8)
    col = (0, 200, 0) if state == "STATIC" else (0, 165, 255)
    cv2.putText(p, f"[{idx + 1}/{total}] {name[:34]}", (12, 26), F, 0.5, (200, 200, 200), 1)
    cv2.putText(p, f"sample {j + 1}/{nframes}  compare @{interval:.0f}s", (12, 50), F, 0.5, (200, 200, 200), 1)
    cv2.putText(p, f"move now: {cur:6.2f}%", (12, 92), F, 0.8, (0, 255, 255), 2)
    cv2.putText(p, f"clip mean: {mean_m:6.2f}%   max: {max_m:6.2f}%", (12, 124), F, 0.6, (0, 255, 255), 1)
    cv2.putText(p, f"[{state}]", (12, 168), F, 0.9, col, 2)
    cv2.putText(p, f"TH  mean < {thr['mean']:.2f}   max < {thr['max']:.2f}", (12, 200), F, 0.55, col, 1)
    cv2.putText(p, "[ ] mean-/+  , . max-/+  space:pause  n/p:clip  r:rand  q:quit",
                (12, 226), F, 0.42, (180, 180, 180), 1)
    sp = _spark(vals, W - 24, 46, thr["mean"], max(0, j - 1))
    p[H - 56:H - 10, 12:12 + sp.shape[1]] = sp
    return p


def show_clip(path, idx, total, thr, interval, pose):
    frames = sample_frames(path, interval)
    if not frames:
        return "next"
    results = [pose.predict(f, conf=CONF, verbose=False)[0] for f in frames]   # 표본마다 pose 추론
    kvs = [kps_of(r) for r in results]
    h, w = frames[0].shape[:2]
    diag = (w ** 2 + h ** 2) ** 0.5
    vals = [move(kvs[k - 1][0], kvs[k - 1][1], kvs[k][0], kvs[k][1], diag) * MOVE_SCALE
            for k in range(1, len(frames))]
    mean_m, max_m = summarize(vals)
    j, paused, last = 0, False, 0.0
    while True:
        state = classify(mean_m, max_m, thr["mean"], thr["max"])
        cur = vals[j - 1] if j > 0 else 0.0
        video = frames[j].copy()                              # ── 영상+골격 창 ──
        draw(video, None, results[j])                         # det 없이 pose 골격만
        cv2.imshow(WIN_VIDEO, _fit(video))
        cv2.imshow(WIN_DATA, _data_panel(idx, total, path.name, j, len(frames),  # ── 데이터 창 ──
                                         interval, cur, mean_m, max_m, state, thr, vals))
        k = cv2.waitKey(30) & 0xFF
        if (cv2.getWindowProperty(WIN_VIDEO, cv2.WND_PROP_VISIBLE) < 1
                or cv2.getWindowProperty(WIN_DATA, cv2.WND_PROP_VISIBLE) < 1
                or k in (ord("q"), 27)):
            return "quit"
        if k == ord("n"):
            return "next"
        if k == ord("p"):
            return "prev"
        if k == ord("r"):
            return "random"
        if k == ord(" "):
            paused = not paused
        elif k == ord("["):
            thr["mean"] = max(0.0, round(thr["mean"] - 0.2, 2))
        elif k == ord("]"):
            thr["mean"] = round(thr["mean"] + 0.2, 2)
        elif k == ord(","):
            thr["max"] = max(0.0, round(thr["max"] - 0.5, 2))
        elif k == ord("."):
            thr["max"] = round(thr["max"] + 0.5, 2)
        now = time.time()
        if not paused and now - last > DWELL_SEC and len(frames) > 1:
            j = (j + 1) % len(frames)
            last = now


def main() -> int:
    ap = argparse.ArgumentParser(description="pose 활동량(행동량) 뷰어 — 클립별 keypoint 이동량")
    ap.add_argument("--src", default=DEFAULT_SRC, help="클립 폴더 또는 mp4")
    ap.add_argument("--model", default=POSE_MODEL, help="pose 모델(.pt)")
    ap.add_argument("--n", type=int, default=100, help="볼 클립 수 (0=전체)")
    ap.add_argument("--interval", type=float, default=INTERVAL_SEC, help="비교 간격(초): 1, 5 등")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--th-mean", type=float, default=TH_MEAN)
    ap.add_argument("--th-max", type=float, default=TH_MAX)
    args = ap.parse_args()

    if not Path(args.model).exists():
        print(f"[에러] pose 모델 없음: {args.model}\n먼저 3_run_training.py 로 학습하세요.")
        return 1
    clips = sorted(Path(args.src).glob("*.mp4")) if Path(args.src).is_dir() else (
        [Path(args.src)] if str(args.src).lower().endswith(".mp4") else [])
    if not clips:
        print(f"[에러] 클립 없음: {args.src}")
        return 1
    random.seed(args.seed)
    random.shuffle(clips)
    if args.n > 0:
        clips = clips[: args.n]
    pose = load_pose(args.model)
    print(f"{len(clips)}개 클립 · {args.interval:.0f}초 간격 활동량 — n/p 이동, q 종료")

    cv2.namedWindow(WIN_VIDEO, cv2.WINDOW_AUTOSIZE)
    cv2.namedWindow(WIN_DATA, cv2.WINDOW_AUTOSIZE)
    try:
        cv2.moveWindow(WIN_VIDEO, 60, 90)
        cv2.moveWindow(WIN_DATA, 60 + VIEW_MAX_W + 40, 90)
    except cv2.error:
        pass

    thr = {"mean": args.th_mean, "max": args.th_max}
    i = 0
    while 0 <= i < len(clips):
        act = show_clip(clips[i], i, len(clips), thr, args.interval, pose)
        if act == "quit":
            break
        if act == "random" and len(clips) > 1:               # r: 현재와 다른 랜덤 클립
            j = i
            while j == i:
                j = random.randrange(len(clips))
            i = j
        else:
            i = max(0, min(i + (1 if act == "next" else -1 if act == "prev" else 0), len(clips) - 1))
    cv2.destroyAllWindows()
    print(f"최종 임계: mean<{thr['mean']} & max<{thr['max']}  (move%, monitor POSE_MOVE_THR≈{thr['mean'] / 100:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
