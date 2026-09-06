# -*- coding: utf-8 -*-
"""얼굴 상태 멀티라벨 모델 로드 + 예측 (3단계 run_training_multilabel 산출물 사용).

output_ml_<net>\best.pth(state_dict) + meta.json(network·input_size·attrs·BGR·0.5정규화) 을 읽어
크롭 1장 → 각 속성 확률(sigmoid). 추론용이라 백본 weights=None(다운로드 없이 state_dict 로드).
"""
import json
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as tvm

# 속성별 임계(확률 >= 값이면 on) — 모든 얼굴상태 추론이 공유(monitor 포함)
ATTR_THR = {"eyes_open": 0.9, "mouth_covered": 0.7, "mouth_open": 0.7, "frown": 0.8}
DEFAULT_THR = 0.5


def _thr_for(a, thr):
    if isinstance(thr, (int, float)):
        return float(thr)
    return (thr or ATTR_THR).get(a, DEFAULT_THR)


def _build(network, n_out):
    if network == "mobilenet_v2":
        m = tvm.mobilenet_v2(weights=None)
        m.classifier[1] = nn.Linear(m.last_channel, n_out)
    elif network == "resnet18":
        m = tvm.resnet18(weights=None)
        m.fc = nn.Linear(m.fc.in_features, n_out)
    else:
        raise ValueError(f"지원 network 아님: {network}")
    return m


def load_face_state(model_dir):
    """(model, meta) 반환. meta = {network, input_size, attrs, ...}."""
    d = Path(model_dir)
    meta = json.load(open(d / "meta.json", encoding="utf-8"))
    model = _build(meta["network"], len(meta["attrs"]))
    model.load_state_dict(torch.load(d / "best.pth", map_location="cpu"))
    model.eval()
    return model, meta


def predict(model, meta, crop_bgr, thr=None):
    """크롭(BGR) → {attr: (prob, on)}. 학습과 동일 전처리(리사이즈·0.5정규화·BGR).
    thr: None=속성별 ATTR_THR · 스칼라=전 속성 동일 · dict=속성별."""
    size = int(meta["input_size"])
    img = cv2.resize(crop_bgr, (size, size)).astype(np.float32) / 255.0
    img = (img - 0.5) / 0.5
    x = torch.from_numpy(np.ascontiguousarray(img.transpose(2, 0, 1)))[None]
    with torch.no_grad():
        probs = torch.sigmoid(model(x))[0].tolist()
    return {a: (float(p), float(p) >= _thr_for(a, thr)) for a, p in zip(meta["attrs"], probs)}


def overlay(frame, box, states, y0=0):
    """감지 박스(초록) + 속성 상태 텍스트. box=(x1,y1,x2,y2)·states=predict 결과."""
    x1, y1, x2, y2 = (int(v) for v in box)
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    yy = max(y1, 16) + y0
    for a, (p, on) in states.items():
        yy += 18
        col = (0, 230, 0) if on else (120, 120, 120)
        cv2.putText(frame, f"{a}:{p:.2f}", (x1, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1)
