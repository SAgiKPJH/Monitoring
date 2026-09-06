# 3_classification_training — 얼굴 상태 4클래스 분류 학습

2단계가 만든 **속성별 이진 데이터셋** `dataset_<attr>\`(ImageFolder, 폴더=클래스)을
**CNN_Training_Standard** 로 학습한다. **속성마다 한 번씩** 돌려 속성당 모델 1개를 만든다.
`run_training.py` 는 CNN 표준 진입점을 env(`DATASET_PATH`/`OUTPUT_PATH`/`PARAMS`)로 호출하는 얇은 래퍼.

## 실행 (단일 멀티라벨 — 채택)

`build_dataset_multilabel.py` 가 만든 `dataset_ml\`(images + 멀티핫 labels.csv)을 **자체 멀티라벨 학습기**로 학습.
백본 1개 + N-출력(sigmoid)+BCE → 크롭 1장에 모든 속성 동시(추론 1회). CNN 표준(단일라벨) 대신 자체 구현.

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\3_classification_training
..\..\.venv\Scripts\python.exe run_training_multilabel.py                                # mobilenet_v2
..\..\.venv\Scripts\python.exe run_training_multilabel.py --params src\params_resnet18.json  # resnet18
```
- 산출물: `output_ml_<네트워크>\best.pth` + `meta.json`(network·input·attrs·BGR). clip 단위 train/val 분리(누수 방지).
- params(network_name·input_size·epoch·batch·lr·train_ratio) 재사용. mobilenet_v2 / resnet18(둘 다 input 128).

---

## (대안) 실행 — 속성별 이진

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\3_classification_training
..\..\.venv\Scripts\python.exe run_training.py --dataset_path .\dataset_eyes_open
..\..\.venv\Scripts\python.exe run_training.py --dataset_path .\dataset_mouth_open
..\..\.venv\Scripts\python.exe run_training.py --dataset_path .\dataset_mouth_covered
..\..\.venv\Scripts\python.exe run_training.py --dataset_path .\dataset_frown

# 네트워크 비교: resnet18 로도 학습(출력이 네트워크명으로 분리됨)
..\..\.venv\Scripts\python.exe run_training.py --dataset_path .\dataset_eyes_open --params src\params_resnet18.json
```

- 네트워크: 기본 `src\params.json`(**mobilenet_v2**) / `--params src\params_resnet18.json`(**resnet18**). 둘 다 input 128·RDK X5 친화.
- 출력은 자동으로 `output_<데이터셋명>_<네트워크>\best\model.pth` 로 분리(속성·모델별로 안 겹침).
- `src\params.json`: network **`mobilenet_v2`** · input **128** · epoch 40 · Adam · GPU · **AMP off**(GTX 1650).
  **RDK X5(BPU) 친화** 선택 — InceptionV3는 무겁고 양자화가 까다로워 제외. resnet18 도 대안.
  더 필요한 백본은 CNN_Training_Standard 의 `Pytorch_Classification_Models.py` 에 추가 가능.
- 각 모델은 그 속성의 **0/1(있음/없음)** 이진 분류. 추론 시 여러 모델을 합쳐 상태 판단.

## 파일

| 파일 | 역할 |
|---|---|
| `run_training.py` | **(최상위)** CNN 표준 호출 래퍼 (`--dataset_path` 속성 데이터셋) |
| `src\params.json` | 하이퍼파라미터 |
| `dataset_<attr>\` | 2단계 `build_dataset.py` 가 속성별로 생성(0/1 ImageFolder) |

> 전제: 각 속성의 0/1 균형(특히 드문 상태: 입가림·인상 등)에 유의. 부족하면 그 상태 크롭을 더 모아 라벨.
> 멀티라벨을 한 모델로 하려면 별도의 멀티라벨 학습 표준이 필요(현재는 속성별 단일라벨).
