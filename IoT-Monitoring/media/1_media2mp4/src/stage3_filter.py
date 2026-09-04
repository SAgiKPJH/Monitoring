"""stage3 — N초 컷 → Cut (전체 클립, 무손실 스트림 카피).

Convert 의 모든 클립을 비디오·오디오 N초에서 잘라 Cut 으로 (재인코딩 없음).
정적 영상 제거는 하지 않음 — 그건 마지막 prune 단계가 담당(scan 결과 기준).
exclude.txt(직접 지운 파일)는 건너뜀. 이미 있는 결과도 건너뜀(증분).
"""
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .ffmpeg_tools import find_ffmpeg
from .cache_util import load_exclude

FFMPEG = find_ffmpeg()


def export_one(src, dst, seconds, no_audio=False):
    """N초 컷 (비디오·오디오 모두), 무손실 카피. 성공 시 None, 실패 시 메시지."""
    audio = ["-map", "0:v:0", "-an"] if no_audio else []
    cmd = [FFMPEG, "-nostdin", "-v", "error", "-y", "-i", str(src), "-t", str(seconds),
           *audio, "-c", "copy", "-movflags", "+faststart", str(dst)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return "timeout"
    if p.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        err = (p.stderr or "").strip().splitlines()
        return err[-1][:200] if err else f"exit {p.returncode}"
    return None


def run(convert_dir, cut_dir, *, seconds=8.0, workers=8,
        no_audio=False, exclude_path=None):
    src_dir, dst_dir = Path(convert_dir), Path(cut_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    excl = load_exclude(exclude_path or (dst_dir.parent / "exclude.txt"))
    files = [f.name for f in sorted(src_dir.glob("*.mp4")) if f.name not in excl]
    todo = [f for f in files if not (dst_dir / f).exists()]
    print(f"  전체 {len(files)}개 (제외 {len(excl)}) / 이미 있음 "
          f"{len(files) - len(todo)}개 / 남은 {len(todo)}개 → {dst_dir}")
    lock = threading.Lock()
    n, fails = 0, []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(export_one, src_dir / f, dst_dir / f, seconds, no_audio): f
                for f in todo}
        for fut in as_completed(futs):
            err = fut.result()
            with lock:
                n += 1
                if err:
                    fails.append((futs[fut], err))
                if n % 1000 == 0 or n == len(todo):
                    print(f"    {n}/{len(todo)} (실패 {len(fails)})")
    for f, err in fails[:10]:
        print(f"    [실패] {f}: {err}")
    print(f"  Cut 완료 — 성공 {n - len(fails)} / 실패 {len(fails)}")
    return {"exported": n - len(fails), "failed": len(fails)}
