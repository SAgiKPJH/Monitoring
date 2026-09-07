#!/usr/bin/env python3
r"""
disk_map.py — 카드 전체를 샘플링해 "어디에 무엇이 남아 있는지" 빠르게 진단.

전체 스캔(45분) 없이, 카드를 N등분해 각 지점을 조금씩 읽어 내용물을 분류한다.
"옛 영상 데이터가 아직 카드에 있는가?" 를 몇 분 안에 판단할 수 있다.

분류:
  ZERO   전부 0x00        → 지워짐(포맷/트림). 복구 불가
  FF     전부 0xFF        → 미사용/erase 상태. 복구 불가
  MEDIA  카메라 파일 시작  → 복구 가능! (01000000 + ts + 34000000)
  H264   H.264 시작코드 다수 → 영상 데이터 (파일 중간일 가능성)
  LOWENT 낮은 엔트로피     → 텍스트/구조화 데이터
  DATA   높은 엔트로피     → 압축/암호화/영상 데이터일 수 있음

사용 (관리자 PowerShell):
  python disk_map.py E:
  python disk_map.py E: --samples 400
"""
import argparse
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sd_recover import Disk, open_fs, human, GB          # noqa: E402

SAMPLE = 64 * 1024


def entropy(b):
    if not b:
        return 0.0
    counts = [0] * 256
    for x in b:
        counts[x] += 1
    n = len(b)
    e = 0.0
    for c in counts:
        if c:
            p = c / n
            e -= p * math.log2(p)
    return e


MAGIC = re.compile(rb'\x01\x00\x00\x00.{16}\x34\x00\x00\x00', re.S)
CHUNK = re.compile(rb'\x34\x00\x00\x00')
SC = re.compile(rb'\x00\x00\x01')

# 관측된 타임스탬프 수집 (범위 밖 값도 확인하려고 넓게 잡음)
seen_ts = []


def scan_chunks(buf):
    """청크 헤더(ts + counter + 34 00 00 00) 개수. 파일 중간이어도 잡힌다."""
    n = 0
    for m in CHUNK.finditer(buf):
        s = m.start() - 12
        if s < 0:
            continue
        ts = struct.unpack_from('<Q', buf, s)[0]
        if 1_000_000_000_000 < ts < 3_000_000_000_000:      # 2001~2065, 넓게
            n += 1
            if len(seen_ts) < 40:
                seen_ts.append(ts)
    return n


def classify(buf):
    if not buf:
        return 'EMPTY', 0
    z = buf.count(0)
    if z == len(buf):
        return 'ZERO', 0
    if buf.count(0xFF) == len(buf):
        return 'FF', 0
    n_media = 0
    for m in MAGIC.finditer(buf):
        ts = struct.unpack_from('<Q', buf, m.start() + 8)[0]
        if 1_000_000_000_000 < ts < 3_000_000_000_000:
            n_media += 1
    n_chunk = scan_chunks(buf)
    if n_media:
        return 'MEDIA', n_media
    if n_chunk >= 3:                     # 파일 중간의 .media 데이터
        return 'MEDIA중간', n_chunk
    n_sc = len(SC.findall(buf))
    e = entropy(buf)
    if n_sc >= 5:
        return 'H264', n_sc
    if z > len(buf) * 0.9:
        return 'ZERO~', z * 100 // len(buf)
    if e < 4.0:
        return 'LOWENT', int(e * 10)
    return 'DATA', int(e * 10)


def parse_size(s):
    """'5G', '512M', '1024' 같은 문자열 → 바이트."""
    s = str(s).strip().upper()
    mul = 1
    if s.endswith('G'):
        mul, s = 1024 ** 3, s[:-1]
    elif s.endswith('M'):
        mul, s = 1024 ** 2, s[:-1]
    elif s.endswith('K'):
        mul, s = 1024, s[:-1]
    return int(float(s) * mul)


