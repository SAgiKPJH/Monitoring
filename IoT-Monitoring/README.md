문서정보 : 2026.06.24. 작성

<br>

# IoT 환경 모니터링 (Grafana · MongoDB · ASP.NET Core · NRF24L01)

온습도/조도 센서 데이터를 무선(NRF24L01)으로 수집하여 Web API → MongoDB에 저장하고, Grafana로 시각화하는 IoT 모니터링 시스템입니다.

## 데이터 흐름

```
[온습도센서(DHT) + 조광센서(CdS)]
        │ (GPIO / ADC)
        ▼
  Raspberry Pi Pico ── NRF24L01 ))) ((( NRF24L01 ── Arduino Uno R3 (ATmega328)
        (송신)                                              │ (UART, JSON 1줄)
                                                            ▼
                                                        ESP8266 (WiFi)
                                                            │ HTTP POST (JSON)
                                                            ▼
                                              ASP.NET Core HTTP API ──► MongoDB
                                                            ▲                │
                                                            │ HTTP(GET)      │
                                                          Grafana ◄──────────┘
                                                  (Infinity datasource)
```

- **Pico** : 센서 측정 → `SensorPayload` 구조체를 NRF24L01로 송신
- **Uno R3** : NRF24L01 수신 → JSON 한 줄로 ESP8266에 UART 전송
- **ESP8266** : 받은 JSON을 그대로 HTTP POST 로 API에 업로드
- **API(ASP.NET Core)** : JSON 저장(타임스탬프 부여) → MongoDB, 조회 API 제공
- **MongoDB** : `monitoring.readings` 컬렉션에 저장
- **Grafana** : Infinity 데이터소스로 API를 조회하여 대시보드 표시

> ⚠️ **Grafana → MongoDB 직접 연결에 대해**
> Grafana OSS(무료)에는 MongoDB 데이터소스가 기본 제공되지 않습니다(공식 MongoDB 플러그인은 Grafana **Enterprise** 전용). 따라서 본 프로젝트는 무료로 동작하도록 **Grafana → API → MongoDB** 경로를 사용합니다(무료 오픈소스 `Infinity` 플러그인). Enterprise 라이선스가 있다면 native MongoDB 플러그인으로 교체하여 Grafana가 MongoDB를 직접 조회하도록 바꿀 수 있습니다.

<br>

## 폴더 구조

```
IoT-Monitoring/
├── docker-compose.yml          # mongo + api + grafana + mongo-express
├── .env.example                # 환경변수 예시 (.env 로 복사)
├── api/                        # ASP.NET Core HTTP API (.NET 10)
│   ├── Program.cs / Controllers / Models / Services
│   └── Dockerfile
├── mongo/init/01-init.sh       # 앱 계정·컬렉션·인덱스 초기화
├── grafana/provisioning/       # 데이터소스 + 대시보드 자동 프로비저닝
│   ├── datasources/datasource.yml
│   └── dashboards/iot-monitoring.json
└── firmware/
    ├── pico/pico_sensor_node/          # 라즈베리파이 피코 (송신)
    ├── uno/uno_rf_receiver/            # 우노 R3 (수신 → ESP)
    └── esp8266/esp8266_wifi_uplink/    # ESP8266 (WiFi 업로드)
```

<br>

## 1. 서버(Docker) 실행

```bash
cd IoT-Monitoring
cp .env.example .env          # 필요시 비밀번호/포트 수정
docker compose up -d --build
```

| 서비스 | 주소 | 비고 |
|---|---|---|
| API | http://localhost:8080 | `/`, `/health`, `/api/readings` |
| Grafana | http://localhost:3000 | 기본 admin / admin (익명 Viewer 허용) |
| MongoDB | localhost:27017 | 계정은 `.env` 참조 |
| mongo-express | http://localhost:8081 | 데이터 확인용(선택), admin / admin |

