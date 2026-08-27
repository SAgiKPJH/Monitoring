# ROS 2 입문 + 이 폴더 파일 설명 (RDK X5 수신기)

ROS 2가 처음이라도 이해되도록, **개념 → 파일별 역할 → 명령어 뜻 → 흐름** 순으로 정리했습니다.

> 📖 **ros2 명령어 전체 정리**는 옆 파일 → [ROS2-명령어.md](ROS2-명령어.md) (치트시트)

---

## 0. 그래서 ROS 2를 꼭 써야 하나요? (아니요, 선택입니다)

우리 수신기(`rdk_rf_receiver.c`)는 **그냥 gcc로 컴파일해서 바로 실행**할 수 있습니다
(상위 [README.md](../README.md) 4절). 부팅 자동실행도 그 실행파일을 systemd에 등록하면 끝이라
**ROS 2 없이도 됩니다.**

그럼 ROS 2로 감싸는 이유는?
- `ros2 launch` / `systemctl` 로 **표준화된 방식**으로 실행·자동시작·로그 관리
- 나중에 **다른 ROS 노드(카메라, 센서 등)와 연동**하기 쉬움
- RDK X5가 ROS 2(tros) 보드라 "ROS 방식으로도 돌리고 싶다"는 요청에 맞춤

> 단순히 데이터만 받아 API로 보내는 게 목적이면 **4절(gcc) + systemd가 더 단순**합니다.
> 아래는 "ROS 2로 하고 싶다"를 위한 설명입니다.

---

## 1. 5분 개념 (딱 이것만 알면 됨)

| 용어 | 쉽게 말하면 |
|---|---|
| **노드(node)** | 실행 중인 프로그램 하나. 우리 수신기 = 노드 1개 |
| **패키지(package)** | 노드 + 빌드설정을 묶은 단위. 우리 것 = `rdk_rf_receiver` |
| **워크스페이스(workspace)** | 패키지들을 모아 빌드하는 폴더 = `ros2_ws/`. `src/`에 패키지를 넣고 빌드 |
| **colcon** | ROS 2 **빌드 도구**. `colcon build` 하면 `src/`의 패키지를 컴파일해서 결과를 `install/`에 만듦 |
| **launch** | 노드를 "이렇게 실행해라"라고 적어둔 파일. `ros2 launch`로 실행 |
| **source setup.bash** | ROS 환경변수를 지금 터미널에 로드. **이걸 해야** `ros2`·`colcon` 명령을 쓸 수 있음 |

> **핵심**: `source` → `colcon build` → `source install/setup.bash` → `ros2 launch`. 이 4단계가 전부.

---

## 2. 이 폴더 파일들 — 하나씩 무슨 역할?

```
ros2_ws/
├── run.sh                       # ⑤ 환경 로드 + 실행을 한 번에 (systemd가 호출)
├── rf-receiver.service          # ⑥ 부팅 자동실행 등록 (리눅스 systemd)
└── src/rdk_rf_receiver/         # ← 패키지
    ├── package.xml              # ① 패키지 명세서
    ├── CMakeLists.txt           # ② 빌드 레시피
    └── launch/
        └── receiver.launch.py   # ③ 실행 설명서
# (빌드하면 자동 생성: build/, install/, log/  ← ④)
```

### ① `package.xml` — 패키지 "명세서"
이 폴더가 ROS 2 패키지임을 알리고 **이름·버전·의존성**을 적는 파일. ROS가 이걸 보고 패키지를 인식합니다.
- `<name>rdk_rf_receiver</name>` : 패키지 이름
- `<buildtool_depend>ament_cmake` : "CMake 방식으로 빌드한다"
- `<exec_depend>launch, launch_ros` : 실행 때 필요한 것(launch 기능)

### ② `CMakeLists.txt` — 빌드 "레시피"
C 소스를 **어떻게 컴파일할지** 적는 파일. gcc로 치면 `gcc rdk_rf_receiver.c -lcurl` 을 규칙으로 적은 것.
- `add_executable(rdk_rf_receiver ../../../rdk_rf_receiver.c)` : **상위 폴더의 C 파일**로 실행파일 만들기
  (사본을 안 만들려고 상위의 그 파일을 그대로 씀 → 그래서 **이 위치에서 빌드**해야 경로가 맞음)
- `target_link_libraries(... ${CURL_LIBRARIES})` : `curl` 라이브러리 연결 (HTTP 전송용)
- `install(TARGETS ...)` : 빌드된 실행파일을 `install/` 로 복사 (ros2가 찾을 수 있게)

