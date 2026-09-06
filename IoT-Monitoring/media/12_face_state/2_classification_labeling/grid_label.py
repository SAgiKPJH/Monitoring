#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\2_classification_labeling
#   ..\..\.venv\Scripts\python.exe grid_label.py           # 1단계 crops\ 를 격자로 라벨링
#   ── 타일 클릭=선택 · Shift+클릭=범위 · Ctrl+클릭=개별 다중 → 키로 선택 전부에 속성 설정 ──
#   e:눈뜸 m:입벌림 c:입가림 f:인상 b:뒤통수 n:None(미상)  ·  a:페이지 라벨완료
#   , / . 이전·다음 페이지 · s 저장 · q 종료
#   타일 하단 E M C F B N = 속성(초록=설정) · 테두리: 노랑=선택, 초록=라벨완료
# ─────────────────────────────────────────────────────────────
r"""얼굴 크롭을 격자로 보며 **여러 속성**을 멀티라벨링 → labels.csv.

속성: eyes_open·mouth_open·mouth_covered(입가림)·frown(인상)·back_head(뒤통수)·none(미상).
타일 클릭(단일)·Shift+클릭(범위)·Ctrl+클릭(개별 다중)으로 선택 후, 키로 **선택된 전부**에 속성 설정
(하나라도 꺼졌으면 전부 켜고, 전부 켜졌으면 전부 끔). 속성 추가는 ATTRS 에 한 줄만.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

from grid_io import collect_crops, load_labels, save_labels

CROPS_DIR = str(Path(__file__).resolve().parent.parent / "1_baby_face_dataset_collect" / "crops")
CSV_PATH = str(Path(__file__).resolve().parent / "labels.csv")
COLS, ROWS, TILE = 15, 6, 150
BAR_H = 52                           # 상단 2줄(상태 + 키 설명)
WIN = "12 grid label (multi-attr)"
FONT = cv2.FONT_HERSHEY_SIMPLEX
_CACHE = {}

# 속성: (토글키, 이름, 한글자표시). 추가하려면 여기에 한 줄.
ATTRS = [
    ("e", "eyes_open", "E"),       # 눈 뜸
    ("m", "mouth_open", "M"),      # 입 벌림
    ("c", "mouth_covered", "C"),   # 입 가림
    ("f", "frown", "F"),           # 인상(울려함)
    ("b", "back_head", "B"),       # 뒤통수(얼굴 안보임)
    ("n", "none", "N"),            # None/미상
]
ATTR_NAMES = [a[1] for a in ATTRS]
ATTR_KEY = {ord(k): name for k, name, _ in ATTRS}


def _crop_img(path):
    if path not in _CACHE:
        data = np.fromfile(str(path), dtype=np.uint8)
        _CACHE[path] = cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None
    return _CACHE[path]


def _tile(crop, size, lab, selected):
    t = np.full((size, size, 3), 40, np.uint8)
    if crop is not None:
        ch, cw = crop.shape[:2]
        s = min(size / cw, size / ch)
        rw, rh = max(1, int(cw * s)), max(1, int(ch * s))
        t[(size - rh) // 2:(size - rh) // 2 + rh, (size - rw) // 2:(size - rw) // 2 + rw] = \
            cv2.resize(crop, (rw, rh))
    step = size // (len(ATTRS) + 1)
    for i, (_, name, ch) in enumerate(ATTRS):                # 하단 속성 표시줄
        on = lab.get(name, 0)
        cv2.putText(t, ch, (6 + i * step, size - 8), FONT, 0.5,
                    (0, 220, 0) if on else (90, 90, 90), 2 if on else 1)
    border = (0, 255, 255) if selected else ((0, 220, 0) if lab.get("labeled") else (110, 110, 110))
    cv2.rectangle(t, (0, 0), (size - 1, size - 1), border, 3 if selected else 2)
    return t


def render(crops, labels, page, sel):
    per = COLS * ROWS
    grid = np.full((ROWS * TILE, COLS * TILE, 3), 20, np.uint8)
    for k in range(per):
        i = page * per + k
        if i >= len(crops):
            break
        r, c = divmod(k, COLS)
        grid[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE] = \
            _tile(_crop_img(crops[i]), TILE, labels[crops[i].name], i in sel)
    n_lab = sum(1 for v in labels.values() if v.get("labeled"))
    bar = np.full((BAR_H, grid.shape[1], 3), 50, np.uint8)
    npages = -(-len(crops) // per)
    cv2.putText(bar, f"p{page + 1}/{npages}  labeled {n_lab}/{len(crops)}  selected {len(sel)}  |  "
                     "click / Shift=range / Ctrl=multi  |  a:accept  ,.:page  s:save  q:quit",
                (8, 18), FONT, 0.42, (255, 255, 255), 1)
    legend = "   ".join(f"{k}={name}" for k, name, _ in ATTRS)   # e=eyes_open  m=mouth_open ...
    cv2.putText(bar, "keys(select tiles then press):  " + legend, (8, 42), FONT, 0.42, (0, 230, 230), 1)
    return np.vstack([bar, grid])


class Grid:
    def __init__(self, crops):
        self.crops, self.page = crops, 0
        self.sel, self.anchor, self.click = set(), -1, None   # sel=선택 집합, anchor=shift 기준

    def on_mouse(self, event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        y -= BAR_H
        if y < 0:
            return
        c, r = x // TILE, y // TILE
        if c < COLS and r < ROWS:
            i = self.page * COLS * ROWS + r * COLS + c
            if i < len(self.crops):
                self.click = (i, bool(flags & cv2.EVENT_FLAG_SHIFTKEY),
                              bool(flags & cv2.EVENT_FLAG_CTRLKEY))


def main() -> int:
    crops = collect_crops(CROPS_DIR)
    if not crops:
        print(f"[에러] 크롭 없음: {CROPS_DIR}\n먼저 1단계 collect.py 로 얼굴 크롭을 모으세요.")
        return 1
    saved = load_labels(CSV_PATH, ATTR_NAMES)
    labels = {c.name: saved.get(c.name, {**{a: 0 for a in ATTR_NAMES}, "labeled": 0}) for c in crops}
    per = COLS * ROWS
    npages = -(-len(crops) // per)
    print(f"{len(crops)}개 크롭 · {npages}페이지 · 속성 {ATTR_NAMES}")

    g = Grid(crops)
    cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WIN, g.on_mouse)
    dirty, img = True, None
    while True:
        if dirty:
            img = render(crops, labels, g.page, g.sel)
            dirty = False
        cv2.imshow(WIN, img)
        k = cv2.waitKey(20) & 0xFF
        if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
            break
        if g.click is not None:
            i, shift, ctrl = g.click
            g.click = None
            if shift and g.anchor >= 0:                       # shift=범위 선택
                lo, hi = sorted((g.anchor, i))
                g.sel = set(range(lo, hi + 1))
            elif ctrl:                                        # ctrl=개별 추가/제거
                g.sel ^= {i}
                g.anchor = i
            else:                                             # 단일 선택
                g.sel, g.anchor = {i}, i
            dirty = True
        if k == 255:
            continue
        if k in (ord("q"), 27):
            break
        elif k in ATTR_KEY and g.sel:                        # 선택된 타일 전부 일괄 설정
            name = ATTR_KEY[k]
            idxs = [j for j in g.sel if j < len(crops)]
            target = 0 if all(labels[crops[j].name].get(name) for j in idxs) else 1
            for j in idxs:                                    # 하나라도 꺼짐→전부 켬, 전부 켜짐→전부 끔
                labels[crops[j].name][name] = target
                labels[crops[j].name]["labeled"] = 1
            dirty = True
        elif k == ord(".") and g.page < npages - 1:
            save_labels(CSV_PATH, labels, ATTR_NAMES)
            g.page += 1
            g.sel, g.anchor, dirty = set(), -1, True
        elif k == ord(",") and g.page > 0:
            save_labels(CSV_PATH, labels, ATTR_NAMES)
            g.page -= 1
            g.sel, g.anchor, dirty = set(), -1, True
        elif k == ord("a"):                                  # 페이지 전체 라벨완료
            for j in range(g.page * per, min((g.page + 1) * per, len(crops))):
                labels[crops[j].name]["labeled"] = 1
            dirty = True
        elif k == ord("s"):
            save_labels(CSV_PATH, labels, ATTR_NAMES)
            print("저장:", CSV_PATH)
    save_labels(CSV_PATH, labels, ATTR_NAMES)
    cv2.destroyAllWindows()
    n_lab = sum(1 for v in labels.values() if v.get("labeled"))
    print(f"저장 완료 — 라벨 {n_lab}/{len(crops)} → {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
