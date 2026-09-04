#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""timelapse — 아기 타임랩스: 시간당 1장, baby 감지 시 **원본** 저장.

Docker 컨테이너로 상시 구동(대부분 sleep, 자원 거의 안 씀). 적응형 스케줄:
  · 저장 성공(아기 감지) → **1시간** 대기 후 다음 시도
  · 미검출(아기 없음)   → **10분** 뒤 재시도 (잡을 때까지 반복)
  → "시간마다 1장 저장하되, 그 시점에 아기가 없으면 10분마다 다시 시도"
매 시도: go2rtc 최신 프레임 1장 → 2클래스 모델 baby 감지(letterbox 640) →
있으면 **박스 없는 원본 프레임**을 JPEG 저장. 설정은 환경변수(기본값 아래).
저장은 로컬(OUT_DIR) 또는 **SCP 로 원격 IP:경로 push**(SCP_TARGET 설정 시) — 볼륨 없이 원격 전송.
detector.py·stream_source.py 는 이 폴더 자체 구현.
"""
import datetime
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import cv2

import stream_source
from detector import load_detector


def _load_env(path):
    """같은 폴더 .env 를 os.environ 에 로드(있으면). 실제 환경변수가 우선(setdefault).
    로컬 실행용 — 도커는 compose 의 env_file 로 주입되므로 여기선 no-op."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env(Path(__file__).with_name(".env"))

STREAM_URL = os.environ.get("STREAM_URL", "")
MODEL      = os.environ.get("MODEL", "models/60/model.pth")
OUT_DIR    = os.environ.get("OUT_DIR", "captures")           # 상대경로 스테이징(기본 ./captures)
SUCCESS_INTERVAL = int(os.environ.get("SUCCESS_INTERVAL_SEC", "3600"))  # 저장 성공 후 대기 — 1시간
RETRY_INTERVAL   = int(os.environ.get("RETRY_INTERVAL_SEC", "600"))     # 아기 없을 때 재시도 — 10분
CONF       = float(os.environ.get("CONF", "0.8"))            # baby 채택 임계
BABY_CLASS = int(os.environ.get("BABY_CLASS", "0"))          # 0=baby (1=baby_face)
IMGSZ      = int(os.environ.get("IMGSZ", "640"))             # 추론 크기(ultralytics letterbox)
WARMUP     = int(os.environ.get("WARMUP_FRAMES", "15"))      # 최신 프레임 확보용 초기 스킵
RUN_ONCE   = os.environ.get("RUN_ONCE", "0") == "1"          # 1이면 1회만(테스트/외부 cron)

# ── SCP 전송(선택) — 저장 파일을 원격 IP:경로 로 push (volume 대신) ──
SCP_TARGET = os.environ.get("SCP_TARGET", "")                # 예: user@192.168.0.10:/home/user/baby/  (빈값=미사용)
SCP_KEY    = os.environ.get("SCP_KEY", "/keys/id_rsa")       # 컨테이너에 마운트한 SSH 개인키
SCP_PORT   = os.environ.get("SCP_PORT", "22")
SCP_LEGACY = os.environ.get("SCP_LEGACY", "1") == "1"        # -O: 레거시 SCP 프로토콜(SFTP subsystem 없는 서버용)
KEEP_LOCAL = os.environ.get("KEEP_LOCAL", "0") == "1"        # SCP 후 로컬 유지? 기본 0=전송하면 삭제
FORCE_SAVE = os.environ.get("FORCE_SAVE", "0") == "1"        # 테스트: 감지 없어도 저장/전송 (RUN_ONCE 와 함께)
_KEY = None                                                  # 600 권한 사용키(main 에서 준비)


def _log(msg):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def grab_frame():
    """스트림에서 최신 프레임 1장(BGR). 실패 시 None."""
    cap, how = stream_source.open_source(STREAM_URL)
    if cap is None:
        return None, how
    frame = None
    for _ in range(WARMUP):
        ok, f = cap.read()
        if ok and f is not None:
            frame = f
    cap.release()
    return frame, how


