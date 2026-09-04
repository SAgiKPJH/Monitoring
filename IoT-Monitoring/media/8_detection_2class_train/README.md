# 8_detection_2class_train — baby + baby_face 2클래스 감지 학습

`baby`(0)·`baby_face`(1) **2클래스 YOLO** 를 학습합니다. 학습 로직은
`D:\Code\Training_Standard\...\OD_Training_Standard\` 에 있고, 이 폴더는 **얇은 래퍼 +
파라미터 + 2클래스 라벨툴** 입니다 (Training_Standard 규격, BGR).

5_detection_train(1클래스 baby)의 2클래스 확장판입니다.

## 데이터셋 (별도 폴더)

데이터셋 본체는 **`..\7_auto_labeling\dataset\`** 에 있습니다 (중복 생성 안 함):

```
7_auto_labeling\dataset\
├── images\      labels\        # YOLO 라벨: 0=baby, 1=baby_face
└── classes.txt  (baby / baby_face)  ← 클래스 수(nc=2)를 여기서 읽음
```

- **baby(0)** 라벨: `..\7_auto_labeling\auto_label.py` (학습 baby 모델로 자동) + 수동.
- **baby_face(1)** 라벨: 아래 `label_tool` 로 각 이미지에 추가.

## 실행

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\8_detection_2class_train

# ① baby_face 라벨 추가 (기존 이미지 제자리 편집)
cd label_tool
..\..\.venv\Scripts\python.exe main.py            # 7_auto_labeling\dataset\images 편집
#   키: 1 baby · 2 baby_face · 드래그 박스 · SPACE 저장 · x 네거티브 · n/p 이동 · q 종료
cd ..

# ② 학습 — run_training.py 만 최상위. 기본 dataset = ..\7_auto_labeling\dataset (GPU)
..\.venv\Scripts\python.exe run_training.py                              # 기본 (GPU)
..\.venv\Scripts\python.exe run_training.py --params src\params_local_cpu.json  # CPU
#   산출물: 8_detection_2class_train\output\best\model.pth  (+ metrics)

# ③ 학습 결과 추론 확인 (이 폴더 output\best\model.pth · 2클래스 자동)
..\.venv\Scripts\python.exe Detection_Sample_Test.py        # 학습 이미지 N개 랜덤 → out_sample\
..\.venv\Scripts\python.exe Detection_Live_Test.py          # go2rtc 실시간 창

# ④ ONNX 내보내기 (배포용)
..\.venv\Scripts\python.exe src\export_onnx.py output\best\model.pth
```

- 추론 테스트는 `..\4_detection_pretrained\src` 재사용(복붙 없음). `DET_MODEL` = 이 폴더 output,
  `DET_CLASSES=None` → baby·baby_face 둘 다 표시. 클래스명은 `output\best\model_info.json` 에서 자동.

## 파일

| 파일 | 역할 |
|---|---|
| `run_training.py` | **(최상위)** OD_Training_Standard 호출 래퍼 (기본 dataset=`..\7_auto_labeling\dataset`) |
| `src\params_gpu.json` / `params_local_cpu.json` | 하이퍼파라미터 (GPU 기본 / CPU). AMP off (GTX 1650) |
| `src\export_onnx.py` | 산출물 → best.onnx (RDK 배포용) |
| `Detection_Sample_Test.py` | 학습 이미지 N개 랜덤 추론 → `out_sample\` (4의 src 재사용) |
| `Detection_Live_Test.py` | go2rtc 실시간 추론 창 (4의 src 재사용) |
| `label_tool\` | **2클래스 라벨툴** — 이미지 제자리 편집 (baby/baby_face), `label_tool\README.md` |

## 클래스 수(nc)는 어떻게 정해지나

OD_Training_Standard 의 `Local_Detection_ClassCodeBuilder` 가 **`dataset\classes.txt`**
(한 줄당 클래스명, 줄 순서 = class id)를 읽어 nc 를 정합니다. 없으면 기본 `["baby"]`(1클래스).
→ 여기선 `baby` / `baby_face` 2줄이라 **nc=2**. params 에 클래스 수를 따로 적지 않습니다.

> baby(0) 라벨만 있고 baby_face(1) 가 아직 0개여도 nc=2 로 학습은 되지만, face 예시가 없으면
> face 검출은 안 됩니다. label_tool 로 face 박스를 충분히 채운 뒤 학습하세요.

## 흐름

`7_auto_labeling`(baby 자동라벨) → `label_tool`(baby_face 추가) → `run_training.py` →
`output\best\model.pth` → `6_detection_trained_inference` 확인 → `src\export_onnx.py` → `rdk_x5` 배포.
