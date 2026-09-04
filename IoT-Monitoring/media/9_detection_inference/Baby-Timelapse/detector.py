# -*- coding: utf-8 -*-
"""자체 완결 감지기 — OD_Training_Standard .pth 로드 + 오버레이 (BGR, N클래스).

model.pth 옆 model_info.json 에서 클래스 수·이름을 자동 인식(baby / baby_face …).
.pt/.onnx/사전학습 이름은 그대로 로드. 포즈 없음(감지 전용).
"""
import json
import tempfile
from pathlib import Path

import cv2

CLASS_COLORS = [(0, 255, 0), (255, 0, 255), (0, 165, 255), (255, 255, 0)]  # BGR, 클래스별


def _names_from_info(pth_path):
    """model.pth 옆 model_info.json → {id: name}. 없으면 {0: 'baby'}."""
    try:
        raw = json.loads(Path(pth_path).with_name("model_info.json").read_text(encoding="utf-8"))
        li = json.loads(json.loads(raw["label_info"])["inference_info"])["label_info"]
        return {i: li[f"label_{i}"]["name"] for i in range(int(li["label_count"]))}
    except Exception:
        return {0: "baby"}


def load_detector(path):
    """감지 모델 → ultralytics YOLO. .pth(state_dict)는 nc·이름 자동 재구성."""
    from ultralytics import YOLO
    p = Path(path)
    if not (p.suffix == ".pth" and p.exists()):
        return YOLO(str(path))                             # 사전학습/.pt/.onnx
    import torch
    from ultralytics.nn.tasks import DetectionModel
    ckpt = torch.load(str(p), map_location="cpu", weights_only=False)
    if isinstance(ckpt, dict) and hasattr(ckpt.get("model"), "yaml"):
        return YOLO(str(p))
    state = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    names = _names_from_info(p)
    model = DetectionModel(cfg="yolo11n.yaml", ch=3, nc=len(names), verbose=False)
    try:
        model.load_state_dict(state)
    except RuntimeError:
        model.load_state_dict({k.split(".", 1)[1]: v for k, v in state.items() if "." in k})
    model.names = names
    tmp = Path(tempfile.gettempdir()) / f"det9_nc{len(names)}_tmp.pt"
    torch.save({"model": model, "train_args": {"task": "detect"}}, str(tmp))
    return YOLO(str(tmp))


def draw(frame, result):
    """감지 박스(클래스별 색) + 라벨(이름 conf) 오버레이. 검출 수 반환."""
    n = 0
    if result is not None and result.boxes is not None:
        names = getattr(result, "names", {}) or {}
        for b in result.boxes:
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
            cid = int(b.cls)
            col = CLASS_COLORS[cid % len(CLASS_COLORS)]
            cv2.rectangle(frame, (x1, y1), (x2, y2), col, 2)
            cv2.putText(frame, f"{names.get(cid, cid)} {float(b.conf):.2f}",
                        (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
            n += 1
    return n