def _prep_key():
    """읽기전용 마운트 키를 600 권한 임시본으로 복사(없으면 None → 기본키/에이전트 시도)."""
    src = Path(SCP_KEY)
    if not src.exists():
        return None
    dst = Path(tempfile.gettempdir()) / "scp_key"
    shutil.copy(src, dst)
    os.chmod(dst, 0o600)
    return str(dst)


def send_scp(path):
    """저장 파일을 SCP_TARGET 으로 전송. 성공 시 True."""
    cmd = ["scp"]
    if SCP_LEGACY:
        cmd.append("-O")                                 # SFTP subsystem 없는 서버 대응
    cmd += ["-P", str(SCP_PORT), "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]
    if _KEY:
        cmd += ["-i", _KEY]
    cmd += [str(path), SCP_TARGET]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        _log(f"SCP 실행 실패: {exc}")
        return False
    if r.returncode == 0:
        return True
    err = (r.stderr or "").strip()
    _log(f"SCP 실패(rc={r.returncode}): {err[-400:] if err else '(no stderr)'}")
    return False


def flush_pending():
    """OUT_DIR 에 남은(이전 전송 실패) 파일을 다시 전송하고 성공 시 삭제.
    SCP 전송·삭제 모드(KEEP_LOCAL=0)에서만 동작 — captures\\ 를 '아직 못 보낸' 대기함으로 취급.
    재시작/매 주기 시작 때 호출되어 밀린 파일을 비운다."""
    if not (SCP_TARGET and not KEEP_LOCAL):
        return
    files = sorted(Path(OUT_DIR).glob("*.jpg"))
    if not files:
        return
    _log(f"미전송 {len(files)}개 재전송 시도")
    sent = 0
    for p in files:
        if send_scp(p):
            p.unlink(missing_ok=True)
            sent += 1
        else:
            break                                        # 서버 불가 시 이번엔 중단(다음 주기 재시도)
    _log(f"재전송 {sent}/{len(files)}")


def capture_once(det):
    """1회 시도. 아기 감지→원본 저장하면 True, 아니면 False."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    frame, how = grab_frame()
    if frame is None:
        _log(f"스트림 열기 실패({how}) — 미검출로 처리")
        return False
    r = det.predict(frame, conf=CONF, classes=[BABY_CLASS], imgsz=IMGSZ, verbose=False)[0]
    n = 0 if r.boxes is None else len(r.boxes)
    if n == 0 and not FORCE_SAVE:
        _log("baby 없음 — 저장 안 함")
        return False
    top = float(r.boxes.conf.max()) if n else 0.0
    tag = "baby" if n else "test"
    path = Path(OUT_DIR) / f"{tag}_{ts}.jpg"
    cv2.imwrite(str(path), frame)                            # 원본(풀해상도, 박스 없음)
    _log((f"baby 감지 {n} (최고 {top:.2f})" if n else "FORCE_SAVE(테스트)") + f" → 저장 {path}")
    if SCP_TARGET:
        if send_scp(path):
            _log(f"SCP 전송 완료 → {SCP_TARGET}")
            if not KEEP_LOCAL:
                Path(path).unlink(missing_ok=True)
        else:
            _log("SCP 실패 — 로컬 파일 유지")
    return n > 0


def main():
    global _KEY
    Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    _KEY = _prep_key() if SCP_TARGET else None
    dest = f"SCP → {SCP_TARGET}" if SCP_TARGET else f"로컬 {OUT_DIR}"
    _log(f"start · model={MODEL} stream={STREAM_URL} conf>={CONF} 저장={dest}\n"
         f"      스케줄: 저장 성공 후 {SUCCESS_INTERVAL // 60}분 · 미검출 시 {RETRY_INTERVAL // 60}분 뒤 재시도")
    det = load_detector(MODEL)
    if RUN_ONCE:
        flush_pending()                                  # 재시작 시 밀린 것 먼저 전송
        capture_once(det)
        return 0
    while True:
        flush_pending()                                  # 시작·매 주기마다 이전 실패분 재전송
        saved = capture_once(det)
        wait = SUCCESS_INTERVAL if saved else RETRY_INTERVAL
        _log(f"다음 시도까지 {wait // 60}분 대기 ({'저장 후 1시간' if saved else '미검출 재시도'})")
        time.sleep(wait)


if __name__ == "__main__":
    raise SystemExit(main())
