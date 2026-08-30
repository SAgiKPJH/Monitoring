# Raspberry Pi Pico 센서 노드 — 초기화 & 설치

방(BRB·BRO·TO·RO·MR)마다 Pico 한 대가 온습도/조도/배터리를 읽어
NRF24L01로 RDK X5 수신기에 보냅니다. **새 Pico를 처음 세팅하거나,
동작이 이상해서 완전히 밀고 다시 올릴 때** 이 문서를 따라가세요.

- 보드: **Raspberry Pi Pico (RP2040, 무선 없는 원본 모델)**
- 펌웨어: **MicroPython**
- 올릴 파일: [`pico_sensor_node/nrf24l01.py`](pico_sensor_node/nrf24l01.py), [`pico_sensor_node/pico_sensor_node.py`](pico_sensor_node/pico_sensor_node.py)

---

## 0. 준비물

| 항목 | 비고 |
|---|---|
| Pico 본체 + **데이터 전송용** micro-USB 케이블 | ⚠️ 충전 전용 케이블이면 드라이브가 안 잡힙니다 |
| `flash_nuke.uf2` | 플래시 완전 삭제용 — 아래 1단계 |
| MicroPython `.uf2` | 아래 2단계 |
| Thonny 또는 `mpremote` | 파이썬 파일 업로드용 — 아래 3단계 |

### 다운로드 링크

**① flash_nuke.uf2** (플래시 전체 초기화)
<https://hirurobotics.gitbook.io/xrp/experiential-robotics-platform-xrp/programming-raspberry-pi-pico-w>
→ 페이지 안의 `flash_nuke.uf2` 파일을 내려받습니다.

> 문서 제목은 Pico **W** 기준이지만, `flash_nuke.uf2`는 RP2040 플래시를 지우는 것뿐이라
> 원본 Pico에도 그대로 씁니다.

**② MicroPython 펌웨어**
<https://micropython.org/download/RPI_PICO/>
→ **“Firmware”/“Releases”** 항목의 최신 `.uf2` (예: `RPI_PICO-2xxxxxxx-vX.Y.Z.uf2`)

> ⚠️ 반드시 **`RPI_PICO`** 페이지에서 받으세요. `RPI_PICO_W` / `RPI_PICO2` 펌웨어를
> 올리면 부팅이 안 되거나 핀 번호가 달라집니다.

---

## 1. 플래시 완전 초기화 (flash_nuke)

기존 코드·설정을 **전부 지웁니다.** 새 보드라면 건너뛰어도 되지만,
증상이 애매할 때는 여기서부터 하는 게 제일 빠릅니다.

1. Pico의 **BOOTSEL 버튼을 누른 채로** USB를 PC에 연결합니다.
2. 버튼을 뗍니다 → **`RPI-RP2`** 라는 USB 드라이브가 잡힙니다.
3. `flash_nuke.uf2`를 그 드라이브에 **복사**합니다.
4. 복사가 끝나면 Pico가 자동으로 재부팅하며 플래시를 지우고,
   다시 **`RPI-RP2` 드라이브 상태로 돌아옵니다.** (이때 USB를 뽑지 마세요)

> 이 상태에서는 아직 MicroPython이 없습니다. 바로 2단계로 갑니다.

---

## 2. MicroPython 설치 (UF2 부트로더 방식)

1. `RPI-RP2` 드라이브가 보이는 상태인지 확인합니다.
   (안 보이면 USB를 뽑고 **BOOTSEL을 누른 채** 다시 연결)
2. 받아둔 MicroPython **`.uf2`** 파일을 `RPI-RP2` 드라이브에 **복사**합니다.
3. 복사 직후 드라이브가 사라지고 Pico가 재부팅됩니다.
   → 이제 **USB 시리얼(COM 포트)** 로 인식됩니다.

**설치 확인** (PowerShell):
```powershell
pip install mpremote
mpremote devs                 # 연결된 포트 목록 (예: COM5 ... Board in FS mode)
mpremote connect COM5 exec "import sys; print(sys.implementation)"
# -> (name='micropython', version=(1, 2x, 0), ...) 나오면 성공
```

Thonny를 쓴다면: **Run → Interpreter → MicroPython (Raspberry Pi Pico)** 선택 후
하단 Shell에 `>>>` 프롬프트가 뜨면 정상입니다.

---

## 3. 펌웨어 파일 올리기

`nrf24l01.py`(드라이버)와 센서 노드 코드 **두 개 다** 올려야 합니다.
그리고 전원만 넣으면 자동 실행되도록 **`main.py`라는 이름으로** 올립니다.

### mpremote (권장)

```powershell
cd d:\Code\Monitoring\IoT-Monitoring\firmware\pico\pico_sensor_node

mpremote connect COM5 fs cp nrf24l01.py :nrf24l01.py
mpremote connect COM5 fs cp pico_sensor_node.py :main.py

mpremote connect COM5 fs ls          # 두 파일이 보이는지 확인
```

> ⚠️ 파일명을 `pico_sensor_node.py` 그대로 올리면 **부팅 시 자동 실행되지 않습니다.**
> MicroPython은 `main.py`만 자동 실행합니다.

### Thonny

