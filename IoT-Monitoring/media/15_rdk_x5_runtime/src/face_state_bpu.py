# -*- coding: utf-8 -*-
"""RDK X5 BPU 백엔드 — models/face_state.bin(mobilenet_v2 멀티라벨) pyeasy_dnn 추론.

face_state.py(torch) 와 같은 인터페이스: load_face_state(bin) → (model, meta) · predict(model, meta, crop, thr)
전처리: BGR uint8 리사이즈 후 vision_bpu._BpuModel 이 .bin 입력 속성(NHWC/NCHW/NV12)에 맞춰 투입.
        정규화 (x-127.5)/127.5 는 .bin 컴파일 시 내장(14_export_BPU/face_state.yaml).
출력: logits → sigmoid(numpy). attrs 는 face_state_info.json(bin 옆). torch 는 import 하지 않는다.
"""
import json
from pathlib import Path

import cv2
import numpy as np

from .face_thr import ATTR_THR, _thr_for  # noqa: F401  (torch 없는 공용 임계)
from .vision_bpu import _BpuModel          # 입력 형식 자동 판별 + 출력 역양자화 공유


def load_face_state(bin_path):
    """(model, meta) — meta = face_state_info.json (network·input_size·attrs)."""
    p = Path(bin_path)
    meta = json.load(open(p.with_name(p.stem + "_info.json"), encoding="utf-8"))
    return _BpuModel(p), meta


def predict(model, meta, crop_bgr, thr=None):
    """크롭(BGR) → {attr: (prob, on)}. thr: None=ATTR_THR · 스칼라 · dict."""
    img = cv2.resize(crop_bgr, (model.w, model.h))                      # BGR uint8 그대로
    out = model.forward(img)[0]                                         # float32 (4D 로 와도 reshape(-1))
    logits = out.reshape(-1)[: len(meta["attrs"])]
    probs = 1.0 / (1.0 + np.exp(-logits))
    return {a: (float(p), float(p) >= _thr_for(a, thr)) for a, p in zip(meta["attrs"], probs)}
