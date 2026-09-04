# -*- coding: utf-8 -*-
"""Presentation layer: display fit + 2x zoom, overlay rendering, mouse input.

The view transform is (ox0, oy0, sx, sy): disp = (orig - offset) * s.
Mouse coords are inverse-transformed with the same tuple, so clicks stay
accurate in both normal and zoomed mode. Overlay text is English only
(cv2.putText cannot draw Hangul).
"""

import time

import cv2

from pose_format import KPT_NAMES, NUM_KPTS, SKELETON

MAX_DISP_W, MAX_DISP_H = 1600, 900   # display fit size; saves stay original-res
ZOOM = 2.0                           # z-key magnification around last click
COL_TEXT = (255, 255, 255)
COL_SAVED = (0, 165, 255)            # "already saved" tag: orange
COL_OK = (80, 255, 80)
COL_WARN = (80, 80, 255)
COL_CENTER = (0, 255, 0)             # nose: green
COL_LEFT = (0, 165, 255)             # left_* joints: orange
COL_RIGHT = (255, 220, 0)            # right_* joints: cyan
COL_BONE = (200, 200, 200)           # skeleton lines: light gray
HELP_LINE = ("n/p:video r:random | a/d:+-1frame w/s:+-1sec | LClick:place "
             "v/RClick:hidden b:back c:clear z:zoom | SPACE/ENTER:save "
             "x:negative q/ESC:quit")


def kpt_color(i):
    """nose green, left side orange, right side cyan (odd/even COCO index)."""
    if i == 0:
        return COL_CENTER
    return COL_LEFT if i % 2 == 1 else COL_RIGHT


def put_text(img, s, org, scale=0.55, color=COL_TEXT, thick=1):
    """putText with a dark outline so text stays readable on any frame."""
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0),
                thick + 2, cv2.LINE_AA)
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color,
                thick, cv2.LINE_AA)


def make_view(frame, zoom, center):
    """Build (disp_base, view) for the frame honoring the zoom toggle.

    Window size is identical in both modes; zoom shows a ZOOM-times crop
    centered on `center` (last click, original px) clamped inside the frame.
    """
    h, w = frame.shape[:2]
    fit = min(1.0, MAX_DISP_W / w, MAX_DISP_H / h)
    dw, dh = int(round(w * fit)), int(round(h * fit))
    if not zoom:
        disp = (cv2.resize(frame, (dw, dh), interpolation=cv2.INTER_AREA)
                if fit < 1.0 else frame.copy())
        return disp, (0.0, 0.0, dw / w, dh / h)
    rw = min(w, max(2, int(round(dw / (fit * ZOOM)))))
    rh = min(h, max(2, int(round(dh / (fit * ZOOM)))))
    cx, cy = center if center else (w / 2.0, h / 2.0)
    x0 = int(round(min(max(cx - rw / 2, 0), w - rw)))
    y0 = int(round(min(max(cy - rh / 2, 0), h - rh)))
    disp = cv2.resize(frame[y0:y0 + rh, x0:x0 + rw], (dw, dh),
                      interpolation=cv2.INTER_LINEAR)
    return disp, (float(x0), float(y0), dw / rw, dh / rh)


def make_mouse_handler(tool):
    """cv2 mouse callback: display coords -> original coords via tool.view."""
    def on_mouse(event, x, y, flags, param):
        if tool.frame is None:
            return
        h, w = tool.frame.shape[:2]
        x0, y0, sx, sy = tool.view
        ox = min(max(x0 + x / sx, 0.0), w - 1.0)
        oy = min(max(y0 + y / sy, 0.0), h - 1.0)
        if event == cv2.EVENT_LBUTTONDOWN:
            tool.place_kp(ox, oy)
        elif event == cv2.EVENT_RBUTTONDOWN:
            tool.skip_kp()
    return on_mouse


def _to_disp(pt, view):
    x0, y0, sx, sy = view
    return int(round((pt[0] - x0) * sx)), int(round((pt[1] - y0) * sy))


def render(tool):
    """Compose the display image: skeleton + joints + status overlay + flash."""
    disp = tool.disp_base.copy()
    for a, b in SKELETON:                     # bones between visible joints only
        ka, kb = tool.kps[a], tool.kps[b]
        if ka and kb and ka[2] == 2 and kb[2] == 2:
            cv2.line(disp, _to_disp(ka, tool.view), _to_disp(kb, tool.view),
                     COL_BONE, 1, cv2.LINE_AA)
    for i, k in enumerate(tool.kps):
        if k and k[2] == 2:
            p = _to_disp(k, tool.view)
            cv2.circle(disp, p, 4, kpt_color(i), -1, cv2.LINE_AA)
            put_text(disp, str(i + 1), (p[0] + 6, p[1] - 6), scale=0.45,
                     color=kpt_color(i))

    pos = sum(1 for v in tool.saved.values() if v)
    neg = len(tool.saved) - pos
    zoom_tag = "  [ZOOM x2]" if tool.zoom else ""
    put_text(disp, f"[{tool.vid_idx + 1}/{len(tool.videos)}] "
                   f"{tool.video_path.name}{zoom_tag}", (8, 24))
    put_text(disp, f"frame {tool.frame_idx + 1}/{tool.frame_count}  "
                   f"saved pose:{pos} neg:{neg} total:{pos + neg}", (8, 48))
    vis = sum(1 for k in tool.kps if k and k[2] == 2)
    if tool.cur < NUM_KPTS:
        put_text(disp, f"NEXT {tool.cur + 1}/{NUM_KPTS}: {KPT_NAMES[tool.cur]}"
                       f"  (visible:{vis})", (8, 78), scale=0.7,
                 color=kpt_color(tool.cur), thick=2)
    else:
        put_text(disp, f"ALL {NUM_KPTS} DONE (visible:{vis}) - SPACE to save",
                 (8, 78), scale=0.7, color=COL_OK, thick=2)
    state = tool.saved.get(tool.stem())
    if state is not None:
        put_text(disp, "[SAVED: POSE]" if state else "[SAVED: NEGATIVE]",
                 (8, 102), color=COL_SAVED)
    put_text(disp, HELP_LINE, (8, disp.shape[0] - 10), scale=0.45)
    if time.time() < tool.flash_until:
        put_text(disp, tool.flash_text,
                 (max(8, disp.shape[1] // 2 - 8 * len(tool.flash_text)),
                  disp.shape[0] // 2),
                 scale=0.9, color=COL_OK if tool.flash_ok else COL_WARN, thick=2)
    return disp
