#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (PC, 이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\14_export_BPU
#   ..\.venv\Scripts\python.exe export_onnx.py           # ..\15_rdk_x5_runtime\models\*.pth/.pt → onnx\*.onnx
#   ..\.venv\Scripts\python.exe export_onnx.py --no-split   # (비권장) 헤드 포함 단일 출력 ONNX 로 변환하고 싶을 때
#   다음: verify_onnx.py(검증) → calib_prep.py → convert.sh(OE docker, .bin → 15_rdk_x5_runtime\models\)
# ─────────────────────────────────────────────────────────────
r"""15_rdk_x5_runtime/models 의 학습 모델 3개 → ONNX (hb_mapper 입력).

- detection.pth (OD state_dict → yolo11n 재구성) → onnx/detection.onnx  **분리 헤드**: reg_s8/16/32 (1,64,H,W) + cls_s8/16/32 (1,nc,H,W)
- pose.pt (ultralytics)                         → onnx/pose.onnx       **분리 헤드**: reg×3 + cls×3 + kpt_s8/16/32 (1,51,H,W)
- face_state.pth (mobilenet_v2 멀티라벨)          → onnx/face_state.onnx [1,n_attrs] (logits)
- 검증용으로 헤드 포함 단일 출력본도 함께 낸다: onnx/detection_full.onnx (1,4+nc,8400), onnx/pose_full.onnx (1,56,8400)

왜 분리 헤드인가: ultralytics 헤드는 box 좌표(0~640)와 score(0~1)를 한 텐서로 concat 한다. INT8 BPU 가 그 텐서를
하나의 scale 로 양자화하면 score 가 0 으로 깎여 감지가 전혀 안 된다(보드에서 det 최대점수 0.00 로 확인). 헤드의
DFL/concat/sigmoid 앞에서 잘라 스케일별 원시 맵을 따로 내보내면 각각 독립 양자화되고, 보드 CPU(float, numpy) 가
15_rdk_x5_runtime/src/yolo_post.raw_to_single 로 복원한다(RDK 모델주가 YOLO 를 다루는 표준 방식).
opset 11 · 배치 1 고정 · 동적축 없음 · YOLO 640, face 는 meta input_size(128).
"""
import argparse
import shutil
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
RDK = HERE.parent / "15_rdk_x5_runtime"
sys.path.insert(0, str(RDK))

OPSET = 11
YOLO_IMGSZ = 640


def export_yolo_full(model, dst, imgsz):
    """ultralytics YOLO 객체 → 헤드 포함 단일 출력 onnx(NMS 없음, onnxslim). 산출물을 dst 로 이동."""
    f = model.export(format="onnx", imgsz=imgsz, opset=OPSET, simplify=True, dynamic=False, batch=1)
    shutil.move(str(f), str(dst))
    return dst


def export_yolo_split(model, dst, imgsz):
    """ultralytics YOLO 객체 → 헤드 앞에서 자른 분리 출력 onnx (스케일별 reg/cls[/kpt] 원시 맵)."""
    import torch
    m = model.model.eval()
    try:
        m.fuse()
    except Exception:  # noqa: BLE001
        pass
    head = m.model[-1]
    nl, has_kpt = head.nl, hasattr(head, "cv4")

    def fwd(self, x):                                       # Detect/Pose.forward 를 원시 맵 반환으로 교체
        outs = [self.cv2[i](x[i]) for i in range(nl)] + [self.cv3[i](x[i]) for i in range(nl)]
        if has_kpt:
            outs += [self.cv4[i](x[i]) for i in range(nl)]
        return outs
    head.forward = types.MethodType(fwd, head)
    strides = [8 * 2 ** i for i in range(nl)]
    names = ([f"reg_s{s}" for s in strides] + [f"cls_s{s}" for s in strides]
             + ([f"kpt_s{s}" for s in strides] if has_kpt else []))
    torch.onnx.export(m, torch.zeros(1, 3, imgsz, imgsz), str(dst), opset_version=OPSET,
                      input_names=["images"], output_names=names, dynamo=False)
    return dst, names


def export_face(pth, dst):
    import torch
    from src.face_state import load_face_state
    model, meta = load_face_state(pth)
    s = int(meta["input_size"])
    torch.onnx.export(model, torch.zeros(1, 3, s, s), str(dst), opset_version=OPSET,
                      input_names=["images"], output_names=["logits"], dynamo=False)
    return dst, meta


def main() -> int:
    ap = argparse.ArgumentParser(description="15_rdk_x5_runtime/models → ONNX (YOLO 는 분리 헤드)")
    ap.add_argument("--models", default=str(RDK / "models"), help="원본 .pth/.pt 폴더")
    ap.add_argument("--out", default=str(HERE / "onnx"))
    ap.add_argument("--no-split", action="store_true", help="YOLO 를 헤드 포함 단일 출력으로 export(INT8 에서 score 손실 — 비권장)")
    args = ap.parse_args()
    src, out = Path(args.models), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    det_pth, pose_pt, face_pth = src / "detection.pth", src / "pose.pt", src / "face_state.pth"
    for p in (det_pth, pose_pt, face_pth):
        if not p.exists():
            print(f"[에러] 없음: {p}")
            return 1
    from src.vision import load_detector, load_pose

    for name, loader, p in (("detection", load_detector, det_pth), ("pose", load_pose, pose_pt)):
        full = export_yolo_full(loader(str(p)), out / f"{name}_full.onnx", YOLO_IMGSZ)
        print(f"{name:10} full  → {full}   (검증 기준·단일 출력)")
        if args.no_split:
            shutil.copy2(full, out / f"{name}.onnx")
            print(f"{name:10} split 생략 → {out / f'{name}.onnx'} 는 단일 출력본(--no-split)")
        else:
            d, names = export_yolo_split(loader(str(p)), out / f"{name}.onnx", YOLO_IMGSZ)
            print(f"{name:10} split → {d}   출력 {len(names)}개: {', '.join(names)}")
    f, meta = export_face(str(face_pth), out / "face_state.onnx")
    print(f"face_state → {f}  (input {meta['input_size']}, attrs {meta['attrs']})")
    for name in ("detection_info.json", "face_state_info.json"):   # 보드 로더용 sidecar(15_rdk_x5_runtime/models 그대로)
        if not (src / name).exists():
            print(f"[경고] {src / name} 없음 — 보드에서 클래스명/attrs 못 읽음")
    print("\n다음: verify_onnx.py 로 검증(분리 디코드 = 단일 출력 확인) → calib_prep.py → convert.sh(OE docker) 로 .bin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
