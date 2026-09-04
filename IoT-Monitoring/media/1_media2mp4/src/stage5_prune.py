"""stage5 — 낮은 변화량(STATIC) 영상 제거.

스캔 캐시에서 STATIC(meanYDIF<thresh_mean AND maxYDIF<thresh_max)로 판정된 클립을
Cut·resized 폴더에서 삭제한다. Convert(원본 master)는 건드리지 않는다.
증분 안전: 이미 지워진 것은 그냥 건너뜀.
"""
from pathlib import Path

from .cache_util import load_cache, classify


def run(cut_dir, resized_dir, cache_path, *, thresh_mean=0.12, thresh_max=2.0):
    done = load_cache(cache_path)
    statics = [r["file"] for r in done.values()
               if classify(r, thresh_mean, thresh_max) == "STATIC"]
    dirs = [Path(d) for d in (cut_dir, resized_dir) if d and Path(d).is_dir()]
    removed = {d.name: 0 for d in dirs}
    for name in statics:
        for d in dirs:
            p = d / name
            if p.exists():
                p.unlink()
                removed[d.name] += 1
    kept = len(done) - len(statics)
    print(f"  STATIC {len(statics)}개 판정 (MOTION 유지 {kept}개) · 삭제: "
          + (" · ".join(f"{k} {v}개" for k, v in removed.items()) or "대상 폴더 없음"))
    return {"static": len(statics), "kept": kept, **removed}
