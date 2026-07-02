# AM2320 → NRF24L01 전송 테스트 (Pico → Uno)

AM2320(온습도, I2C)를 Pico에서 읽어 NRF24L01로 Uno에 전송. 단방향(auto-ACK off).

- `micropython/pico_am2320_tx.py` (+ `nrf24l01.py`) — Pico 송신 (Thonny)
- `uno_am2320_rx/uno_am2320_rx.ino` — Uno 수신 (Arduino)

> **NRF24L01 연결핀·라디오 설정은 [`../test-nrf24l01`](../test-nrf24l01) 참고** (CE/CSN/SCK/MOSI/MISO, 채널 101·250kbps·주소 `"Node1"`·auto-ACK off 모두 동일). 이 테스트는 payload만 다름 → **12B** (`<ffI` = temp+hum+seq).

## AM2320 연결핀
| AM2320 | Pico (I2C0) |
|---|---|
| VDD | 3V3 |
| SDA | GP0 |
| GND | GND |
| SCL | GP1 |

- 모듈에 풀업 없으면 SDA·SCL에 **4.7~10kΩ 풀업 → 3V3**.
- I2C 주소 **0x5C**, 읽기 주기 **2초**(최소 간격).

## 실행
1. Pico(Thonny): `nrf24l01.py` + `pico_am2320_tx.py` 업로드 → Run.
2. Uno: `uno_am2320_rx.ino` 업로드(DIP USB↔ATmega) → 시리얼 모니터 **115200**.
3. Uno에 `#n  T=..C  H=..%` 가 2초마다 출력되면 성공.
