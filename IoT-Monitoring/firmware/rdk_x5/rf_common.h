/*
 * rf_common.h — NRF24L01 수신 공통 로직 (SPI · 프로토콜 · 중복제거 · HTTP)
 * -----------------------------------------------------------------------
 * 단독 C 버전(rdk_rf_receiver.c)과 ROS 2 C++ 노드(ros2_ws/.../rf_receiver_node.cpp)가
 * 같은 코드를 쓰도록 main() 을 제외한 전부를 여기 모았다.
 * 설정(SPI_DEV, POLL_US, API_URL 등)도 이 파일 상단 한 곳에서만 바꾸면 된다.
 *
 * C 와 C++ 양쪽에서 컴파일된다 (static inline 함수 + 헤더 전용).
 */
#ifndef RF_COMMON_H
#define RF_COMMON_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <time.h>
#include <sys/ioctl.h>
#include <linux/spi/spidev.h>
#include <curl/curl.h>

/* ===================== configuration — edit for your board/network ===================== */
#define SPI_DEV     "/dev/spidev1.1"   /* CSN is wired to CS1 = pin 26 (use spidev1.0 if on pin 24) */
#define SPI_SPEED   4000000            /* 4 MHz (NRF max 10 MHz); drop to 1000000 if unreliable */
/* CE handling: simplest is to wire NRF CE -> 3V3 (always-on RX) and keep CE_TIE_HIGH
 * defined — this drops the libgpiod dependency entirely. Config is written while the
 * radio is powered down (PWR_UP set last), so a permanently-high CE is safe.
 * To drive CE from a GPIO instead, comment out CE_TIE_HIGH and set CE_CHIP/CE_LINE. */
#define CE_TIE_HIGH 1
#define CE_CHIP     "gpiochip0"        /* (only if CE_TIE_HIGH is off) find with `gpioinfo` */
#define CE_LINE     22                 /* (only if CE_TIE_HIGH is off) line offset on CE_CHIP */

#define RF_CHANNEL   101               /* must match the Pico/Uno */
#define PAYLOAD_SIZE 30                /* "<ffIHHfH6sBB" — must match the Pico/Uno */
#define DEDUP_WINDOW_SEC 30            /* keep only the first of identical (deviceId,seq) within N s (Pico sends 3x) */
#define POLL_US 20000          /* RX FIFO 폴링 주기(us). 짧을수록 커널 SPI 로그가 폭증한다 */
static const uint8_t ADDRESS[5] = { 'N', 'o', 'd', 'e', '1' };  /* "Node1" */

#define API_URL   "http://172.30.1.42:8080/api/readings"
#define ERROR_URL "http://172.30.1.42:8080/api/errors"
#define API_KEY   ""                   /* set to match the API's API_KEY, or leave empty */
/* ======================================================================================= */

#ifndef CE_TIE_HIGH
#include <gpiod.h>
#endif

/* NRF24L01 SPI commands */
#define CMD_W_REGISTER   0x20
#define CMD_R_RX_PAYLOAD 0x61
#define CMD_FLUSH_RX     0xE2
#define CMD_NOP          0xFF

/* NRF24L01 registers */
#define REG_CONFIG     0x00
#define REG_EN_AA      0x01
#define REG_EN_RXADDR  0x02
#define REG_SETUP_AW   0x03
#define REG_SETUP_RETR 0x04
#define REG_RF_CH      0x05
#define REG_RF_SETUP   0x06
#define REG_STATUS     0x07
#define REG_RX_ADDR_P1 0x0B
#define REG_RX_PW_P1   0x12
#define REG_FIFO_STATUS 0x17
#define REG_DYNPD      0x1C
#define REG_FEATURE    0x1D

/* Wire payload — identical layout to the Pico (TX) and Uno. Packed so sizeof == 30. */
#pragma pack(push, 1)
typedef struct {
    float    temperature;
    float    humidity;
    uint32_t sequence;
    uint16_t light;
    uint16_t lightPercent;
    float    battery;
    uint16_t batteryPercent;
    char     deviceId[6];
    uint8_t  msgType;     /* 0 = sensor reading, 1 = error report */
    uint8_t  errorCode;   /* when msgType==1: 1=AM2320, 2=NRF */
} SensorPayload;
#pragma pack(pop)

