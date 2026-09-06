#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\3_classification_training
#   ..\..\.venv\Scripts\python.exe run_training_multilabel.py                          # mobilenet_v2
#   ..\..\.venv\Scripts\python.exe run_training_multilabel.py --params src\params_resnet18.json
#   전제: 2단계 build_dataset_multilabel.py 로 dataset_ml\(images + labels.csv) 생성
# ─────────────────────────────────────────────────────────────
r"""단일 멀티라벨 얼굴상태 분류 학습 (자체 구현, BCE).

백본 1개 + N-출력(sigmoid) → 크롭 1장에 여러 속성 동시 예측(추론 1회). RDK 배포(ONNX) 친화.
CNN_Training_Standard 는 단일라벨이라 여기선 자체 학습. params(network_name/input_size/epoch/
batch_size/lr/train_ratio/using_gpu) 재사용. BGR 무변환·0.5 정규화(Training_Standard 관례).
"""
import argparse
import csv
import json
import random
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.models as tvm
from torch.utils.data import DataLoader, Dataset

HERE = Path(__file__).resolve().parent


def build_model(network, n_out):
    if network == "mobilenet_v2":
        m = tvm.mobilenet_v2(weights="DEFAULT")
        m.classifier[1] = nn.Linear(m.last_channel, n_out)
    elif network == "resnet18":
        m = tvm.resnet18(weights="DEFAULT")
        m.fc = nn.Linear(m.fc.in_features, n_out)
    else:
        raise ValueError(f"지원 network_name 아님(멀티라벨): {network} — mobilenet_v2/resnet18")
    return m


def _augment(img, aug):
    """float[0,1] BGR HxWxC 라벨보존 증강(학습 시). 얼굴 상태는 좌우대칭·광도 변화에 라벨 불변."""
    if aug.get("horizontal_flip") and random.random() < 0.5:
        img = img[:, ::-1]
    rot = aug.get("rotation", 0)
    if rot:
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), random.uniform(-rot, rot), 1.0)
        img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
    b = aug.get("brightness", 0)
    if b:
        img = img + random.uniform(-b, b)
    c = aug.get("contrast", 0)
    if c:
        img = (img - 0.5) * (1.0 + random.uniform(-c, c)) + 0.5
    n = aug.get("noise", 0)
    if n:
        img = img + np.random.normal(0, n, img.shape)
    return np.clip(img, 0, 1).astype(np.float32)


class MLSet(Dataset):
    def __init__(self, rows, root, attrs, size, aug=None, train=False):
        self.rows, self.root, self.attrs, self.size = rows, root, attrs, size
        self.aug, self.train = aug or {}, train

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        data = np.fromfile(str(self.root / r["file"]), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)           # BGR 유지
        img = cv2.resize(img, (self.size, self.size)).astype(np.float32) / 255.0
        if self.train and self.aug:
            img = _augment(img, self.aug)
        img = (img - 0.5) / 0.5
        x = torch.from_numpy(np.ascontiguousarray(img.transpose(2, 0, 1)))
        y = torch.tensor([float(int(r[a])) for a in self.attrs])
        return x, y


def split_by_clip(rows, ratio, seed):
    """clip(파일명 _f 앞) 단위로 train/val 분리 — 같은 클립이 양쪽에 안 가게(누수 방지)."""
    groups = {}
    for r in rows:
        groups.setdefault(r["file"].split("_f")[0], []).append(r)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    target_val = round(len(rows) * (1 - ratio))
    train, val, vc = [], [], 0
    for k in keys:
        g = groups[k]
        if vc < target_val and (len(rows) - vc - len(g)) > 0:
            val += g
            vc += len(g)
        else:
            train += g
    return train, val


def main() -> int:
    ap = argparse.ArgumentParser(description="단일 멀티라벨 얼굴상태 분류 학습 (BCE)")
    ap.add_argument("--data", default=str(HERE / "dataset_ml"), help="build_dataset_multilabel.py 산출")
    ap.add_argument("--params", default=str(HERE / "src" / "params.json"))
    ap.add_argument("--output_path", default="", help="비우면 output_ml_<네트워크>")
    args = ap.parse_args()

    data = Path(args.data)
    csv_path = data / "labels.csv"
    if not csv_path.is_file():
        print(f"[에러] {csv_path} 없음 — 먼저 build_dataset_multilabel.py 실행")
        return 1
    hp = json.load(open(args.params, encoding="utf-8-sig"))["hyperparameter"]
    net, size = hp["network_name"], int(hp["input_size"])
    epochs, batch = int(hp["epoch"]), int(hp["batch_size"])
    lr, ratio = float(hp["lr"]), float(hp.get("train_ratio", 0.8))
    aug = hp.get("augmentation", {})
    device = "cuda" if (hp.get("using_gpu", True) and torch.cuda.is_available()) else "cpu"
    out = Path(args.output_path) if args.output_path else HERE / f"output_ml_{net}"
    out.mkdir(parents=True, exist_ok=True)

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    attrs = [c for c in rows[0].keys() if c != "file"] if rows else []
    if not rows:
        print("데이터 0건"); return 1
    tr, va = split_by_clip(rows, ratio, 42)
    print(f"net={net} size={size} device={device} · train {len(tr)} / val {len(va)} · 속성 {attrs}")
    print(f"aug={aug or '없음'}")

    dl_tr = DataLoader(MLSet(tr, data / "images", attrs, size, aug, train=True),
                       batch_size=batch, shuffle=True, num_workers=0)
    dl_va = DataLoader(MLSet(va, data / "images", attrs, size), batch_size=batch, num_workers=0) if va else None

    model = build_model(net, len(attrs)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    crit = nn.BCEWithLogitsLoss()
    best = None
    for ep in range(1, epochs + 1):
        model.train()
        tl = 0.0
        for x, y in dl_tr:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = crit(model(x), y)
            loss.backward()
            opt.step()
            tl += loss.item() * len(x)
        tl /= max(1, len(tr))
        vl, acc = _validate(model, dl_va, crit, device, attrs)
        acc_s = " ".join(f"{a[:5]}:{v:.2f}" for a, v in zip(attrs, acc)) if acc else ""
        print(f"  ep {ep:3d}/{epochs}  train {tl:.4f}  val {vl:.4f}  {acc_s}", flush=True)
        score = vl if dl_va else tl
        if best is None or score < best:
            best = score
            torch.save(model.state_dict(), out / "best.pth")
            json.dump({"network": net, "input_size": size, "attrs": attrs,
                       "normalize": [0.5, 0.5], "channel": "BGR"},
                      open(out / "meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n완료 — best {best:.4f} → {out}\\best.pth (+ meta.json)")
    return 0


def _validate(model, dl, crit, device, attrs):
    if dl is None:
        return 0.0, None
    model.eval()
    vl, correct, n = 0.0, np.zeros(len(attrs)), 0
    with torch.no_grad():
        for x, y in dl:
            x, y = x.to(device), y.to(device)
            logit = model(x)
            vl += crit(logit, y).item() * len(x)
            pred = (torch.sigmoid(logit) > 0.5).float()
            correct += (pred == y).sum(0).cpu().numpy()
            n += len(x)
    return vl / max(1, n), (correct / max(1, n)).tolist()


if __name__ == "__main__":
    raise SystemExit(main())
