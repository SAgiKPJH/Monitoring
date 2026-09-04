#!/usr/bin/env python3
"""OD_Training_Standard 학습 진입점 얇은 래퍼.

사용법:
    python run_training.py [--dataset_path .\\dataset] [--params params_gpu.json]

기본 데이터셋은 이 폴더의 dataset\\ (images/ labels/), 기본 params 는 params.json.
Training_Standard 경로: 기본 D:\\Code\\Training_Standard,
환경변수 TRAINING_STANDARD_ROOT 로 재정의 가능.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = r'D:\Code\Training_Standard'
DEFAULT_DATASET = str(Path(__file__).with_name('dataset'))


def main() -> int:
    ap = argparse.ArgumentParser(description='baby OD 학습 실행 (OD_Training_Standard 호출)')
    ap.add_argument('--dataset_path', default=DEFAULT_DATASET,
                    help='images/ labels/ 를 담은 데이터셋 폴더 (기본: 이 폴더의 dataset)')
    ap.add_argument('--params', default=str(Path(__file__).resolve().parent / 'src' / 'params_gpu.json'),
                    help='하이퍼파라미터 JSON (기본: src\\params_gpu.json)')
    ap.add_argument('--output_path', default=str(Path(__file__).resolve().parent / 'output'),
                    help='학습 산출물 폴더 (기본: 이 폴더의 output)')
    args = ap.parse_args()

    root = Path(os.environ.get('TRAINING_STANDARD_ROOT', DEFAULT_ROOT))
    entry = root / 'Training Standard' / 'OD_Training_Standard' / 'od_training_standard_local.py'

    if not root.is_dir():
        print(f'[에러] Training_Standard 저장소가 없습니다: {root}\n'
              '       환경변수 TRAINING_STANDARD_ROOT 로 실제 경로를 지정하세요.')
        return 1
    if not entry.is_file():
        print(f'[에러] 학습 진입점이 아직 없습니다: {entry}\n'
              '       OD_Training_Standard 구현(병렬 진행 중)이 완료됐는지 확인하세요.')
        return 1
    if not Path(args.dataset_path).is_dir():
        print(f'[에러] 데이터셋 폴더가 없습니다: {args.dataset_path}')
        return 1
    if not Path(args.params).is_file():
        print(f'[에러] params 파일이 없습니다: {args.params}')
        return 1

    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(
        [str(root), str(entry.parent), env.get('PYTHONPATH', '')]).rstrip(os.pathsep)

    cmd = [sys.executable, str(entry),
           '--dataset_path', str(Path(args.dataset_path).resolve()),
           '--params', str(Path(args.params).resolve()),
           '--output_path', str(Path(args.output_path).resolve())]
    print('실행:', ' '.join(cmd))
    return subprocess.call(cmd, cwd=str(entry.parent), env=env)


if __name__ == '__main__':
    sys.exit(main())