static int spi_fd = -1;
static volatile sig_atomic_t running = 1;
#ifndef CE_TIE_HIGH
static struct gpiod_chip *ce_chip;
static struct gpiod_line *ce_line;
#endif

/* ---- SPI helpers ---- */
static inline void spi_xfer(const uint8_t *tx, uint8_t *rx, int len)
{
    struct spi_ioc_transfer tr;
    memset(&tr, 0, sizeof(tr));
    tr.tx_buf = (unsigned long)tx;
    tr.rx_buf = (unsigned long)rx;
    tr.len = len;
    tr.speed_hz = SPI_SPEED;
    tr.bits_per_word = 8;
    if (ioctl(spi_fd, SPI_IOC_MESSAGE(1), &tr) < 0)
        perror("spi transfer");
}

static inline void reg_write(uint8_t reg, uint8_t val)
{
    uint8_t tx[2] = { (uint8_t)(CMD_W_REGISTER | (reg & 0x1F)), val };
    uint8_t rx[2];
    spi_xfer(tx, rx, 2);
}

static inline void reg_write_bytes(uint8_t reg, const uint8_t *buf, int n)
{
    uint8_t tx[1 + 32], rx[1 + 32];
    tx[0] = (uint8_t)(CMD_W_REGISTER | (reg & 0x1F));
    memcpy(tx + 1, buf, n);
    spi_xfer(tx, rx, 1 + n);
}

static inline uint8_t reg_read(uint8_t reg)
{
    uint8_t tx[2] = { (uint8_t)(reg & 0x1F), CMD_NOP };
    uint8_t rx[2];
    spi_xfer(tx, rx, 2);
    return rx[1];
}

static inline void reg_read_bytes(uint8_t reg, uint8_t *buf, int n)
{
    uint8_t tx[1 + 32], rx[1 + 32];
    tx[0] = (uint8_t)(reg & 0x1F);
    memset(tx + 1, CMD_NOP, n);
    spi_xfer(tx, rx, 1 + n);
    memcpy(buf, rx + 1, n);
}

/* Read back key registers to verify SPI comms + that config was applied. */
static inline void dump_registers(void)
{
    uint8_t addr[5] = { 0 };
    reg_read_bytes(REG_RX_ADDR_P1, addr, 5);
    printf("NRF regs: CONFIG=0x%02X EN_AA=0x%02X EN_RXADDR=0x%02X RF_CH=%u RF_SETUP=0x%02X "
           "RX_PW_P1=%u STATUS=0x%02X FIFO=0x%02X ADDR_P1=%02X%02X%02X%02X%02X\n",
           reg_read(REG_CONFIG), reg_read(REG_EN_AA), reg_read(REG_EN_RXADDR),
           reg_read(REG_RF_CH), reg_read(REG_RF_SETUP), reg_read(REG_RX_PW_P1),
           reg_read(REG_STATUS), reg_read(REG_FIFO_STATUS),
           addr[0], addr[1], addr[2], addr[3], addr[4]);
    printf("  expect:  CONFIG=0x0F EN_AA=0x00 EN_RXADDR=0x02 RF_CH=101 RF_SETUP=0x22 "
           "RX_PW_P1=30 ADDR_P1=4E6F646531(\"Node1\")\n");
    printf("  (all 0x00 => MISO/SPI 안됨 · all 0xFF => NRF 전원/MOSI/CSN 문제)\n");
}

/* CONFIG reads back 0x0F only when the NRF is actually answering over SPI. */
static inline int link_ok(void) { return reg_read(REG_CONFIG) == 0x0F; }

static inline void flush_rx(void)
{
    uint8_t tx = CMD_FLUSH_RX, rx;
    spi_xfer(&tx, &rx, 1);
}

static inline void read_payload(uint8_t *buf, int n)
{
    uint8_t tx[1 + 32], rx[1 + 32];
    tx[0] = CMD_R_RX_PAYLOAD;
    memset(tx + 1, CMD_NOP, n);
    spi_xfer(tx, rx, 1 + n);
    memcpy(buf, rx + 1, n);
}

