cmake_minimum_required(VERSION 3.8)
project(rdk_rf_receiver CXX)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(CURL REQUIRED)

add_executable(rf_receiver_node src/rf_receiver_node.cpp)

# 공용 로직 rf_common.h 는 firmware/rdk_x5/ 에 있다 (단독 C 버전과 공유).
#   src/rdk_rf_receiver → ../../..  =  firmware/rdk_x5
target_include_directories(rf_receiver_node PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/../../..)

ament_target_dependencies(rf_receiver_node rclcpp std_msgs)

# CE 를 GPIO 로 제어할 때(rf_common.h 의 CE_TIE_HIGH 해제)는 gpiod 를 추가한다:
#   target_link_libraries(rf_receiver_node ${CURL_LIBRARIES} gpiod)
target_link_libraries(rf_receiver_node ${CURL_LIBRARIES})

install(TARGETS rf_receiver_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})

ament_package()
