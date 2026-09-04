# Baby-Timelapse — 아기 타임랩스 캡처 (Docker)

Mint PC(리눅스)에서 **Docker 컨테이너**로 상시 구동. go2rtc 스트림에서 프레임을 받아
학습 2클래스 모델로 **baby**를 감지하고, 있으면 **박스 없는 원본 사진**을 저장한다 → 시간순 타임랩스.
대부분 시간은 sleep 이라 자원을 거의 안 쓴다.

**스케줄(시간당 1장):** 저장 성공 → **1시간** 대기 · 미검출 → **10분** 뒤 재시도(잡을 때까지).
즉 매 시간 1장 저장을 목표로, 그 시점에 아기가 없으면 10분마다 다시 시도하다 잡으면 다시 1시간 쉼.

## 구성 (자체 완결 — 도커 빌드 컨텍스트)

```
Baby-Timelapse/
├── capture.py          # 매 주기: 프레임 수신 → baby 감지 → 있으면 저장/SCP 전송
├── detector.py         # .pth 로드(model_info.json로 클래스 자동) + 추론
├── stream_source.py    # go2rtc fMP4 실시간 + 스냅샷 폴백
├── models/60/          # 번들 모델 (model.pth + model_info.json)
├── Dockerfile          # CPU 전용 이미지 (ffmpeg + ultralytics + openssh)
├── docker-compose.yml  # host 네트워크 · SCP/볼륨 저장 · 재시작
└── requirements.txt
```

## 실행 (Mint PC)

```bash
cd Baby-Timelapse
docker compose up -d --build         # 빌드 후 백그라운드 상시 구동
docker compose logs -f               # 로그(감지/전송 여부) 확인
docker compose down                  # 정지
```

## 저장 방식 — ① SCP 원격 전송(기본) 또는 ② 로컬 볼륨

감지된 **원본 사진**을 원격 PC로 **SCP push**(볼륨 없이)하거나, 호스트 폴더에 로컬 저장한다.

### ① SCP — 특정 IP:경로 로 전송 (기본)

```bash
cd Baby-Timelapse
ssh-keygen -t ed25519 -f ./id_rsa -N ""             # 1) 배포용 키 생성(이 폴더에 id_rsa/.pub)
ssh-copy-id -p 22 -i ./id_rsa.pub user@192.168.0.10 # 2) 원격에 공개키 등록
cp .env_sample .env                                 # 3) 설정 복사 → .env 의 SCP_TARGET·SCP_PORT 채우기
docker compose up -d --build
```

- **개인키(`id_rsa`)만** 컨테이너에 읽기전용 마운트(데이터 볼륨 아님). 저장 즉시 원격으로 전송.
- 원격 경로는 **디렉터리(끝 `/`)** — 파일은 `baby_<시각>.jpg` 로 도착.
- `KEEP_LOCAL=0`(기본): 전송 성공 시 컨테이너 로컬본 삭제(원격만 보관). **전송 실패 시** 로컬 유지.
- **밀린 것 자동 재전송**: `captures\` 는 '아직 못 보낸' 대기함 — **재시작·매 주기 시작 때** 남은 파일을 다시 전송한다(KEEP_LOCAL=0). 서버가 잠깐 죽어도 복구되면 밀린 사진이 나간다.
- TOFU(`accept-new`)·`BatchMode`(비번 프롬프트 없이 키 인증만). 배포 전용·비번 없는 키 권장,
  원격 `authorized_keys` 에 `command=`/`from=` 제한을 두면 더 안전.

### 전송 테스트 (내 PC에서, 감지 없이)

Windows 개발 PC 에서 SCP 경로가 실제로 되는지 1회 확인:
```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\9_detection_inference\Baby-Timelapse
# 0) 먼저 수동 scp 로 SSH 접속·키 확인 (이게 되면 앱도 됨)
"hi $(Get-Date)" | Out-File -Encoding ascii testfile.txt
scp -O testfile.txt user@192.168.0.10:/home/user/baby_captures/   # -O: SFTP subsystem 없는 서버 대응
#   (커스텀 포트면 -P <포트> 추가: scp -O -P 12233 ...)

