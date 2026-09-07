#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행:
#   cd D:\Code\Monitoring\IoT-Monitoring\media\15_rdk_x5_runtime
#   ..\.venv\Scripts\python.exe monitoring.py            # dev(현재 PC, torch/ultralytics 모델)
#   (RDK X5 배포 시 감지/분류 백엔드를 BPU 런타임으로 교체 — README 참고)
# ─────────────────────────────────────────────────────────────
r"""RDK X5 실시간 모니터링 오케스트레이션 — 순차 상태머신(각 단계는 끝날 때까지 대기).

  1) 움직임 감지(1초 1회, YDIF)                → 변화 있으면 다음 단계 트리거
  2) baby 존재 감지(기본 5분 1회 · 1의 움직임 시 즉시)
  3) 30초 관찰 창 1개: 얼굴 상태(baby_face 크롭 → 눈뜸/입가림/인상) + pose 변화량(자주 움직임)을
     같은 프레임으로 같이 관찰 → 관찰된 조건을 **한 문구**로 알람 (예: 눈 뜸(깨어 있음) + pose 변화(자주 움직임) — 30초 관찰)
관찰 = 창 안 폴(2초)의 OBS_RATIO(절반) 이상에서 조건 성립. "내내 지속"이 아니라 폴 몇 번 놓쳐도 취소되지 않는다.
쿨다운은 조건별(key face:<attr> / pose) — 쿨다운 안인 조건만 문구에서 빠지고 나머지는 나간다.
알람은 Slack + Grafana(alarm.py). 모델은 8(감지)·12(얼굴상태)·13(pose) 재사용.
"""
import math
import os
import sys
import time
from pathlib import Path

import cv2


def _load_env(path):
    """같은 폴더 .env 를 os.environ 에 로드(실제 env 우선). alarm import 전에 호출.

    값 뒤 인라인 주석(공백 + '#')은 제거하고, 따옴표로 감싼 값은 따옴표 안만 취한다
    (예: ALARM_COOLDOWN=300   # 5분  → '300').
    """
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip()
        if v[:1] in ('"', "'") and v.count(v[0]) >= 2:           # 따옴표 값: 닫는 따옴표까지
            v = v[1:v.index(v[0], 1)]
        else:                                                    # 인라인 주석 제거 (공백 + #)
            for sep in (" #", "\t#"):
                v = v.split(sep, 1)[0]
        os.environ.setdefault(k.strip(), v.strip())


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))                            # 폴더 독립 — 15_rdk_x5_runtime 안 모듈만 사용

_load_env(HERE / ".env")
BACKEND = os.environ.get("BACKEND", "").lower()          # torch(PC 개발) | bpu(RDK X5 NPU, models/*.bin) | 빈값=자동
if not BACKEND:                                          # 자동: 보드(hobot_dnn 있음) → bpu, 아니면 torch
    try:
        import hobot_dnn  # noqa: F401
        BACKEND = "bpu"
    except ImportError:
        BACKEND = "torch"
_BPU = BACKEND == "bpu"

from src import alarm  # noqa: E402  (.env 로드 후 임포트 — 알람 채널 env 반영. 부속 코드는 src/)

from src.variance import to_gray_small, ydif             # noqa: E402
from src.pose_motion import kps_of, move                 # noqa: E402
from src.stream_source import open_source                # noqa: E402
from src.face_thr import ATTR_THR                        # noqa: E402  (torch 없는 공용 임계)

load_detector = load_pose = load_face_state = predict = None   # load_backend() 가 바인딩


def load_backend():
    """BACKEND 에 맞는 모델 로더/예측 함수를 지연 import 해 모듈 전역에 바인딩.

    모듈 import 자체는 가볍게 유지 → 1_slack_send_test 처럼 모델이 필요 없는 도구는 torch/hobot 없이도 동작.
    잘못된 백엔드(예: 보드에서 BACKEND=torch)면 traceback 대신 원인·조치를 안내하고 종료.
    """
    global load_detector, load_pose, load_face_state, predict
    if load_detector is not None:
        return
    try:
        if _BPU:                                         # 보드: hobot_dnn(pyeasy_dnn) — torch 불필요
            from src.vision_bpu import load_detector as _ld, load_pose as _lp
            from src.face_state_bpu import load_face_state as _lf, predict as _pr
        else:                                            # PC: torch/ultralytics
            from src.vision import load_detector as _ld, load_pose as _lp
            from src.face_state import load_face_state as _lf, predict as _pr
    except ImportError as e:
        hint = ("보드에서는 .env 에 BACKEND=bpu 로 두거나 비워두세요(자동 판별). 예: BACKEND=bpu python3 ..."
                if not _BPU else "BACKEND=bpu 는 hobot_dnn 이 있는 RDK 보드에서만 동작합니다(PC 는 torch)")
        raise SystemExit(f"[에러] BACKEND={BACKEND} 백엔드 import 실패: {e}\n  → {hint}")
    load_detector, load_pose, load_face_state, predict = _ld, _lp, _lf, _pr

