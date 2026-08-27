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

## 3. 설정 (`rdk_rf_receiver.c` 상단)

```c
#define SPI_DEV   "/dev/spidev1.1"   // 핀24=CS1=spidev1.1 (RDK X5는 RPi와 반대!). 핀26이면 spidev1.0
#define CE_TIE_HIGH 1                // CE→3V3 직결(기본). GPIO로 제어하려면 이 줄 주석 처리
#define CE_CHIP   "gpiochip0"        // (CE_TIE_HIGH 끈 경우만) gpioinfo 결과
#define CE_LINE   22                 // (CE_TIE_HIGH 끈 경우만) gpioinfo 결과
#define API_URL   "http://172.30.1.42:8080/api/readings"
#define ERROR_URL "http://172.30.1.42:8080/api/errors"
#define API_KEY   ""                 // API의 API_KEY와 동일하게 (없으면 빈값)
```
`RF_CHANNEL`(101)·주소("Node1")·`PAYLOAD_SIZE`(30)는 Pico와 일치하므로 그대로 두세요.

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

## 5. ROS 2 (TogetheROS.Bot)로 실행

RDK X5는 **TogetheROS.Bot(tros, ROS 2 Humble 기반)** 을 지원합니다. 아래처럼 **ROS 2 패키지로
감싸면** `colcon build` / `ros2 run` / `ros2 launch` 로 관리·실행할 수 있습니다.

### 패키지는 이미 만들어 뒀습니다 (`ros2_ws/`)
```
ros2_ws/
├── run.sh                       # 환경 source + ros2 launch (systemd에서 호출)
├── rf-receiver.service          # 부팅 자동실행 (systemd)
└── src/rdk_rf_receiver/
    ├── package.xml
    ├── CMakeLists.txt           # 상위의 ../../../rdk_rf_receiver.c 를 그대로 빌드(사본 X)
    └── launch/receiver.launch.py
```

### 빌드 (제자리 in-place)
```bash
sudo apt install -y libcurl4-openssl-dev            # CE 3V3 직결이면 gpiod 불필요
cd firmware/rdk_x5/ros2_ws
source /opt/tros/humble/setup.bash                  # 없으면 /opt/ros/humble/setup.bash
colcon build
```
> CMake가 `../../../rdk_rf_receiver.c` 를 참조하므로 **반드시 `firmware/rdk_x5/ros2_ws` 안에서** 빌드하세요(경로 일치).

### 수동 실행 (확인용)
```bash
source install/setup.bash
ros2 launch rdk_rf_receiver receiver.launch.py
```
> `/dev/spidev1.x` 는 `crw-rw-rw-` 라 일반 사용자로 접근됩니다(sudo 불필요).

### 🔌 부팅 자동실행 (systemd)
```bash
chmod +x firmware/rdk_x5/ros2_ws/run.sh
firmware/rdk_x5/ros2_ws/run.sh          # 1) 먼저 이 스크립트로 잘 뜨는지 확인 (Ctrl+C)

# 2) rf-receiver.service 의 ExecStart 를 run.sh 실제 절대경로로, User 를 실제 계정으로 수정 후:
sudo cp firmware/rdk_x5/ros2_ws/rf-receiver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rf-receiver
journalctl -u rf-receiver -f            # 로그 실시간 확인
```
- 부팅 때마다 `ros2 launch` 자동 기동, 크래시 시 5초 후 재시작.
- **코드 수정 후**: `colcon build` 다시 → `sudo systemctl restart rf-receiver`.

### (선택) ROS 토픽으로 발행하기
지금 코드는 데이터를 **HTTP로만** 보냅니다. RDK X5의 **ROS 그래프(토픽)** 에도 올리고
싶으면, C용 클라이언트 라이브러리 **rclc**로 퍼블리셔를 추가하면 됩니다:

- `find_package(rclc REQUIRED)` / `rcl` / `std_msgs` 의존성 추가
- 수신 시 `handle_payload()`에서 JSON 문자열을 `std_msgs/msg/String`으로 `/iot/readings`,
  에러는 `/iot/errors` 토픽에 publish
- 그러면 `ros2 topic echo /iot/readings` 로 실시간 확인 가능

필요하면 rclc 퍼블리셔가 포함된 버전으로 확장해 드리겠습니다.

---

## 6. 확인 & 참고

```bash
curl "http://172.30.1.42:8080/api/readings/latest?deviceId=BRB"
curl "http://172.30.1.42:8080/api/errors?deviceId=BRB&limit=10"
```

- **Uno와 동시 사용 금지**: 같은 주소/채널이라 둘 다 켜면 패킷을 나눠 받습니다. RDK X5로 넘어갈 땐 Uno는 끄세요.
- **페이로드 30바이트**는 Pico/Uno와 반드시 동일해야 수신됩니다.
- 라디오 설정은 [uno_rf_receiver.ino](../uno/uno_rf_receiver/uno_rf_receiver.ino)를 미러링했습니다.
