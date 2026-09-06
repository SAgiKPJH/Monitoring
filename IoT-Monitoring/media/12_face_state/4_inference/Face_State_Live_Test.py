#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\4_inference
#   ..\..\.venv\Scripts\python.exe Face_State_Live_Test.py         # go2rtc 실시간 얼굴상태
#   키: s 스크린샷(out\) · q/ESC 종료
# ─────────────────────────────────────────────────────────────
r"""go2rtc 실시간 스트림 → baby_face 감지(8 모델) → 얼굴 크롭 → 상태 멀티라벨 오버레이.

스트림/감지기는 4_detection_pretrained\src 재사용, 얼굴상태는 3단계 output_ml_<net>.
"""
import os
import sys
import time
from pathlib import Path

import cv2

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1] / "4_detection_pretrained"))   # media/4_detection_pretrained

from face_state import load_face_state, overlay, predict  # noqa: E402
from src.inference import load_detector                    # noqa: E402
from src.stream_source import open_source                  # noqa: E402

# ══════════════════════ 설정 ══════════════════════
STREAM_URL = r"http://172.30.1.42:1984/stream.html?src=camera1"
DET_MODEL = str(_HERE.parents[1] / "8_detection_2class_train" / "output" / "60" / "model.pth")
FACE_CLASS = 1                       # 8 모델: 0=baby, 1=baby_face
FACE_MODEL_DIR = _HERE.parent / "3_classification_training" / "output_ml_mobilenet_v2"
DET_CONF = 0.8                       # baby/baby_face 채택 (face_state.ATTR_THR 로 속성 판정)
SCALE = 0.5                          # 화면 표시 축소
# ═══════════════════════════════════════════════════


def main() -> int:
    if not (FACE_MODEL_DIR / "best.pth").exists():
        print(f"[에러] 얼굴상태 모델 없음: {FACE_MODEL_DIR}\\best.pth")
        return 1
    if not Path(DET_MODEL).exists():
        print(f"[에러] 감지 모델 없음: {DET_MODEL}")
        return 1
    det = load_detector(DET_MODEL)
    model, meta = load_face_state(FACE_MODEL_DIR)
    print(f"det={Path(DET_MODEL).parent.name}  state={FACE_MODEL_DIR.name}  attrs={meta['attrs']}")
    cap, how = open_source(STREAM_URL)
    if cap is None:
        print(f"[에러] 스트림 열기 실패: {STREAM_URL} ({how})")
        return 1
    print("소스:", how)
    out = _HERE / "out"
    out.mkdir(exist_ok=True)
    miss = 0
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            miss += 1
            if miss > 90:
                print("[정보] 스트림 종료/끊김")
                break
            continue
        miss = 0
        r = det.predict(frame, conf=DET_CONF, classes=[FACE_CLASS], imgsz=640, verbose=False)[0]
        for b in (r.boxes or []):
            box = [float(v) for v in b.xyxy[0]]
            x1, y1, x2, y2 = (int(v) for v in box)
            crop = frame[max(0, y1):y2, max(0, x1):x2]
            if crop.size == 0:
                continue
            overlay(frame, box, predict(model, meta, crop))
        vis = cv2.resize(frame, None, fx=SCALE, fy=SCALE) if SCALE != 1 else frame
        cv2.putText(vis, "s:shot  q:quit", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.imshow("12 face-state live", vis)
        k = cv2.waitKey(1) & 0xFF
        if cv2.getWindowProperty("12 face-state live", cv2.WND_PROP_VISIBLE) < 1 or k in (ord("q"), 27):
            break
        if k == ord("s"):
            cv2.imwrite(str(out / f"shot_{int(time.time())}.jpg"), vis)
            print("저장:", out.resolve())
    cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
