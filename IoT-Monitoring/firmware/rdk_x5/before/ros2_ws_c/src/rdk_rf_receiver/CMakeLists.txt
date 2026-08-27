cmake_minimum_required(VERSION 3.8)
project(rdk_rf_receiver C)

find_package(ament_cmake REQUIRED)
find_package(CURL REQUIRED)

# 상위 폴더의 단일 소스(firmware/rdk_x5/rdk_rf_receiver.c (before/ 로 이동하며 ../ 하나 추가됨))를 그대로 컴파일 — 사본 중복 방지.
# (이 워크스페이스를 firmware/rdk_x5/ros2_ws 안에서 in-place 로 빌드한다는 전제)
add_executable(rdk_rf_receiver ${CMAKE_CURRENT_SOURCE_DIR}/../../../../rdk_rf_receiver.c)

# CE를 3V3 직결(CE_TIE_HIGH, 기본)이면 curl만. GPIO로 CE 제어하면 gpiod 도 링크:
#   target_link_libraries(rdk_rf_receiver ${CURL_LIBRARIES} gpiod)
target_link_libraries(rdk_rf_receiver ${CURL_LIBRARIES})
target_include_directories(rdk_rf_receiver PRIVATE ${CURL_INCLUDE_DIRS})

install(TARGETS rdk_rf_receiver DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})

ament_package()
