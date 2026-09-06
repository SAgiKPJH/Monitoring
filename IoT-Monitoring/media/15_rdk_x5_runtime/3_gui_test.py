#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 3단계 — GUI 시각 검증. 두 가지 방식:
#  (a) Windows 창:   ..\.venv\Scripts\python.exe 3_gui_test.py [--src <mp4|url>] [--win 1280x720]
#                    키: space 일시정지 · q/ESC 종료
#  (b) 보드(RDK X5, 헤드리스): python3 3_gui_test.py        (창 불가 → 자동 --serve 8080, 또는 --serve 포트 지정)
#                    → Windows 브라우저에서  http://<보드IP>:8080/   (Ctrl+C 종료)
#   시각화 conf: --vis-conf 0.25 (운용 임계 미만 후보도 회색으로 표시)   다음: monitoring.py(실제 운용)
# ─────────────────────────────────────────────────────────────
r"""소스를 돌리며 monitoring.py 와 같은 단계(감지·얼굴상태·pose·움직임)를 한 화면에 **전부** 오버레이한다.

- detection : VIS_CONF 이상 **모든 후보 박스** + 라벨(`baby 0.63`). 운용 임계(BABY_CONF/FACE_CONF) 이상은 색(초록/하늘)
              굵게, 미만은 회색 + `<임계` 표시 → "왜 감지가 안 되는지"(conf 부족) 를 눈으로 확인.
- classification : 모든 baby_face 후보에 분류 실행 → 속성별 **확률 막대**(임계 눈금, 초록=on · 빨강=on&알람속성 · 회색=off)
              + 우상단 **얼굴 크롭 썸네일**(분류기가 실제로 본 이미지).
- pose      : 골격(노랑) + keypoint 이동량 %(POSE_MOVE_THR 비교).
- HUD       : 현재 시각(카메라 타임스탬프와 비교=지연) · BACKEND · fps · 프레임 age · YDIF · baby/얼굴 수 · 위험 · pose.
--serve PORT: 창 대신 MJPEG(HTTP) 서빙(표준 라이브러리만) → 헤드리스 보드에서 실행하고 브라우저로 확인.
알람은 보내지 않는다. torch/BPU 결과 객체 모두 처리(pose_motion._np).
"""
import argparse
import http.server
import socketserver
import sys
import threading
import time
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import monitoring as M  # noqa: E402
from src.pose_motion import _np, kps_of, move  # noqa: E402

SKELETON = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12),
            (11, 13), (13, 15), (12, 14), (14, 16), (0, 5), (0, 6)]
WIN = "15 gui test"
KP_THR = 0.3
JPEG_Q = 80
DEFAULT_SERVE_PORT = 8080                  # 창을 못 띄우는 환경(보드)에서 자동 --serve 포트
VIS_CONF = 0.25                            # 시각화용 감지 conf(운용 임계는 monitoring BABY_CONF/FACE_CONF)
F = cv2.FONT_HERSHEY_SIMPLEX
C_BABY, C_FACE, C_WEAK, C_POSE = (0, 255, 0), (255, 220, 0), (140, 140, 140), (0, 255, 255)
C_ON, C_ALARM, C_OFF, C_TXT = (0, 230, 0), (0, 0, 255), (150, 150, 150), (235, 235, 235)


# ─────────────── MJPEG 서버 (--serve) ───────────────
class _Stream:
    latest, lock = None, threading.Lock()

    @classmethod
    def set(cls, jpg):
        with cls.lock:
            cls.latest = jpg

    @classmethod
    def get(cls):
        with cls.lock:
            return cls.latest


