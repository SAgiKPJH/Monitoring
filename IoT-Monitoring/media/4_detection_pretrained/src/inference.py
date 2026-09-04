"""감지(baby)·포즈 모델 로드 · 추론 · 오버레이 (BGR).

감지: 파인튜닝 baby 모델(state_dict .pth / ultralytics .pt / .onnx) — 초록 박스.
포즈: 사전학습 yolo11-pose(COCO 17) — 하늘색 골격 (참고용, 아기 도메인 약함).
"""
import tempfile
from pathlib import Path

import cv2

SKELETON = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12),
            (11, 13), (13, 15), (12, 14), (14, 16), (0, 5), (0, 6)]


def _names_from_info(pth_path):
    """model.pth 옆 model_info.json 에서 {id: name} 로드 (OD_Training_Standard 저장 포맷).
    없거나 파싱 실패 시 단일 클래스 {0: 'baby'}."""
    import json
    try:
        raw = json.loads(pth_path.with_name("model_info.json").read_text(encoding="utf-8"))
        li = json.loads(json.loads(raw["label_info"])["inference_info"])["label_info"]
        return {i: li[f"label_{i}"]["name"] for i in range(int(li["label_count"]))}
    except Exception:
        return {0: "baby"}


def load_detector(path: str):
    """감지 모델 → ultralytics YOLO.
    - 사전학습 이름/.pt(예: yolo11m.pt) 또는 .onnx → 그대로 (자동 다운로드)
    - OD_Training_Standard state_dict(.pth) → yolo11n 으로 재구성 (nc·클래스명은 model_info.json)
    """
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


def infer(det, pose, frame, conf, classes=None):
    """(det_result, pose_result) — 각각 None 가능. classes 로 감지 클래스 필터(예: [0]=person)."""
    det_r = det.predict(frame, conf=conf, classes=classes, verbose=False)[0] if det else None
    pose_r = pose.predict(frame, conf=0.10, verbose=False)[0] if pose else None
    return det_r, pose_r


def draw(frame, det_r, pose_r, kp_thr=0.3):
    """감지 박스(초록) + 포즈 골격(하늘색) 오버레이. 검출 수 반환. 라벨은 모델 클래스명."""
    n_det = 0
    if det_r is not None and det_r.boxes is not None:
        names = getattr(det_r, "names", {}) or {}
        for b in det_r.boxes:
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
            label = names.get(int(b.cls), "obj")
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{label} {float(b.conf):.2f}", (x1, max(y1 - 6, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
            n_det += 1
    if (pose_r is not None and pose_r.keypoints is not None
            and len(pose_r.keypoints) > 0 and pose_r.keypoints.conf is not None):
        kps, confs = pose_r.keypoints.xy[0], pose_r.keypoints.conf[0]
        for a, b in SKELETON:
            if float(confs[a]) > kp_thr and float(confs[b]) > kp_thr:
                cv2.line(frame, tuple(map(int, kps[a])), tuple(map(int, kps[b])), (255, 255, 0), 2)
        for j in range(len(kps)):
            if float(confs[j]) > kp_thr:
                cv2.circle(frame, tuple(map(int, kps[j])), 3, (255, 200, 0), -1)
    return n_det
