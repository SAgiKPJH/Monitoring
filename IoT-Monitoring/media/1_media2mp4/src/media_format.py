#!/usr/bin/env python3
r"""
media_format.py — 카메라 .media 포맷 파서 (공용 모듈)

리버스 엔지니어링으로 확정한 구조 — 파일은 **청크의 연속**이다:

  청크 헤더 24 bytes
    +0   type      uint32 LE   1 = 비디오 키프레임(SPS/PPS/IDR), 0 = 비디오 P프레임, 3 = 오디오
    +4   length    uint32 LE   payload 바이트 수
    +8   timestamp uint64 LE   Unix epoch milliseconds
    +16  counter   uint32 LE   증가 카운터
    +20  flags     uint32 LE   기기/펌웨어에 따라 0x34 또는 0x00 (값 고정 아님)
  payload  length bytes
    · 비디오: H.264 Annex-B (00 00 00 01 …)
    · 오디오: PCM 8000 Hz, mono, s16le

검증: 샘플 0000.media(539,628 B)를 length 필드로 따라가면 청크 420개
      (키프레임 2 · P프레임 118 · 오디오 300) 후 **정확히 파일 끝**에서 종료.
(get_dataset/media_format.py 와 동일 — Convert.py 자립용 사본)
"""
import struct
from datetime import datetime, timezone

HDR = 24
H264_SC = b'\x00\x00\x00\x01'

TYPE_KEYFRAME = 1
TYPE_PFRAME = 0
TYPE_AUDIO = 3

AUDIO_RATE = 8000
AUDIO_CHANNELS = 1
AUDIO_WIDTH = 2                      # s16le

TS_MIN = 1_500_000_000_000           # 2017-07 이후
TS_MAX = 2_500_000_000_000           # 2049 이전
MAX_CHUNK = 4 * 1024 * 1024


class Chunk:
    __slots__ = ('offset', 'type', 'length', 'ts', 'counter', 'flags', 'ps', 'pe', 'is_video')

    def __init__(self, offset, typ, length, ts, counter, flags, ps, pe, is_video):
        self.offset, self.type, self.length = offset, typ, length
        self.ts, self.counter, self.flags = ts, counter, flags
        self.ps, self.pe, self.is_video = ps, pe, is_video


def read_header(data, pos):
    """(type, length, ts, counter, flags) 또는 None(유효하지 않음)."""
    if pos + HDR > len(data):
        return None
    typ, length = struct.unpack_from('<II', data, pos)
    ts = struct.unpack_from('<Q', data, pos + 8)[0]
    counter, flags = struct.unpack_from('<II', data, pos + 16)
    if not (TS_MIN < ts < TS_MAX) or not (0 < length <= MAX_CHUNK):
        return None
    if typ not in (TYPE_PFRAME, TYPE_KEYFRAME, TYPE_AUDIO):
        return None
    return typ, length, ts, counter, flags


def walk(data, start=0, limit_bytes=None):
    """start 부터 length 필드를 따라가며 청크를 수집. (chunks, end_pos)."""
    chunks = []
    pos = start
    end = len(data) if limit_bytes is None else min(len(data), start + limit_bytes)
    while pos + HDR <= end:
        h = read_header(data, pos)
        if h is None:
            break
        typ, length, ts, counter, flags = h
        ps = pos + HDR
        pe = ps + length
        if pe > end:
            break
        chunks.append(Chunk(pos, typ, length, ts, counter, flags, ps, pe,
                            data[ps:ps + 4] == H264_SC))
        pos = pe
    return chunks, pos


def parse(data):
    """파일 전체를 청크 리스트로. (walk 의 얇은 래퍼)"""
    return walk(data, 0)[0]


def is_file_start(data, pos=0):
    """이 위치가 파일 시작인가: 키프레임 청크 + payload 가 H.264 SPS."""
    h = read_header(data, pos)
    if h is None or h[0] != TYPE_KEYFRAME:
        return False
    ps = pos + HDR
    if data[ps:ps + 4] != H264_SC or ps + 4 >= len(data):
        return False
    return (data[ps + 4] & 0x1F) == 7            # NAL 7 = SPS


def demux(data):
    """(video_h264, audio_pcm, info)."""
    chunks, _ = walk(data, 0)
    vid = bytearray()
    aud = bytearray()
    vts = []
    for c in chunks:
        if c.is_video:
            vid += data[c.ps:c.pe]
            vts.append(c.ts)
        elif c.type == TYPE_AUDIO:
            aud += data[c.ps:c.pe]
    info = {
        'chunks': len(chunks),
        'video_frames': len(vts),
        'audio_bytes': len(aud),
        'first_ts': vts[0] if vts else (chunks[0].ts if chunks else None),
        'last_ts': vts[-1] if vts else (chunks[-1].ts if chunks else None),
    }
    span = ((info['last_ts'] - info['first_ts']) / 1000.0) if len(vts) > 1 else 0
    info['duration_sec'] = span
    info['fps'] = (len(vts) - 1) / span if span > 0 else 0
    info['audio_sec'] = len(aud) / (AUDIO_RATE * AUDIO_CHANNELS * AUDIO_WIDTH)
    return bytes(vid), bytes(aud), info


def ts_to_datetime(ts_ms, offset_hours=0):
    """Unix ms → naive datetime (UTC + offset_hours)."""
    return datetime.fromtimestamp(ts_ms / 1000.0 + offset_hours * 3600,
                                  tz=timezone.utc).replace(tzinfo=None)


def looks_like_media(data):
    return is_file_start(data, 0)
