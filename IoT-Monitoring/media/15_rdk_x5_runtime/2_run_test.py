#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 2단계 — 파이프라인 1회 실행 테스트 (PC·보드 공통, 알람 없음)
#   cd D:\Code\Monitoring\IoT-Monitoring\media\15_rdk_x5_runtime
#   ..\.venv\Scripts\python.exe 2_run_test.py                     # .env STREAM_URL 로 5프레임
#   ..\.venv\Scripts\python.exe 2_run_test.py --src D:\carved-08\Cut\xxx.mp4 --n 10
#   보드(BACKEND=bpu): python3 2_run_test.py   → NPU 단계별 추론 지연 + 모델별 메모리(MB, %) + BPU 사용률
#   다음: 3_gui_test.py(시각 확인) → monitoring.py(실제 운용)
# ─────────────────────────────────────────────────────────────
r"""모델 로드 → 소스 열기 → 프레임 N개로 움직임(YDIF)·baby/face 감지·얼굴상태·pose 이동량을
각각 1회씩 실행하고 **단계별 소요시간(ms)** 을 출력한다. monitoring.py 의 함수를 그대로 사용하므로
여기서 돌면 실제 운용도 돈다. 30초 관찰 판정·알람은 하지 않는다.

메모리: 모델별 파일 크기 + 로드 전후 프로세스 RSS 증가(MB) + 전체 RAM 대비 %. RDK X5 의 BPU 는
별도 VRAM 이 없고 ION/CMA 로 **시스템 RAM 을 공유**하므로 이 RSS 증가가 "NPU 에 잡는 메모리"에 해당한다
(/proc 기반 — Linux 만, PC(Windows) 는 n/a). BPU 사용률은 /sys/devices/system/bpu/bpu0/ratio 가 있을 때 표시.
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import monitoring as M  # noqa: E402  (.env·BACKEND·모델 경로·단계 함수 재사용)

BPU_RATIO = Path("/sys/devices/system/bpu/bpu0/ratio")   # RDK: BPU 사용률(%)


def _proc_kb(path, key):
    try:
        for line in open(path, encoding="utf-8"):
            if line.startswith(key):
                return int(line.split()[1])
    except OSError:
        pass
    return None


def _rss_mb():                  # 프로세스 상주 메모리(MB), Linux 만
    kb = _proc_kb("/proc/self/status", "VmRSS:")
    return kb / 1024 if kb is not None else None


def _memtotal_mb():
    kb = _proc_kb("/proc/meminfo", "MemTotal:")
    return kb / 1024 if kb is not None else None


def _bpu_ratio():
    try:
        return int(BPU_RATIO.read_text().strip())
    except (OSError, ValueError):
        return None


def timed(label, fn):
    t = time.perf_counter()
    r = fn()
    print(f"  {label:<13} {(time.perf_counter() - t) * 1000:8.1f} ms")
    return r


def _crop(frame, box):
    x1, y1, x2, y2 = (int(v) for v in box)
    return frame[max(0, y1):y2, max(0, x1):x2]


def main() -> int:
    ap = argparse.ArgumentParser(description="파이프라인 1회 실행 + 단계별 시간/메모리")
    ap.add_argument("--src", default=M.STREAM_URL, help="스트림 URL 또는 mp4")
    ap.add_argument("--n", type=int, default=5, help="처리할 프레임 수")
    ap.add_argument("--img", default="", help="정지 이미지(jpg 파일 또는 폴더)로 단계 실행 — 스트림 없이 모델만 검증(ref_frames/ 참고)")
    args = ap.parse_args()

    print(f"BACKEND={M.BACKEND} · models={M.MODELS}")
    M.load_backend()                                     # 백엔드 로더 바인딩(잘못된 BACKEND 면 안내 후 종료)
    for p in (M.DET_MODEL, M.FACE_MODEL):
        if not Path(p).exists():
            print(f"[에러] 모델 없음: {p}" + ("  ← 14_export_BPU 로 .bin 생성" if M._BPU else ""))
            return 1

    mem_total = _memtotal_mb()
    rows = []
    print("[모델 로드]  파일 크기 · 로드 전후 RSS 증가(=NPU 공유 RAM 점유)" + (f" · 전체 {mem_total:.0f} MB 대비 %" if mem_total else ""))

    def load(label, path, fn):
        r0, t = _rss_mb(), time.perf_counter()
        obj = fn()
        dt, r1 = (time.perf_counter() - t) * 1000, _rss_mb()
        d = (r1 - r0) if (r0 is not None and r1 is not None) else None
        size = Path(path).stat().st_size / 1048576
        rows.append((size, d))
        pct = f" ({d / mem_total * 100:.1f}%)" if (d is not None and mem_total) else ""
        print(f"  {label:<13} {dt:8.1f} ms · 파일 {size:5.1f} MB · RSS "
              + (f"+{d:.1f} MB{pct}" if d is not None else "n/a(Linux 만)"))
        return obj

    det = load("detector", M.DET_MODEL, lambda: M.load_detector(M.DET_MODEL))
    fmodel, fmeta = load("face_state", M.FACE_MODEL, lambda: M.load_face_state(M.FACE_MODEL))
    pose = load("pose", M.POSE_MODEL, lambda: M.load_pose(M.POSE_MODEL)) if Path(M.POSE_MODEL).exists() else None
    if pose is None:
        print("  (pose 모델 없음 — pose 단계 건너뜀)")
    tot_s = sum(s for s, _ in rows)
    ds = [d for _, d in rows if d is not None]
    line = f"  {'합계':<13} 파일 {tot_s:.1f} MB"
    if ds:
        tot_d = sum(ds)
        line += f" · RSS +{tot_d:.1f} MB" + (f" ({tot_d / mem_total * 100:.1f}% of {mem_total:.0f} MB)" if mem_total else "")
        line += f" · 프로세스 RSS {_rss_mb():.0f} MB"
    print(line)

    if args.img:                                          # ── 정지 이미지 모드: 스트림 없이 모델만 A/B 검증 ──
        import cv2
        p = Path(args.img)
        if not p.exists():
            print(f"[에러] 경로 없음: {p.resolve()}\n"
                  "  보드로 ref_frames 폴더를 통째로 복사했는지 확인:  scp -r ref_frames sunrise@<보드IP>:/home/sunrise/JJU/Monitoring/\n"
                  "  확인:  ls ref_frames  → jpg 3장 + ref_scores.txt")
            return 1
        files = sorted([*p.glob("*.jpg"), *p.glob("*.png")]) if p.is_dir() else [p]
        if not files:
            print(f"[에러] 폴더에 jpg/png 없음: {p.resolve()}")
            return 1
        print(f"\n[정지 이미지 {len(files)}장] 임계 전 최대점수 — PC 값(ref_frames/ref_scores.txt)과 비교")
        print(f"{'파일':32} {'det baby':>9} {'det face':>9} {'boxes':>6} {'pose max':>9}  face_state")
        for f in files:
            img = cv2.imread(str(f))
            if img is None:
                print(f"{f.name:32} 읽기 실패")
                continue
            baby, faces = M.has_baby(det, img)
            lm = getattr(det, "last_max", None)
            r = det.predict(img, conf=0.25, verbose=False)[0]
            nbox = len(r.boxes or [])
            if lm is None:                                    # torch 백엔드: 후보(≥0.25) 중 클래스별 최대 conf 로 대체
                best = {}
                for b in (r.boxes or []):
                    best[int(b.cls)] = max(best.get(int(b.cls), 0.0), float(b.conf))
                lm = [best.get(M.BABY_CLASS, 0.0), best.get(M.FACE_CLASS, 0.0)]
            pm = ""
            if pose is not None:
                pose.predict(img, conf=0.2, verbose=False)
                pm = f"{pose.last_max:9.3f}" if getattr(pose, "last_max", None) is not None else f"{'-':>9}"
            fs = ""
            if faces:
                st = M.predict(fmodel, fmeta, _crop(img, faces[0]))
                fs = " ".join(f"{a[:5]}:{pr:.2f}" for a, (pr, _) in st.items())
            dm = f"{lm[0]:9.3f} {lm[1] if len(lm) > 1 else 0:9.3f}" if lm is not None else f"{'-':>9} {'-':>9}"
            print(f"{f.name[:32]:32} {dm} {nbox:6d} {pm}  {fs}")
        print("\n판독: PC 값(0.6~0.9)과 비슷하면 보드 파이프라인 정상(=라이브에서 안 잡히면 장면/모델 한계),"
              " 0.0x 이면 보드 입력/런타임 문제(hobot_dnn 투입 형식).")
        return 0

    cap, how = M.open_source(args.src)
    if cap is None:
        print(f"[에러] 소스 열기 실패: {args.src} ({how})")
        return 1
    print(f"[소스] {how}")

    prev, memo = None, {}
    for i in range(args.n):
        frame = M.grab(cap)
        if frame is None:
            print("프레임 없음 — 종료")
            break
        print(f"\n[frame {i + 1}/{args.n}] {frame.shape[1]}x{frame.shape[0]}")
        g = timed("motion(ydif)", lambda: M.to_gray_small(frame, 320))
        if prev is not None:
            y = M.ydif(prev, g)
            print(f"    YDIF={y:.2f}  (thr {M.MOTION_THR}) → motion={y > M.MOTION_THR}")
        prev = g
        baby, faces = timed("detect", lambda: M.has_baby(det, frame))
        print(f"    baby={baby}  faces={len(faces)}  (conf≥{M.BABY_CONF}/{M.FACE_CONF})")
        lm = getattr(det, "last_max", None)                       # BPU: 임계 전 클래스별 최대 점수(진단)
        if lm is not None:
            print(f"    det 최대점수(임계 전) baby={lm[0]:.2f} face={lm[1] if len(lm) > 1 else 0:.2f}"
                  "   ← 0.1 미만이면 입력 형식/양자화 의심, 0.3~0.7 이면 conf 부족")
        if hasattr(cap, "age") and cap.age() is not None:
            print(f"    프레임 age {cap.age() * 1000:.0f} ms · 수신 {getattr(cap, 'rx_fps', 0):.1f} fps"
                  "   ← 수신 fps 가 카메라 fps 보다 낮으면 디코드가 못 따라감(지연 누적)")
        if faces:
            st = timed("face_state", lambda: M.predict(fmodel, fmeta, _crop(frame, faces[0])))
            print("    " + "  ".join(f"{a}:{p:.2f}{'*' if on else ''}" for a, (p, on) in st.items()) + "   (*=임계 초과)")
            print(f"    위험속성({'/'.join(M.FACE_ALARM_ATTRS)}) = {M.face_alarm_state(fmodel, fmeta, frame, faces)}")
        if pose is not None:
            mv = timed("pose", lambda: M.pose_moving(pose, frame, memo))
            print(f"    pose moving={mv}  (thr {M.POSE_MOVE_THR}, 첫 프레임은 기준만 저장)")
            if getattr(pose, "last_max", None) is not None:
                print(f"    pose 최대 conf(임계 전) {pose.last_max:.2f}")
        ratio = _bpu_ratio()
        if ratio is not None:
            print(f"    BPU 사용률 {ratio}%  (직전 추론 구간, {BPU_RATIO})")
    cap.release()
    rss = _rss_mb()
    if rss is not None:
        print(f"\n[메모리] 프로세스 RSS {rss:.0f} MB" + (f" = 전체 {mem_total:.0f} MB 의 {rss / mem_total * 100:.1f}%" if mem_total else ""))
    print("완료 — 알람은 보내지 않았습니다. 시각 확인은 3_gui_test.py, 실제 운용은 monitoring.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
