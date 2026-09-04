"""stage1 — .media → mp4 (H.264 비디오 + PCM 오디오 먹싱, 내장 시각으로 이름).

폴더 하위를 재귀 탐색해 모든 *.media 를 mp4 로 변환. 이미 변환된 것은 건너뜀(증분).
결과 이름: <out>/YYYY-MM-DD_HH-MM-SS.mp4 (같은 초는 _1, _2 접미사).
"""
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from . import media_format as mf
from .ffmpeg_tools import find_ffmpeg

FFMPEG = find_ffmpeg()
MEDIA_EXT = ".media"


def _out_name(dt, index=None):
    base = dt.strftime("%Y-%m-%d_%H-%M-%S")
    return base + (".mp4" if index is None else f"_{index}.mp4")


def _convert_one(src, dst, no_audio):
    """.media 한 개 → mp4. (성공여부, 메시지)."""
    with open(src, "rb") as f:
        video, audio, info = mf.demux(f.read())
    if not video:
        return False, "비디오 청크 없음 (포맷 불일치/손상)"
    fps = info["fps"] if info["fps"] > 0.5 else 10.0
    tmp_v, tmp_a = dst + ".h264.tmp", dst + ".pcm.tmp"
    try:
        with open(tmp_v, "wb") as f:
            f.write(video)
        cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
               "-framerate", f"{fps:.4f}", "-i", tmp_v]
        if audio and not no_audio:
            with open(tmp_a, "wb") as f:
                f.write(audio)
            cmd += ["-f", "s16le", "-ar", str(mf.AUDIO_RATE), "-ac", str(mf.AUDIO_CHANNELS),
                    "-i", tmp_a, "-c:a", "aac", "-b:a", "64k"]
        cmd += ["-c:v", "copy", "-movflags", "+faststart", dst]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
            return False, (r.stderr or "").strip()[:200] or "ffmpeg 실패"
    finally:
        for t in (tmp_v, tmp_a):
            if os.path.exists(t):
                os.remove(t)
    return True, f"{info['video_frames']}프레임 {fps:.1f}fps"


def _collect(input_dir, out_dir):
    files = []
    for root, _, names in os.walk(input_dir):
        rp = os.path.abspath(root)
        if rp == out_dir or rp.startswith(out_dir + os.sep):
            continue                                   # 출력 폴더는 탐색 제외
        files += [os.path.join(root, n) for n in names if n.lower().endswith(MEDIA_EXT)]
    return sorted(files)


def _plan(files, out_dir, time_offset, use_mtime):
    """출력 이름 결정(내장 시각) + 이미 변환된 것 제외. (todo, skipped)."""
    todo, skipped, used = [], 0, {}
    for src in files:
        dt = None
        if not use_mtime:
            try:
                with open(src, "rb") as f:
                    h = mf.read_header(f.read(4096), 0)
                if h:
                    dt = mf.ts_to_datetime(h[2], time_offset)
            except Exception:
                dt = None
        if dt is None:
            dt = datetime.fromtimestamp(os.path.getmtime(src))
        key = dt.strftime("%Y-%m-%d_%H-%M-%S")
        idx = used.get(key)
        used[key] = 0 if idx is None else idx + 1
        dst = os.path.join(out_dir, _out_name(dt, None if idx is None else idx + 1))
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            skipped += 1
            continue
        todo.append((src, dst))
    return todo, skipped


def run(input_dir, out_dir, *, time_offset=-9.0, no_audio=False, use_mtime=False, workers=0):
    input_dir, out_dir = os.path.abspath(input_dir), os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    files = _collect(input_dir, out_dir)
    print(f"  .media 발견: {len(files)}개")
    if not files:
        return {"converted": 0, "skipped": 0, "failed": 0}
    todo, skipped = _plan(files, out_dir, time_offset, use_mtime)
    print(f"  이미 변환됨: {skipped}개 · 변환 대상: {len(todo)}개")
    if not todo:
        return {"converted": 0, "skipped": skipped, "failed": 0}
    jobs = workers if workers > 0 else min(16, os.cpu_count() or 4)
    done = failed = 0
    lock = threading.Lock()

    def work(item):
        s, d = item
        try:
            return (s, d) + _convert_one(s, d, no_audio)
        except Exception as e:
            return s, d, False, str(e)[:150]

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for fut in as_completed([ex.submit(work, it) for it in todo]):
            s, d, ok, msg = fut.result()
            with lock:
                if ok:
                    done += 1
                    if done <= 5 or done % 100 == 0 or done == len(todo):
                        print(f"    OK {os.path.basename(d)} [{msg}]")
                else:
                    failed += 1
                    if os.path.exists(d):
                        try:
                            os.remove(d)
                        except OSError:
                            pass
                    print(f"    X 실패 {os.path.basename(s)}: {msg}")
    print(f"  변환 {done} · 생략 {skipped} · 실패 {failed}")
    return {"converted": done, "skipped": skipped, "failed": failed}
