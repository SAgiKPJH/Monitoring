#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (PC, 이 폴더에서):  ..\.venv\Scripts\python.exe verify_onnx.py [--img <frame.jpg>]
#   PASS 가 나와야 export·보드용 후처리(15_rdk_x5_runtime/src/yolo_post)가 맞는 것. 그다음 calib_prep.py → convert.sh.
# ─────────────────────────────────────────────────────────────
r"""ONNX + 보드용 후처리를 PC 에서 검증 — onnxruntime.

① *_full.onnx(헤드 포함 단일 출력)를 ultralytics(자체 전/후처리)와 우리 파이프라인(letterbox → onnxruntime →
   yolo_post)으로 각각 돌려 박스/키포인트 일치 확인.
② detection.onnx / pose.onnx(분리 헤드, hb_mapper 입력)의 원시 맵을 yolo_post.raw_to_single 로 CPU 디코드한 텐서가
   *_full.onnx 의 단일 출력과 같은지 확인 → 보드의 분리 출력 경로가 맞다는 뜻(INT8 오차 제외).
③ face_state 는 torch vs onnx 확률 비교.
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
RDK = HERE.parent / "15_rdk_x5_runtime"
sys.path.insert(0, str(RDK))
from src.yolo_post import decode_detect, decode_pose, letterbox, raw_to_single  # noqa: E402

ONNX = HERE / "onnx"
CONF = 0.25


def _sess(name):
    import onnxruntime as ort
    return ort.InferenceSession(str(ONNX / name), providers=["CPUExecutionProvider"])


def _prep(bgr):
    """우리 전처리: letterbox → BGR→RGB → /255 → NCHW float32 (.bin 은 이 색변환·정규화를 내장)."""
    lb, r, pad = letterbox(bgr, 640)
    x = lb[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    return np.ascontiguousarray(x), r, pad


def _iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter + 1e-9)


def check_detect_full(img, nc):
    from ultralytics import YOLO
    ref = YOLO(str(ONNX / "detection_full.onnx")).predict(img, conf=CONF, imgsz=640, device="cpu", verbose=False)[0]
    ref_b = [(int(b.cls), float(b.conf), [float(v) for v in b.xyxy[0]]) for b in ref.boxes]
    x, r, pad = _prep(img)
    out = _sess("detection_full.onnx").run(None, {"images": x})[0]
    boxes, conf, cls = decode_detect(out, nc, CONF, r, pad, img.shape[:2])
    print(f"[detect full] ultralytics {len(ref_b)}개 vs ours {len(boxes)}개")
    ok = len(ref_b) == len(boxes)
    for c, s, bx in ref_b:
        j = max(range(len(boxes)), key=lambda k: _iou(bx, boxes[k]), default=None)
        if j is None:
            ok = False
            print("   매칭 없음:", c, s)
            continue
        iou = _iou(bx, boxes[j])
        print(f"   cls {c}=={cls[j]}  conf {s:.3f}~{conf[j]:.3f}  IoU {iou:.3f}")
        ok &= (c == cls[j]) and iou > 0.95 and abs(s - conf[j]) < 0.01
    return ok


def check_pose_full(img):
    from ultralytics import YOLO
    ref = YOLO(str(ONNX / "pose_full.onnx")).predict(img, conf=CONF, imgsz=640, device="cpu", verbose=False)[0]
    x, r, pad = _prep(img)
    out = _sess("pose_full.onnx").run(None, {"images": x})[0]
    boxes, conf, kxy, kcf = decode_pose(out, CONF, r, pad, img.shape[:2])
    n_ref = 0 if ref.keypoints is None else len(ref.keypoints)
    print(f"[pose full] ultralytics {n_ref}개 vs ours {len(boxes)}개")
    if n_ref == 0 or len(boxes) == 0:
        return n_ref == len(boxes)
    ref_xy = ref.keypoints.xy[0].cpu().numpy()
    m = ref.keypoints.conf[0].cpu().numpy() >= 0.5      # ultralytics 는 conf<0.5 keypoint xy 를 0 으로 둠
    d = float(np.abs(ref_xy[m] - kxy[0][m]).max()) if m.any() else 0.0
    print(f"   keypoint 최대 오차 {d:.2f}px (visible {int(m.sum())}개)  conf {float(ref.boxes.conf[0]):.3f}~{conf[0]:.3f}")
    return d < 1.0


def check_split(img, name, nc, nkpt):
    """분리 헤드 onnx 원시 맵 → raw_to_single ↔ *_full.onnx 단일 출력 비교."""
    x, _, _ = _prep(img)
    full = _sess(f"{name}_full.onnx").run(None, {"images": x})[0]
    s = _sess(f"{name}.onnx")
    outs = s.run(None, {"images": x})
    if len(outs) == 1:
        print(f"[{name} split] 단일 출력본(--no-split) — 분리 검증 생략")
        return True
    rec = raw_to_single(outs, nc, nkpt)
    d = np.abs(rec - full)
    C = 4 + nc + nkpt * 3
    dbox, dsc = float(d[0, :4].max()), float(d[0, 4:4 + nc].max())
    dk = float(d[0, 4 + nc:].max()) if nkpt else 0.0
    print(f"[{name} split] 출력 {len(outs)}개 {[tuple(o.shape) for o in outs]} → 복원 {rec.shape} vs full {full.shape}")
    print(f"   최대 오차: box {dbox:.4f}px · score {dsc:.6f}" + (f" · kpt {dk:.4f}" if nkpt else ""))
    ok = rec.shape == full.shape and full.shape[1] == C and dbox < 0.05 and dsc < 1e-4 and dk < 0.05
    return ok


def check_face(crop):
    from src.face_state import load_face_state, predict
    model, meta = load_face_state(str(RDK / "models" / "face_state.pth"))
    ref = predict(model, meta, crop)                              # torch
    s = int(meta["input_size"])
    x = ((cv2.resize(crop, (s, s)).astype(np.float32) / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[None]
    logits = _sess("face_state.onnx").run(None, {"images": np.ascontiguousarray(x)})[0][0]
    probs = 1 / (1 + np.exp(-logits))
    d = max(abs(ref[a][0] - float(p)) for a, p in zip(meta["attrs"], probs))
    print(f"[face] torch vs onnx 확률 최대 오차 {d:.5f}  " + " ".join(f"{a}:{ref[a][0]:.2f}" for a in meta["attrs"]))
    return d < 1e-3


def main() -> int:
    ap = argparse.ArgumentParser(description="ONNX + 후처리 검증(onnxruntime)")
    ap.add_argument("--img", default="", help="테스트 프레임 jpg (기본: 13_pose_train/dataset/images)")
    args = ap.parse_args()
    for n in ("detection", "detection_full", "pose", "pose_full", "face_state"):
        if not (ONNX / f"{n}.onnx").exists():
            print(f"[에러] {ONNX / f'{n}.onnx'} 없음 — export_onnx.py 먼저")
            return 1
    imgs = ([Path(args.img)] if args.img else
            sorted((HERE.parent / "13_pose_train" / "dataset" / "images").glob("*.jpg")))
    img = cv2.imread(str(imgs[0]))
    if img is None:
        print("[에러] 테스트 이미지 없음")
        return 1

    from src.vision import _names_from_info, load_detector
    nc = len(_names_from_info(RDK / "models" / "detection.pth"))
    det = load_detector(str(RDK / "models" / "detection.pth"))    # face 크롭용(torch)
    crop = None
    for p in imgs[:50]:
        fr = cv2.imread(str(p))
        r = det.predict(fr, conf=0.5, verbose=False)[0] if fr is not None else None
        for b in (r.boxes if r is not None else []):
            if int(b.cls) == 1:
                x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
                crop = fr[max(0, y1):y2, max(0, x1):x2]
                break
        if crop is not None and crop.size:
            break

    print(f"테스트 이미지: {imgs[0].name}  ({img.shape[1]}x{img.shape[0]})  nc={nc}")
    a = check_detect_full(img, nc)
    b = check_pose_full(img)
    c = check_split(img, "detection", nc, 0)
    d = check_split(img, "pose", 1, 17)
    e = check_face(crop) if (crop is not None and crop.size) else (print("[face] baby_face 크롭 없음 — 건너뜀") or True)
    ok = a and b and c and d and e
    print("\n결과:", "PASS — export·단일/분리 후처리 정상 (다음: calib_prep.py → convert.sh)" if ok else "FAIL — 위 차이 확인")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
