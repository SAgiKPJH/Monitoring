#!/usr/bin/env python3
"""
RDK X5 (Linux SBC) - NRF24L01 receiver -> HTTP uplink  (Python version)
-----------------------------------------------------------------------
Same job as rdk_rf_receiver.c: receives the 30-byte sensor/error struct over
NRF24L01 and POSTs it as JSON to the ASP.NET Core API.

Radio config mirrors the proven Uno setup: channel 101, 250kbps, PA_LOW,
16-bit CRC, auto-ACK OFF, address "Node1", static 30-byte payload on pipe 1.

  Pico(s) --NRF24L01--> RDK X5 (this script) --HTTP--> API (/api/readings, /api/errors)

Wiring: NRF CE -> 3V3 (always-on RX, no GPIO needed).  CSN -> spi1 CS0 (pin 24)
        => /dev/spidev1.0 (bus 1, device 0).  See README.md.

Run:
  sudo apt install -y python3-spidev
  sudo python3 rdk_rf_receiver.py
"""
import sys
import spidev
import struct
import time
import json
import urllib.request

# ===================== configuration =====================
SPI_BUS, SPI_DEV = 1, 1          # /dev/spidev1.1  (CSN on CS1 = pin 26; use 1,0 if on pin 24)
SPI_SPEED = 4_000_000            # 4 MHz (NRF max 10 MHz); drop to 1_000_000 if unreliable
RF_CHANNEL = 101
ADDRESS = b"Node1"               # must match the Pico
PAYLOAD_SIZE = 30                # "<ffIHHfH6sBB"

API_URL = "http://172.30.1.42:8080/api/readings"
ERROR_URL = "http://172.30.1.42:8080/api/errors"
API_KEY = ""                     # set to match the API's API_KEY, or leave empty
DEDUP_WINDOW_SEC = 30            # keep only the first of identical (deviceId,seq) within N s (Pico sends 3x)
# =========================================================

# NRF24L01 registers / commands
CONFIG, EN_AA, EN_RXADDR, SETUP_AW, SETUP_RETR = 0x00, 0x01, 0x02, 0x03, 0x04
RF_CH, RF_SETUP, STATUS, RX_ADDR_P1, RX_PW_P1 = 0x05, 0x06, 0x07, 0x0B, 0x12
FIFO_STATUS, DYNPD, FEATURE = 0x17, 0x1C, 0x1D
R_RX_PAYLOAD, FLUSH_RX, W_REGISTER = 0x61, 0xE2, 0x20

spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEV)
spi.max_speed_hz = SPI_SPEED
spi.mode = 0


def wreg(reg, vals):
    if isinstance(vals, int):
        vals = [vals]
    spi.xfer2([W_REGISTER | (reg & 0x1F)] + list(vals))


def rreg(reg, n=1):
    return spi.xfer2([reg & 0x1F] + [0xFF] * n)[1:]


def nrf_init():
    wreg(EN_AA, 0x00)                 # auto-ACK OFF (match the Pico)
    wreg(EN_RXADDR, 0x02)             # enable RX pipe 1
    wreg(SETUP_AW, 0x03)              # 5-byte address width
    wreg(SETUP_RETR, 0x00)
    wreg(RF_CH, RF_CHANNEL)           # channel 101
    wreg(RF_SETUP, 0x22)              # 250kbps + PA_LOW
    wreg(FEATURE, 0x00)
    wreg(DYNPD, 0x00)
    wreg(RX_ADDR_P1, list(ADDRESS))   # "Node1"
    wreg(RX_PW_P1, PAYLOAD_SIZE)      # static 30-byte payload
    wreg(STATUS, 0x70)                # clear RX_DR|TX_DS|MAX_RT
    spi.xfer2([FLUSH_RX])
    wreg(CONFIG, 0x0F)                # EN_CRC|CRCO(16-bit)|PWR_UP|PRIM_RX
    time.sleep(0.005)                 # power-up settle (CE tied high -> RX)


