#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\9_detection_inference\live
#   ..\..\.venv\Scripts\python.exe live.py               # go2rtc 실시간 창 (640x640)
#   키: q/ESC 종료 · s 스크린샷(out\)
# ─────────────────────────────────────────────────────────────
r"""9_detection_inference — 학습 2클래스 모델로 go2rtc 실시간 추론 (자체 완결).

스트림 프레임을 **640x640 으로 resize** 해서 추론·표시한다. 모델은 이 폴더 models\ 에 번들
(best / 60). 아래 [설정] 만 고치면 됨. detector.py·stream_source.py 는 이 폴더 자체 구현.
"""
import os
import time
from pathlib import Path

import cv2

import stream_source
from detector import load_detector, draw

_HERE = os.path.dirname(os.path.abspath(__file__))

# ══════════════════════ 설정 ══════════════════════
STREAM_URL  = r"http://172.30.1.42:1984/stream.html?src=camera1"   # go2rtc
MODEL       = os.path.join(_HERE, "models", "60", "model.pth")     # 또는 models\best\model.pth
IMGSZ       = 640                     # 스트림을 IMGSZ x IMGSZ 로 resize 수신
CONF        = 0.8                     # 채택 임계 (threshold 0.8)
DET_CLASSES = None                    # 2클래스 전체 (baby·baby_face)
WIN_SCALE   = 1.0                     # 창 표시 배율(640 그대로면 1.0; 크게 보려면 1.5 등)
# ═══════════════════════════════════════════════════


def main():
    print(f"model  = {MODEL}\nstream = {STREAM_URL}\nresize = {IMGSZ}x{IMGSZ}  conf >= {CONF}")
    det = load_detector(MODEL)
    cap, how = stream_source.open_source(STREAM_URL)
    if cap is None:
        print(f"[에러] 스트림 열기 실패: {STREAM_URL} ({how})\n  확인: http://172.30.1.42:1984/streams")
        return 1
    print("소스:", how)
    out = Path(_HERE) / "out"
    out.mkdir(exist_ok=True)
    n = miss = 0
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            miss += 1
            if miss > 90:                       # 초반 mid-GOP·일시 끊김 견딤
                print("[정보] 스트림 종료/끊김")
                break
            continue
        miss = 0
        frame = cv2.resize(frame, (IMGSZ, IMGSZ))          # 640x640 수신
        t1 = time.time()
        r = det.predict(frame, conf=CONF, classes=DET_CLASSES, verbose=False)[0]
        ms = (time.time() - t1) * 1000
        n_det = draw(frame, r)
        n += 1
        fps = n / max(time.time() - t0, 1e-3)
        cv2.putText(frame, f"det:{n_det} {ms:.0f}ms fps:{fps:.1f} conf>={CONF}  [s]ave [q]uit",
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        show = frame if WIN_SCALE == 1.0 else cv2.resize(frame, None, fx=WIN_SCALE, fy=WIN_SCALE)
        cv2.imshow("9 detection live (640x640)", show)
        k = cv2.waitKey(1) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == ord("s"):
            cv2.imwrite(str(out / f"shot_{int(time.time())}.jpg"), frame)
            print("저장:", out.resolve())
    cap.release()
    cv2.destroyAllWindows()
    print(f"처리 {n}프레임")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
