# -*- coding: utf-8 -*-
"""Interactive state machine and main loop for the 2-class image labeler.

Navigates a folder of images (not clips). Active class is toggled with 1/2 and
applies to newly drawn boxes; existing labels load automatically for re-editing.
"""

import random
import time

import cv2
import numpy as np

import labeler_io
from labeler_view import MAX_DISP_H, MAX_DISP_W, make_mouse_handler, render

WIN = "baby-2class-label-tool"
FLASH_SEC = 0.9


class LabelTool:
    def __init__(self, images, labels_dir):
        self.images = images
        self.labels_dir = labels_dir
        labels_dir.mkdir(parents=True, exist_ok=True)
        self.idx, self.image_path = 0, None
        self.frame, self.disp_base, self.scale = None, None, 1.0
        self.boxes, self.dragging = [], False        # boxes: (x1,y1,x2,y2,cls) original px
        self.drag_a = self.drag_b = None
        self.active_cls = 0                           # 0=baby, 1=baby_face
        self.flash_text, self.flash_until, self.flash_ok = "", 0.0, True
        self.saved = labeler_io.scan_existing(labels_dir)

    def stem(self):
        return self.image_path.stem if self.image_path else "-"

    def headline(self):
        return f"[{self.idx + 1}/{len(self.images)} IMG] {self.image_path.name}"

    def help_text(self):
        return ("1:baby 2:baby_face | n/p:image r:random | drag:box u:undo c:clear "
                "| SPACE/ENTER:save x:negative q/ESC:quit")

    def flash(self, text, ok=True):
        self.flash_text, self.flash_ok = text, ok
        self.flash_until = time.time() + FLASH_SEC
        print(f"[{self.stem()}] {text}")

    def load_image(self, idx):
        n = len(self.images)
        for _ in range(n):
            idx %= n
            path = self.images[idx]
            data = np.fromfile(str(path), dtype=np.uint8)      # unicode-path safe
            frame = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
            if frame is not None:
                self.idx, self.image_path = idx, path
                self._set_frame(frame)
                return True
            print(f"[skip] unreadable image: {path}")
            idx += 1
        return False

    def _set_frame(self, frame):
        self.frame = frame
        h, w = frame.shape[:2]
        self.scale = min(1.0, MAX_DISP_W / w, MAX_DISP_H / h)
        size = (int(w * self.scale), int(h * self.scale))
        self.disp_base = (cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
                          if self.scale < 1.0 else frame.copy())
        self.dragging, self.drag_a, self.drag_b = False, None, None
        self.boxes = labeler_io.load_label(self.labels_dir, self.stem(), w, h)

    def save(self, negative=False):
        if self.frame is None:
            return
        if negative and self.boxes:
            return self.flash("boxes exist - press c to clear before negative", ok=False)
        if not negative and not self.boxes:
            return self.flash("no box - drag one, or press x for negative", ok=False)
        h, w = self.frame.shape[:2]
        err = labeler_io.save_label(self.labels_dir, self.stem(), self.boxes, w, h)
        if err:
            return self.flash(err, ok=False)
        self.saved[self.stem()] = not negative
        n_face = sum(1 for b in self.boxes if b[4] == 1)
        self.flash("SAVED negative" if negative
                   else f"SAVED {len(self.boxes)} box(es) (face:{n_face})")

    def _handle_key(self, key):
        if key == ord("n"):
            self.load_image(self.idx + 1)
        elif key == ord("p"):
            self.load_image(self.idx - 1)
        elif key == ord("r") and len(self.images) > 1:
            j = self.idx
            while j == self.idx:
                j = random.randrange(len(self.images))
            self.load_image(j)
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
        if not self.load_image(0):
            print("[ERROR] no readable image in the source.")
            cv2.destroyAllWindows()
            return 1
        while True:
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
        cv2.destroyAllWindows()
        pos = sum(1 for v in self.saved.values() if v)
        print(f"done. labels total {len(self.saved)} "
              f"(pos:{pos} neg:{len(self.saved) - pos}) -> {self.labels_dir}")
        return 0
