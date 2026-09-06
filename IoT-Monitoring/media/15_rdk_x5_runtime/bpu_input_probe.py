#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 보드 전용 진단 — detection.bin 에 같은 이미지를 여러 입력 형식으로 넣어 "맞는 형식"을 찾는다.
#   python3 bpu_input_probe.py                                   # ref_frames/2026-08-03_10-05-37_f0021.jpg (PC INT8 기준 0.92)
#   python3 bpu_input_probe.py <이미지> [models/detection.bin]
#   → 형식별 det 최대점수 표. 0.8~0.9 가 나오는 줄이 정답 → src/vision_bpu._prep_input 에 반영.
# ─────────────────────────────────────────────────────────────
r"""PC 의 양자화 ONNX(HB_ONNXRuntime)는 0.85 인데 보드 .bin 이 0.000 이면 모델이 아니라 **hobot_dnn 에 넣는 입력 형식**이
문제다. HWC/NHWC · BGR/RGB · uint8/int8(-128) · NCHW · NV12 를 전부 시도해 어떤 형식에서 점수가 살아나는지 본다.
입출력 텐서 속성(type/layout/scale, 원시 출력 dtype·범위)도 함께 출력한다.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from src.yolo_post import _rows, letterbox, raw_to_single   # noqa: E402
from src.vision_bpu import _bgr2nv12, _dequant               # noqa: E402

NC = 2


def _props(t):
    p = t.properties
    sd = getattr(p, "scale_data", None)
    sc = np.asarray(sd if sd is not None else []).ravel()
    return (f"shape={tuple(int(x) for x in p.shape)} layout={getattr(p, 'layout', '?')} "
            f"type={getattr(p, 'tensor_type', '?')} dtype={getattr(p, 'dtype', '?')} scale_len={sc.size}"
            + (f" scale[:2]={sc[:2].tolist()}" if sc.size else ""))


def score(outs):
    res = [_dequant(o) for o in outs]
    single = raw_to_single(res, NC) if len(res) > 1 else res[0]
    mx = _rows(single, 4 + NC)[:, 4:4 + NC].max(0)
    raws = [np.asarray(o.buffer) for o in outs]
    cls = [a for a in raws if NC in a.shape and 64 not in a.shape]          # 원시 cls 맵(디양자화 전)
    stat = f"{cls[0].dtype}[{float(cls[0].min()):.2f},{float(cls[0].max()):.2f}]" if cls else "-"
    return mx, stat


def main() -> int:
    img_path = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "ref_frames" / "2026-08-03_10-05-37_f0021.jpg")
    bin_path = sys.argv[2] if len(sys.argv) > 2 else str(HERE / "models" / "detection.bin")
    from hobot_dnn import pyeasy_dnn as dnn                     # 보드 전용
    m = dnn.load(bin_path)[0]
    print(f"모델: {bin_path}")
    for i, t in enumerate(m.inputs):
        print(f"  input[{i}]  {_props(t)}")
    for i, t in enumerate(m.outputs):
        print(f"  output[{i}] {_props(t)}")

    img = cv2.imread(img_path)
    if img is None:
        print(f"[에러] 이미지 없음: {img_path}")
        return 1
    lb, _, _ = letterbox(img, 640)
    i8 = (lb.astype(np.int16) - 128).astype(np.int8)
    variants = [
        ("HWC  uint8 BGR (현재 코드)", np.ascontiguousarray(lb)),
        ("HWC  uint8 RGB", np.ascontiguousarray(lb[:, :, ::-1])),
        ("NHWC uint8 BGR (1,H,W,3)", np.ascontiguousarray(lb[None])),
        ("NHWC uint8 RGB (1,H,W,3)", np.ascontiguousarray(lb[None, :, :, ::-1])),
        ("HWC  int8  BGR (uint8-128)", np.ascontiguousarray(i8)),
        ("NHWC int8  BGR (1,H,W,3)", np.ascontiguousarray(i8[None])),
        ("CHW  uint8 BGR", np.ascontiguousarray(lb.transpose(2, 0, 1))),
        ("NCHW uint8 BGR (1,3,H,W)", np.ascontiguousarray(lb.transpose(2, 0, 1)[None])),
        ("NCHW int8  BGR (1,3,H,W)", np.ascontiguousarray(i8.transpose(2, 0, 1)[None])),
        ("NV12 (BGR→NV12 1-D)", _bgr2nv12(lb)),
        ("NV12 (H*3/2, W) 2-D", _bgr2nv12(lb).reshape(-1, 640)),
    ]
    print(f"\n이미지: {Path(img_path).name}  (PC INT8 기준: det baby≈0.92 / face≈0.85)")
    print(f"{'입력 형식':32} {'det max baby':>12} {'face':>7}   원시 cls 출력 dtype[min,max]")
    for label, x in variants:
        try:
            outs = m.forward(x)
            mx, stat = score(outs)
            flag = "  ◀ 정답 후보" if mx.max() > 0.5 else ""
            print(f"{label:32} {mx[0]:12.3f} {mx[1]:7.3f}   {stat}{flag}")
        except Exception as e:  # noqa: BLE001
            print(f"{label:32} forward 실패: {type(e).__name__}: {str(e)[:70]}")
    print("\n0.8 이상이 나온 형식을 알려주세요 → src/vision_bpu._prep_input 에 반영합니다. "
          "전부 0 이면 원시 cls dtype/범위와 output 속성(scale) 을 보고 역양자화를 고칩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