/* ---- CE control ---- */
#ifndef CE_TIE_HIGH
static inline int ce_init(void)
{
    ce_chip = gpiod_chip_open_by_name(CE_CHIP);
    if (!ce_chip) { perror("gpiod_chip_open " CE_CHIP); return -1; }
    ce_line = gpiod_chip_get_line(ce_chip, CE_LINE);
    if (!ce_line) { perror("gpiod_chip_get_line"); return -1; }
    if (gpiod_line_request_output(ce_line, "nrf24-ce", 0) < 0) {
        perror("gpiod_line_request_output");
        return -1;
    }
    return 0;
}
static inline void ce_set(int v) { gpiod_line_set_value(ce_line, v); }
#else
static inline int ce_init(void) { return 0; }     /* CE hard-wired to 3V3 */
static inline void ce_set(int v) { (void)v; }      /* no-op — CE stays high */
#endif

/* ---- radio init: mirror the Uno's working config ---- */
static inline void nrf_init(void)
{
    ce_set(0);                                 /* standby while configuring */
    reg_write(REG_EN_AA, 0x00);                /* auto-ACK OFF (match the Pico) */
    reg_write(REG_EN_RXADDR, 0x02);            /* enable RX pipe 1 */
    reg_write(REG_SETUP_AW, 0x03);             /* 5-byte address width */
    reg_write(REG_SETUP_RETR, 0x00);           /* no auto-retransmit (RX side) */
    reg_write(REG_RF_CH, RF_CHANNEL);          /* channel 101 */
    reg_write(REG_RF_SETUP, 0x22);             /* 250kbps + PA_LOW */
    reg_write(REG_FEATURE, 0x00);              /* no dynamic payload / ack payload */
    reg_write(REG_DYNPD, 0x00);
    reg_write_bytes(REG_RX_ADDR_P1, ADDRESS, 5);
    reg_write(REG_RX_PW_P1, PAYLOAD_SIZE);     /* static 30-byte payload */
    reg_write(REG_STATUS, 0x70);               /* clear RX_DR|TX_DS|MAX_RT */
    flush_rx();
    reg_write(REG_CONFIG, 0x0F);               /* EN_CRC|CRCO(16-bit)|PWR_UP|PRIM_RX */
    usleep(5000);                              /* power-up settle */
    ce_set(1);                                 /* start listening */
    usleep(150);
}

/* ---- HTTP ---- */
static inline size_t discard_cb(char *p, size_t s, size_t n, void *u)
{
    (void)p; (void)u;
    return s * n;
}

static inline void http_post(const char *url, const char *json)
{
    CURL *c = curl_easy_init();
    if (!c) return;
    struct curl_slist *h = NULL;
    h = curl_slist_append(h, "Content-Type: application/json");
    if (API_KEY[0]) {
        char keyhdr[128];
        snprintf(keyhdr, sizeof(keyhdr), "X-Api-Key: %s", API_KEY);
        h = curl_slist_append(h, keyhdr);
    }
    curl_easy_setopt(c, CURLOPT_URL, url);
    curl_easy_setopt(c, CURLOPT_POSTFIELDS, json);
    curl_easy_setopt(c, CURLOPT_HTTPHEADER, h);
    curl_easy_setopt(c, CURLOPT_TIMEOUT_MS, 4000L);
    curl_easy_setopt(c, CURLOPT_WRITEFUNCTION, discard_cb);
    CURLcode rc = curl_easy_perform(c);          /* fire-and-forget */
    if (rc != CURLE_OK)
        fprintf(stderr, "POST %s failed: %s\n", url, curl_easy_strerror(rc));
    curl_slist_free_all(h);
    curl_easy_cleanup(c);
}

/* ---- timestamp + de-dup ---- */
static inline const char *now_str(void)
{
    static char buf[24];
    time_t t = time(NULL);
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", localtime(&t));
    return buf;
}

/* Pico sends each packet 3x. Keep only the FIRST of an identical (deviceId, seq, msgType)
 * seen within DEDUP_WINDOW_SEC; later copies are dropped. */
static struct { char id[7]; uint32_t seq; uint8_t mt; time_t t; int valid; } g_seen[16];

