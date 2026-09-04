# -*- coding: utf-8 -*-
"""COCO-17 constants and pure YOLO-pose label-line helpers.

No cv2/numpy here so the format logic stays unit-testable on its own.
A keypoint is (x, y, v) in pixels with v=2 (visible) or v=0 (not labeled,
stored as x=y=0). One baby per frame -> one label line per file.
"""

KPT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]
NUM_KPTS = len(KPT_NAMES)                       # 17
FLIP_IDX = [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
SKELETON = [                                    # standard COCO pairs, 0-based
    (15, 13), (13, 11), (16, 14), (14, 12), (11, 12),
    (5, 11), (6, 12), (5, 6), (5, 7), (6, 8), (7, 9), (8, 10),
    (1, 2), (0, 1), (0, 2), (1, 3), (2, 4), (3, 5), (4, 6),
]
BOX_MARGIN = 0.15      # auto-bbox margin per side, fraction of keypoint extent
MIN_BOX_PX = 2.0       # floor for degenerate extents (e.g. one visible joint)


def auto_bbox(kps_px, w, h):
    """Visible-keypoint extent + BOX_MARGIN per side, clamped to the image.

    Returns (x1, y1, x2, y2) in pixels, or None when nothing is visible.
    A degenerate extent (single joint / collinear joints) is widened to
    MIN_BOX_PX so the saved box never has zero width/height.
    """
    xs = [k[0] for k in kps_px if k[2] == 2]
    ys = [k[1] for k in kps_px if k[2] == 2]
    if not xs:
        return None
    x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
    x1, x2 = x1 - (x2 - x1) * BOX_MARGIN, x2 + (x2 - x1) * BOX_MARGIN
    y1, y2 = y1 - (y2 - y1) * BOX_MARGIN, y2 + (y2 - y1) * BOX_MARGIN
    if x2 - x1 < MIN_BOX_PX:
        cx = (x1 + x2) / 2
        x1, x2 = cx - MIN_BOX_PX / 2, cx + MIN_BOX_PX / 2
    if y2 - y1 < MIN_BOX_PX:
        cy = (y1 + y2) / 2
        y1, y2 = cy - MIN_BOX_PX / 2, cy + MIN_BOX_PX / 2
    return (max(0.0, x1), max(0.0, y1), min(float(w), x2), min(float(h), y2))


def build_label_line(kps_px, w, h):
    """One YOLO-pose line: '0 cx cy bw bh x1 y1 v1 ... x17 y17 v17'.

    All coordinates normalized to 0~1; v is 2 (visible) or 0 (not labeled).
    Returns None when no keypoint is visible (caller must refuse the save).
    """
    box = auto_bbox(kps_px, w, h)
    if box is None:
        return None
    x1, y1, x2, y2 = box
    parts = ["0", f"{(x1 + x2) / 2 / w:.6f}", f"{(y1 + y2) / 2 / h:.6f}",
             f"{(x2 - x1) / w:.6f}", f"{(y2 - y1) / h:.6f}"]
    for x, y, v in kps_px:
        if v == 2:
            parts += [f"{min(max(x / w, 0.0), 1.0):.6f}",
                      f"{min(max(y / h, 0.0), 1.0):.6f}", "2"]
        else:
            parts += ["0.000000", "0.000000", "0"]
    return " ".join(parts)


def parse_label_line(line, w, h):
    """Parse one saved line back into 17 pixel keypoints, or None if malformed.

    Any v >= 1 is loaded as visible (v=2) so hand-edited v=1 labels stay
    editable; they are re-saved as v=2.
    """
    vals = line.split()
    if len(vals) != 5 + NUM_KPTS * 3:
        return None
    try:
        nums = [float(v) for v in vals]
    except ValueError:
        return None
    kps = []
    for i in range(NUM_KPTS):
        x, y, v = nums[5 + i * 3: 8 + i * 3]
        kps.append((x * w, y * h, 2) if v >= 1 else (0.0, 0.0, 0))
    return kps
