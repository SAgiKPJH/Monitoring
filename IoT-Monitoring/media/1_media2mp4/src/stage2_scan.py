"""stage2 — 변화량(YDIF) 스캔 + 분포 리포트.

각 mp4 의 처음 N초를 160px 그레이로 축소해 인접 프레임 평균 휘도 차(YDIF)를 계산.
결과는 JSONL 캐시에 증분 저장(중단해도 이어서). 끝에 MOTION/STATIC 분포와 txt 리포트.
"""
import json
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .ffmpeg_tools import find_ffmpeg
from .cache_util import load_cache, classify

FFMPEG = find_ffmpeg()
YDIF_RE = re.compile(r"lavfi\.signalstats\.YDIF=([0-9.eE+-]+)")
MOVING_FRAME_YDIF = 1.0
MIN_FRAMES = 10


def score_one(path, seconds, hwaccel=""):
    """한 파일의 YDIF 통계 dict."""
    hw = ["-hwaccel", hwaccel] if hwaccel else ["-threads", "1"]
    cmd = [FFMPEG, "-nostdin", "-v", "error", *hw, "-i", str(path), "-t", str(seconds),
           "-vf", "scale=160:-2,format=gray,signalstats,"
                  "metadata=print:key=lavfi.signalstats.YDIF:file=-",
           "-an", "-f", "null", "-"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {"file": path.name, "status": "error", "error": "timeout"}
    vals = [float(m) for m in YDIF_RE.findall(p.stdout)][1:]   # 첫 프레임 제외
    if len(vals) < MIN_FRAMES:
        return {"file": path.name, "status": "error", "frames": len(vals), "error": "no frames"}
    s, n = sorted(vals), len(vals)
    return {"file": path.name, "status": "ok" if p.returncode == 0 else "ok_partial",
            "frames": n, "mean": round(sum(vals) / n, 4), "max": round(s[-1], 4),
            "p95": round(s[min(n - 1, int(n * 0.95))], 4),
            "moving": round(sum(1 for v in vals if v > MOVING_FRAME_YDIF) / n, 4)}


def _report(recs, thresh_mean, thresh_max, txt_path):
    counts = {"STATIC": 0, "MOTION": 0, "ERROR": 0}
    lines = []
    for r in sorted(recs, key=lambda r: r["file"]):
        c = classify(r, thresh_mean, thresh_max)
        counts[c] += 1
        if c == "ERROR":
            lines.append(f"{r['file']}\t-\t-\t-\t-\tERROR")
        else:
            lines.append(f"{r['file']}\t{r['mean']:.4f}\t{r['max']:.4f}"
                         f"\t{r['p95']:.4f}\t{r['moving'] * 100:.1f}\t{c}")
    head = (f"# 총 {len(recs)}개: MOTION {counts['MOTION']} / "
            f"STATIC {counts['STATIC']} / ERROR {counts['ERROR']} "
            f"(STATIC=mean<{thresh_mean} AND max<{thresh_max})")
    if txt_path:
        Path(txt_path).parent.mkdir(parents=True, exist_ok=True)
        Path(txt_path).write_text(head + "\n# file\tmean\tmax\tp95\tmoving%\tclass\n"
                                  + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {head}")
    return counts


def run(convert_dir, cache_path, *, seconds=8.0, workers=8, hwaccel="",
        thresh_mean=0.12, thresh_max=2.0, txt_path=None):
    files = sorted(Path(convert_dir).glob("*.mp4"))
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    done = load_cache(cache_path)
    todo = [f for f in files if f.name not in done]
    print(f"  전체 {len(files)}개 / 캐시 {len(files) - len(todo)}개 / 스캔 {len(todo)}개")
    if todo:
        lock = threading.Lock()
        n = 0
        with open(cache_path, "a", encoding="utf-8") as out, \
                ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(score_one, f, seconds, hwaccel): f for f in todo}
            for fut in as_completed(futs):
                rec = fut.result()
                with lock:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    out.flush()
                    n += 1
                    if n % 500 == 0 or n == len(todo):
                        print(f"    {n}/{len(todo)}")
    counts = _report(list(load_cache(cache_path).values()), thresh_mean, thresh_max, txt_path)
    return {"scanned": len(todo), **counts}
