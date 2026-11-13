# Watchme 1단계 (무료 체험 + 집 서버) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 성별·나이·키·몸무게 입력 → 참고 위험도 → 30일 식단·운동 + 1년 시나리오 PDF → 폰 체크 페이지 → 30일 뒤 변화 리포트를, 사용자의 집 노트북 서버에서 운영한다.

**Architecture:** FastAPI 서버 렌더링 앱 1개 + PostgreSQL, Docker Compose. 도메인 로직(위험도, 계획, 시나리오, 리포트)은 순수 함수로 분리해 DB 없이 테스트. 사용자는 로그인 없이 랜덤 토큰 링크(`/c/<token>`)로 식별. **서버 먼저**: 골격을 노트북에 올려 Funnel로 공개한 뒤 기능마다 배포.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2, PostgreSQL 16 (테스트는 SQLite), reportlab + NanumGothic, qrcode, pypdf(테스트), pytest, httpx, Docker Compose, Ubuntu Server LTS, Tailscale.

**Spec:** `docs/superpowers/specs/2026-11-13-watchme-design.md` (2단계 카카오 연동은 별도 계획)

## Global Constraints

- 표현은 "참고 위험도"·"시나리오"만. "진단/예측/치료" 금지. 모든 결과 화면과 PDF에 면책 문구: `본 결과는 공개 통계 기반의 참고용이며 의학적 진단이 아닙니다.`
- 입력: 성별(M/F)·나이(18–100)·키(120–220cm)·몸무게(30–250kg). 이름·연락처 수집 안 함. 시작 폼에 `수집 항목: 성별·나이·키·몸무게·일일 체크 기록 / 보관: 체험 종료 후 90일` 안내.
- 토큰: `secrets.token_urlsafe(16)` 이상. 접근 로그에 `/c/<token>` 경로를 남기지 않음(uvicorn access log 끔, 앱 로그는 토큰 앞 4자만).
- 체험 기간 = 시작일 포함 30일. **모든 날짜는 `zoneinfo.ZoneInfo("Asia/Seoul")` 기준** `app/clock.py::today_kst() -> date` 한 곳에서만 구함.
- 공개 주소는 `PUBLIC_BASE_URL` 환경변수(예: `https://<machine>.<tailnet>.ts.net`). 요청의 `base_url`로 링크·QR을 만들지 않음.
- 한국 평균 통계는 `app/data/korea_stats.json`에 `source`·`year`와 함께 저장, 코드에 하드코딩 금지.
- 요청 제한: `POST /start` IP당 10분에 5회 + 전체 하루 500회, `POST /c/{token}/day/{n}` IP당 1분에 30회. 초과 시 429와 한국어 안내.
- 모바일 우선, 한국어 UI. 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- SSH/관리 접속은 Tailscale 내부망만. 인터넷에는 HTTPS만 노출. Docker 포트는 `127.0.0.1`에만 바인딩(Docker는 ufw를 우회함).

## Review Focus

1. 비정상 입력(범위 밖 숫자, 문자열, 성별 누락): 500이 아니라 400 + 폼 오류 문구. → Task 3·7 테스트
2. 없는/형식이 틀린 토큰: 404, 스택트레이스 노출 없음. → Task 7 테스트
3. 같은 날 두 번 체크(더블 탭): 행 1개, 마지막 값. → Task 6·7 테스트
4. 기록이 거의/전혀 없는 30일 리포트: 예외 없이 "기록 부족" 안내. → Task 8 테스트
5. 한국 시간 자정~오전 9시 사이 체크가 전날로 기록되지 않음. → Task 6 테스트(`today` 주입 + `today_kst` 단위 테스트)

---

### Task 0: 프로젝트 골격

**Files:** Create `pyproject.toml`, `.gitignore`, `app/__init__.py`, `app/main.py`, `app/clock.py`, `tests/test_health.py`, `tests/test_clock.py`

**Interfaces:**
- Produces: `app.main.app`; `GET /healthz → {"ok": true}`; `app.clock.today_kst(now: datetime | None = None) -> date`

