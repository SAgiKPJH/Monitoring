# label_tool — 2클래스 박스 라벨툴 (baby / baby_face)

박스를 `1`=baby(초록)·`2`=baby_face(자홍) 두 클래스로 찍는 라벨러. 두 가지 모드가 있습니다.

- **[A] 이미지 편집 모드**(`--images`): 기존 dataset 이미지를 열어 박스를 추가/수정.
  이미지는 그대로, `labels\` txt 만 갱신. auto_label 의 baby 박스에 **baby_face 만 얹는** 주 용도.
- **[B] 클립 모드**(`--clips`): mp4 클립을 넘겨보며 고른 프레임을 dataset 으로 **추출**(JPEG+라벨).
  `--clips` 는 **여러 폴더/파일**을 받습니다. carved-08 원본 클립에서 바로 라벨링할 때.

## 실행

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\8_detection_2class_train\label_tool

# [A] 이미지 편집 (기본 = 7_auto_labeling\dataset)
..\..\.venv\Scripts\python.exe main.py
..\..\.venv\Scripts\python.exe main.py --images <이미지폴더> --labels <저장폴더>

# [B] 클립에서 추출
..\..\.venv\Scripts\python.exe main.py --clips D:\carved-08\Cut                 # 단일
..\..\.venv\Scripts\python.exe main.py --clips D:\carved-08\Cut D:\carved\Cut   # 복수
..\..\.venv\Scripts\python.exe main.py --clips D:\carved-08\Cut --out <저장dataset>
```

## 키

| 키 | 동작 |
|---|---|
| `1` / `2` | 활성 클래스 = **baby**(초록) / **baby_face**(자홍) |
| 마우스 드래그 | 박스 추가 (활성 클래스) · `u` 마지막 취소 · `c` 전체 비우기 |
| `SPACE`/`ENTER` | 저장 · `x` 네거티브(대상 없음, `c` 로 비운 뒤) · `q`/`ESC` 종료 |
| `n` / `p` / `r` | (A) 이미지 이동 / (B) 클립 이동 · `r` 랜덤 |
| `a`/`d` · `w`/`s` · 트랙바 | (B 전용) ±1프레임 · ±1초 · 프레임 탐색 |

- 저장 파일명: (A) 이미지 stem 그대로, (B) `<클립>_f####`. 같은 프레임을 다시 열면 라벨 자동 로드.

## 흐름 (baby_face 채우기)

1. auto_label 이 만든 이미지에는 **baby 박스가 이미** 있습니다 — 열면 자동으로 불러와 표시.
2. `2` 로 baby_face 전환 → 아기 **얼굴** 영역을 드래그.
3. baby 박스가 어긋났으면 `1` 로 전환해 수정(취소 후 다시).
4. `SPACE` 저장 → 같은 이미지의 라벨에 두 클래스가 함께 기록됩니다.
5. 얼굴이 안 보이는 이미지(뒤통수·이불 속)는 baby 만 두고 넘어가면 됩니다.

## 파일 (Training_Standard: 파일당 ≤200줄, BGR 무변환)

| 파일 | 역할 |
|---|---|
| `main.py` | CLI 진입점 · 모드 분기 (`--images` / `--labels` / `--clips` / `--out`) |
| `labeler_ui.py` | [A] 이미지 네비게이션 메인루프 (LabelTool) |
| `clip_ui.py` | [B] 클립 탐색 + 프레임 추출 메인루프 (ClipLabelTool) |
| `labeler_view.py` | 오버레이(클래스별 색) + 마우스 드래그 (공용) |
| `labeler_io.py` | 이미지/클립 목록 · 영상 열기 · YOLO 라벨(클래스 id) 읽기/쓰기 · 추출 저장 |
