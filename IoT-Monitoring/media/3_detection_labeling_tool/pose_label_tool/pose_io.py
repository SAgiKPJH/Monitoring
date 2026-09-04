# -*- coding: utf-8 -*-
"""File I/O: video listing/opening, JPEG + YOLO-pose label read/write.

Video helpers mirror label_tool/labeler_io.py so both tools behave the same.
Training_Standard channel rule: frames are saved exactly as cv2 delivers them
(BGR order) straight into the JPEG encoder -- no RGB conversion anywhere.
"""

from pathlib import Path

import cv2

from pose_format import build_label_line, parse_label_line

JPEG_QUALITY = 95


def collect_videos(src):
    """Return sorted mp4 list from a folder, or a single-file list."""
    src = Path(src)
    if src.is_file():
        return [src] if src.suffix.lower() == ".mp4" else []
    if src.is_dir():
        return sorted(p for p in src.iterdir() if p.suffix.lower() == ".mp4")
    return []


def scan_existing(labels_dir):
    """stem -> True(pose) / False(negative) for labels already on disk."""
    saved = {}
    for txt in labels_dir.glob("*.txt"):
        try:
            saved[txt.stem] = txt.stat().st_size > 0
        except OSError:
            pass
    return saved


def open_video(videos, idx, step=1):
    """Open videos[idx], skipping unreadable files in `step` direction (wraps).

    Returns (idx, cap, first_frame, frame_count, fps) or None if nothing opens.
    """
    n = len(videos)
    for _ in range(n):
        idx %= n
        cap = cv2.VideoCapture(str(videos[idx]))
        frame = None
        if cap.isOpened():
            ok, frame = cap.read()
            frame = frame if ok else None
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame is not None and count > 0:
            fps = cap.get(cv2.CAP_PROP_FPS)
            return idx, cap, frame, count, (fps if fps and fps > 0 else 15.0)
        cap.release()
        print(f"[skip] unreadable video: {videos[idx]}")
        idx += step
    return None


def load_kps(labels_dir, stem, w, h):
    """Read an existing label back into 17 pixel keypoints (for re-editing).

    Returns the keypoint list, or None when the file is missing/empty/broken
    (negative samples have an empty txt on purpose).
    """
    try:
        text = (labels_dir / f"{stem}.txt").read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        kps = parse_label_line(line, w, h)
        if kps is not None:
            return kps
    return None


def save_sample(images_dir, labels_dir, stem, frame_bgr, kps_px):
    """Save original-res JPEG (BGR as-is) + YOLO-pose txt. Error text or None.

    `kps_px` None means a negative sample: the .txt is created empty on
    purpose. Otherwise it must be 17 (x, y, v) tuples with >=1 visible.
    """
    h, w = frame_bgr.shape[:2]
    line = None
    if kps_px is not None:
        line = build_label_line(kps_px, w, h)
        if line is None:
            return "no visible keypoint - refused"
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        return "jpeg encode failed"
    try:
        buf.tofile(str(images_dir / f"{stem}.jpg"))  # unicode-path safe on Windows
        (labels_dir / f"{stem}.txt").write_text(
            line + "\n" if line else "", encoding="utf-8")
    except OSError as exc:
        return f"write failed: {exc}"
    return None
