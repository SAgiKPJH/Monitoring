# 4_detection_pretrained — 실시간 스트림 감지 + 포즈 추론

go2rtc 라이브 영상을 받아 **1/2 축소 후 감지(baby) + 포즈**를 오버레이로 확인합니다.
학습 로직은 없고, 학습된 모델로 **추론만** 하는 데모/모니터 폴더입니다.

## 실행

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\4_detection_pretrained

# ① 실시간 스트림 (go2rtc) — 창
..\.venv\Scripts\python.exe Detection_Live_Test.py          # 실시간 창 (기본)
..\.venv\Scripts\python.exe Detection_Live_Test.py shot 30  # 창 없이 30프레임 → out\

# ② 학습 이미지 5개 랜덤 추론 (모델 확인용)
..\.venv\Scripts\python.exe Detection_Sample_Test.py        # → out_sample\
..\.venv\Scripts\python.exe Detection_Sample_Test.py 10     # 개수 지정
```

- 창 키: `d`/`p` 감지·포즈 토글, `s` 스크린샷(out\), `q` 종료
- 설정은 각 파일 상단만 고치면 됩니다:
  - `Detection_Live_Test.py`: `STREAM_URL` · `DET_MODEL`/`DET_CLASSES` · `POSE_MODEL` · `SCALE` · `CONF` · `MODE`
    (기본 = **사전학습** yolo11m person. baby 파인튜닝은 주석대로 전환)
  - `Detection_Sample_Test.py`: `SRC_DIR`(학습 이미지) · `DET_MODEL`(기본 = baby 파인튜닝) · `N_SAMPLES`

## 스트림 (go2rtc)

- `STREAM_URL` 에 go2rtc 주소를 넣으면 **자동으로 실시간 fMP4**(`/api/stream.mp4`)를 씁니다.
  RTSP(:8554)가 안 열려 있어도 `:1984`만으로 1920x1080 실시간 수신 (초반 키프레임 전 프레임은 스킵).
  실패 시 스냅샷 폴링(`/api/frame.jpeg`, 저프레임)으로 자동 폴백.
- 스트림 이름 확인: `http://<호스트>:1984/streams`  (예: `camera1`)
- `STREAM_URL` 에 mp4 파일 경로를 넣으면 파일로도 시험됩니다.

## 모델

이 폴더는 **사전학습(pretrained) 모델만** 씁니다. 학습한 baby 모델 추론은 `..\6_detection_trained_inference`.

| 역할 | 기본값 | 비고 |
|---|---|---|
| 감지 | `yolo11m.pt` (COCO person) | 이름만 주면 자동 다운로드. `DET_CLASSES=[0]`(person) |
| 포즈 | `yolo11n-pose.pt` | COCO 17 사전학습 — 아기 도메인 약함(참고용). 파인튜닝 전까지 골격 부정확 |

## 구성

| 파일 | 역할 |
|---|---|
| `Detection_Live_Test.py` | 실시간 스트림 추론 (창/shot) |
| `Detection_Sample_Test.py` | 학습 이미지 N개 랜덤 추론 (모델 확인) |
| `src/stream_source.py` | go2rtc 실시간 fMP4 + 스냅샷 폴백 |
| `src/inference.py` | 감지·포즈 로드 / 추론 / 오버레이 (BGR, 클래스 필터) |
| `src/live_view.py` · `src/shot.py` | 실시간 창 루프 · 단발 캡처 저장 |

학습은 `..\5_detection_train`.

Training_Standard 규격: 전 파일 60줄 이하, BGR 무변환.

> 이 폴더가 라이브 추론의 정식 위치입니다. (구 `detection/yolo_train/live_viewer.py` 를 대체)
