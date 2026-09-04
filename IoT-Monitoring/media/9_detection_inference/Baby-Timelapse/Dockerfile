# timelapse — 아기 타임랩스 캡처 (CPU 전용, 아기 감지 시 원본 저장)
FROM python:3.11-slim

# cv2(VideoCapture fMP4) + ultralytics + scp(원격 전송)에 필요한 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# torch 는 CPU 휠로 (CUDA 미포함 → 이미지 작게)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 + 모델 번들
COPY detector.py stream_source.py capture.py ./
COPY models ./models

ENV OUT_DIR=captures \
    SUCCESS_INTERVAL_SEC=3600 \
    RETRY_INTERVAL_SEC=600 \
    CONF=0.8 \
    SCP_KEY=/keys/id_rsa \
    KEEP_LOCAL=0 \
    STREAM_URL=http://172.30.1.42:1984/stream.html?src=camera1

# OUT_DIR 은 WORKDIR(/app) 기준 상대경로 → /app/captures. 전송 후 삭제(KEEP_LOCAL=0).
CMD ["python", "capture.py"]
