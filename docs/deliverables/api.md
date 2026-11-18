# API 명세서

- 기준: `app/routes.py`, `app/main.py`
- 방식: **서버 렌더링 HTML** (FastAPI + Jinja2). JSON API가 아니라 브라우저 폼 POST → `303 See Other` 리다이렉트(PRG 패턴)예요. `/healthz`만 JSON.
- 요청 본문: `application/x-www-form-urlencoded` (HTML `<form>`)
- 인증: 없음. 경로의 `{token}`(랜덤 22자)이 곧 열쇠. 2단계에서 카카오 로그인은 "연결"용 선택 기능.
- 자동 문서(`/docs`, `/redoc`, `/openapi.json`)는 공개 서버라 꺼 둠.
- 오류는 모두 같은 안내 화면(`error.html`)에 상태 코드와 한 줄 메시지.

## 1. 공통

### 요청 제한 (IP별, 메모리 기반 `RateLimiter`)

| 이름 | 한도 | 적용 경로 |
|---|---|---|
| `START_PER_IP` | 10분 5회 | `POST /start`, `POST /c/{token}/next` |
| `START_GLOBAL` | 하루 500회(전체) | `POST /start` |
| `DAY_PER_IP` | 1분 30회 | `POST /c/{token}/day/{n}`, `POST /c/{token}/week/{w}/level`, `POST /c/{token}/kakao/notify`·`/unlink` |
| `AUTH_PER_IP` | 10분 10회 | 카카오 로그인 시작(`/c/{token}/kakao`, `/auth/kakao`) |

초과 시 `429` "요청이 너무 많아요. 잠시 후 다시 시도해 주세요." IP는 프록시가 덮어쓴 `X-Forwarded-For` 첫 값.

### 체험 상태에 따른 공통 처리

| 상황 | 응답 |
|---|---|
| `{token}` 체험 없음 | `404` "체험을 찾을 수 없어요…" |
| 맞춤 질문 전(`setup_done = False`)에 기록·리포트·PDF 접근 | `303` → `/c/{token}/setup` |
| 맞춤 질문 끝난 뒤 `/setup` 접근 | `303` → `/c/{token}` |

## 2. 1단계 엔드포인트 (✅ 구현)

| # | 메서드 | 경로 | 설명 | 성공 응답 |
|---|---|---|---|---|
| 1 | GET | `/` | 시작 화면(예시 위험도) | 200 HTML |
| 2 | GET | `/start` | 몸 정보 입력 폼 | 200 HTML |
| 3 | POST | `/start` | 체험 생성 | 303 → `/c/{token}/result` |
| 4 | GET | `/c/{token}/result` | 위험도 결과 | 200 HTML |
| 5 | GET | `/c/{token}/setup` | 맞춤 질문 폼 | 200 HTML |
| 6 | POST | `/c/{token}/setup` | 맞춤 답변 저장 | 303 → `/c/{token}/ready` |
| 7 | GET | `/c/{token}/ready` | 응원 + 주의사항, 6초 뒤 자동 이동 | 200 HTML |
| 8 | GET | `/c/{token}` | 기록 화면(오늘 계획·도장판·주간 요약) | 200 HTML |
| 9 | POST | `/c/{token}/day/{n}` | n일째 기록 저장(덮어쓰기) | 303 → `/c/{token}` |
| 10 | POST | `/c/{token}/week/{w}/level` | 다음 주 강도 결정 | 303 → `/c/{token}` |
| 11 | GET | `/c/{token}/report` | 30일 변화 리포트 | 200 HTML |
| 12 | GET | `/c/{token}/week/{w}.pdf` | 주간 계획표 PDF | 200 `application/pdf` |
| 13 | GET | `/c/{token}/plan.pdf` | (옛 링크) 현재 주 PDF로 | 303 → `/c/{token}/week/{현재 주}.pdf` |
| 14 | GET | `/healthz` | 헬스 체크 | 200 `{"ok": true}` |
| 15 | GET | `/static/*` | CSS·JS·글꼴 | 200 |

### 2.1 POST `/start` — 체험 생성

