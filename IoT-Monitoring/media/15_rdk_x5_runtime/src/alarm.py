# -*- coding: utf-8 -*-
r"""알람 전송 — Slack Webhook + Grafana, 동일 알람 5분 쿨다운.

규칙 상세는 알람규칙.md 참고. env:
  SLACK_WEBHOOK                    : Slack Incoming Webhook (텍스트). 이미지는 첨부 불가.
  GRAFANA_URL + GRAFANA_TOKEN      : /api/annotations 텍스트 주석.
알람 스냅샷은 항상 alarms/alarm_<시각 id>.jpg 로 로컬 저장. 보내는 문구에는 **경로 없이 시각 id(예 20260906_143352)만** 붙인다.
"""
import os
import time
import urllib.request
from pathlib import Path

import cv2

SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", "")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "")
GRAFANA_TOKEN = os.environ.get("GRAFANA_TOKEN", "")
COOLDOWN = float(os.environ.get("ALARM_COOLDOWN", "300"))    # 동일 알람 최소 간격(초) = 5분
ALARM_DIR = Path(__file__).resolve().parents[1] / "alarms"   # 런타임 루트/alarms (src/ 가 아님)

_last = {}                                                    # key -> 마지막 전송 시각


def _post_json(url, data, headers, timeout=10):
    import json
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status < 300
    except Exception as e:
        print(f"[alarm] 전송 실패 {url}: {e}")
        return False


def send(text, key="", cooldown=None, tags=None, image=None):
    """알람 전송. 같은 key 는 cooldown(기본 5분) 안에는 재전송 안 함. image=프레임(BGR) 또는 경로.
    key 는 문자열 또는 목록(한 문구에 조건 여러 개) — 목록이면 하나라도 쿨다운 안이면 안 보냄(send_parts 가 미리 거른다)."""
    keys = [key] if isinstance(key, str) else list(key)
    cd = COOLDOWN if cooldown is None else cooldown
    now = time.time()
    if any(k and now - _last.get(k, 0) < cd for k in keys):
        return False
    for k in keys:
        _last[k or text] = now

    stamp = time.strftime("%Y%m%d_%H%M%S")                  # 알람 시각 id = alarm_<stamp>.jpg 의 <stamp>
    path = None                                              # 스냅샷 로컬 저장(항상)
    if image is not None:
        ALARM_DIR.mkdir(exist_ok=True)
        if isinstance(image, (str, Path)):
            path = Path(image)
        else:
            path = ALARM_DIR / f"alarm_{stamp}.jpg"
            cv2.imwrite(str(path), image)
    msg = f"{text}  [{stamp}]"                               # 보내는 문구: 경로 없이 시각 id 만
    print(f"[ALARM] {msg}" + (f"  → {path}" if path else ""), flush=True)   # 경로는 콘솔에만

    ok = True
    if SLACK_WEBHOOK:                                        # 웹훅=텍스트만
        ok &= _post_json(SLACK_WEBHOOK, {"text": f":baby: {msg}"}, {})
    if GRAFANA_URL and GRAFANA_TOKEN:
        ok &= _post_json(GRAFANA_URL.rstrip("/") + "/api/annotations",
                         {"text": msg, "tags": tags or ["baby-monitor"]},
                         {"Authorization": f"Bearer {GRAFANA_TOKEN}"})
    return ok


def send_parts(parts, cooldown=None, tags=None, image=None, sep=" + ", suffix=""):
    """조건 여러 개를 **한 문구**로 — parts=[(key, 문구), ...]. 쿨다운 안인 key 는 빼고 남은 것만 sep 으로 이어 1건 전송.
    예: [("face:eyes_open", "눈 뜸(깨어 있음)"), ("pose", "pose 변화(자주 움직임)")]
        → "눈 뜸(깨어 있음) + pose 변화(자주 움직임)<suffix>  [시각 id]" (두 key 모두 쿨다운 시작)."""
    cd = COOLDOWN if cooldown is None else cooldown
    now = time.time()
    live = [(k, t) for k, t in parts if not (k and now - _last.get(k, 0) < cd)]
    if not live:
        return False
    return send(sep.join(t for _, t in live) + suffix, key=[k for k, _ in live], cooldown=cd, tags=tags, image=image)
