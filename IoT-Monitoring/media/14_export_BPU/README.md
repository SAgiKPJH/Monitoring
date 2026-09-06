# 14_export_BPU — 학습 모델 → RDK X5 BPU(NPU) `.bin` 변환

`15_rdk_x5_runtime/models/` 의 학습 모델 3개(detection.pth · pose.pt · face_state.pth)를 **ONNX → hb_mapper(INT8) → `.bin`**
으로 바꿔 다시 `15_rdk_x5_runtime/models/` 에 넣는다. 보드(15_rdk_x5_runtime)는 이 폴더에 의존하지 않는다(런타임 자립).

## 왜 hb_mapper(INT8) → `.bin` 인가

RDK X5 의 NPU(BPU, Bayes-e)는 **PyTorch/ONNX 를 직접 실행하지 못한다.** BPU 가 실행하는 유일한 형식이
D-Robotics 툴체인(`hb_mapper`)이 만든 **`.bin`(HBM)** 이다. 변환 없이 보드에서 torch 로 돌리면 NPU 는 놀고
Cortex-A55 **CPU** 만 쓰게 되어 프레임당 수백 ms~수 초가 걸린다(15_rdk 의 `BACKEND=torch` 가 그 상태).

| 단계 | 하는 일 | 왜 필요한가 |
|---|---|---|
| **ONNX export** | torch 모델 → 프레임워크 중립 그래프 | `hb_mapper` 의 입력 형식. torch 의존 제거 |
| **INT8 양자화** (`makertbin`) | float32 가중치/활성값 → 8bit 정수 | BPU 연산기는 **INT8 전용**이라 정수가 아니면 NPU 에 올릴 수 없다. 부수 효과로 모델 4배 작고, 메모리 대역폭↓, 전력↓ |
| **캘리브레이션** | 실제 프레임 ~100장으로 각 층의 값 범위 측정 | INT8 은 표현 범위가 좁아 **어느 구간을 8bit 에 매핑할지** 데이터로 정해야 정확도가 유지된다(QAT 아닌 PTQ) |
| **컴파일** | BPU 명령어로 변환, 층 융합·메모리 배치 최적화 | 보드에서 로드 즉시 실행되는 하드웨어 전용 실행파일 = `.bin` |
| **전처리 내장** | BGR→RGB 색변환·정규화를 `.bin` 안에 | 보드 CPU 가 float 변환/정규화를 안 해도 되고, 카메라 BGR uint8 을 그대로 NPU 에 투입 |

정리: **`.bin` 은 "NPU 가 실행할 수 있는 형태"** 이고, **INT8 은 그 NPU 의 요구 사항**이며, **캘리브레이션은 INT8 로 줄이면서 정확도를 지키는 절차**다.
양자화로 소수점 정밀도가 약간 줄어드니(보통 mAP −1~2%p) 변환 후 보드에서 `2_run_test`/`3_gui_test` 로 결과를 한 번 확인한다.

### YOLO 는 "분리 헤드"로 export 한다 (INT8 함정)

ultralytics 의 Detect/Pose 헤드는 마지막에 **box 좌표(0~640 px)와 class score(0~1)를 한 텐서로 concat** 한다.
INT8 로 양자화하면 그 텐서 전체가 하나의 scale(≈640/127 ≈ 5)로 표현되어 **0~1 인 score 는 전부 0 으로 깎인다** —
보드에서 `det 최대점수(임계 전) baby=0.00 face=0.00` 으로 실제 확인된 증상. 그래서 `export_onnx.py` 는 헤드의
DFL/concat/sigmoid **앞에서 잘라** 스케일별 원시 맵(`reg_s8/16/32` 64ch · `cls_s8/16/32` nc ch · pose 는 `kpt_s8/16/32` 51ch)을
**여러 출력**으로 내보내고(각각 독립 양자화), 보드는 `15_rdk_x5_runtime/src/yolo_post.raw_to_single` 로 CPU(float) 에서
DFL·앵커·sigmoid 를 복원한다 — RDK 모델주(model zoo)가 YOLO 를 다루는 표준 방식. 검증용으로 헤드 포함 단일 출력본
`*_full.onnx` 도 함께 만들며 `verify_onnx.py` 가 "분리 디코드 == 단일 출력" 을 확인한다. face_state 는 해당 없음.

## 순서

| 단계 | 어디서 | 명령 | 결과 |
|---|---|---|---|
| 1. ONNX export | PC | `..\.venv\Scripts\python.exe export_onnx.py` | `onnx\detection.onnx`(분리 헤드 6출력) `pose.onnx`(9출력) `face_state.onnx` + 검증용 `*_full.onnx` |
| 2. **검증** | PC | `..\.venv\Scripts\python.exe verify_onnx.py` | `PASS` — full 은 ultralytics 와 일치, 분리 디코드(`raw_to_single`) == full 출력 |
| 3. 캘리브레이션 | PC | `..\.venv\Scripts\python.exe calib_prep.py --n 100` | `calib\frames\` (**640x640 letterbox**, 아기 프레임 우선) · `calib\faces\` (**128x128** 크롭) — 런타임과 동일 전처리 |
| 4. **변환** | OE docker | `bash convert.sh` | `..\15_rdk_x5_runtime\models\{detection,pose,face_state}.bin` (+ `out\<모델>\*_quantized_model.onnx`) |
| 4-1. **INT8 PC 테스트** | OE docker | `python3 verify_quant.py --n 20` | float vs 양자화 ONNX 의 최대점수·감지 비교 → `PASS`(비율>0.7) 여야 보드에서도 감지됨 |
| 5. 배포 | 보드 | `15_rdk_x5_runtime` 폴더 복사 → `.env` `BACKEND=bpu` → `python3 2_run_test.py` | NPU 추론 |

### 4-1. 보드 없이 INT8 정확도 확인 — `verify_quant.py` (docker)
`hb_mapper makertbin` 이 `out/<모델>/<모델>_quantized_model.onnx` 를 남기는데, 이는 보드 `.bin` 과 **수치적으로 동일한 양자화 모델**이다.
docker 안의 `HB_ONNXRuntime` 으로 이걸 x86 에서 돌려 float ONNX 와 같은 프레임으로 비교한다(후처리는 보드와 같은 `yolo_post`).
```powershell
docker run --rm -it --platform linux/amd64 `
  -v D:\Code\Monitoring\IoT-Monitoring\media:/work -w /work/14_export_BPU `
  openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8 python3 verify_quant.py --n 20
