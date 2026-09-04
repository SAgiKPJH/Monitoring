# -*- coding: utf-8 -*-
"""File I/O for the labeling tool: video listing/opening, YOLO labels, JPEG saving.

Training_Standard channel rule: frames are saved exactly as cv2 delivers them
(BGR order) straight into the JPEG encoder -- no RGB conversion anywhere.
"""

from pathlib import Path

import cv2

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
    """stem -> True(positive) / False(negative) for labels already on disk."""
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


def load_label(labels_dir, stem, w, h):
    """Read an existing YOLO label back into pixel boxes (for re-editing)."""
    boxes = []
    try:
        text = (labels_dir / f"{stem}.txt").read_text(encoding="utf-8")
    except OSError:
        return boxes
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            _, cx, cy, bw, bh = (float(v) for v in parts)
        except ValueError:
            continue
        boxes.append((int(round((cx - bw / 2) * w)), int(round((cy - bh / 2) * h)),
                      int(round((cx + bw / 2) * w)), int(round((cy + bh / 2) * h))))
    return boxes


def save_sample(images_dir, labels_dir, stem, frame_bgr, boxes):
    """Save original-res JPEG (BGR as-is) + YOLO txt. Returns error text or None.

    `boxes` empty means a negative sample: the .txt is created empty on purpose.
    """
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        return "jpeg encode failed"
    h, w = frame_bgr.shape[:2]
    lines = [f"0 {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
             f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}" for x1, y1, x2, y2 in boxes]
    try:
        buf.tofile(str(images_dir / f"{stem}.jpg"))  # unicode-path safe on Windows
        text = "\n".join(lines) + ("\n" if lines else "")
        (labels_dir / f"{stem}.txt").write_text(text, encoding="utf-8")
    except OSError as exc:
        return f"write failed: {exc}"
    return None
