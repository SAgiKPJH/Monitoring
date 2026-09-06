# -*- coding: utf-8 -*-
"""pose 활동량(행동량) 계산 — 표본 프레임 간 keypoint 이동량.

11_variance_measure 의 YDIF(픽셀 밝기차) 대신, 학습 pose 모델의 keypoint 좌표가
프레임 사이 얼마나 움직였는지로 '아기가 얼마나 행동하는지'를 수치화한다.
- move(prev, cur): 공통으로 보이는 keypoint 평균 이동거리 / 이미지 대각선 (0~1, 클수록 활발)
- 구간의 mean/max 로 STATIC(정적)/ACTIVE(활발) 판정 (folder 11 규칙과 동일 구조).
monitoring.py 의 pose_moving 과 같은 지표(정규화 변위)를 view/분석용으로 정리한 것.
"""
import cv2
import numpy as np

KP_CONF = 0.3      # 이 conf 이상 keypoint 만 이동량 계산에 사용(둘 다 보일 때만 비교)


def _np(t):
    """torch 텐서(.cpu()) 든 numpy 든 → numpy (torch·BPU 백엔드 공용)."""
    return t.cpu().numpy() if hasattr(t, "cpu") else np.asarray(t)


def kps_of(pose_result):
    """pose 결과 → (xy[N,2] float, vis[N] bool). 감지 없으면 (None, None)."""
    kp = pose_result.keypoints
    if kp is None or len(kp) == 0:
        return None, None
    xy = _np(kp.xy[0]).astype(np.float64)
    cf = _np(kp.conf[0]) if kp.conf is not None else np.ones(len(xy))
    return xy, (cf >= KP_CONF)


def move(prev, prev_vis, cur, cur_vis, diag):
    """공통 visible keypoint 의 평균 이동거리 / 대각선(0~1). 공통 없으면 0."""
    if prev is None or cur is None or prev.shape != cur.shape or diag <= 0:
        return 0.0
    m = prev_vis & cur_vis
    if not m.any():
        return 0.0
    return float(np.linalg.norm(cur[m] - prev[m], axis=1).mean() / diag)


def classify(mean_m, max_m, th_mean, th_max):
    return "STATIC" if (mean_m < th_mean and max_m < th_max) else "ACTIVE"


def summarize(vals):
    """이동량 리스트 → (mean, max). 비면 (0,0)."""
    if not vals:
        return 0.0, 0.0
    a = np.asarray(vals, np.float64)
    return float(a.mean()), float(a.max())


def sample_frames(path, interval, max_samples=150):
    """interval 초 간격 표본 프레임(BGR)만 디코드해 반환(필요한 프레임만 → 부하↓)."""
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    fps = fps if fps > 0 else 15.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    step = max(1, int(round(fps * interval)))
    frames, f = [], 0
    while f < total and len(frames) < max_samples:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, fr = cap.read()
        if not ok or fr is None:
            break
        frames.append(fr)
        f += step
    cap.release()
    return frames
