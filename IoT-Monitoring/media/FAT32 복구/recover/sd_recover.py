#!/usr/bin/env python3
r"""
sd_recover.py — SD카드 삭제 파일 복구 (FAT32 / exFAT, 표준 라이브러리만)

두 가지 방식:
  1) 엔트리 복구 (기본)  : 디렉터리 엔트리를 찾아 이름·시각·크기·위치 복원 → 추출
  2) 카빙 (--carve)      : 디렉터리가 날아갔을 때, 파일 시그니처로 raw 추출

스캔은 카드 전체를 읽어 오래 걸리므로 **결과를 캐시**합니다(scan_cache.json).
한 번 스캔한 뒤에는 --from-scan 으로 **즉시** 다시 필터링·추출할 수 있습니다.

⚠️ 대상 카드에 아무것도 쓰지 말 것 / 출력은 다른 드라이브 / 관리자 PowerShell 에서 실행

사용:
  # 1) 전체 스캔(느림) → 캐시 저장, 목록 확인
  python sd_recover.py E: --list-only
  # 2) 캐시로 즉시 필터 (재스캔 없음)
  python sd_recover.py --from-scan scan_cache.json --contains media --list-only
  # 3) 추출
  python sd_recover.py --from-scan scan_cache.json --contains media --out D:\recovered
  # 4) 디렉터리가 없을 때: 카빙
  python sd_recover.py E: --carve --carve-like sample.media --out D:\carved
"""
import argparse
import binascii
import json
import os
import re
import struct
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import media_format as mf                                    # noqa: E402

SECTOR = 512
GB = 1024 ** 3
BLOCK = 8 * 1024 * 1024
ENTRY = 32
DEFAULT_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_cache.json")
# 유효한 파일 속성 조합 (디렉터리·볼륨라벨·0x00 제외). 빠른 1차 필터.
VALID_ATTRS = frozenset((0x01, 0x02, 0x04, 0x20, 0x21, 0x22, 0x24, 0x26, 0x27))
# 8.3 이름에 허용되는 바이트: 대문자·숫자·일부 기호·공백 (소문자는 8.3에서 불가)
SFN_CHARS = frozenset(
    b'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' + b"!#$%&'()-@^_`{}~ " + bytes([0x7D, 0x7E])
)
# NTRes(offset 12): 보통 0, 소문자 플래그 0x08/0x10/0x18
VALID_NTRES = frozenset((0x00, 0x08, 0x10, 0x18))


