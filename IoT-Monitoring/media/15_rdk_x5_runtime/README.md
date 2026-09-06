# 15_rdk_x5_runtime — RDK X5 실시간 모니터링

- 카메라 스트림 -> 아기를 모니터링 -> 알람
- 순서는 직렬 순차 실행

## 파이프라인 (순차)

1. YDIF: **움직임 감지**, 1초 1회
2. yolo-detection: **baby 존재 감지**, 기본 **5분 1회**, 단 1에서 움직임이면 즉시 측정
3. mobilenet-classification: **얼굴 상태**, baby_face 크롭 → 눈뜸/입벌림/입가림/인상. **30초 관찰 창**에서 눈뜸·입가림·인상이 관찰되면 **속성별 알람**
4. yolo-pose: **pose 움직임 감지**, 30초 관찰 창에서 움직임이 관찰되면 **알람**

설정은 `monitoring.py` 상단에서 조정(얼굴 속성 임계는 `src/face_thr.py`, 쿨다운은 `.env`).

| 이름 | 설명 | 기본 값 |
| --- | --- | ------- |
| `MOTION_INTERVAL` | 움직임 감지 주기(초) | 1 |
| `MOTION_THR` | YDIF 움직임 임계(folder 11 로 캘리브레이션) | 0.5 |
| `BABY_INTERVAL` | baby 감지 기본 주기(초) — 움직임 시 즉시 | 300 (5분) |
| `BABY_CONF` / `FACE_CONF` | baby / baby_face 감지 conf | 0.8 / 0.8 |
| `FACE_ALARM_ATTRS` | 관찰되면 알람을 내는 얼굴 속성(알람 key `face:<속성>`, 쿨다운도 속성별) | mouth_covered, frown, eyes_open |
| `ATTR_THR` (`src/face_thr.py`) | 얼굴 속성별 on 임계 | eyes_open 0.9 · mouth_covered 0.7 · mouth_open 0.7 · frown 0.8 |
| `POSE_MOVE_THR` | keypoint 이동량 임계(대각선 비율, 13/5 뷰어 2.2%) | 0.022 |
| `OBS_SEC` / `OBS_RATIO` | 관찰 창(초) / 창 안 폴의 이 비율 이상에서 관찰되면 알람 | 30 / 0.5 |
| `POLL_SEC` | 관찰 폴링 간격(초) | 2 |
| `ALARM_COOLDOWN` (`.env`) | 동일 알람 최소 간격(초) | 300 (5분) |

## 테스트 순서 (1 → 2 → 3 → monitoring.py)

