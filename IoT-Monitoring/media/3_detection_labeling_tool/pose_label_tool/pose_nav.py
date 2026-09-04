# -*- coding: utf-8 -*-
"""Video navigation + trackbar + view refresh, mixed into PoseTool (pose_ui.py)."""

import cv2

import pose_io
from pose_format import NUM_KPTS
from pose_view import make_view

WIN = "baby-pose-label-tool"
TRACKBAR = "frame"


class PoseNavMixin:
    def open_video(self, idx, step=1):
        opened = pose_io.open_video(self.videos, idx, step)
        if opened is None:
            return False
        if self.cap is not None:
            self.cap.release()
        self.vid_idx, self.cap, frame, self.frame_count, self.fps = opened
        self.video_path = self.videos[self.vid_idx]
        self._set_frame(0, frame)
        self._sync_trackbar()
        return True

    def seek(self, idx):
        idx = max(0, min(idx, self.frame_count - 1))
        if idx == self.frame_idx and self.frame is not None:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.flash(f"cannot read frame {idx}", ok=False)
        else:
            self._set_frame(idx, frame)
        self._sync_trackbar()

    def _set_frame(self, idx, frame):
        self.frame_idx, self.frame = idx, frame
        self._update_view()
        stem = self.stem()  # reload keypoints of an already-saved frame
        h, w = frame.shape[:2]
        loaded = (pose_io.load_kps(self.out_labels, stem, w, h)
                  if self.saved.get(stem) else None)
        self.kps = loaded if loaded else [None] * NUM_KPTS
        self.cur = NUM_KPTS if loaded else 0

    def _update_view(self):
        self.disp_base, self.view = make_view(self.frame, self.zoom,
                                              self.last_click)

    def _on_trackbar(self, pos):
        if not self._tb_guard:
            self.pending_seek = pos

    def _sync_trackbar(self):
        if not self._tb_ready:
            return
        self._tb_guard = True
        try:
            cv2.setTrackbarMax(TRACKBAR, WIN, max(self.frame_count - 1, 1))
        except AttributeError:
            pass
        cv2.setTrackbarPos(TRACKBAR, WIN, self.frame_idx)
        self._tb_guard = False
