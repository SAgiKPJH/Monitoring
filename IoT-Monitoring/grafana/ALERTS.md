# 알림(Alert) 비즈니스 정리

센서 → API → Grafana(Infinity) → **Slack** 으로 흐르는 알림 규칙의 한 장 요약.
규칙 원본은 `provisioning/alerting/` 의 YAML (여기가 진실 공급원, UI 수정은 재시작 시 덮어씀).

```
Pico(5분마다 전송) → RDK X5 → API(Mongo) ← Grafana 가 주기 평가 → 조건 충족 → Slack
```

## 1. 환경 알림 — 온도 · 습도 · 배터리 (`rules.yaml`)

**⚠️ 현재 BRB(아기 침대 옆)만 적용.** 다른 방(BRO/TO/RO/MR)은 아직 복제 안 함.
평가 1분 주기, 최신값(`/api/readings/latest`) 기준.

| 항목 | 조건 | 심각도 |
|---|---|---|
| 온도 높음 | > 27℃ | 위험 |
| 온도 높음 | > 28℃ | 경고 |
| 온도 낮음 | < 22℃ | 위험 |
| 온도 낮음 | < 20℃ | 경고 |
| 습도 | 40~60% 벗어남 | 위험 |
| 습도 | 20~80% 벗어남 | 경고 |
| 배터리 | < 20% | 경고 |
| 배터리 | < 10% | 교체 |

> 참고: 온도 27/28, 습도 범위는 중첩 사양이라 **경계를 넘으면 두 알림이 같이** 올 수 있음
> (예: 29℃ → 위험+경고, 습도 15% → 위험+경고). 사용자 지정 사양 그대로 구현한 것.

## 2. 데이터 끊김 알림 (`rules-stale.yaml`)

**5개 방 전부 적용.** 평가 5분 주기, `/api/readings/status` 의 `ageMinutes`(마지막 수신 후 경과 분) 기준.

| 조건 | 의미 | 심각도 |
|---|---|---|
| ageMinutes > 30 | 30분째 데이터 없음 | 경고 |
| ageMinutes > 60 | 연결 끊김 | 위험 |
| ageMinutes = -1 | 한 번도 수신 없음 | (알림 안 감) |

대시보드의 「📡 노드 연결 상태」 패널이 같은 값을 색으로 표시
(초록 정상 · 주황 30분↑ · 빨강 60분↑ · 회색 데이터 없음).

## 3. 환기 추천 알림 (`rules-comfort.yaml`)

| 조건 | 동작 |
|---|---|
| BRB ≥ 20℃ **이고** TO ≤ BRB 가 **10분 지속** | 🌬️ "밖이 더 시원해요 — 창문 열기 좋은 때" (정보) |

- 20℃ 문턱은 **방(BRB) 기준** — 겨울에 방이 춥고 밖이 더 추울 땐 안 울림.
- `for: 10m` 은 경계값 근처에서 발생/해제 반복(플래핑) 방지용.
- 조건이 풀리면 🟢 해제 메시지도 옴.

## 4. 오류(Exception) 리포트 — 알림 아님

Pico 가 blink 후 NRF 로 보낸 오류(`errorCode`)는 `/api/errors` → Mongo 에 쌓이고
대시보드 「⚠️ 오류 로그」 테이블에서 **조회만** 한다. Slack 알림은 안 감.
(코드 1 = AM2320 읽기 실패, 2 = NRF 초기화 실패)

## 5. 전송 정책 — Slack (`slack.yaml`)

| 설정 | 값 | 의미 |
|---|---|---|
| 수신처 | Slack incoming webhook (`SLACK_WEBHOOK_URL`, `.env`) | 단일 채널 |
| group_by | alertname + deviceId | 방·규칙별로 묶어서 |
| group_wait / group_interval | 0s / 1m | 발생 즉시 전송 |
| repeat_interval | 4h | 계속 걸려 있으면 4시간마다 재전송 |
| 해제 메시지 | 켜짐 | 🔴 발생 / 🟢 해제 둘 다 전송 |

메시지 본문은 각 규칙의 `summary` (현재 측정값 포함).

## 6. 운영 메모

- **반영**: YAML 수정 → `docker compose restart grafana`
- **uid 변경 금지**: 규칙 `uid` 를 바꾸면 옛 uid 가 DB 에 남아 **알림이 중복** →
  옛 uid 를 `deleteRules:` 에 등록해야 함 (예: `rules.yaml` 하단)
- **noDataState / execErrState = OK**: API 가 죽거나 응답이 없어도 이 규칙들 자체는
  오탐하지 않음 (데이터 끊김은 2번 규칙이 전담)
- 알림 상태 확인: Grafana → Alerting → Alert rules → **IoT Alerts** 폴더

## TODO

- [ ] 환경 알림(1번)을 BRO/TO/RO/MR 에도 복제 (rules.yaml 헤더 주석 참고)
