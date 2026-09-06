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
    """알람 전송. 같은 key 는 cooldown(기본 5분) 안에는 재전송 안 함. image=프레임(BGR) 또는 경로."""
    cd = COOLDOWN if cooldown is None else cooldown
    now = time.time()
    if key and now - _last.get(key, 0) < cd:
        return False
    _last[key or text] = now

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
