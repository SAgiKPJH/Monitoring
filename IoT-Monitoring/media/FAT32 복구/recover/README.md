# recover — SD카드 삭제 파일 복구 (.media 등)

`sd_recover.py` : FAT32/exFAT 볼륨을 raw 로 읽어 삭제된 파일을 복구합니다.
**스캔 결과를 캐시**하므로, 한 번 스캔한 뒤에는 필터를 바꿔도 재스캔 없이 즉시 확인됩니다.

## ⚠️ 먼저
- 대상 카드(E:)에 **아무것도 쓰지 마세요**. 카메라에 다시 꽂지 마세요(루프 녹화가 덮어씀).
- 출력은 **다른 드라이브**(D: 등). 같은 드라이브면 실행을 거부합니다.
- **관리자 권한 PowerShell** 에서 실행.

---

## 1) 전체 스캔 (57GB 기준 ~45분, 1회만)
확장자 필터 없이 **전부** 모아 캐시에 저장합니다.
```powershell
cd D:\Code\Monitoring\IoT-Monitoring\media
.\.venv\Scripts\python.exe recover\sd_recover.py E: --list-only
```
끝나면 `recover\scan_cache.json` 이 생기고, 아래처럼 출력됩니다.
```
[수집] 총 41823개 (삭제됨 41706 · 정상 117)
[필터 결과] 41823개
  DEL  2026-07-24 15:30:00    327.0 KB  cluster=51232   0000.media
  ...
```

## 2) 캐시로 즉시 필터 (재스캔 없음 — 몇 초)
```powershell
.\.venv\Scripts\python.exe recover\sd_recover.py --from-scan recover\scan_cache.json --contains media --list-only
```

## 3) 추출
```powershell
.\.venv\Scripts\python.exe recover\sd_recover.py --from-scan recover\scan_cache.json --contains media --deleted-only --out D:\recovered
```

## 4) mp4 변환
```powershell
.\.venv\Scripts\python.exe media_to_mp4.py D:\recovered --out .\Convert
```

---

## 옵션
| 옵션 | 설명 |
|---|---|
| `--list-only` | 추출 없이 목록만 |
| `--from-scan <json>` | 캐시에서 즉시 필터 (재스캔 없음) |
| `--save-scan <json>` | 캐시 저장 위치 (기본 `recover/scan_cache.json`) |
| `--contains media` | 이름에 문자열 포함 (권장 — 이름이 잘려도 매칭) |
| `--ext media` | 확장자 필터 (8.3로 잘린 `.med` 도 함께 매칭) |
| `--deleted-only` | 삭제된 것만 |
| `--min-size N` | N바이트 미만 무시 (기본 1024) |
| `--limit-list N` | 목록 출력 줄 수 (기본 80) |

---

## ⭐ 카메라 .media 전용 카빙 (`--carve-format media`) — 권장

디렉터리 엔트리가 덮여 이름 기반 복구가 안 될 때 사용합니다. 이 포맷 전용이라 정확합니다:
**구조 검증**(`01000000` 매직 + 유효 Unix ms 타임스탬프 + `34 00 00 00` + H.264 SPS)
+ **클러스터 정렬 검사**로 파일 중간의 GOP 세그먼트를 걸러내고 진짜 파일 시작만 잡습니다.
복구본 이름·수정시각은 **파일에 내장된 촬영 시각**으로 붙습니다.

```powershell
# 1) 먼저 200개만 시험
.\.venv\Scripts\python.exe recover\sd_recover.py E: --carve --carve-format media --out D:\carved --carve-limit 200
# 2) mp4 로 변환해 재생 확인
.\.venv\Scripts\python.exe media_to_mp4.py D:\carved --out .\Convert
# 3) 괜찮으면 전체
.\.venv\Scripts\python.exe recover\sd_recover.py E: --carve --carve-format media --out D:\carved --carve-limit 0
```
| 옵션 | 설명 |
|---|---|
| `--carve-limit N` | 최대 개수 (0=무제한). 먼저 200으로 시험 권장 |
| `--carve-max-size N` | 파일 최대 크기 (기본 8MB) |
| `--time-offset -9` | 내장 시각(UTC) 보정 (기본 −9 = 카메라 표시시각) |
| `--carve-unaligned` | 클러스터 정렬 무시 (파편까지 긁지만 중간 GOP도 잡힘) |

---

## 일반 카빙 (다른 포맷)
디렉터리 엔트리가 덮였다면 이름 기반 복구가 불가능합니다. 이때는 **파일 시그니처**로 직접 긁어냅니다.
```powershell
# 정상 .media 파일이 하나라도 있으면 그 앞부분을 시그니처로 사용 (가장 정확)
.\.venv\Scripts\python.exe recover\sd_recover.py E: --carve --carve-like 샘플.media --out D:\carved

# 또는 시그니처를 직접 지정 (예: H.264 start code)
.\.venv\Scripts\python.exe recover\sd_recover.py E: --carve --carve-magic 00000001 --out D:\carved --carve-limit 200
```
| 카빙 옵션 | 설명 |
|---|---|
| `--carve-like <파일>` | 그 파일의 앞 N바이트를 시그니처로 |
| `--carve-bytes N` | 시그니처 길이 (기본 8) |
| `--carve-magic <hex>` | 시그니처 직접 지정 |
| `--carve-max-size N` | 파일 최대 크기 (기본 8MB) |
| `--carve-limit N` | 최대 개수 (0=무제한, 먼저 200개로 시험 권장) |

> 카빙은 **파일명·시각이 없습니다**(`carved_000123_off...media`). 먼저 `--carve-limit 200`으로
> 몇 개 뽑아 재생되는지 확인한 뒤 전체를 돌리세요.

---

## 검증 상태 / 한계
- 합성 **FAT32·exFAT 이미지로 end-to-end 검증**: 삭제 파일의 긴 이름·시각·크기 복원 + 추출 내용 **바이트 일치**, 캐시/필터/카빙 동작 확인.
- **연속 배치 가정** 추출 — 카메라 순차 기록은 대개 맞지만, 조각난 파일은 뒷부분이 깨질 수 있음
  → 그런 경우 `--carve` 또는 [PhotoRec](https://www.cgsecurity.org/wiki/TestDisk_Download).
- 이미 덮어쓰인 데이터는 어떤 도구로도 복구 불가.
