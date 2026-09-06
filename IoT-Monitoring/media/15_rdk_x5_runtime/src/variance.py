# -*- coding: utf-8 -*-
"""프레임 변화량(YDIF) 계산 — 연속 프레임 루마(밝기) 절대차의 평균.

folder 1 의 ffmpeg signalstats YDIF 와 같은 개념을 cv2 로 계산한다(스케일 0~255).
- ydif(prev, cur) : 두 프레임의 |Y차| 평균 (한 프레임의 순간 변화량)
- 한 구간(클립/윈도우)의 meanYDIF = ydif 들의 평균, maxYDIF = ydif 들의 최댓값
정적(STATIC) 판정: meanYDIF < th_mean AND maxYDIF < th_max (folder 1 규칙과 동일).
"""
import cv2
import numpy as np


def to_gray_small(frame, width=320, height=0):
    """변화량 계산용 축소 후 그레이(Y). (resize 로 속도·해상도 무관성 확보)
    height>0 이면 (width,height) 로 고정 리사이즈, 아니면 가로 width 기준 비율 유지 축소."""
    h, w = frame.shape[:2]
    if height and height > 0:
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    elif w > width:
        frame = cv2.resize(frame, (width, max(1, int(h * width / w))), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def ydif(prev_gray, cur_gray, ignore=None):
    """연속 프레임 루마 절대차 평균(0~255). 값이 클수록 변화 큼.
    ignore=(x1,y1,x2,y2) 비율(0~1) 박스는 계산에서 제외 — 예: 타임스탬프 숫자 영역."""
    d = np.abs(cur_gray.astype(np.int16) - prev_gray.astype(np.int16))
    if ignore:
        h, w = d.shape
        x1, y1 = int(ignore[0] * w), int(ignore[1] * h)
        x2, y2 = int(ignore[2] * w), int(ignore[3] * h)
        if x2 > x1 and y2 > y1:
            d[y1:y2, x1:x2] = 0
            kept = d.size - (y2 - y1) * (x2 - x1)
            return float(d.sum() / max(1, kept))
    return float(d.mean())


def classify(mean_ydif, max_ydif, th_mean, th_max):
    return "STATIC" if (mean_ydif < th_mean and max_ydif < th_max) else "MOTION"


def clip_ydifs(path, *, interval=1.0, seconds=8.0, width=320, height=0, ignore=None, max_samples=300):
    """클립 앞 seconds 초에서 interval 초 간격 표본을 뽑아 연속 표본 간 ydif 리스트.
    interval<=0 이면 매 프레임(프레임-투-프레임). 실패 시 []."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    fps = fps if fps > 0 else 15.0
    step = max(1, int(round(fps * interval))) if interval > 0 else 1
    limit = int(fps * seconds)
    vals, prev, f = [], None, 0
    while f < limit and len(vals) < max_samples:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, fr = cap.read()
        if not ok or fr is None:
            break
        g = to_gray_small(fr, width, height)
        if prev is not None:
            vals.append(ydif(prev, g, ignore))
        prev = g
        f += step
    cap.release()
    return vals


def summarize(vals):
    """ydif 리스트 → (meanYDIF, maxYDIF). 비면 (0,0)."""
    if not vals:
        return 0.0, 0.0
    arr = np.asarray(vals, dtype=np.float64)
    return float(arr.mean()), float(arr.max())


def percentiles(values, ps=(5, 10, 25, 50, 75, 90, 95, 99)):
    """값 분포의 퍼센타일 dict. threshold 고를 때 사용."""
    if not values:
        return {p: 0.0 for p in ps}
    arr = np.asarray(values, dtype=np.float64)
    return {p: float(np.percentile(arr, p)) for p in ps}