class _Handler(http.server.BaseHTTPRequestHandler):
    INDEX = (b"<html><head><title>15 gui test</title></head><body style='margin:0;background:#111'>"
             b"<img src='/stream.mjpg' style='max-width:100%;display:block;margin:auto'></body></html>")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(self.INDEX)
            return
        if self.path != "/stream.mjpg":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        last = None
        try:
            while True:
                buf = _Stream.get()
                if buf is not None and buf is not last:
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(buf)).encode() + b"\r\n\r\n" + buf + b"\r\n")
                    last = buf
                time.sleep(0.03)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, *_):
        pass


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_server(port):
    srv = _Server(("0.0.0.0", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ─────────────── 그리기 유틸 (해상도 비례 S = max(h,w)/1280) ───────────────
def _winsize(s):
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise argparse.ArgumentTypeError("창 크기 형식: 1280x720")


def _S(img):
    return max(img.shape[0], img.shape[1]) / 1280.0


def _label(img, text, org, color, S, bg=(0, 0, 0)):
    """배경 박스가 있는 텍스트(가독성). org=(x, 기준선 y). 줄 높이 반환."""
    fs, th = 0.55 * S, max(1, int(round(1.5 * S)))
    (tw, tht), base = cv2.getTextSize(text, F, fs, th)
    x, y = int(org[0]), int(org[1])
    cv2.rectangle(img, (x, y - tht - base - 2), (x + tw + 4, y + 2), bg, -1)
    cv2.putText(img, text, (x + 2, y - base // 2), F, fs, color, th, cv2.LINE_AA)
    return tht + base + 6


def _bar(img, x, y, w, h, frac, thr, color):
    """확률 막대 + 임계 눈금(흰 선)."""
    cv2.rectangle(img, (x, y), (x + w, y + h), (60, 60, 60), -1)
    cv2.rectangle(img, (x, y), (x + int(w * min(max(frac, 0.0), 1.0)), y + h), color, -1)
    tx = x + int(w * thr)
    cv2.line(img, (tx, y - 2), (tx, y + h + 2), (255, 255, 255), 1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (200, 200, 200), 1)


def _fit(frame, mw, mh):
    h, w = frame.shape[:2]
    s = min(1.0, mw / w, mh / h)
    return cv2.resize(frame, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1.0 else frame


# ─────────────── 단계별 시각화 ───────────────
def draw_det(img, r, S):
    """VIS_CONF 이상 모든 후보 박스 + 라벨. 운용 임계 이상=색·굵게, 미만=회색+'<임계'.
    반환: (faces_all[(x1,y1,x2,y2,conf)], faces_strong[(x1,y1,x2,y2)], baby_strong 수)."""
    names = getattr(r, "names", {}) or {}
    faces_all, faces_strong, baby_strong = [], [], 0
    for b in (r.boxes or []):
        cls, cf = int(b.cls), float(b.conf)
        x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
        is_face = cls == M.FACE_CLASS
        thr = M.FACE_CONF if is_face else M.BABY_CONF
        strong = cf >= thr
        col = (C_FACE if is_face else C_BABY) if strong else C_WEAK
        cv2.rectangle(img, (x1, y1), (x2, y2), col, max(1, int(round(2 * S))) if strong else 1)
        ly = y1 - 4 if y1 - 4 >= int(110 * S) else y1 + int(24 * S)   # 상단(타임스탬프/HUD 영역)이면 박스 안쪽에
        _label(img, f"{names.get(cls, cls)} {cf:.2f}" + ("" if strong else f" <{thr}"), (x1, ly), col, S)
        if is_face:
            faces_all.append((x1, y1, x2, y2, cf))
            if strong:
                faces_strong.append((x1, y1, x2, y2))
        elif strong:
            baby_strong += 1
    return faces_all, faces_strong, baby_strong


def draw_face_states(img, fmodel, fmeta, frame, faces_all, S):
    """모든 baby_face 후보에 분류 → 속성 확률 막대(임계 눈금) + 우상단 크롭 썸네일. 위험(운용 임계 얼굴 & 알람속성 on) 반환."""
    danger = False
    thumb_y, th_h = int(64 * S), int(150 * S)
    bw, bh, gap = int(150 * S), int(13 * S), int(21 * S)
    for i, (x1, y1, x2, y2, cf) in enumerate(faces_all):
        crop = frame[max(0, y1):y2, max(0, x1):x2]
        if crop.size == 0:
            continue
        st = M.predict(fmodel, fmeta, crop)
        strong = cf >= M.FACE_CONF
        px = x2 + 8 if x2 + 8 + bw + int(150 * S) < img.shape[1] else max(0, x1 - bw - int(160 * S))
        py = max(y1, int(24 * S))
        for a, (p, on) in st.items():                     # 속성 막대 + 값
            alarm_attr = a in M.FACE_ALARM_ATTRS
            col = C_ALARM if (on and alarm_attr) else C_ON if on else C_OFF
            _bar(img, px, py, bw, bh, p, M.ATTR_THR.get(a, 0.5), col)
            _label(img, f"{a} {p:.2f}{'*' if on else ''}", (px + bw + 4, py + bh), col, S * 0.9)
            py += gap
            danger |= strong and on and alarm_attr
        th_w = int(th_h * crop.shape[1] / max(1, crop.shape[0]))   # 썸네일(우상단 세로 스택)
        tx = img.shape[1] - th_w - 10
        if 0 < th_w < img.shape[1] // 3 and thumb_y + th_h < img.shape[0]:
            img[thumb_y:thumb_y + th_h, tx:tx + th_w] = cv2.resize(crop, (th_w, th_h))
            cv2.rectangle(img, (tx, thumb_y), (tx + th_w, thumb_y + th_h), C_FACE if strong else C_WEAK, 2)
            _label(img, f"face#{i + 1} {cf:.2f}", (tx, thumb_y - 3), C_FACE if strong else C_WEAK, S * 0.9)
            thumb_y += th_h + int(28 * S)
    return danger


def draw_pose(img, r, memo, diag, S):
    """골격 오버레이 + 이동량(%) 반환(이전 프레임 대비, 없으면 None)."""
    xy, vis = kps_of(r)
    if xy is None:
        return None
    cf = _np(r.keypoints.conf[0])
    lw = max(1, int(round(2 * S)))
    for a, b in SKELETON:
        if cf[a] > KP_THR and cf[b] > KP_THR:
            cv2.line(img, tuple(map(int, xy[a])), tuple(map(int, xy[b])), C_POSE, lw)
    for j in range(len(xy)):
        if cf[j] > KP_THR:
            cv2.circle(img, tuple(map(int, xy[j])), max(2, int(3 * S)), (0, 200, 255), -1)
    prev = memo.get("kv")
    memo["kv"] = (xy, vis)
    return move(prev[0], prev[1], xy, vis, diag) * 100 if prev else None


def _det_max(det, r, vis_conf):
    """임계 전 최대 점수 문자열(baby/face). BPU 는 last_max(전 앵커), torch 는 vis_conf 이상 후보 중 최대."""
    lm = getattr(det, "last_max", None)
    if lm is not None:
        return "/".join(f"{v:.2f}" for v in lm) + " (pre-thr)"
    best = {}
    for b in (r.boxes or []):
        c = int(b.cls)
        best[c] = max(best.get(c, 0.0), float(b.conf))
    return "/".join(f"{best.get(c, 0.0):.2f}" for c in (M.BABY_CLASS, M.FACE_CLASS)) + f" (>={vis_conf})"


def draw_legend(img, S):
    lines = [f"box: baby(green) / baby_face(cyan) = conf >= {M.BABY_CONF}/{M.FACE_CONF}   gray = weak (>= {VIS_CONF})",
             f"attr bar: green=on  red=on&alarm({'/'.join(M.FACE_ALARM_ATTRS)})  gray=off  | white tick = threshold",
             "pose: yellow skeleton (kpt conf>0.3)   HUD clock vs camera timestamp = lag"]
    y = img.shape[0] - int(8 * S)
    for t in reversed(lines):
        y -= _label(img, t, (10, y), C_TXT, S * 0.8)


def main() -> int:
    ap = argparse.ArgumentParser(description="GUI 시각 검증 (창 또는 --serve MJPEG) — 감지·분류·pose 전부 오버레이")
    ap.add_argument("--src", default=M.STREAM_URL, help="스트림 URL 또는 mp4")
    ap.add_argument("--win", type=_winsize, default=(1280, 720), help="표시 최대 크기 WxH")
    ap.add_argument("--drain", type=int, default=0, help="루프당 읽을 프레임 수(파일 소스용, 0=자동)")
    ap.add_argument("--serve", type=int, default=0,
                    help="헤드리스(보드): 이 포트로 MJPEG 서빙 → 브라우저 http://<보드IP>:포트/ (창 안 띄움)")
    ap.add_argument("--vis-conf", type=float, default=VIS_CONF, help="시각화용 감지 conf(후보 표시 하한)")
    args = ap.parse_args()
    M.load_backend()                                     # 백엔드 로더 바인딩(잘못된 BACKEND 면 안내 후 종료)
    for p in (M.DET_MODEL, M.FACE_MODEL):
        if not Path(p).exists():
            print(f"[에러] 모델 없음: {p}")
            return 1
    det = M.load_detector(M.DET_MODEL)
    fmodel, fmeta = M.load_face_state(M.FACE_MODEL)
    pose = M.load_pose(M.POSE_MODEL) if Path(M.POSE_MODEL).exists() else None
    cap, how = M.open_source(args.src)
    if cap is None:
        print(f"[에러] 소스 열기 실패: {args.src} ({how})")
        return 1
    is_file = str(args.src).lower().endswith((".mp4", ".avi", ".mkv"))
    drain = args.drain or (1 if is_file else 3)
    port = args.serve
    if not port:                                          # 창 시도 → 헤드리스(보드, opencv-headless)면 자동 --serve
        try:
            cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)
        except cv2.error:
            port = DEFAULT_SERVE_PORT
            print(f"[3_gui_test] 창을 못 띄우는 환경(헤드리스) → --serve {port} 로 자동 전환", flush=True)
    serve = port > 0
    if serve:
        start_server(port)
        print(f"BACKEND={M.BACKEND} · {how} · MJPEG 서빙 → 브라우저에서 http://<이 장치 IP>:{port}/  (Ctrl+C 종료)", flush=True)
    else:
        print(f"BACKEND={M.BACKEND} · {how} · drain={drain} · space:pause q:quit")

    prev_gray, memo, paused, shown, t_fps, n_fps, fps = None, {}, False, None, time.time(), 0, 0.0
    try:
        while True:
            if not paused:
                frame = M.grab(cap, warm=drain)
                if frame is None:
                    if is_file:                                   # 클립 끝 → 처음부터 반복(시각 테스트용)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        prev_gray, memo = None, {}
                        continue
                    print("프레임 없음 — 종료")
                    break
                img = frame.copy()
                h, w = frame.shape[:2]
                S = _S(img)
                g = M.to_gray_small(frame, 320)
                y = M.ydif(prev_gray, g) if prev_gray is not None else 0.0
                prev_gray = g
                r = det.predict(frame, conf=args.vis_conf, verbose=False)[0]   # 모든 후보(시각화용 낮은 conf)
                faces_all, faces_strong, n_baby = draw_det(img, r, S)
                danger = draw_face_states(img, fmodel, fmeta, frame, faces_all, S)
                mv = None
                if pose is not None:
                    pr = pose.predict(frame, conf=0.2, verbose=False)[0]
                    mv = draw_pose(img, pr, memo, (w ** 2 + h ** 2) ** 0.5, S)
                n_fps += 1
                if time.time() - t_fps >= 1.0:
                    fps, n_fps, t_fps = n_fps / (time.time() - t_fps), 0, time.time()
                age = cap.age() if hasattr(cap, "age") else None      # 최신 프레임 수신 후 경과(리더 소스)
                lag = (f"  age {age * 1000:.0f}ms rx {getattr(cap, 'rx_fps', 0.0):.1f}fps" if age is not None else "")
                pm = (f"pose move {mv:.2f}% (thr {M.POSE_MOVE_THR * 100:.1f}%) moving={mv > M.POSE_MOVE_THR * 100}"
                      if mv is not None else "pose move -")
                pmx = getattr(pose, "last_max", None) if pose is not None else None
                y0 = int(84 * S)                                  # 카메라 타임스탬프(좌상단) 아래에 HUD
                y0 += _label(img, f"{time.strftime('%H:%M:%S')}  BACKEND={M.BACKEND}  {fps:.1f} fps{lag}   "
                                  f"YDIF {y:.2f} (thr {M.MOTION_THR}) motion={y > M.MOTION_THR}", (10, y0), C_TXT, S)
                y0 += _label(img, f"baby {n_baby}  faces {len(faces_strong)}/{len(faces_all)} (strong/all)  "
                                  f"face-danger={danger}   {pm}", (10, y0), C_ALARM if danger else C_TXT, S)
                _label(img, f"det max baby/face {_det_max(det, r, args.vis_conf)}   "
                            f"pose max {pmx:.2f}" if pmx is not None else
                            f"det max baby/face {_det_max(det, r, args.vis_conf)}", (10, y0), C_TXT, S * 0.9)
                draw_legend(img, S)
                shown = _fit(img, *args.win)
            if serve:
                if shown is not None:
                    ok, buf = cv2.imencode(".jpg", shown, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_Q])
                    if ok:
                        _Stream.set(buf.tobytes())
                continue                                      # 페이스는 추론 시간이 결정
            if shown is not None:
                cv2.imshow(WIN, shown)
            k = cv2.waitKey(1 if not paused else 50) & 0xFF
            if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1 or k in (ord("q"), 27):
                break
            if k == ord(" "):
                paused = not paused
    except KeyboardInterrupt:
        print("\n종료")
    cap.release()
    if not serve:
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
