# NRF24L01 링크 테스트 (Pico ↔ Uno)

Pico(송신) ↔ Uno(수신) NRF24L01 무선 링크만 검증. 두 보드는 선 연결 없이 무선으로 통신.

- `micropython/` — Pico 송신 (Thonny/MicroPython)
- `uno_rx_test/` — Uno 수신 (Arduino/C++)

## 연결 핀
| | Pico (SPI0) | Uno |
|---|---|---|
| CE | GP14 | D9 |
| CSN | GP15 | D10 |
| SCK | GP6 | D13 |
| MOSI | GP7 | D11 |
| MISO | GP4 | D12 |
| VCC | **3V3** | **3V3** |
| GND | GND | GND |

- VCC **5V 금지**. NRF VCC–GND에 **10~100µF 캡** 권장.

## 설정 (양쪽 동일)
- 채널 **101** (WiFi 2.4GHz 대역 위 → 간섭 적음), 250kbps, 주소 `"Node1"`, payload **8B**
- **auto-ACK off** (단방향) — MicroPython↔RF24 ACK 비호환 회피. 링크 확인은 **Uno의 `RX #n` 증가**로.

## 실행
- Uno 시리얼 모니터 **115200**.
