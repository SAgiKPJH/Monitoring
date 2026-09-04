# -*- coding: utf-8 -*-
"""File I/O for the 2-class image labeler: image listing, YOLO label read/write.

Edits an existing dataset in place: images/ stay as they are (BGR JPEG), only
labels/ txt is written. Label line = `<cls> cx cy bw bh` (cls 0=baby, 1=baby_face).
Training_Standard: frames are BGR as cv2 delivers them — no RGB conversion.
"""

from pathlib import Path

import cv2

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}
JPEG_QUALITY = 95


def collect_images(images_dir):
    """Return sorted image paths under a folder (or a single image file)."""
    p = Path(images_dir)
    if p.is_file():
        return [p] if p.suffix.lower() in IMAGE_EXTS else []
    if p.is_dir():
        return sorted(q for q in p.iterdir() if q.suffix.lower() in IMAGE_EXTS)
    return []


def collect_clips(src):
    """Return sorted mp4 list from a folder, or a single-file list (clip mode)."""
    p = Path(src)
    if p.is_file():
        return [p] if p.suffix.lower() == ".mp4" else []
    if p.is_dir():
        return sorted(q for q in p.iterdir() if q.suffix.lower() == ".mp4")
    return []


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


def save_extract(images_dir, labels_dir, stem, frame_bgr, boxes):
    """Clip mode: write extracted JPEG (BGR as-is) + YOLO label. Err text or None."""
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        return "jpeg encode failed"
    try:
        buf.tofile(str(Path(images_dir) / f"{stem}.jpg"))   # unicode-path safe
    except OSError as exc:
        return f"write failed: {exc}"
    h, w = frame_bgr.shape[:2]
    return save_label(labels_dir, stem, boxes, w, h)


def scan_existing(labels_dir):
    """stem -> True(has boxes) / False(empty=negative) for labels already on disk."""
    saved = {}
    for txt in Path(labels_dir).glob("*.txt"):
        try:
            saved[txt.stem] = txt.stat().st_size > 0
        except OSError:
            pass
    return saved


def load_label(labels_dir, stem, w, h):
    """Read a YOLO label into pixel boxes (x1, y1, x2, y2, cls) for re-editing."""
    boxes = []
    try:
        text = (Path(labels_dir) / f"{stem}.txt").read_text(encoding="utf-8")
    except OSError:
        return boxes
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            cls = int(float(parts[0]))
            cx, cy, bw, bh = (float(v) for v in parts[1:])
        except ValueError:
            continue
        boxes.append((int(round((cx - bw / 2) * w)), int(round((cy - bh / 2) * h)),
                      int(round((cx + bw / 2) * w)), int(round((cy + bh / 2) * h)), cls))
    return boxes


def save_label(labels_dir, stem, boxes, w, h):
    """Write YOLO txt (empty = negative). Image is left untouched. Err text or None."""
    lines = [f"{cls} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
             f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}" for x1, y1, x2, y2, cls in boxes]
    try:
        text = "\n".join(lines) + ("\n" if lines else "")
        (Path(labels_dir) / f"{stem}.txt").write_text(text, encoding="utf-8")
    except OSError as exc:
        return f"write failed: {exc}"
    return None
