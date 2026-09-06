# 14_export_BPU/Dockerfile — D-Robotics OE(OpenExplorer) X5 툴체인 이미지 위에 얇게 얹은 변환용 이미지
#
# 플랫폼: linux/amd64 (x86_64). x64 Windows(Docker Desktop/WSL2)·x64 리눅스에서 네이티브로 돈다.
# 툴체인(hb_mapper 등)은 공식 이미지에 이미 들어있어 여기서는 태그 고정 + 작업폴더 + 기본 명령만 정한다.
# 빌드/실행은 run_docker.ps1(Windows) · run_docker.sh(Linux) · docker compose 중 하나로.
#
# OE_TAG 는 보유한 OE 패키지 버전과 맞춘다 (docker pull 가능한 태그: README 참고).
ARG OE_TAG=v1.2.8
FROM --platform=linux/amd64 openexplorer/ai_toolchain_ubuntu_20_x5_cpu:${OE_TAG}

# media 전체를 /work 로 마운트해 쓰므로(convert.sh 가 ../15_rdk_x5_runtime/models 에 .bin 복사) 여기만 지정
WORKDIR /work/14_export_BPU

# 기본: 변환 일괄 실행. 대화형 점검은 `... bash` 로 덮어쓴다.
CMD ["bash", "convert.sh"]
