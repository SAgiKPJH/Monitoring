# ROS 2 명령어 치트시트 (실전 위주)

`ros2 <동사> <대상> ...` 구조입니다. **모르면 `--help`**: 아무 명령 뒤에 `-h`/`--help`.
탭키 자동완성도 됩니다(`ros2 to<Tab>` → `topic`).

> ⚠️ 모든 `ros2`/`colcon` 명령은 **먼저 환경을 source** 해야 동작:
> `source /opt/tros/humble/setup.bash` (+ 내 워크스페이스면 `source install/setup.bash`)

---

## 0. 개념 한 줄
- **노드(node)**: 실행 중인 프로그램. **토픽(topic)**: 노드끼리 주고받는 방송 채널(발행/구독).
- **서비스(service)**: 요청→응답(1:1). **액션(action)**: 오래 걸리는 작업(진행률 있는 요청).
- **파라미터(param)**: 노드의 설정값. **인터페이스(interface)**: 메시지/서비스/액션의 데이터 형식.

---

## 1. 실행
```bash
ros2 run <패키지> <실행파일>              # 노드 하나 실행   예: ros2 run rdk_rf_receiver rdk_rf_receiver
ros2 launch <패키지> <런치파일>           # 런치파일로 실행  예: ros2 launch rdk_rf_receiver receiver.launch.py
ros2 launch <패키지> <런치> arg:=값       # 런치에 인자 전달
```

## 2. 노드 (node)
```bash
ros2 node list                          # 실행 중인 노드 목록   예: /rf_receiver
ros2 node info /rf_receiver             # 그 노드의 토픽/서비스/파라미터 등 상세
```

## 3. 토픽 (topic) — 가장 많이 씀
```bash
ros2 topic list                         # 토픽 목록
ros2 topic list -t                      # 타입까지 표시
ros2 topic echo /토픽                    # 그 토픽에 흐르는 메시지 실시간 출력  ★
ros2 topic info /토픽                    # 타입·발행자/구독자 수
ros2 topic hz /토픽                      # 초당 메시지 수(빈도)
ros2 topic bw /토픽                      # 대역폭(데이터량)
ros2 topic pub /토픽 <타입> '{데이터}'    # 직접 메시지 발행(테스트용)
#   예: ros2 topic pub /chatter std_msgs/msg/String '{data: hello}'
ros2 topic pub --once /토픽 <타입> '{..}' # 한 번만 발행
```
> 참고: 우리 `rf_receiver`는 데이터를 **HTTP로만** 보내서 토픽엔 안 올립니다.
> 토픽으로도 보려면 rclc 퍼블리셔 추가(요청 시 확장).

## 4. 서비스 (service)
```bash
ros2 service list                       # 서비스 목록
ros2 service type /서비스               # 서비스 타입
ros2 service call /서비스 <타입> '{..}'  # 서비스 호출(요청→응답)
ros2 service find <타입>                # 특정 타입의 서비스 찾기
```

## 5. 파라미터 (param)
```bash
ros2 param list                         # 노드들의 파라미터 목록
ros2 param get /노드 <파라미터>          # 값 읽기
ros2 param set /노드 <파라미터> <값>     # 값 바꾸기
ros2 param dump /노드                    # 노드 파라미터 전체를 yaml로 출력
ros2 param load /노드 params.yaml        # yaml에서 로드
```

## 6. 액션 (action)
```bash
ros2 action list                        # 액션 목록
ros2 action info /액션                   # 상세
ros2 action send_goal /액션 <타입> '{..}'  # 목표 전송(진행률 보려면 --feedback)
```

## 7. 인터페이스 (메시지/서비스/액션 형식)
```bash
ros2 interface list                     # 모든 msg/srv/action 타입 목록
ros2 interface show std_msgs/msg/String # 그 타입의 필드 구조 보기   ★
ros2 interface proto std_msgs/msg/String # 예시(프로토타입) 출력 → pub 할 때 복붙
```

## 8. 패키지 (pkg)
```bash
ros2 pkg list                           # 설치된 패키지 목록
ros2 pkg executables <패키지>            # 그 패키지의 실행파일들
ros2 pkg prefix <패키지>                 # 그 패키지 설치 경로
ros2 pkg create <이름> --build-type ament_cmake   # 새 패키지 뼈대 생성
```

## 9. 기록 & 재생 (rosbag2)
```bash
ros2 bag record /토픽1 /토픽2            # 토픽을 파일로 기록
ros2 bag record -a                      # 모든 토픽 기록
ros2 bag info <bag폴더>                  # 기록 내용 요약
ros2 bag play <bag폴더>                  # 기록을 그대로 재생(테스트/디버깅)
```

## 10. 진단 & 기타
```bash
ros2 doctor                             # 환경 점검(문제 진단)
ros2 doctor --report                    # 상세 리포트
ros2 wtf                                # doctor 별칭
ros2 daemon status                      # ros2 데몬 상태 (list가 이상하면 restart)
ros2 daemon stop && ros2 daemon start   # 데몬 재시작
ros2 topic list 이 이상할 때 daemon 재시작이 자주 해결
```

---

## 11. 빌드/환경 (ros2 아니지만 필수)
```bash
source /opt/tros/humble/setup.bash      # ★ROS 켜기 (모든 ros2/colcon 앞에 필요)
cd firmware/rdk_x5/ros2_ws
colcon build                            # 워크스페이스 빌드(src → install)
colcon build --packages-select <패키지>  # 특정 패키지만 빌드
colcon build --symlink-install          # 파이썬/런치 수정 시 재빌드 없이 반영(심링크)
source install/setup.bash               # ★빌드 결과를 ros2에 등록
rosdep install --from-paths src -y      # src 패키지들의 의존성 자동 설치
```

---

## 12. 우리 프로젝트에 바로 써보기
```bash
source /opt/tros/humble/setup.bash
cd firmware/rdk_x5/ros2_ws && source install/setup.bash

ros2 node list                          # → /rf_receiver 보이면 실행 중
ros2 node info /rf_receiver             # 노드 상세
ros2 pkg executables rdk_rf_receiver    # → rdk_rf_receiver
ros2 launch rdk_rf_receiver receiver.launch.py    # 실행
```

---

## 13. 팁
- **`--help`가 최고**: `ros2 topic --help`, `ros2 topic echo --help` …
- **탭 완성**: 명령·토픽·타입 다 자동완성됨.
- **자주 쓰는 3개만 외우면 됨**: `ros2 node list`, `ros2 topic echo`, `ros2 launch`.
- `ros2 topic list`가 비거나 이상 → `ros2 daemon stop && ros2 daemon start`.
- 공식 튜토리얼: <https://docs.ros.org/en/humble/Tutorials.html> (Humble = tros 기반 버전).
