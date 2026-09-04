#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# 실행:  cd D:\Code\Monitoring\IoT-Monitoring\media\8_detection_2class_train\label_tool
#
# [A] 이미지 편집 모드 — 이미 뽑아둔 dataset 이미지에 baby_face 추가
#   ..\..\.venv\Scripts\python.exe main.py                                              # 기본: 7_auto_labeling\dataset
#   ..\..\.venv\Scripts\python.exe main.py --images ..\..\7_auto_labeling\dataset\images
#   ..\..\.venv\Scripts\python.exe main.py --images <이미지폴더> --labels <저장폴더>       # 저장 위치 분리
#
# [B] 클립 모드 — carved-08 클립(mp4)을 넘겨보며 프레임을 dataset 으로 추출
#   ..\..\.venv\Scripts\python.exe main.py --clips D:\carved-08\Cut                      # 단일 폴더
#   ..\..\.venv\Scripts\python.exe main.py --clips D:\carved-08\Cut D:\carved\Cut        # 복수 폴더
#   ..\..\.venv\Scripts\python.exe main.py --clips D:\carved-08\Cut --out <저장dataset>  # 저장 dataset 지정
#
#   키: 1 baby · 2 baby_face(활성) · 드래그 박스 · u 취소 · c 비우기 · SPACE 저장 · x 네거티브 · q 종료
#       (A) n/p 이미지 이동   (B) n/p 클립 · r 랜덤 · a/d ±1프레임 · w/s ±1초 · 트랙바
#
# ..\..\.venv\Scripts\python.exe main.py --clips D:\carved-08\Cut D:\carved\Cut --out D:\Code\Monitoring\IoT-Monitoring\media\8_detection_2class_train\dataset
# ─────────────────────────────────────────────────────────────
r"""2-class bounding-box labeler (baby=0, baby_face=1) — 두 가지 모드.

[A] 이미지 편집 모드(--images): 기존 dataset 이미지를 열어 baby_face 등 박스를 추가/수정,
    이미지는 그대로 두고 labels\ txt 만 갱신. 저장된 라벨은 다시 열면 자동 로드.
[B] 클립 모드(--clips): mp4 클립을 넘겨보며 고른 프레임을 dataset 으로 추출(JPEG+라벨) 저장.
    --clips 는 여러 폴더/파일을 받는다. BGR 무변환 (Training_Standard).

Modules (Training_Standard: <=200 lines/file):
    main.py         - CLI entry point (this file, 모드 분기)
    labeler_ui.py   - [A] 이미지 네비게이션 메인루프 (LabelTool)
    clip_ui.py      - [B] 클립 탐색 + 프레임 추출 메인루프 (ClipLabelTool)
    labeler_view.py - overlay rendering (per-class color) + mouse drag-box (공용)
    labeler_io.py   - image/clip listing, 영상 열기, YOLO label read/write, 추출 저장
"""
import argparse
import sys
from pathlib import Path

try:
    import cv2    # noqa: F401 - checked here so the error message is friendly
    import numpy  # noqa: F401
except ImportError as exc:
    sys.stderr.write(
        "\n[ERROR] Required packages are missing: opencv-python, numpy\n"
        "        e.g.  ..\\..\\.venv\\Scripts\\python.exe -m pip install opencv-python numpy\n"
        f"        import error: {exc}\n\n")
    sys.exit(1)

from labeler_io import collect_clips, collect_images  # noqa: E402 - after cv2 guard
from labeler_ui import LabelTool                       # noqa: E402
from clip_ui import ClipLabelTool                      # noqa: E402

_DATASET = Path(__file__).resolve().parent.parent.parent / "7_auto_labeling" / "dataset"
DEFAULT_IMAGES = str(_DATASET / "images")
DEFAULT_OUT = str(_DATASET)


def _gather_clips(sources):
    """여러 폴더/파일에서 mp4 를 모아 경로 중복 제거 + 이름순 정렬."""
    clips, seen = [], set()
    for src in sources:
        found = collect_clips(src)
        if not found:
            print(f"[warn] no mp4 at: {src}")
        for c in found:
            if str(c) not in seen:
                seen.add(str(c))
                clips.append(c)
    return sorted(clips, key=lambda p: p.name)


def main():
    ap = argparse.ArgumentParser(
        description="2-class (baby, baby_face) box labeler. Keys: 1/2 class, drag box, "
                    "SPACE save, x negative, q quit")
    ap.add_argument("--images", default=DEFAULT_IMAGES,
                    help="이미지 편집 모드: 이미지 폴더 (기본: %(default)s)")
    ap.add_argument("--labels", default="",
                    help="이미지 모드 라벨 폴더 (기본: images 의 형제 labels\\)")
    ap.add_argument("--clips", nargs="+", metavar="DIR",
                    help="클립 모드: mp4 폴더/파일 (여러 개 가능) — 프레임을 dataset 으로 추출")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="클립 모드 추출 저장 dataset (images/ labels/ 생성, 기본: %(default)s)")
    args = ap.parse_args()

    if args.clips:                                     # ── 클립 모드 (프레임 추출) ──
        clips = _gather_clips(args.clips)
        if not clips:
            print(f"[ERROR] no mp4 found in --clips: {args.clips}")
            return 1
        out = Path(args.out)
        print(f"{len(clips)} clip(s) from {len(args.clips)} source(s)")
        print(f"extract -> {out}\\images, {out}\\labels   (1=baby, 2=baby_face)")
        return ClipLabelTool(clips, out).run()

    images = collect_images(args.images)               # ── 이미지 편집 모드 ──
    if not images:
        print(f"[ERROR] no image found at: {args.images}")
        return 1
    labels_dir = Path(args.labels) if args.labels else Path(args.images).parent / "labels"
    print(f"{len(images)} image(s) under {args.images}")
    print(f"labels -> {labels_dir}   (1=baby, 2=baby_face)")
    return LabelTool(images, labels_dir).run()


if __name__ == "__main__":
    sys.exit(main())
