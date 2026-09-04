# 7_auto_labeling — 자동 라벨링 + 데이터셋 본체

손으로 박스 치기 전에 **우리가 학습한 baby 모델을 라벨 공장으로** 써서 학습 데이터를 빠르게
늘립니다(반자동 pseudo-label). 만들어진 데이터셋(`dataset\`)이 이 폴더에 있고,
`..\8_detection_2class_train` 이 이 데이터셋을 그대로 학습합니다.

## auto_label.py

`D:\carved-08\Cut` 클립마다 **첫 프레임 + 중간 프레임(2장)** 을 뽑아, 파인튜닝 baby 모델
(`..\5_detection_train\output\best\model.pth`)이 잡은 것만 YOLO 라벨(class 0=baby)로 저장 →
`dataset\images|labels\` (`auto` 접미사). 검수 몽타주 `_preview_auto\` 생성.

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\7_auto_labeling
..\.venv\Scripts\python.exe auto_label.py --n-clips 100      # 랜덤 100클립 (권장 시작값)
..\.venv\Scripts\python.exe auto_label.py --n-clips 0        # 전체
#   → _preview_auto\ 몽타주 검수 후 잘못된 것은 dataset\images|labels 에서 삭제
```

| 옵션 | 기본 | 설명 |
|---|---|---|
| `--src` | `D:\carved-08\Cut` | 클립 폴더 (영상당 2프레임) |
| `--out` | `.\dataset` | 저장 위치 (이 폴더의 dataset) |
| `--model` | `..\5_detection_train\output\best\model.pth` | 라벨 공장 = **학습한 baby 모델** |
| `--n-clips` | 200 | 처리 클립 수 (0=전체, 증분: 이미 라벨된 클립 제외) |
| `--conf` | 0.4 | 채택 최소 신뢰도 |
| `--min/max-area` | 0.01 / 0.45 | 박스/프레임 면적비 (과대 박스 배제) |

## dataset\ (2클래스 공용)

```
dataset\
├── images\        # 프레임 JPEG (BGR)
├── labels\        # YOLO txt — 0=baby, 1=baby_face
└── classes.txt    # baby / baby_face  ← 클래스 수(nc=2)를 여기서 정함
```

- auto_label 은 **baby(0)** 만 채웁니다. **baby_face(1)** 는
  `..\8_detection_2class_train\label_tool` 로 각 이미지에 추가합니다.
- `..\8_detection_2class_train\run_training.py` 가 이 `dataset\` 를 학습 대상으로 씁니다.

## 주의

- 모델이 잘못 잡은(아기 아님·박스 어긋남) 프레임은 `_preview_auto\` 몽타주에서 확인해
  `dataset\images|labels\` 에서 해당 파일 삭제 (baby 클래스 오염 방지).
- 이불 속·어려운 케이스는 `..\3_detection_labeling_tool\label_tool` 수동 보강.
- auto 라벨 파일명은 `..._f####auto.jpg`, 수동 라벨은 접미사 없음 — 학습 때 합산.