- 대시보드: Grafana 접속 → **Dashboards → IoT 환경 모니터링** (자동 등록됨)
- 동작 확인(데이터 수동 주입):
  ```bash
  curl -X POST http://localhost:8080/api/readings \
    -H "Content-Type: application/json" \
    -d '{"deviceId":"node-01","temperature":24.3,"humidity":51.2,"light":640,"lightPercent":62,"sequence":1}'

  curl "http://localhost:8080/api/readings/latest?deviceId=node-01"
  ```

  > **Windows 주의 — 인라인 JSON 따옴표 문제**: 위 `bash` 예시는 Windows 셸에서 그대로 쓰면 깨집니다.
  > - **PowerShell**: `curl`은 `Invoke-WebRequest` 별칭이라 `-H`/`-d`가 안 됩니다(`Cannot bind parameter 'Headers'`). `curl.exe`를 써도 인라인 `-d '{...}'`는 큰따옴표가 제거되어 `{deviceId:...}`로 전송 → 잘못된 JSON.
  > - **cmd.exe**: 작은따옴표를 문자열 구분자로 보지 않아 `'{...}'`(맨 앞에 `'`)가 본문에 그대로 들어가 전송 → `'' is an invalid start of a value` (400).
  >
  > → 아래 방법을 사용하세요. (두 방법 모두 실제 전송 본문을 캡처해 유효 JSON임을 검증함)

  ```powershell
  # 방법 A (권장, PowerShell): 객체를 JSON으로 변환 → 따옴표 문제 자체가 없음
  $body = @{ deviceId='node-01'; temperature=24.3; humidity=51.2; light=640; lightPercent=62; sequence=1 } | ConvertTo-Json
  Invoke-RestMethod -Method Post -Uri http://localhost:8080/api/readings -ContentType 'application/json' -Body $body
  Invoke-RestMethod -Uri "http://localhost:8080/api/readings/latest?deviceId=node-01"
  # API_KEY 설정 시: -Headers @{ "X-Api-Key" = "yourkey" } 추가
  ```

  ```bat
  REM 방법 B (cmd / PowerShell 공통): curl.exe + 파일로 본문 전달 → 셸 따옴표 회피
  REM   위 JSON 한 줄을 reading.json 으로 저장한 뒤 실행:
  curl.exe -X POST http://localhost:8080/api/readings -H "Content-Type: application/json" -d "@reading.json"
  ```


### API 엔드포인트

| Method | Path | 설명 |
|---|---|---|
| POST | `/api/readings` | 측정값 저장 (ESP8266가 호출) |
| GET | `/api/readings?deviceId=&from=&to=&limit=` | 기간 조회 (Grafana가 호출) |
| GET | `/api/readings/latest?deviceId=` | 최신값 1건 |
| GET | `/health` | 헬스 체크 |

저장 문서 형식:
```json
{ "deviceId": "node-01", "temperature": 24.3, "humidity": 51.2,
  "light": 640, "lightPercent": 62, "battery": 3.78, "batteryPercent": 65,
  "sequence": 1, "timestamp": "2026-06-24T01:23:45.678Z" }
```

`API_KEY` 를 `.env`에 설정하면 POST 요청에 `X-Api-Key` 헤더가 필요합니다(미설정 시 인증 없음).

<br>

## 2. 펌웨어

### 공통 무선/데이터 규약 (반드시 일치)

- **NRF24L01** : 채널 `101`, `250KBPS`, 주소 `"Node1"`, **auto-ACK off**(단방향), 고정 페이로드 `sizeof(SensorPayload)`(28B)
- **페이로드 구조체** (Pico/Uno 동일, packed 금지 — 자연 정렬 28바이트):
  ```c
  struct SensorPayload {
    float    temperature;    // °C
    float    humidity;       // %RH
    uint32_t sequence;       // 패킷 카운터
    uint16_t light;          // raw ADC 0..1023
    uint16_t lightPercent;   // 0..100
    float    battery;        // 18650 전압(V)
    uint16_t batteryPercent; // 0..100
    char     deviceId[6];    // Pico가 지정한 id (그대로 전달, <=5글자)
  };
  ```
- **deviceId**: **Pico가 `DEVICE_ID`로 직접 지정** → Uno는 **변환 없이 그대로** JSON/DB에 전달. 여러 Pico는 각자 `DEVICE_ID`만 다르게(`node1`~`node5` 등), 무선 주소 `"Node1"`은 공통. (**5글자 이내**)
- **Uno → ESP8266 (UART 9600, 8N1)** : 줄바꿈(`\n`)으로 끝나는 JSON 1줄
- **ESP8266 → API** : 위 JSON을 그대로 `POST /api/readings`

### 2-1. Raspberry Pi Pico (송신) — MicroPython / Thonny
- Thonny + MicroPython. 파일: [pico_sensor_node.py](firmware/pico/pico_sensor_node/pico_sensor_node.py) + `nrf24l01.py`(함께 업로드). 실사용은 **`main.py`로 저장**해 전원만 넣어도 자동 실행.
- 센서: **AM2320**(온습도, I2C0: SDA=GP0, SCL=GP1) + CdS 조도(ADC0: GP26)
- NRF(SPI0): CE=GP14, CSN=GP15, SCK=GP6, MOSI=GP7, MISO=GP4, VCC=**3V3**
- 조정: `TEMP_OFFSET`/`HUM_OFFSET`(온·습도 보정), `SEND_PERIOD_MS`(전송 주기, **기본 5분**). **온보드 LED = 상태표시**: 부팅 3회 / **평소 10초마다 짧게(동작중)** / AM2320 에러 = 빠르게 2 + 길게 1 / NRF init 에러 = 빠르게 3 + 길게 1(반복).

