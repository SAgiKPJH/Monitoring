#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\3_detection_labeling_tool\label_tool
#   ..\..\.venv\Scripts\python.exe main.py                       # 기본 (D:\carved\Cut → D:\carved\yolo_baby)
#   ..\..\.venv\Scripts\python.exe main.py --src <폴더|mp4> --out <출력>
#   키: r 랜덤점프 · n/p 영상 · 트랙바+a/d 1프레임·w/s 1초 · 드래그 박스(여러개, u 취소)
#       SPACE/ENTER 저장 · x 네거티브(아기없음) · q/ESC 종료
# ─────────────────────────────────────────────────────────────
"""Entry point for the YOLO baby-labeling tool.

Browse home-cam clips (mp4), pick frames you like, drag boxes over the baby,
and save original-resolution JPEGs + YOLO txt labels (single class 0 = baby).

Usage:
    python main.py [--src D:\\carved\\Cut] [--out D:\\carved\\yolo_baby]

Modules (Training_Standard: <=200 lines per file):
    main.py         - CLI entry point (this file)
    labeler_ui.py   - window / keyboard / state main loop
    labeler_view.py - overlay rendering + mouse drag-box input
    labeler_io.py   - video listing/opening, JPEG + YOLO label read/write
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
        "        Install them into your environment first, e.g.:\n"
        "          python -m pip install opencv-python numpy\n"
        "        (venv example)\n"
        "          D:\\Code\\Monitoring\\IoT-Monitoring\\media\\.venv\\Scripts\\python.exe"
        " -m pip install opencv-python numpy\n"
        f"        import error: {exc}\n\n"
    )
    sys.exit(1)

from labeler_io import collect_videos  # noqa: E402 - after the friendly cv2 guard
from labeler_ui import LabelTool       # noqa: E402


def main():
    ap = argparse.ArgumentParser(
        description="Bounding-box labeling tool for YOLO baby detection "
                    "(single class 0 = baby). Keys: see README.md")
    ap.add_argument("--src", default=r"D:\carved\Cut",
                    help="mp4 folder or a single mp4 file (default: %(default)s)")
    ap.add_argument("--out", default=r"D:\carved\yolo_baby",
                    help="output root; images/ and labels/ are created under it "
                         "(default: %(default)s)")
    args = ap.parse_args()

    videos = collect_videos(args.src)
    if not videos:
        print(f"[ERROR] no mp4 found at: {args.src}")
        return 1
    print(f"{len(videos)} video(s) found under {args.src}")
    print(f"output -> {args.out}\\images, {args.out}\\labels")
    return LabelTool(videos, Path(args.out)).run()


if __name__ == "__main__":
    sys.exit(main())
