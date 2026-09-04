"""감지(baby)·포즈 모델 로드 · 추론 · 오버레이 (BGR).

감지: 파인튜닝 baby 모델(state_dict .pth / ultralytics .pt / .onnx) — 초록 박스.
포즈: 사전학습 yolo11-pose(COCO 17) — 하늘색 골격 (참고용, 아기 도메인 약함).
"""
import tempfile
from pathlib import Path

import cv2

SKELETON = [(5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12),
            (11, 13), (13, 15), (12, 14), (14, 16), (0, 5), (0, 6)]


def load_detector(path: str):
    """감지 모델 → ultralytics YOLO.
    - 사전학습 이름/.pt(예: yolo11m.pt) 또는 .onnx → 그대로 (자동 다운로드)
    - OD_Training_Standard state_dict(.pth) → yolo11n 으로 재구성 (baby)
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
    model = DetectionModel(cfg="yolo11n.yaml", ch=3, nc=1, verbose=False)
    try:
        model.load_state_dict(state)
    except RuntimeError:
        model.load_state_dict({k.split(".", 1)[1]: v for k, v in state.items() if "." in k})
    model.names = {0: "baby"}
    tmp = Path(tempfile.gettempdir()) / "detpretrained_tmp.pt"
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
