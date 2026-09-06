#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\3_classification_training
#   ..\..\.venv\Scripts\python.exe run_training.py
#   기본 dataset\ (2단계 build_dataset.py 산출) + src\params.json 으로 학습 → output\
# ─────────────────────────────────────────────────────────────
"""CNN_Training_Standard 분류 학습 래퍼 — 얼굴 상태(눈×입) 4클래스.

dataset(ImageFolder: 폴더=클래스) + params 를 CNN 표준 진입점에 env 로 넘겨 학습한다.
표준 진입점은 DATASET_PATH/OUTPUT_PATH/PARAMS 환경변수를 읽음(로컬 래퍼 규약).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = r'D:\Code\Training_Standard'
HERE = Path(__file__).resolve().parent


def _net_name(params_path):
    """params 의 network_name (출력 폴더 구분용). 실패 시 'model'."""
    import json
    try:
        with open(params_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)['hyperparameter'].get('network_name', 'model')
    except Exception:
        return 'model'


def main() -> int:
    ap = argparse.ArgumentParser(description='얼굴 상태 속성별 이진 분류 학습 (CNN_Training_Standard 호출)')
    ap.add_argument('--dataset_path', default=str(HERE / 'dataset_eyes_open'),
                    help='속성별 이진 데이터셋 (예: .\\dataset_eyes_open). 2단계 build_dataset.py 산출')
    ap.add_argument('--params', default=str(HERE / 'src' / 'params.json'),
                    help='기본 mobilenet_v2. resnet 은 src\\params_resnet18.json')
    ap.add_argument('--output_path', default='', help='비우면 output_<데이터셋명>_<네트워크>')
    args = ap.parse_args()
    if not args.output_path:                                  # 속성·네트워크별 출력 분리
        args.output_path = str(HERE / f'output_{Path(args.dataset_path).name}_{_net_name(args.params)}')

    root = Path(os.environ.get('TRAINING_STANDARD_ROOT', DEFAULT_ROOT))
    entry = root / 'Training Standard' / 'CNN_Training_Standard' / 'classification_training_standard_local.py'
    if not entry.is_file():
        print(f'[에러] CNN 진입점 없음: {entry}')
        return 1
    if not Path(args.dataset_path).is_dir():
        print(f'[에러] 데이터셋 없음: {args.dataset_path}\n'
              '       먼저 ..\\2_classification_labeling\\build_dataset.py 로 조립하세요.')
        return 1
    if not Path(args.params).is_file():
        print(f'[에러] params 없음: {args.params}')
        return 1

    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(entry.parent), env.get('PYTHONPATH', '')]).rstrip(os.pathsep)
    env['DATASET_PATH'] = str(Path(args.dataset_path).resolve())
    env['OUTPUT_PATH'] = str(Path(args.output_path).resolve())
    env['PARAMS'] = str(Path(args.params).resolve())
    print('실행:', entry, '\n dataset =', env['DATASET_PATH'], '\n output  =', env['OUTPUT_PATH'])
    return subprocess.call([sys.executable, str(entry)], cwd=str(entry.parent), env=env)


if __name__ == '__main__':
    sys.exit(main())
