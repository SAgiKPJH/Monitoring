"""ffmpeg / ffprobe 실행 파일 탐색 (media/ffmpeg/bin → PATH)."""
import os
import shutil
from pathlib import Path

_SRC = Path(__file__).resolve().parent          # media/src
_MEDIA = _SRC.parent                             # media


def find_ffmpeg(name: str = "ffmpeg") -> str:
    """번들(media/ffmpeg/bin) 우선, 없으면 PATH. 최후엔 이름 그대로 반환."""
    exe = f"{name}.exe" if os.name == "nt" else name
    for base in (_MEDIA, _MEDIA.parent):
        p = base / "ffmpeg" / "bin" / exe
        if p.is_file():
            return str(p)
    return shutil.which(name) or exe
