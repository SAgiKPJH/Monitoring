#!/usr/bin/env python3

# 실행
# cd D:\Code\Monitoring\IoT-Monitoring\media
#.\.venv\Scripts\python.exe Convert.py

r"""
Convert.py — .media → mp4 데이터셋 파이프라인 (단계별 오케스트레이터)

아래 [입력/출력 폴더] 와 [단계 ON/OFF] 만 고치고 실행하세요:

    python Convert.py                 # 아래 RUN 에서 켠 단계를 순서대로 실행
    python Convert.py convert scan    # 인자로 특정 단계만 실행 (RUN 무시)

각 단계 구현은 src/ 안에 있고, 여기서는 하나씩 호출만 합니다:
    1 convert : .media → mp4                        (src/stage1_convert.py)
    2 filter  : 8초 컷 (전체, 무손실) → Cut          (src/stage3_filter.py)
    3 resize  : 해상도 축소 → resized                (src/stage4_resize.py)
    4 scan    : 변화량(YDIF) 스캔 (resized 기준·빠름)  (src/stage2_scan.py)
    5 prune   : 낮은 변화량 제거 (Cut·resized 에서 STATIC 삭제)  (src/stage5_prune.py)
    6 drop_convert : (선택) Convert 삭제·Cut 유지 — 완료 후 한 번만
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ══════════════════════ 입력 / 출력 폴더 ══════════════════════
INPUT_DIR = r"D:\carved-08"                        # ① .media 원본 (하위 재귀 탐색)
WORK_DIR  = INPUT_DIR                               # 산출물 루트 (기본: 입력 폴더 안)
#   └ 데이터셋 바꿀 때 위 두 줄만 고치면 아래는 자동으로 따라갑니다.

CONVERT_DIR = WORK_DIR + r"\Convert"               # ① 변환된 mp4
CUT_DIR     = WORK_DIR + r"\Cut"                    # ③ 정적 제거 + 8초 컷 결과
RESIZED_DIR = WORK_DIR + r"\resized"               # ④ 해상도 축소본
CACHE_PATH  = WORK_DIR + r"\motion_cache.jsonl"     # 변화량 스캔 캐시 (증분)
REPORT_TXT  = WORK_DIR + r"\motion_scores.txt"      # 변화량 리포트
EXCLUDE_TXT = WORK_DIR + r"\exclude.txt"            # 제외 목록 (직접 지운 파일)

# ══════════════════════ 단계 ON / OFF ══════════════════════
RUN = {"convert": True, "filter": True, "resize": True, "scan": True,
       "prune": True, "drop_convert": False}
#   drop_convert 는 완료 후 수동으로만: python Convert.py drop_convert
#   (자동으로 켜면 재실행 때 Convert 가 없어 전량 재변환됨)

# ══════════════════════ 파라미터 ══════════════════════
TIME_OFFSET = -9.0     # .media 내장시각(UTC) 보정 시간 (이 카메라는 -9)
SECONDS     = 8.0      # 컷 길이 / 변화량 스캔 구간
THRESH_MEAN = 0.12     # STATIC 판정: meanYDIF 가 이 값 미만이고
THRESH_MAX  = 2.0      #             maxYDIF 가 이 값 미만이면 정적(제거)
WIDTH       = 480      # ④ 축소 가로 픽셀 (세로 비율 자동)
CRF         = 28       # ④ 화질 (낮을수록 좋고 큼, 18~30)
NO_AUDIO    = False    # True 면 오디오 제외
WORKERS     = min(16, os.cpu_count() or 8)
# ═════════════════════════════════════════════════════════════

import shutil  # noqa: E402
from src import (stage1_convert, stage2_scan, stage3_filter,  # noqa: E402
                 stage4_resize, stage5_prune)


def _banner(num, name, desc):
    print(f"\n{'=' * 62}\n [{num}] {name:<12} {desc}\n{'=' * 62}", flush=True)


def main():
    picked = {a.lower() for a in sys.argv[1:]}          # 인자 주면 그 단계만
    run = {k: (k in picked if picked else RUN[k]) for k in RUN}
    t0 = time.time()

    if run["convert"]:
        _banner(1, "convert", f"{INPUT_DIR} → {CONVERT_DIR}")
        stage1_convert.run(INPUT_DIR, CONVERT_DIR, time_offset=TIME_OFFSET,
                           no_audio=NO_AUDIO, workers=WORKERS)

    if run["filter"]:
        _banner(2, "filter", f"{SECONDS:.0f}초 컷 (전체) → {CUT_DIR}")
        stage3_filter.run(CONVERT_DIR, CUT_DIR, seconds=SECONDS, workers=WORKERS,
                          no_audio=NO_AUDIO, exclude_path=EXCLUDE_TXT)

    if run["resize"]:
        _banner(3, "resize", f"{WIDTH}px 축소 → {RESIZED_DIR}")
        stage4_resize.run(CUT_DIR, RESIZED_DIR, width=WIDTH, crf=CRF, seconds=SECONDS,
                          workers=WORKERS, no_audio=NO_AUDIO, exclude_path=EXCLUDE_TXT)

    if run["scan"]:
        _banner(4, "scan", f"변화량(YDIF) 스캔 (resized 기준) + 리포트")
        stage2_scan.run(RESIZED_DIR, CACHE_PATH, seconds=SECONDS, workers=WORKERS,
                        thresh_mean=THRESH_MEAN, thresh_max=THRESH_MAX, txt_path=REPORT_TXT)

    if run["prune"]:
        _banner(5, "prune", f"낮은 변화량 제거 (Cut·resized 에서 STATIC 삭제)")
        stage5_prune.run(CUT_DIR, RESIZED_DIR, CACHE_PATH,
                         thresh_mean=THRESH_MEAN, thresh_max=THRESH_MAX)

    if run["drop_convert"]:
        _banner(6, "drop_convert", f"Convert 삭제 (Cut 유지): {CONVERT_DIR}")
        if os.path.isdir(CONVERT_DIR):
            shutil.rmtree(CONVERT_DIR)
            print(f"  Convert 삭제 완료 — .media 원본으로 언제든 재변환 가능")
        else:
            print("  Convert 폴더 없음 (이미 삭제됨)")

    print(f"\n[완료] 총 {time.time() - t0:.0f}초")


if __name__ == "__main__":
    main()
