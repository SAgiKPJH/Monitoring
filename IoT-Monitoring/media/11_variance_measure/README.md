# 11_variance_measure — 변화량(YDIF) 측정 · threshold 찾기

스트림/클립의 **프레임 변화량(YDIF)** 을 측정해, 정적(STATIC)과 움직임(MOTION)을 가르는
**적당한 threshold** 를 찾기 위한 도구. YDIF = 연속 프레임의 루마(밝기) 절대차 평균(0~255,
folder 1 의 ffmpeg signalstats YDIF 와 같은 개념).

```
11_variance_measure/
├── live.py        # go2rtc 실시간: 현재 YDIF·롤링 평균/최대·판정·스파크라인 창 + CSV 기록
├── sample_view.py  # 샘플 클립을 창에서 **하나씩 재생**하며 실시간 YDIF·집계·판정 확인
├── sample.py       # 샘플 클립들의 YDIF 분포(퍼센타일·히스토그램) → 임계 후보
├── variance.py     # 공용 YDIF 계산·통계 (스트림 수신은 4_detection_pretrained\src 재사용)
└── out/          # ydif_live.csv · ydif_sample.csv · 스크린샷
```

## live — 실시간으로 눈으로 찾기

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\11_variance_measure
..\.venv\Scripts\python.exe live.py
```
- 오버레이: `YDIF now / mean / max` + `[STATIC|MOTION]`(현재 임계 기준) + 스파크라인(빨강=mean 임계선).
- 아기가 **가만히 있을 때 vs 움직일 때** YDIF 를 보고 그 사이 값을 임계로 잡으면 된다.
- 키: `[` `]` mean 임계 -/+, `,` `.` max 임계 -/+ (실시간으로 판정이 바뀌는 지점 확인), `s` 스크린샷, `q` 종료.
- 매 프레임 값이 `out\ydif_live.csv` 에 기록됨(엑셀 등으로 분포 분석).

## sample_view — 클립 하나씩 창에서 확인

```powershell
..\.venv\Scripts\python.exe sample_view.py --n 100
```
- 샘플 클립을 **창에 하나씩 재생**하며 현재 YDIF·이 클립의 mean/max·판정을 실시간 표시.
- 전체 YDIF 곡선(스파크라인) 위에 재생 위치 마커. 클립은 자동 루프 재생.
- 키: `n`/`p` 다음/이전 클립 · `space` 일시정지 · `[` `]` mean 임계 · `,` `.` max 임계 · `q` 종료.

## sample — 클립 분포로 통계적으로 찾기

```powershell
..\.venv\Scripts\python.exe sample.py --n 300     # 랜덤 300클립 (기본 carved-08\Cut)
..\.venv\Scripts\python.exe sample.py --n 0       # 전체
```
- 각 클립 앞 8초의 `meanYDIF·maxYDIF` 를 구해 **퍼센타일 + 히스토그램** 출력, `out\ydif_sample.csv` 저장.
- "하위 X% 를 STATIC 으로 보고 싶다"를 정하면 그 **퍼센타일이 임계 후보**. (예: 하위 50% → p50)

## 무시영역 (IGNORE_RECT)

카메라 **타임스탬프 숫자**(좌상단)가 매초 바뀌어 변화량을 부풀리므로, `IGNORE_RECT`(비율
`x1,y1,x2,y2`, 0~1)로 그 영역을 **계산에서 제외**한다. live.py·sample.py·sample_view.py 상단에서
지정(기본 `(0.0,0.0,0.30,0.10)`=좌상단, `None`=없음). 창에는 **초록 사각형**으로 표시.

## 판정 규칙 (folder 1 과 동일)

`STATIC = meanYDIF < TH_MEAN AND maxYDIF < TH_MAX` — 둘 다 작아야 정적.
- 여기서 찾은 값을 `1_media2mp4\Convert.py` 의 `THRESH_MEAN`·`THRESH_MAX` 로 쓰면 스캔/prune 이 같은 기준으로 동작.
- 주의: 이 도구의 YDIF 는 cv2 기반(축소 폭 `WIDTH`)이라 ffmpeg YDIF 와 **스케일이 약간 다를 수 있음** —
  값 자체보다 **정적/움직임 구간의 상대 차이**로 임계를 잡는 걸 권장.

## 옵션 (상단 설정 / CLI)

| | live.py | sample.py |
|---|---|---|
| 대상 | `STREAM_URL`(go2rtc) | `--src`(클립 폴더) · `--n`(클립 수) |
| resize | `RESIZE_W`·`RESIZE_H`(320·auto) | `--width`·`--height`(320·auto) |
| 구간 | `WINDOW`(프레임 수) | `--seconds`(8) |
| 임계 표시 | `TH_MEAN`·`TH_MAX`(키로 조정) | 퍼센타일로 제안 |
