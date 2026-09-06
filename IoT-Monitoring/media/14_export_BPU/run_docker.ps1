# 14_export_BPU\run_docker.ps1 — x64 Windows(Docker Desktop, WSL2 백엔드)에서 OE docker 빌드 + 변환
#   변환 일괄:  .\run_docker.ps1
#   대화형 셸:  .\run_docker.ps1 -Shell
#   OE 버전:    .\run_docker.ps1 -Tag v1.2.8
# 전제: Docker Desktop 실행 중(리눅스 컨테이너 모드). 이미지는 linux/amd64 로 네이티브 실행.
param(
    [string]$Tag = "v1.2.8",
    [switch]$Shell
)
$ErrorActionPreference = "Stop"
$here  = $PSScriptRoot
$media = (Resolve-Path (Join-Path $here "..")).Path      # media 전체를 /work 로 마운트

Write-Host "== build baby-bpu-convert:$Tag (linux/amd64, base openexplorer OE $Tag) =="
docker build --platform linux/amd64 --build-arg OE_TAG=$Tag -t "baby-bpu-convert:$Tag" $here
if ($LASTEXITCODE -ne 0) { exit 1 }

$cmd = if ($Shell) { @("bash") } else { @("bash", "convert.sh") }
Write-Host "== run: $($cmd -join ' ')  (mount $media -> /work) =="
docker run --rm -it --platform linux/amd64 -v "${media}:/work" -w /work/14_export_BPU "baby-bpu-convert:$Tag" @cmd
