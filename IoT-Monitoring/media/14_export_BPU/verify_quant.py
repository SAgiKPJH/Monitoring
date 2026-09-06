#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 양자화(INT8) 정확도 PC 테스트 — OE docker 안에서 실행 (보드 없이, .bin 과 동일한 양자화 모델을 x86 에서 돌림)
#   docker run --rm -it --platform linux/amd64 -v D:\Code\Monitoring\IoT-Monitoring\media:/work -w /work/14_export_BPU \
#       openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8 python3 verify_quant.py --n 20
#   전제: convert.sh 실행 후 out/<모델>/<모델>_quantized_model.onnx 존재. 프레임은 calib/frames (또는 --frames <폴더>).
# ─────────────────────────────────────────────────────────────
r"""float ONNX(onnx/<모델>.onnx, 분리 헤드) vs hb_mapper 양자화 ONNX(out/<모델>/<모델>_quantized_model.onnx)를
같은 프레임으로 돌려 **임계 전 최대 점수·감지 결과**를 비교한다.

양자화 ONNX 는 보드 .bin 과 수치적으로 동일(툴체인 보장)하므로
  - 여기서도 점수가 죽어 있으면 → 캘리브레이션/양자화 문제(PC 에서 yaml·calib 로 해결)
  - 여기선 멀쩡한데 보드에서만 안 되면 → 보드 입력/런타임 문제
HB_ONNXRuntime(horizon_tc_ui) 사용 — docker 전용. 후처리는 15_rdk_x5_runtime/src/yolo_post(보드와 동일 코드).
"""
import argparse
import glob
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
RDK = HERE.parent / "15_rdk_x5_runtime"
sys.path.insert(0, str(RDK))
from src.yolo_post import _rows, decode_detect, decode_pose, letterbox, raw_to_single  # noqa: E402

CONF = 0.25
NKPT = 17


def _runtime():
    try:
        from horizon_tc_ui import HB_ONNXRuntime
        return HB_ONNXRuntime
    except ImportError:
        print("[에러] horizon_tc_ui(HB_ONNXRuntime) 없음 — OE docker 안에서 실행하세요 (README 참고)")
        sys.exit(1)


def _io(sess):
    ins = [i.name for i in sess.get_inputs()]
    outs = [o.name for o in sess.get_outputs()]
    return ins, outs, [int(d) if str(d).isdigit() else d for d in sess.get_inputs()[0].shape]


