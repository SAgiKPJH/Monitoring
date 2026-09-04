#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\3_Detection_Labeling_Tool\pose_label_tool
#   ..\..\.venv\Scripts\python.exe main.py                       # 기본 (D:\carved\Cut → D:\carved\yolo_baby_pose)
#   ..\..\.venv\Scripts\python.exe main.py --src <폴더|mp4> --out <출력>
#   키: 좌클릭=관절 배치(순서 안내) · v/우클릭=안보임 · b 뒤로 · c 초기화 · z 2배확대
#       SPACE/ENTER 저장(남은 관절 자동 안보임) · x 네거티브 · q/ESC 종료
# ─────────────────────────────────────────────────────────────
"""Entry point for the YOLO-pose baby keypoint labeling tool.

Browse home-cam clips (mp4), pick frames, click the 17 COCO keypoints in
guided order (one baby per frame), and save original-resolution JPEGs +
YOLO-pose txt labels (single class 0 = baby, kpt_shape [17, 3]).

Usage:
    python main.py [--src D:\\carved\\Cut] [--out D:\\carved\\yolo_baby_pose]

Modules (Training_Standard: <=200 lines per file):
    main.py            - CLI entry point (this file)
    pose_ui.py         - state init, key map, main event loop
    pose_nav.py        - video open/seek, trackbar, view refresh (mixin)
    pose_edit.py       - keypoint place/skip/undo/save operations (mixin)
    pose_view.py       - display fit + zoom, overlay rendering, mouse input
    pose_io.py         - video listing/opening, JPEG + label read/write
    pose_format.py     - COCO-17 constants and pure label-line build/parse
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

from pose_io import collect_videos  # noqa: E402 - after the friendly cv2 guard
from pose_ui import PoseTool        # noqa: E402


def main():
    ap = argparse.ArgumentParser(
        description="COCO-17 keypoint labeling tool for YOLO-pose baby "
                    "fine-tuning (single class 0 = baby, one baby per frame). "
                    "Keys: see README.md")
    ap.add_argument("--src", default=r"D:\carved\Cut",
                    help="mp4 folder or a single mp4 file (default: %(default)s)")
    ap.add_argument("--out", default=r"D:\carved\yolo_baby_pose",
                    help="output root; images/ and labels/ are created under it "
                         "(default: %(default)s)")
    args = ap.parse_args()

    videos = collect_videos(args.src)
    if not videos:
        print(f"[ERROR] no mp4 found at: {args.src}")
        return 1
    print(f"{len(videos)} video(s) found under {args.src}")
    print(f"output -> {args.out}\\images, {args.out}\\labels")
    return PoseTool(videos, Path(args.out)).run()


if __name__ == "__main__":
    sys.exit(main())
