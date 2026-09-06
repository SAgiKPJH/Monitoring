# 2_classification_labeling — 눈/입 클릭 라벨 + 4클래스 조립

1단계 `crops\` 를 격자로 띄워 **클릭으로 눈/입 open** 을 라벨(`labels.csv`), 그 뒤 4클래스
ImageFolder 로 조립해 3단계 학습에 넘긴다.

## ① grid_label.py — 격자 멀티라벨링

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\2_classification_labeling
..\..\.venv\Scripts\python.exe grid_label.py
```
- **타일 클릭 = 선택**(노랑 테두리) → **키로 속성 토글**:
  `e`눈뜸 · `m`입벌림 · `c`입가림 · `f`인상 · `b`뒤통수 · `n`None(미상)
- 타일 하단 `E M C F B N` = 속성(초록=설정) · 테두리 초록=라벨완료
- 키: `a` 페이지 전체 라벨완료 · `,`/`.` 이전·다음 페이지 · `s` 저장 · `q` 종료
- 크롭은 1단계 폴더 참조, 라벨은 이 폴더 `labels.csv`(멀티라벨).
- **속성 추가**는 `grid_label.py` 의 `ATTRS` 에 `("키","이름","글자")` 한 줄만.

## ② build_dataset_multilabel.py — 멀티라벨 데이터셋 조립 (채택)

```powershell
..\..\.venv\Scripts\python.exe build_dataset_multilabel.py
```
- `labels.csv`(라벨완료·뒤통수/None 제외) → `..\3_classification_training\dataset_ml\{images, labels.csv(멀티핫)}`.
- 크롭 1장에 여러 속성 동시 → 3단계에서 **단일 멀티라벨 모델**(추론 1회) 학습.

다음: `..\3_classification_training\run_training_multilabel.py`.

> 대안(속성별 이진): `build_dataset.py` → `dataset_<attr>\{0_,1_}` (속성당 모델 N개, CNN 표준 재사용).
