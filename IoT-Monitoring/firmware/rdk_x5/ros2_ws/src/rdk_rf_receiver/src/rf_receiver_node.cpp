// rf_receiver_node.cpp — NRF24L01 수신기를 ROS 2 노드(rclcpp)로 실행
// ---------------------------------------------------------------------
//   node   : /rf_receiver
//   topics : /iot/readings , /iot/errors   (std_msgs/String, JSON 문자열)
//
// 수신 패킷을 (1) 기존처럼 API 로 POST 하고 (2) ROS 토픽으로도 발행한다.
// SPI·프로토콜·중복제거·HTTP 로직은 상위 폴더의 rf_common.h 를 공유하므로
// 단독 C 버전(rdk_rf_receiver.c)과 동작이 항상 일치한다.
//
// 조회:  ros2 node list · ros2 topic echo /iot/readings

#include "rf_common.h"          // static inline 함수 모음 — C++ 로 그대로 컴파일된다

#include <chrono>
#include <memory>
#include <stdexcept>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/string.hpp>

// 폴링 주기(POLL_US) 기준 횟수로 환산
static constexpr unsigned long kReinitEvery = 1000000UL / POLL_US;    // 1초마다 재초기화
static constexpr unsigned long kErrLogEvery = 300000000UL / POLL_US;  // 5분마다 경고 로그

class RfReceiver : public rclcpp::Node
{
public:
    RfReceiver() : rclcpp::Node("rf_receiver")
    {
        pub_read_ = create_publisher<std_msgs::msg::String>("iot/readings", 10);
        pub_err_  = create_publisher<std_msgs::msg::String>("iot/errors", 10);

        curl_global_init(CURL_GLOBAL_DEFAULT);
        spi_fd = spi_open(SPI_DEV);
        if (spi_fd < 0) throw std::runtime_error("spidev 열기 실패: " SPI_DEV);
        if (ce_init() < 0) throw std::runtime_error("CE 초기화 실패");

        nrf_init();
        RCLCPP_INFO(get_logger(), "receiver up: ch=%d 250kbps addr=Node1 payload=%d",
                    RF_CHANNEL, PAYLOAD_SIZE);
        dump_registers();

        timer_ = create_wall_timer(std::chrono::microseconds(POLL_US),
                                   std::bind(&RfReceiver::poll, this));
    }

    ~RfReceiver() override
    {
        ce_set(0);
#ifndef CE_TIE_HIGH
        gpiod_line_release(ce_line);
        gpiod_chip_close(ce_chip);
#endif
        if (spi_fd >= 0) close(spi_fd);
        curl_global_cleanup();
    }

private:
    void poll()
    {
        // SPI 가 0x00/0xFF 만 읽히면 NRF 가 응답하지 않는 것(배선/접촉 불량).
        // 매번 로그를 찍거나 매번 재초기화하면 커널 SPI 로그까지 폭증해 디스크를 채운다.
        if (!link_ok()) {
            if (linked_ || errs_ % kErrLogEvery == 0)
                RCLCPP_WARN(get_logger(),
                            "NRF 응답 없음 (SPI read 실패) — CSN/MISO/SCK/VCC/GND 접촉 확인. 재시도...");
            if (errs_ % kReinitEvery == 0) nrf_init();
            errs_++;
            linked_ = false;
            return;
        }
        if (!linked_) {
            RCLCPP_INFO(get_logger(), "link OK — listening for packets...");
            errs_ = 0;
            linked_ = true;
        }

        while (!(reg_read(REG_FIFO_STATUS) & 0x01)) {   // 쌓인 패킷 모두 비운다
            uint8_t buf[PAYLOAD_SIZE];
            read_payload(buf, PAYLOAD_SIZE);
            reg_write(REG_STATUS, 0x40);                // clear RX_DR

            RfMessage m;
            if (!rf_decode(buf, &m)) continue;          // 중복·빈 패킷

            RCLCPP_INFO(get_logger(), "%s", m.log);
            http_post(m.url, m.json);                   // 기존 API 업링크

            std_msgs::msg::String msg;                  // ROS 토픽 발행
            msg.data = m.json;
            (m.is_error ? pub_err_ : pub_read_)->publish(msg);
        }
    }

    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr pub_read_, pub_err_;
    rclcpp::TimerBase::SharedPtr timer_;
    unsigned long errs_ = 0;
    bool linked_ = false;
};

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IOLBF, 0);
    rclcpp::init(argc, argv);
    int rc = 0;
    try {
        rclcpp::spin(std::make_shared<RfReceiver>());
    } catch (const std::exception &e) {
        RCLCPP_FATAL(rclcpp::get_logger("rf_receiver"), "%s", e.what());
        rc = 1;
    }
    rclcpp::shutdown();
    return rc;
}