def dump_registers():
    addr = "".join("%02X" % b for b in rreg(RX_ADDR_P1, 5))
    print("NRF regs: CONFIG=0x%02X EN_RXADDR=0x%02X RF_CH=%d RF_SETUP=0x%02X "
          "RX_PW_P1=%d STATUS=0x%02X ADDR_P1=%s"
          % (rreg(CONFIG)[0], rreg(EN_RXADDR)[0], rreg(RF_CH)[0], rreg(RF_SETUP)[0],
             rreg(RX_PW_P1)[0], rreg(STATUS)[0], addr))
    print('  expect:  CONFIG=0x0F EN_RXADDR=0x02 RF_CH=101 RF_SETUP=0x22 '
          'RX_PW_P1=30 ADDR_P1=4E6F646531("Node1")')


def http_post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    if API_KEY:
        req.add_header("X-Api-Key", API_KEY)
    try:
        urllib.request.urlopen(req, timeout=4).read()   # fire-and-forget
    except Exception as e:
        print("POST %s failed: %s" % (url, e))


_seen = {}   # deviceId -> (msgtype, seq, monotonic_time), for de-dup of the Pico's 3x send


def _is_dup(dev, msgtype, seq):
    prev = _seen.get(dev)
    now = time.monotonic()
    if prev and prev[0] == msgtype and prev[1] == seq and (now - prev[2]) < DEDUP_WINDOW_SEC:
        return True
    _seen[dev] = (msgtype, seq, now)
    return False


def now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def handle_payload(data):
    (t, h, seq, light, lightpct, batt, batpct,
     device, msgtype, errcode) = struct.unpack("<ffIHHfH6sBB", data)
    dev = device.split(b"\x00", 1)[0].decode("ascii", "replace")

    if msgtype == 1:   # error report -> /api/errors
        if _is_dup(dev, 1, seq):
            return
        print("%s [%s] ERROR code=%d seq=%d -> /api/errors" % (now_str(), dev, errcode, seq))
        http_post(ERROR_URL, {"type": "error", "deviceId": dev,
                              "errorCode": errcode, "sequence": seq})
        return

    if t == 0.0 and h == 0.0 and light == 0 and lightpct == 0:
        return   # skip empty/garbage packets

    if _is_dup(dev, 0, seq):   # drop the 2nd/3rd retransmit copy
        return

    print("%s [%s] T=%.1f H=%.1f light=%d(%d%%) bat=%.2fV(%d%%) seq=%d"
          % (now_str(), dev, t, h, light, lightpct, batt, batpct, seq))
    http_post(API_URL, {"deviceId": dev, "temperature": round(t, 2),
                        "humidity": round(h, 2), "light": light,
                        "lightPercent": lightpct, "battery": round(batt, 2),
                        "batteryPercent": batpct, "sequence": seq})


def link_ok():
    # CONFIG reads back 0x0F only when the NRF is actually responding over SPI.
    return rreg(CONFIG)[0] == 0x0F


def main():
    nrf_init()
    print("RDK X5 NRF24L01 receiver up (python): ch=%d 250kbps addr=Node1 payload=%d"
          % (RF_CHANNEL, PAYLOAD_SIZE))
    dump_registers()

    debug = "-d" in sys.argv or "--debug" in sys.argv
    linked = False
    idle = 0
    try:
        while True:
            # SPI reading 0x00/0xFF = the NRF isn't answering (wiring/contact), NOT data.
            # Say so and re-init instead of spinning silently on garbage packets.
            if not link_ok():
                print("!! NRF 응답 없음 (SPI read 실패) — CSN/MISO/SCK/VCC/GND 접촉 확인. 재시도...")
                linked = False
                time.sleep(1)
                nrf_init()
                idle = 0
                continue
            if not linked:
                print("link OK — listening for packets...")
                linked = True

            fifo = rreg(FIFO_STATUS)[0]
            if not (fifo & 0x01):                        # RX FIFO not empty
                data = bytes(spi.xfer2([R_RX_PAYLOAD] + [0xFF] * PAYLOAD_SIZE)[1:])
                wreg(STATUS, 0x40)                       # clear RX_DR
                handle_payload(data)
                idle = 0
            else:
                time.sleep(0.002)
                if debug:                                # -d/--debug: ~5s liveness heartbeat
                    idle += 1
                    if idle % 2500 == 0:
                        print("...idle %ds: STATUS=0x%02X" % (idle * 2 // 1000, rreg(STATUS)[0]))
    except KeyboardInterrupt:
        pass
    finally:
        spi.close()
        print("\nreceiver stopped")


if __name__ == "__main__":
    main()
