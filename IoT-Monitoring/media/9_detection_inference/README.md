# 9_detection_inference — 학습 2클래스 모델 추론 (배포/운영)

학습한 baby+baby_face 모델을 **실제로 돌리는** 폴더. 두 용도로 나뉜다.

```
9_detection_inference/
├── live/       # 개발 PC에서 실시간 확인 (창)
│   ├── live.py            # go2rtc 스트림 → 640x640 → 추론 → 창 표시
│   ├── detector.py        # .pth 로드(model_info.json로 nc·클래스 자동) + 오버레이
│   ├── stream_source.py   # go2rtc fMP4 실시간 + 스냅샷 폴백
│   └── models/{best,60}/  # 번들 모델 2종
└── Baby-Timelapse/    # Mint PC에서 Docker 상시 구동 (아기 타임랩스)
    └── …                  # 매시간 baby 감지 시 원본 저장 · Baby-Timelapse/README.md
```

## live/ — 실시간 창 (개발 PC)

```powershell
cd 9_detection_inference\live
..\..\.venv\Scripts\python.exe live.py     # q/ESC 종료 · s 스크린샷
```
설정은 `live.py` 상단: `MODEL`(best/60), `IMGSZ=640`, `CONF=0.8`, `STREAM_URL`.

## Baby-Timelapse/ — 타임랩스 캡처 (Docker)

매시간 스트림에서 baby 감지 시 원본 저장. 리눅스(Mint) + Docker.
```bash
cd 9_detection_inference/Baby-Timelapse && docker compose up -d --build
```
자세한 건 `Baby-Timelapse/README.md`.

## 공통

- 모델은 각 폴더에 **번들**(자체 완결). 클래스명은 `model_info.json` 에서 자동(baby / baby_face).
- 학습·라벨은 `..\8_detection_2class_train`. 이 폴더는 추론 전용.
