# -*- coding: utf-8 -*-
"""Presentation layer: overlay rendering and mouse drag-box input.

Overlay text is English only (cv2.putText cannot draw Hangul).
"""

import time

import cv2

MAX_DISP_W, MAX_DISP_H = 1600, 900   # display fit size; saves stay original-res
MIN_BOX_PX = 8                       # ignore accidental tiny drags (original px)
COL_BOX = (0, 255, 0)                # finished boxes: green
COL_DRAG = (0, 255, 255)             # box being dragged: yellow
COL_TEXT = (255, 255, 255)
COL_SAVED = (0, 165, 255)            # "already saved" tag: orange
COL_OK = (80, 255, 80)
COL_WARN = (80, 80, 255)
HELP_LINE = ("n/p:video r:random | a/d:+-1frame w/s:+-1sec | drag:box u:undo "
             "c:clear | SPACE/ENTER:save x:negative q/ESC:quit")


def put_text(img, s, org, scale=0.55, color=COL_TEXT, thick=1):
    """putText with a dark outline so text stays readable on any frame."""
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0),
                thick + 2, cv2.LINE_AA)
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color,
                thick, cv2.LINE_AA)


def make_mouse_handler(tool):
    """cv2 mouse callback: drag to add a box (display coords -> original coords)."""
    def on_mouse(event, x, y, flags, param):
        if tool.frame is None:
            return
        h, w = tool.frame.shape[:2]
        ox = max(0, min(int(round(x / tool.scale)), w - 1))
        oy = max(0, min(int(round(y / tool.scale)), h - 1))
        if event == cv2.EVENT_LBUTTONDOWN:
            tool.dragging, tool.drag_a, tool.drag_b = True, (ox, oy), (ox, oy)
        elif event == cv2.EVENT_MOUSEMOVE and tool.dragging:
            tool.drag_b = (ox, oy)
        elif event == cv2.EVENT_LBUTTONUP and tool.dragging:
            tool.dragging = False
            x1, x2 = sorted((tool.drag_a[0], ox))
            y1, y2 = sorted((tool.drag_a[1], oy))
            if (x2 - x1) >= MIN_BOX_PX and (y2 - y1) >= MIN_BOX_PX:
                tool.boxes.append((x1, y1, x2, y2))
            tool.drag_a = tool.drag_b = None
    return on_mouse


def render(tool):
    """Compose the display image: boxes + status overlay + flash message."""
    disp = tool.disp_base.copy()
    s = tool.scale
    for x1, y1, x2, y2 in tool.boxes:
        cv2.rectangle(disp, (int(x1 * s), int(y1 * s)),
                      (int(x2 * s), int(y2 * s)), COL_BOX, 2)
    if tool.dragging and tool.drag_a and tool.drag_b:
        cv2.rectangle(disp, (int(tool.drag_a[0] * s), int(tool.drag_a[1] * s)),
                      (int(tool.drag_b[0] * s), int(tool.drag_b[1] * s)), COL_DRAG, 1)

    pos = sum(1 for v in tool.saved.values() if v)
    neg = len(tool.saved) - pos
    put_text(disp, f"[{tool.vid_idx + 1}/{len(tool.videos)}] {tool.video_path.name}",
             (8, 24))
    put_text(disp, f"frame {tool.frame_idx + 1}/{tool.frame_count}  "
                   f"boxes:{len(tool.boxes)}  "
                   f"saved pos:{pos} neg:{neg} total:{pos + neg}", (8, 48))
    state = tool.saved.get(tool.stem())
    if state is not None:
        put_text(disp, "[SAVED: POSITIVE]" if state else "[SAVED: NEGATIVE]",
                 (8, 72), color=COL_SAVED)
    put_text(disp, HELP_LINE, (8, disp.shape[0] - 10), scale=0.45)
    if time.time() < tool.flash_until:
        put_text(disp, tool.flash_text,
                 (max(8, disp.shape[1] // 2 - 8 * len(tool.flash_text)),
                  disp.shape[0] // 2),
                 scale=0.9, color=COL_OK if tool.flash_ok else COL_WARN, thick=2)
    return disp