### 2-2. Arduino Uno R3 (수신 → ESP)
- Arduino IDE 보드: **Arduino Uno** (CH340G)
- 라이브러리: `RF24`(TMRh20)
- NRF: CE=D9, CSN=D10, SCK=D13, MOSI=D11, MISO=D12, VCC=**3V3**
- **콤보 보드 DIP 스위치**: ATmega TX/RX ↔ ESP8266 로 연결(보통 1·2 ON / 3·4 OFF).
  - 이 상태에서는 D0/D1이 ESP에 물려 있어 USB 시리얼 모니터를 동시에 쓸 수 없습니다.
  - **ATmega 업로드 시**: 3·4 ON(USB↔ATmega)으로 바꿔 굽고 다시 원위치.
- 코드: [uno_rf_receiver.ino](firmware/uno/uno_rf_receiver/uno_rf_receiver.ino)

> 💡 센서·WiFi를 붙이기 전에 **NRF24L01 무선 링크만 먼저 검증**하려면 [test-nrf24l01/](test-nrf24l01/) 의 최소 송/수신 테스트 스케치를 사용하세요.

### 2-3. ESP8266 (WiFi 업로드)
- Arduino IDE 보드: **Generic ESP8266 Module** (콤보 보드 프로파일)
- [esp8266_wifi_uplink.ino](firmware/esp8266/esp8266_wifi_uplink/esp8266_wifi_uplink.ino) 상단에서 설정:
  - `WIFI_SSID`, `WIFI_PASS`
  - `API_URL` = `http://<도커-실행-PC-IP>:8080/api/readings` (localhost 아님!)
  - `API_KEY` (API에 설정한 경우만)
- **ESP8266 업로드 시**: DIP 스위치를 ESP 플래시 모드로 변경 후 굽고 원위치(보드 매뉴얼 참조).

<br>

## 3. 실행 (전체 시스템 동작)

펌웨어 업로드가 끝났으면 아래 순서로 켜면 데이터가 흐릅니다. 각 보드는 **전원만 넣으면 자동 실행**됩니다.

**① 서버(Docker 호스트) 먼저** — API가 떠 있어야 데이터를 받습니다.
```bash
cd IoT-Monitoring
docker compose up -d --build      # 코드 변경 시 --build 필수 (안 하면 옛 이미지 재사용 → 500)
docker compose ps                 # 전부 Up, mongo healthy 확인
```

**② Pico(센서 노드) 전원 인가**
- MicroPython 스크립트를 **`main.py`로 저장**해 두면 전원만 넣어도 자동 실행.
- **부팅 시 LED 3회 깜빡** 후 5분마다 측정·송신. **평소 10초마다 짧게 깜빡=동작중.** LED 상태표시로 배터리 구동(시리얼 없음) 시에도 진단 가능 — AM2320 에러=빠2+길1, NRF 에러=빠3+길1.

**③ Uno+ESP8266 콤보보드 → 실행 모드**
- DIP를 **`ATmega328 ↔ ESP8266`** 모드로 (보드 인쇄 표 참조; **SW7 OFF** — ESP 정상 부팅에 GPIO0=HIGH 필요).
  - Uno가 NRF 수신 → JSON을 ESP로(UART 9600) → ESP가 WiFi로 API에 POST.
  - ⚠️ 이 모드에선 **USB 시리얼 모니터 사용 불가**(D0/D1이 ESP에 물림). 디버깅은 업로드 모드로 잠깐 전환.
- 전원 인가 → WiFi 접속 후 자동 전송 시작.

**④ 확인**
- **Grafana** `http://<호스트>:3000` → **IoT 환경 모니터링** 대시보드 값이 갱신되면 성공.
- mongo-express `http://<호스트>:8081` → `monitoring.readings` 문서 증가 확인.
- API 직접: `GET http://<호스트>:8080/api/readings/latest?deviceId=node-01`

> 문제 시 단계별 격리 검증: NRF 링크 → [test-nrf24l01](test-nrf24l01/), ESP→API → [test-esp8266-api](test-esp8266-api/).

<br>

## 4. 문제 해결 (Troubleshooting)

- **NRF24L01 통신 안 됨**: VCC는 반드시 3.3V, VCC-GND 사이 `10µF` 캡 권장. 양쪽 채널/주소/데이터레이트/페이로드 크기가 동일해야 함.
- **DHT 읽기 NaN**: DATA 라인에 10kΩ 풀업 추가, 측정 간격 2초 이상.
- **API에 데이터가 안 들어옴**: ESP `API_URL`의 IP가 도커 실행 PC의 LAN IP인지 확인(방화벽 8080 허용). `docker logs iot-api`.
- **Grafana 그래프 비어있음**: 패널 시간범위(우상단)를 최근으로, 데이터소스(IoT-API) 연결 확인, `GET /api/readings` 가 값을 반환하는지 확인.
- **mongo 초기화 안 됨**: `01-init.sh`는 **빈 데이터 볼륨 최초 1회만** 실행됨. 재실행하려면 `docker compose down -v` 후 다시 기동(데이터 삭제됨).
- **`01-init.sh` 권한/줄바꿈**: 스크립트는 LF 줄바꿈이어야 함(CRLF 금지).

<br>

### 제작자
[@SAgiKPJH](https://github.com/SAgiKPJH)
