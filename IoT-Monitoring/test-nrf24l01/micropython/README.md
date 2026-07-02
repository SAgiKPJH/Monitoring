# Pico 송신 — MicroPython / Thonny

- `pico_tx_test.py` — 송신 스크립트
- `nrf24l01.py` — 공식 드라이버(MIT), Pico에 함께 업로드

## 연결 핀 (Pico SPI0)
| NRF24L01 | Pico |
|---|---|
| CE | GP14 |
| CSN | GP15 |
| SCK | GP6 |
| MOSI | GP7 |
| MISO | GP4 |
| VCC | **3V3** |
| GND | GND |

- VCC **5V 금지**. NRF VCC–GND에 **10~100µF 캡** 권장.

## 설정
- 채널 **101** (WiFi 대역 위 → 간섭 적음), 250kbps, 주소 `b"Node1"`, payload **8B**
- **auto-ACK off**: `nrf.reg_write(0x01, 0x00)` (Uno도 `radio.setAutoAck(false)`)

## 실행 (Thonny)
1. `nrf24l01.py`를 Pico에 업로드 (Files 패널 → Upload to /).
2. `pico_tx_test.py` Run → Uno 시리얼(@115200)에서 `RX #n` 증가 확인.
