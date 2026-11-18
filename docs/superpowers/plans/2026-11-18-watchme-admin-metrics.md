# Watchme 운영 지표 페이지 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 나만 여는 `/admin` 한 화면을 만든다. 맨 위에 카톡 연결자 수를 크게 보여 주고, 그 아래 날짜별 추이·전환·지속률·AI·카톡 발송 결과를 보여 준다. 랜딩 조회수 카운터도 함께 만든다.

**Architecture:**
- 새 표 3개(`landing_views`, `send_runs`, `test_trials`)를 둔다. 서버가 켜질 때 `create_all`이 만든다.
- 집계는 `app/metrics.py`가 맡는다. 행을 가져와 파이썬에서 KST 날짜로 묶는다. 사용자가 적어 단순함을 택했다.
- 인증과 화면은 `app/admin.py` 라우터가 맡는다.

**Tech Stack:** FastAPI, Jinja2, SQLAlchemy (새 라이브러리 없음)

**Spec:** `docs/superpowers/specs/2026-11-18-watchme-admin-metrics-design.md`

## Global Constraints
- `ADMIN_KEY`가 비어 있거나 없으면 `/admin`은 무조건 404다. 빈 키끼리 비교해 통과하는 일이 없어야 한다.
- 키 값은 Claude가 보거나 출력하지 않는다. `.env`는 커밋하지 않는다. `.env.example`에는 빈 줄만 둔다.
- 카운터와 발송 기록에 IP·쿠키 ID·User-Agent·토큰·카카오 회원번호를 저장하지 않는다.
- 관리 화면 응답에는 `Cache-Control: no-store`와 `X-Robots-Tag: noindex`를 붙인다.
- 테스트 제외 기준: `METRICS_SINCE`(KST 날짜, 선택)보다 먼저 만든 체험과 `test_trials`에 있는 체험은 모든 숫자에서 뺀다. 카톡 계정은 남은(실제) 체험을 하나 이상 가진 것만 센다.
- 랜딩 카운터 오류가 랜딩을 깨뜨리면 안 된다.
- 운영 DB의 기존 표는 바꾸지 않는다(새 표만 추가).
- 테스트 명령은 `.venv/Scripts/python -m pytest -q`이다. worktree에서는 `../../../.venv/Scripts/python`.
- 커밋 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.

## Review Focus
1. **`ADMIN_KEY`가 없거나 빈 값일 때 `/admin?key=`:** 404여야 하고 쿠키도 굽지 않아야 한다. → Task 2.
2. **카운터 저장이 실패할 때(표 없음 등):** 랜딩은 200이어야 한다. → Task 1.
3. **틀린 키를 반복할 때:** 404를 돌려주고, 10번을 넘기면 429다(`AUTH_PER_IP`). → Task 2.
4. **관리자 쿠키로 시작한 체험:** 시작 수·연결자·지속률 어디에도 잡히지 않아야 한다. → Task 3.
5. **빈 DB:** 모든 숫자가 0이고, 퍼센트 계산에서 0으로 나누는 오류가 없어야 한다. → Task 3·4.

---

### Task 1: 새 표 + 랜딩 조회 카운터 + 발송 기록

**Files:**
- Modify: `app/models.py` (표 3개)
- Create: `app/metrics.py` (`count_landing`, `record_run`, `is_bot`)
- Modify: `app/routes.py` `landing`(`db` 의존성 추가, 카운터 호출), `scripts/send.py`(실행마다 기록), `app/service.py` `purge_expired`(만료 체험의 `test_trials`도 삭제)
- Test: `tests/test_metrics.py`, `tests/test_routes.py`