| 필드 | 형식 | 규칙 |
|---|---|---|
| `sex` | `M` \| `F` | 필수 |
| `age` | 정수 | 18~100 |
| `height_cm` | 실수 | 120~220 |
| `weight_kg` | 실수 | 30~250 |

- 처리: `assess()`로 검증·위험도 계산 → 계획 종류(`plan_variant`) 결정 → `trials` 행 생성(`start_date` = 오늘 KST).
- 오류: 통계 파일 없음 `503` / 요청 제한 `429` / 숫자 아님·범위 밖 `400`(입력 폼을 값과 함께 다시 보여 주고 `role="alert"` 메시지).

```http
POST /start
Content-Type: application/x-www-form-urlencoded

sex=M&age=45&height_cm=172&weight_kg=82
```
```http
HTTP/1.1 303 See Other
Location: /c/Xb3k...Q9/result
```

### 2.2 POST `/c/{token}/setup` — 맞춤 답변

| 필드 | 값 |
|---|---|
| `diet_style` | `veg` 채식 위주 \| `meat` 고기·생선 \| `mixed` 골고루 |
| `lunch_place` | `home` 집밥 \| `out` 회사·외식 \| `store` 편의점 |
| `breakfast` | `skip` 거의 안 먹음 \| `light` 간단히 \| `full` 챙겨 먹음 |
| `exercise_min` | `10` \| `25` \| `45` |
| `free_days` | 0(월)~6(일) 중 **서로 다른 2개** (같은 이름으로 2번 전송) |

- 오류: 선택지 밖 → `400` "선택지 중에서 골라 주세요" / 요일 개수 틀림 → `400` "자유 한 끼 요일은 서로 다른 2개를 골라 주세요".

### 2.3 GET `/c/{token}` — 기록 화면

| 쿼리 | 설명 |
|---|---|
| `day` (선택) | 1~오늘 사이면 그날 계획·기록을 보여 줌(지난 날 수정). 범위 밖이면 오늘 |

- 화면 데이터: 오늘 n(시작일 기준, 1~30으로 자름), 계획 30일, 기록, 연속 기록, 강도 단계, 의심 카드(정체 조건), 주간 요약(7·14·21·28일째 기록 후 ~ 다음 날), 참고 위험도, 30일 끝났으면 리포트 버튼.

### 2.4 POST `/c/{token}/day/{n}` — 하루 기록

| 필드 | 형식 | 규칙 |
|---|---|---|
| `kept` | `1` \| `0` | `1`이면 지켰어요, 그 외 못 지켰어요 |
| `weight_kg` | 실수 또는 빈 값 | 선택, 30~250 |

- `n`은 1~오늘. 미래 날짜 `400` "아직 기록할 수 없는 날이에요." / 몸무게 범위 밖 `400`.
- 같은 날 다시 보내면 덮어씀(`day_logs` 복합 PK).

### 2.5 POST `/c/{token}/week/{w}/level` — 강도 결정

| 필드 | 값 |
|---|---|
| `choice` | `up` 올리기 \| `keep` 이대로 유지 |

- 조건: `w`가 지금 요약 중인 주차 + 그 주가 정체 조건 + 아직 결정 안 함. 아니면 `400` "지금은 강도를 정할 수 없어요…".
- 결과: `week_decisions`에 (w, 단계) 저장, 최대 2단계, 다음 주 첫날부터 계획에 반영.

### 2.6 GET `/c/{token}/report`

- 31일째부터 리포트(체중 변화, 위험도 처음 → 지금). 그 전엔 "N일 남았어요" 화면(200).

### 2.7 GET `/c/{token}/week/{w}.pdf`

- `w` = 1~5 (1–7, 8–14, 15–21, 22–28, 29–30일). 숫자 아님·범위 밖 `404`.
- 받는 시점: `w`주는 `7(w-1)`일째부터(다음 주는 이번 주 마지막 날부터 미리). 이르면 `400`.
- 응답 헤더: `Content-Disposition: inline; filename="watchme-week{w}.pdf"`. 1주차는 "내 결과 요약" 페이지 포함. QR은 `PUBLIC_BASE_URL/c/{token}`.

## 3. 2단계 엔드포인트 (✅ 구현, 2026-11-17 운영 확인)