1. 좌측 파일 탐색기에서 PC 쪽 `pico_sensor_node` 폴더를 엽니다.
2. `nrf24l01.py` 우클릭 → **Upload to /**
3. `pico_sensor_node.py` 우클릭 → **Upload to /** → Pico 쪽에서 **`main.py`로 이름 변경**

---

## 4. 노드별 설정 — `DEVICE_ID`

Pico마다 **반드시 다른 값**으로 바꿔서 올립니다.
[`pico_sensor_node.py`](pico_sensor_node/pico_sensor_node.py) 상단:

```python
DEVICE_ID = "BRB"       # 이 노드의 id
```

| 값 | 위치 |
|---|---|
| `BRB` | 안방 |
| `BRO` | 작은방 |
| `TO`  | 화장실 |
| `RO`  | 거실 |
| `MR`  | 주방 |

**규칙 (API의 `DeviceId` 값 객체와 동일):** 영문자·숫자만, **1~5자**.
어기면 서버가 400으로 거부합니다 — 페이로드의 `char deviceId[6]`(5자 + 널) 제약에서 온 규칙입니다.

같이 확인할 값:
```python
CHANNEL = 101           # 수신기와 동일해야 함
ADDRESS = b"Node1"      # 수신기와 동일해야 함
SEND_PERIOD_MS = 300000 # 5분 주기
TEMP_OFFSET = 0.0       # 기준 온도계와 차이 나면 보정 (예: 2도 높게 읽으면 -2.0)
HUM_OFFSET = 0.0
```

---

## 5. 배선

```
NRF24L01 (SPI0):  CE=GP14  CSN=GP15  SCK=GP6  MOSI=GP7  MISO=GP4  VCC=3V3
AM2320   (I2C0):  SDA=GP0  SCL=GP1   VDD=3V3  GND=GND            (주소 0x5C)
CdS      (ADC0):  3V3 --[CdS]--+-- GP26 --[10k]-- GND            (밝을수록 값 ↑)
18650          :  VSYS(39번 핀). 전압은 ADC3/GP29(=VSYS/3)로 읽음. 보호회로 있는 셀 사용
```

⚠️ NRF24L01 **VCC는 3V3** (5V 금지). 전원이 흔들리면 송신이 실패하니 VCC–GND에 **10µF** 권장.

⚠️ AM2320 핀 순서는 (앞면, 다리 아래) **1=VDD · 2=SDA · 3=GND · 4=SCL** — 3·4번을 바꿔 꽂기 쉬움.

> **SCL(GP1)이 LOW로 끌려가는 보드** (옆 핀이 GND라 브리지/플럭스 누설이 잘 생기는 자리):
> 1. 진단: [am2320_check.py](pico_sensor_node/am2320_check.py) → LOW 고정이면 원인 추적 모드가 안내
> 2. `Pin(1, Pin.OUT, value=1)` 구동 시 `1`이 나오면(저항성 누설) — 배선 변경 없이
>    [am2320_pushpull_test.py](pico_sensor_node/am2320_pushpull_test.py) 로 확인 후
>    `I2C_SCL_PUSHPULL = True` (RO 노드가 이 경우)
> 3. 구동해도 `0`(완전 단락)이면 — 브리지 제거, 또는 SCL 배선을 GP5(물리 7번 핀)로 옮기고
>    `I2C_SCL_PIN = 5`

---

## 6. 동작 확인

### 시리얼 로그

```powershell
mpremote connect COM5              # Ctrl+] 로 빠져나옴
```
```
=== Pico sensor node (MicroPython) ===
BRB #1  T=28.1C H=53.2%  light=812(79%)  bat=3.92V(76%)  -> sent
```

### 내장 LED 패턴

| 패턴 | 의미 |
|---|---|
| 느린 깜빡임 3회 (부팅 직후) | 정상 기동 |
| 10초마다 아주 짧게 1회 | 살아 있음 (전송 대기 중) |
| 빠르게 2회 + 길게 1회 | **AM2320 읽기 실패** → 오류 전송 후 자동 재시작 |
| 빠르게 3회 + 길게 1회 | **NRF24L01 초기화 실패** → 전송 불가, 자동 재시작 |

오류는 NRF로도 보고되어 `POST /api/errors`에 쌓입니다 → Grafana **“오류 자세히”** 패널에서 확인.

### 서버까지 도달했는지

```bash
curl -s "http://172.30.1.42:8080/api/readings/latest?deviceId=BRB"
curl -s "http://172.30.1.42:8080/api/readings/status"
```

---

## 7. 문제 해결

| 증상 | 확인 |
|---|---|
| `RPI-RP2` 드라이브가 안 뜸 | 충전 전용 케이블 / BOOTSEL을 **누른 채로** 연결했는지 |
| COM 포트가 안 보임 | 장치 관리자 확인, `mpremote devs`, 다른 USB 포트 |
| `ImportError: no module named 'nrf24l01'` | `nrf24l01.py`를 안 올렸습니다 (3단계) |
| 전원만 넣으면 아무 것도 안 함 | 파일명이 `main.py`가 아닙니다 |
| NRF 오류 패턴(3+1)이 계속 | 배선(특히 CSN·SCK) 접촉 불량, VCC 3V3 확인, 캡 추가 |
| 서버에 안 들어옴 | `CHANNEL`·`ADDRESS`가 수신기와 같은지, RDK X5 쪽 `rf-receiver` 상태 확인 |
| 값이 이상함 | `TEMP_OFFSET`/`HUM_OFFSET`으로 보정 |

**완전히 밀고 다시:** 1단계(flash_nuke)부터 반복하면 됩니다.

---

## 8. 참고

- 수신기 쪽 설정: [`../rdk_x5/README.md`](../rdk_x5/README.md)
- 페이로드 구조는 수신기와 **반드시 동일**해야 합니다:
  `struct.pack("<ffIHHfH6sBB", ...)` — 30바이트
- 각 패킷은 3번 전송(`TX_REPEAT`)하고, 수신기가 30초 창에서 중복을 걸러냅니다.
