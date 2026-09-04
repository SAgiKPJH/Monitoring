"""변화량 스캔 캐시(JSONL) 읽기 · MOTION/STATIC 분류 · 제외 목록."""
import json
from pathlib import Path


def load_cache(cache_path) -> dict:
    """파일명 → 스캔 레코드 dict (증분 JSONL, 마지막 값이 우선)."""
    done = {}
    p = Path(cache_path)
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                done[rec["file"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def load_exclude(path) -> set:
    """사용자 제외 목록 (한 줄당 파일명, # 주석 무시). filter/resize 가 건너뜀."""
    p = Path(path)
    if p.exists():
        return {ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")}
    return set()


def classify(rec: dict, thresh_mean: float, thresh_max: float) -> str:
    """STATIC = meanYDIF<thresh_mean AND maxYDIF<thresh_max, error 는 ERROR, 나머지 MOTION."""
    if rec.get("status") == "error":
        return "ERROR"
    if rec["mean"] < thresh_mean and rec["max"] < thresh_max:
        return "STATIC"
    return "MOTION"
