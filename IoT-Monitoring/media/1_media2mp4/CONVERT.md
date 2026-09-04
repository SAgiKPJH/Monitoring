# Convert.py — .media → mp4 데이터셋 파이프라인

`.media` 원본을 mp4 로 만들고 → 변화량으로 정적 영상을 거르고 → 8초 컷(Cut) → (선택) 축소까지
**한 파일에서 단계별로** 실행합니다. 로직은 전부 `src/` 안에 있고 `Convert.py` 는 호출만 합니다.

## 실행

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media
.\.venv\Scripts\python.exe Convert.py            # Convert.py 상단 RUN 에서 켠 단계 순서대로
.\.venv\Scripts\python.exe Convert.py convert    # 특정 단계만 (convert / scan / filter / resize)
.\.venv\Scripts\python.exe Convert.py scan filter
```

## 설정 (Convert.py 상단만 고치면 됨)

| 항목 | 뜻 |
|---|---|
| `INPUT_DIR` | ① .media 원본 폴더 (하위 재귀 탐색) |
| `CONVERT_DIR` | ① 변환된 mp4 |
| `CUT_DIR` | ③ 정적 제거 + 8초 컷 결과 (학습용 원본) |
| `RESIZED_DIR` | ④ 해상도 축소본 |
| `CACHE_PATH` / `REPORT_TXT` | 변화량 스캔 캐시(증분) / 리포트 txt |
| `EXCLUDE_TXT` | 직접 지운 파일 목록 — filter/resize 가 다시 만들지 않음 |
| `RUN` | 단계별 ON/OFF (`convert/scan/filter/resize`) |
| `THRESH_MEAN`·`THRESH_MAX` | 정적 판정 (meanYDIF·maxYDIF 둘 다 미만이면 제거) |
| `SECONDS`·`WIDTH`·`CRF`·`NO_AUDIO`·`WORKERS` | 컷 길이·축소폭·화질·오디오·병렬 |

## 단계 (src/)

| # | 단계 | 파일 | 하는 일 |
|---|---|---|---|
| 1 | convert | `src/stage1_convert.py` | .media 파싱(H.264+PCM) → mp4, 내장 시각으로 이름, 증분 |
| 2 | scan | `src/stage2_scan.py` | 처음 8초 YDIF 변화량 → JSONL 캐시(증분) + 분포 리포트 |
| 3 | filter | `src/stage3_filter.py` | MOTION 만 비디오·오디오 8초 컷 무손실 → Cut (exclude 존중) |
| 4 | resize | `src/stage4_resize.py` | Cut → 가로 WIDTH 축소 재인코딩 (Cut 보존) |
| 공용 | | `src/media_format.py` · `ffmpeg_tools.py` · `cache_util.py` | .media 파서 · ffmpeg 탐색 · 캐시/분류/제외 |

- 모든 단계 **증분**: 이미 만든 결과는 건너뛰므로 중단 후 재실행 안전.
- ffmpeg 는 `media/ffmpeg/bin` 을 자동 인식(없으면 PATH). 원본은 삭제·수정하지 않음.
- Training_Standard 규격: 전 파일 150줄 이하, BGR 무변환 저장.

> 참고: 기존 `get_dataset/motion_filter.py auto` 와 동일한 파이프라인을, 편집·가독 중심으로
> 재구성한 것입니다. 검수용 격자(grid_mosaic)·복구(recover) 등 부가 도구는 `get_dataset/` 에 남아 있습니다.