class Disk:
    def __init__(self, target):
        if os.path.isfile(target):
            self.path = target
        else:
            m = re.fullmatch(r'([A-Za-z]):?[\\/]?', target)
            if not m:
                sys.exit("[오류] 대상은 드라이브 문자(E:) 또는 이미지 파일이어야 합니다: %s" % target)
            self.path = r'\\.\%s:' % m.group(1).upper()
        try:
            self.f = open(self.path, 'rb', buffering=0)
        except PermissionError:
            sys.exit("[오류] 접근 거부 — 관리자 권한 PowerShell 에서 실행하세요.")
        except FileNotFoundError:
            sys.exit("[오류] 대상을 찾을 수 없습니다: %s" % target)

    def read_at(self, off, size):
        a = off - (off % SECTOR)
        n = ((off + size + SECTOR - 1) // SECTOR) * SECTOR - a
        self.f.seek(a)
        buf = self.f.read(n)
        return buf[off - a: off - a + size]


def dos_datetime(dosdate, dostime):
    try:
        return datetime((dosdate >> 9) + 1980, (dosdate >> 5) & 0xF, dosdate & 0x1F,
                        (dostime >> 11) & 0x1F, (dostime >> 5) & 0x3F, (dostime & 0x1F) * 2)
    except ValueError:
        return None


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip() or "noname"


def valid_name(name):
    return bool(name) and len(name) <= 255 and all(31 < ord(c) for c in name)


def human(n):
    n = float(n)
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or u == 'GB':
            return "%.1f %s" % (n, u)
        n /= 1024.0


class Found:
    __slots__ = ('name', 'size', 'cluster', 'mtime', 'deleted')

    def __init__(self, name, size, cluster, mtime, deleted=True):
        self.name, self.size, self.cluster = name, size, cluster
        self.mtime, self.deleted = mtime, deleted

    def to_dict(self):
        return {'name': self.name, 'size': self.size, 'cluster': self.cluster,
                'mtime': self.mtime.isoformat() if self.mtime else None,
                'deleted': self.deleted}

    @staticmethod
    def from_dict(d):
        return Found(d['name'], d['size'], d['cluster'],
                     datetime.fromisoformat(d['mtime']) if d['mtime'] else None,
                     d.get('deleted', True))


class Progress:
    def __init__(self, total, label="스캔"):
        self.total, self.t0, self.last = max(1, total), time.time(), 0.0
        self.label = label

    def update(self, done, hits):
        now = time.time()
        if now - self.last < 1.0 and done < self.total:
            return
        self.last = now
        el = now - self.t0
        spd = done / el if el > 0 else 0
        eta = (self.total - done) / spd if spd > 0 else 0
        sys.stdout.write("\r  %s %5.1f%%  (%s / %s, %.0f MB/s, 남은 ~%d분%02d초)  발견 %d개    "
                         % (self.label, done * 100.0 / self.total, human(done), human(self.total),
                            spd / 1024 / 1024, eta // 60, eta % 60, hits))
        sys.stdout.flush()

    def done(self):
        sys.stdout.write("\n")


# ---------------- FAT32 ----------------
class Fat32:
    NAME = "FAT32"
    LFN_ATTR = 0x0F

    def __init__(self, disk, boot):
        self.d = disk
        self.bps = struct.unpack_from('<H', boot, 11)[0]
        self.spc = boot[13]
        reserved = struct.unpack_from('<H', boot, 14)[0]
        nfats = boot[16]
        fatsz = struct.unpack_from('<I', boot, 36)[0]
        total = struct.unpack_from('<I', boot, 32)[0] or struct.unpack_from('<H', boot, 19)[0]
        if not (self.bps and self.spc and fatsz and total):
            sys.exit("[오류] FAT32 부트섹터 값이 비정상입니다.")
        self.cluster_bytes = self.bps * self.spc
        first_data = reserved + nfats * fatsz
        self.data_off = first_data * self.bps
        self.max_cluster = (total - first_data) // self.spc + 1
        self.data_size = (self.max_cluster - 1) * self.cluster_bytes
        print("[%s] 클러스터 %s · 데이터영역 %s" %
              (self.NAME, human(self.cluster_bytes), human(self.data_size)))

    def cl_off(self, n):
        return self.data_off + (n - 2) * self.cluster_bytes

    @staticmethod
    def _lfn_part(e):
        s = (e[1:11] + e[14:26] + e[28:32]).decode('utf-16le', 'ignore')
        for stop in ('\x00', '\uffff'):
            i = s.find(stop)
            if i >= 0:
                s = s[:i]
        return s

    def scan(self):
        """삭제·정상 엔트리를 모두 수집(캐시용). 필터는 나중에 적용."""
        found, prog = [], Progress(self.data_size)
        off, end = self.data_off, self.data_off + self.data_size
        while off < end:
            n = min(BLOCK, end - off)
            blk = self.d.read_at(off, n)
            if not blk:
                break
            self._scan_block(blk, found)
            off += n
            prog.update(off - self.data_off, len(found))
        prog.done()
        return found

    def _scan_block(self, blk, found):
        max_cluster, append = self.max_cluster, found.append
        cbytes, vol_size = self.cluster_bytes, self.data_size
        for i in range(0, len(blk) - ENTRY + 1, ENTRY):
            attr = blk[i + 11]
            if attr not in VALID_ATTRS:              # 1차: 속성 바이트
                continue
            if blk[i + 12] not in VALID_NTRES:       # 2차: NTRes 예약 바이트
                continue
            b0 = blk[i]
            deleted = (b0 == 0xE5)
            # 3차(핵심): 8.3 이름 11바이트가 모두 유효한 문자여야 함.
            # 랜덤 데이터가 이걸 통과할 확률은 사실상 0 → 오탐 제거.
            short = blk[i:i + 11]
            if not all(c in SFN_CHARS for c in (short[1:] if deleted else short)):
                continue
            if not deleted and b0 not in SFN_CHARS:
                continue
            e = blk[i:i + ENTRY]
            size = struct.unpack_from('<I', e, 28)[0]
            cluster = (struct.unpack_from('<H', e, 20)[0] << 16) | struct.unpack_from('<H', e, 26)[0]
            if not (2 <= cluster <= max_cluster) or not (0 < size <= vol_size):
                continue
            # 4차: 파일이 볼륨 밖으로 넘어가면 허위
            if cluster + (size + cbytes - 1) // cbytes - 1 > max_cluster:
                continue
            mtime = dos_datetime(struct.unpack_from('<H', e, 24)[0],
                                 struct.unpack_from('<H', e, 22)[0])
            parts, j = [], i - ENTRY                  # 앞의 LFN 체인에서 긴 이름 복원
            while j >= 0 and len(parts) < 20:
                if blk[j + 11] == self.LFN_ATTR:
                    parts.append(self._lfn_part(blk[j:j + ENTRY]))
                    j -= ENTRY
                else:
                    break
            if parts:
                name = ''.join(parts)
            else:                                     # 8.3 (삭제 시 첫 글자 소실 → '_')
                base = e[1:8].decode('ascii', 'ignore').rstrip()
                ext = e[8:11].decode('ascii', 'ignore').rstrip()
                name = ('_' if deleted else chr(b0)) + base + ('.' + ext if ext else '')
            if valid_name(name):
                append(Found(name, size, cluster, mtime, deleted))

    def extract(self, item, fh):
        off, left = self.cl_off(item.cluster), item.size
        while left > 0:
            n = min(4 * 1024 * 1024, left)
            data = self.d.read_at(off, n)
            if not data:
                break
            fh.write(data)
            off += len(data)
            left -= len(data)
        return item.size - left


# ---------------- exFAT ----------------
class Exfat:
    NAME = "exFAT"

    def __init__(self, disk, boot):
        self.d = disk
        self.bps = 1 << boot[108]
        self.spc = 1 << boot[109]
        heap = struct.unpack_from('<I', boot, 88)[0]
        self.count = struct.unpack_from('<I', boot, 92)[0]
        if not (self.bps and self.spc and self.count):
            sys.exit("[오류] exFAT 부트섹터 값이 비정상입니다.")
        self.cluster_bytes = self.bps * self.spc
        self.data_off = heap * self.bps
        self.max_cluster = self.count + 1
        self.data_size = self.count * self.cluster_bytes
        print("[%s] 클러스터 %s · 데이터영역 %s" %
              (self.NAME, human(self.cluster_bytes), human(self.data_size)))

    def cl_off(self, n):
        return self.data_off + (n - 2) * self.cluster_bytes

    @staticmethod
    def _ts(v):
        try:
            return datetime(1980 + (v >> 25), (v >> 21) & 0xF, (v >> 16) & 0x1F,
                            (v >> 11) & 0x1F, (v >> 5) & 0x3F, (v & 0x1F) * 2)
        except ValueError:
            return None

    def scan(self):
        found, prog = [], Progress(self.data_size)
        off, end = self.data_off, self.data_off + self.data_size
        while off < end:
            n = min(BLOCK, end - off)
            blk = self.d.read_at(off, n)
            if not blk:
                break
            self._scan_block(blk, found)
            off += n
            prog.update(off - self.data_off, len(found))
        prog.done()
        return found

    def _scan_block(self, blk, found):
        limit = len(blk) - ENTRY * 2
        for i in range(0, limit + 1, ENTRY):
            t = blk[i]
            if t not in (0x05, 0x85):
                continue
            deleted = (t == 0x05)
            s = blk[i + ENTRY:i + ENTRY * 2]
            if s[0] not in (0x40, 0xC0):
                continue
            name_len = s[3]
            cluster = struct.unpack_from('<I', s, 20)[0]
            size = struct.unpack_from('<Q', s, 24)[0]
            if not (2 <= cluster <= self.max_cluster) or not (0 < size < 512 * GB) \
                    or not (0 < name_len <= 255):
                continue
            chars, j = [], i + ENTRY * 2
            while j + ENTRY <= len(blk) and blk[j] in (0x41, 0xC1) and len(''.join(chars)) < name_len:
                chars.append(blk[j + 2:j + ENTRY].decode('utf-16le', 'ignore'))
                j += ENTRY
            name = ''.join(chars)[:name_len]
            if valid_name(name):
                found.append(Found(name, size, cluster,
                                   self._ts(struct.unpack_from('<I', blk, i + 12)[0]), deleted))

    extract = Fat32.extract


# ---------------- 카빙 (디렉터리가 없을 때) ----------------
def pattern_to_regex(pat_hex):
    r"""'01000000????????01BA' → 정규식. '??' 는 임의의 1바이트 와일드카드."""
    s = re.sub(r'\s+', '', pat_hex)
    if len(s) % 2:
        sys.exit("[오류] 카빙 패턴의 hex 길이가 홀수입니다: %s" % pat_hex)
    out, i, plen = b'', 0, 0
    while i < len(s):
        pair = s[i:i + 2]
        if pair == '??':
            out += b'.'
        else:
            try:
                out += re.escape(bytes([int(pair, 16)]))
            except ValueError:
                sys.exit("[오류] 카빙 패턴에 잘못된 hex: %r" % pair)
        i += 2
        plen += 1
    return re.compile(out, re.DOTALL), plen


def carve_media(disk, fs, out, max_size, limit, aligned=True, tz_offset=-9.0,
                scan_bytes=0, strict=False):
    r"""카메라 .media 전용 카빙 (구조 검증 + 클러스터 정렬).

    파일 시작 조건:
      01 00 00 00 | duration(4) | ts(8, Unix ms) | counter(4) | 34 00 00 00 | 00 00 00 01 | SPS
    파일 중간의 GOP 세그먼트도 같은 구조라, **클러스터 경계에서 시작하는 것만**
    진짜 파일로 인정한다(FAT 파일은 항상 클러스터 정렬).
    """
    os.makedirs(out, exist_ok=True)
    cb = fs.cluster_bytes
    base = fs.data_off
    end = fs.data_off + fs.data_size
    if scan_bytes:
        end = min(end, base + scan_bytes)
    prog = Progress(end - base, "카빙")
    starts = []
    off = base
    # 1단계: 파일 시작 후보 수집.
    # 파일은 '키프레임 청크(type=1) + H.264 SPS' 로 시작하고, FAT 파일이므로 클러스터 정렬됨.
    while off < end:
        n = min(BLOCK, end - off)
        blk = disk.read_at(off, n)
        if not blk:
            break
        step = cb if aligned else 512
        for k in range(0, len(blk) - mf.HDR - 8, step):
            if mf.is_file_start(blk, k):
                ts = struct.unpack_from('<Q', blk, k + 8)[0]
                starts.append((off + k, ts))
        off += n
        prog.update(off - base, len(starts))
    prog.done()
    print("[카빙] 파일 시작 후보 %d개" % len(starts))
    if not starts:
        return 0

    # 2단계: 각 시작점에서 청크를 따라가 **정확한 파일 끝**을 구한 뒤 추출
    n_out = 0
    total_bytes = 0
    for i, (pos, ts) in enumerate(starts):
        nxt = starts[i + 1][0] if i + 1 < len(starts) else end
        cap = min(nxt - pos, max_size)
        buf = disk.read_at(pos, cap)
        chunks, real_end = mf.walk(buf, 0)
        if not chunks or real_end < 1024:
            continue                                   # 청크가 안 이어지면 허위 후보
        data = buf[:real_end]
        dt = datetime.fromtimestamp(ts / 1000.0 + tz_offset * 3600, tz=timezone.utc)
        name = "%s_off%d.media" % (dt.strftime("%Y-%m-%d_%H-%M-%S"), pos)
        dst = os.path.join(out, name)
        with open(dst, 'wb') as f:
            f.write(data)
        # mtime도 파일명과 같은 표시 시각으로 (엔트리 복구의 naive local .timestamp()와 동일 규약)
        mt = dt.replace(tzinfo=None).timestamp()
        os.utime(dst, (mt, mt))
        n_out += 1
        total_bytes += real_end
        if n_out <= 10 or n_out % 500 == 0:
            nv = sum(1 for c in chunks if c.is_video)
            print("  OK  %s (%s, 청크%d 비디오%d)" % (name, human(real_end), len(chunks), nv))
        if limit and n_out >= limit:
            print("[카빙] 상한 %d개 도달 (전체는 --carve-limit 0)" % limit)
            break
    print("[카빙] 추출 %d개 · 합계 %s" % (n_out, human(total_bytes)))
    return n_out


def carve(disk, rx, plen, out, max_size, limit, total=None):
    """시그니처(정규식)로 raw 추출. 각 히트 = 파일 시작, 다음 히트나 max_size 에서 끊음."""
    os.makedirs(out, exist_ok=True)
    if total is None:
        try:
            total = os.path.getsize(disk.path)
        except OSError:
            total = 0
    prog = Progress(total or 1, "카빙")
    off, n_found, prev = 0, 0, None
    carry, carry_off = b'', 0
    while total == 0 or off < total:
        blk = disk.read_at(off, BLOCK)
        if not blk:
            break
        buf = carry + blk
        base = carry_off
        for m in rx.finditer(buf):
            hit = base + m.start()
            if prev is not None and hit > prev:
                size = min(hit - prev, max_size)
                _write_carved(disk, prev, size, out, n_found)
                n_found += 1
                if limit and n_found >= limit:
                    prog.done()
                    print("[카빙] 상한 %d개 도달 (전체를 원하면 --carve-limit 0)" % limit)
                    return n_found
            prev = hit
        keep = plen - 1
        carry = buf[-keep:] if keep > 0 else b''
        carry_off = base + len(buf) - len(carry)
        off += len(blk)
        prog.update(off, n_found)
        if len(blk) < BLOCK:
            break
    if prev is not None:
        _write_carved(disk, prev, max_size, out, n_found)
        n_found += 1
    prog.done()
    return n_found


def _write_carved(disk, offset, size, out, idx):
    dst = os.path.join(out, "carved_%06d_off%d.media" % (idx, offset))
    with open(dst, 'wb') as f:
        left = size
        pos = offset
        while left > 0:
            n = min(4 * 1024 * 1024, left)
            data = disk.read_at(pos, n)
            if not data:
                break
            f.write(data)
            pos += len(data)
            left -= len(data)


# ---------------- main ----------------
def open_fs(disk):
    boot = disk.read_at(0, SECTOR)
    if boot[3:11] == b'EXFAT   ':
        return Exfat(disk, boot)
    if boot[82:90].startswith(b'FAT32'):
        return Fat32(disk, boot)
    sys.exit("[오류] FAT32/exFAT 볼륨이 아닙니다 (부트섹터 인식 실패). 드라이브 문자를 확인하세요.")


def match_filters(it, args):
    if it.size < args.min_size:
        return False
    if args.deleted_only and not it.deleted:
        return False
    if args.contains and args.contains.lower() not in it.name.lower():
        return False
    if args.ext:
        e = args.ext.lower().lstrip('.')
        # 8.3 로만 남은 경우 확장자가 3글자로 잘림(media -> med) → 둘 다 허용
        if not (it.name.lower().endswith('.' + e) or it.name.lower().endswith('.' + e[:3])):
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description="SD카드 삭제 파일 복구 (FAT32/exFAT)")
    ap.add_argument("target", nargs='?', help="드라이브 문자(E:) 또는 이미지 파일")
    ap.add_argument("--out", default=None, help="복구 저장 폴더 (반드시 다른 드라이브)")
    ap.add_argument("--ext", default=None, help="확장자 필터 (예: media — 잘린 .med 도 매칭)")
    ap.add_argument("--contains", default=None, help="이름에 이 문자열 포함")
    ap.add_argument("--min-size", type=int, default=1024, help="이 크기(B) 미만 무시")
    ap.add_argument("--deleted-only", action="store_true", help="삭제된 것만 (기본: 전부 표시)")
    ap.add_argument("--list-only", action="store_true", help="추출 없이 목록만")
    ap.add_argument("--limit-list", type=int, default=80, help="목록 최대 출력 줄 수")
    ap.add_argument("--summary", action="store_true", help="확장자별 분포만 출력 (진단용)")
    ap.add_argument("--from-scan", default=None, help="캐시(json)에서 불러와 즉시 필터 — 재스캔 없음")
    ap.add_argument("--save-scan", default=DEFAULT_CACHE, help="스캔 결과 캐시 저장 위치")
    # 카빙
    ap.add_argument("--carve", action="store_true", help="시그니처 카빙 모드 (디렉터리 손실 시)")
    ap.add_argument("--carve-like", default=None, help="이 파일의 앞부분을 시그니처로 사용")
    ap.add_argument("--carve-magic", default=None, help="시그니처 hex (예: 00000001)")
    ap.add_argument("--carve-pattern", default=None,
                    help="와일드카드 지원 hex 패턴. '??'=임의 1바이트 (예: 01000000????????01BA)")
    ap.add_argument("--carve-bytes", type=int, default=8, help="--carve-like 에서 쓸 바이트 수")
    ap.add_argument("--carve-max-size", type=int, default=8 * 1024 * 1024, help="카빙 최대 파일 크기")
    ap.add_argument("--carve-limit", type=int, default=0, help="최대 개수 (0=무제한)")
    ap.add_argument("--carve-format", choices=['media'], default=None,
                    help="포맷 인식 카빙. 'media' = 카메라 .media (구조검증 + 클러스터정렬, 권장)")
    ap.add_argument("--carve-unaligned", action="store_true",
                    help="클러스터 정렬 무시 (파편까지 긁지만 파일 중간 GOP도 잡힘)")
    ap.add_argument("--time-offset", type=float, default=-9.0,
                    help="내장 시각(UTC) 보정 시간. 이 카메라는 -9 가 표시시각과 일치")
    ap.add_argument("--carve-scan-gb", type=float, default=0,
                    help="카드 앞부분 N GB 만 스캔 (0=전체). 빠른 시험용")
    ap.add_argument("--carve-strict", action="store_true",
                    help="첫 청크가 비디오인 파일만 (기본은 오디오로 시작하는 파일도 포함)")
    args = ap.parse_args()

    # ---- 카빙 모드 ----
    if args.carve:
        if not args.target:
            sys.exit("[오류] 카빙에는 대상(E:)이 필요합니다.")
        if not args.out:
            sys.exit("[오류] --out 폴더를 지정하세요.")
        if args.carve_format == 'media':
            disk = Disk(args.target)
            fs = open_fs(disk)
            n = carve_media(disk, fs, os.path.abspath(args.out),
                            args.carve_max_size, args.carve_limit,
                            aligned=not args.carve_unaligned,
                            tz_offset=args.time_offset,
                            scan_bytes=int(args.carve_scan_gb * GB),
                            strict=args.carve_strict)
            print("[완료] 카빙 %d개 -> %s" % (n, os.path.abspath(args.out)))
            print("→ 이제 변환:  python media_to_mp4.py \"%s\" --out .\\Convert"
                  % os.path.abspath(args.out))
            return
        if args.carve_pattern:
            pat = args.carve_pattern
        elif args.carve_like:
            with open(args.carve_like, 'rb') as f:
                pat = binascii.hexlify(f.read(args.carve_bytes)).decode()
        elif args.carve_magic:
            pat = args.carve_magic
        else:
            sys.exit("[오류] --carve-pattern / --carve-magic / --carve-like 중 하나가 필요합니다.")
        rx, plen = pattern_to_regex(pat)
        print("[카빙] 패턴: %s (%d bytes, ?? = 와일드카드)" % (pat, plen))
        disk = Disk(args.target)
        n = carve(disk, rx, plen, os.path.abspath(args.out),
                  args.carve_max_size, args.carve_limit)
        print("[완료] 카빙 %d개 -> %s" % (n, os.path.abspath(args.out)))
        print("※ 카빙 파일에는 원본 파일명·시각이 없습니다 (물리 순서 = 대략 녹화 순서).")
        return

    # ---- 엔트리 복구 모드 ----
    fs = None
    if args.from_scan:
        with open(args.from_scan, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        items = [Found.from_dict(d) for d in cache['items']]
        print("[캐시] %s 에서 %d개 로드 (스캔 대상: %s)" %
              (args.from_scan, len(items), cache.get('target', '?')))
        if not args.list_only:
            disk = Disk(cache['target'])
            fs = open_fs(disk)
    else:
        if not args.target:
            sys.exit("[오류] 대상(E:) 또는 --from-scan 캐시가 필요합니다.")
        disk = Disk(args.target)
        fs = open_fs(disk)
        print("[스캔] 전체 탐색 중... (57GB 기준 약 45분, 결과는 캐시에 저장됨)")
        items = fs.scan()
        try:
            with open(args.save_scan, 'w', encoding='utf-8') as f:
                json.dump({'target': args.target, 'scanned': datetime.now().isoformat(),
                           'items': [i.to_dict() for i in items]}, f, ensure_ascii=False)
            print("[캐시] 저장: %s  → 다음부터  --from-scan \"%s\"  로 즉시 필터"
                  % (args.save_scan, args.save_scan))
        except OSError as e:
            print("[경고] 캐시 저장 실패: %s" % e)

    n_del = sum(1 for i in items if i.deleted)
    print("[수집] 총 %d개 (삭제됨 %d · 정상 %d)" % (len(items), n_del, len(items) - n_del))

    if args.summary:
        hist = {}
        for it in items:
            ext = ('.' + it.name.rsplit('.', 1)[1].lower()) if '.' in it.name else '(없음)'
            d = hist.setdefault(ext, [0, 0, 0])          # [개수, 삭제됨, 총크기]
            d[0] += 1
            d[1] += 1 if it.deleted else 0
            d[2] += it.size
        print("[확장자 분포]  확장자      개수   (삭제됨)      총크기")
        for ext, (n, nd, sz) in sorted(hist.items(), key=lambda kv: -kv[1][0])[:30]:
            print("   %-12s %7d   %7d   %10s" % (ext, n, nd, human(sz)))
        return

    seen, results = set(), []
    for it in items:
        if not match_filters(it, args):
            continue
        key = (it.name.lower(), it.size, it.cluster)
        if key in seen:
            continue
        seen.add(key)
        results.append(it)
    results.sort(key=lambda x: (x.mtime or datetime.min, x.name))

    print("[필터 결과] %d개" % len(results))
    total = 0
    for n, it in enumerate(results):
        total += it.size
        if n < args.limit_list:
            print("  %s %s  %10s  cluster=%-9d %s" %
                  ('DEL ' if it.deleted else 'live',
                   it.mtime.strftime('%Y-%m-%d %H:%M:%S') if it.mtime else '  시각불명       ',
                   human(it.size), it.cluster, it.name))
    if len(results) > args.limit_list:
        print("  ... 외 %d개 (--limit-list 로 더 보기)" % (len(results) - args.limit_list))
    if results:
        print("  합계 %s" % human(total))
    else:
        print("→ 조건에 맞는 게 없습니다. --ext/--contains 를 빼고 전체를 확인해 보세요.")
        print("   엔트리 자체가 거의 없다면 디렉터리가 덮인 것 → --carve 모드를 사용하세요.")
        return

    if args.list_only:
        print("\n추출하려면 --list-only 를 빼고 --out D:\\recovered 를 추가하세요.")
        return

    out = os.path.abspath(args.out) if args.out else None
    if not out:
        sys.exit("[오류] --out 폴더를 지정하세요.")
    src_drv = os.path.splitdrive(fs.d.path.replace('\\\\.\\', ''))[0].upper()
    if src_drv and os.path.splitdrive(out)[0].upper() == src_drv:
        sys.exit("[오류] 출력 폴더가 복구 대상 드라이브와 같습니다 — 다른 드라이브로 지정하세요.")
    os.makedirs(out, exist_ok=True)

    ok = fail = 0
    for it in results:
        name = safe_name(it.name)
        dst = os.path.join(out, name)
        k = 1
        while os.path.exists(dst):
            stem, dot, ext = name.rpartition('.')
            dst = os.path.join(out, "%s_%d%s%s" % (stem or name, k, '.' if dot else '', ext if dot else ''))
            k += 1
        try:
            with open(dst, 'wb') as f:
                got = fs.extract(it, f)
            if it.mtime:
                ts = it.mtime.timestamp()
                os.utime(dst, (ts, ts))
            ok += 1
            if ok <= 20 or ok % 100 == 0:
                print("  OK  %s (%s)" % (os.path.basename(dst), human(got)))
        except Exception as e:
            print("  X   %s: %s" % (it.name, e))
            try:
                os.remove(dst)
            except OSError:
                pass
            fail += 1

    print("[완료] 복구 %d · 실패 %d  ->  %s" % (ok, fail, out))
    print("※ 연속 배치 가정 추출입니다. 중간부터 깨진 파일은 조각나 있던 것 —")
    print("  그런 경우 --carve 나 PhotoRec 을 시도하세요.")


if __name__ == "__main__":
    main()
