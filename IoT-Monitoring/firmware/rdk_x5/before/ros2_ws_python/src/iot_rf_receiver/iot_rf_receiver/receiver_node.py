#!/usr/bin/env python3
"""
iot_rf_receiver — NRF24L01 수신을 ROS 2 노드(rclpy)로.
받은 측정/에러를 (1) API로 POST + (2) ROS 토픽으로 발행.
  node   : /rf_receiver
  topics : /iot/readings, /iot/errors   (std_msgs/String, JSON 문자열)
조회 예:  ros2 node list · ros2 topic echo /iot/readings
"""
import json
import struct
import time
import urllib.request

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

import spidev

# ===================== configuration =====================
SPI_BUS, SPI_DEV = 1, 1          # /dev/spidev1.1 (핀24=CS1). 배선에 맞게: for cs in 0 1 테스트로 확인
SPI_SPEED = 4_000_000            # 불안하면 1_000_000
RF_CHANNEL = 101
ADDRESS = b"Node1"
PAYLOAD_SIZE = 30                # "<ffIHHfH6sBB"

API_URL = "http://172.30.1.42:8080/api/readings"
ERROR_URL = "http://172.30.1.42:8080/api/errors"
API_KEY = ""

DEDUP_WINDOW_SEC = 30            # 같은 (deviceId,seq)가 N초 내면 첫 것만 (Pico 3회 전송)
POLL_SEC = 0.05                  # RX FIFO 확인 주기(50ms)
# =========================================================

CONFIG, EN_AA, EN_RXADDR, SETUP_AW, SETUP_RETR = 0x00, 0x01, 0x02, 0x03, 0x04
RF_CH, RF_SETUP, STATUS, RX_ADDR_P1, RX_PW_P1 = 0x05, 0x06, 0x07, 0x0B, 0x12
FIFO_STATUS, DYNPD, FEATURE = 0x17, 0x1C, 0x1D
R_RX_PAYLOAD, FLUSH_RX, W_REGISTER = 0x61, 0xE2, 0x20


class RfReceiver(Node):
    def __init__(self):
        super().__init__('rf_receiver')
        self.pub_read = self.create_publisher(String, 'iot/readings', 10)
        self.pub_err = self.create_publisher(String, 'iot/errors', 10)

        self.spi = spidev.SpiDev()
        self.spi.open(SPI_BUS, SPI_DEV)
        self.spi.max_speed_hz = SPI_SPEED
        self.spi.mode = 0

        self._seen = {}
        self._linked = False
        self.nrf_init()
        self.get_logger().info("RF receiver node up: ch=%d addr=Node1 payload=%d" % (RF_CHANNEL, PAYLOAD_SIZE))
        self.dump_registers()
        self.timer = self.create_timer(POLL_SEC, self.poll)

    # ---- NRF 레지스터 ----
    def wreg(self, reg, vals):
        if isinstance(vals, int):
            vals = [vals]
        self.spi.xfer2([W_REGISTER | (reg & 0x1F)] + list(vals))

    def rreg(self, reg, n=1):
        return self.spi.xfer2([reg & 0x1F] + [0xFF] * n)[1:]

    def nrf_init(self):
        self.wreg(EN_AA, 0x00)
        self.wreg(EN_RXADDR, 0x02)
        self.wreg(SETUP_AW, 0x03)
        self.wreg(SETUP_RETR, 0x00)
        self.wreg(RF_CH, RF_CHANNEL)
        self.wreg(RF_SETUP, 0x22)
        self.wreg(FEATURE, 0x00)
        self.wreg(DYNPD, 0x00)
        self.wreg(RX_ADDR_P1, list(ADDRESS))
        self.wreg(RX_PW_P1, PAYLOAD_SIZE)
        self.wreg(STATUS, 0x70)
        self.spi.xfer2([FLUSH_RX])
        self.wreg(CONFIG, 0x0F)
        time.sleep(0.005)

    def dump_registers(self):
        addr = "".join("%02X" % b for b in self.rreg(RX_ADDR_P1, 5))
        self.get_logger().info(
            "NRF regs: CONFIG=0x%02X RF_CH=%d RF_SETUP=0x%02X RX_PW_P1=%d STATUS=0x%02X ADDR=%s"
            % (self.rreg(CONFIG)[0], self.rreg(RF_CH)[0], self.rreg(RF_SETUP)[0],
               self.rreg(RX_PW_P1)[0], self.rreg(STATUS)[0], addr))

    def link_ok(self):
        return self.rreg(CONFIG)[0] == 0x0F

    # ---- 주기 폴링 ----
    def poll(self):
        if not self.link_ok():
            self.get_logger().warn("NRF 응답 없음 (SPI 실패) — CSN/MISO/SCK/전원 접촉 확인. 재시도")
            self._linked = False
            time.sleep(1)
            self.nrf_init()
            return
        if not self._linked:
            self.get_logger().info("link OK — listening for packets")
            self._linked = True
        while not (self.rreg(FIFO_STATUS)[0] & 0x01):     # RX FIFO 비어있지 않으면 드레인
            data = bytes(self.spi.xfer2([R_RX_PAYLOAD] + [0xFF] * PAYLOAD_SIZE)[1:])
            self.wreg(STATUS, 0x40)
            self.handle(data)

    # ---- de-dup ----
    def _dup(self, dev, mt, seq):
        now = time.monotonic()
        prev = self._seen.get(dev)
        if prev and prev[0] == mt and prev[1] == seq and (now - prev[2]) < DEDUP_WINDOW_SEC:
            return True
        self._seen[dev] = (mt, seq, now)
        return False

    def http_post(self, url, payload):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        if API_KEY:
            req.add_header("X-Api-Key", API_KEY)
        try:
            urllib.request.urlopen(req, timeout=4).read()
        except Exception as e:
            self.get_logger().error("POST %s 실패: %s" % (url, e))

    def handle(self, data):
        (t, h, seq, light, lightpct, batt, batpct, dev_b, mt, err) = struct.unpack("<ffIHHfH6sBB", data)
        dev = dev_b.split(b"\x00", 1)[0].decode("ascii", "replace")

        if mt == 1:   # 에러
            if self._dup(dev, 1, seq):
                return
            payload = {"type": "error", "deviceId": dev, "errorCode": err, "sequence": seq}
            self.get_logger().warn("[%s] ERROR code=%d seq=%d" % (dev, err, seq))
            self.http_post(ERROR_URL, payload)
            self.pub_err.publish(String(data=json.dumps(payload, ensure_ascii=False)))
            return

        if t == 0.0 and h == 0.0 and light == 0 and lightpct == 0:
            return
        if self._dup(dev, 0, seq):
            return

        payload = {"deviceId": dev, "temperature": round(t, 2), "humidity": round(h, 2),
                   "light": light, "lightPercent": lightpct, "battery": round(batt, 2),
                   "batteryPercent": batpct, "sequence": seq}
        self.get_logger().info("[%s] T=%.1f H=%.1f light=%d(%d%%) bat=%.2fV(%d%%) seq=%d"
                               % (dev, t, h, light, lightpct, batt, batpct, seq))
        self.http_post(API_URL, payload)
        self.pub_read.publish(String(data=json.dumps(payload, ensure_ascii=False)))


def main():
    rclpy.init()
    node = RfReceiver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.spi.close()
        except Exception:
            pass
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
