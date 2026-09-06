"""프레임 소스 — go2rtc 실시간 우선, 스냅샷 폴백. 실시간 소스는 **최신 프레임만** 유지(지연 누적 방지).

go2rtc 가 :1984(HTTP)만 열려 있어도 **fMP4 스트림(/api/stream.mp4)** 은 cv2(FFMPEG)로 실시간 수신된다
(1920x1080 H.264). 안 되면 /api/frame.jpeg 스냅샷 폴링으로 폴백. BGR 반환.

지연 누적 문제: 실시간 스트림을 추론 속도(카메라 fps 보다 느림)로 read() 하면 안 읽은 프레임이 FFmpeg/TCP
버퍼에 쌓여 read() 가 점점 옛 프레임을 돌려준다. LatestFrameReader 가 백그라운드 스레드로 grab()(디코드만)을
쉬지 않고 호출해 항상 최신 위치를 유지하고, 소비자가 read() 할 때만 retrieve()(BGR 변환)한다 → 항상 '지금'
프레임, CPU 부하는 최소. rx_fps(수신 fps)가 카메라 fps 보다 낮으면 디코드가 못 따라가는 것 → 더 가벼운 소스
(go2rtc MJPEG 엔드포인트 /api/stream.mjpeg?src=… 또는 저해상도 서브스트림)를 STREAM_URL 에 직접 지정.
파일(mp4)은 순차 재생이 목적이라 감싸지 않는다.
"""
import re
import threading
import time
import urllib.request

import cv2
import numpy as np


class SnapshotPoller:
    """go2rtc /api/frame.jpeg 폴링 — VideoCapture 와 같은 read()/release() 계약. 매번 새 스냅샷(지연 없음)."""

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


class LatestFrameReader:
    """실시간 소스용 최신 프레임 리더 — VideoCapture 계약(isOpened/read/release) + age()/rx_fps.

    스레드: cap.grab() 반복(디코드만, 최신 위치 유지). read(): 마지막 grab 프레임을 retrieve()(BGR 변환).
    stall_sec 동안 프레임이 안 오면 끊긴 것으로 보고 reopen_sec 후 재접속을 반복한다.
    """

    def __init__(self, url, api=cv2.CAP_FFMPEG, stall_sec=10.0, reopen_sec=2.0):
        self.url, self.api, self.stall_sec, self.reopen_sec = url, api, stall_sec, reopen_sec
        self._cap, self._has, self._t = None, False, 0.0
        self._lock, self._stop = threading.Lock(), threading.Event()
        self._n, self._t_fps, self.rx_fps = 0, time.time(), 0.0      # 수신(grab) fps
        self._open()
        self._th = threading.Thread(target=self._loop, name="LatestFrameReader", daemon=True)
        self._th.start()

    def _open(self):
        cap = cv2.VideoCapture(self.url, self.api)
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)              # 지원 백엔드에선 내부 버퍼도 최소화
        except cv2.error:
            pass
        if not cap.isOpened():
            cap.release()
            return False
        with self._lock:
            self._cap, self._has = cap, False
        return True

    def _loop(self):
        last_ok = time.time()
        while not self._stop.is_set():
            ok = False
            if self._cap is not None:
                with self._lock:
                    ok = self._cap.grab()                    # 디코드만 → 최신 프레임 위치로
            if ok:
                now = time.time()
                if not self._has:                            # 첫 프레임(접속 대기 시간 제외)부터 fps 측정
                    self._n, self._t_fps = 0, now
                self._t, self._has, last_ok = now, True, now
                self._n += 1
                if now - self._t_fps >= 1.0:
                    self.rx_fps, self._n, self._t_fps = self._n / (now - self._t_fps), 0, now
                time.sleep(0.001)                            # 소비자 스레드에 잠깐 양보
                continue
            if time.time() - last_ok > self.stall_sec:       # 무응답/끊김 → 재접속
                with self._lock:
                    if self._cap is not None:
                        self._cap.release()
                    self._cap, self._has = None, False
                time.sleep(self.reopen_sec)
                if self._open():
                    print(f"[stream] 재접속: {self.url}", flush=True)
                last_ok = time.time()
            else:
                time.sleep(0.01)

    def isOpened(self):  # noqa: N802
        return self._cap is not None or self._has

    def read(self):
        """마지막으로 grab 된(=최신) 프레임을 BGR 로. (ok, frame)"""
        if not self._has or self._cap is None:
            return False, None
        with self._lock:
            if self._cap is None:
                return False, None
            ok, f = self._cap.retrieve()
        return (bool(ok) and f is not None), f

    def age(self):
        """최신 프레임을 받은 뒤 지난 시간(초). None=아직 프레임 없음. 정상이면 수십 ms 이내."""
        return (time.time() - self._t) if self._has else None

    def release(self):
        self._stop.set()
        self._th.join(timeout=2.0)
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None


def _go2rtc(url):
    base = re.match(r"(https?://[^/]+)", url)
    src = re.search(r"[?&]src=([^&]+)", url)
    return (base.group(1) if base else None), (src.group(1) if src else None)


def _live(url, label, wait=10.0):
    """실시간 소스를 LatestFrameReader 로 열고 첫 프레임을 wait 초까지 기다린다. (소스, 설명) / (None, 이유)."""
    rd = LatestFrameReader(url)
    t0 = time.time()
    while time.time() - t0 < wait:
        ok, _ = rd.read()
        if ok:
            return rd, f"{label} 최신프레임 ({url})"
        if not rd.isOpened():
            break
        time.sleep(0.1)
    rd.release()
    return None, "열기 실패"


def open_source(url: str):
    """URL 에 맞는 프레임 소스 반환. (소스, 설명). 실패 시 (None, 이유).
    파일은 순차 VideoCapture, 실시간(RTSP/go2rtc/HTTP)은 최신 프레임 리더.
    go2rtc 엔드포인트를 직접 주면(/api/stream.mjpeg 등) 그대로 연다."""
    if url.lower().endswith((".mp4", ".avi", ".mkv", ".mov")):
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        return (cap, "VideoCapture(FFMPEG, 파일)") if cap.isOpened() else (None, "열기 실패")
    if url.startswith("rtsp"):
        return _live(url, "RTSP")
    if "/api/" in url:                                       # 지정 엔드포인트(mjpeg/mp4 등) 그대로
        return _live(url, "go2rtc 지정 엔드포인트")

    base, src = _go2rtc(url)
    if base and src:
        mp4 = f"{base}/api/stream.mp4?src={src}"           # ① 실시간 fMP4
        got = _live(mp4, "go2rtc fMP4 실시간")
        if got[0] is not None:
            return got
        snap = f"{base}/api/frame.jpeg?src={src}"          # ② 스냅샷 폴링 폴백
        p = SnapshotPoller(snap)
        if p.isOpened():
            return p, f"go2rtc 스냅샷 폴링 ({snap})"

    return _live(url, "VideoCapture(FFMPEG)")
