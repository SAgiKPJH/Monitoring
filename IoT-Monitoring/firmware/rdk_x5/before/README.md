# before/ — 이전 구현 보관

현행은 상위 `ros2_ws/` (C++ · rclcpp) 입니다. 여기 있는 둘은 참고용으로만 남겨둡니다.

| 폴더 | 언어 | 성격 | 한계 |
|---|---|---|---|
| `ros2_ws_c/` | C | `ros2 launch` 가 **C 실행파일을 프로세스로 띄우기만** 함 | ROS 라이브러리를 안 써서 `ros2 node list` 에 안 뜸 |
| `ros2_iot_ws_python/` | Python (rclpy) | 진짜 ROS 노드. 토픽 발행까지 동작 | C 로직과 이원화되어 수정이 두 곳에 필요 |

## 왜 C++ 로 옮겼나
- `ros2_ws_c` 는 ROS 그래프에 등록되지 않아 `ros2 node list` · `ros2 topic echo` 가 불가능했다.
- `ros2_iot_ws_python` 은 노드로는 동작하지만, 검증된 C 로직과 별도 구현이라 **같은 수정을 두 번** 해야 했다.
- 현행 C++ 버전은 `rf_common.h` 를 단독 C 버전과 **공유**하므로 로직이 갈라지지 않는다.

## 주의
- `ros2_ws_c/` 의 CMake 는 `../../../../rdk_rf_receiver.c` 를 참조한다 (before/ 로 옮기며 `../` 하나 추가됨).
  단독 C 파일은 이제 `rf_common.h` 를 include 하는 얇은 main() 이라, 이 패키지도 그대로 빌드된다.
- NRF 는 하나뿐이므로 **여러 수신기를 동시에 실행하지 말 것** (SPI 충돌).
