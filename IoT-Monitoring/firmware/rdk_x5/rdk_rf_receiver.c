/*
 * rdk_rf_receiver.c — RDK X5 NRF24L01 수신기 (ROS 없이 단독 실행)
 * ----------------------------------------------------------------
 * Pico(들)이 NRF24L01 로 보낸 30바이트 패킷을 받아 ASP.NET Core API 로 POST 한다.
 * SPI·프로토콜·중복제거·HTTP 로직은 rf_common.h 에 있고 여기서는 main() 만 담당한다.
 *   → 설정(SPI_DEV, POLL_US, API_URL 등)도 rf_common.h 상단에서 바꾼다.
 *
 * ROS 2 노드 버전은 ros2_ws/ 참고 (같은 rf_common.h 를 공유).
 *
 * 빌드 (RDK X5 에서):
 *   gcc rdk_rf_receiver.c -o rdk_rf_receiver -lcurl
 *   (CE 를 GPIO 로 제어하면 rf_common.h 의 CE_TIE_HIGH 를 끄고 -lgpiod 추가)
 *
 * 배선·설정: 같은 폴더의 README.md
 */
#include "rf_common.h"

int main(int argc, char **argv)
{
    /* stdout을 줄 단위 버퍼링 — ros2 launch/journald(파이프)에서도 로그가 즉시 보이게. */
    setvbuf(stdout, NULL, _IOLBF, 0);

    int debug = 0;
    for (int i = 1; i < argc; i++)
        if (!strcmp(argv[i], "-d") || !strcmp(argv[i], "--debug"))
            debug = 1;                     /* -d/--debug: print idle heartbeat */

    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);

    curl_global_init(CURL_GLOBAL_DEFAULT);

    spi_fd = spi_open(SPI_DEV);
    if (spi_fd < 0) return 1;
    if (ce_init() < 0) return 1;

    nrf_init();
    printf("RDK X5 NRF24L01 receiver up: ch=%d 250kbps addr=Node1 payload=%d\n",
           RF_CHANNEL, PAYLOAD_SIZE);
    dump_registers();

    uint8_t buf[PAYLOAD_SIZE];
    unsigned long idle = 0;
    unsigned long errs = 0;
    int linked = 0;
    while (running) {
        /* SPI reading 0x00/0xFF = the NRF isn't answering (wiring/contact), NOT data.
         * Say so and re-init instead of spinning silently on garbage packets.
         * 매초 출력하면 배선이 빠진 채 방치될 때 journald 가 디스크를 채운다
         * → 상태가 바뀔 때와 5분마다만 출력한다. */
        if (!link_ok()) {
            if (linked || errs % 300 == 0)
                printf("%s !! NRF 응답 없음 (SPI read 실패) — CSN/MISO/SCK/VCC/GND 접촉 확인. 재시도...\n", now_str());
            errs++;
            linked = 0;
            sleep(1);
            nrf_init();
            idle = 0;
            continue;
        }
        if (!linked) { printf("%s link OK — listening for packets...\n", now_str()); errs = 0; linked = 1; }

        /* 폴링 주기가 짧으면 SPI 전송마다 커널 로그(spidev xfer)가 쌓여 디스크를 채운다.
         * Pico 는 5분마다 3연속 전송하고 RX FIFO 가 3개를 담으므로 20ms 로도 충분하다. */
        if (!(reg_read(REG_FIFO_STATUS) & 0x01)) {   /* RX FIFO 에 데이터 있음 */
            while (!(reg_read(REG_FIFO_STATUS) & 0x01)) {   /* 쌓인 것 모두 비운다 */
                read_payload(buf, PAYLOAD_SIZE);
                reg_write(REG_STATUS, 0x40);         /* clear RX_DR */
                RfMessage m;
                if (rf_decode(buf, &m)) {
                    printf("%s %s\n", now_str(), m.log);
                    http_post(m.url, m.json);
                }
            }
            idle = 0;
        } else {
            usleep(POLL_US);
            if (debug && ++idle % (5000000 / POLL_US) == 0)   /* -d/--debug: ~5s 생존 신호 */
                printf("%s ...idle %lus: STATUS=0x%02X\n", now_str(),
                       idle * (unsigned long)POLL_US / 1000000UL, reg_read(REG_STATUS));
        }
    }

    ce_set(0);
#ifndef CE_TIE_HIGH
    gpiod_line_release(ce_line);
    gpiod_chip_close(ce_chip);
#endif
    close(spi_fd);
    curl_global_cleanup();
    printf("\nreceiver stopped\n");
    return 0;
}
