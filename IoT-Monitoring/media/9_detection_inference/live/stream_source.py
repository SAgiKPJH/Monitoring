# -*- coding: utf-8 -*-
"""프레임 소스 — go2rtc 실시간 우선, 스냅샷 폴백 (자체 완결 copy).

go2rtc 가 :1984(HTTP)만 열려 있어도 **fMP4 스트림(/api/stream.mp4)** 은 cv2(FFMPEG)로
실시간 수신된다. 안 되면 /api/frame.jpeg 스냅샷 폴링으로 폴백. BGR 반환.
"""
import re
import urllib.request

import cv2
import numpy as np


class SnapshotPoller:
    """go2rtc /api/frame.jpeg 폴링 — VideoCapture 와 같은 read()/release() 계약."""

    def __init__(self, url: str, timeout: float = 10.0):
        self.url, self.timeout = url, timeout

    def isOpened(self):  # noqa: N802
        ok, _ = self.read()
        return ok

    def read(self):
        try:
            with urllib.request.urlopen(self.url, timeout=self.timeout) as r:
                buf = np.frombuffer(r.read(), dtype=np.uint8)
            fr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            return fr is not None, fr
        except Exception:
            return False, None

    def release(self):
        pass


def _go2rtc(url):
    base = re.match(r"(https?://[^/]+)", url)
    src = re.search(r"[?&]src=([^&]+)", url)
    return (base.group(1) if base else None), (src.group(1) if src else None)


def open_source(url: str):
    """URL 에 맞는 프레임 소스 반환. (소스, 설명). 실패 시 (None, 이유)."""
    if url.lower().endswith((".mp4", ".avi", ".mkv", ".mov")) or url.startswith("rtsp"):
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        return (cap, "VideoCapture(FFMPEG)") if cap.isOpened() else (None, "열기 실패")

    base, src = _go2rtc(url)
    if base and src:
        mp4 = f"{base}/api/stream.mp4?src={src}"           # ① 실시간 fMP4
        cap = cv2.VideoCapture(mp4, cv2.CAP_FFMPEG)
        if cap.isOpened():
            for _ in range(60):                            # 키프레임 전 깨진 프레임 스킵
                ok, _f = cap.read()
                if ok and _f is not None:
                    return cap, f"go2rtc fMP4 실시간 ({mp4})"
            cap.release()
        snap = f"{base}/api/frame.jpeg?src={src}"          # ② 스냅샷 폴링 폴백
        p = SnapshotPoller(snap)
        if p.isOpened():
            return p, f"go2rtc 스냅샷 폴링 ({snap})"

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    return (cap, "VideoCapture(FFMPEG)") if cap.isOpened() else (None, "열기 실패")
