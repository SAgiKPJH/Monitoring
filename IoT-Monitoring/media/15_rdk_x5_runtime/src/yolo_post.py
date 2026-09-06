# -*- coding: utf-8 -*-
"""YOLO(ultralytics 11) ONNX/BPU 출력 후처리 — 순수 numpy (torch/hobot 무관).

ultralytics 가 export 한 ONNX(NMS 없음) 출력을 그대로 디코드한다.
  detect: (1, 4+nc, N) = xywh(입력 640 px) + 클래스 점수(sigmoid 완료)
  pose  : (1, 56,   N) = xywh + conf + 17*(x, y, v)   (v = keypoint conf)
letterbox 로 넣었으니 결과 좌표를 원본으로 되돌린다(un-letterbox) — ultralytics scale_boxes 와 동일.
BPU 백엔드(vision_bpu)와 PC 검증(14_export_BPU/verify_onnx, onnxruntime)이 이 코드를 공유한다.
"""
import cv2
import numpy as np

PAD = 114


def letterbox(img, size=640):
    """비율 유지 축소 + 회색(114) 패딩 → (size,size). (out, ratio, (left,top)) — ultralytics LetterBox 동일."""
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nw, nh = int(round(w * r)), int(round(h * r))
    dw, dh = (size - nw) / 2, (size - nh) / 2
    out = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR) if (nw, nh) != (w, h) else img.copy()
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    out = cv2.copyMakeBorder(out, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(PAD, PAD, PAD))
    return out, r, (left, top)


_LB_CACHE = {}


def letterbox_shared(img, size=640):
    """letterbox 와 동일하되 **직전 프레임 결과를 캐시** — 같은 프레임에 detect·pose 가 연속 호출될 때 1회만 계산
    (보드 CPU 3~5 ms/프레임 절약). 키 = 버퍼 주소·shape·size + 저해상 지문(주소 재사용 오인 방지)."""
    key = (img.__array_interface__["data"][0], img.shape, size, img[::120, ::120].tobytes())
    if _LB_CACHE.get("k") == key:
        return _LB_CACHE["v"]
    out = letterbox(img, size)
    _LB_CACHE["k"], _LB_CACHE["v"] = key, out
    return out


def unletterbox(xy, ratio, pad, shape=None):
    """letterbox 좌표 → 원본. xy 마지막 축이 (x,y) 반복(xyxy 또는 (..,2)). shape=(h,w) 주면 클립."""
    xy = xy.astype(np.float64).copy()
    xy[..., 0::2] = (xy[..., 0::2] - pad[0]) / ratio
    xy[..., 1::2] = (xy[..., 1::2] - pad[1]) / ratio
    if shape is not None:
        xy[..., 0::2] = xy[..., 0::2].clip(0, shape[1])
        xy[..., 1::2] = xy[..., 1::2].clip(0, shape[0])
    return xy


def _rows(out, c):
    """모델 출력 → (N, C). 채널 수 c 를 기준으로 어떤 차원 배치든 정규화.

    ONNX 는 (1,C,N)/(1,N,C) 지만 BPU(hb_mapper) 는 4D 로 채워 내보낸다: (1,C,N,1) · (1,1,C,N) · (1,N,1,C),
    드물게 (1,C,H,W)(H*W=N). squeeze 후 길이가 c 인 축을 채널로 잡아 (N,C) 로 만든다.
    """
    a = np.squeeze(np.asarray(out, dtype=np.float32))
    if a.ndim == 1:                                   # N==1 로 squeeze 된 경우 (C,)
        return a.reshape(1, -1) if a.shape[0] == c else a.reshape(-1, 1)
    if a.ndim > 2:
        ax = next((i for i, n in enumerate(a.shape) if n == c), None)
        if ax is None:
            raise ValueError(f"출력 형태에서 채널축(={c})을 못 찾음: {np.asarray(out).shape}")
        return np.moveaxis(a, ax, 0).reshape(c, -1).T
    return a if a.shape[1] == c else a.T


def _xywh2xyxy(b):
    x, y, w, h = b.T
    return np.stack([x - w / 2, y - h / 2, x + w / 2, y + h / 2], 1)


def nms(boxes, scores, iou_thr):
    """xyxy (M,4), scores (M,) → keep 인덱스(점수 내림차순). greedy NMS."""
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        rest = order[1:]
        xx1, yy1 = np.maximum(x1[i], x1[rest]), np.maximum(y1[i], y1[rest])
        xx2, yy2 = np.minimum(x2[i], x2[rest]), np.minimum(y2[i], y2[rest])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        iou = inter / (areas[i] + areas[rest] - inter + 1e-9)
        order = rest[iou <= iou_thr]
    return keep


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _chw(m, ch):
    """원시 맵 (1,C,H,W)/(1,H,W,C)/(C,H,W)/(H,W,C) → ((C, H*W), H, W). 채널축 = 길이 ch 이고 나머지 두 축이 같은(H==W) 축."""
    a = np.asarray(m, np.float32)
    if a.ndim == 4 and a.shape[0] == 1:
        a = a[0]
    if a.ndim != 3:
        raise ValueError(f"raw map 형태 이상: {np.asarray(m).shape}")
    for ax in (0, 2):
        o = [d for i, d in enumerate(a.shape) if i != ax]
        if a.shape[ax] == ch and o[0] == o[1]:
            if ax == 2:
                a = np.moveaxis(a, 2, 0)
            return a.reshape(a.shape[0], -1), a.shape[1], a.shape[2]
    raise ValueError(f"채널 {ch} 축을 못 찾음: {a.shape}")


