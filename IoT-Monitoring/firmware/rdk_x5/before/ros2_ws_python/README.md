# ros2_iot_ws — 진짜 ROS 2 노드 버전 (rclpy)

기존 `ros2_ws/`(C 실행파일을 launch로 돌리기만 함)와 달리, 여기는 **진짜 ROS 2 노드**입니다.
`ros2 node list` / `ros2 topic echo` 로 조회되고, 나중에 **여러 노드와 연동**할 수 있습니다.

```
NRF 수신 → (1) API POST (기존)  +  (2) ROS 토픽 발행
  node   : /rf_receiver
  topics : /iot/readings , /iot/errors   (std_msgs/String, JSON)
```

## 구조 (ament_python 패키지)
```
ros2_iot_ws/
├── run.sh                         # 환경 source + ros2 launch
├── iot-rf-receiver.service        # 부팅 자동실행 (systemd)
└── src/iot_rf_receiver/
    ├── package.xml                # rclpy, std_msgs 의존
    ├── setup.py / setup.cfg       # 파이썬 패키지 설정 (entry point: receiver)
    ├── resource/iot_rf_receiver
    ├── iot_rf_receiver/receiver_node.py   ← 노드 본체 (SPI 수신 + POST + publish)
    └── launch/receiver.launch.py
```

## ⚠️ 먼저: 기존 C 수신 서비스 끄기
NRF 하나를 **두 프로세스가 동시에** 읽으면 충돌합니다. 이 rclpy 노드를 쓰려면 **기존 C 서비스 중지**:
```bash
sudo systemctl disable --now rf-receiver
```

## 빌드 & 실행
```bash
sudo apt install -y python3-spidev                 # 없으면
cd firmware/rdk_x5/ros2_iot_ws
source /opt/tros/humble/setup.bash                 # 없으면 /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
ros2 launch iot_rf_receiver receiver.launch.py     # 또는  ros2 run iot_rf_receiver receiver
```
> `receiver_node.py` 상단 `SPI_BUS, SPI_DEV = 1, 1` 은 **핀24=CS1(spidev1.1)** 기준. 배선 다르면 수정.

## ros2 로 조회 (이제 됨!)
```bash
ros2 node list                     # → /rf_receiver
ros2 node info /rf_receiver        # 발행 토픽 등 상세
ros2 topic list                    # → /iot/readings, /iot/errors
ros2 topic echo /iot/readings      # 수신 데이터 실시간 (JSON) ★
ros2 topic hz /iot/readings        # 수신 빈도
```

## 부팅 자동실행 (systemd)
```bash
chmod +x run.sh
./run.sh                            # 먼저 잘 뜨는지 확인 (Ctrl+C)
# iot-rf-receiver.service 의 ExecStart 경로·User 수정 후:
sudo cp iot-rf-receiver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now iot-rf-receiver
journalctl -u iot-rf-receiver -f
```

## 참고
- **코드 수정 후**: `colcon build` → `sudo systemctl restart iot-rf-receiver`.
- 다른 노드(예: 카메라/제어)를 추가하면 `src/` 에 패키지를 더 만들고 같은 워크스페이스에서 `colcon build`.
- 토픽 메시지는 지금 `std_msgs/String`(JSON)입니다. 정형 메시지가 필요하면 커스텀 `.msg` 타입도 만들 수 있어요.
