# baby pose label tool — YOLO-pose 키포인트 라벨링 툴

홈캠 아기 침대 영상(`*.mp4`)을 훑어보며 프레임을 고르고, **COCO 17 키포인트를
안내 순서대로 클릭**해 ultralytics YOLO-pose 파인튜닝용 이미지(원본 해상도
JPEG) + 라벨(txt)을 저장하는 툴입니다. 프레임당 아기 1명을 가정합니다.

- 단일 클래스: `baby` (class id **0**), `kpt_shape: [17, 3]`
- 의존성: `opencv-python`, `numpy` 만 사용 (cv2.imshow 기반 GUI)
- Training_Standard 규격 준수 (py 파일당 200줄 이하, BGR 무변환 저장)
- 조작 체계는 옆 폴더의 `label_tool`(바운딩박스 툴)과 동일한 골격입니다.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `main.py` | 진입점 (CLI 인자 파싱, 실행) |
| `pose_ui.py` | 상태 초기화, 키 매핑, 메인 이벤트 루프 |
| `pose_nav.py` | 영상 열기/탐색, 트랙바, 뷰 갱신 (PoseTool 믹스인) |
| `pose_edit.py` | 키포인트 배치/스킵/되돌리기/저장 로직 (PoseTool 믹스인) |
| `pose_view.py` | 화면 축소·확대(뷰 변환), 오버레이 렌더링, 마우스 입력 |
| `pose_io.py` | 영상 목록/열기, JPEG·라벨 읽기/쓰기 |
| `pose_format.py` | COCO 17 상수 + 라벨 라인 생성/파싱 (순수 함수, cv2 무의존) |

## 설치 및 실행

```powershell
# 의존성 설치 (media venv에는 이미 opencv 설치됨)
D:\Code\Monitoring\IoT-Monitoring\media\.venv\Scripts\python.exe -m pip install opencv-python numpy

# 실행 (기본값: --src D:\carved\Cut  --out D:\carved\yolo_baby_pose)
D:\Code\Monitoring\IoT-Monitoring\media\.venv\Scripts\python.exe main.py

# 경로 지정 실행 (src는 mp4 폴더 또는 단일 mp4 파일)
python main.py --src D:\carved\Cut --out D:\carved\yolo_baby_pose
```

## 키 조작

| 키 | 동작 |
|---|---|
| `n` / `p` | 다음 / 이전 영상 |
| `r` | 랜덤 영상 점프 |
| 트랙바 | 프레임 위치 이동 |
| `a` / `d` | 1프레임 뒤로 / 앞으로 |
| `s` / `w` | 1초 뒤로 / 앞으로 |
| **좌클릭** | 현재 관절 배치 (visible, v=2) → 다음 관절로 |
| **`v` / 우클릭** | 현재 관절 "안 보임" 처리 (v=0, 좌표 0,0) → 다음 관절로 |
| `b` | 한 관절 뒤로 (마지막 입력 취소 후 다시 찍기) |
| `c` | 현재 프레임 키포인트 전체 초기화 |
| `z` | **마지막 클릭 지점 중심 2배 확대 토글** (확대 중에도 클릭 정상 동작) |
| `SPACE` / `ENTER` | **저장** — 17개 미완료 시 남은 관절은 전부 v=0 처리 후 저장 |
| `x` | 네거티브 저장 (아기 없음 — 이미지 + 빈 .txt) |
| `q` / `ESC` | 종료 (창 닫기 버튼도 동일) |

화면 상단에 `NEXT 4/17: left_ear` 처럼 **다음에 찍을 관절 번호·이름**이 해당 관절
색으로 표시됩니다 (nose 초록, left_* 주황, right_* 하늘색). 찍힌 관절은 점 +
번호(1~17)로 표시되고, 보이는 관절끼리 COCO 스켈레톤 연결선이 실시간으로
그려집니다. 이불에 가린 아기는 관절 몇 개만 찍고 바로 `SPACE`로 저장하는 흐름이
기본 사용 패턴입니다.

## COCO 17 키포인트 순서

| # | 이름 | # | 이름 | # | 이름 |
|---|---|---|---|---|---|
| 1 | nose | 7 | right_shoulder | 13 | right_hip |
| 2 | left_eye | 8 | left_elbow | 14 | left_knee |
| 3 | right_eye | 9 | right_elbow | 15 | right_knee |
| 4 | left_ear | 10 | left_wrist | 16 | left_ankle |
| 5 | right_ear | 11 | right_wrist | 17 | right_ankle |
| 6 | left_shoulder | 12 | left_hip | | |

(표의 #은 화면 표시와 같은 1-기준 번호입니다. 라벨 파일 안에서는 이 순서대로
17개가 나열될 뿐 번호 자체는 저장되지 않습니다.)

