"""
Sensor node - Raspberry Pi Pico (MicroPython) - production firmware
------------------------------------------------------------------
Reads AM2320 (temp/humidity, I2C) + CdS light sensor (ADC) and sends a 16-byte
struct over NRF24L01 to the Uno receiver. One-way, auto-ACK off.
The on-board LED toggles every 1s as a "running" heartbeat.

Requires nrf24l01.py on the Pico (sits next to this file).
Board: original Raspberry Pi Pico (RP2040) running MicroPython.

Wiring:
  NRF24L01 (SPI0): CE=GP14 CSN=GP15 SCK=GP6 MOSI=GP7 MISO=GP4 VCC=3V3
  AM2320   (I2C0): SDA=GP0  SCL=GP1  VDD=3V3  GND=GND        (I2C addr 0x5C)
  CdS      (ADC0): 3V3 --[CdS]--+-- GP26 --[10k]-- GND       (more light -> higher value)
  LED: on-board GP25 (heartbeat)

Payload must stay identical to uno_rf_receiver.ino:
  struct { float temperature; float humidity; uint32 sequence; uint16 light; uint16 lightPercent; }
"""
from machine import Pin, SPI, I2C, ADC, Timer
from nrf24l01 import NRF24L01
import struct
import time

# ---- config ----
CHANNEL = 101             # must match the Uno (above the WiFi band)
ADDRESS = b"Node1"        # must match the Uno
PAYLOAD = 16              # "<ffIHH"
SEND_PERIOD_MS = 30000    # read + transmit interval (30s; temp/humidity change slowly)
AM2320_ADDR = 0x5C

# per-device calibration (tune against a reference; e.g. -2.0 if it reads 2C high)
TEMP_OFFSET = 0.0
HUM_OFFSET = 0.0

# ---- hardware ----
spi = SPI(0, sck=Pin(6), mosi=Pin(7), miso=Pin(4), baudrate=4_000_000, polarity=0, phase=0)
csn = Pin(15, Pin.OUT, value=1)
ce = Pin(14, Pin.OUT, value=0)
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100_000)
ldr = ADC(Pin(26))                 # CdS on ADC0
led = Pin(25, Pin.OUT)             # original Pico on-board LED (Pico W: Pin("LED"))

# ---- radio ----
nrf = NRF24L01(spi, csn, ce, channel=CHANNEL, payload_size=PAYLOAD)
nrf.reg_write(0x01, 0x00)          # EN_AA = 0 -> auto-ACK off (match the Uno)
nrf.open_tx_pipe(ADDRESS)
nrf.stop_listening()

# ---- 1s heartbeat LED (independent of the send loop) ----
def _beat(t):
    led.toggle()

Timer(period=1000, mode=Timer.PERIODIC, callback=_beat)


def read_am2320():
    try:
        i2c.writeto(AM2320_ADDR, b"\x00")   # wake (NAK -> OSError)
    except OSError:
        pass
    time.sleep_ms(1)
    i2c.writeto(AM2320_ADDR, b"\x03\x00\x04")
    time.sleep_ms(2)
    d = i2c.readfrom(AM2320_ADDR, 8)        # [03, 04, RHh, RHl, Th, Tl, CRCl, CRCh]
    crc = 0xFFFF
    for b in d[:6]:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else (crc >> 1)
    if (d[6] | (d[7] << 8)) != crc:
        raise OSError("AM2320 CRC error")
    rh = ((d[2] << 8) | d[3]) / 10.0
    t = (((d[4] & 0x7F) << 8) | d[5]) / 10.0
    if d[4] & 0x80:
        t = -t
    return t, rh


def read_light():
    raw = ldr.read_u16() >> 6               # 16-bit -> 0..1023
    pct = raw * 100 // 1023
    return raw, pct


print("=== Pico sensor node (MicroPython) ===")
seq = 0
while True:
    seq += 1
    try:
        t, h = read_am2320()
        t += TEMP_OFFSET
        h += HUM_OFFSET
    except OSError as e:
        print("AM2320 read fail:", e)
        time.sleep_ms(SEND_PERIOD_MS)
        continue
    light, lightpct = read_light()
    buf = struct.pack("<ffIHH", t, h, seq & 0xFFFFFFFF, light, lightpct)
    try:
        nrf.send(buf)
        s = "sent"
    except OSError:
        s = "TX FAIL"
    print("#{}  T={:.1f}C H={:.1f}%  light={}({}%)  -> {}".format(seq, t, h, light, lightpct, s))
    time.sleep_ms(SEND_PERIOD_MS)     # LED keeps blinking via the Timer during this
