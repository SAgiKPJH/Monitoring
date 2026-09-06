# -*- coding: utf-8 -*-
"""얼굴 속성 임계 — torch 없이 import 가능 (torch·BPU 백엔드, monitor 가 공유)."""

ATTR_THR = {"eyes_open": 0.9, "mouth_covered": 0.7, "mouth_open": 0.7, "frown": 0.8}
DEFAULT_THR = 0.5


def _thr_for(a, thr):
    """thr: None=속성별 ATTR_THR · 스칼라=전 속성 동일 · dict=속성별."""
    if isinstance(thr, (int, float)):
        return float(thr)
    return (thr or ATTR_THR).get(a, DEFAULT_THR)
