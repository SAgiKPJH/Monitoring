# -*- coding: utf-8 -*-
"""Keypoint editing + save operations, mixed into PoseTool (pose_ui.py).

self.kps is a 17-slot list of None (undecided) or (x, y, v) in original
pixels; self.cur is the index of the next joint to input.
"""

import pose_io
from pose_format import NUM_KPTS


class PoseEditMixin:
    def place_kp(self, ox, oy):
        """Left click: place the current joint as visible (v=2)."""
        self.last_click = (ox, oy)
        if self.cur >= NUM_KPTS:
            return self.flash("all 17 done - b to edit, SPACE to save", ok=False)
        self.kps[self.cur] = (ox, oy, 2)
        self.cur += 1

    def skip_kp(self):
        """v key / right click: mark the current joint not visible (v=0)."""
        if self.frame is not None and self.cur < NUM_KPTS:
            self.kps[self.cur] = (0.0, 0.0, 0)
            self.cur += 1

    def back_kp(self):
        """b key: step one joint back and clear it for re-input."""
        if self.cur > 0:
            self.cur -= 1
            self.kps[self.cur] = None

    def clear_kps(self):
        """c key: reset every keypoint of the current frame."""
        self.kps, self.cur = [None] * NUM_KPTS, 0

    def save(self, negative=False):
        if self.frame is None:
            return
        if negative and any(k is not None for k in self.kps):
            return self.flash("keypoints exist - press c before negative", ok=False)
        kps = None
        if not negative:  # SPACE before 17/17: remaining joints become v=0
            kps = [k if k is not None else (0.0, 0.0, 0) for k in self.kps]
            if not any(k[2] == 2 for k in kps):
                return self.flash("no visible joint - press x for negative",
                                  ok=False)
        err = pose_io.save_sample(self.out_images, self.out_labels, self.stem(),
                                  self.frame, kps)
        if err:
            return self.flash(err, ok=False)
        if kps is not None:
            self.kps, self.cur = kps, NUM_KPTS
        self.saved[self.stem()] = not negative
        vis = sum(1 for k in kps if k[2] == 2) if kps else 0
        self.flash("SAVED negative (no baby)" if negative
                   else f"SAVED pose ({vis}/{NUM_KPTS} visible)")
