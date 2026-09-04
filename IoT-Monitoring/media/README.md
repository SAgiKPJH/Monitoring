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

## 🚀 데이터 파이프라인 ①→⑤ (get_dataset)

모든 명령은 이 폴더 기준입니다 (`cd D:\Code\Monitoring\IoT-Monitoring\media`).
자세한 설명·옵션은 [get_dataset/PIPELINE.md](get_dataset/PIPELINE.md) 참고.

```powershell
# ① .media 획득 — SD카드에서 복구/카빙 (⚠️ 관리자 PowerShell · 이미 폴더에 있으면 생략)
.\.venv\Scripts\python.exe get_dataset\recover\sd_recover.py E: --carve --carve-format media --out D:\carved --carve-limit 0

# ②＋③ mp4 변환 + 변화량 획득 — 한 번에 (증분, 재실행 안전. ④까지 이어서 실행됨)
.\.venv\Scripts\python.exe get_dataset\motion_filter.py auto D:\carved
#   결과: D:\carved\Convert\ (mp4) · D:\carved\motion_scores.txt (파일별 변화량)

# ④ 정적 영상 제거 + 8초 컷 → Cut + 크기 조정 → resized  (auto 에 포함 · 단독 재실행은 아래)
.\.venv\Scripts\python.exe get_dataset\motion_filter.py export D:\carved\Convert D:\carved\Cut
.\.venv\Scripts\python.exe get_dataset\motion_filter.py resize D:\carved\Cut D:\carved\resized --width 480
#   결과: D:\carved\Cut\ (원본 화질, 비디오·오디오 8초 컷) · D:\carved\resized\ (480x270, Cut 보존)

# ⑤ 추가 축소 (학습용 240x136)
.\.venv\Scripts\python.exe get_dataset\motion_filter.py resize D:\carved\resized D:\carved\resized_2 --width 240

# 💡 Cut/resized 에서 직접 지운 영상은 exclude.txt 에 자동 등록되어 다시 생성되지 않음
# 💡 검수용 격자 모자이크: get_dataset\grid_mosaic.py (PIPELINE.md 참고)
```

## 🧠 YOLO baby 감지 — 부트스트랩 루프 (detection/yolo_train)

**Training_Standard 규격 준수**: 학습 로직은 `D:\Code\Training_Standard\Training Standard\OD_Training_Standard\`,
추론 로직은 `...\Inference Standard\OD_Inference_Standard\` — 이 저장소에는 라벨링 툴과 얇은 래퍼만 있음.
채널은 학습·추론·배포 전부 **BGR 통일**. 상세: [detection/yolo_train/README.md](detection/yolo_train/README.md)

```powershell
# ⑥ 사전학습 실측 (선택) — COCO person/pose 가 이 도메인에서 되는지
.\.venv\Scripts\python.exe detection\yolo_train\test_pretrained.py        # 실측: n 31% / m 77%
.\.venv\Scripts\python.exe detection\yolo_train\test_pretrained_pose.py   # 실측: 관절 2~3/17 — 사용 불가

# ⑦ 라벨 확보 — 의사라벨(자동) + 수동 보강
.\.venv\Scripts\python.exe detection\yolo_train\auto_label.py --n-clips 200   # yolo11m 라벨 공장 → D:\carved\yolo_baby
#   검수: D:\carved\yolo_baby\_preview_auto\ 몽타주 → 잘못된 것 삭제
.\.venv\Scripts\python.exe detection\label_tool\label_tool.py                 # 수동 라벨링 (이불 속·네거티브 x키)
.\.venv\Scripts\python.exe detection\pose_label_tool\pose_label_tool.py       # 포즈(COCO 17 관절) 라벨링 → D:\carved\yolo_baby_pose

# ⑧ 학습 (OD_Training_Standard 진입점 호출) → D:\carved\yolo_baby_output\best\
.\.venv\Scripts\python.exe detection\yolo_train\run_training.py --params detection\yolo_train\params_local_cpu.json
#   Colab 은 detection\yolo_train\train_baby_yolo.ipynb (동일 진입점)

# ⑨ 결과 확인 — 표준 추론 / 라이브 뷰어
.\.venv\Scripts\python.exe detection\yolo_train\run_inference.py <이미지폴더>       # → pred_out\
.\.venv\Scripts\python.exe detection\yolo_train\live_viewer.py --url "http://172.30.1.42:1984/api/frame.jpeg?src=camera1"
#   go2rtc 라이브 (1/2 축소, 감지+포즈 오버레이) · 키: d/p 토글, s 스크린샷, q 종료
#   RTSP 미개방 환경이라 frame.jpeg 폴링 사용 — mp4 파일 경로를 주면 파일로도 시험 가능

# ⑩ 배포 — ONNX → RDK X5 (rdk_x5/README.md)
.\.venv\Scripts\python.exe detection\yolo_train\export_onnx.py D:\carved\yolo_baby_output\best\model.pth
```

1차 실측(2026-09-04): 의사라벨 85장 학습 → 어려운 벤치 13장에서 사전학습 nano 31% → **파인튜닝 62%**(conf 0.20),
빈 침대 오탐 0, 어른 오인 0, 라이브 정탐 확인. 다음 사이클 = auto_label 확장(--n-clips 500 --conf 0.4) + 재학습.

## 🎞 클립 멀티라벨 트랙 (detection/notebooks — 비교군·연구용)

```powershell
.\.venv\Scripts\python.exe detection\prepare_dataset.py        # → D:\carved\dataset (Drive 업로드용)
```
이후 `D:\carved\dataset` 을 Drive `BabyMon/dataset` 에 올리고 `detection/notebooks` (라벨링·베이스라인·label_free
무라벨 10종·HD판 notebooks_original)을 Colab에서 실행. 라벨 체계·모듈 설계(M1~M4)·논문 인용·실측 결과는
[detection/README.md](detection/README.md) · [detection/RUN_ORDER.md](detection/RUN_ORDER.md) ·
결과 보고서 `detection/notebooks_result/Result.md`.
