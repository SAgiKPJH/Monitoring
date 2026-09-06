#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\13_pose_train
#   ..\.venv\Scripts\python.exe 1_pose_correct.py --src D:\carved-08\Cut --win 1020x660
#   창 크기 지정:  --win 1280x720   |  baby 게이트 끄기: --no-detect
#   (다음 단계: 2_build_data.py → 3_run_training.py)
#   → baby 감지(8) 되면 pose 모델 예측을 프리필하고, **틀린 keypoint 만 고쳐** dataset\ 저장.
#   키/편집은 folder 3 pose_label_tool 과 동일(그 UI 재사용).
# ─────────────────────────────────────────────────────────────
r"""pose 교정 라벨 툴 — baby 감지 후 pose 예측을 초기값으로 깔고 틀린 것만 수정.

folder 3 pose_label_tool(편집·저장·네비 UI)을 재사용한다. 프레임을 열 때 라벨이 없으면
① baby 감지(8 모델)가 있을 때만 ② pose 모델(best.pt, 없으면 사전학습 yolo11n-pose)로
keypoint 를 **프리필**한다. baby 감지 여부는 화면 우상단 배지로 표시(DETECTED/none/gate off).
사용자는 잘못 잡힌 점만 옮기고 저장 → 빠른 pose 데이터 확보.
저장은 13\dataset\ (YOLO-pose). 표시 창 크기는 --win 으로 지정.
"""
import argparse
import sys
from pathlib import Path

import cv2

_HERE = Path(__file__).resolve().parent
MEDIA = _HERE.parent
sys.path.insert(0, str(MEDIA / "3_detection_labeling_tool" / "pose_label_tool"))
sys.path.insert(0, str(MEDIA / "4_detection_pretrained"))

import pose_ui                        # noqa: E402  (render 래핑용)
import pose_view                      # noqa: E402  (창 크기 오버라이드 + put_text)
from pose_ui import PoseTool          # noqa: E402  (folder 3 편집 UI)
from pose_io import collect_videos    # noqa: E402
from pose_format import NUM_KPTS      # noqa: E402

DET_MODEL = str(MEDIA / "8_detection_2class_train" / "output" / "60" / "model.pth")
BABY_CLASS = 0                         # 8 모델: 0=baby, 1=baby_face
BABY_CONF = 0.8                        # baby 감지 임계
KP_CONF = 0.3                          # 이 conf 이상 keypoint 만 프리필(나머지는 미배치)


class PoseCorrectTool(PoseTool):
    """PoseTool + baby게이트 + pose 프리필 — 저장 라벨이 없으면 예측 keypoint 로 채운다."""

    def __init__(self, videos, out_dir, pose, det=None):
        super().__init__(videos, out_dir)
        self.pose, self.det = pose, det
        self.baby_seen = None                               # None=게이트 off, True/False=감지결과

    def _set_frame(self, idx, frame):
        super()._set_frame(idx, frame)
        self.baby_seen = None
        if self.frame is None:
            return
        if self.det is not None:                            # 프레임마다 baby 감지 판정(배지 표시용)
            self.baby_seen = self._detect_baby(frame)
        if (self.det is None or self.baby_seen) and all(k is None for k in self.kps):
            self.kps = self._predict_pose(frame)            # baby 있을 때만 pose 프리필

    def _detect_baby(self, frame):
        r = self.det.predict(frame, conf=BABY_CONF, verbose=False)[0]
        return any(int(b.cls) == BABY_CLASS and float(b.conf) >= BABY_CONF
                   for b in (r.boxes or []))

    def _predict_pose(self, frame):
        r = self.pose.predict(frame, conf=0.2, verbose=False)[0]
        if r.keypoints is None or len(r.keypoints) == 0:
            return [None] * NUM_KPTS
        xy = r.keypoints.xy[0].cpu().numpy()
        cf = r.keypoints.conf[0].cpu().numpy() if r.keypoints.conf is not None else None
        return [(int(xy[i][0]), int(xy[i][1]), 2) if (cf is None or cf[i] > KP_CONF) else None
                for i in range(NUM_KPTS)]


_orig_render = pose_ui.render


def _render_with_baby(tool):
    """folder 3 render 위에 baby 감지 배지(우상단)를 덧그린다."""
    disp = _orig_render(tool)
    seen = getattr(tool, "baby_seen", None)
    if seen is None:
        txt, col = "BABY: gate off", (180, 180, 180)
    elif seen:
        txt, col = "BABY: DETECTED", (80, 255, 80)          # 초록
    else:
        txt, col = "BABY: none (no pose)", (80, 80, 255)    # 빨강 — 프리필 안 함
    (tw, _), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    pose_view.put_text(disp, txt, (max(8, disp.shape[1] - tw - 12), 26),
                       scale=0.6, color=col, thick=2)
    return disp


pose_ui.render = _render_with_baby                          # run() 루프가 이 래퍼를 호출


def _winsize(s):
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception:
        raise argparse.ArgumentTypeError("창 크기 형식: 1280x720")


def main() -> int:
    ap = argparse.ArgumentParser(description="pose 교정 라벨(baby 감지→pose 예측 프리필 후 수정)")
    ap.add_argument("--src", default=r"D:\carved-08\Cut", help="클립 폴더 또는 mp4")
    ap.add_argument("--out", default=str(_HERE / "dataset"), help="저장 폴더(YOLO-pose)")
    ap.add_argument("--model", default="", help="pose 모델(기본: output\\train_colab_209\\weights\\best.pt, 없으면 사전학습)")
    ap.add_argument("--win", type=_winsize, default=(1600, 900), help="표시 창 최대 크기 WxH (기본 1600x900)")
    ap.add_argument("--no-detect", action="store_true", help="baby 감지 게이트 없이 모든 프레임 pose 프리필")
    args = ap.parse_args()

    pose_view.MAX_DISP_W, pose_view.MAX_DISP_H = args.win   # 표시 창 크기 반영

    model = args.model or str(_HERE / "output" / "train" / "weights" / "best.pt")
    if not Path(model).exists():
        model = "yolo11n-pose.pt"                            # 학습 전이면 사전학습으로 프리필(부트스트랩)
        print("학습 pose 모델 없음 → 사전학습 yolo11n-pose 로 프리필(부트스트랩)")
    videos = collect_videos(args.src)
    if not videos:
        print(f"[에러] 클립 없음: {args.src}")
        return 1
    try:
        from src.inference import load_detector, load_pose
    except ImportError:
        print("ultralytics/4_detection_pretrained 필요")
        return 1
    pose = load_pose(model)
    det = None
    if not args.no_detect and Path(DET_MODEL).exists():
        det = load_detector(DET_MODEL)                       # baby 감지(8) → 있으면 pose
    else:
        print("baby 감지 게이트 비활성 → 모든 프레임 pose 프리필")
    print(f"{len(videos)}클립 · baby감지→pose 프리필 후 교정 → {args.out}  "
          f"(pose:{Path(model).name}, 창:{args.win[0]}x{args.win[1]})")
    return PoseCorrectTool(videos, Path(args.out), pose, det).run()


if __name__ == "__main__":
    raise SystemExit(main())