- [ ] **Step 1:** `git init`, `.gitignore`(`.venv`, `__pycache__`, `.env`, `*.pdf`, `*.sqlite`)
- [ ] **Step 2:** 테스트: `/healthz` 200·`{"ok": True}`; `today_kst(datetime(2026,11,13,16,0,tzinfo=UTC)) == date(2026,11,14)`(UTC 16시 = KST 다음날 1시)
- [ ] **Step 3:** `pytest -v` → FAIL
- [ ] **Step 4:** 구현. `pyproject.toml` 의존성: fastapi, uvicorn[standard], jinja2, python-multipart, sqlalchemy, psycopg[binary], reportlab, qrcode[pil]; dev: pytest, httpx, pypdf
- [ ] **Step 5:** `pytest -v` → PASS, 커밋 `chore: project skeleton`

### Task 1: Docker Compose

**Files:** Create `Dockerfile`, `compose.yaml`, `.env.example`

- [ ] **Step 1:** `Dockerfile`(python:3.12-slim, `TZ=Asia/Seoul`, `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log`)
- [ ] **Step 2:** `compose.yaml`: `app`(`DATABASE_URL`, `PUBLIC_BASE_URL` 주입, `ports: ["127.0.0.1:8000:8000"]`, `restart: unless-stopped`), `db`(postgres:16, 볼륨 `pgdata`, 포트 공개 안 함, `restart: unless-stopped`). `.env.example`에 두 변수와 `POSTGRES_PASSWORD`
- [ ] **Step 3:** `docker compose up -d --build` → `curl localhost:8000/healthz` 가 `{"ok":true}`
- [ ] **Step 4:** 비공개 GitHub 저장소 생성(사용자 확인 후) 및 push, 커밋 `chore: compose`

### Task 2: 집 서버 구축 + 골격 공개 (운영 작업)

**Files:** Create `docs/server-runbook.md` (실제 수행한 명령과 결과를 단계마다 기록), `scripts/backup.sh`

- [ ] **Step 1 (BIOS):** 충전 제한(60–80%) 지원 시 켜기, 정전 후 자동 켜짐(AC power recovery) 켜기. 미지원이면 runbook에 기록
- [ ] **Step 2:** Ubuntu Server LTS 설치(디스크 전체 초기화, OpenSSH 포함). `/etc/systemd/logind.conf`에 `HandleLidSwitch=ignore`, `HandleLidSwitchExternalPower=ignore`. 검증: 덮개 닫고 5분 뒤 응답
- [ ] **Step 3:** 개발 PC 공개키 등록 → `PasswordAuthentication no`. `ufw default deny incoming`. 검증: 비밀번호 로그인 거부
- [ ] **Step 4:** Tailscale 설치·로그인, `ufw allow in on tailscale0`. 검증: Tailscale 주소로 SSH 성공, 같은 공유기 LAN IP로는 실패
- [ ] **Step 5:** Docker 설치, `git clone` → `.env` 작성 → `docker compose up -d --build`. 검증: 서버에서 `curl localhost:8000/healthz`
- [ ] **Step 6:** Tailscale 관리 콘솔에서 HTTPS 인증서 활성화, ACL `nodeAttrs`에 `funnel` 허용. `tailscale funnel --bg 8000`. `.env`의 `PUBLIC_BASE_URL`을 그 주소로. 검증: 폰(LTE)에서 `https://<machine>.<tailnet>.ts.net/healthz`
- [ ] **Step 7:** 클라이언트 IP 확인: 임시로 `/healthz`에서 `X-Forwarded-For`와 `request.client.host`를 로그 출력해 Funnel 경유 시 실제 폰 IP가 어느 쪽에 오는지 runbook에 기록하고 임시 코드 제거. (Task 7 요청 제한이 이 결과를 씀)
- [ ] **Step 8:** `scripts/backup.sh`: `docker compose exec -T db pg_dump` → `~/backups/YYYYMMDD.sql.gz`, 7일 초과분 삭제, 이어서 Tailscale로 개발 PC에 복사(`tailscale file cp` 또는 `rsync`). cron 매일 04:00. 검증: 개발 PC에 파일 도착 + 빈 DB에 복원해 행 수 일치
- [ ] **Step 9 (btw):** AI 에이전트는 별도 디렉터리·별도 compose 프로젝트(별도 네트워크). 검증: 에이전트 컨테이너에서 `nc -z db 5432` 실패
- [ ] **Step 10:** 배포 절차를 runbook에 고정: `git pull && docker compose up -d --build`. 이후 모든 Task는 끝날 때 이 절차로 배포하고 폰으로 확인

