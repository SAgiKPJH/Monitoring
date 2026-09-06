#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
# 실행 (이 폴더에서):
#   cd D:\Code\Monitoring\IoT-Monitoring\media\13_pose_train
#   처음부터(COCO 사전학습):  ..\.venv\Scripts\python.exe 3_run_training.py
#   이어학습(새 데이터로 best.pt 이어서):
#     ..\.venv\Scripts\python.exe 3_run_training.py --from output\train\weights\best.pt --name train2
#   전제: 1_pose_correct.py 로 라벨 생성 → 2_build_data.py 로 data.yaml 구성
# ─────────────────────────────────────────────────────────────
r"""baby pose(COCO-17 keypoint) 학습 — ultralytics yolo11n-pose 파인튜닝.

pose 학습 표준(Training_Standard)이 없어 **ultralytics 직접** 사용한다.
라벨은 `..\3_detection_labeling_tool\pose_label_tool`(YOLO-pose, 17 keypoint)로 만든다.
GTX 1650 fp16 불안정 → amp=False.
※ '이어학습'은 ultralytics resume 이 아니다: resume 은 체크포인트의 옛 데이터·에폭을 되불러와
   추가된 데이터셋을 무시한다. 새 데이터로는 best.pt 를 시작 가중치로 준 **새 파인튜닝**(--from)을 쓴다.
"""
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ══════════════════════ 설정 ══════════════════════
DATA_YAML = str(HERE / "dataset" / "data.yaml")
BASE_MODEL = "yolo11n-pose.pt"       # 사전학습 COCO pose (자동 다운로드)
EPOCHS = 250
PATIENCE = 30                        # 조기종료: val 개선 없이 이 에폭 지나면 중단 (0=비활성)
IMGSZ = 640
BATCH = 8
DEVICE = 0                           # GPU 0 · CPU 면 "cpu"
DEGREES = 45.0                       # 무작위 회전 증강 ±도 (0=끔). keypoint 도 같이 회전됨
FLIPLR = 0.5                         # 좌우반전 확률 (data.yaml flip_idx 로 좌/우 관절 스왑 — pose 안전)
FLIPUD = 0.5                         # 상하반전 확률 (기본 끔 — 필요시 0.5)
POSE_FITNESS_W = 0.9                 # fitness 의 Pose 비중(Box=1-값). best.pt 선택·조기종료가 Pose 우선(1.0=순수 Pose)
OUTPUT = str(HERE / "output")
# ═══════════════════════════════════════════════════


def _apply_pose_priority_fitness():
    """fitness 를 Pose 우선으로 재정의 → best.pt 선택·조기종료가 Pose 기준으로 동작.

    기본 PoseMetrics.fitness = pose_mAP50-95 + box_mAP50-95 (Box 지배적).
    → POSE_FITNESS_W 로 가중: fitness = W*pose + (1-W)*box.
    """
    from ultralytics.utils.metrics import DetMetrics, PoseMetrics

    def _fit(self):
        return (POSE_FITNESS_W * self.pose.fitness()
                + (1 - POSE_FITNESS_W) * DetMetrics.fitness.fget(self))
    PoseMetrics.fitness = property(_fit)


def _epoch_best_marker(trainer):
    """매 에폭 끝(on_fit_epoch_end): 이번 에폭이 새 best 인지 + Pose mAP 표시.

    이 시점엔 trainer.best_fitness 가 이번 에폭까지 반영돼 있어, 새 best 면
    fitness == best_fitness. (fitness = Pose 우선 가중, _apply_pose_priority_fitness 참고)
    """
    if trainer.fitness is None:
        return
    fit = float(trainer.fitness)
    best = float(trainer.best_fitness) if trainer.best_fitness is not None else fit
    ep = trainer.epoch + 1
    m = getattr(trainer, "metrics", None) or {}
    pose = m.get("metrics/mAP50-95(P)")
    extra = f"  Pose50-95={float(pose):.4f}" if pose is not None else ""
    mark = "  ★ NEW BEST (best.pt 갱신)" if fit >= best else f"  (best {best:.4f})"
    print(f"[epoch {ep}] fitness={fit:.4f}{extra}{mark}", flush=True)