**Interfaces:**
- Produces:
  - `class LandingView(Base)`: `__tablename__="landing_views"`, `day: date` PK, `count: int`
  - `class SendRun(Base)`: `"send_runs"`, `day: date` + `kind: String(8)` 복합 PK, `sent: int`, `failed: int`
  - `class TestTrial(Base)`: `"test_trials"`, `token: String(64)` PK. FK 없음. 지우기는 purge가 맡는다.
  - `is_bot(user_agent: str) -> bool`
    - 정규식은 `r"bot|crawl|spider|slurp|scrap|facebookexternalhit|preview|headless|curl|wget|python"`, 대소문자를 무시한다.
    - 빈 문자열도 True.
  - `count_landing(db: Session, user_agent: str, today: date) -> None`
    - 봇이면 아무것도 하지 않는다.
    - 아니면 `UPDATE … SET count = count + 1`을 하고, 바뀐 행이 없으면 INSERT(count = 1)한다.
    - INSERT가 IntegrityError면 rollback 뒤 UPDATE를 한 번 더 한다.
  - `record_run(db: Session, day: date, kind: str, sent: int, failed: int) -> None`: 같은 (day, kind)면 더한다. 방식은 위와 같다.

- [ ] **Step 1: 실패하는 테스트** (`tests/test_metrics.py`, db fixture는 `tests.test_service`에서 가져온다)
  - `test_is_bot`
    - `is_bot("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)") is False`
    - `"kakaotalk-scrap/1.0"`, `"facebookexternalhit/1.1"`, `""`, `"Googlebot/2.1"`은 True.
  - `test_count_landing_adds_per_day`
    - 같은 날 두 번, 다른 날 한 번 → 그날 2, 다른 날 1.
    - 봇 UA 한 번은 변화 없음.
  - `test_record_run_accumulates`
    - `record_run(d,"morning",3,1)`을 두 번 → `sent == 6`, `failed == 2`.
    - `"evening"`은 별도 행.
- `tests/test_routes.py`
  - `test_landing_counts_view_but_not_bots`
    - `client.get("/", headers={"user-agent": "Mozilla/5.0"})` → `landing_views` 오늘 행이 1.
    - `user-agent: kakaotalk-scrap/1.0` → 그대로 1.
  - `test_landing_survives_counter_error`: `monkeypatch.setattr(routes, "count_landing", 터지는 함수)` → `/` 200.
- `test_purge_removes_test_marks`(`tests/test_service.py`): 만료된 체험의 `TestTrial`도 지워진다.

- [ ] **Step 2: 실패 확인**
  - Run: `.venv/Scripts/python -m pytest -q tests/test_metrics.py tests/test_routes.py tests/test_service.py`
  - Expected: FAIL (모듈·모델 없음)
- [ ] **Step 3: 구현**
  - `landing`은 카운터 호출을 `try/except Exception`으로 감싼다. 예외가 나면 `db.rollback()` 후 `log.warning("landing count failed")`만 남긴다. 호출은 `stats is None`(준비 중) 분기보다 앞에 둔다.
  - `scripts/send.py`는 `send_all` 결과를 `record_run(db, today, kind, sent, failed)`로 남긴다. 카카오가 꺼져 있어 일찍 끝나는 경우는 기록하지 않는다.
- [ ] **Step 4: 통과 확인** — 전체 테스트 PASS
- [ ] **Step 5: 커밋** — `feat: landing view counter and send run log`

---

### Task 2: 관리자 들어가기 (`app/admin.py`)

**Files:**
- Create: `app/admin.py` (라우터, `is_admin`)
- Modify: `app/main.py`(라우터 등록), `app/routes.py` `start`(관리자면 `TestTrial` 기록), `.env.example`(`ADMIN_KEY=`, `METRICS_SINCE=` 빈 줄과 설명 주석)
- Test: `tests/test_admin.py`

