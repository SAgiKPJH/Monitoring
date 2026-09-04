"""stage4 — 해상도 축소 재인코딩 (Cut 원본 보존, 기본 480px).

Cut 의 각 mp4 를 가로 width 로 축소(세로 비율 자동, 짝수 보정). 오디오는 카피 유지.
exclude.txt 존중, 이미 있는 결과는 건너뜀(증분).
"""
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .ffmpeg_tools import find_ffmpeg
from .cache_util import load_exclude

FFMPEG = find_ffmpeg()


def resize_one(src, dst, width, crf, preset, seconds, no_audio=False):
    """가로 width 로 축소 재인코딩. 성공 시 None, 실패 시 메시지."""
    audio = ["-an"] if no_audio else ["-c:a", "copy"]
    cmd = [FFMPEG, "-nostdin", "-v", "error", "-y", "-i", str(src), "-t", str(seconds),
           "-vf", f"scale={width}:-2", "-c:v", "libx264", "-crf", str(crf),
           "-preset", preset, *audio, "-movflags", "+faststart", str(dst)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return "timeout"
    if p.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        err = (p.stderr or "").strip().splitlines()
        return err[-1][:200] if err else f"exit {p.returncode}"
    return None


def run(cut_dir, resized_dir, *, width=480, crf=28, preset="veryfast",
        seconds=8.0, workers=8, no_audio=False, exclude_path=None):
    src_dir, dst_dir = Path(cut_dir), Path(resized_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    excl = load_exclude(exclude_path or (dst_dir.parent / "exclude.txt"))
    files = [f for f in sorted(src_dir.glob("*.mp4")) if f.name not in excl]
    todo = [f for f in files if not (dst_dir / f.name).exists()]
    print(f"  전체 {len(files)}개 (제외 적용) / 이미 있음 {len(files) - len(todo)}개 / "
          f"남은 {len(todo)}개 → {dst_dir} (width={width}, crf={crf})")
    lock = threading.Lock()
    n, fails = 0, []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(resize_one, f, dst_dir / f.name, width, crf, preset,
                          seconds, no_audio): f for f in todo}
        for fut in as_completed(futs):
            err = fut.result()
            with lock:
                n += 1
                if err:
                    fails.append((futs[fut].name, err))
                if n % 500 == 0 or n == len(todo):
                    print(f"    {n}/{len(todo)} (실패 {len(fails)})")
    for f, err in fails[:10]:
        print(f"    [실패] {f}: {err}")
    print(f"  resize 완료 — 성공 {n - len(fails)} / 실패 {len(fails)}")
    return {"resized": n - len(fails), "failed": len(fails)}