### ③ `launch/receiver.launch.py` — 실행 "설명서"
`ros2 launch`가 읽는 파일. 내용은 딱 하나: **"rdk_rf_receiver 패키지의 rdk_rf_receiver 실행파일을
rf_receiver 라는 이름의 노드로 실행해라"**. (디버그 `-d`를 주고 싶으면 이 파일 `arguments`에 추가)

### ④ `build/`, `install/`, `log/` (빌드하면 생김 — 직접 안 만듦)
- `build/` : 빌드 중간 산출물
- `install/` : **완성된 실행파일**이 여기 들어감. `source install/setup.bash` 하면 `ros2`가 여길 보고 노드를 찾음
- `log/` : 빌드 로그

### ⑤ `run.sh` — "환경 로드 + 실행"을 한 번에
매번 손으로 `source ...; ros2 launch ...` 치기 번거로우니 묶은 셸 스크립트. 자기 위치를 자동으로 찾아
ROS 환경을 source 하고 `ros2 launch`를 실행합니다. **부팅 자동실행(systemd)이 이 스크립트를 호출**합니다.

### ⑥ `rf-receiver.service` — 부팅 자동실행 (systemd)
리눅스의 자동실행 관리자(systemd)에게 **"부팅하면 run.sh를 실행하고, 죽으면 다시 켜"** 라고 등록하는 파일.
- `ExecStart=` : 실행할 것 → `run.sh`의 **실제 경로**로 수정 필요
- `User=` : 어느 계정으로 실행할지 → 실제 계정명으로
- `Restart=always` : 크래시 시 재시작

---

## 3. 전체 흐름 한눈에

```
 rdk_rf_receiver.c  (C 소스, 우리가 계속 고쳐온 그 파일)
        │
        │  colcon build     ← CMakeLists.txt 레시피대로 컴파일
        ▼
 install/ 안에 실행파일 생성
        │
        │  ros2 launch      ← receiver.launch.py 대로 노드 실행
        ▼
 노드 rf_receiver 동작  →  NRF 수신  →  API로 POST
        ▲
        │  부팅 시 자동:  systemd(rf-receiver.service) → run.sh → 위 launch
```

---

## 4. 명령어 = 무슨 뜻?

```bash
source /opt/tros/humble/setup.bash        # ROS 켜기 (ros2·colcon 명령 사용 가능해짐) ★꼭 먼저
cd firmware/rdk_x5/ros2_ws                 # 워크스페이스로 이동
colcon build                              # src/의 패키지 빌드 → install/ 생성
source install/setup.bash                 # 방금 빌드한 내 패키지를 ros2에 등록
ros2 launch rdk_rf_receiver receiver.launch.py   # 실행 (launch 파일대로)
#  또는 launch 없이 직접:
ros2 run rdk_rf_receiver rdk_rf_receiver
```

- `colcon: command not found` → **`source setup.bash`를 안 한 것.** 먼저 source. 그래도 없으면 설치:
  `sudo apt install -y python3-colcon-common-extensions` 후 다시 source.
- `ros2 launch`가 패키지를 못 찾음 → **`source install/setup.bash`를 안 한 것.**

---

## 5. 초보가 자주 막히는 곳

| 증상 | 원인 | 해결 |
|---|---|---|
| `colcon: command not found` | ROS 환경 source 안 함 | `source /opt/tros/humble/setup.bash` (경로는 `ls /opt/tros/`로 확인) |
| `ros2: command not found` | 위와 동일 | 위와 동일 |
| colcon은 되는데 빌드 실패(소스 못 찾음) | ros2_ws 밖에서 빌드 | **`firmware/rdk_x5/ros2_ws` 안에서** `colcon build` |
| `ros2 launch` 시 "package not found" | 빌드 후 install source 안 함 | `source install/setup.bash` |
| 서비스가 안 뜸 | service의 경로/계정 안 맞음 | `ExecStart`·`User` 수정, `journalctl -u rf-receiver -f` 로 로그 확인 |

---

## 6. 요약 (딱 이 순서)
1. `source /opt/tros/humble/setup.bash`  ← ROS 켜기
2. `cd firmware/rdk_x5/ros2_ws && colcon build`  ← 빌드
3. `source install/setup.bash && ros2 launch rdk_rf_receiver receiver.launch.py`  ← 실행 확인
4. `rf-receiver.service` 경로·계정 수정 → `/etc/systemd/system/`에 복사 → `sudo systemctl enable --now rf-receiver`  ← 부팅 자동실행

> 부팅 자동실행만 목적이고 ROS가 부담되면, 상위 [README.md](../README.md) **4절(gcc 빌드)** 실행파일을
> 같은 방식(systemd)으로 등록하는 게 더 간단합니다. ROS 2는 "표준화·확장" 용도입니다.
