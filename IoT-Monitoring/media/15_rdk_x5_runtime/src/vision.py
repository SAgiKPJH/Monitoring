# -*- coding: utf-8 -*-
"""감지·포즈 모델 로드 (14 자립용, 4_detection_pretrained/src/inference 발췌).

- load_detector: OD_Training_Standard state_dict(.pth) → yolo11n 재구성. 클래스명은
  같은 폴더의 `<stem>_info.json`(예: detection_info.json)에서 읽음(없으면 {0:'baby'}).
- load_pose: ultralytics .pt 로드.
모델 파일은 14/models/ 안에 두어 폴더 독립 실행이 가능하다.
"""
import tempfile
from pathlib import Path


def _names_from_info(pth_path):
    """`<stem>_info.json`(OD_Training_Standard 포맷)에서 {id: name}. 실패 시 {0:'baby'}."""
    import json
    try:
        info = pth_path.with_name(pth_path.stem + "_info.json")
        raw = json.loads(info.read_text(encoding="utf-8"))
        li = json.loads(json.loads(raw["label_info"])["inference_info"])["label_info"]
        return {i: li[f"label_{i}"]["name"] for i in range(int(li["label_count"]))}
    except Exception:
        return {0: "baby"}


def load_detector(path: str):
    """감지 모델 → ultralytics YOLO. .pt/.onnx 는 그대로, state_dict .pth 는 yolo11n 재구성."""
    from ultralytics import YOLO
    p = Path(path)
    if not (p.suffix == ".pth" and p.exists()):
        return YOLO(path)                              # 사전학습/.pt/.onnx
    import torch
    ckpt = torch.load(str(p), map_location="cpu", weights_only=False)
    if isinstance(ckpt, dict) and hasattr(ckpt.get("model"), "yaml"):
        return YOLO(str(p))
    from ultralytics.nn.tasks import DetectionModel
    state = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    names = _names_from_info(p)                         # 1클래스(baby)·2클래스(baby+face) 자동
    model = DetectionModel(cfg="yolo11n.yaml", ch=3, nc=len(names), verbose=False)
    try:
        model.load_state_dict(state)
    except RuntimeError:
        model.load_state_dict({k.split(".", 1)[1]: v for k, v in state.items() if "." in k})
    model.names = names
    tmp = Path(tempfile.gettempdir()) / f"det_nc{len(names)}_tmp.pt"
    torch.save({"model": model, "train_args": {"task": "detect"}}, str(tmp))
    return YOLO(str(tmp))


def load_pose(path: str):
    from ultralytics import YOLO
    return YOLO(path)