기준: `app/kakao_routes.py`, `app/routes.py`. 카카오 키가 없으면 카카오 경로는 모두 `404`.

| 메서드 | 경로 | 설명 | 응답 |
|---|---|---|---|
| GET | `/c/{token}/kakao` | 체험에서 카카오 연결 시작. `state` 생성, 서명 쿠키 `wm_kakao`(HttpOnly, SameSite=Lax, 10분)에 `state.token` | 303 → `kauth.kakao.com/oauth/authorize` (scope=`talk_message`) |
| GET | `/auth/kakao` | 시작 화면에서 "카카오로 이어서 하기" | 303 → 카카오 인가 |
| GET | `/auth/kakao/callback` | 쿼리 `code`, `state`, `error`. 토큰 교환 → 회원번호 → 연결 → 환영 메시지 | 303 → `/c/{token}?kakao=linked` 등 |
| POST | `/c/{token}/kakao/notify` | `on=1\|0` 알림 켜기·끄기 | 303 → `/c/{token}` |
| POST | `/c/{token}/kakao/unlink` | 카카오 연결 끊기 + 저장 토큰 삭제 | 303 → `/c/{token}?kakao=unlinked` |
| POST | `/c/{token}/next` | 다음 30일 도전(한 번만) | 303 → `/c/{새 token}/ready` |

### 콜백 결과 (`?kakao=` 안내 문구)

| 값 | 상황 | 안내 |
|---|---|---|
| `linked` | 연결 성공 | 카톡이 연결됐어요 ✅ |
| `cancel` | 동의 화면에서 취소(`error=access_denied`) | 카카오 연결을 취소했어요 |
| `nomsg` | 로그인은 했지만 `talk_message` 미동의 | 메시지 동의가 없어서 알림을 보낼 수 없어요 |
| `taken` | 다른 카카오 계정에 이미 연결된 체험 | 이 체험은 다른 카카오 계정에 연결돼 있어요 |
| `unlinked` | 연결 끊기 완료 | 카카오 연결을 끊었어요. 저장한 정보도 지웠어요. |

| 오류 | 응답 |
|---|---|
| 쿠키 없음·서명 위조·`state` 불일치 | `400` "로그인 요청이 만료됐어요. 다시 시도해 주세요." (DB 변화 없음) |
| `code` 없음 | `400` "로그인 요청이 올바르지 않아요. 다시 시도해 주세요." |
| 이어서 하기인데 계정에 체험 없음 | `404` "카카오에 연결된 체험이 없어요. 새로 시작해 주세요." |
| 연결 안 된 체험에서 알림 켜기·끄기 | `400` "카카오에 연결된 체험이 아니에요." |
| 카카오 5xx·네트워크 오류 | `502` "카카오 연결 중 문제가 생겼어요…" |
| `/next`를 30일 전에 | `400` "30일을 마친 뒤에 시작할 수 있어요." |

### 서버 → 카카오 (외부 API, `app/kakao.py`)

| 용도 | 호출 |
|---|---|
| 토큰 발급·갱신 | `POST https://kauth.kakao.com/oauth/token` |
| 회원번호 | `GET https://kapi.kakao.com/v2/user/me` |
| 나에게 보내기 | `POST https://kapi.kakao.com/v2/api/talk/memo/default/send` (텍스트 템플릿, 200자 이하, 버튼 1개) |
| 연결 끊기 | `POST https://kapi.kakao.com/v1/user/unlink` |

### 정기 발송 (HTTP 아님, cron)

| 시각(KST) | 명령 | 내용 |
|---|---|---|
| 매일 07:30 | `python -m scripts.send morning` | Day 1~30 오늘 계획, Day 31 리포트 안내 |
| 매일 21:00 | `python -m scripts.send evening` | 기록 확인(기록 여부에 따라 문구 다름) |

- 서버 crontab에 2026-11-17 등록. 결과는 `~/send.log`(`2026-11-17 evening sent=1 failed=0`처럼 보낸 게 있을 때만 한 줄).
- "나에게 보내기"는 카톡 '나와의 채팅'으로 들어가 **폰 알림이 울리지 않아요**(2026-11-17 실험). 화면·환영 메시지에 직접 확인하라는 안내를 넣었어요.