| 순서 | 파일 | 어디서 | 확인하는 것 |
|---|---|---|---|
| 1 | `1_slack_send_test.py` | PC·보드 | `.env` 의 Slack 웹훅/Grafana 로 **테스트 알람 1건 실제 전송**(쿨다운 무시, 스냅샷은 `alarms\` 저장) |
| 2 | `2_run_test.py` | PC·보드 | 모델 로드 → 소스 → 프레임 N개로 움직임·감지·얼굴상태·pose 를 1회씩 실행, **단계별 ms 출력**(알람 X). 보드에서 `BACKEND=bpu` 로 돌리면 NPU 지연 확인 |
| 3 | `3_gui_test.py` | PC 창 **또는 보드→브라우저** | 박스·얼굴 속성·골격·YDIF·pose 이동량 실시간 오버레이. PC: 창(`space` 일시정지 `q` 종료). **보드(헤드리스)**: `python3 3_gui_test.py`(창 불가 시 자동 `--serve 8080`) 후 Windows 브라우저에서 `http://<보드IP>:8080/` (MJPEG, 표준 라이브러리만) |
| 3-1 | `3_1_pc_live_test.py` | **PC** | 같은 실시간 스트림을 **torch(float)** 로 3과 똑같이 창에 표시 → 보드(BPU INT8) 화면과 나란히 비교. PC 는 잡는데 보드만 못 잡으면 `.bin` 입력형식/양자화 문제, PC 도 못 잡으면 모델/장면 문제 |
| 끝 | `monitoring.py` | 보드(또는 PC) | 실제 운용 — 순차 상태머신 + 30초 관찰 판정 + 알람 |

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\15_rdk_x5_runtime
..\.venv\Scripts\python.exe 1_slack_send_test.py
..\.venv\Scripts\python.exe 2_run_test.py --src D:\carved-08\Cut\<clip>.mp4 --n 5   # --src 생략 시 .env STREAM_URL
..\.venv\Scripts\python.exe 3_gui_test.py --src D:\carved-08\Cut\<clip>.mp4 --win 1280x720
..\.venv\Scripts\python.exe monitoring.py
```
셋 다 `monitoring.py` 의 함수·설정·백엔드 선택을 그대로 import 하므로, 테스트가 통과하면 운용도 같은 코드로 돈다.

## 실행 (dev, 현재 PC)

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\15_rdk_x5_runtime
cp .env_sample .env          # STREAM_URL·SLACK_WEBHOOK·GRAFANA_URL/TOKEN 채우기
..\.venv\Scripts\python.exe monitoring.py
```
- 모델: **`models\` 안에** `detection.pth`(+`detection_info.json`) · `face_state.pth`(+`face_state_info.json`) ·
  `pose.pt`. **이 폴더만으로 독립 실행**(다른 번호 폴더 코드/모델에 의존하지 않음). pose.pt 없으면 4단계 건너뜀.
- 알람: `src/alarm.py` 가 Slack Webhook + Grafana annotation 전송(미설정 시 콘솔만, 쿨다운 있음).
- `detection.pth` 는 **2클래스(baby, baby_face)** 여야 3단계(얼굴상태)가 baby_face 크롭을 얻는다
  (`detection_info.json` 의 클래스 수와 .pth 가 일치해야 로드됨).

## 알람 (Slack Webhook + Grafana) — 규칙은 `알람규칙.md`

- **텍스트**를 보내고, 스냅샷 이미지는 항상 `alarms\` 에 로컬 저장(웹훅은 파일 첨부 불가 → 경로만 안내).
- **동일 알람은 5분 쿨다운**(`ALARM_COOLDOWN`, key: face/pose).

| env | 뜻 |
|---|---|
| `SLACK_WEBHOOK` | Slack Incoming Webhook(텍스트). 미설정 시 콘솔만 |
| `GRAFANA_URL` | 예 `https://ajusoft.net/grafana` (`/api/annotations` 주석) |
| `GRAFANA_TOKEN` | Grafana API/서비스계정 토큰(annotations 쓰기) |
| `ALARM_COOLDOWN` | 동일 알람 최소 간격(초, 기본 300=5분) |

## RDK X5 배포 (BPU/NPU) — `BACKEND=bpu`

**보드 작업 폴더 = `/home/sunrise/JJU/Monitoring`** — 아래 명령, systemd 유닛(`deploy/*.service`), ROS2 `runtime_dir` 기본값,
`scp` 대상이 모두 이 경로 기준. 다른 곳에 두면 `install_service.sh` 는 자동 치환하고, ROS2 는 상위 폴더에서 `monitoring.py` 를 찾아 맞춘다.

1. **PC**: `..\14_export_BPU` 에서 ONNX export → `verify_onnx.py` PASS → `calib_prep.py` → (OE docker) `convert.sh`
   → `models\detection.bin` `pose.bin` `face_state.bin` 이 이 폴더에 생성됨 (그 폴더 README 참고).
2. **보드**: 이 폴더 **통째로** 복사(`models\` 의 `.bin` + `*_info.json` 포함) → `.env` 에 `BACKEND=bpu`.
   ```bash
   pip3 install -r requirements.txt     # numpy·opencv-python-headless 뿐 — torch/ultralytics 불필요, hobot_dnn 은 보드 기본 제공
   python3 2_run_test.py                # NPU 단계별 지연 확인
   python3 monitoring.py
   ```
   ※ detection/pose `.bin` 은 **분리 헤드 export**(14_export_BPU `export_onnx.py` 기본)로 변환한 것이어야 한다 — 헤드 포함
   단일 출력으로 변환하면 INT8 양자화에 score 가 0 으로 깎여 감지가 전혀 안 된다(`det 최대점수 0.00`). 출력 개수는
   로드 로그 `[vision_bpu] … 출력 분리 출력 6개/9개` 로 확인. face_state 는 무관.
3. `BACKEND=bpu` 면 `src/vision_bpu.py` / `src/face_state_bpu.py`(pyeasy_dnn) 가 로드되고 **torch 는 import 되지 않는다**.
   전처리(letterbox·BGR uint8 그대로)와 후처리(`yolo_post`)는 PC 에서 onnxruntime 으로 검증한 **동일 코드**.
   색변환·정규화는 `.bin` 컴파일 시 내장(14_export_BPU 의 yaml) — 보드 코드는 리사이즈만 한다.
카메라 입력은 go2rtc(HTTP) 또는 로컬 MIPI/USB 카메라. 상태머신·알람(src/alarm.py)·스케줄·`pose_motion` 지표는 백엔드와 무관.

**지연/감지 진단 (3_gui_test HUD · 2_run_test 출력)**
- `age`(최신 프레임 수신 후 경과): 수십 ms 면 정상. 실시간 소스는 `LatestFrameReader` 가 grab() 만 반복해 최신 프레임만 유지.
- `rx`(수신 fps): 카메라 fps(현재 ~26) 보다 낮으면 보드 CPU 가 1080p H.264 디코드를 못 따라가 지연이 누적된다 →
  카메라/go2rtc 쪽에서 fps·해상도를 낮추거나 저해상도 서브스트림 src 를 쓴다. (go2rtc `/api/stream.mjpeg` 는 이 환경에서
  열리지 않음 — go2rtc 호스트에 ffmpeg 필요.) go2rtc fMP4 자체의 GOP/프래그먼트 지연(~1–2 s)은 코드로 못 줄인다.
- `[vision_bpu] … 입력 shape/layout/type → 투입 NCHW_I8`: **RDK X5 실측(2026-09-06, `bpu_input_probe.py`)** — .bin 속성은
  `NHWC/uint8` 로 보고되지만 pyeasy_dnn 에는 **NCHW(1,3,H,W) int8(uint8−128)** 로 넣어야 PC 양자화 모델과 같은 점수
  (0.924 = PC 0.924). NHWC uint8 로 넣으면 0.000. 기본값이 `nchw_i8` 이고 `.env` 의 `BPU_INPUT` 으로 바꿀 수 있다.
  다른 보드/OE 버전에서 감지가 0 이면 `python3 bpu_input_probe.py` 로 11개 형식을 한 번에 시험해 정답 형식을 찾는다.
- `det 최대점수(임계 전)`: 아기가 있는데 0.1 미만이면 .bin 입력형식/양자화 문제, 0.3~0.7 이면 conf 부족(임계/데이터). PC 의
  `3_1_pc_live_test.py`(torch float) 와 같은 장면을 비교하면 원인이 갈린다.
- **정지 이미지 A/B (가장 결정적)**: `ref_frames/` 에 PC 에서 점수를 아는 프레임 3장 + `ref_scores.txt`(float/INT8 기준값)가 있다.
  보드에서 `python3 2_run_test.py --img ref_frames` → 같은 이미지의 `det baby/face` 최대점수를 기준값과 비교.
  **비슷(±0.1)** 이면 보드 파이프라인 정상 → 라이브에서 안 잡히는 건 장면/모델 한계(야간·이불·각도 → 학습 데이터 보강).
  **0.0x** 이면 보드 입력/런타임 문제 → `hrt_model_exec model_info --model_file models/detection.bin` 출력과 `[vision_bpu]` 로그를 확인.

### 보드 `models/` 구성 (BPU)

| 파일 | 역할 | 보드 | PC(export·torch 개발) |
|---|---|---|---|
| `detection.bin` | 감지(분리 헤드 6출력) | 필수 | — |
| `detection_info.json` | 클래스 이름/개수(`baby`, `baby_face` → nc=2). `.bin` 옆에서 읽음 | **필수** | 필수(.pth 재구성용) |
| `pose.bin` | pose(분리 헤드 9출력) | 필수 | — |
| `face_state.bin` | 얼굴상태 | 필수 | — |
| `face_state_info.json` | attrs 4개·`input_size` 128·network. `.bin` 옆에서 읽음 | **필수** | 필수 |
| `detection.pth` `face_state.pth` `pose.pt` | torch 원본 | 불필요 | 필수(14_export_BPU 의 export 원본, `BACKEND=torch`) |

`_info.json` 은 `.bin` 과 **이름이 짝**이어야 한다(`<stem>_info.json`). 원본은 8(`output/60/model.pth` + `model_info.json`),
12(`output_ml_mobilenet_v2/best.pth` + `meta.json`), 13(`output/<run>/weights/best.pt`)에서 복사해 이름만 바꾼 것.

## 자동 실행 — systemd(권장) · ROS2(선택)

**둘은 대체재가 아니라 층이 다르다.** systemd = 프로세스 관리(부팅 자동 실행·크래시 재시작·journal 로그, 의존성 0),
ROS2 = 프로세스 간 통신(토픽). `monitoring.py` 는 단독 스크립트라 **운용은 systemd 만으로 충분**하고,
ROS2 는 다른 ROS2 노드(TROS 카메라 노드 등)와 토픽으로 연동하거나 `ros2 topic echo` 로 상태를 볼 때만 쓴다.
ROS2 노드로 띄우더라도 부팅 자동 실행은 결국 systemd(`baby-monitor-ros2.service`)가 한다.

### systemd (권장)
```bash
cd /home/sunrise/JJU/Monitoring
bash deploy/install_service.sh              # 유닛의 경로/사용자를 실제 값으로 치환 → /etc/systemd/system → enable --now
systemctl status baby-monitor               # 상태
journalctl -u baby-monitor -f               # 로그(실시간)
sudo systemctl restart baby-monitor         # .env 바꾼 뒤 재시작
```
`deploy/baby-monitor.service`: `python3 monitoring.py`, `Restart=always`(5초), 네트워크 준비 후 시작.

### ROS2 (선택) — `ros2_ws/src/baby_monitor`
monitoring.py 는 그대로 두고 rclpy 노드가 스레드로 실행하며, `alarm.send` 를 감싸 **`/baby_monitor/alarm`**(String JSON) 을 발행하고
1초마다 **`/baby_monitor/status`**(alive·uptime·alarms·backend) 하트비트를 낸다.
```bash
source /opt/tros/humble/setup.bash          # RDK X5 TROS (버전에 따라 /opt/tros/setup.bash)
cd ./ros2_ws && colcon build --symlink-install && source install/setup.bash
ros2 launch baby_monitor monitor.launch.py  # runtime_dir 자동 탐지(ros2_ws 상위에서 monitoring.py 찾음). 다른 곳이면 runtime_dir:=/경로 또는 env BABY_MONITOR_DIR
ros2 topic echo /baby_monitor/alarm         # 다른 터미널
bash deploy/install_service.sh ros2         # 부팅 자동 실행이 필요하면(일반 서비스와 둘 중 하나만)
```

## 스펙(Spec) — 추론 시간 실측

`2_run_test.py` 로 측정(2026-09-06). 입력 1920x1080(go2rtc fMP4) → 감지/pose 는 640 letterbox, face 는 128 크롭.
아기 미검출 상태(faces=0)라 **face_state 추론 시간은 미측정**. 첫 프레임은 워밍업이라 별도 표기.

### RDK X5 — `BACKEND=bpu` (INT8 `.bin`, OE v1.2.8 · BPU 1.3.6 · HBRT 3.15.55 · DNN 1.24.5)

| 단계 | 시간 | 비고 |
|---|---|---|
| 모델 로드 detector | **365 ms** | 최초 부팅 직후 1,174 ms(파일 캐시 전) |
| 모델 로드 face_state | **72 ms** | |
| 모델 로드 pose | **146 ms** | |
| 움직임 YDIF (1920x1080→320 gray) | **~30 ms** / 프레임 | 29–34 ms, CPU(A55). 1초 1회라 부담 없음 |
| **detect** (yolo11n 2클래스, BPU) | **~105 ms** / 프레임 | 정상상태 100–120 ms, 첫 프레임 115–125 ms. 출력 `(1,6,8400,1)` float32 |
| **pose** (yolo11n-pose, BPU) | **~150 ms** / 프레임 | 정상상태 145–160 ms, 첫 프레임 160–175 ms. 출력 `(1,56,8400,1)` float32 |
| face_state (mobilenet_v2 128, BPU) | 미측정 | 아기 검출 시 재측정 |

- **한 사이클(움직임+detect+pose) ≈ 285 ms + face** → 관찰 폴링 `POLL_SEC=2초` 대비 충분한 여유. 풀 파이프라인 연속 실행 시 약 3 fps(`3_gui_test --serve` 체감 속도).
- 위 detect/pose 시간에는 letterbox 전처리 + numpy 후처리(디코드·NMS)가 포함된다(CPU). 순수 BPU 시간은 그보다 짧다.
- 출력이 float32 로 나와 역양자화(`_dequant`)는 통과 경로만 탄다.

### NPU 메모리 · BPU 사용률 (RDK X5)

RDK X5 의 BPU 는 별도 VRAM 이 없고 **ION/CMA 로 시스템 RAM 을 공유**한다. 그래서 "NPU 에 잡는 메모리" =
모델 로드 전후 **프로세스 RSS 증가량**이고, `2_run_test.py` 가 모델마다 파일 크기 · RSS 증가(MB) · 전체 RAM 대비 % 를 출력한다
(`[모델 로드]` 줄). BPU 사용률은 `/sys/devices/system/bpu/bpu0/ratio` 를 추론 직후 읽어 `BPU 사용률 N%` 로 표시(없으면 생략).

보드 실측(2026-09-06, `python3 2_run_test.py --n 5`, RDK X5 4 GB — `MemTotal` **3062 MB**):

| 모델 (`.bin`, INT8) | 파일 크기 | 로드 시 RSS 증가 | 전체 RAM 대비 | 로드 시간 |
|---|---|---|---|---|
| detection (yolo11n 2클래스) | **4.4 MB** (float .pth 10.1) | **+30.7 MB** (DNN 런타임 초기화 포함) | 1.0% | 386 ms |
| face_state (mobilenet_v2 128) | **2.6 MB** (float .pth 8.7) | **+5.1 MB** | 0.2% | 76 ms |
| pose (yolo11n-pose) | **5.6 MB** (float .pt 5.9) | **+0.1 MB** (BPU 버퍼는 ION/지연 할당) | 0.0% | 146 ms |
| **합계** | **12.6 MB** (float 24.7) | **+36.0 MB** | **1.2%** | — |

- 프로세스 RSS: 모델 로드 직후 **84 MB** → 5프레임 추론 후 **201 MB (6.6%)**. 1080p 프레임·letterbox·출력·OpenCV 버퍼가 추론 시 붙으므로
  **운용 계획 기준은 ~200 MB(≈7%)**. 첫 모델 로드 값에는 DNN 런타임 초기화가 얹히고, BPU 모델 메모리는 ION/CMA 에서 잡혀 RSS 에 다 보이지 않는다.
- **BPU 사용률 5–7%** (`/sys/devices/system/bpu/bpu0/ratio`, 2_run_test 를 쉬지 않고 돌릴 때). 한 사이클의 대부분이 CPU(전·후처리, 디코드)라
  NPU 여유가 크고, 운용(monitoring)은 대부분 대기라 평균 ~0%. 보조 확인: `hrut_somstatus`(BPU ratio·온도), `free -m`.
- 재측정: 보드에서 `python3 2_run_test.py --n 5` → `[모델 로드]`/`BPU 사용률`/`[메모리]` 줄.

### PC 참고 — `BACKEND=torch` (Windows, i7-9750H + GTX 1650, CUDA)

| 단계 | 시간 | 비고 |
|---|---|---|
| 모델 로드 detector / face / pose | 0.7–2.1 s / 0.14 s / 0.08 s | .pth→yolo11n 재구성 포함 |
| 움직임 YDIF | 3–15 ms | |
| detect / pose | ~20 ms / ~30 ms (워밍업 후) | 첫 프레임 detect 0.8–1.8 s(CUDA 초기화) |

> 갱신 방법: 보드에서 `python3 2_run_test.py --n 10` 을 아기가 있는 시간대에 돌려 face_state 값을 채우고 이 표를 수정.

## 파일

| 파일 | 역할 |
|---|---|
| `1_slack_send_test.py` | 알람 채널 테스트(테스트 알람 1건 실제 전송) |
| `2_run_test.py` | 파이프라인 1회 실행 + 단계별 소요시간(알람 X, PC·보드 공통) |
| `3_gui_test.py` | GUI 시각 검증 — PC 창, 또는 보드에서 자동 `--serve 8080`(MJPEG) → Windows 브라우저. 감지 후보 전부·분류 막대·썸네일·골격·HUD(시각/age/rx/최대점수) |
| `3_1_pc_live_test.py` | PC 에서 같은 실시간 스트림을 torch(float)로 3과 동일하게 표시(3_gui_test 재사용) → 보드(BPU) 화면과 비교 |
| `monitoring.py` | **실제 운용** — 순차 상태머신(움직임→감지→얼굴상태→pose, 30초 관찰 판정, 속성별 알람 호출) |
| `src/alarm.py` | Slack Webhook + Grafana 알람 전송(env·쿨다운) |
| `src/vision.py` | 감지·포즈 모델 로드(`load_detector`/`load_pose`, `<stem>_info.json` 클래스명) |
| `src/face_state.py` | 얼굴상태(멀티라벨) 로드·예측(`load_face_state`/`predict`/`ATTR_THR`) |
| `src/stream_source.py` | 입력 스트림(go2rtc fMP4/스냅샷) |
| `src/variance.py` | 움직임 감지 YDIF |
| `src/pose_motion.py` | pose 활동량(keypoint 이동량, monitor·13/5 공유 지표, torch/BPU 결과 모두 처리) |
| `src/vision_bpu.py` / `src/face_state_bpu.py` | **BPU 백엔드**(hobot_dnn pyeasy_dnn) — `BACKEND=bpu` 시 로드, torch 불필요 |
| `src/yolo_post.py` | YOLO 출력 후처리(letterbox·decode·NMS, 순수 numpy) — PC 검증·보드 공용 |
| `src/face_thr.py` | 얼굴 속성 임계 `ATTR_THR`(torch 없이 공유) |
| `models\` | torch: `detection.pth` `face_state.pth` `pose.pt` · BPU: `detection.bin` `face_state.bin` `pose.bin` (+각 `_info.json`) |
| `requirements.txt` | **보드 pip 설치 목록**(numpy·opencv-python-headless 뿐; hobot_dnn·ROS2 는 시스템 제공) |
| `deploy\` | systemd 유닛(`baby-monitor.service` 권장 · `baby-monitor-ros2.service`) + `install_service.sh` |
| `ros2_ws\` | (선택) ROS2 패키지 `baby_monitor` — monitoring 을 노드로 실행, `/baby_monitor/alarm`·`/status` 토픽 |
| `.env_sample` | 설정 템플릿(스트림·알람 채널) |