def raw_to_single(maps, nc, nkpt=0, imgsz=640, reg_max=16):
    """분리 출력(스케일별 reg(64)·cls(nc)[·kpt(nkpt*3)] 원시 맵) → ultralytics 단일 출력 (1, 4+nc[+nkpt*3], N).

    INT8 BPU 에서 box(0~640)와 score(0~1)를 한 텐서로 concat 하면 score 가 양자화 step 에 깎여 0 이 된다.
    그래서 14_export_BPU 는 헤드 앞에서 잘라 스케일별 원시 맵을 내보내고(각각 따로 양자화), 여기서 CPU(float)로
    DFL(softmax 기대값)·앵커 복원·sigmoid 를 한다 — ultralytics Detect/Pose 의 _inference·kpts_decode 와 동일.
    맵의 순서/레이아웃(NCHW·NHWC)은 채널 수(64·nc·nkpt*3)와 크기로 자동 판별.
    """
    reg, cls, kpt = {}, {}, {}
    for m in maps:
        for ch, dst in ((4 * reg_max, reg), (nc, cls), (nkpt * 3, kpt)):
            if not ch:
                continue
            try:
                c, H, W = _chw(m, ch)
            except ValueError:
                continue
            dst[H] = c
            break
    if not reg or set(reg) != set(cls) or (nkpt and set(reg) != set(kpt)):
        raise ValueError(f"원시 맵 구성 이상: reg{sorted(reg)} cls{sorted(cls)} kpt{sorted(kpt)}")
    idx = np.arange(reg_max, dtype=np.float32)[None, :, None]
    cols = []
    for H in sorted(reg, reverse=True):                     # 80,40,20 = stride 8,16,32
        s = imgsz / H
        gy, gx = np.mgrid[0:H, 0:H]
        gx, gy = gx.reshape(-1).astype(np.float32), gy.reshape(-1).astype(np.float32)
        d = reg[H].reshape(4, reg_max, -1)                  # DFL: softmax(16) 기대값 → l,t,r,b (grid 단위)
        d = np.exp(d - d.max(1, keepdims=True))
        dist = ((d / d.sum(1, keepdims=True)) * idx).sum(1)
        ax, ay = gx + 0.5, gy + 0.5                          # 앵커 중심
        x1, y1, x2, y2 = ax - dist[0], ay - dist[1], ax + dist[2], ay + dist[3]
        parts = [np.stack([(x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1]) * s, _sigmoid(cls[H])]
        if nkpt:
            k = kpt[H].reshape(nkpt, 3, -1)                  # kpts_decode: (raw*2 + grid) * stride, v=sigmoid
            parts.append(np.stack([(k[:, 0] * 2 + gx) * s, (k[:, 1] * 2 + gy) * s, _sigmoid(k[:, 2])], 1)
                         .reshape(nkpt * 3, -1))
        cols.append(np.concatenate(parts, 0))
    return np.concatenate(cols, 1)[None]                    # (1, 4+nc[+51], 8400)


def decode_detect(out, nc, conf_thr, ratio, pad, shape=None, iou_thr=0.7, max_det=300):
    """detect 출력 → (boxes xyxy 원본좌표 (K,4), conf (K,), cls (K,)). 클래스별 NMS(offset)."""
    p = _rows(out, 4 + nc)
    scores = p[:, 4:4 + nc]
    cls = scores.argmax(1)
    conf = scores[np.arange(len(p)), cls]
    m = conf >= conf_thr
    p, conf, cls = p[m], conf[m], cls[m]
    if len(p) == 0:
        return np.zeros((0, 4)), np.zeros(0), np.zeros(0, int)
    boxes = _xywh2xyxy(p[:, :4])
    keep = nms(boxes + cls[:, None] * 4096.0, conf, iou_thr)[:max_det]   # 클래스 offset → 클래스별 NMS
    return unletterbox(boxes[keep], ratio, pad, shape), conf[keep], cls[keep]


def decode_pose(out, conf_thr, ratio, pad, shape=None, nkpt=17, iou_thr=0.7, max_det=10):
    """pose 출력 → (boxes (K,4), conf (K,), kpts_xy 원본좌표 (K,17,2), kpts_conf (K,17))."""
    p = _rows(out, 5 + nkpt * 3)
    conf = p[:, 4]
    m = conf >= conf_thr
    p, conf = p[m], conf[m]
    if len(p) == 0:
        return np.zeros((0, 4)), np.zeros(0), np.zeros((0, nkpt, 2)), np.zeros((0, nkpt))
    boxes = _xywh2xyxy(p[:, :4])
    keep = nms(boxes, conf, iou_thr)[:max_det]
    kp = p[keep, 5:].reshape(-1, nkpt, 3)
    return (unletterbox(boxes[keep], ratio, pad, shape), conf[keep],
            unletterbox(kp[..., :2], ratio, pad, shape), kp[..., 2])
