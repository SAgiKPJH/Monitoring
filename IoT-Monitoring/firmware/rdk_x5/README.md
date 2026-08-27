# RDK X5 — NRF24L01 수신기 (Uno 대체)

## 1. 배선 (NRF24L01 → RDK X5 40핀 헤더)

| NRF24L01 핀 | RDK X5 연결 | 40핀 헤더 위치(예상) | 비고 |
|---|---|---|---|
| **VCC** | 3V3 | 1번 (3V3) | ⚠️ **5V 금지**. 안정화용 10µF 캡 권장 |
| **GND** | GND | 6번 등 | 공통 그라운드 |
| **CE**  | **3V3** (권장) | 1/17번(3V3) | 항상 RX. GPIO로 제어하려면 코드 `CE_TIE_HIGH` 끄고 GPIO에 배선 |
| **CSN** | SPI1 CS | **24번** | ⚠️ RDK X5는 RPi와 반대: **핀24=CS1=`spidev1.1`**, 핀26=CS0=`spidev1.0` |
| **SCK** | SPI1 SCLK | 23번 | |
| **MOSI**| SPI1 MOSI | 19번 | |
| **MISO**| SPI1 MISO | 21번 | |
| **IRQ** | 미연결 | — | 폴링 방식이라 불필요 |

> 📌 위 SPI 핀은 **RDK X5 공식 spi1** 위치입니다 (공식 문서: SPI1 = 40핀 **19·21·23·24·26**, CS 2개, 3.3V).
> ⚠️ **RDK X5는 RPi와 CS가 반대**입니다: **핀24 = CS1 = `/dev/spidev1.1`**, 핀26 = CS0 = `/dev/spidev1.0`.
> 확실히 하려면 `for cs in 0 1` 테스트에서 **CONFIG=0x0F 나오는 노드**가 실제 CSN 위치입니다.
> **CE는 3V3에 직결**하면(항상 RX) GPIO를 안 써도 됩니다 — RDK X5의 40핀 라인은 unnamed라
> 매핑이 번거로우니 이 방식을 권장. 실제 SPI 노드만 `ls /dev/spidev*`로 확인하세요.

## 2. 사전 준비 (RDK X5, Ubuntu)

**SPI 활성화** (RDK 설정 도구 → SPI on → 재부팅):
```bash
sudo srpi-config        # Interface Options → Peripheral bus config (SPI) → SPI1 Enable  (도구명이 다르면 device tree overlay로)
ls -l /dev/spidev*      # 활성 버스가 노드로 보임
# 이 보드 출력: /dev/spidev1.0  /dev/spidev1.1   → CSN=핀24면 spidev1.1 (RDK X5는 핀24=CS1!)
```

**어느 CS(노드)에 NRF가 물렸는지 확인** — 두 노드에 CONFIG를 써보고 `0x0F`가 돌아오는 쪽이 정답:
```bash
for cs in 0 1; do
python3 - "$cs" <<'EOF'
import spidev, sys
cs=int(sys.argv[1]); spi=spidev.SpiDev(); spi.open(1,cs)
spi.max_speed_hz=1000000; spi.mode=0
spi.xfer2([0x20,0x0F]); v=spi.xfer2([0x00,0xFF])[1]   # write CONFIG=0x0F, read back
print("spidev1.%d -> CONFIG=0x%02X %s" % (cs, v, "  <-- NRF 여기!" if v==0x0F else ""))
spi.close()
EOF
done
```
→ `CONFIG=0x0F` 나온 노드를 코드 `SPI_DEV`에 넣으세요. **이 보드: 핀24 배선 → `spidev1.1`** (RDK X5는 RPi와 CS 반대).

> - `ls /dev/spidev*` 로 **spi1에 해당하는 노드**를 확인해 코드 `SPI_DEV`에 넣기 (예: `/dev/spidev0.0`).
>   버스 번호↔노드 매핑은 device tree alias에 따라 달라지니 실제 목록으로 확인하세요.

**라이브러리 설치**:
```bash
sudo apt update
sudo apt install -y libcurl4-openssl-dev build-essential   # GPIO로 CE 제어 시: + gpiod libgpiod-dev
```

**(선택) GPIO로 CE 제어할 때만** — 배선한 헤더 핀의 chip/line 확인:
```bash
gpioinfo                # less 없으면 그냥 실행. "gpiochipN" + line offset → CE_CHIP/CE_LINE
```
> RDK X5의 40핀 라인은 **unnamed**라 물리핀 매핑이 번거롭습니다. **CE→3V3 직결이 훨씬 간단**하며,
> 이 경우 이 단계와 libgpiod 자체가 필요 없습니다.

