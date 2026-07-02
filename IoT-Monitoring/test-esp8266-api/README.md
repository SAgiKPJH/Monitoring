# ESP8266 → API 전송 테스트

Uno·NRF·센서 없이 **ESP8266이 WiFi로 ASP.NET API에 POST가 되는지**만 확인. 가짜 측정값을 주기적으로 보내고 **HTTP 응답 코드**를 출력.

- `esp8266_api_test/esp8266_api_test.ino`

## 설정 (스케치 상단)
| 항목 | 값 |
|---|---|
| WIFI_SSID / WIFI_PASS | 실제 WiFi |
| API_URL | `http://<도커PC-IP>:8080/api/readings` (**localhost 아님**) |
| API_KEY | API에 설정한 경우만 (아니면 빈칸) |

## 실행
1. 콤보보드 **DIP: 5·6·7 ON** (USB↔ESP8266 + 플래시; 아래 표) — 플래시·모니터 둘 다 이 위치.
2. 보드 `Generic ESP8266 Module` 로 `esp8266_api_test.ino` 업로드.
3. 시리얼 모니터 **115200**.
4. 사전조건: 도커 스택 실행 중(`docker compose up -d`), ESP와 **같은 네트워크**.

## 콤보보드 DIP 스위치 (UNO+WiFi R3 · ATmega328P + ESP8266 + CH340G)
해당 모드의 스위치만 ON, 나머지는 OFF:

| 모드 | 스위치 | 용도 |
|---|---|---|
| **USB ↔ ESP8266 (+플래시)** | **5·6·7 ON** | ESP 업로드 + 시리얼 모니터 ← **이 테스트** (SW7 = ESP GPIO0 플래시 활성화) |
| USB ↔ ATmega328 | 보드 인쇄 표 확인 | Uno(ATmega) 업로드 + 시리얼 모니터 |
| ATmega328 ↔ ESP8266 | 보드 인쇄 표 확인 | 두 칩이 통신 (통합 실행 모드) |

- 이 테스트(ESP→API)는 **5·6·7 ON**. SW7이 GPIO0(플래시)을 잡아줘 **버튼 안 눌러도** 업로드됩니다.
- 업로드 후 **스케치가 실행 안 되면(모니터 무반응) SW7만 OFF + 리셋** — 정상 부팅엔 GPIO0=HIGH 필요. 모니터는 **5·6 ON** 유지.
- ⚠️ 위 스위치 값은 **이 보드 기준**(리비전마다 다름). ATmega/통합 실행 모드의 스위치는 보드에 **인쇄된 표**를 확인하세요.
- **ESP 업로드 실패(`Timed out waiting for packet header`)** 대처:
  1. **5·6·7 ON** 인지 확인 (특히 SW7 = 플래시 활성화).
  2. **Upload Speed 115200**으로 낮추기 (Tools 메뉴) — CH340 고속 실패 방지.
  3. COM 포트를 다른 앱(시리얼 모니터/Thonny)이 점유하지 않게, USB 재연결.

## 정상 출력
```
WiFi OK, IP=192.168.x.x
POST #1 -> HTTP 201  body={"id":"...","deviceId":"esp-test",...}
```
`HTTP 201` = 저장 성공. mongo-express(`:8081`)나 Grafana에서도 데이터 확인 가능.

## 응답 코드 해석
| 코드 | 의미 / 조치 |
|---|---|
| 201 | 성공 |
| -1 | 연결 실패 — API IP/포트 오류, 도커 미실행, 방화벽, 다른 네트워크 |
| 400 | JSON 형식 오류 |
| 401 | API_KEY 필요/불일치 |
