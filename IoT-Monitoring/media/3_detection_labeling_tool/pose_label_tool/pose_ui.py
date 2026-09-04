# -*- coding: utf-8 -*-
"""Interactive state machine and main loop (cv2 window, keyboard dispatch).

Composition: PoseNavMixin (video/trackbar/view refresh) + PoseEditMixin
(keypoint place/skip/undo/save). This file owns state init, the key map
and the event loop.
"""

import random
import time

import cv2

import pose_io
from pose_edit import PoseEditMixin
from pose_format import NUM_KPTS
from pose_nav import TRACKBAR, WIN, PoseNavMixin
from pose_view import make_mouse_handler, render

FLASH_SEC = 0.9


class PoseTool(PoseNavMixin, PoseEditMixin):
    def __init__(self, videos, out_dir):
        self.videos = videos
        self.out_images = out_dir / "images"
        self.out_labels = out_dir / "labels"
        self.out_images.mkdir(parents=True, exist_ok=True)
        self.out_labels.mkdir(parents=True, exist_ok=True)
        self.vid_idx, self.cap, self.video_path = 0, None, None
        self.frame_count, self.fps, self.frame_idx = 0, 15.0, 0
        self.frame, self.disp_base, self.view = None, None, (0.0, 0.0, 1.0, 1.0)
        self.kps, self.cur = [None] * NUM_KPTS, 0
        self.zoom, self.last_click = False, None
        self.pending_seek = None                        # set by trackbar callback
        self._tb_guard = self._tb_ready = False
        self.flash_text, self.flash_until, self.flash_ok = "", 0.0, True
        self.saved = pose_io.scan_existing(self.out_labels)

    def stem(self):
        return f"{self.video_path.stem}_f{self.frame_idx:04d}"

    def flash(self, text, ok=True):
        self.flash_text, self.flash_ok = text, ok
        self.flash_until = time.time() + FLASH_SEC
        name = self.video_path.name if self.video_path else "-"
        print(f"[{name} f{self.frame_idx:04d}] {text}")

    def _handle_key(self, key):
        if key == ord("n"):
            self.open_video(self.vid_idx + 1, 1)
        elif key == ord("p"):
            self.open_video(self.vid_idx - 1, -1)
        elif key == ord("r") and len(self.videos) > 1:
            idx = self.vid_idx
            while idx == self.vid_idx:
                idx = random.randrange(len(self.videos))
            self.open_video(idx, 1)
        elif key == ord("a"):
            self.seek(self.frame_idx - 1)
        elif key == ord("d"):
            self.seek(self.frame_idx + 1)
        elif key == ord("w"):
            self.seek(self.frame_idx + int(round(self.fps)))
        elif key == ord("s"):
            self.seek(self.frame_idx - int(round(self.fps)))
        elif key == ord("v"):                 # current joint not visible
            self.skip_kp()
        elif key == ord("b"):                 # one joint back (re-do)
            self.back_kp()
        elif key == ord("c"):
            self.clear_kps()
        elif key == ord("z"):                 # 2x zoom around last click
            self.zoom = not self.zoom
            self._update_view()
        elif key in (32, 13):                 # SPACE / ENTER -> pose save
            self.save(negative=False)
        elif key == ord("x"):                 # negative save (no baby)
            self.save(negative=True)

    def run(self):
        cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(WIN, make_mouse_handler(self))
        if not self.open_video(0, 1):
            print("[ERROR] no readable video in the source.")
            cv2.destroyAllWindows()
            return 1
        cv2.createTrackbar(TRACKBAR, WIN, 0, max(self.frame_count - 1, 1),
                           self._on_trackbar)
        self._tb_ready = True
        self._sync_trackbar()
        while True:
            if self.pending_seek is not None:
                target, self.pending_seek = self.pending_seek, None
                self.seek(target)
            cv2.imshow(WIN, render(self))
            key = cv2.waitKey(30)
            if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
                break                         # user closed the window
            if key == -1:
                continue
            key &= 0xFF
            if 65 <= key <= 90:               # tolerate CapsLock / Shift
                key += 32
            if key in (ord("q"), 27):         # q / ESC
                break
            self._handle_key(key)
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
        pos = sum(1 for v in self.saved.values() if v)
        print(f"done. saved total {len(self.saved)} "
              f"(pose:{pos} neg:{len(self.saved) - pos}) -> {self.out_images.parent}")
        return 0
