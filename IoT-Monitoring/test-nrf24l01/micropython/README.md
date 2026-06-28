# Pico TX 테스트 — MicroPython / Thonny 버전

Arduino `.ino` 대신 **Thonny(MicroPython)** 로 Pico 송신부를 돌리는 버전입니다.
**수신측(Uno)은 그대로 Arduino** [`uno_rx_test.ino`](../uno_rx_test/uno_rx_test.ino) 를 사용합니다 (변경 없음).

라디오 설정을 Uno의 RF24와 일치시켰으므로 서로 통신됩니다:

| 항목 | 값 | 비고 |
|---|---|---|
| 채널 | 76 | RF24 `setChannel(76)` |
| 데이터레이트 | 250kbps | 드라이버 기본값 `SPEED_250K` = `RF24_250KBPS` |
| 주소 | `b"Node1"` | 5바이트, RF24 `"Node1"` 와 동일 |
| 페이로드 | 8바이트 | `struct.pack("<II", ...)` = AVR `{uint32; uint32}` |
| CRC / 주소폭 | 16-bit / 5B | 드라이버 기본값 = RF24 기본값 |

## 파일
- `pico_tx_test.py` — 송신 테스트 스크립트 (Thonny에서 실행)
- `nrf24l01.py` — 공식 MicroPython 드라이버 (Pico에 **함께** 올려야 함)

## 배선 (Arduino 테스트와 동일, SPI0)
`CE=GP14, CSN=GP15, SCK=GP6, MOSI=GP7, MISO=GP4, VCC=`**`3V3`**(5V 금지). VCC–GND 사이 **10~100µF 캡** 권장.

## 실행 방법 (Thonny)
1. Pico를 USB로 연결 → Thonny 우하단 인터프리터가 **MicroPython (Raspberry Pi Pico)** 인지 확인.
   (아니면 Run → Select interpreter… 에서 선택. MicroPython 펌웨어가 없으면 Thonny가 설치 안내함)
2. **`nrf24l01.py` 를 Pico에 업로드**:
   - Thonny 좌측 **Files** 패널에서 PC의 `nrf24l01.py` 우클릭 → **Upload to /**
   - 또는 `nrf24l01.py` 열고 **File → Save as → Raspberry Pi Pico** → 파일명 `nrf24l01.py`
3. `pico_tx_test.py` 열고 **Run (F5)** → 셸(Shell)에 TX 로그 출력.
4. (선택) 전원만 켜도 자동 실행하려면 Pico에 **`main.py`** 라는 이름으로 저장.

> Uno 쪽: DIP 스위치를 **USB↔ATmega** 로 두고 `uno_rx_test.ino` 업로드 → 시리얼 모니터 @115200 에서 `RX #...` 확인.

> **auto-ACK는 끕니다(단방향).** MicroPython 드라이버 ↔ Arduino RF24의 auto-ACK 핸드셰이크가 불안정해, 스크립트가 `nrf.reg_write(0x01, 0x00)`(EN_AA=0)로 ACK를 끄고 Uno도 `setAutoAck(false)`로 맞춥니다. 그래서 Pico의 `sent`는 "송신함"일 뿐, **실제 수신 확인은 Uno의 `RX #n`** 으로 합니다.

## 정상 출력 예
Pico (Thonny Shell):
```
=== Pico NRF24L01 TX test (MicroPython) ===
TX #1 -> sent  [sent=1 fail=0]
TX #2 -> sent  [sent=2 fail=0]
```
Uno (시리얼 모니터 @115200) ← **여기서 링크 확인**:
```
RX #1  senderMs=... [recv=1 missed=0]
RX #2  senderMs=... [recv=2 missed=0]
```
- Uno의 `RX #n`(recv)이 계속 증가하면 링크 정상.
- `RX #1`에서 멈추면 구버전(auto-ACK on)일 수 있으니 최신 스크립트로 다시 실행하세요.

## 드라이버 출처
`nrf24l01.py` 는 micropython-lib 공식 드라이버(MIT)입니다:
<https://github.com/micropython/micropython-lib/blob/master/micropython/drivers/radio/nrf24l01/nrf24l01.py>
