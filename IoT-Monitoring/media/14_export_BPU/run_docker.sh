#!/bin/bash
# 14_export_BPU/run_docker.sh — x86_64 리눅스(Mint 등) 또는 Windows Git Bash 에서 OE docker 빌드 + 변환
#   변환 일괄:  bash run_docker.sh
#   대화형 셸:  bash run_docker.sh shell
#   OE 버전:    OE_TAG=v1.2.8 bash run_docker.sh
# 이미지는 linux/amd64 — x64 에서 네이티브 실행. media 전체를 /work 로 마운트한다.
set -e
TAG="${OE_TAG:-v1.2.8}"
HERE="$(cd "$(dirname "$0")" && pwd)"
MEDIA="$(cd "$HERE/.." && pwd)"

# Git Bash(MSYS) 는 /work 같은 경로를 C:\...\work 로 바꿔버리므로 변환을 끄고, 마운트 소스는 Windows 경로로
case "$(uname -s)" in
  MINGW*|MSYS*) export MSYS_NO_PATHCONV=1; MEDIA_MOUNT="$(cygpath -w "$MEDIA")" ;;
  *)            MEDIA_MOUNT="$MEDIA" ;;
esac

echo "== build baby-bpu-convert:$TAG (linux/amd64, base openexplorer OE $TAG) =="
docker build --platform linux/amd64 --build-arg OE_TAG="$TAG" -t "baby-bpu-convert:$TAG" "$HERE"

if [ "$1" = "shell" ]; then CMD=(bash); else CMD=(bash convert.sh); fi
echo "== run: ${CMD[*]}  (mount $MEDIA_MOUNT -> /work) =="
docker run --rm -it --platform linux/amd64 -v "$MEDIA_MOUNT:/work" -w /work/14_export_BPU "baby-bpu-convert:$TAG" "${CMD[@]}"