def _report_best(train_dir):
    """results.csv 에서 best 에폭(=best.pt) 을 찾아 출력. fitness 는 Pose 우선 가중(학습과 동일)."""
    import csv
    p = Path(train_dir) / "results.csv"
    if not p.is_file():
        return
    try:
        rows = [{k.strip(): v for k, v in r.items()}
                for r in csv.DictReader(open(p, encoding="utf-8"))]

        def fit(r):                                          # 학습 fitness 와 동일 가중
            return (POSE_FITNESS_W * float(r["metrics/mAP50-95(P)"])
                    + (1 - POSE_FITNESS_W) * float(r["metrics/mAP50-95(B)"]))
        i = max(range(len(rows)), key=lambda j: fit(rows[j]))    # 첫 최대(동률 시 앞 에폭)
        r = rows[i]
        ep = int(float(r["epoch"]))
    except (KeyError, ValueError, IndexError):
        print("(best 에폭 파싱 실패 — results.csv 확인)")
        return
    print(f"\n★ best 에폭: {ep} / {len(rows)}  (best.pt = 이 에폭 가중치)")
    print(f"   Pose mAP50-95={float(r['metrics/mAP50-95(P)']):.4f}  mAP50={float(r['metrics/mAP50(P)']):.4f}")
    print(f"   Box  mAP50-95={float(r['metrics/mAP50-95(B)']):.4f}  mAP50={float(r['metrics/mAP50(B)']):.4f}")
    if ep >= len(rows):
        print("   ※ best 가 마지막 에폭 → 아직 수렴 전. EPOCHS 를 늘리세요.")


def main() -> int:
    ap = argparse.ArgumentParser(description="baby pose 학습 / 새 데이터 이어학습")
    ap.add_argument("--from", dest="init", default="",
                    help="이어학습 시작 가중치(예: output\\train\\weights\\best.pt). 비우면 COCO 사전학습부터")
    ap.add_argument("--name", default="train", help="산출물 run 이름 output\\<name> (이어학습은 새 이름 권장)")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    args = ap.parse_args()

    if not Path(DATA_YAML).is_file():
        print(f"[에러] data.yaml 없음: {DATA_YAML}\n"
              "  먼저 2_build_data.py 실행(1_pose_correct.py 로 만든 dataset 을 split + data.yaml 생성)")
        return 1

    init = BASE_MODEL
    if args.init:                                                # 이어학습(warm-start)
        if not Path(args.init).is_file():
            print(f"[에러] 시작 가중치 없음: {args.init}")
            return 1
        run_dir = (Path(OUTPUT) / args.name).resolve()
        if Path(args.init).resolve().parent.parent == run_dir:  # 읽는 체크포인트를 덮어쓰기 방지
            print(f"[에러] 시작 가중치가 출력 폴더({run_dir})와 같습니다.\n"
                  "  이어학습은 새 --name 을 주세요(예: --name train2) — 기존 run/체크포인트 보존.")
            return 1
        init = args.init

    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics 필요: pip install ultralytics")
        return 1
    print(f"시작 가중치: {init}" + ("  (COCO 사전학습부터)" if init == BASE_MODEL else "  (이어학습)"))
    _apply_pose_priority_fitness()                               # fitness=Pose 우선 → best.pt·조기종료 Pose 기준
    print(f"평가/조기종료 기준: Pose 우선 (fitness = {POSE_FITNESS_W}*Pose + {1 - POSE_FITNESS_W:.1f}*Box)")
    model = YOLO(init)
    model.add_callback("on_fit_epoch_end", _epoch_best_marker)   # 에폭마다 best 갱신 여부 + Pose mAP
    model.train(data=DATA_YAML, epochs=args.epochs, patience=PATIENCE, imgsz=IMGSZ, batch=BATCH,
                device=DEVICE, amp=False, degrees=DEGREES, fliplr=FLIPLR, flipud=FLIPUD,
                project=OUTPUT, name=args.name, exist_ok=True)
    print(f"완료 — 산출물: {OUTPUT}\\{args.name}\\weights\\best.pt")
    _report_best(Path(OUTPUT) / args.name)                       # best 가 몇 에폭인지 보고
    print("추론: 4_Pose_Sample_Test.py (POSE_MODEL 을 위 best.pt 로)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