def run_float(sess, lb):
    """float ONNX: RGB float NCHW /255 (우리 verify_onnx 와 동일 전처리)."""
    ins, outs, _ = _io(sess)
    x = np.ascontiguousarray(lb[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0)
    return [np.asarray(o, np.float32) for o in sess.run(outs, {ins[0]: x})]


def run_quant(sess, lb):
    """양자화 ONNX: 런타임 입력 그대로(BGR uint8, 레이아웃은 모델 입력 shape 로 판별). uint8 → input_offset=128."""
    ins, outs, shp = _io(sess)
    nhwc = len(shp) == 4 and shp[-1] == 3
    x = np.ascontiguousarray(lb[None] if nhwc else lb.transpose(2, 0, 1)[None], dtype=np.uint8)
    try:
        res = sess.run(outs, {ins[0]: x}, input_offset=128)
    except TypeError:                                    # 구버전 시그니처
        res = sess.run(outs, {ins[0]: x})
    return [np.asarray(o, np.float32) for o in res]


def single(outs, nc, nkpt=0):
    return outs[0] if len(outs) == 1 else raw_to_single(outs, nc, nkpt)


def main() -> int:
    ap = argparse.ArgumentParser(description="float vs INT8(양자화 ONNX) 비교 — OE docker 전용")
    ap.add_argument("--frames", default=str(HERE / "calib" / "frames"), help="테스트 프레임 폴더(jpg)")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--model", default="all", choices=["all", "detection", "pose"])
    args = ap.parse_args()
    HB = _runtime()
    frames = sorted(glob.glob(str(Path(args.frames) / "*.jpg")))[: args.n]
    if not frames:
        print(f"[에러] 프레임 없음: {args.frames}")
        return 1
    import json
    from src.vision import _names_from_info
    nc = len(_names_from_info(RDK / "models" / "detection.bin"))
    print(f"프레임 {len(frames)}장 · nc={nc}")

    ok_all = True
    for name in (["detection", "pose"] if args.model == "all" else [args.model]):
        fq = HERE / "out" / name / f"{name}_quantized_model.onnx"
        ff = HERE / "onnx" / f"{name}.onnx"
        if not fq.exists():
            print(f"\n[{name}] {fq} 없음 — convert.sh 먼저 (out/ 보존)")
            ok_all = False
            continue
        sf, sq = HB(model_file=str(ff)), HB(model_file=str(fq))
        print(f"\n===== {name} =====  float: {ff.name}  |  quant: {fq.name}  (입력 {_io(sq)[2]})")
        print(f"{'프레임':28} {'float max':>10} {'quant max':>10} {'float n':>8} {'quant n':>8}  IoU(첫 박스)")
        fmax, qmax, fdet, qdet = [], [], 0, 0
        for p in frames:
            img = cv2.imread(p)
            lb, r, pad = letterbox(img, 640)
            if name == "detection":
                of, oq = single(run_float(sf, lb), nc), single(run_quant(sq, lb), nc)
                mf, mq = float(_rows(of, 4 + nc)[:, 4:].max()), float(_rows(oq, 4 + nc)[:, 4:].max())
                bf, cf, _ = decode_detect(of, nc, CONF, r, pad, img.shape[:2])
                bq, cq, _ = decode_detect(oq, nc, CONF, r, pad, img.shape[:2])
            else:
                of, oq = single(run_float(sf, lb), 1, NKPT), single(run_quant(sq, lb), 1, NKPT)
                mf, mq = float(_rows(of, 5 + NKPT * 3)[:, 4].max()), float(_rows(oq, 5 + NKPT * 3)[:, 4].max())
                bf, cf, _, _ = decode_pose(of, CONF, r, pad, img.shape[:2])
                bq, cq, _, _ = decode_pose(oq, CONF, r, pad, img.shape[:2])
            iou = "-"
            if len(bf) and len(bq):
                a, b = bf[0], bq[0]
                x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
                inter = max(0, x2 - x1) * max(0, y2 - y1)
                iou = f"{inter / ((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter + 1e-9):.2f}"
            fmax.append(mf); qmax.append(mq); fdet += len(bf) > 0; qdet += len(bq) > 0
            print(f"{Path(p).name[:28]:28} {mf:10.3f} {mq:10.3f} {len(bf):8d} {len(bq):8d}  {iou}")
        print(f"{'평균/합계':28} {np.mean(fmax):10.3f} {np.mean(qmax):10.3f} {fdet:8d} {qdet:8d}")
        ratio = np.mean(qmax) / max(np.mean(fmax), 1e-6)
        verdict = ("양자화 정상(점수 보존)" if ratio > 0.7 else
                   "양자화가 점수를 크게 깎음 → 캘리브레이션 데이터/yaml(calibration_type, 분리 헤드) 점검" if ratio > 0.05 else
                   "양자화 후 점수가 사실상 0 → 분리 헤드 export 인지(onnx 출력 6/9개), 캘리브레이션 입력형식 점검")
        print(f"→ quant/float 최대점수 비율 {ratio:.2f} : {verdict}")
        ok_all &= ratio > 0.7
    print("\n결과:", "PASS — INT8 모델이 float 과 유사하게 감지함 (보드에서만 안 되면 보드 입력/런타임 쪽)" if ok_all else "FAIL/주의 — 위 판정 참고")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
