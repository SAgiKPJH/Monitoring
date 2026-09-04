# 6_detection_trained_inference — 학습된 baby 모델 추론

`5_detection_train` 에서 학습한 **baby 모델**을 실시간 스트림/샘플 이미지에 추론합니다.
`4_detection_pretrained` 와 동일한 실행이며, **차이는 모델뿐**(사전학습 person → 파인튜닝 baby).

## 복붙 없음 — src 재사용

이 폴더에는 **엔트리 파일 2개만** 있습니다. 구현(`stream_source`·`inference`·`live_view`·
`shot`·`app`)은 `..\4_detection_pretrained\src` 를 sys.path 로 그대로 씁니다(심볼릭 링크 X,
git·권한 문제 없음). 즉 로직 수정은 3 한 곳에서만 하면 5 에도 반영됩니다.

## 실행

```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media\6_detection_trained_inference

# 실시간 스트림 (학습된 baby 모델)
..\.venv\Scripts\python.exe Detection_Live_Test.py          # 창
..\.venv\Scripts\python.exe Detection_Live_Test.py shot 30  # 창 없이 → out\

# 학습 이미지 5개 랜덤 추론 (학습 결과 확인)
..\.venv\Scripts\python.exe Detection_Sample_Test.py        # → out_sample\
```

- 창 키: `d`/`p` 감지·포즈 토글, `s` 스크린샷, `q` 종료
- 각 파일 상단 `DET_MODEL` 만 바꾸면 다른 학습 산출물로 교체 (state_dict `.pth` / `.pt` / `.onnx` 자동 인식)

## 3 과의 차이

| | 4_detection_pretrained | 6_detection_trained_inference |
|---|---|---|
| 감지 모델 | `yolo11m.pt` (COCO person) | `...\yolo_baby_output\best\model.pth` (파인튜닝 baby) |
| DET_CLASSES | `[0]` person | `None` (baby 단일) |
| src | 자체 보유 | 3 것을 재사용 |
