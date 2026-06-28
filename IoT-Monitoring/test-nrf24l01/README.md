# NRF24L01 링크 테스트 (Pico ↔ Uno)

전체 파이프라인(센서·UART·WiFi·DB)을 붙이기 전에 **Pico ↔ Uno 무선 링크만** 따로 검증하는 최소 코드입니다.
실제 펌웨어와 **동일한 배선·라디오 설정**(채널 76, 250KBPS, PA_LOW, 주소 `"Node1"`)을 사용하므로,
이 테스트가 통과하면 실제 배선/설정이 맞다는 의미입니다.

- [`pico_tx_test/`](pico_tx_test/pico_tx_test.ino) — Pico = **송신** (Arduino/C++, 1초마다 카운터 전송)
- [`uno_rx_test/`](uno_rx_test/uno_rx_test.ino) — Uno = **수신** (Arduino/C++, 받은 카운터를 USB 시리얼로 출력)
- [`micropython/`](micropython/) — Pico 송신부를 **Thonny(MicroPython)** 로 돌리는 대체 버전 (수신측 Uno는 그대로 Arduino 사용)

> 두 보드는 **서로 선으로 연결하지 않습니다.** 각자 NRF24L01만 배선하고 전원만 주면 통신은 무선(공중)으로 이뤄집니다.
> **단방향(auto-ACK off) 테스트**입니다 — MicroPython 드라이버 ↔ Arduino RF24 간 auto-ACK 핸드셰이크가 불안정해서 양쪽 다 ACK를 끕니다(데이터 흐름은 어차피 Pico→Uno 단방향). 그래서 **링크 확인은 Pico가 아니라 Uno의 `RX #n` 증가**로 합니다.

## 배선 (실제 펌웨어와 동일)

| | Pico (SPI0) | Uno |
|---|---|---|
| CE | GP14 | D9 |
| CSN | GP15 | D10 |
| SCK | GP6 | D13 |
| MOSI | GP7 | D11 |
| MISO | GP4 | D12 |
| VCC | **3V3** | **3V3** |
| GND | GND | GND |

- VCC는 **절대 5V 금지**. VCC–GND 사이 **10~100µF 캐패시터** 권장(전원 안정 — 안 달면 통신이 불안정).
- Pico는 SPI0 기본핀이 아니므로 스케치에서 `radio.begin()` 전에 `SPI.setRX(4)/setSCK(6)/setTX(7)`로 핀을 지정합니다.

## 실행 순서

1. **Pico**: 보드 `Raspberry Pi Pico`, 라이브러리 `RF24` 설치 → `pico_tx_test.ino` 업로드.
2. **Uno**: 보드 `Arduino Uno`, 라이브러리 `RF24` → `uno_rx_test.ino` 업로드.
   - 콤보 보드면 **DIP 스위치를 USB↔ATmega(보통 3·4 ON)** 로 둬야 USB 시리얼 모니터가 됩니다. (이 테스트엔 ESP8266 불필요)
3. 두 보드를 PC에 연결하고 각각 **시리얼 모니터 @115200** 을 엽니다. (포트별 별도 창)

## 정상 출력 예

Pico (송신) — `sent`는 "송신함"일 뿐:
```
TX #12  -> sent   [sent=12 fail=0]
```
Uno (수신) — **실제 링크 확인은 여기서**:
```
RX #12  senderMs=12345   [recv=12 missed=0]
```
Uno의 `RX #n`(recv)이 계속 올라가고 `missed`가 0에 가까우면 링크 정상입니다.

## 문제 해결

| 증상 | 원인 / 조치 |
|---|---|
| `RF24 init FAILED` | SPI 배선/전원 문제. Pico는 SPI0 핀(MISO=GP4, SCK=GP6, MOSI=GP7)·CE=GP14·CSN=GP15 확인, **3V3 공급** 확인 |
| Uno의 `RX #n`이 안 늘어남(또는 `RX #1`에서 멈춤) | 양쪽 스케치가 모두 **auto-ACK off 최신본**인지 확인(구버전은 #1에서 멈춤). 이후 배선·주소·채널·전원(캡)·거리 점검 |
| Uno에 아무것도 안 옴 | 주소(`"Node1"`)·채널(76)·payload 크기 불일치, Uno **DIP 스위치 USB 모드** 미설정, 안테나/접촉 불량 |
| 가끔 `missed`가 증가 | 전원 노이즈/거리. PA_LOW 유지, **캐패시터 추가**, 모듈 간 거리 단축, 금속/간섭원 회피 |
| 둘 다 멀쩡한데 안 됨 | 정품/짝퉁 모듈 전원 품질 문제 → VCC에 100µF + 0.1µF 병렬, 또는 3.3V 외부 공급 |

검증이 끝나면 본 시스템 펌웨어([pico_sensor_node.ino](../firmware/pico/pico_sensor_node/pico_sensor_node.ino), [uno_rf_receiver.ino](../firmware/uno/uno_rf_receiver/uno_rf_receiver.ino))로 교체하면 됩니다.