**Interfaces:**
- Consumes: `TestTrial`(Task 1), 기존 `AUTH_PER_IP`·`client_ip`·`_error`·`_page`·`PUBLIC_BASE_URL`(routes).
- Produces:
  - `COOKIE = "wm_admin"`.
  - `admin_key() -> str`: 요청마다 `os.environ.get("ADMIN_KEY", "").strip()`.
  - `is_admin(request: Request) -> bool`: 키가 비어 있으면 False. 아니면 `hmac.compare_digest(request.cookies.get(COOKIE, ""), sha256(key).hexdigest())`.
  - `GET /admin`. 처리 순서:
    1. 키가 없으면 404 `"페이지를 찾을 수 없어요."`.
    2. `key` 쿼리가 있으면 `AUTH_PER_IP` 검사(넘치면 기존 `_too_many`).
       - 맞으면 303 → `/admin`, 쿠키(값 = 해시, `max_age=180일`, `httponly`, `secure`는 https일 때, `samesite="lax"`).
       - 틀리면 404(같은 문구).
    3. 쿼리가 없을 때 `is_admin`이 아니면 404.
    4. 맞으면 Task 4의 화면을 그린다. 이 Task에서는 `"운영 지표"` 제목만 있는 임시 화면이다.
  - 모든 `/admin` 응답에 `Cache-Control: no-store`, `X-Robots-Tag: noindex`를 붙인다.
  - `start`: 체험을 만든 직후 `is_admin(request)`이면 `db.add(TestTrial(token=trial.token)); db.commit()`.

- [ ] **Step 1: 실패하는 테스트** (`tests/test_routes.py`의 `client` fixture를 쓴다. `monkeypatch.setenv("ADMIN_KEY", "k" * 32)`)
  - `test_admin_off_without_key`: env 없음 → `/admin` 404, `/admin?key=` 404이고 `set-cookie` 없음.
  - `test_admin_blank_key_env_stays_off`: `ADMIN_KEY="  "` → `/admin?key=` 404.
  - `test_admin_login_sets_cookie_and_strips_key`
    - 맞는 키 → 303, location `/admin`, `set-cookie`에 `wm_admin=`이 있고 키 원문은 없음.
    - 이어서 `/admin` → 200, `no-store`, `noindex`.
  - `test_admin_wrong_key_404_then_rate_limited`: 틀린 키 10번 404, 11번째 429.
  - `test_admin_without_cookie_404`: 키 설정 + 쿠키 없음 → 404.
  - `test_admin_started_trial_marked_test`: 로그인한 client로 `/start` → `test_trials`에 그 토큰이 있다. 쿠키를 지우고 시작하면 없다.
- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python -m pytest -q tests/test_admin.py` → FAIL
- [ ] **Step 3: 구현** — 위 순서대로 만든다.
- [ ] **Step 4: 통과 확인** — 전체 테스트 PASS
- [ ] **Step 5: 커밋** — `feat: admin login with ADMIN_KEY cookie`

---

### Task 3: 집계 (`app/metrics.py`)

**Files:**
- Modify: `app/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: Task 1 표, 기존 모델(`Trial`, `DayLog`, `KakaoAccount`, `TrialOwner`, `AiPick`, `NextTrial`), `DAYS`.
- Produces:
  - `kst_date(dt: datetime) -> date`: tzinfo가 없으면 UTC로 보고 KST(+9h) 날짜로 바꾼다.
  - `since_from_env() -> date | None`: `METRICS_SINCE`가 `YYYY-MM-DD`면 date, 비었거나 형식이 틀리면 None.
  - 데이터 클래스 (모두 `@dataclass(frozen=True)`):
    - `KakaoStats(receiving: int, total: int, dead: int, off: int, new_today: int)`
    - `DayRow(day: date, views: int, starts: int, setups: int, links: int, checkers: int)`
    - `Step(name: str, count: int, pct: int | None)`: pct는 앞 단계 대비 반올림 %. 첫 단계이거나 앞 단계가 0이면 None.
    - `Retention(day: int, kept: int, eligible: int)`
    - `SendDay(day: date, kind: str, sent: int, failed: int)`
    - `Metrics(kakao: KakaoStats, daily: list[DayRow], funnel: list[Step], retention: list[Retention], next_count: int, ai: dict[str, int], sends: list[SendDay], since: date | None)`
  - `collect(db: Session, today: date, since: date | None) -> Metrics`

정의(정확히):
- **실제 체험**: `token ∉ test_trials`이고 (since가 None이거나 `kst_date(created_at) >= since`).
- **카톡 계정**: 실제 체험을 하나 이상 가진 계정(`TrialOwner`로 연결).
  - `receiving`: `can_message`이고 `notify`이고 `refresh_token_enc`가 None이 아님.
  - `dead`: `refresh_token_enc`가 None이거나 `can_message`가 아님.
  - `off`: dead가 아니면서 `notify`가 아님.
  - `new_today`: `kst_date(created_at) == today`.
