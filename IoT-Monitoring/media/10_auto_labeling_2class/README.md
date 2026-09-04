# 10_auto_labeling_2class — 2클래스 자동 라벨링 (baby + baby_face)

7_auto_labeling(1클래스 baby)의 **2클래스판**. 학습한 2클래스 모델을 라벨 공장으로 써서
carved-08 클립에서 **baby(0)·baby_face(1)** 의사라벨을 자동 생성한다(반자동 pseudo-label 확장).

## auto_label.py

클립마다 **첫 프레임 + 중간 프레임(2장)** 에 8의 2클래스 모델
(`..\8_detection_2class_train\output\60\model.pth`)을 돌려, 채택된 박스를 **클래스 id 그대로**
YOLO 라벨로 저장 → 이 폴더 `dataset\`(images/labels/**classes.txt**). 검수 몽타주 `_preview_auto\`.

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\10_auto_labeling_2class
..\.venv\Scripts\python.exe auto_label.py --n-clips 100      # 랜덤 100클립 (권장 시작값)
..\.venv\Scripts\python.exe auto_label.py --n-clips 0        # 전체
#   → _preview_auto\ 몽타주 검수 후 잘못된 것은 dataset\images|labels 에서 삭제
```

| 옵션 | 기본 | 설명 |
|---|---|---|
| `--src` | `D:\carved-08\Cut` | 클립 폴더 (영상당 2프레임) |
| `--out` | `.\dataset` | 저장 위치 (이 폴더 dataset) |
| `--model` | `..\8_detection_2class_train\output\60\model.pth` | 2클래스 라벨 공장 (best 로 교체 가능) |
| `--n-clips` | 200 | 처리 클립 수 (0=전체, 증분: 이미 라벨된 클립 제외) |
| `--conf` | 0.5 | 채택 최소 신뢰도 |
| `--min/max-area` | 0.0 / 0.9 | 박스/프레임 면적비 (얼굴이 작아 하한 0) |

## 출력 dataset\

```
dataset\
├── images\   labels\        # YOLO: 0=baby, 1=baby_face
└── classes.txt              # 모델 클래스명으로 자동 생성(baby / baby_face)
```

- 그대로 `..\8_detection_2class_train\run_training.py --dataset_path` 대상이 될 수 있다(2클래스 학습 재확장).

## 주의 — 얼굴 품질은 현재 모델에 달림

- 이 도구가 만드는 **baby_face** 라벨은 **현재 2클래스 모델이 아는 만큼만** 정확하다.
  face 학습 예시가 적으면 얼굴 pseudo-label 이 부실하므로, 8의 `label_tool` 로 **얼굴 시드셋을
  충분히 라벨→재학습→이 도구로 확장**하는 순서를 권장(자기지도 확장 루프).
- baby 는 이미 잘 잡히므로 baby 라벨은 신뢰도 높음. 몽타주에서 얼굴 박스 위주로 검수.