---

## 3. 설정 (`rf_common.h` 상단 — 단독 C · ROS 노드 공용)

```c
#define SPI_DEV   "/dev/spidev1.1"   // 핀24=CS1=spidev1.1 (RDK X5는 RPi와 반대!). 핀26이면 spidev1.0
#define CE_TIE_HIGH 1                // CE→3V3 직결(기본). GPIO로 제어하려면 이 줄 주석 처리
#define CE_CHIP   "gpiochip0"        // (CE_TIE_HIGH 끈 경우만) gpioinfo 결과
#define CE_LINE   22                 // (CE_TIE_HIGH 끈 경우만) gpioinfo 결과
#define API_URL   "http://172.30.1.42:8080/api/readings"
#define ERROR_URL "http://172.30.1.42:8080/api/errors"
#define API_KEY   ""                 // API의 API_KEY와 동일하게 (없으면 빈값)
#define POLL_US   20000              // RX FIFO 폴링 주기(us). 줄이면 커널 SPI 로그가 폭증
```
`RF_CHANNEL`(101)·주소("Node1")·`PAYLOAD_SIZE`(30)는 Pico와 일치하므로 그대로 두세요.

> 이 헤더 하나만 고치면 **단독 C 버전과 ROS 2 노드에 동시에 반영**됩니다.

---

## 4. 단독 빌드 & 실행

```bash
# 기본: CE→3V3 직결(CE_TIE_HIGH) → gpiod 불필요
gcc rdk_rf_receiver.c -o rdk_rf_receiver -lcurl
sudo ./rdk_rf_receiver          # spidev 접근에 권한 필요할 수 있음

gcc rdk_rf_receiver.c -o rdk_rf_receiver -lcurl && sudo ./rdk_rf_receiver
sudo python3 rdk_rf_receiver.py      # 또는 python 실행
```
> **GPIO로 CE를 제어**하려면: 코드의 `CE_TIE_HIGH`를 주석 처리하고 `-lgpiod`를 붙여 빌드 →
> `gcc rdk_rf_receiver.c -o rdk_rf_receiver -lgpiod -lcurl` (libgpiod **v1** 기준, Ubuntu 22.04/tros Humble).
정상이면 수신할 때마다 로그가 찍힙니다:
```
[BRB] T=24.5 H=55.3 light=512(48%) bat=3.85V(72%) seq=42
[BRB] ERROR code=1 seq=43 -> /api/errors
```

### 부팅 자동 실행 (systemd)
`/etc/systemd/system/rf-receiver.service`:
```ini
[Unit]
Description=RDK X5 NRF24L01 receiver
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/home/sunrise/rdk_rf_receiver
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now rf-receiver
journalctl -u rf-receiver -f
```

---

## 5. ROS 2 (TogetheROS.Bot)로 실행 — C++ rclcpp 노드

RDK X5 는 **TogetheROS.Bot(tros, ROS 2 Humble 기반)** 을 지원합니다.
현행 `ros2_ws/` 는 **진짜 ROS 2 노드**라 `ros2 node list` · `ros2 topic echo` 로 조회됩니다.

```
node   : /rf_receiver
topics : /iot/readings , /iot/errors     (std_msgs/String, JSON 문자열)
```
수신 패킷을 **API 로 POST 하면서 동시에 토픽으로도 발행**합니다.

### 파일 구성
```
firmware/rdk_x5/
├── rf_common.h                  # ★공용 로직 (SPI·프로토콜·중복제거·HTTP·설정)
├── rdk_rf_receiver.c            # 단독 실행용 main() — ROS 없이 gcc 로 빌드
├── ros2_ws/                     # 현행: C++ rclcpp 노드
│   ├── run.sh                   #   환경 source + ros2 launch (systemd 가 호출)
│   ├── rf-receiver.service      #   부팅 자동실행
│   └── src/rdk_rf_receiver/
│       ├── package.xml          #   rclcpp · std_msgs 의존
│       ├── CMakeLists.txt       #   ../../.. 를 include 경로로 → rf_common.h 공유
│       ├── src/rf_receiver_node.cpp
│       └── launch/receiver.launch.py
└── before/                      # 이전 구현 보관 (C 래핑판 · Python 판) — before/README.md
```
> **설정은 `rf_common.h` 상단 한 곳**에서만 바꿉니다 (`SPI_DEV`, `POLL_US`, `API_URL` …).
> 단독 C 버전과 ROS 노드가 같은 헤더를 쓰므로 로직이 갈라지지 않습니다.

