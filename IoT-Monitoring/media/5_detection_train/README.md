# 5_detection_train — baby 감지(YOLO) 학습

라벨 데이터로 **baby 감지 YOLO** 를 학습하고 ONNX 로 내보냅니다.
학습 로직은 `D:\Code\Training_Standard\Training Standard\OD_Training_Standard\` 에 있고,
이 폴더는 **얇은 래퍼 + 데이터 + 파라미터** 입니다 (Training_Standard 규격, BGR).

## 데이터

`dataset\images\*.jpg` + `dataset\labels\*.txt` (YOLO, 단일 클래스 0=baby, 빈 txt=네거티브)
— 현재 352장 복사돼 있음. 라벨은 두 툴로 늘립니다:
- 수동: `..\3_detection_labeling_tool\label_tool\main.py` (박스 + `x` 네거티브)
- 의사라벨(자동): `..\auto_label\auto_label.py` (기본 출력이 이 폴더 `dataset\`)

## 실행

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\5_detection_train

# 학습 — run_training.py 만 최상위. 기본 dataset\ + src\params_gpu.json (GPU)
..\.venv\Scripts\python.exe run_training.py                              # 기본 (GPU)
..\.venv\Scripts\python.exe run_training.py --params src\params_local_cpu.json  # CPU
#   산출물: D:\Code\Monitoring\IoT-Monitoring\media\5_detection_train\output\best\model.pth  (+ metrics.csv)

# ONNX 내보내기 (배포용) — src\ 에 있음
..\.venv\Scripts\python.exe src\export_onnx.py D:\Code\Monitoring\IoT-Monitoring\media\5_detection_train\output\best\model.pth
#   → best.onnx (opset 11, 640) → RDK X5 (rdk_x5) 배포

# 학습 결과 확인은 6_detection_trained_inference (별도 폴더)
```

## 파라미터 (params*.json)

| 파일 | 용도 |
|---|---|
| `params_gpu.json` | **기본** (GPU, epoch 60, batch 8, **AMP off**) — GTX 1650 fp16 NaN 방지 |
| `params_local_cpu.json` | CPU 전용 (epoch 40, batch 8) |

network_name(yolo11n)·input_size(640)·회전 증강(degrees 180: 아기 거꾸로 누움) 등.
`network_name` 없으면 즉시 에러(규격).

## 파일

| 파일 | 역할 |
|---|---|
| `run_training.py` | **(최상위)** OD_Training_Standard 진입점 호출 래퍼 (기본 dataset\ + src\params_gpu.json) |
| `dataset\` | 학습 데이터 (images/ labels/) |
| `src\params*.json` | 하이퍼파라미터 (기본/GPU/CPU) |
| `src\export_onnx.py` | 산출물 → best.onnx (RDK 배포용) |
| `src\train_baby_yolo.ipynb` | Colab 학습 래퍼 (같은 진입점, Drive 업로드 전제) |

> `run_inference.py` 는 제거 — 학습 모델 추론은 `6_detection_trained_inference` 가 담당.

## 흐름

라벨링/의사라벨 → `run_training.py` → 산출물(`best\model.pth`) →
학습 결과 확인 `..\6_detection_trained_inference\Detection_Sample_Test.py`(학습 이미지) ·
`Detection_Live_Test.py`(라이브) → `src\export_onnx.py` → `..\rdk_x5` 배포.

> 1차 결과(2026-09): 352장 학습 → val mAP50 0.91, 학습 이미지 검출 conf 0.56~0.84.
> 다음 사이클: auto_label 확장(--n-clips 500 --conf 0.4) + 어려운 케이스 수동 보강 → 재학습.
