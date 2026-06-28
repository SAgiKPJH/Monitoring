"""
NRF24L01 link test - Raspberry Pi Pico (TRANSMITTER) - MicroPython / Thonny
---------------------------------------------------------------------------
Sends an incrementing counter to the Uno R3 once per second.

The RECEIVER stays on Arduino: ../uno_rx_test/uno_rx_test.ino
Radio settings here are matched to the Uno's RF24 so they interoperate:
  channel 76, 250kbps, address b"Node1", 8-byte payload, auto-ACK.

Requires: nrf24l01.py uploaded onto the Pico (sits next to this file).
Board:    original Raspberry Pi Pico (RP2040) running MicroPython.

Wiring (NRF24L01 -> Pico, SPI0)  [same as the Arduino test]:
  VCC -> 3V3 (NEVER 5V)   GND -> GND
  CE  -> GP14   CSN -> GP15
  SCK -> GP6    MOSI -> GP7   MISO -> GP4
  (10~100uF cap across VCC/GND recommended)

Run with Thonny's green Run button (F5).
Save as main.py on the Pico if you want it to auto-run on power-up.
"""
from machine import Pin, SPI
from nrf24l01 import NRF24L01
import struct
import time

# --- wiring (must match the Uno + the Arduino sketch) ---
SPI_ID = 0
PIN_SCK, PIN_MOSI, PIN_MISO = 6, 7, 4   # SPI0
PIN_CE, PIN_CSN = 14, 15

# --- radio config (must match the Uno RF24) ---
ADDRESS = b"Node1"   # 5 bytes, identical to the receiver
CHANNEL = 76
PAYLOAD = 8          # 2x uint32 == Uno setPayloadSize(sizeof(TestPacket))

spi = SPI(SPI_ID, sck=Pin(PIN_SCK), mosi=Pin(PIN_MOSI), miso=Pin(PIN_MISO),
          baudrate=4_000_000, polarity=0, phase=0)   # nRF24L01 = SPI mode 0
csn = Pin(PIN_CSN, mode=Pin.OUT, value=1)
ce = Pin(PIN_CE, mode=Pin.OUT, value=0)

# Driver defaults already match the Uno: 250kbps (SPEED_250K), 5-byte address,
# 16-bit CRC. We only set channel + payload size + our pipe address.
nrf = NRF24L01(spi, csn, ce, channel=CHANNEL, payload_size=PAYLOAD)
# Disable auto-ACK (EN_AA register = 0x01 -> 0). The MicroPython driver <-> Arduino
# RF24 auto-ACK handshake is unreliable, and a failed ACK leaves the packet stuck in
# the TX FIFO (the driver never flush_tx on MAX_RT). One-way (no ACK) is all the
# production data flow needs. Confirm reception on the Uno's "RX #n" counter.
nrf.reg_write(0x01, 0x00)
nrf.open_tx_pipe(ADDRESS)
nrf.stop_listening()    # transmitter mode

print("=== Pico NRF24L01 TX test (MicroPython) ===")
print("channel={} payload={}B addr={} auto-ack=OFF".format(CHANNEL, PAYLOAD, ADDRESS))
print("sending 1 packet/sec  (watch the Uno's RX #n to confirm the link)")

counter = 0
ok = 0
fail = 0
while True:
    counter += 1
    ms = time.ticks_ms() & 0xFFFFFFFF
    # little-endian uint32 x2 == AVR struct { uint32 counter; uint32 senderMillis; }
    buf = struct.pack("<II", counter & 0xFFFFFFFF, ms)
    try:
        nrf.send(buf)             # auto-ACK off -> returns once the packet is transmitted
        ok += 1
        result = "sent"
    except OSError:
        fail += 1
        result = "TX FAIL"
    print("TX #{} -> {}  [sent={} fail={}]".format(counter, result, ok, fail))
    time.sleep(1)