### Task 3: 참고 위험도

**Files:** Create `app/risk.py`, `app/data/korea_stats.json`, `tests/test_risk.py`

**Interfaces:**
- Produces:
  - `@dataclass Assessment: sex, age, height_cm, weight_kg, bmi: float, bmi_band: str, avg_height_cm: float, avg_weight_kg: float, hypertension_vs_avg: float, diabetes_vs_avg: float, hypertension_level: str, diabetes_level: str`
  - `assess(sex: str, age: int, height_cm: float, weight_kg: float, stats: dict | None = None) -> Assessment`
  - `class InvalidInput(ValueError)` (메시지는 한국어, 폼에 그대로 표시)
  - `bmi_band ∈ {"저체중","정상","과체중","비만"}` (<18.5, <23, <25, ≥25, 대한비만학회), level ∈ `{"낮음","보통","높음"}` (vs_avg <0.8, <1.3, 그 이상)
  - `*_vs_avg` = 같은 성별·연령대·BMI 구간 유병률 ÷ 같은 성별·연령대 전체 유병률

- [ ] **Step 1 (데이터 확인, 코드 전):** 국민건강통계(질병관리청)·KOSIS에서 성별×연령대(10세 단위)×비만 여부별 고혈압·당뇨 유병률과 성별×연령대 평균 키·체중을 찾는다. 교차표가 없으면 (a) 국민건강영양조사 원자료로 직접 계산 또는 (b) 성별·연령대 전체 유병률 + 문헌 BMI 구간 상대위험도로 대체. **어느 쪽인지와 출처를 사용자에게 보고하고 확정 후 진행**
- [ ] **Step 2:** 테스트(주입 `stats`): 해당 구간 유병률이 전체와 같으면 `vs_avg == 1.0`; 비만 구간 유병률 0.4 / 전체 0.2 → `2.0`, level `"높음"`; BMI 경계값 23.0은 `"과체중"`; 범위 밖 각 필드·`sex="X"` → `InvalidInput`
- [ ] **Step 3:** FAIL 확인 → 구현 → PASS
- [ ] **Step 4:** `korea_stats.json`에 확정한 실제 수치·출처 입력, 실제 데이터로 `assess("M",40,175,80)`이 예외 없이 그럴듯한 값인지 확인. 커밋 `feat: risk assessment`, 배포

### Task 4: 30일 계획 + 1년 시나리오

**Files:** Create `app/plan.py`, `app/data/templates.json`, `tests/test_plan.py`

**Interfaces:**
- Consumes: `Assessment`, `assess`
- Produces:
  - `@dataclass DayPlan: day: int, meals: dict[str, str], exercise: str` (`meals` 키 `breakfast|lunch|dinner`)
  - `choose_variant(a: Assessment) -> str` (templates.json 최상위 키 중 하나)
  - `make_plan(variant: str) -> list[DayPlan]` (길이 30, day 1..30)
  - `@dataclass ScenarioPoint: month: int, weight_kg: float, assessment: Assessment`
  - `scenario(a: Assessment) -> list[ScenarioPoint]` (month 0·3·6·12)

- [ ] **Step 1:** 테스트: 모든 variant에서 `len == 30`, day 1..30, 끼니 비어있지 않음; `bmi_band=="비만"`과 `"정상"`의 `choose_variant` 결과가 다름; 같은 variant는 항상 같은 계획(결정적); 시나리오: BMI ≥ 23이면 12개월 체중 = 시작 × 0.94(소수 1자리), 3개월 = 시작 × 0.985, BMI < 23이면 모든 시점 체중 동일; 나이는 시점에 따라 바꾸지 않음
- [ ] **Step 2:** FAIL → 구현(variant 4종: 정상·과체중·비만·고위험(level 높음 1개 이상), 7일 패턴을 30일로 반복, 저염·저당 식단, 걷기·스트레칭 위주) → PASS
- [ ] **Step 3:** 커밋 `feat: plan and scenario`, 배포