- **daily**: today부터 29일 전까지 30행, 최신이 먼저.
  - `views`: `landing_views` 그날 값.
  - `starts`: 그날 만든 실제 체험 수.
  - `setups`: 그중 설정 완료 수. 설정 시각은 저장하지 않으므로 만든 날 기준.
  - `links`: 그날 만든 카톡 계정 수(위 계정 기준).
  - `checkers`: 그날 날짜에 해당하는 기록(`start_date + day - 1 == 그날`)이 있는 실제 체험 수.
- **funnel**:
  - 이름과 순서: `"랜딩 조회"`(since 이후 `landing_views` 합, since가 None이면 전체) → `"시작"` → `"질문 완료"` → `"카톡 연결"`(TrialOwner가 있는 실제 체험).
- **retention**: N ∈ (1, 7, 14, 30).
  - `eligible`: 설정을 마쳤고 `start_date <= today - (N-1)일`인 실제 체험.
  - `kept`: 그중 `DayLog.day >= N` 기록이 하나라도 있는 것.
- **next_count**: `NextTrial.token`이 실제 체험인 수.
- **ai**: 실제 체험의 `AiPick.status`별 수. 키는 `ok`, `empty`, `failed`, 없으면 0.
- **sends**: `send_runs`에서 `day >= today - 6일`, 날짜 내림차순.

- [ ] **Step 1: 실패하는 테스트** (`tests/test_metrics.py`. 체험은 `start_trial`·`save_setup`·`save_day`, 계정은 `accounts.save_account`·`accounts.link`로 만든다. `created_at`은 직접 바꾼다)
  - `test_collect_empty_db_is_all_zero`
    - KakaoStats 모두 0, daily 30행 모두 0.
    - funnel의 pct는 모두 None, retention의 kept·eligible은 0.
    - ai는 `{"ok":0,"empty":0,"failed":0}`.
  - `test_kakao_stats_split`
    - 계정 4개: 받는 중 / 알림 끔 / 끊김(`mark_dead`) / 테스트 체험에만 연결.
    - → `receiving == 1`, `off == 1`, `dead == 1`, `total == 3`.
  - `test_since_and_test_trials_excluded`
    - since 전날 만든 체험 1개, 테스트 표시 1개, 실제 1개 → funnel "시작" == 1.
  - `test_daily_rows_by_kst_date`
    - `created_at = datetime(2026,11,17,16,0)`(UTC, KST로는 11/18 01:00) → today = 11/18 행의 starts == 1.
  - `test_funnel_pct`: 조회 10, 시작 4, 완료 3, 연결 1 → pct `[None, 40, 75, 33]`.
  - `test_retention`
    - 8일째인 체험 2개: 하나는 day 7·8 기록, 하나는 day 1만.
    - → N=1 `kept 2/2`, N=7 `kept 1/2`, N=14 `eligible 0`.
- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python -m pytest -q tests/test_metrics.py` → FAIL
- [ ] **Step 3: 구현**
  - 표마다 필요한 열만 가져와 파이썬에서 거르고 묶는다.
  - 맨 위에 `# ponytail: 열 때마다 전체 집계. 체험 수천 개를 넘으면 SQL 집계나 일별 스냅샷으로`를 남긴다.
- [ ] **Step 4: 통과 확인** — 전체 테스트 PASS
- [ ] **Step 5: 커밋** — `feat: admin metrics aggregation`

---

### Task 4: 관리 화면 (`admin.html`)

**Files:**
- Create: `app/templates/admin.html`
- Modify: `app/admin.py`(임시 화면 → `collect(db, today_kst(), since_from_env())`), `app/static/app.css`
- Test: `tests/test_admin.py`

**Interfaces:**
- Consumes: `collect`, `Metrics` 등(Task 3), `is_admin`(Task 2).
- Produces: 템플릿 변수 `m: Metrics`, `today: date`.

