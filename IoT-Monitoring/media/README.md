# media — 카메라 녹화 복구·정제 파이프라인 + 아기 상태 감지 모델

```
[get_dataset]  SD카드 ──▶ .media ──▶ Convert/*.mp4 ──▶ Cut · resized · resized_2        (데이터 확보)
[detection]    의사라벨/수동라벨 ──▶ OD_Training_Standard 학습 ──▶ ONNX ──▶ RDK X5 배포  (YOLO baby 감지)
[live]         go2rtc(:1984) ──▶ live_viewer (1/2 축소, 감지+포즈 오버레이)              (실시간 확인)
```

## 폴더 구조 (비즈니스별)

| 폴더/파일 | 역할 | 안내 문서 |
|---|---|---|
| `get_dataset/` | **① .media 획득 → ⑤ 크기 조정** 데이터 파이프라인 전체 (복구·변환·변화량·격자검수) | [get_dataset/PIPELINE.md](get_dataset/PIPELINE.md) |
| `detection/` | **아기 상태 감지 모델** — 라벨 체계, Colab 노트북(헤비/경량), YOLO 라벨링·학습 툴 | [detection/README.md](detection/README.md) |
| `rdk_x5/` | **RDK X5 ROS2 감지 노드** — go2rtc 스트림 → YOLO(baby) → `present`/`detections` 토픽 | [rdk_x5/README.md](rdk_x5/README.md) |
| `ffmpeg/` | 공용 ffmpeg 바이너리 (두 폴더의 스크립트가 자동 탐색) | |
| `DCIM/` | 카메라에서 직접 복사한 .media 원본 | |
| `VENV.md` | 가상환경(.venv) 사용법 | |

# 조건 (아기에게 볼 것)
1. 코가 가려졌는가? (이불로) (막히고 있는가?)
2. 자주 움직이는가?
3. 눈을 뜨고 있는가?
4. 소리 -> 먹고싶은건지 뭔지
5. 울려고 하는가? (인상을 쓰는가)
6. 손을 꺼냈는가?
7. 토의 징조 - 입에서 물이 나오는가?, 토를 했는가?