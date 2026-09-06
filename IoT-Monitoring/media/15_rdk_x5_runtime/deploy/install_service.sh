#!/bin/bash
# ─────────────────────────────────────────────────────────────
# systemd 서비스 설치 (보드에서, 15_rdk_x5_runtime 폴더 안에서 실행)
#   bash deploy/install_service.sh          # 단독 실행 서비스(baby-monitor)  ← 권장
#   bash deploy/install_service.sh ros2     # ROS2 노드 서비스(baby-monitor-ros2), ros2_ws 빌드 후
# 유닛 파일의 /home/sunrise/JJU/Monitoring · User=sunrise 를 실제 경로/사용자로 치환해 설치하고 enable --now.
# 제거:  sudo systemctl disable --now baby-monitor && sudo rm /etc/systemd/system/baby-monitor.service
# ─────────────────────────────────────────────────────────────
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-$USER}"
NAME="baby-monitor"; [ "$1" = "ros2" ] && NAME="baby-monitor-ros2"
SRC="$DIR/deploy/$NAME.service"
[ -f "$SRC" ] || { echo "[에러] $SRC 없음"; exit 1; }
[ -f "$DIR/monitoring.py" ] || { echo "[에러] $DIR/monitoring.py 없음 — 15_rdk_x5_runtime 안에서 실행하세요"; exit 1; }
[ -f "$DIR/.env" ] || echo "[경고] $DIR/.env 없음 — cp .env_sample .env 후 BACKEND=bpu 등 설정 권장"

sed -e "s#/home/sunrise/JJU/Monitoring#$DIR#g" -e "s#^User=.*#User=$USER_NAME#" "$SRC" \
  | sudo tee "/etc/systemd/system/$NAME.service" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now "$NAME"
echo "── 설치 완료: $NAME (경로 $DIR, 사용자 $USER_NAME) ──"
sudo systemctl status "$NAME" --no-pager | head -12 || true
echo "로그:  journalctl -u $NAME -f"