### Task 5: PDF

**Files:** Create `app/pdf.py`, `app/fonts/NanumGothic.ttf`(OFL, 라이선스 파일 동봉), `tests/test_pdf.py`

**Interfaces:**
- Consumes: `Assessment`, `list[DayPlan]`, `list[ScenarioPoint]`
- Produces: `render_pdf(a: Assessment, plan: list[DayPlan], points: list[ScenarioPoint], check_url: str) -> bytes`

- [ ] **Step 1:** 테스트: `b"%PDF"`로 시작; pypdf로 추출한 텍스트에 면책 문구, `"시나리오"`, 첫날 아침 메뉴 문자열이 포함; 페이지 수 ≥ 3
- [ ] **Step 2:** FAIL → 구현(1쪽: 평균 비교·참고 위험도·1년 시나리오 표·면책·`check_url` QR, 이후 주차별 표) → PASS
- [ ] **Step 3:** 생성 PDF를 폰과 PC에서 열어 한글·표 육안 확인, 커밋 `feat: pdf`

### Task 6: 저장소 (체험·기록)

**Files:** Create `app/db.py`, `app/models.py`, `app/service.py`, `tests/test_service.py`

**Interfaces:**
- Produces:
  - `Trial(token PK, created_at, start_date: date, sex, age, height_cm, weight_kg, plan_variant: str)`
  - `DayLog(token FK, day 1..30, kept: bool, weight_kg: float | None)`, `UniqueConstraint(token, day)`
  - `start_trial(db, sex, age, height_cm, weight_kg, today: date) -> Trial` (검증은 `assess` 재사용, `plan_variant = choose_variant(...)`)
  - `get_trial(db, token) -> Trial | None`
  - `save_day(db, token, day, kept, weight_kg) -> None` (덮어쓰기, day 범위 밖·체중 30–250 밖이면 `ValueError`)
  - `get_logs(db, token) -> list[DayLog]` (day 오름차순)
  - `current_day(trial, today) -> int` (1..30)
  - `get_db()` FastAPI 의존성. `DATABASE_URL` 기본 `sqlite:///./watchme.sqlite`, 시작 시 `create_all`

- [ ] **Step 1:** 테스트(SQLite 메모리): 토큰 길이 ≥ 22·두 번 호출 시 다름; `save_day` 두 번 → 행 1개·마지막 값; day 0/31 → `ValueError`; `current_day`는 시작 당일 1, +29일 30, +100일 30; 없는 토큰 → `None`; `plan_variant`가 저장됨
- [ ] **Step 2:** FAIL → 구현(덮어쓰기는 select 후 update/insert, DB 방언 무관) → PASS, 커밋 `feat: storage`, 배포(Postgres에서 테이블 생성 확인)

### Task 7: 웹 화면 + 요청 제한

**Files:** Create `app/routes.py`, `app/ratelimit.py`, `app/templates/{base,start,check,error}.html`, `tests/test_routes.py`, `tests/test_ratelimit.py`; Modify `app/main.py`

**Interfaces:**
- Consumes: Task 3–6, `today_kst`, `PUBLIC_BASE_URL`
- Produces:
  - `GET /` 시작 폼(수집 안내 포함), `POST /start` → 303 `/c/{token}`, `GET /c/{token}`, `POST /c/{token}/day/{n}`(form `kept`, `weight_kg` 선택) → 303, `GET /c/{token}/plan.pdf`
  - `class RateLimiter(limit: int, window_s: int)`, `.hit(key: str, now: float) -> bool` (허용이면 True)
  - `client_ip(request) -> str` (Task 2 Step 7 결과대로 `X-Forwarded-For` 또는 `request.client.host`)