static inline int is_duplicate(const char *id, uint32_t seq, uint8_t mt)
{
    time_t now = time(NULL);
    for (int i = 0; i < 16; i++) {                 /* known device? */
        if (g_seen[i].valid && strcmp(g_seen[i].id, id) == 0) {
            if (g_seen[i].seq == seq && g_seen[i].mt == mt &&
                (now - g_seen[i].t) < DEDUP_WINDOW_SEC)
                return 1;                          /* same packet within window -> drop */
            g_seen[i].seq = seq; g_seen[i].mt = mt; g_seen[i].t = now;
            return 0;
        }
    }
    for (int i = 0; i < 16; i++) {                 /* new device -> record */
        if (!g_seen[i].valid) {
            strncpy(g_seen[i].id, id, 6); g_seen[i].id[6] = '\0';
            g_seen[i].seq = seq; g_seen[i].mt = mt; g_seen[i].t = now; g_seen[i].valid = 1;
            break;
        }
    }
    return 0;
}

/* ---- payload handling ---- */

/* ---- 수신 패킷 → 전송용 JSON + 로그 문자열 ----
 * 반환 1 = 보낼 것, 0 = 무시(중복/빈 패킷). 로깅·발행은 호출자가 담당한다. */
typedef struct {
    char id[7];
    int  is_error;
    const char *url;
    char json[256];
    char log[224];
} RfMessage;

static inline int rf_decode(const uint8_t *raw, RfMessage *m)
{
    SensorPayload p;
    memcpy(&p, raw, sizeof(p));

    memcpy(m->id, p.deviceId, 6);
    m->id[6] = '\0';

    if (p.msgType == 1) {                    /* 에러 리포트 -> /api/errors */
        if (is_duplicate(m->id, p.sequence, 1)) return 0;
        m->is_error = 1;
        m->url = ERROR_URL;
        snprintf(m->json, sizeof(m->json),
            "{\"type\":\"error\",\"deviceId\":\"%s\",\"errorCode\":%u,\"sequence\":%lu}",
            m->id, (unsigned)p.errorCode, (unsigned long)p.sequence);
        snprintf(m->log, sizeof(m->log), "[%s] ERROR code=%u seq=%lu -> /api/errors",
            m->id, (unsigned)p.errorCode, (unsigned long)p.sequence);
        return 1;
    }

    /* 빈/쓰레기 패킷 (센서값 전부 0) 무시 */
    if (p.temperature == 0.0f && p.humidity == 0.0f && p.light == 0 && p.lightPercent == 0)
        return 0;
    if (is_duplicate(m->id, p.sequence, 0)) return 0;   /* 2·3번째 재전송분 제거 */

    m->is_error = 0;
    m->url = API_URL;
    snprintf(m->json, sizeof(m->json),
        "{\"deviceId\":\"%s\",\"temperature\":%.2f,\"humidity\":%.2f,"
        "\"light\":%u,\"lightPercent\":%u,\"battery\":%.2f,\"batteryPercent\":%u,\"sequence\":%lu}",
        m->id, p.temperature, p.humidity,
        (unsigned)p.light, (unsigned)p.lightPercent, p.battery,
        (unsigned)p.batteryPercent, (unsigned long)p.sequence);
    snprintf(m->log, sizeof(m->log),
        "[%s] T=%.1f H=%.1f light=%u(%u%%) bat=%.2fV(%u%%) seq=%lu",
        m->id, p.temperature, p.humidity,
        (unsigned)p.light, (unsigned)p.lightPercent, p.battery,
        (unsigned)p.batteryPercent, (unsigned long)p.sequence);
    return 1;
}

static inline int spi_open(const char *dev)
{
    int fd = open(dev, O_RDWR);
    if (fd < 0) { perror("open spidev"); return -1; }
    uint8_t mode = SPI_MODE_0, bits = 8;
    uint32_t speed = SPI_SPEED;
    ioctl(fd, SPI_IOC_WR_MODE, &mode);
    ioctl(fd, SPI_IOC_WR_BITS_PER_WORD, &bits);
    ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, &speed);
    return fd;
}

static inline void on_signal(int s) { (void)s; running = 0; }

#endif /* RF_COMMON_H */
