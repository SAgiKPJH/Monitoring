# -*- coding: utf-8 -*-
"""Clip-mode main loop: browse mp4 clips, pick frames, draw baby/baby_face boxes,
then EXTRACT the frame into a dataset (images/ + labels/). 2 classes.

이미지 편집기(labeler_ui.LabelTool)와 달리, 클립에서 고른 프레임을 dataset 으로 새로 추출 저장한다.
같은 프레임을 다시 열면 저장된 라벨을 불러와 재편집. BGR 무변환 (Training_Standard).
"""

import random
import time

import cv2

import labeler_io
from labeler_view import MAX_DISP_H, MAX_DISP_W, make_mouse_handler, render

WIN = "baby-2class-clip-tool"
TRACKBAR = "frame"
FLASH_SEC = 0.9


class ClipLabelTool:
    def __init__(self, videos, out_dir):
        self.videos = videos
        self.out_images = out_dir / "images"
        self.out_labels = out_dir / "labels"
        self.out_images.mkdir(parents=True, exist_ok=True)
        self.out_labels.mkdir(parents=True, exist_ok=True)
        self.vid_idx, self.cap, self.video_path = 0, None, None
        self.frame_count, self.fps, self.frame_idx = 0, 15.0, 0
        self.frame, self.disp_base, self.scale = None, None, 1.0
        self.boxes, self.dragging = [], False           # boxes: (x1,y1,x2,y2,cls) original px
        self.drag_a = self.drag_b = None
        self.active_cls = 0                             # 0=baby, 1=baby_face
        self.pending_seek = None
        self._tb_guard = self._tb_ready = False
        self.flash_text, self.flash_until, self.flash_ok = "", 0.0, True
        self.saved = labeler_io.scan_existing(self.out_labels)

    def stem(self):
        return f"{self.video_path.stem}_f{self.frame_idx:04d}" if self.video_path else "-"

    def headline(self):
        return (f"[{self.vid_idx + 1}/{len(self.videos)} CLIP] {self.video_path.name}"
                f"  f{self.frame_idx + 1}/{self.frame_count}")

    def help_text(self):
        return ("1:baby 2:baby_face | n/p:clip r:random a/d:+-1f w/s:+-1s | drag:box "
                "u:undo c:clear | SPACE:save x:negative q:quit")

    def flash(self, text, ok=True):
        self.flash_text, self.flash_ok = text, ok
        self.flash_until = time.time() + FLASH_SEC
        print(f"[{self.stem()}] {text}")

    def open_video(self, idx, step=1):
        opened = labeler_io.open_video(self.videos, idx, step)
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
        h, w = frame.shape[:2]
        self.scale = min(1.0, MAX_DISP_W / w, MAX_DISP_H / h)
        size = (int(w * self.scale), int(h * self.scale))
        self.disp_base = (cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
                          if self.scale < 1.0 else frame.copy())
        self.dragging, self.drag_a, self.drag_b = False, None, None
        self.boxes = (labeler_io.load_label(self.out_labels, self.stem(), w, h)
                      if self.saved.get(self.stem()) else [])

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

    def save(self, negative=False):
        if self.frame is None:
            return
        if negative and self.boxes:
            return self.flash("boxes exist - press c to clear before negative", ok=False)
        if not negative and not self.boxes:
            return self.flash("no box - drag one, or press x for negative", ok=False)
        err = labeler_io.save_extract(self.out_images, self.out_labels, self.stem(),
                                      self.frame, self.boxes)
        if err:
            return self.flash(err, ok=False)
        self.saved[self.stem()] = not negative
        n_face = sum(1 for b in self.boxes if b[4] == 1)
        self.flash("SAVED negative" if negative
                   else f"SAVED {len(self.boxes)} box(es) (face:{n_face})")

    def _handle_key(self, key):
        if key == ord("n"):
            self.open_video(self.vid_idx + 1, 1)
        elif key == ord("p"):
            self.open_video(self.vid_idx - 1, -1)
        elif key == ord("r") and len(self.videos) > 1:
            j = self.vid_idx
            while j == self.vid_idx:
                j = random.randrange(len(self.videos))
            self.open_video(j, 1)
        elif key == ord("a"):
            self.seek(self.frame_idx - 1)
        elif key == ord("d"):
            self.seek(self.frame_idx + 1)
        elif key == ord("w"):
            self.seek(self.frame_idx + int(round(self.fps)))
        elif key == ord("s"):
            self.seek(self.frame_idx - int(round(self.fps)))
        elif key == ord("1"):
            self.active_cls = 0
        elif key == ord("2"):
            self.active_cls = 1
        elif key == ord("u") and self.boxes:
            self.boxes.pop()
        elif key == ord("c"):
            self.boxes = []
        elif key in (32, 13):                 # SPACE / ENTER -> positive save
            self.save(negative=False)
        elif key == ord("x"):                 # negative save (no target)
            self.save(negative=True)

    def run(self):
        cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(WIN, make_mouse_handler(self))
        if not self.open_video(0, 1):
            print("[ERROR] no readable video in the source.")
            cv2.destroyAllWindows()
            return 1
        cv2.createTrackbar(TRACKBAR, WIN, 0, max(self.frame_count - 1, 1), self._on_trackbar)
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
        print(f"done. extracted {len(self.saved)} "
              f"(pos:{pos} neg:{len(self.saved) - pos}) -> {self.out_images.parent}")
        return 0
