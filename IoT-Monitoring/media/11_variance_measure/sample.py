#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\11_variance_measure
#   ..\.venv\Scripts\python.exe sample.py --n 300      # 랜덤 300클립 분포
#   ..\.venv\Scripts\python.exe sample.py --n 0        # 전체
# ─────────────────────────────────────────────────────────────
r"""11_variance_measure/sample.py — 샘플 클립들의 변화량(YDIF) 분포로 threshold 찾기.

각 클립 앞 SECONDS 초의 meanYDIF·maxYDIF 를 구해, 클립 간 분포(퍼센타일·히스토그램)를 보여준다.
"하위 몇 %를 STATIC 으로 볼지" 정하면 그 퍼센타일이 곧 임계 후보다. 리포트는 out\ydif_sample.csv.
"""
import argparse
import csv
import random
from pathlib import Path

import numpy as np

from variance import clip_ydifs, percentiles, summarize

DEFAULT_SRCS = [r"D:\carved-08\Cut", r"D:\carved\Cut"]
IGNORE_RECT = (0.0, 0.0, 0.30, 0.10)   # 계산 제외 영역 비율(x1,y1,x2,y2) — 좌상단 타임스탬프. None=없음


def _hist(values, bins=10, width=40):
    if not values:
        return ""
    arr = np.asarray(values, dtype=np.float64)
    lo, hi = float(arr.min()), float(arr.max())
    if hi <= lo:
        hi = lo + 1e-6
    counts, edges = np.histogram(arr, bins=bins, range=(lo, hi))
    mx = max(int(counts.max()), 1)
    return "\n".join(f"  {e0:7.3f}~{e1:7.3f} | {'#' * int(c / mx * width)} {c}"
                     for c, e0, e1 in zip(counts, edges[:-1], edges[1:]))


def main():
    ap = argparse.ArgumentParser(description="샘플 클립 변화량 분포 → threshold 찾기")
    ap.add_argument("--src", default=next((s for s in DEFAULT_SRCS if Path(s).is_dir()), DEFAULT_SRCS[0]))
    ap.add_argument("--n", type=int, default=300, help="측정 클립 수 (0=전체)")
    ap.add_argument("--interval", type=float, default=1.0, help="비교 간격(초): 1, 5 등 (0=매 프레임)")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--width", type=int, default=320, help="변화량 계산 resize 폭")
    ap.add_argument("--height", type=int, default=0, help="resize 높이(0=비율유지)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    clips = sorted(Path(args.src).glob("*.mp4"))
    if not clips:
        print(f"[에러] 클립 없음: {args.src}")
        return 1
    random.seed(args.seed)
    random.shuffle(clips)
    if args.n > 0:
        clips = clips[: args.n]
    print(f"src={args.src}\n{len(clips)}개 클립 변화량 측정 ({args.interval:.0f}초 간격 비교, "
          f"앞 {args.seconds:.0f}초, resize {args.width}x{args.height or 'auto'})")

    means, maxes, rows = [], [], []
    for i, c in enumerate(clips, 1):
        m, mx = summarize(clip_ydifs(c, interval=args.interval, seconds=args.seconds,
                                     width=args.width, height=args.height, ignore=IGNORE_RECT))
        means.append(m)
        maxes.append(mx)
        rows.append([c.name, round(m, 3), round(mx, 3)])
        if i % 50 == 0:
            print(f"  {i}/{len(clips)}")

    out = Path(__file__).resolve().parent / "out"
    out.mkdir(exist_ok=True)
    with open(out / "ydif_sample.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file", "meanYDIF", "maxYDIF"])
        w.writerows(rows)

    pm, px = percentiles(means), percentiles(maxes)
    print("\n=== meanYDIF 분포 (클립별 평균 변화량, 0~255) ===")
    print("  " + "  ".join(f"p{k}:{v:.3f}" for k, v in pm.items()))
    print(_hist(means))
    print("\n=== maxYDIF 분포 (클립별 최대 순간 변화량) ===")
    print("  " + "  ".join(f"p{k}:{v:.3f}" for k, v in px.items()))
    print(_hist(maxes))
    print(f"\n리포트: {out / 'ydif_sample.csv'}")
    print("threshold: 하위 X% 를 STATIC 으로 보고 싶으면 meanYDIF·maxYDIF 의 pX 근처를 임계로.")
    print(f"  예) 하위 50% STATIC → mean_th≈{pm[50]:.3f}, max_th≈{px[50]:.3f}"
          f"  ·  하위 25% → mean_th≈{pm[25]:.3f}, max_th≈{px[25]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
