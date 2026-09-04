#!/usr/bin/env python3
"""학습 산출물(state_dict .pth / ultralytics .pt) → best.onnx (RDK X5 BPU 용).

사용법:
    python export_onnx.py <model.pth | best.pt> [--out best.onnx] [--imgsz 640]

- opset 11 / imgsz 640 / batch 1 고정 (D-Robotics 툴체인 요구)
- state_dict(OD_Training_Standard 폴백 산출물)면 ultralytics yolo11n 으로 재구성 후 export
"""
import argparse
from pathlib import Path

RDK_GUIDE = """
다음 단계 (RDK X5 배포):
  1. 개발 PC 의 D-Robotics OpenExplorer(ai_toolchain) 도커에서 변환:
       hb_mapper makertbin --config config.yaml --model-type onnx
     config.yaml 핵심: march: "bayes-e", input_type_rt: nv12,
                       input_type_train: bgr   <- 학습 채널 BGR (Training_Standard 규격)
     (캘리브레이션: 실제 babycam 프레임 수십~수백 장 필요)
  2. 생성된 best.bin 을 RDK X5 로 복사 -> baby_detect 노드에서 사용
"""


def die(msg: str):
    print(msg)
    raise SystemExit(1)


def load_yolo(path: Path):
    """ultralytics YOLO 객체 반환 (.pt 체크포인트 / state_dict 모두 대응)."""
    try:
        import torch
        from ultralytics import YOLO
        from ultralytics.nn.tasks import DetectionModel
    except ImportError:
        die('torch + ultralytics 가 필요합니다:  pip install ultralytics')

    ckpt = torch.load(str(path), map_location='cpu', weights_only=False)
    if isinstance(ckpt, dict) and hasattr(ckpt.get('model'), 'yaml'):
        return YOLO(str(path))  # ultralytics 체크포인트(.pt)

    # state_dict → yolo11n 재구성 (단일 클래스 baby)
    state = ckpt.get('state_dict', ckpt) if isinstance(ckpt, dict) else ckpt
    model = DetectionModel(cfg='yolo11n.yaml', ch=3, nc=1, verbose=False)
    try:
        model.load_state_dict(state)
    except RuntimeError:
        # 래퍼 저장 시 붙는 'model.'/'module.' 접두어 1단계 제거 후 재시도
        model.load_state_dict({k.split('.', 1)[1]: v for k, v in state.items() if '.' in k})
    model.names = {0: 'baby'}
    # exporter 가 요구하는 부속 속성(args/task/pt_path...)을 ultralytics 가 채우도록,
    # 네이티브 체크포인트 형태로 임시 저장 후 YOLO() 정식 경로로 로드
    import tempfile
    tmp = Path(tempfile.gettempdir()) / 'od_export_tmp.pt'
    torch.save({'model': model, 'train_args': {'task': 'detect'}}, str(tmp))
    return YOLO(str(tmp))


def main() -> int:
    ap = argparse.ArgumentParser(description='baby OD → ONNX export (opset11, batch1)')
    ap.add_argument('model', help='model.pth(state_dict) 또는 best.pt 경로')
    ap.add_argument('--out', default='best.onnx', help='출력 ONNX 경로 (기본 best.onnx)')
    ap.add_argument('--imgsz', type=int, default=640)
    args = ap.parse_args()

    path = Path(args.model)
    if not path.is_file():
        die(f'모델 파일이 없습니다: {path}')

    yolo = load_yolo(path)
    onnx_path = Path(yolo.export(format='onnx', opset=11, imgsz=args.imgsz,
                                 batch=1, simplify=True, dynamic=False))
    out = Path(args.out)
    if onnx_path.resolve() != out.resolve():
        import shutil
        shutil.move(str(onnx_path), str(out))
    print(f'\nexport 완료: {out.resolve()} (opset 11, imgsz {args.imgsz}, batch 1)')
    print(RDK_GUIDE)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