# ══════════════════════ 설정 ══════════════════════
MODELS = HERE / "models"                                 # 모델은 이 폴더 안(독립 실행)
STREAM_URL = os.environ.get("STREAM_URL", "http://172.30.1.42:1984/stream.html?src=camera1")
DET_MODEL = str(MODELS / ("detection.bin" if _BPU else "detection.pth"))    # + detection_info.json
FACE_MODEL = str(MODELS / ("face_state.bin" if _BPU else "face_state.pth"))  # + face_state_info.json
POSE_MODEL = str(MODELS / ("pose.bin" if _BPU else "pose.pt"))               # .bin 은 14_export_BPU 로 생성
BABY_CLASS, FACE_CLASS = 0, 1

MOTION_INTERVAL = 1.0        # 움직임 감지 주기(초)
MOTION_THR = 0.5            # YDIF 임계(folder 11 로 캘리브레이션)
BABY_INTERVAL = 300.0       # baby 감지 기본 주기(초, 5분) — 움직임 시 즉시도 함
BABY_CONF = 0.8            # baby 감지 conf
FACE_CONF = 0.8            # baby_face 감지 conf
OBS_SEC = 30.0              # 관찰 창(초): 이 시간 동안 POLL_SEC 마다 확인
POLL_SEC = 2.0             # 관찰 폴링 간격(초) → 창당 15회
OBS_RATIO = 0.5            # 창 안 폴의 이 비율 이상에서 관찰되면 알람(0.5 = 절반). 폴 몇 번 놓쳐도 취소 안 됨
# 얼굴 속성 임계는 src/face_thr.ATTR_THR 공유(import). 아래는 그중 알람 트리거 속성 — OBS_SEC 관찰 창에서 관찰되면
# **속성별로** 알람(key face:<attr>, 쿨다운도 속성별) → 눈 뜸 알람이 입 가려짐 알람을 묻지 않는다.
FACE_ALARM_ATTRS = ["mouth_covered", "frown", "eyes_open"]
ATTR_LABEL = {"eyes_open": "눈 뜸(깨어 있음)", "mouth_covered": "입 가려짐(이불 등)",
              "frown": "인상(울기 직전)", "mouth_open": "입 벌림",
              "pose": "pose 변화(자주 움직임)"}                              # 알람 문구(조건별)
POSE_MOVE_THR = 0.022      # 정규화 keypoint 이동량(초과 시 '움직임') = 13/5 뷰어 TH_MEAN 2.2%
# ═══════════════════════════════════════════════════


def grab(cap, warm=3):
    """최신 프레임 1장. 실시간 소스(LatestFrameReader, age() 있음)는 항상 최신이라 1번만 읽고,
    파일은 warm 장을 읽어 마지막 것을 쓴다."""
    frame = None
    if hasattr(cap, "age"):
        warm = 1
    for _ in range(warm):
        ok, f = cap.read()
        if ok and f is not None:
            frame = f
    return frame


def has_baby(det, frame):
    """baby(conf>=BABY_CONF) 존재 여부 + baby_face(conf>=FACE_CONF) 박스 목록."""
    r = det.predict(frame, conf=min(BABY_CONF, FACE_CONF), verbose=False)[0]
    faces, baby = [], False
    for b in (r.boxes or []):
        cls, cf = int(b.cls), float(b.conf)
        if cls == FACE_CLASS and cf >= FACE_CONF:
            faces.append([float(v) for v in b.xyxy[0]])
        elif cls == BABY_CLASS and cf >= BABY_CONF:
            baby = True
    return baby, faces


def face_on_attrs(fmodel, fmeta, frame, faces):
    """baby_face 들에서 임계(ATTR_THR)를 넘긴 **알람 속성 집합** — 어느 얼굴에서든 on 이면 포함."""
    on = set()
    for x1, y1, x2, y2 in faces:
        crop = frame[max(0, int(y1)):int(y2), max(0, int(x1)):int(x2)]
        if crop.size == 0:
            continue
        st = predict(fmodel, fmeta, crop)               # {attr: (prob, _)}
        on |= {a for a in FACE_ALARM_ATTRS if st.get(a, (0.0,))[0] >= ATTR_THR.get(a, 0.5)}
    return on


def face_alarm_state(fmodel, fmeta, frame, faces):
    """baby_face 중 하나라도 알람 속성이 on 이면 True (2_run_test 등 도구 호환)."""
    return bool(face_on_attrs(fmodel, fmeta, frame, faces))


