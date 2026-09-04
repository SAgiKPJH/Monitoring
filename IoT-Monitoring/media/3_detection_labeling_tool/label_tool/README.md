# baby label tool — YOLO 바운딩박스 라벨링 툴

홈캠 아기 침대 영상(`*.mp4`)을 빠르게 훑어보며 **원하는 프레임만 골라** 아기 영역에
박스를 그리고, YOLO 학습용 이미지(원본 해상도 JPEG) + 라벨(txt)을 저장하는 툴입니다.

- 단일 클래스: `baby` (class id **0**)
- 의존성: `opencv-python`, `numpy` 만 사용 (cv2.imshow 기반 GUI)
- Training_Standard 규격 준수 (py 파일당 200줄 이하, BGR 무변환 저장, temp 미사용)

## 파일 구성

| 파일 | 역할 |
|---|---|
| `main.py` | 진입점 (CLI 인자 파싱, 실행) |
| `labeler_ui.py` | 창/키보드/트랙바 상태 관리 및 메인 루프 |
| `labeler_view.py` | 화면 오버레이 렌더링 + 마우스 드래그 박스 입력 |
| `labeler_io.py` | 영상 목록/열기, JPEG·YOLO 라벨 읽기/쓰기 |

## 설치 및 실행

```powershell
# 의존성 설치 (media venv 기준 — 현재 venv에는 opencv가 없음)
D:\Code\Monitoring\IoT-Monitoring\media\.venv\Scripts\python.exe -m pip install opencv-python numpy

# 실행 (기본값: --src D:\carved\Cut  --out D:\carved\yolo_baby)
D:\Code\Monitoring\IoT-Monitoring\media\.venv\Scripts\python.exe main.py

# 경로 지정 실행 (src는 mp4 폴더 또는 단일 mp4 파일)
python main.py --src D:\carved\Cut --out D:\carved\yolo_baby
```

## 키 조작

| 키 | 동작 |
|---|---|
| `n` / `p` | 다음 / 이전 영상 |
| `r` | **랜덤 영상 점프** (수천 개 영상을 빠르게 훑을 때) |
| 트랙바 | 프레임 위치 이동 (마우스로 드래그) |
| `a` / `d` | 1프레임 뒤로 / 앞으로 |
| `s` / `w` | 1초 뒤로 / 앞으로 |
| 마우스 드래그 | 박스 그리기 (여러 개 가능, 그리는 중 노란색 → 확정 초록색) |
| `u` | 마지막 박스 취소 |
| `c` | 박스 전체 취소 |
| `SPACE` / `ENTER` | **현재 프레임 저장** (이미지 + YOLO 라벨) |
| `x` | **네거티브 저장** (아기 없음 — 이미지 + 빈 .txt) |
| `q` / `ESC` | 종료 (창 닫기 버튼도 동일) |

## 저장 형식

```
<out>\
  images\<클립이름>_f0037.jpg   # 원본 해상도(1920x1080) JPEG, 품질 95
  labels\<클립이름>_f0037.txt   # YOLO: "0 cx cy w h" (0~1 정규화), 네거티브는 빈 파일
```

- 이미 저장된 프레임으로 이동하면 `[SAVED: POSITIVE/NEGATIVE]` 표시가 뜨고,
  기존 박스가 다시 로드되어 **수정 후 재저장(덮어쓰기)** 할 수 있습니다.
- 화면 상단에 세션 누적이 아닌 **out 폴더 전체 기준** 저장 수(pos/neg/total)가 표시됩니다.
  (툴 시작 시 labels 폴더를 스캔하므로 재실행해도 이어서 집계)

## 사용 팁 (권장 워크플로)

1. `r`로 랜덤 영상을 띄운다 → 아기가 잘 보이는 프레임을 트랙바/`a·d`로 고른다.
2. 아기 몸 전체(이불에 덮였으면 보이는 실루엣 포함)를 드래그 → `SPACE` 저장.
3. 빈 침대·부모만 있는 프레임 등은 `x`로 네거티브 저장 (배경 오탐 감소에 중요).
4. 다시 `r` → 반복. 야간 IR/주간 컬러가 골고루 섞이도록 다양한 영상에서 뽑는 것이 좋다.

## 한계 / 참고

- 오버레이 텍스트는 영어입니다 (cv2.putText가 한글을 그리지 못함).
- 깨진(디코딩 불가) mp4는 자동으로 건너뛰고 콘솔에 `[skip]`으로 표시됩니다.
- 저장 경로는 유니코드 안전(imencode+tofile)이지만, **영상 파일명이 한글인 경우**
  일부 OpenCV/FFmpeg 빌드에서 열리지 않을 수 있습니다 (그 경우 자동 스킵됨).
- 화면은 1600x900 이내로 축소 표시되지만 저장은 항상 원본 해상도입니다.
- 프레임 저장명은 `_f{프레임번호:04d}` — 8초·15fps(≈120프레임) 클립 기준 충분합니다.
- `x`(네거티브)는 박스가 그려져 있으면 실수 방지를 위해 거부합니다 (`c`로 지운 뒤 저장).
