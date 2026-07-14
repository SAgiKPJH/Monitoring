"""
Sensor node - Raspberry Pi Pico (MicroPython) - production firmware
------------------------------------------------------------------
Reads AM2320 (temp/humidity, I2C) + CdS light (ADC) + 18650 battery voltage (VSYS)
and sends a 32-byte struct over NRF24L01 to the Uno receiver. One-way, auto-ACK off.
On-board LED = status: boot 3 blinks; alive = short blink every 10s; AM2320 err = 2 fast + 1 long;
NRF init err = 3 fast + 1 long (repeats). Sends every 5 minutes.

Requires nrf24l01.py on the Pico (sits next to this file).
Board: original Raspberry Pi Pico (RP2040) running MicroPython.

Wiring:
  NRF24L01 (SPI0): CE=GP14 CSN=GP15 SCK=GP6 MOSI=GP7 MISO=GP4 VCC=3V3
  AM2320   (I2C0): SDA=GP0  SCL=GP1  VDD=3V3  GND=GND        (I2C addr 0x5C)
  CdS      (ADC0): 3V3 --[CdS]--+-- GP26 --[10k]-- GND       (more light -> higher value)
  18650: -> VSYS (pin 39). Voltage read on ADC3/GP29 (= VSYS/3 internally). Protected cell assumed.

Payload must stay identical to uno_rf_receiver.ino:
  struct { float temperature; float humidity; uint32 sequence; uint16 light;
           uint16 lightPercent; float battery; uint16 batteryPercent; char deviceId[6]; }
"""
from machine import Pin, SPI, I2C, ADC
from nrf24l01 import NRF24L01
import struct
import time

# ---- config ----
CHANNEL = 101             # must match the Uno (above the WiFi band)
ADDRESS = b"Node1"        # must match the Uno
DEVICE_ID = "BRB"       # THIS node's id (<=5 chars), forwarded to the DB as-is (change per Pico)
PAYLOAD = 28              # "<ffIHHfH6s"
SEND_PERIOD_MS = 300000   # read + transmit interval (5 min)
ERROR_RETRY_MS = 5000     # retry interval after an AM2320 error (LED keeps signalling)
HEARTBEAT_MS = 10000      # short "alive" blink every 10s while waiting between sends
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
vsys = ADC(29)                     # VSYS sense (ADC3/GP29 = VSYS/3) -> 18650 voltage
led = Pin(25, Pin.OUT, value=0)    # on-board status LED


# ---- status LED patterns ----
def _blink(on_ms, off_ms):
    led.on()
    time.sleep_ms(on_ms)
    led.off()
    time.sleep_ms(off_ms)


def _blink_fast(n):
    for _ in range(n):
        _blink(120, 130)


def _blink_long():
    _blink(600, 250)


def status_startup():
    for _ in range(3):             # boot: 3 blinks, ~1s apart
        _blink(200, 800)


def status_am2320_err():
    _blink_fast(2)                 # AM2320 error: 2 fast + 1 long
    _blink_long()


def status_nrf_err():
    _blink_fast(3)                 # NRF error: 3 fast + 1 long
    _blink_long()


def status_alive():
    led.on()                       # very short "still running" heartbeat
    time.sleep_ms(30)
    led.off()


status_startup()

# ---- radio ----
try:
    nrf = NRF24L01(spi, csn, ce, channel=CHANNEL, payload_size=PAYLOAD)
    nrf.reg_write(0x01, 0x00)      # EN_AA = 0 -> auto-ACK off (match the Uno)
    nrf.open_tx_pipe(ADDRESS)
    nrf.stop_listening()
except OSError as e:
    print("NRF init FAIL:", e)
    while True:                    # fatal -> keep signalling on the LED
        status_nrf_err()
        time.sleep_ms(1000)


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


def read_battery():
    # VSYS = (ADC/65535 * 3.3) * 3  (on-board 1/3 divider); ADC vref is a stable 3.3V.
    total = 0
    for _ in range(8):
        total += vsys.read_u16()
    v = (total / 8) * (3.3 * 3 / 65535)
    # 18650 Li-ion: ~4.2V full, ~3.0V empty (linear estimate, clamped 0..100)
    pct = int(max(0, min(100, (v - 3.0) / (4.2 - 3.0) * 100)))
    return v, pct


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
        status_am2320_err()
        time.sleep_ms(ERROR_RETRY_MS)
        continue
    light, lightpct = read_light()
    vbat, batpct = read_battery()
    buf = struct.pack("<ffIHHfH6s", t, h, seq & 0xFFFFFFFF, light, lightpct, vbat, batpct, DEVICE_ID.encode())
    try:
        nrf.send(buf)
        s = "sent"
    except OSError:
        s = "TX FAIL"
    print("{} #{}  T={:.1f}C H={:.1f}%  light={}({}%)  bat={:.2f}V({}%)  -> {}".format(
        DEVICE_ID, seq, t, h, light, lightpct, vbat, batpct, s))

    # wait for the next cycle; short heartbeat blink every 10s to show it's alive
    waited = 0
    while waited < SEND_PERIOD_MS:
        time.sleep_ms(HEARTBEAT_MS)
        status_alive()
        waited += HEARTBEAT_MS