# 1) 앱 경로로 1회 전송 (FORCE_SAVE=1 → 아기 없어도 현재 프레임을 강제 전송)
$env:RUN_ONCE="1"; $env:FORCE_SAVE="1"; $env:CONF="0.5"
$env:SCP_TARGET="user@192.168.0.10:/home/user/baby_captures/"
$env:KEEP_LOCAL="1"      # 테스트: 로컬 captures\ 에도 남겨 확인
..\..\.venv\Scripts\python.exe capture.py
```
- 원격 폴더에 `test_<시각>.jpg` 가 생기면 성공. `SCP_KEY` 기본값은 Windows 에 없어 **기본 SSH 키/에이전트**를 쓴다(0번이 그걸 검증).
- `FORCE_SAVE`·`KEEP_LOCAL` 은 **테스트 전용** — 실제 운영(docker)에서는 안 켠다.

### ② 로컬 볼륨 — SCP 안 씀

`docker-compose.yml` 에서 `SCP_TARGET` 을 비우고 볼륨 주석을 해제:
```yaml
    volumes:
      - ./sample_path:/data/captures   # ← 원하는 호스트 경로(절대경로 권장)
```
> `sample_path` 처럼 `.`/`/` 없이 쓰면 docker 가 **named volume** 으로 오해하니 `./` 나 절대경로로.

## 설정 (`.env` — `cp .env_sample .env` 후 값 채우기)

로컬·도커 공통으로 `.env` 에서 읽는다(로컬: capture.py 가 로드, 도커: compose `env_file`). `.env` 는 커밋 금지.

| 변수 | 기본 | 뜻 |
|---|---|---|
| `STREAM_URL` | go2rtc camera1 | 스트림 주소 |
| `SUCCESS_INTERVAL_SEC` | `3600` | 저장 성공 후 대기(1시간). 하루 1회면 `86400` |
| `RETRY_INTERVAL_SEC` | `600` | 아기 없을 때 재시도 간격(10분) |
| `CONF` | `0.8` | baby 채택 임계(높을수록 확실한 것만 저장) |
| `BABY_CLASS` | `0` | 감지 대상 클래스(0=baby, 1=baby_face) |
| `MODEL` | `models/60/model.pth` | 번들 모델 경로 |
| `RUN_ONCE` | `0` | `1`이면 1회만 캡처 후 종료(테스트·외부 cron) |
| `SCP_TARGET` | (빈값) | 채우면 SCP 전송: `user@IP:/원격/경로/` |
| `SCP_PORT` | `22` | 원격 SSH 포트 |
| `SCP_KEY` | `/keys/id_rsa` | 컨테이너 내 개인키(마운트 위치) |
| `KEEP_LOCAL` | `0`(compose) | SCP 성공 후 로컬 유지 여부(`1`=유지) |
| `FORCE_SAVE` | `0` | 테스트용: 감지 없어도 저장/전송(`RUN_ONCE` 와 함께) |
| `SCP_LEGACY` | `1` | `-O`(레거시 SCP). SFTP subsystem 없는 서버 대응. SFTP-only 서버면 `0` |

- 컨테이너 시작 직후 1회 즉시 시도. 이후 **저장하면 1시간, 못 잡으면 10분** 간격(적응형).
- 감지는 원본 프레임에 ultralytics 내부 letterbox(640)로 수행 → 왜곡 없음. **저장은 원본 해상도**.

## 네트워크

- LAN 의 go2rtc(`172.30.1.42:1984`) 접근을 위해 `network_mode: host` 사용(리눅스에서 가장 간단).
- bridge 로 바꾸려면 compose 에서 그 줄을 지우고, 컨테이너에서 스트림 호스트가 닿는지 확인.

## GPU — 이 Mint PC 는 CPU 로 (GPU 불가)

Mint PC 의 GPU 는 **GTX 550 Ti (Fermi, compute 2.1, VRAM 962MB)** · 드라이버 390.
- Fermi 는 **CUDA 9 에서 제거**됐고, 현대 PyTorch/ultralytics(CUDA 11/12 빌드)에는 sm_21 커널이 없다.
- 억지로 CUDA torch + `--gpus` 를 붙이면 첫 추론에서 `CUDA error: no kernel image is available`
  로 죽는다 → **넣으면 안 됨**. 그래서 이 이미지는 **CPU 전용**(torch cpu 휠)이다.
- 부하가 10분/1시간에 1회(yolo11n@640, 수백 ms)라 **CPU 로 충분**하고 GPU 이득이 없다.
- 나중에 **compute ≥ 5.0** GPU(예: GTX 10 시리즈 이상)로 바꾸면 GPU 가속 구성을 추가할 수 있다:
  `nvidia-container-toolkit` 설치 → Dockerfile 을 CUDA torch 로 → compose 에 `gpus: all`.
  (필요할 때 요청하면 그 변형을 만들어 둠)

## 로컬(도커 없이) 테스트

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\9_detection_inference\Baby-Timelapse
$env:RUN_ONCE=1; $env:OUT_DIR="captures"; ..\..\.venv\Scripts\python.exe capture.py
```
