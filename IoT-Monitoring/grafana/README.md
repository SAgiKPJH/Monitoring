# Grafana 운영 — 인증 · 세션 · 로그인 이력

설정은 [docker-compose.yml](../docker-compose.yml)의 `grafana` 서비스 환경변수와 `.env` 에 있습니다.
**환경변수를 바꾼 뒤에는 `restart` 가 아니라 `up -d` 로 컨테이너를 재생성**해야 반영됩니다.

```bash
docker compose up -d grafana
```

---

## 1. 로그인 필수 설정

```yaml
GF_AUTH_ANONYMOUS_ENABLED: "false"    # 로그인해야 대시보드 열람 가능
GF_USERS_ALLOW_SIGN_UP: "false"       # 자가 가입 차단 (관리자만 계정 생성)
```

계정은 `.env` 의 `GRAFANA_USER` / `GRAFANA_PASSWORD` 로 만들어집니다.

> ⚠️ 이 값은 **첫 실행(빈 볼륨)에서만** 계정을 생성합니다. 이미 `admin/admin` 으로 초기화된 볼륨이 있으면
> 그 계정이 그대로 남습니다. 기존 계정으로 로그인 후 **Administration → Users** 에서 변경하세요.

---

## 2. 로그인 유지 기간

`.env` 에서 조절합니다.

```ini
GRAFANA_SESSION_IDLE=30d    # 이 기간 미접속 시 자동 로그아웃 (Grafana 기본 7d)
GRAFANA_SESSION_MAX=90d     # 로그인 후 최대 유지 기간 (Grafana 기본 30d)
```

| 변수 | 대응 Grafana 설정 | 의미 |
|---|---|---|
| `GRAFANA_SESSION_IDLE` | `GF_AUTH_LOGIN_MAXIMUM_INACTIVE_LIFETIME_DURATION` | **체감 기간** — 마지막 접속 후 이만큼 지나면 로그아웃 |
| `GRAFANA_SESSION_MAX` | `GF_AUTH_LOGIN_MAXIMUM_LIFETIME_DURATION` | 계속 접속해도 이 기간이 지나면 재로그인 |

형식: `12h`, `7d`, `30d`, `90d`, `1y`

---

## 3. 로그인 이력 · 접속 IP 확인

Grafana 는 모든 HTTP 요청을 IP와 함께 기록하므로 `/login` 요청만 추려 봅니다.

```bash
# 로그인 시도 전체 (IP + 성공/실패)
docker logs iot-grafana 2>&1 | grep "path=/login"

# 실패만 (status=401)
docker logs iot-grafana 2>&1 | grep "path=/login" | grep "status=401"

# 실시간 감시
docker logs -f iot-grafana 2>&1 | grep "path=/login"

# IP별 시도 횟수 집계
docker logs iot-grafana 2>&1 | grep "path=/login" \
  | grep -oP 'remote_addr=\S+' | sort | uniq -c | sort -rn
```

로그 형태 (핵심 필드):
```
msg="Request Completed" method=POST path=/login status=401 remote_addr=172.30.1.55 ...
                                           ↑ 401=실패 / 200=성공   ↑ 접속 IP
```

### 사용자별 마지막 접속 시각
```bash
curl -s -u <계정>:<비밀번호> http://172.30.1.42:3000/api/users | python3 -m json.tool
```
→ 각 계정의 `lastSeenAt`. UI 로는 **Administration → Users**.

### 무차별 대입 차단 (자동)
`GF_SECURITY_DISABLE_BRUTE_FORCE_LOGIN_PROTECTION: "false"` — **5회 연속 실패 시 5분 차단**됩니다.

---

## 4. 알아둘 제약

| 항목 | 내용 |
|---|---|
| **IP가 게이트웨이로 보일 때** | `remote_addr` 가 `172.x.0.1`(도커 게이트웨이)만 찍히면 실제 클라이언트 IP가 가려진 것. 위 grep 으로 먼저 확인 |
| **로그 순환 삭제** | 현재 `max-size: 10m × max-file: 3`. 오래 보관하려면 compose 의 `x-common` 로깅 옵션을 늘릴 것 |
| **정식 감사 로그** | 누가 언제 무엇을 조회했는지 추적하는 audit log 는 **Grafana Enterprise 전용**. OSS 는 위 컨테이너 로그가 사실상 유일한 수단 |
| **`login_attempt` 테이블** | Grafana DB 에 username+IP 가 저장되지만 무차별 대입 방어용이라 **몇 분 뒤 자동 삭제** → 이력 추적엔 부적합 |

---

## 5. 기타 운영

### 홈 화면을 IoT 대시보드로
```yaml
GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH: /etc/grafana/provisioning/dashboards/iot-monitoring.json
```
접속 즉시 **IoT 집 모니터링** 대시보드가 뜹니다. 특정 계정이 개인 설정
(**Profile → Preferences → Home Dashboard**)을 지정했다면 그 계정만 개인 설정이 우선합니다.

### 프로비저닝 (파일로 관리되는 항목)
| 경로 | 내용 |
|---|---|
| `provisioning/dashboards/iot-monitoring.json` | 대시보드 (평면도 · 상세 · 오류 로그) |
| `provisioning/alerting/rules.yaml` | 알림 규칙 (온도/습도/배터리) |
| `provisioning/alerting/rules-stale.yaml` | 데이터 끊김 알림 (30분 경고 / 60분 연결 끊김) |
| `provisioning/alerting/rules-comfort.yaml` | 환기 추천 알림 (BRB ≥ 20℃ 이고 TO ≤ BRB → 밖이 더 시원) |
| `provisioning/alerting/slack.yaml` | Slack 컨택트포인트 · 라우팅 |
| `provisioning/datasources/` | Infinity 데이터소스 |

파일 수정 후 반영:
```bash
docker compose restart grafana
```

> 규칙의 `uid` 를 바꾸면 **옛 uid 규칙이 DB 에 남아 알림이 중복**됩니다.
> `rules.yaml` 의 `deleteRules:` 에 옛 uid 를 명시해 삭제하세요.

### Grafana 만 완전 초기화 (⚠️ UI 에서 수정한 대시보드·계정·알림 이력 소실)

다른 서비스(mongo·api·go2rtc)는 건드리지 않습니다.
볼륨은 **컨테이너를 삭제해야** 지울 수 있으므로 `stop` 이 아니라 `rm -sf` 를 씁니다.

```bash
docker compose rm -sf grafana                    # 중지 + 컨테이너 삭제
docker volume rm iot-monitoring_grafana_data     # 볼륨 삭제
docker compose up -d grafana                     # 재생성 (프로비저닝 다시 적용)
```

초기화 후에는 `.env` 의 `GRAFANA_USER` / `GRAFANA_PASSWORD` 로 계정이 새로 만들어지고,
`provisioning/` 의 대시보드·알림·데이터소스가 자동 적용됩니다.

> `docker volume rm` 이 *volume is in use* 로 실패하면 컨테이너가 아직 남아 있는 것입니다.
> `docker ps -a | grep grafana` 로 확인 후 `docker rm -f iot-grafana` 로 지우세요.