```
| quant/float 최대점수 비율 | 판정 | 다음 |
|---|---|---|
| > 0.7 | 양자화 정상 | 보드에서만 안 되면 보드 입력/런타임 쪽 (`[vision_bpu]` 로그·`3_1_pc_live_test` 비교) |
| 0.05 ~ 0.7 | 양자화가 점수를 깎음 | `calib_prep.py` 로 **아기 프레임 위주·letterbox** 캘리브레이션 재생성 → `convert.sh` 재실행. yaml `calibration_type` 을 `kl`/`max` 로 바꿔 비교 |
| < 0.05 | 점수 사실상 0 | `onnx/<모델>.onnx` 가 분리 헤드(출력 6/9개)인지, 캘리브레이션 입력 형식(yaml `input_type_*`) 점검 |

### OE(OpenExplorer) docker — x64 Windows / x64 리눅스 공통

툴체인(`hb_mapper`)은 D-Robotics 공식 이미지 **`openexplorer/ai_toolchain_ubuntu_20_x5_cpu`** (linux/amd64, 약 1.8 GB)에
들어있다. Docker Hub 실제 태그: **`v1.2.8`**(2024-11, 최신) · `v1.2.6` · `v1.2.2` — **보유한 OE 패키지 버전과 같은 태그**를 쓴다.
(`_gpu` 이미지는 10 GB, nvidia-docker 필요 — 캘리브레이션 가속용이라 변환엔 CPU 판이면 충분.)
media 전체를 `/work` 로 마운트하면 `convert.sh` 가 `../15_rdk_x5_runtime/models/` 에 `.bin` 을 넣는다.

**Windows x64 (PowerShell, Docker Desktop 실행 중이어야 함):**
```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\14_export_BPU
docker pull openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8
docker run --rm -it --platform linux/amd64 `
  -v D:\Code\Monitoring\IoT-Monitoring\media:/work -w /work/14_export_BPU `
  openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8 bash convert.sh
```

**리눅스 x64 (Mint 등):**
```bash
cd /path/to/media/14_export_BPU
docker pull openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8
docker run --rm -it --platform linux/amd64 \
  -v "$(cd .. && pwd)":/work -w /work/14_export_BPU \
  openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8 bash convert.sh
```

- **대화형으로 점검**하려면 위 명령 끝의 `bash convert.sh` 를 `bash` 로 바꿔 들어간 뒤 `bash convert.sh` 또는
  `hb_mapper checker --model-type onnx --march bayes-e --model onnx/detection.onnx` 처럼 하나씩 실행.
- Windows 는 Docker Desktop 이 **리눅스 컨테이너 모드**(기본)여야 하고 데몬이 켜져 있어야 한다.
- (선택) 같은 일을 감싼 래퍼: `run_docker.ps1` / `run_docker.sh` / `docker compose run --rm convert` — `Dockerfile` 이 태그를 고정.
- `convert.sh` 는 모델마다 `hb_mapper checker`(지원 op 점검) → `makertbin`(양자화·컴파일) → `.bin` 복사.

## 입력 규약 (yaml ↔ 보드 코드가 맞물림)

| 모델 | 보드 투입(`input_type_rt`) | ONNX 기대(`input_type_train`) | `.bin` 내장 정규화 | 보드 전처리 |
|---|---|---|---|---|
| detection / pose | BGR uint8 NHWC | RGB NCHW | /255 | `yolo_post.letterbox(640)` 만 |
| face_state | BGR uint8 NHWC | BGR NCHW | (x−127.5)/127.5 | `cv2.resize(128)` 만 |

- 색변환(BGR→RGB)·정규화는 **모두 `.bin` 안**에 있으므로 보드는 cv2 BGR 프레임을 그대로 넣는다(`15_rdk_x5_runtime/src/vision_bpu.py`, `src/face_state_bpu.py`).
- 출력 텐서는 ONNX 와 같은 형태(detect `[1,4+nc,8400]`, pose `[1,56,8400]`, face `[1,4]` logits) → `yolo_post` 가 디코드/NMS.
- `*_info.json`(클래스명·attrs)은 15_rdk_x5_runtime/models 에 그대로 두면 `.bin` 옆에서 읽힌다.

## 참고
- yaml 의 `march: bayes-e` = RDK X5. 다른 보드(X3=bernoulli2, S100 등)는 값이 다르다.
- `preprocess_on: True` 라 캘리브레이션은 jpg 그대로 사용. OE 버전에 따라 키 이름/지원 여부가 다르면
  `hb_mapper makertbin` 이 알려주는 대로 yaml 을 조정(구조는 동일).
- 양자화 정확도는 캘리브레이션 이미지가 **실제 카메라 분포**여야 좋다 → `calib_prep.py` 는 13 dataset 프레임을 쓴다.
- `checker` 에서 CPU 로 떨어지는 op 가 있어도 동작은 한다(속도만 영향). YOLO 의 DFL/decode 부 일부가 해당될 수 있다.
