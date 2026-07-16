# Tuya 카메라 연동 (go2rtc → Grafana)

Tuya 클라우드 홈캠(KERUI 등)을 브라우저/Grafana에서 보기.
로컬 RTSP가 없으므로 **go2rtc의 네이티브 Tuya(WebRTC)** 를 사용합니다.

```
Tuya 카메라 ──(클라우드/WebRTC)──▶ go2rtc(:1984) ──(WebRTC iframe)──▶ Grafana 패널
```

## 1. 사전 준비
- **"Tuya Smart" 앱 계정** — ⚠️ **"Smart Life" 앱은 미지원**. Smart Life에 있으면 **삭제 후 Tuya Smart 앱에 다시 추가**.
- 카메라 **device_id**: Tuya Smart 앱 → 기기 → 설정/기기정보. (재추가하면 id가 바뀜)

## 2. 설정 — `.env`
```ini
TUYA_EMAIL=계정이메일
TUYA_PASSWORD=비밀번호        # ⚠️ URL 인코딩:  & → %26,  % → %25,  # → %23,  + → %2B
TUYA_DEVICE_ID=eb...
GO2RTC_PORT=1984
```
- 비밀번호는 URL 쿼리에 들어가므로 **특수문자 인코딩 필수**.
- `.env`는 gitignore 됨 → **Mint 호스트엔 수동 복사**(이미 있으면 Camera 섹션만 append).
- region은 [go2rtc.yaml](go2rtc.yaml)에서 `protect-us`(미주/한국 대개) / `protect-eu` / `protect-in`.

## 3. 실행
```bash
docker compose up -d
```

## 4. 확인
- **http://<호스트>:1984** (go2rtc 웹 UI) → `camera1` 재생되면 성공.
- 손으로 안 맞춰지면 → 웹 UI **[Add] > [Tuya]** 마법사(지역 선택 + 이메일/비번)로 **자동 발견**이 제일 쉽고 실패가 적음.

## 5. Grafana
- 대시보드 **카메라 패널**이 자동 임베드: `http://<호스트>:1984/stream.html?src=camera1` (WebRTC).
- HTML 임베드 허용: docker-compose에 `GF_PANELS_DISABLE_SANITIZE_HTML=true` 설정됨.

## 6. 영상 + 소리 얻기
go2rtc는 소스의 **영상+오디오 트랙을 함께** 전달합니다. **출력 방식에 따라 소리 유무가 갈립니다**:

| 방식 | URL (`<호스트>` = 172.30.1.42) | 영상 | 소리 |
|---|---|---|---|
| **WebRTC** (권장) | `http://<호스트>:1984/stream.html?src=camera1` | ✅ | ✅ |
| HLS | `http://<호스트>:1984/api/stream.m3u8?src=camera1` | ✅ | ✅ |
| MJPEG | `http://<호스트>:1984/api/stream.mjpeg?src=camera1` | ✅ | ❌ 무음 |
| 스냅샷 | `http://<호스트>:1984/api/frame.jpeg?src=camera1` | 정지 | ❌ |

- **소리를 들으려면 WebRTC(또는 HLS)** 사용. **MJPEG은 소리 없음** (Grafana 패널은 WebRTC라 OK).
- 브라우저는 자동재생 시 **음소거로 시작** → 플레이어/Grafana 카메라 패널에서 **스피커 아이콘 클릭해 음소거 해제**.
- 오디오 코덱이 WebRTC 비호환이면 go2rtc가 **자동 트랜스코딩**(ffmpeg 내장).
- 그래도 무음이면: 카메라 마이크가 켜져 있는지, `:1984` 스트림 info에 **audio 트랙**이 잡히는지 확인.

## 7. iOS / iPad (Safari) — 데스크톱은 되는데 아이폰만 안 될 때
iPhone/iPad Safari는 WebRTC가 까다로워 **3가지**가 필요합니다:

**① ICE 후보 명시 (재생 실패 방지)** — `go2rtc.yaml`:
```yaml
webrtc:
  candidates:
    - 172.30.1.42:8555   # 도커 호스트 LAN IP
    - stun:8555
```
데스크톱은 자동 후보로 되지만 iOS는 이게 없으면 연결 실패.

**② H.264 트랜스코딩 (검은 화면 방지)** — 카메라가 **H.265(HEVC)** 면 iOS WebRTC가 디코드 못 해 **검은 화면**. `streams`에 H.264 소스 추가:
```yaml
streams:
  camera1:
    - tuya://...
    - ffmpeg:camera1#video=h264
```
→ go2rtc가 **iOS엔 H.264(변환), 데스크톱엔 원본** 자동 제공(iOS 접속 시에만 ffmpeg 동작).

**③ 방화벽 8555** — 호스트가 `8555`(tcp+udp) 허용: `sudo ufw allow 8555`.

### 증상별 진단
| 증상 | 원인 | 조치 |
|---|---|---|
| 재생 실패(에러 뜸) | ICE 후보 미설정 | ① candidates 추가 |
| 검은 화면(에러 없음) | H.265 코덱 | ② ffmpeg h264 소스 추가 |
| 로딩만/느림 | iPhone은 MSE 미지원 | URL에 `&mode=webrtc` |
| 직접은 되는데 Grafana만 X | 교차출처 iframe 정책 | 패널을 "새 탭 열기" 링크로 |

### 테스트 순서
1. 아이폰 Safari에서 **직접**: `http://172.30.1.42:1984/stream.html?src=camera1&mode=webrtc`
2. 위가 되면 Grafana 패널도 됩니다(안 되면 iframe 문제 → 마지막 행).

> 설정 변경 후엔 `docker compose restart go2rtc`. iOS는 **같은 WiFi(LAN)** 여야 함.

## 트러블슈팅
| 증상 | 원인 / 조치 |
|---|---|
| 로그인/재생 실패 | ① **Smart Life 계정**(→ Tuya Smart로 이전) ② **region 불일치**(protect-us→eu/in) ③ 계정 2FA |
| region 모름 | 웹 UI 마법사에서 지역 선택하며 시도 |
| 비번에 `&%#+` 등 | **URL 인코딩** (`&`→`%26` 등) |
| device_id 안 맞음 | 웹 UI 마법사가 **계정에서 자동 발견**하니 그걸로 |
| 화면 안 뜸(패널만 검정) | `:1984`에서 먼저 재생되는지 확인 → 되면 Grafana 패널의 호스트 IP 확인 |

> 참고: Tuya 클라우드 경유라 초기 연결에 수 초 지연·간헐 재연결이 있을 수 있습니다(정상).
> 이 카메라는 로컬 RTSP가 아니므로 `CAMERA_IP`는 사용되지 않습니다.
