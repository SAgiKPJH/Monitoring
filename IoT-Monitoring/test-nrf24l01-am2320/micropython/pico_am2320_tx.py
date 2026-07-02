"""
AM2320 -> NRF24L01 transmit test - Raspberry Pi Pico (MicroPython / Thonny)
Reads AM2320 (temp/humidity over I2C) and sends it to the Uno via NRF24L01.
One-way, auto-ACK off (matches the Uno).  Requires nrf24l01.py on the Pico.

Wiring:
  NRF24L01 (SPI0): CE=GP14 CSN=GP15 SCK=GP6 MOSI=GP7 MISO=GP4 VCC=3V3
  AM2320   (I2C0): SDA=GP0  SCL=GP1  VDD=3V3  GND=GND   (I2C addr 0x5C)
"""
from machine import Pin, SPI, I2C
from nrf24l01 import NRF24L01
import struct
import time

# --- NRF24L01 on SPI0 ---
spi = SPI(0, sck=Pin(6), mosi=Pin(7), miso=Pin(4), baudrate=4_000_000, polarity=0, phase=0)
csn = Pin(15, Pin.OUT, value=1)
ce = Pin(14, Pin.OUT, value=0)

# --- AM2320 on I2C0 ---
i2c = I2C(0, sda=Pin(0), scl=Pin(1), freq=100_000)
AM2320_ADDR = 0x5C

# --- radio config (must match the Uno) ---
ADDRESS = b"Node1"
CHANNEL = 101         # above the WiFi 2.4GHz band -> less interference
PAYLOAD = 12          # "<ffI" = temperature(float) + humidity(float) + sequence(uint32)

nrf = NRF24L01(spi, csn, ce, channel=CHANNEL, payload_size=PAYLOAD)
nrf.reg_write(0x01, 0x00)     # EN_AA = 0 -> auto-ACK off (match the Uno)
nrf.open_tx_pipe(ADDRESS)
nrf.stop_listening()


def read_am2320():
    # wake the sensor (it sleeps; first transaction is NAKed)
    try:
        i2c.writeto(AM2320_ADDR, b"\x00")
    except OSError:
        pass
    time.sleep_ms(1)
    # function 0x03 = read registers, start 0x00, length 4
    i2c.writeto(AM2320_ADDR, b"\x03\x00\x04")
    time.sleep_ms(2)
    d = i2c.readfrom(AM2320_ADDR, 8)   # [03, 04, RHh, RHl, Th, Tl, CRCl, CRCh]
    # CRC-16 (modbus) over the first 6 bytes
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


print("=== Pico AM2320 -> NRF24L01 TX ===")
seq = 0
while True:
    seq += 1
    try:
        t, h = read_am2320()
    except OSError as e:
        print("AM2320 read fail:", e)
        time.sleep(2)
        continue
    buf = struct.pack("<ffI", t, h, seq & 0xFFFFFFFF)
    try:
        nrf.send(buf)
        s = "sent"
    except OSError:
        s = "TX FAIL"
    print("#{}  T={:.1f}C  H={:.1f}%  -> {}".format(seq, t, h, s))
    time.sleep(2)     # AM2320 min read interval ~2s