def observe_attrs(get_on, attrs, seconds, poll, ratio, label):
    """seconds 관찰 창을 poll 간격으로 n 회 확인해, 폴의 ratio 이상에서 on 이었던 속성만 반환(=관찰됨).
    창은 한 번만 돌고 속성별 결과를 나눠 준다. 폴 몇 번 놓쳐도 취소되지 않고,
    남은 폴을 전부 맞혀도 어떤 속성도 ratio 에 못 미치면 조기 종료."""
    n = max(1, round(seconds / poll))
    need = max(1, math.ceil(n * ratio))
    hits = {a: 0 for a in attrs}
    for i in range(n):
        for a in set(get_on()) & hits.keys():
            hits[a] += 1
        left = n - i - 1
        if all(h + left < need for h in hits.values()):
            return set()
        if left:
            time.sleep(poll)
    seen = {a for a, h in hits.items() if h >= need}
    if seen:
        print(f"  [{label}] {seconds:.0f}초 관찰: " + ", ".join(f"{a} {hits[a]}/{n}" for a in sorted(seen)))
    return seen


def pose_moving(pose, frame, memo):
    """이전 대비 keypoint 이동량(visible 공통)이 임계 초과면 True. memo['kv'] 에 이전 (xy,vis) 보관.

    13/5_pose_activity_view 와 동일 지표(pose_motion.move) — 뷰어로 캘리브레이션한 TH 가 그대로 적용.
    """
    r = pose.predict(frame, conf=0.2, verbose=False)[0]
    xy, vis = kps_of(r)
    if xy is None:
        return False
    h, w = frame.shape[:2]
    diag = (w ** 2 + h ** 2) ** 0.5
    prev = memo.get("kv")
    memo["kv"] = (xy, vis)
    if prev is None:
        return False
    return move(prev[0], prev[1], xy, vis, diag) > POSE_MOVE_THR


def main() -> int:
    load_backend()                                           # BACKEND 에 맞는 로더 바인딩(잘못되면 안내 후 종료)
    if not Path(DET_MODEL).exists() or not Path(FACE_MODEL).exists():
        print(f"[에러] models\\ 에 모델이 없습니다: {MODELS}  (BACKEND={BACKEND})\n"
              f"  필요: {Path(DET_MODEL).name}·{Path(FACE_MODEL).name}(각 _info.json)·{Path(POSE_MODEL).name}"
              + ("  ← 14_export_BPU 로 .bin 생성" if _BPU else ""))
        return 1
    print(f"BACKEND={BACKEND} · models={MODELS}")
    det = load_detector(DET_MODEL)
    fmodel, fmeta = load_face_state(FACE_MODEL)
    pose = load_pose(POSE_MODEL) if Path(POSE_MODEL).exists() else None
    cap, how = open_source(STREAM_URL)
    if cap is None:
        print(f"[에러] 스트림 열기 실패: {STREAM_URL} ({how})")
        return 1
    print(f"소스: {how} · 움직임 {MOTION_INTERVAL}s · baby {BABY_INTERVAL/60:.0f}분 · 관찰 {OBS_SEC:.0f}s×{OBS_RATIO:.0%}")
    if pose is None:
        print("  (pose 모델 없음 — 4단계 pose 알람 건너뜀. 13 학습 후 활성)")

    prev_gray = None
    last_baby = 0.0
    memo = {}
    while True:
        # ── 1) 움직임 감지 (1초 주기) ──
        frame = grab(cap)
        if frame is None:
            time.sleep(MOTION_INTERVAL)
            continue
        g = to_gray_small(frame, 320)
        motion = prev_gray is not None and ydif(prev_gray, g) > MOTION_THR
        prev_gray = g
        now = time.time()
        if not (motion or now - last_baby >= BABY_INTERVAL):
            time.sleep(MOTION_INTERVAL)
            continue

        # ── 2) baby 존재 감지 ──
        last_baby = now
        baby, faces = has_baby(det, frame)
        if not baby and not faces:
            continue
        print(f"[{time.strftime('%H:%M:%S')}] baby 감지 (motion={motion}) · face {len(faces)}")

        # ── 3) 30초 관찰 창 1개: 얼굴 속성 + pose 움직임을 같은 프레임으로 같이 관찰 → 관찰된 조건을 한 문구로 알람 ──
        def _on_now():                                       # 폴마다 프레임 1장 → 얼굴 재감지·속성, pose 이동량
            f = grab(cap)
            if f is None:
                return set()
            on = face_on_attrs(fmodel, fmeta, f, has_baby(det, f)[1])
            if pose is not None and pose_moving(pose, f, memo):
                on.add("pose")
            return on
        conds = FACE_ALARM_ATTRS + (["pose"] if pose is not None else [])
        seen = observe_attrs(_on_now, conds, OBS_SEC, POLL_SEC, OBS_RATIO, "관찰")
        if seen:                                             # 조건별 key 로 쿨다운 → 남은 조건만 " + " 로 이어 1건
            alarm.send_parts([("pose" if c == "pose" else f"face:{c}", ATTR_LABEL.get(c, c)) for c in conds if c in seen],
                             suffix=f" — {OBS_SEC:.0f}초 관찰", tags=["baby-monitor"] + [c for c in conds if c in seen],
                             image=grab(cap))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n종료")
