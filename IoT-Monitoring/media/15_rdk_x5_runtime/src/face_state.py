# -*- coding: utf-8 -*-
"""얼굴 상태 멀티라벨 모델 로드 + 예측 (14 자립용, 12_face_state/4_inference 발췌).

face_state.pth(state_dict) + face_state_info.json(network·input_size·attrs) 을 읽어
크롭 1장 → 각 속성 확률(sigmoid). 추론용이라 백본 weights=None(다운로드 없이 state_dict 로드).
"""
import json
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as tvm

from .face_thr import ATTR_THR, DEFAULT_THR, _thr_for  # noqa: F401  (torch 없는 공용 임계 — BPU 백엔드와 공유)


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


def load_face_state(pth_path):
    """(model, meta) 반환. `<pth>` state_dict + `<stem>_info.json`(network·input_size·attrs)."""
    p = Path(pth_path)
    meta = json.load(open(p.with_name(p.stem + "_info.json"), encoding="utf-8"))
    model = _build(meta["network"], len(meta["attrs"]))
    model.load_state_dict(torch.load(p, map_location="cpu"))
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
