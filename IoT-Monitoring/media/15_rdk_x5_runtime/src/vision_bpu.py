# -*- coding: utf-8 -*-
"""RDK X5 BPU 백엔드 — hobot_dnn(pyeasy_dnn) 로 models/detection.bin · pose.bin 추론.

vision.py(torch) 와 같은 인터페이스: load_detector(path)/load_pose(path) → .predict(frame, conf, verbose)
결과는 monitoring/pose_motion 이 쓰는 최소 duck-type(boxes: cls/conf/xyxy[0], keypoints: xy[0]/conf[0]/len).
전처리: letterbox 640 후 .bin 입력 속성(shape/layout/tensor_type)에 맞춰 자동 투입(NHWC-BGR · NCHW-BGR · NV12).
후처리: yolo_post (순수 numpy — PC 에서 onnxruntime 으로 검증한 동일 코드).
  - 출력 1개(ultralytics 단일 텐서 (1,4+nc,8400)) → 그대로 디코드.
  - 출력 여러 개(14_export_BPU --split-head: 스케일별 reg/cls[/kpt] 원시 맵) → raw_to_single 로 CPU 에서 DFL·sigmoid·
    앵커 복원 후 디코드. INT8 에서 box 와 score 를 한 텐서로 합치면 score 가 0 으로 깎이므로 이 방식이 기본.
진단: 로드 시 입력 속성·투입 방식, 첫 forward 시 출력 형태를 출력. predict 후 last_max(임계 전 최대 점수).
torch 는 import 하지 않는다(보드에 불필요).
"""
import os
from pathlib import Path

import cv2
import numpy as np

from .vision import _names_from_info          # torch 없이 import 가능(지연 import 구조)
from .yolo_post import _rows, decode_detect, decode_pose, raw_to_single
from .yolo_post import letterbox_shared as letterbox   # 같은 프레임에 detect·pose 연속 호출 시 letterbox 1회

IOU_THR = 0.7                                # ultralytics 기본 NMS iou
NKPT = 17


class _Box:
    __slots__ = ("cls", "conf", "xyxy")

    def __init__(self, cls, conf, xyxy):
        self.cls, self.conf, self.xyxy = int(cls), float(conf), [list(map(float, xyxy))]  # xyxy[0]


class _Kpts:
    def __init__(self, xy, conf):
        self.xy, self.conf = xy, conf        # (K,17,2), (K,17) numpy — [0]=첫(최고 conf) 사람

    def __len__(self):
        return len(self.xy)


class _Result:
    def __init__(self, boxes=None, keypoints=None, names=None):
        self.boxes, self.keypoints, self.names = boxes or [], keypoints, names or {}


# ─────────────── 입력/출력 텐서 어댑터 ───────────────
DEFAULT_INPUT = (os.environ.get("BPU_INPUT") or "nchw_i8").lower()   # .env 의 빈 값(BPU_INPUT=)도 기본값으로   # .env 로 덮어쓰기 가능 (아래 실측 근거)


def _input_mode(shape, layout="", ttype=""):
    """.bin 입력 속성 → (mode, h, w).  mode: nv12 | nchw_i8(기본) | nchw_u8 | nhwc_u8 | nhwc_i8

    **RDK X5 실측(OE 1.2.8 · DNN 1.24.5, bpu_input_probe.py)**: yaml `input_type_rt: bgr`·`input_layout_rt: NHWC` 로
    컴파일한 .bin 은 속성에 NHWC/uint8 로 보고되지만, pyeasy_dnn.forward 에는 **NCHW (1,3,H,W) int8(uint8-128)** 로
    넣어야 PC 양자화 모델과 같은 점수가 나온다(0.924 = PC 0.924). NHWC uint8 로 넣으면 점수 0.000, NCHW uint8 은 0.83.
    그래서 이미지 입력은 속성 문자열과 무관하게 DEFAULT_INPUT(nchw_i8) 을 쓰고, NV12 타입만 자동 판별한다.
    다른 보드/OE 버전에서 다르면 .env 의 BPU_INPUT 으로 바꾸고 bpu_input_probe.py 로 확인.
    """
    shape = tuple(int(x) for x in shape)
    t, l = str(ttype).upper(), str(layout).upper()
    nhwc_like = len(shape) == 4 and shape[-1] in (1, 3) and shape[1] not in (1, 3)
    if "NV12" in t or "YUV" in t:
        h, w = (shape[1], shape[2]) if ("NHWC" in l or nhwc_like) else (shape[-2], shape[-1])
        return "nv12", h, w
    h, w = (shape[1], shape[2]) if ("NHWC" in l or nhwc_like) else (shape[2], shape[3])
    return DEFAULT_INPUT, h, w


