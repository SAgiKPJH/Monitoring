"""실시간/샘플 추론 실행 로직 — 각 Detection_*_Test.py 는 config 만 넘겨 호출.

4_detection_pretrained(사전학습)·6_detection_trained_inference(파인튜닝)가 이 모듈을 공유한다.
(5 는 자체 src 없이 sys.path 로 이 폴더 src 를 재사용 — 복붙 없음)
"""
import random
from pathlib import Path

import cv2

from . import stream_source, inference, live_view, shot


def run_live(argv, *, stream_url, det_model, pose_model, det_classes=None,
             scale=0.5, conf=0.20, mode="live", shot_frames=20):
    """go2rtc 실시간 스트림 → 감지+포즈 (창 또는 shot). argv 로 mode/frames 오버라이드."""
    args = [a.lower() for a in argv]
    m = args[0] if args and args[0] in ("live", "shot") else mode
    frames = next((int(a) for a in args if a.isdigit()), shot_frames)
    print(f"det  = {det_model}\npose = {pose_model}\nurl  = {stream_url} (scale {scale})")
    det, pose = inference.load_detector(det_model), inference.load_pose(pose_model)
    cap, how = stream_source.open_source(stream_url)
    if cap is None:
        print(f"[에러] 스트림 열기 실패: {stream_url}\n  go2rtc 확인: http://<호스트>:1984/streams")
        return 1
    if m == "shot":
        shot.run(cap, how, det, pose, scale=scale, conf=conf, classes=det_classes, frames=frames)
    else:
        live_view.run(cap, how, det, pose, scale=scale, conf=conf, classes=det_classes)
    return 0


def run_sample(argv, *, src_dir, det_model, pose_model, det_classes=None,
               conf=0.20, n_samples=5, out_dir="out_sample"):
    """이미지 폴더에서 N개 랜덤 → 감지+포즈 추론 → out_dir 저장."""
    n = next((int(a) for a in argv if a.isdigit()), n_samples)
    imgs = sorted(Path(src_dir).glob("*.jpg"))
    if not imgs:
        print(f"[에러] 이미지 없음: {src_dir}")
        return 1
    sample = random.sample(imgs, min(n, len(imgs)))
    print(f"det = {det_model}\n이미지 {len(imgs)}개 중 {len(sample)}개 랜덤 추론\n")
    det, pose = inference.load_detector(det_model), inference.load_pose(pose_model)
    out = Path(out_dir)
    out.mkdir(exist_ok=True)
    hit = 0
    for i, ip in enumerate(sample, 1):
        frame = cv2.imread(str(ip))
        if frame is None:
            print(f"  {i}/{len(sample)} {ip.name}: 읽기 실패")
            continue
        det_r, pose_r = inference.infer(det, pose, frame, conf, det_classes)
        n_det = inference.draw(frame, det_r, pose_r)
        top = (float(det_r.boxes.conf.max())
               if det_r is not None and det_r.boxes is not None and len(det_r.boxes) else 0.0)
        hit += n_det > 0
        cv2.imwrite(str(out / f"sample_{i:02d}_{ip.stem}.jpg"), frame)
        print(f"  {i}/{len(sample)} {ip.name}: det {n_det} (최고 {top:.2f})")
    print(f"\n완료 — {len(sample)}장 중 {hit}장 검출 · 결과: {out.resolve()}")
    return 0
