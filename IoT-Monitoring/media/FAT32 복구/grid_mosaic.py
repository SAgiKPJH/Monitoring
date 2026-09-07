#!/usr/bin/env python3
"""grid_mosaic.py — 다수의 작은 mp4 를 격자로 합쳐 모자이크 영상 생성

resized_2(240x136) 클립을 시간순으로 cols x rows 격자에 배치 (기본 20x20 = 400개/격자).
타일은 기본적으로 **원본 해상도 그대로** 붙이며 출력 크기 제한 없음
(240x136 x 20x20 → 4800x2720). 오디오는 전부 믹스, 짧은 클립은 마지막 프레임 유지.
각 클립에서 소리가 나는 구간(바닥 소음 대비 +8dB)에는 그 타일에 초록 테두리 표시.

  python grid_mosaic.py D:\\carved\\resized_2 D:\\carved\\grid                 # 20x20 → 61개
  python grid_mosaic.py D:\\carved\\resized_2 D:\\carved\\grid --tile-w 96 --tile-h 54   # 타일 축소 시

2단계 계층 합성(행 hstack → 열 vstack)을 **격자 하나씩 순차** 처리 (기본 workers=1,
BelowNormal 우선순위 — 다른 작업을 방해하지 않음. 빠르게: --workers 12 --priority normal).
출력은 임시 파일에 쓰고 패킷 수 검증 후 rename — 중단돼도 잘린 파일이 남지 않음.
소리 분석은 <dst>\\audio_activity.jsonl 에 캐시. 만들어진 grid_NNN.mp4 는 건너뜀(증분).
격자별 시간 범위는 <dst>\\grid_index.txt 에 기록.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def _ff(name: str) -> str:
    """ffmpeg 실행 파일 탐색: 이 폴더 → media 루트 → PATH"""
    for base in (SCRIPT_DIR, SCRIPT_DIR.parent):
        p = base / "ffmpeg" / "bin" / name
        if p.exists():
            return str(p)
    return name


FFMPEG = _ff("ffmpeg.exe")
FFPROBE = _ff("ffprobe.exe")

AUDIO_SR = 8000
AUDIO_WIN = 0.2          # RMS 창 (초)
AUDIO_DB_OVER = 8.0      # 바닥(p20) 대비 이 이상 크면 '소리 있음'
AUDIO_DB_MIN = -50.0     # 최소 절대 문턱 (dBFS)


def run_ff(cmd, timeout=600):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        err = (p.stderr or "").strip().splitlines()
        return err[-1][:300] if err else f"exit {p.returncode}"
    return None


def run_ff_verified(cmd, out_path: Path, min_packets: int, timeout=600):
    """임시 파일에 쓰고 비디오 패킷 수를 검증한 뒤에만 최종 이름으로 rename.
    중간에 죽어도 잘린 파일이 '완성'으로 남지 않음."""
    tmp = out_path.with_name(out_path.name + ".tmp.mp4")
    err = run_ff(cmd[:-1] + [str(tmp)], timeout=timeout)
    if err:
        tmp.unlink(missing_ok=True)
        return err
    p = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "v:0",
                        "-count_packets", "-show_entries", "stream=nb_read_packets",
                        "-of", "csv=p=0", str(tmp)],
                       capture_output=True, text=True, timeout=120)
    try:
        n = int(p.stdout.strip())
    except ValueError:
        n = -1
    if p.returncode != 0 or n < min_packets:
        tmp.unlink(missing_ok=True)
        return f"출력 검증 실패 (패킷 {n} < {min_packets})"
    os.replace(tmp, out_path)
    return None


def audio_intervals(path: Path, seconds: float):
    """소리 활동 구간 [(s,e),...] — 0.2초 RMS 가 파일 자체 바닥보다 +8dB 이상인 창"""
    import numpy as np
    cmd = [FFMPEG, "-nostdin", "-v", "error", "-i", str(path), "-t", str(seconds),
           "-vn", "-f", "s16le", "-ac", "1", "-ar", str(AUDIO_SR), "-"]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return []
    if p.returncode != 0 or len(p.stdout) < 2:
        return []
    x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    n = int(AUDIO_SR * AUDIO_WIN)
    m = len(x) // n
    if m == 0:
        return []
    rms = np.sqrt((x[: m * n].reshape(m, n) ** 2).mean(axis=1))
    db = 20 * np.log10(rms + 1e-6)
    thr = max(float(np.percentile(db, 20)) + AUDIO_DB_OVER, AUDIO_DB_MIN)
    ivs = []
    for i, on in enumerate(db > thr):
        if on:
            s, e = round(i * AUDIO_WIN, 2), round((i + 1) * AUDIO_WIN, 2)
            if ivs and s <= ivs[-1][1] + 1e-6:
                ivs[-1][1] = e
            else:
                ivs.append([s, e])
    return [(s, min(e, seconds)) for s, e in ivs]


def build_row(files, ivs_list, out_path, tile_w, tile_h, seconds, row_w, border):
    """클립들을 가로로 이어붙인 한 행 생성 + 오디오 믹스 + 소리 구간 초록 테두리"""
    n = len(files)
    cmd = [FFMPEG, "-nostdin", "-v", "error", "-y"]
    for f in files:
        cmd += ["-i", str(f)]
    fc = []
    for i in range(n):
        chain = (f"[{i}:v]scale={tile_w}:{tile_h},setsar=1,fps=15,format=yuv420p,"
                 f"tpad=stop_mode=clone:stop_duration={seconds},trim=0:{seconds}")
        if border and ivs_list[i]:
            en = "+".join(f"between(t,{s},{e})" for s, e in ivs_list[i])
            bt = max(2, tile_w // 80)
            chain += f",drawbox=x=0:y=0:w=iw:h=ih:color=lime:t={bt}:enable='{en}'"
        fc.append(chain + f"[v{i}]")
        fc.append(f"[{i}:a]apad=whole_dur={seconds},atrim=0:{seconds}[a{i}]")
    vins = "".join(f"[v{i}]" for i in range(n))
    if n > 1:
        fc.append(f"{vins}hstack=inputs={n},pad={row_w}:{tile_h}:0:0[rv]")
    else:
        fc.append(f"[v0]pad={row_w}:{tile_h}:0:0[rv]")
    ains = "".join(f"[a{i}]" for i in range(n))
    fc.append(f"{ains}amix=inputs={n}:duration=longest[ra]" if n > 1
              else "[a0]anull[ra]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[rv]", "-map", "[ra]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-c:a", "aac", "-b:a", "96k", "-t", str(seconds), str(out_path)]
    return run_ff_verified(cmd, out_path, min_packets=int(seconds * 15 * 0.8))


def build_grid(row_files, out_path, width, height, seconds, crf, guide_w=0, guide_h=0):
    """행들을 세로로 쌓아 최종 격자 생성 + 행 오디오 합산 (+N칸마다 푸른 안내선)"""
    n = len(row_files)
    cmd = [FFMPEG, "-nostdin", "-v", "error", "-y"]
    for f in row_files:
        cmd += ["-i", str(f)]
    fc = []
    vins = "".join(f"[{i}:v]" for i in range(n))
    center = f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    if guide_w and guide_h:
        center += f",drawgrid=w={guide_w}:h={guide_h}:t=3:color=dodgerblue@0.9"
    if n > 1:
        fc.append(f"{vins}vstack=inputs={n},{center}[gv]")
    else:
        fc.append(f"[0:v]{center}[gv]")
    ains = "".join(f"[{i}:a]" for i in range(n))
    fc.append((f"{ains}amix=inputs={n}:duration=longest:normalize=0," if n > 1
               else "[0:a]") + "alimiter=limit=0.97[ga]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[gv]", "-map", "[ga]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
            "-t", str(seconds), str(out_path)]
    return run_ff_verified(cmd, out_path, min_packets=int(seconds * 15 * 0.8),
                           timeout=1200)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="타일 mp4 폴더 (예: D:\\carved\\resized_2)")
    ap.add_argument("dst", help="격자 결과 폴더 (예: D:\\carved\\grid)")
    ap.add_argument("--cols", type=int, default=20)
    ap.add_argument("--rows", type=int, default=20)
    ap.add_argument("--tile-w", type=int, default=0, help="타일 가로 (0=원본 크기 유지)")
    ap.add_argument("--tile-h", type=int, default=0, help="타일 세로 (0=원본 크기 유지)")
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--crf", type=int, default=23)
    ap.add_argument("--workers", type=int, default=1,
                    help="한 격자 내부 행 병렬 수 (기본 1 = 완전 순차)")
    ap.add_argument("--priority", choices=["low", "normal"], default="low",
                    help="low(기본)=다른 작업에 CPU 양보")
    ap.add_argument("--limit", type=int, default=0, help="앞 N개 파일만 (시험용)")
    ap.add_argument("--no-border", action="store_true", help="소리 테두리 표시 끄기")
    ap.add_argument("--guide", type=int, default=5, help="N칸마다 푸른 안내선 (0=끄기)")
    ap.add_argument("--only-sound", action="store_true",
                    help="소리 감지된 클립만 모아서 격자 구성")
    ap.add_argument("--activity-cache", default="",
                    help="소리 분석 캐시 jsonl (기본 <dst>\\audio_activity.jsonl)")
    args = ap.parse_args()

    if args.priority == "low" and os.name == "nt":
        import ctypes  # BelowNormal — ffmpeg 자식들도 상속
        ctypes.windll.kernel32.SetPriorityClass(
            ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)

    src, dst = Path(args.src), Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)
    per_grid = args.cols * args.rows
    files = sorted(src.glob("*.mp4"))
    if args.limit:
        files = files[: args.limit]
    if not files:
        sys.exit(f"[grid] {src} 에 mp4 없음")
    # 타일 크기: 지정 없으면 첫 파일의 원본 해상도 (libx264 제약으로 짝수 내림)
    tile_w, tile_h = args.tile_w, args.tile_h
    if not tile_w or not tile_h:
        probe = subprocess.run(
            [FFPROBE, "-v", "error",
             "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0", str(files[0])],
            capture_output=True, text=True, timeout=30)
        w, h = (int(v) for v in probe.stdout.strip().split(","))
        tile_w, tile_h = tile_w or w, tile_h or h
    tile_w, tile_h = max(2, tile_w & ~1), max(2, tile_h & ~1)
    out_w, out_h = args.cols * tile_w, args.rows * tile_h

    # 소리 활동 분석 (캐시 증분, 병렬) — 격자 구성 전에 수행해 --only-sound 필터에 사용
    activity = {}
    act_path = Path(args.activity_cache) if args.activity_cache else dst / "audio_activity.jsonl"
    lock = threading.Lock()
    if not args.no_border or args.only_sound:
        if act_path.exists():
            with open(act_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                        activity[r["file"]] = [tuple(v) for v in r["iv"]]
                    except (json.JSONDecodeError, KeyError):
                        continue
        need = sorted((p for p in files if p.name not in activity), key=lambda p: p.name)
        if need:
            print(f"[grid] 소리 분석: 캐시 {len(activity)}개 / 남은 {len(need)}개", flush=True)
            n_done = 0
            with open(act_path, "a", encoding="utf-8") as out, \
                    ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(audio_intervals, p, args.seconds): p for p in need}
                for fut in as_completed(futs):
                    p = futs[fut]
                    iv = fut.result()
                    with lock:
                        activity[p.name] = iv
                        out.write(json.dumps({"file": p.name, "iv": iv}) + "\n")
                        n_done += 1
                        if n_done % 2000 == 0 or n_done == len(need):
                            print(f"[grid] 소리 분석 {n_done}/{len(need)}", flush=True)
    if args.only_sound:
        files = [p for p in files if activity.get(p.name)]
        print(f"[grid] 소리 있는 클립만: {len(files)}개", flush=True)
    grids = [files[i:i + per_grid] for i in range(0, len(files), per_grid)]
    todo = [(gi, chunk) for gi, chunk in enumerate(grids)
            if not (dst / f"grid_{gi + 1:03d}.mp4").exists()
            or (dst / f"grid_{gi + 1:03d}.mp4").stat().st_size == 0]
    print(f"[grid] 타일 {len(files)}개 → 격자 {len(grids)}개 "
          f"({args.cols}x{args.rows}, 타일 {tile_w}x{tile_h}px, 출력 {out_w}x{out_h}) / "
          f"이미 있음 {len(grids) - len(todo)}개 / 남은 {len(todo)}개 (workers={args.workers})",
          flush=True)

    with open(dst / "grid_index.txt", "w", encoding="utf-8") as f:
        f.write(f"# 격자당 {args.cols}x{args.rows}={per_grid}개, 시간순 배치 (좌→우, 위→아래)\n")
        f.write("# 초록 테두리 = 해당 클립에서 소리 감지 구간\n" if not args.no_border else "")
        for gi, chunk in enumerate(grids):
            f.write(f"grid_{gi + 1:03d}.mp4\t{len(chunk)}개\t"
                    f"{chunk[0].name}  ~  {chunk[-1].name}\n")

    fails = []

    # 격자 단위 순차 처리: 행 생성 → 조립 → 정리가 끝나야 다음 격자로 (한 개씩)
    n_ok = 0
    for k, (gi, chunk) in enumerate(todo, 1):
        rows_dir = dst / f".rows_{gi + 1:03d}"
        rows_dir.mkdir(exist_ok=True)
        jobs = []
        for ri in range(0, len(chunk), args.cols):
            row_files = chunk[ri:ri + args.cols]
            ivs = [activity.get(p.name, []) for p in row_files]
            jobs.append((rows_dir / f"row_{ri // args.cols:02d}.mp4", row_files, ivs))
        grid_fail = None
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(build_row, rf, ivs, rp, tile_w, tile_h, args.seconds,
                              args.cols * tile_w, not args.no_border): rp
                    for rp, rf, ivs in jobs}
            for fut in as_completed(futs):
                err = fut.result()
                if err and not grid_fail:
                    grid_fail = f"{futs[fut].name}: {err}"
        if not grid_fail:
            row_files = sorted(rows_dir.glob("row_*.mp4"))
            grid_fail = build_grid(row_files, dst / f"grid_{gi + 1:03d}.mp4",
                                   out_w, out_h, args.seconds, args.crf,
                                   guide_w=args.guide * tile_w if args.guide else 0,
                                   guide_h=args.guide * tile_h if args.guide else 0)
        if grid_fail:
            fails.append((f"grid_{gi + 1:03d}", grid_fail))
        else:
            n_ok += 1
            shutil.rmtree(rows_dir, ignore_errors=True)
        print(f"[grid] {k}/{len(todo)} grid_{gi + 1:03d} "
              f"{'완료' if not grid_fail else '실패'}", flush=True)

    for name, err in fails[:20]:
        print(f"  [실패] {name}: {err}")
    print(f"[grid] 완료 — 격자 성공 {n_ok} / 실패 {len(fails)} → {dst}", flush=True)
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
