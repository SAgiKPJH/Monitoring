#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\13_pose_train
#   ..\.venv\Scripts\python.exe 4_Pose_Sample_Test.py --src D:\carved-08\Cut
#   n/p: 이전/다음 클립  ·  a/d: -+1프레임  ·  w/s: -+1초  ·  트랙바: 프레임 이동
#   r: 랜덤 클립  ·  SPACE: 현재 오버레이 저장(out_sample\)  ·  q/ESC: 종료  ·  창 크기: --win 1280x800
# ─────────────────────────────────────────────────────────────
r"""학습한 baby pose 모델로 **영상(클립)** 을 프레임 넘겨보며 골격 오버레이 확인.

1_pose_correct(라벨)·folder 3(라벨러)와 같은 클립 네비게이션을 재사용(복붙 없음).
추론·오버레이는 ..\4_detection_pretrained\src. 프레임이 바뀔 때만 재추론(폴링 루프).
"""
import argparse
import os
import random
import sys
from pathlib import Path

import cv2

_HERE = os.path.dirname(os.path.abspath(__file__))
_MEDIA = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_MEDIA, "3_detection_labeling_tool", "pose_label_tool"))
sys.path.insert(0, os.path.join(_MEDIA, "4_detection_pretrained"))

# ══════════════════════ 설정 ══════════════════════
SRC = r"D:\carved-08\Cut"                                                   # 클립 폴더 또는 mp4
POSE_MODEL = os.path.join(_HERE, "output", "train2", "weights", "best.pt")   # 학습 pose 모델
CONF = 0.20
WIN = "pose-sample-test"
MAX_W, MAX_H = 1280, 800                                                    # 표시 창 최대 크기
# ═══════════════════════════════════════════════════

from pose_io import collect_videos, open_video  # noqa: E402  (folder 3 클립 네비)
from src.inference import draw, load_pose        # noqa: E402  (folder 4 추론/오버레이)


def _put(img, s, org, color=(255, 255, 255), scale=0.6, thick=2):
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 2, cv2.LINE_AA)
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def _fit(frame):
    h, w = frame.shape[:2]
    s = min(1.0, MAX_W / w, MAX_H / h)
    return cv2.resize(frame, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA) if s < 1.0 else frame


def _winsize(s):
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise argparse.ArgumentTypeError("창 크기 형식: 1280x800")


class PoseViewer:
    def __init__(self, videos, pose):
        self.videos, self.pose = videos, pose
        self.cap, self.vidx, self.fidx, self.count, self.fps = None, 0, 0, 0, 15.0
        self.frame, self.full = None, None
        self.dirty, self.guard, self.tb_ready, self.pending = True, False, False, None

    def open(self, idx, step=1):
        opened = open_video(self.videos, idx, step)
        if opened is None:
            return False
        if self.cap is not None:
            self.cap.release()
        self.vidx, self.cap, frame, self.count, self.fps = opened
        self._set(0, frame)
        self._synctb()
        return True

    def seek(self, idx):
        idx = max(0, min(idx, self.count - 1))
        if idx == self.fidx and self.frame is not None:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = self.cap.read()
        if ok and frame is not None:
            self._set(idx, frame)
        self._synctb()

    def _set(self, idx, frame):
        self.fidx, self.frame, self.dirty = idx, frame, True

    def _synctb(self):
        if not self.tb_ready:
            return
        self.guard = True
        try:
            cv2.setTrackbarMax("frame", WIN, max(self.count - 1, 1))
        except AttributeError:
            pass
        cv2.setTrackbarPos("frame", WIN, self.fidx)
        self.guard = False

    def render(self):
        if not self.dirty or self.frame is None:
            return
        self.dirty = False
        f = self.frame.copy()
        pose_r = self.pose.predict(f, conf=CONF, verbose=False)[0]
        draw(f, None, pose_r)                                    # det 없이 pose 골격만
        n = len(pose_r.keypoints) if pose_r.keypoints is not None else 0
        _put(f, f"[{self.vidx + 1}/{len(self.videos)}] {self.videos[self.vidx].name}  "
                f"f{self.fidx + 1}/{self.count}  pose:{n}", (8, 26))
        _put(f, "n/p:clip  a/d:frame  w/s:1s  r:random  SPACE:save  q:quit",
             (8, f.shape[0] - 12), scale=0.5, thick=1)
        self.full = f


def main() -> int:
    global MAX_W, MAX_H
    ap = argparse.ArgumentParser(description="pose 학습 모델 인터랙티브 추론 뷰어(클립)")
    ap.add_argument("--src", default=SRC, help="클립 폴더 또는 mp4")
    ap.add_argument("--model", default=POSE_MODEL, help="pose 모델(.pt)")
    ap.add_argument("--win", type=_winsize, default=(MAX_W, MAX_H), help="표시 창 최대 크기 WxH")
    args = ap.parse_args()
    MAX_W, MAX_H = args.win

    if not Path(args.model).exists():
        print(f"[에러] pose 모델 없음: {args.model}\n먼저 3_run_training.py 로 학습하세요.")
        return 1
    videos = collect_videos(args.src)
    if not videos:
        print(f"[에러] 클립 없음: {args.src}")
        return 1
    pose = load_pose(args.model)
    out = Path(_HERE) / "out_sample"

    cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)
    v = PoseViewer(videos, pose)
    if not v.open(0, 1):
        print("[에러] 읽을 수 있는 클립 없음")
        cv2.destroyAllWindows()
        return 1
    cv2.createTrackbar("frame", WIN, 0, max(v.count - 1, 1),
                       lambda p: None if v.guard else setattr(v, "pending", p))
    v.tb_ready = True
    v._synctb()

    while True:
        if v.pending is not None:
            p, v.pending = v.pending, None
            v.seek(p)
        v.render()
        if v.full is not None:
            cv2.imshow(WIN, _fit(v.full))
        key = cv2.waitKey(30) & 0xFF
        if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
            break
        if key in (ord("q"), 27):
            break
        elif key == ord("n"):
            v.open(v.vidx + 1, 1)
        elif key == ord("p"):
            v.open(v.vidx - 1, -1)
        elif key == ord("d"):
            v.seek(v.fidx + 1)
        elif key == ord("a"):
            v.seek(v.fidx - 1)
        elif key == ord("w"):
            v.seek(v.fidx + int(round(v.fps)))
        elif key == ord("s"):
            v.seek(v.fidx - int(round(v.fps)))
        elif key == ord("r") and len(videos) > 1:
            j = v.vidx
            while j == v.vidx:
                j = random.randrange(len(videos))
            v.open(j, 1)
        elif key in (32, 13) and v.full is not None:            # SPACE/ENTER: 저장
            out.mkdir(exist_ok=True)
            dst = out / f"pose_{videos[v.vidx].stem}_f{v.fidx:04d}.jpg"
            cv2.imwrite(str(dst), v.full)
            print(f"  저장: {dst}")
    if v.cap is not None:
        v.cap.release()
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
