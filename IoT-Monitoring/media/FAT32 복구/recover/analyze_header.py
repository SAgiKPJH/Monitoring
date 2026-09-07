#!/usr/bin/env python3
r"""
analyze_header.py — 샘플 .media 파일들의 공통 헤더(시그니처)를 찾아
sd_recover.py --carve 에 쓸 --carve-magic 값을 알려준다.

여러 파일의 앞부분을 비교해 **공통 접두사**를 구하고, 파일 크기 통계로
--carve-max-size 추천값도 제시한다.

사용:
  python analyze_header.py D:\recovered_live
  python analyze_header.py D:\recovered_live --bytes 64
"""
import argparse
import binascii
import os
import sys


def hexdump(data, width=16, limit=64):
    out = []
    for off in range(0, min(len(data), limit), width):
        chunk = data[off:off + width]
        hx = ' '.join('%02X' % b for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        out.append("  %04X  %-47s  |%s|" % (off, hx, asc))
    return '\n'.join(out)


def common_prefix(blobs):
    if not blobs:
        return b''
    n = min(len(b) for b in blobs)
    i = 0
    while i < n and all(b[i] == blobs[0][i] for b in blobs):
        i += 1
    return blobs[0][:i]


def main():
    ap = argparse.ArgumentParser(description="샘플 파일들의 공통 헤더(카빙 시그니처) 분석")
    ap.add_argument("folder", help="샘플 .media 파일들이 있는 폴더")
    ap.add_argument("--ext", default="media", help="대상 확장자 (기본 media)")
    ap.add_argument("--bytes", type=int, default=64, help="비교할 앞부분 바이트 수")
    ap.add_argument("--max-files", type=int, default=50, help="비교할 최대 파일 수")
    args = ap.parse_args()

    files = []
    for root, _, names in os.walk(args.folder):
        for n in sorted(names):
            if n.lower().endswith('.' + args.ext.lower().lstrip('.')):
                files.append(os.path.join(root, n))
    if not files:
        sys.exit("[오류] .%s 파일을 찾지 못했습니다: %s" % (args.ext, args.folder))
    files = files[:args.max_files]

    blobs, sizes = [], []
    for p in files:
        with open(p, 'rb') as f:
            blobs.append(f.read(args.bytes))
        sizes.append(os.path.getsize(p))

    print("[샘플] %d개 파일 분석" % len(files))
    print("\n[첫 번째 파일 헤더]  %s" % os.path.basename(files[0]))
    print(hexdump(blobs[0], limit=args.bytes))

    if len(blobs) > 1:
        print("\n[두 번째 파일 헤더]  %s" % os.path.basename(files[1]))
        print(hexdump(blobs[1], limit=args.bytes))

    pre = common_prefix(blobs)
    print("\n[공통 접두사] %d bytes" % len(pre))
    if pre:
        print(hexdump(pre, limit=len(pre)))

    # 바이트 위치별 일치율 — 접두사가 짧아도 고정 패턴을 찾기 위해
    n = min(len(b) for b in blobs)
    fixed = [i for i in range(n) if all(b[i] == blobs[0][i] for b in blobs)]
    print("\n[고정 바이트 위치] %d / %d  → %s" %
          (len(fixed), n, ', '.join(str(i) for i in fixed[:40]) + (' ...' if len(fixed) > 40 else '')))

    print("\n[크기 통계] 최소 %s · 최대 %s · 평균 %s" %
          (_h(min(sizes)), _h(max(sizes)), _h(sum(sizes) // len(sizes))))

    print("\n" + "=" * 70)
    if len(pre) >= 4:
        magic = binascii.hexlify(pre[:min(16, len(pre))]).decode()
        rec_size = max(sizes) * 2
        print("추천 카빙 명령:")
        print("  python recover\\sd_recover.py E: --carve \\")
        print("      --carve-magic %s \\" % magic)
        print("      --carve-max-size %d \\" % rec_size)
        print("      --carve-limit 200 --out D:\\carved_test")
        print("\n  (먼저 200개만 뽑아 재생되는지 확인 → 되면 --carve-limit 0 으로 전체)")
    else:
        print("[경고] 공통 접두사가 %d바이트로 너무 짧습니다." % len(pre))
        print("  파일마다 헤더가 달라 시그니처 카빙이 어려울 수 있습니다.")
        print("  위 헤더 덤프를 보고 고정 패턴을 직접 골라 --carve-magic 에 지정하세요.")
    print("=" * 70)


def _h(n):
    n = float(n)
    for u in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or u == 'GB':
            return "%.1f %s" % (n, u)
        n /= 1024.0


if __name__ == "__main__":
    main()