- [ ] **Step 1:** 요청 제한 테스트: limit 5/600s에서 같은 키 5회 True, 6번째 False, 600초 뒤 다시 True; 다른 키는 독립
- [ ] **Step 2:** 라우트 테스트: 유효 POST → 303, Location이 `/c/`로 시작; 그 페이지 200 + 면책 문구; 나이 0·문자열 → 400 + 오류 문구; `/c/없는토큰` → 404; 같은 날 두 번 POST → 행 1개; `n=31` → 400; `plan.pdf`는 `%PDF` 시작이고 QR 대상(`check_url`)이 `PUBLIC_BASE_URL`로 시작(`render_pdf`를 monkeypatch해 인자 확인); `/start` 6회 연속 → 6번째 429
- [ ] **Step 3:** FAIL → 구현 → PASS. 리미터는 프로세스 메모리 dict (`# ponytail: 단일 uvicorn 프로세스 전제, 워커를 늘리면 Redis 등 공유 저장소로`). 전체 하루 500회 상한은 같은 클래스에 키 `"global"`로
- [ ] **Step 4:** 체크 화면: 30일 격자, 오늘 칸 강조, 칸 탭 → 지킴 토글 + 체중 입력. JS 최소. 커밋 `feat: web flow + rate limit`, 배포 후 폰에서 시작→체크→PDF(QR로 다시 진입) 완주

### Task 8: 30일 리포트 + 데모 데이터

**Files:** Create `app/report.py`, `app/templates/report.html`, `scripts/seed_demo.py`, `tests/test_report.py`; Modify `app/routes.py`

**Interfaces:**
- Consumes: `Trial`, `get_logs`, `assess`
- Produces:
  - `@dataclass Report: kept_days, logged_days, start_weight, end_weight: float | None, weight_change: float | None, before: Assessment, after: Assessment | None, enough_data: bool` (`enough_data` = 체중 기록 ≥ 2 그리고 체크 ≥ 10일)
  - `build_report(trial, logs, today) -> Report | None` (30일 미경과면 None)
  - `GET /c/{token}/report`: 미경과 → "N일 남았어요"(200), 경과 → 리포트 + "2달째부터 카카오톡으로 이어가기" 안내(결제 없음)
  - `python -m scripts.seed_demo` → 시작일이 31일 전이고 랜덤 기록 30일이 채워진 체험을 만들고 URL 출력

- [ ] **Step 1:** 테스트: 체중 기록 4건·지킴 20일 → `weight_change == end - start`, `kept_days == 20`; 기록 0건 → `enough_data False`, `after None`, 예외 없음; 29일차 → None; 마지막 체중으로 `after.bmi != before.bmi`; 라우트 미경과/경과 각 200; 시드 스크립트 실행 후 해당 리포트 200
- [ ] **Step 2:** FAIL → 구현(`end_weight` = 가장 늦은 날의 체중) → PASS
- [ ] **Step 3:** 커밋 `feat: report + demo seed`, 배포 후 서버에서 시드 실행 → 폰으로 리포트 확인

### Task 9: evrd.fyi 연결 (학습 과제)

**Files:** Create `ddns/update.py`, `tests/test_ddns.py`, `Caddyfile`; Modify `compose.yaml`, `docs/server-runbook.md`

**Interfaces:**
- Produces: `ddns.update.run(current_ip: str, get_record: Callable[[], str], set_record: Callable[[str], None]) -> bool`

- [ ] **Step 1:** 테스트: 같은 IP → `set_record` 미호출·False; 다르면 1회 호출·True. FAIL → 구현(Porkbun API 호출은 `__main__`에서만 연결, API 키는 `.env`) → PASS
- [ ] **Step 2:** KT 공유기 80/443 포트포워딩 → LTE 폰에서 `curl -I http://<공인IP>`. **막히면 멈추고 runbook에 기록 후 Cloudflare 이전 여부를 사용자와 상의**
- [ ] **Step 3:** 열리면 compose에 `caddy`(80/443 공개, `evrd.fyi` → `app:8000`) 추가, Porkbun에서 Vercel 레코드 제거 후 A 레코드를 공인 IP로, cron 5분마다 DDNS. Funnel 경유 시와 클라이언트 IP 출처가 달라지므로 `client_ip` 갱신. `PUBLIC_BASE_URL=https://evrd.fyi`
- [ ] **Step 4:** 검증: LTE 폰에서 `https://evrd.fyi/healthz`, 체험 완주. 커밋 `feat: evrd.fyi via caddy + ddns`

---

## 남은 한계
- PDF QR에 개인 토큰이 들어 있어 PDF를 공유하면 기록 접근 가능. 2단계 카카오 로그인에서 계정 연결로 해소.
