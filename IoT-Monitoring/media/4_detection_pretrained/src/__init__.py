"""src — 실시간 스트림 추론(감지+포즈) 구현.

  stream_source : go2rtc 실시간 fMP4 + 스냅샷 폴백
  inference     : 감지(baby)·포즈 모델 로드·추론·오버레이
  live_view     : 실시간 창
  shot          : 단발 캡처 → 추론 → 저장
"""