def main():
    ap = argparse.ArgumentParser(description="카드 내용물 샘플 진단")
    ap.add_argument("target", help="드라이브 문자(E:) 또는 이미지 파일")
    ap.add_argument("--samples", type=int, default=200, help="샘플 지점 수 (기본 200)")
    ap.add_argument("--dump-at", default=None,
                    help="이 위치(데이터영역 기준 오프셋, 예 5G/512M)의 원본을 저장 후 종료")
    ap.add_argument("--dump-size", default="1M", help="덤프 크기 (기본 1M)")
    ap.add_argument("--dump-out", default="dump.bin", help="덤프 저장 파일")
    args = ap.parse_args()

    disk = Disk(args.target)
    fs = open_fs(disk)
    base, size = fs.data_off, fs.data_size

    if args.dump_at is not None:
        off = base + parse_size(args.dump_at)
        n = parse_size(args.dump_size)
        buf = disk.read_at(off, n)
        with open(args.dump_out, 'wb') as f:
            f.write(buf)
        print("[덤프] 데이터영역+%s (절대 %d) 에서 %s 저장 -> %s"
              % (args.dump_at, off, human(len(buf)), args.dump_out))
        print("\n[앞 256바이트]")
        for o in range(0, min(256, len(buf)), 16):
            c = buf[o:o + 16]
            print("  %06X  %-47s  |%s|" % (o, ' '.join('%02X' % b for b in c),
                                           ''.join(chr(b) if 32 <= b < 127 else '.' for b in c)))
        print("\n[분류] %s" % (classify(buf[:SAMPLE]),))
        return
    step = max(SAMPLE, size // args.samples)

    print("[진단] %s · 데이터영역 %s · %d개 지점 샘플링 (각 %s)\n"
          % (fs.NAME, human(size), args.samples, human(SAMPLE)))

    stats = {}
    rows = []
    off = base
    i = 0
    while off < base + size and i < args.samples:
        buf = disk.read_at(off, SAMPLE)
        kind, extra = classify(buf)
        stats[kind] = stats.get(kind, 0) + 1
        rows.append((off - base, kind, extra))
        off += step
        i += 1
        if i % 20 == 0:
            sys.stdout.write("\r  %d/%d ..." % (i, args.samples))
            sys.stdout.flush()
    sys.stdout.write("\r" + " " * 30 + "\r")

    # 구간 맵 (연속 동일 분류는 묶어서 표시)
    print("[구간 맵]")
    start, cur = rows[0][0], rows[0][1]
    for pos, kind, extra in rows[1:] + [(size, None, 0)]:
        if kind != cur:
            print("  %8s ~ %8s   %s" % (human(start), human(pos), cur))
            start, cur = pos, kind

    print("\n[분류 요약]")
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print("   %-8s %4d개  (%.1f%%)" % (k, v, v * 100.0 / len(rows)))

    media = stats.get('MEDIA', 0)
    mid = stats.get('MEDIA중간', 0)
    h264 = stats.get('H264', 0)
    dead = stats.get('ZERO', 0) + stats.get('ZERO~', 0) + stats.get('FF', 0)

    if seen_ts:
        from datetime import datetime, timezone
        lo, hi = min(seen_ts), max(seen_ts)
        print("\n[발견된 내장 타임스탬프] %d개 샘플" % len(seen_ts))
        for lbl, v in (("최소", lo), ("최대", hi)):
            dt = datetime.fromtimestamp(v / 1000 - 9 * 3600, tz=timezone.utc)
            print("   %s: %d -> %s (카메라 표시시각 기준)" % (lbl, v, dt.strftime('%Y-%m-%d %H:%M:%S')))

    print("\n[판정]")
    if media:
        print("  ✅ 파일 시작점 %d개 지점 — 그대로 카빙 가능." % media)
    if mid:
        print("  ✅ .media 청크(파일 중간) %d개 지점 — 데이터는 살아있음!" % mid)
        print("     파일 '시작'만 못 찾는 상태 → --carve-unaligned 로 GOP 단위 추출 권장:")
        print("       python recover\\sd_recover.py E: --carve --carve-format media \\")
        print("           --carve-unaligned --out D:\\carved_u --carve-limit 300")
    if h264 and not (media or mid):
        print("  ⚠️ H.264 는 있으나 .media 청크 구조가 아님 (%d개 지점)." % h264)
        print("     다른 포맷이거나 헤더가 손상됨.")
    if not (media or mid or h264):
        print("  ❌ 영상 데이터의 흔적 없음.")
    print("  지워진(0x00/0xFF) 구간: %.1f%%" % (dead * 100.0 / len(rows)))


if __name__ == "__main__":
    main()
