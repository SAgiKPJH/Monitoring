"""src — Convert.py 파이프라인의 단계별 기능 구현.

  stage1_convert : .media → mp4
  stage2_scan    : 변화량(YDIF) 스캔·리포트
  stage3_filter  : 정적 영상 제거 + 8초 컷 → Cut
  stage4_resize  : 해상도 축소

공용: media_format(.media 파서) · ffmpeg_tools · cache_util
"""