### 빌드
```bash
sudo apt install -y libcurl4-openssl-dev            # CE 3V3 직결이면 gpiod 불필요
cd firmware/rdk_x5/ros2_ws
source /opt/tros/humble/setup.bash                  # 없으면 /opt/ros/humble/setup.bash
colcon build
```
> CMake 가 `../../..`(= `firmware/rdk_x5`)를 include 경로로 잡아 `rf_common.h` 를 찾습니다.
> 따라서 **`firmware/rdk_x5/ros2_ws` 안에서** 빌드하세요.

### 실행 & 조회
```bash
source install/setup.bash
ros2 launch rdk_rf_receiver receiver.launch.py

# 다른 터미널에서
ros2 node list                    # → /rf_receiver
ros2 topic echo /iot/readings     # 수신 데이터 실시간 (JSON)
ros2 topic hz /iot/readings
```
> `/dev/spidev1.x` 는 `crw-rw-rw-` 라 일반 사용자로 접근됩니다(sudo 불필요).

### 🔌 부팅 자동실행 (systemd)
```bash
chmod +x run.sh
./run.sh                                  # 1) 먼저 직접 실행해 확인 (Ctrl+C)

# 2) rf-receiver.service 의 ExecStart 를 run.sh 절대경로로, User 를 실제 계정으로 수정 후:
sudo cp rf-receiver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rf-receiver
journalctl -u rf-receiver -f
```
- **코드 수정 후**: `colcon build` → `sudo systemctl restart rf-receiver`
- ⚠️ NRF 는 하나뿐이므로 **단독 C 버전과 ROS 노드를 동시에 실행하지 마세요** (SPI 충돌).

---

## 6. 디스크 관리 (⚠️ 중요)

### 증상
```
OSError: [Errno 28] No space left on device
df -h  →  /dev/root  57G  55G  0  100% /
```

### 원인
커널이 **SPI 전송마다 로그를 남긴다**(`spidev spi1.0: xfer len 2 ...`).
수신기가 RX FIFO 를 폴링하므로 폴링 주기가 짧으면 초당 수백~수천 줄이 쌓인다.
실제로 `/var/log/syslog` 와 `/var/log/kern.log` 가 각각 **24GB** 까지 자랐다.

### 즉시 복구
```bash
sudo du -xh --max-depth=1 /var 2>/dev/null | sort -rh | head    # 어디가 찼는지
sudo truncate -s 0 /var/log/syslog /var/log/kern.log            # rm 아니라 truncate
df -h
```
> `rm` 으로 지우면 rsyslog 가 파일을 열고 있어 **공간이 반환되지 않는다.**

### 재발 방지
```bash
# 1) 커널 SPI 디버그 메시지를 rsyslog 단계에서 폐기 (재부팅해도 유지)
echo ':msg, contains, "spidev spi" stop' | sudo tee /etc/rsyslog.d/10-drop-spidev.conf
sudo systemctl restart rsyslog

# 2) 동적 디버그가 켜져 있으면 끄기
echo 'module spidev -p' | sudo tee /sys/kernel/debug/dynamic_debug/control

# 3) 저널 상한
sudo sed -i 's/^#\?SystemMaxUse=.*/SystemMaxUse=200M/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
```

### 코드 차원의 완화 (이미 반영됨)
| 항목 | 값 | 효과 |
|---|---|---|
| `POLL_US` | 2ms → **20ms** | SPI 전송 1/10 → 커널 로그도 1/10 |
| FIFO 처리 | 1개 → **전부 드레인** | 느린 폴링에도 패킷 손실 없음 |
| NRF 오류 로그 | 매초 → **상태 변화 시 + 5분마다** | 배선 빠진 채 방치돼도 로그 폭주 없음 |
| `run.sh` | 3일 지난 `~/.ros/log` 정리 | 재시작 반복 시 로그 디렉터리 누적 방지 |

> Pico 는 5분마다 3연속 전송하고 NRF RX FIFO 가 3개를 담으므로 **20ms 폴링으로도 손실이 없다.**

---

## 7. 확인 & 참고

```bash
curl "http://172.30.1.42:8080/api/readings/latest?deviceId=BRB"
curl "http://172.30.1.42:8080/api/errors?deviceId=BRB&limit=10"
```

- **Uno와 동시 사용 금지**: 같은 주소/채널이라 둘 다 켜면 패킷을 나눠 받습니다. RDK X5로 넘어갈 땐 Uno는 끄세요.
- **페이로드 30바이트**는 Pico/Uno와 반드시 동일해야 수신됩니다.
- 라디오 설정은 [uno_rf_receiver.ino](../uno/uno_rf_receiver/uno_rf_receiver.ino)를 미러링했습니다.