def _bgr2nv12(img):
    """BGR(HxWx3) → NV12 1-D uint8 (Y h*w 뒤에 UV 인터리브 h*w/2). h, w 짝수."""
    h, w = img.shape[:2]
    yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV_I420)          # (h*3/2, w): Y | U(h/4) | V(h/4)
    y = yuv[:h].reshape(-1)
    u = yuv[h:h + h // 4].reshape(-1)
    v = yuv[h + h // 4:].reshape(-1)
    uv = np.empty(u.size + v.size, np.uint8)
    uv[0::2], uv[1::2] = u, v
    return np.concatenate([y, uv])


def _prep_input(img_hwc, mode):
    """BGR uint8 HWC → pyeasy_dnn 투입 배열. mode 별 레이아웃/자료형 (bpu_input_probe.py 로 검증)."""
    img = np.ascontiguousarray(img_hwc, dtype=np.uint8)
    if mode == "nv12":
        return _bgr2nv12(img)
    i8 = (img.astype(np.int16) - 128).astype(np.int8) if mode.endswith("_i8") else img
    if mode.startswith("nchw"):
        return np.ascontiguousarray(i8.transpose(2, 0, 1)[None])          # (1,3,H,W)
    return np.ascontiguousarray(i8[None])                                  # (1,H,W,3)


def _dequant(o):
    """pyeasy_dnn 출력 텐서 → float32 numpy. 정수(양자화) 출력이면 properties.scale_data 로 역양자화."""
    b = np.asarray(o.buffer)
    if b.dtype.kind not in "iu":
        return b.astype(np.float32, copy=False)
    sc = getattr(getattr(o, "properties", None), "scale_data", None)
    sc = np.asarray(sc, np.float32).ravel() if sc is not None else np.zeros(0, np.float32)
    b = b.astype(np.float32)
    if sc.size == 1:
        return b * sc[0]
    if sc.size > 1:
        ax = next((i for i, n in enumerate(b.shape) if n == sc.size), None)
        if ax is not None:
            shape = [1] * b.ndim
            shape[ax] = sc.size
            return b * sc.reshape(shape)
    print(f"[vision_bpu] 정수 출력 {b.shape} 에 scale(len={sc.size}) 적용 실패 — 14_export_BPU yaml 출력 설정 확인")
    return b


class _BpuModel:
    """pyeasy_dnn 모델 1개. forward(bgr_uint8_HWC) → float32 출력 numpy 리스트(입력 형식은 자동 맞춤)."""

    def __init__(self, bin_path):
        from hobot_dnn import pyeasy_dnn as dnn          # 보드 전용(지연 import)
        self.m = dnn.load(str(bin_path))[0]
        self.name = Path(bin_path).name
        p = self.m.inputs[0].properties
        self.shape = tuple(int(x) for x in p.shape)
        layout, ttype = getattr(p, "layout", ""), getattr(p, "tensor_type", "")
        self.mode, self.h, self.w = _input_mode(self.shape, layout, ttype)
        self._logged = False
        print(f"[vision_bpu] {self.name} 입력 shape={self.shape} layout={layout} type={ttype} "
              f"→ 투입 {self.mode.upper()} {self.w}x{self.h}", flush=True)

    def forward(self, img_hwc):
        outs = self.m.forward(_prep_input(img_hwc, self.mode))
        res = [_dequant(o) for o in outs]
        if not self._logged:                             # 원격 진단용: 출력 형태를 1회 출력
            self._logged = True
            kind = "단일 출력(헤드 포함)" if len(res) == 1 else f"분리 출력 {len(res)}개(원시 맵 → CPU 디코드)"
            print(f"[vision_bpu] {self.name} 출력 {kind}: " + ", ".join(f"{tuple(r.shape)}" for r in res), flush=True)
        return res


def _single(outs, nc, nkpt=0):
    """출력 리스트 → ultralytics 단일 텐서 (1, 4+nc[+nkpt*3], N). 1개면 그대로, 여러 개면 원시 맵 디코드."""
    return outs[0] if len(outs) == 1 else raw_to_single(outs, nc, nkpt)


# ─────────────── 감지 / pose ───────────────
class _Detector:
    def __init__(self, bin_path):
        self.bpu = _BpuModel(bin_path)
        self.names = _names_from_info(Path(bin_path))   # detection_info.json (bin 옆)
        self.nc = len(self.names)
        self.last_max = None                             # 임계 전 클래스별 최대 점수(진단)

    def predict(self, frame, conf=0.25, verbose=False, **_):
        lb, r, pad = letterbox(frame, self.bpu.w)
        out = _single(self.bpu.forward(lb), self.nc)
        self.last_max = _rows(out, 4 + self.nc)[:, 4:4 + self.nc].max(0).tolist()
        boxes, cf, cls = decode_detect(out, self.nc, conf, r, pad, frame.shape[:2], IOU_THR)
        return [_Result(boxes=[_Box(c, s, b) for b, s, c in zip(boxes, cf, cls)], names=self.names)]


class _Pose:
    def __init__(self, bin_path):
        self.bpu = _BpuModel(bin_path)
        self.last_max = None                             # 임계 전 최대 conf(진단)

    def predict(self, frame, conf=0.25, verbose=False, **_):
        lb, r, pad = letterbox(frame, self.bpu.w)
        out = _single(self.bpu.forward(lb), 1, NKPT)
        self.last_max = float(_rows(out, 5 + NKPT * 3)[:, 4].max())
        boxes, cf, kxy, kcf = decode_pose(out, conf, r, pad, frame.shape[:2], iou_thr=IOU_THR)
        kp = _Kpts(kxy, kcf) if len(boxes) else None
        return [_Result(boxes=[_Box(0, s, b) for b, s in zip(boxes, cf)], keypoints=kp)]


def load_detector(path):
    return _Detector(path)


def load_pose(path):
    return _Pose(path)
