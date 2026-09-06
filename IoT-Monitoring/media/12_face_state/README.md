# 12_face_state — 아기 얼굴 상태(눈 뜸 / 입 벌림) 분류

baby_face 감지(8·10) → **얼굴 크롭** → 눈(open/closed)·입(open/closed) 상태 분류.
접근 3안 중 **얼굴 크롭 분류**(감지와 분리, 라벨링 쉬움, 야간·각도에 강함)를 채택.

## 파이프라인 (4단계)

1. **`1_baby_face_dataset_collect/`** — baby_face 감지→**크롭 수집**만 (라벨링 없음)
2. **`2_classification_labeling/`** — 크롭을 격자로 **멀티 속성 클릭 라벨** → 멀티라벨 데이터셋 조립
3. **`3_classification_training/`** — **단일 멀티라벨 모델** 학습(mobilenet_v2 / resnet18)
4. **`4_inference/`** — 학습 모델로 **실시간(live)·샘플(sample) 추론**(눈뜸/입벌림/입가림/인상 오버레이)

## 속성(멀티라벨) — 단일 멀티라벨 모델 (채택)

라벨은 여러 속성을 **독립적으로** 단다:
**eyes_open · mouth_open · mouth_covered(입가림) · frown(인상) · back_head(뒤통수) · none(미상)**.
(속성 추가는 `2_classification_labeling/grid_label.py` 의 `ATTRS` 에 한 줄만.)

학습은 **백본 1개 + N-출력(sigmoid) 단일 멀티라벨 모델** — 크롭 1장에 모든 속성을 동시 예측
(**추론 1회, 모델 1개**, RDK X5 친화):
- 2단계 `build_dataset_multilabel.py` → `dataset_ml\{images, labels.csv(멀티핫)}`
- 3단계 `run_training_multilabel.py` (자체 BCE 학습, mobilenet_v2 / resnet18, clip 단위 train/val)
- **back_head·none** 은 얼굴 판별 불가라 학습에서 **제외**.

> 대안(속성별 이진): `build_dataset.py` + `run_training.py` — CNN 표준(단일라벨) 재사용, 속성당 모델 N개(추론 N회).

## 흐름

`collect.py`(1) → `grid_label.py`(2, 멀티라벨) → `build_dataset_multilabel.py`(2) →
`run_training_multilabel.py`(3) → `4_inference`(live/sample)

> 전제: baby_face 감지기(8)가 쓸 만해야 크롭 품질이 좋습니다. 얼굴 라벨 보강→재학습이 선행되면 좋습니다.
> 데이터 균형(특히 `eyesC_mouthO` 희소)에 유의.