left/right는 **아기 본인 기준**입니다. 아기가 화면에서 거꾸로(머리가 아래)
누워 있어도 아기의 왼쪽 어깨는 left_shoulder로 찍어야 합니다. 학습 시
`flip_idx`가 좌우반전 증강을 올바르게 처리하려면 이 기준이 일관돼야 합니다.

## 저장 형식

```
<out>\
  images\<클립이름>_f0037.jpg   # 원본 해상도(1920x1080) JPEG 품질 95, BGR 무변환
  labels\<클립이름>_f0037.txt   # YOLO-pose 1줄, 네거티브는 빈 파일
```

라벨 한 줄 = `0 cx cy w h x1 y1 v1 ... x17 y17 v17` (값 56개, 전부 0~1 정규화,
v는 0 또는 2):

```
0 0.512033 0.487500 0.221833 0.305833 0.500000 0.350000 2 0.000000 0.000000 0 ...
```

- **바운딩박스는 자동 계산**: visible(v=2) 관절들의 extent에 상하좌우 각각
  extent의 15% 마진을 더한 뒤 이미지 경계로 클램프합니다 (별도 박스 드로잉
  없음). extent가 퇴화한 경우(관절 1개 등)에만 최소 2px 폭/높이를 보장합니다.
- visible 관절이 0개면 저장을 거부합니다 (`x` 네거티브를 쓰세요).
- 이미 저장된 프레임으로 이동하면 `[SAVED: POSE/NEGATIVE]` 표시가 뜨고 기존
  키포인트가 로드되어 **수정 후 재저장(덮어쓰기)** 할 수 있습니다.
  (저장된 POSE를 네거티브로 바꾸려면 `c`로 지운 뒤 `x`)
- 상단 저장 카운트(pose/neg/total)는 out 폴더 전체 기준입니다 (시작 시 labels
  폴더 스캔 — 재실행해도 이어서 집계).

## ultralytics 학습 연결

YOLO-pose 파인튜닝 시 `data.yaml`에 **`kpt_shape`와 `flip_idx`가 반드시**
들어가야 합니다. `flip_idx`는 좌우반전 증강 시 left/right 관절을 맞바꾸는
인덱스 표로, 이것이 빠지거나 틀리면 반전 증강이 라벨을 망가뜨립니다.

```yaml
# data.yaml 예시
path: D:/carved/yolo_baby_pose
train: images        # 필요 시 train/val 폴더로 분할
val: images
kpt_shape: [17, 3]   # 17개 관절 x (x, y, visibility)
flip_idx: [0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15]
names:
  0: baby
```

```python
from ultralytics import YOLO
model = YOLO("yolo11n-pose.pt")          # 성인 COCO 사전학습에서 파인튜닝
model.train(data="data.yaml", epochs=100, imgsz=960)
```

## 사용 팁 (권장 워크플로)

1. `r`로 랜덤 영상 → 아기가 잘 보이는 프레임을 트랙바/`a·d`로 고른다.
2. 안내 순서대로 좌클릭, 안 보이는 관절은 `v`(또는 우클릭)로 넘긴다.
   얼굴 관절처럼 촘촘한 곳은 근처를 한 번 클릭해 두고 `z` 확대 후 `b`로
   되돌아가 정밀하게 다시 찍으면 편하다.
3. 이불로 가려 몇 개만 보이면 그만큼만 찍고 `SPACE` (나머지 자동 v=0).
4. 빈 침대·부모만 있는 프레임은 `x` 네거티브 저장.
5. 야간 IR/주간 컬러, 정방향/거꾸로 자세가 골고루 섞이도록 뽑는다.

## 한계 / 참고

- 오버레이 텍스트는 영어입니다 (cv2.putText가 한글을 그리지 못함).
- 프레임당 아기 1명(라벨 1줄)만 지원합니다. 두 명 이상이면 한 명만 찍거나
  그 프레임을 건너뛰세요.
- v=1(보이지만 가려짐) 구분은 없습니다 — v=2(찍음) / v=0(안 찍음)만 사용.
  손으로 고친 v=1 라벨을 다시 열면 v=2로 로드·재저장됩니다.
- 확대(`z`)는 마지막 클릭 지점 중심 2배 크롭이며 창 크기는 유지됩니다.
  클릭 좌표는 뷰 변환 튜플로 역변환되므로 확대 중에도 정확합니다.
- 깨진 mp4는 자동 스킵(`[skip]` 콘솔 표시), 저장 경로는 유니코드 안전
  (imencode+tofile). 화면은 1600x900 이내 축소 표시, 저장은 항상 원본 해상도.
- `x`(네거티브)는 키포인트가 하나라도 입력돼 있으면 실수 방지를 위해
  거부합니다 (`c`로 지운 뒤 저장).
