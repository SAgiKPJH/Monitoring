# .venv 구성 & 실행 (media_to_mp4)

## 1. 가상환경 생성 (최초 1회)
```powershell
cd IoT-Monitoring\media
python -m venv .venv
```

## 2. 활성화
```powershell
# PowerShell
.\.venv\Scripts\Activate.ps1

# cmd
.\.venv\Scripts\activate.bat

# Git Bash / Linux
source .venv/Scripts/activate      # (리눅스는 .venv/bin/activate)
```

## 3. (선택) 패키지 설치 — 이 스크립트는 표준 라이브러리만 사용, 설치 불필요
```powershell
pip install -r requirements.txt
```

## 4. ffmpeg 설치 (변환에 필수, venv와 별개)
```powershell
# Windows
winget install Gyan.FFmpeg

# Ubuntu / RDK X5 / Mint
sudo apt install -y ffmpeg
```

## 5. 실행
```powershell
python get_dataset\media_to_mp4.py <소스폴더>
```

## 6. 비활성화
```powershell
deactivate
```

## (참고) 활성화 없이 바로 실행
```powershell
.\.venv\Scripts\python.exe media_to_mp4.py
```

## PowerShell 에서 Activate.ps1 실행이 막힐 때
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
