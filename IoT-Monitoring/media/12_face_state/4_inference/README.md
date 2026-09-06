# 4_inference — 얼굴 상태 추론 (live · sample)

3단계 **멀티라벨 모델**(`output_ml_<net>\best.pth` + `meta.json`)로 얼굴 상태
(눈뜸·입벌림·입가림·인상)를 추론한다. 크롭 1장 → sigmoid N개 → 임계 0.5.

## Face_State_Live_Test.py — 실시간

go2rtc 스트림 → **baby_face 감지(8 모델)** → 얼굴 크롭 → 상태 오버레이 창.
```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\12_face_state\4_inference
..\..\.venv\Scripts\python.exe Face_State_Live_Test.py     # s 스크린샷 · q 종료
```
설정(상단): `STREAM_URL` · `DET_MODEL`(8) · `FACE_MODEL_DIR`(3의 output_ml_*) · `DET_CONF` · `SCALE`.

## Face_State_Sample_Test.py — mp4 클립에서 샘플

**mp4 클립**(라벨링 때와 동일 소스)을 그때그때 읽어 프레임을 뜨고 → baby·baby_face 감지(8) →
baby_face 크롭 → 상태 추론 → **창에 하나씩 표시**(+ `out_sample\` 저장). (라이브 스트림은 Live_Test)
```powershell
..\..\.venv\Scripts\python.exe Face_State_Sample_Test.py --n-clips 30
..\..\.venv\Scripts\python.exe Face_State_Sample_Test.py --src D:\carved\Cut
```
창 키(라벨툴처럼): `a`/`d` ±1프레임 · `w`/`s` ±1초 · **트랙바**(프레임) · `n`/`p` 클립 · `r` 랜덤 · `space` 저장 · `q` 종료.
각 프레임에 baby·baby_face 박스 + baby_face 상태(속성 확률)를 오버레이. 프레임 바뀔 때만 감지(가벼움).
설정: `--src`(클립 폴더) · `--n-clips` · `--conf`(감지) · `--margin`(얼굴 여유) · `--thr`(속성 임계) ·
`DET_MODEL`(8) · `FACE_MODEL_DIR`(3의 output_ml_*). 클립당 첫·중간·끝 3프레임 추출.

## 구성

| 파일 | 역할 |
|---|---|
| `face_state.py` | 모델 로드(meta.json)·전처리(BGR·0.5)·`predict`·`overlay` (공용) |
| `Face_State_Live_Test.py` | 스트림 실시간(감지+상태). 4_detection_pretrained\src 재사용 |
| `Face_State_Sample_Test.py` | 크롭 N개 상태 추론 → out_sample |

- 전제: 3단계 `run_training_multilabel.py` 로 `best.pth`+`meta.json` 생성.
- resnet18 모델을 쓰려면 `FACE_MODEL_DIR` 을 `output_ml_resnet18` 로 변경.
- meta.json 이 network·input_size·attrs 를 담아, 백본/속성 구성을 자동으로 맞춘다.
