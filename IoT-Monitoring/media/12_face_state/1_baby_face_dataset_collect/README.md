# 1_baby_face_dataset_collect — 얼굴 크롭 수집 (라벨링 없음)

8의 2클래스 모델로 **baby_face** 를 감지해 **얼굴만 크롭**해 `crops\` 에 모은다.
(auto-label 의 얼굴 박스를 잘라 모으는 것과 동일 개념. **라벨링은 2단계**에서.)

## 실행

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\1_baby_face_dataset_collect
..\..\.venv\Scripts\python.exe collect.py --n-clips 200          # carved-08 클립에서
..\..\.venv\Scripts\python.exe collect.py --src <이미지폴더> --images   # 이미지 폴더에서
```

| 옵션 | 기본 | 뜻 |
|---|---|---|
| `--src` | `D:\carved-08\Cut` | 클립 폴더(또는 `--images` 로 이미지 폴더) |
| `--model` | `..\..\8_detection_2class_train\output\60\model.pth` | baby_face 감지 모델 |
| `--n-clips` | 200 | 처리 클립/이미지 수 (0=전체) |
| `--conf` | 0.5 | baby_face 채택 conf |
| `--margin` | 0.25 | 박스 확장 비율(얼굴 여유) |
| `--min-size` | 48 | 이보다 작은 얼굴(px)은 버림(눈/입 판별 불가) |

→ `crops\<클립>_f####_<i>.jpg`. 다음: `..\2_classification_labeling\grid_label.py` 로 라벨링.