화면(base.html 상속, 히어로 brand_note는 `"운영 지표"`):
- **히어로**
  - kicker `"💬 지금 카톡 알림 받는 사람"`.
  - h1에 `m.kakao.receiving`을 크게(`명`).
  - sub: `f"연결 {total} · 끊김 {dead} · 알림 끔 {off} · 오늘 새 연결 {new_today}"`.
- **카드 "단계별 전환"**: 단계마다 이름 · 수 · (pct가 있으면 `"{pct}%"`). "랜딩 조회" 옆에 작게 `"중복 포함"`.
- **카드 "최근 30일"**
  - 표 열: 날짜(`m/d`), 조회, 시작, 완료, 연결, 체크.
  - 수치 칸 안에 `<i style="width:{비율}%">` 막대를 둔다. 열마다 30일 중 최댓값 기준이고, 최댓값이 0이면 0%.
  - `.scroll-x` 상자로 감싸 좁은 화면에서 가로로 스크롤되게 한다.
- **카드 "체크 지속률"**
  - `f"{N}일째: {kept}/{eligible}명 ({pct}%)"`. eligible이 0이면 `"아직 없음"`.
  - 그 아래 `f"30일 완주 후 다음 도전: {next_count}명"`.
- **카드 "AI 한 줄 요청"**: `f"반영 {ok} · 뺄 것 없음 {empty} · 실패 {failed}"`.
- **카드 "카톡 발송 (최근 7일)"**: 날짜 · 아침/저녁 · 보냄 · 실패. 실패가 1 이상이면 빨간 글씨. 기록이 없으면 `"기록 없음"`.
- **맨 아래 muted 안내**: `"집계 기준: {since 또는 '처음부터'} · 관리자 브라우저로 시작한 체험은 제외 · 조회수는 중복 포함 · 끝나고 90일 지난 체험은 자동 삭제되어 빠져요."`

- [ ] **Step 1: 실패하는 테스트**
  - `test_admin_page_shows_kakao_count_first`
    - 받는 중 계정 2개를 만들고 로그인 후 `/admin`.
    - `"지금 카톡 알림 받는 사람"`이 `"단계별 전환"`보다 앞에 있고, h1 안에 `2`가 있다.
  - `test_admin_page_empty_db_renders`
    - 빈 DB에서 200.
    - `"아직 없음"`과 `"기록 없음"`이 있다.
    - 30일 표 행이 30개다(`<tr` 수로 세되 머리 행을 뺀다).
  - `test_admin_page_shows_send_failures`: `record_run(today,"morning",5,2)` → `"5"`와 `class="bad"`가 있다.
- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python -m pytest -q tests/test_admin.py` → FAIL
- [ ] **Step 3: 구현** — 위 화면을 만든다. CSS는 기존 `.card`·`.muted`를 쓰고, 새로 `.scroll-x`, `.mtable`, `.mtable i`(막대), `.bad`만 더한다.
- [ ] **Step 4: 확인**
  - 전체 테스트 PASS.
  - 미리보기에 시드 데이터를 넣고 375px 폭과 데스크톱에서 화면을 본다. 넘침이나 겹침이 없어야 한다.
- [ ] **Step 5: 커밋** — `feat: admin metrics page`

---

### Task 5: 문서

**Files:** `docs/server-runbook.md`(16절), spec 상태 줄

- [ ] **Step 1: runbook 16절 작성**
  - `ADMIN_KEY` 넣는 법: 사용자가 직접 서버 `.env`에 넣고 `docker compose up -d`로 다시 띄운다. 길고 무작위인 값을 쓴다.
  - 즐겨찾기 방법: `https://evrd.fyi/admin?key=…`로 한 번 들어간 뒤 `/admin`을 즐겨찾기한다.
  - `METRICS_SINCE`의 뜻.
  - 새 표 3개는 자동 생성된다는 것.
  - `send_runs`가 cron 실행마다 쌓인다는 것.
  - spec 상태 줄을 "구현 완료(브랜치)"로 바꾼다.
- [ ] **Step 2: 커밋**
  - `docs: admin metrics runbook`.
  - 제출물(requirements·api·wireframes·README)은 배포 뒤 `docs/deliverables`만 담아 따로 커밋한다.
