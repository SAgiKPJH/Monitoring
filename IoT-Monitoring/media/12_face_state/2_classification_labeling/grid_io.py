# -*- coding: utf-8 -*-
"""grid 라벨러 I/O — 얼굴 크롭 목록 + **멀티 속성** 라벨 CSV.

속성 목록은 grid_label.ATTRS 에서 정의(눈뜸·입벌림·입가림·인상·뒤통수·None …).
CSV: file, <속성들 0/1>, labeled(0/1). 크롭은 1단계 폴더에 두고 라벨만 저장.
"""
import csv
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def collect_crops(crops_dir):
    p = Path(crops_dir)
    return sorted(q for q in p.iterdir() if q.suffix.lower() in IMAGE_EXTS) if p.is_dir() else []


def load_labels(csv_path, attrs):
    """file -> {<attr>:0/1, labeled:0/1}. 없으면 빈 dict."""
    out = {}
    p = Path(csv_path)
    if not p.exists():
        return out
    with open(p, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                d = {a: int(row.get(a, 0) or 0) for a in attrs}
                d["labeled"] = int(row.get("labeled", 1) or 0)
                out[row["file"]] = d
            except (KeyError, ValueError):
                continue
    return out


def save_labels(csv_path, labels, attrs):
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file", *attrs, "labeled"])
        for name, v in sorted(labels.items()):
            w.writerow([name, *[v.get(a, 0) for a in attrs], v.get("labeled", 0)])
