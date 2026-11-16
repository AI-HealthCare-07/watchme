# Watchme 2단계 (카카오 로그인 + 하루 두 번 카톡) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 개인 링크 체험을 카카오 계정에 연결하고, "나에게 보내기"로 매일 아침 7:30 계획·저녁 21:00 기록 확인 메시지를 보내며, 30일 뒤 리포트에서 다음 30일 도전을 시작하게 한다.

**Architecture:** 카카오 HTTP 호출·암호화·서명은 `app/kakao.py` 한 곳(httpx 클라이언트는 모듈 변수라 테스트에서 `httpx.MockTransport`로 교체). 계정·연결·발송 기록 DB 조작은 `app/accounts.py`, 메시지 문장은 `app/messages.py`(순수 함수), 발송 루프는 `app/notify.py` + cron이 부르는 `scripts/send.py`. 웹 경로는 새 `app/kakao_routes.py`(기존 `app/routes.py`의 `_page`/`_error`/리미터 재사용). 새 표 4개만 추가(`create_all`), 기존 표 변경 없음.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2, httpx(운영 의존성으로 이동), cryptography(Fernet, 새 의존성), pytest(TDD).

**Spec:** `docs/superpowers/specs/2026-11-16-watchme-phase2-design.md` (승인됨). 실행자는 이 계획과 spec을 같이 읽는다.

## Global Constraints

- 동의항목은 `talk_message` 하나만 요청. 저장하는 카카오 정보는 회원번호(`id`)와 암호화한 refresh token뿐. 액세스 토큰은 저장하지 않음.
- 체험 토큰을 카카오로 가는 URL·파라미터(`state` 포함)에 넣지 않는다. 체험 토큰은 서명한 쿠키에만.
- 카카오 키(`KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`)나 `TOKEN_KEY`가 없으면 카카오 기능 전체가 꺼지고(버튼·카드 숨김, 카카오 경로 404), 1단계 흐름은 그대로 동작. 기존 152개 테스트는 키 없이 통과해야 한다.
- 메시지: 같은 (계정, 날짜, 종류)는 최대 한 번. 종류 `morning | evening | report | welcome`. 시간 7:30 / 21:00 KST(cron). 실패해도 재시도 없음.
- 텍스트 템플릿 `text`는 200자 이하.
- 링크·redirect_uri는 `PUBLIC_BASE_URL` 기준. redirect_uri = `{PUBLIC_BASE_URL}/auth/kakao/callback`.
- 테스트는 실제 카카오를 부르지 않는다. 실행: `.venv/Scripts/python -m pytest -q`.
- 운영 DB를 지우지 않는다. `.env`, `data/raw/`, 키를 커밋하지 않는다. 키 값은 사용자가 직접 입력하고 실행자는 출력·열람하지 않는다.
- 문구: 친근한 존댓말("~해요"), 혼내지 않기. 외부 스크립트 로드 금지.
- main에서 작업, 배포는 `git push evrd main`. 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. 콜백에 `state` 쿠키 없음·서명 위조·`state` 불일치·`code`와 `error` 둘 다 없음 → 500이 아니라 400 안내 화면, DB 변화 없음. → Task 4 테스트
2. 카카오가 5xx·네트워크 오류를 낼 때(콜백, 발송, 연결 끊기) → 콜백은 502 안내, 발송은 다음 사람으로 계속, 연결 끊기는 로컬 삭제는 진행. → Task 2·4·6·7 테스트
3. 같은 날 cron 두 번 실행 → 두 번째 실행은 0통. → Task 6 테스트
4. 발송 날짜 경계: n = 0(시작 전), 1, 30, 31, 32 / 셋업 안 끝난 체험 / 계정에 체험 두 개(다음 도전) → 가장 최근 체험만, n=31은 아침 리포트만. → Task 6 테스트
5. 같은 체험으로 "다음 30일 도전하기" 두 번 POST, 30일 전에 POST → 두 번째는 같은 새 체험으로 이동(중복 생성 없음), 30일 전은 400. → Task 8 테스트

---

### Task 1: 설정·의존성·암호화·서명

**Files:**
- Create: `app/kakao.py`
- Modify: `pyproject.toml` (dependencies에 `httpx`, `cryptography` 추가, dev의 `httpx` 제거), `compose.yaml` (app environment에 `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`, `TOKEN_KEY`를 `${...}`로 전달), `.env.example` (세 이름과 한 줄 설명, 값 비움. `TOKEN_KEY` 생성 명령은 Task 5의 runbook 참고라고 적기)
- Test: `tests/test_kakao.py`

**Interfaces:**
- Produces (`app/kakao.py`):
  - `enabled() -> bool` — 세 환경변수가 모두 비어 있지 않을 때 True. 호출 때마다 `os.environ`을 읽는다(테스트에서 `monkeypatch.setenv`).
  - `encrypt(plain: str) -> str`, `decrypt(token: str) -> str` — `cryptography.fernet.Fernet(TOKEN_KEY)`.
  - `sign(value: str) -> str`, `unsign(signed: str) -> str | None` — `value + "." + hmac_sha256(key, value) hex`; 키는 `TOKEN_KEY` 바이트. 형식이 틀리거나 서명이 다르면 None(`hmac.compare_digest`).

- [ ] **Step 1: 의존성 설치** — `pyproject.toml` 수정 후 `.venv/Scripts/python -m pip install -e ".[dev]"`. Expected: `cryptography` 설치됨.
- [ ] **Step 2: 실패하는 테스트 작성** (`tests/test_kakao.py`, 모듈 맨 위에 공용 fixture `kakao_env`: `monkeypatch.setenv`로 세 변수를 채움, `TOKEN_KEY`는 `Fernet.generate_key().decode()`)
  - `test_enabled_needs_all_three_vars`: 셋 다 있으면 True, `KAKAO_CLIENT_SECRET`을 지우면 False, 아무것도 없으면 False.
  - `test_encrypt_roundtrip_and_not_plain`: `decrypt(encrypt("rt-123")) == "rt-123"`, `"rt-123" not in encrypt("rt-123")`.
  - `test_sign_roundtrip_and_tamper`: `unsign(sign("abc.tok")) == "abc.tok"`; 마지막 글자를 바꾼 값, `"garbage"`, `""` → None.
- [ ] **Step 3: 실패 확인** — `.venv/Scripts/python -m pytest tests/test_kakao.py -q` → FAIL (모듈 없음).
- [ ] **Step 4: 구현** — 위 Interfaces대로 `app/kakao.py` 작성.
- [ ] **Step 5: 통과 확인** — 같은 명령 PASS, 전체 `pytest -q`도 PASS(152 + 새 테스트).
- [ ] **Step 6: 커밋** — `git add pyproject.toml compose.yaml .env.example app/kakao.py tests/test_kakao.py` → `feat: kakao config, token encryption and cookie signing`

### Task 2: 카카오 HTTP 클라이언트

**Files:**
- Modify: `app/kakao.py`
- Test: `tests/test_kakao.py`

**Interfaces:**
- Consumes: Task 1의 환경변수 읽기.
- Produces (`app/kakao.py`):
  - `http: httpx.Client` — 모듈 변수 `httpx.Client(timeout=10)`. 테스트는 `monkeypatch.setattr(kakao, "http", httpx.Client(transport=httpx.MockTransport(handler)))`.
  - `class KakaoError(Exception)`, `class KakaoAuthError(KakaoError)` — 토큰 무효·동의 없음·연결 끊김(다시 로그인해야 하는 경우).
  - `@dataclass(frozen=True) class Tokens: access_token: str; refresh_token: str | None; scope: frozenset[str]`
  - `redirect_uri() -> str` — `f"{PUBLIC_BASE_URL}/auth/kakao/callback"` (`PUBLIC_BASE_URL`은 `os.environ` 기본값 `http://localhost:8000`, 끝 `/` 제거 — routes.py와 같은 규칙).
  - `authorize_url(state: str) -> str` — `https://kauth.kakao.com/oauth/authorize?client_id=…&redirect_uri=…&response_type=code&state=…&scope=talk_message` (`urllib.parse.urlencode`).
  - `exchange_code(code: str) -> Tokens` — POST `https://kauth.kakao.com/oauth/token` form: `grant_type=authorization_code, client_id, redirect_uri, code, client_secret`.
  - `refresh(refresh_token: str) -> Tokens` — 같은 URL, `grant_type=refresh_token, client_id, refresh_token, client_secret`. 응답에 `refresh_token`이 없으면 `Tokens.refresh_token=None`.
  - `user_id(access_token: str) -> int` — GET `https://kapi.kakao.com/v2/user/me`, `Authorization: Bearer …`, 응답 `id`.
  - `send_memo(access_token: str, text: str, url: str, button: str) -> None` — POST `https://kapi.kakao.com/v2/api/talk/memo/default/send`, form `template_object=json.dumps({"object_type": "text", "text": text, "link": {"web_url": url, "mobile_web_url": url}, "button_title": button}, ensure_ascii=False)`.
  - `unlink(access_token: str) -> None` — POST `https://kapi.kakao.com/v1/user/unlink`.
  - 응답 `scope`(공백 구분 문자열, 없으면 빈 집합) → `frozenset`.
  - 오류 분류(`_check(resp)` 하나로): HTTP 401, 또는 JSON `code ∈ {-401, -402, -101}`, 또는 토큰 엔드포인트의 `error == "invalid_grant"` → `KakaoAuthError`. 그 밖의 4xx/5xx → `KakaoError`. `httpx.HTTPError`(네트워크)는 `KakaoError`로 감싼다.

- [ ] **Step 1: 실패하는 테스트 작성** (MockTransport handler가 받은 요청을 리스트에 모아 검증)
  - `test_authorize_url_has_only_talk_message_scope`: 쿼리 파싱 결과 `scope == ["talk_message"]`, `state == ["s1"]`, `redirect_uri == ["https://evrd.example/auth/kakao/callback"]` (`PUBLIC_BASE_URL` setenv).
  - `test_exchange_code_sends_secret_and_parses_scope`: 요청 본문에 `client_secret`, `code=c1`; 응답 `{"access_token":"a","refresh_token":"r","scope":"talk_message"}` → `Tokens("a","r",frozenset({"talk_message"}))`.
  - `test_refresh_without_new_refresh_token`: 응답 `{"access_token":"a2"}` → `refresh_token is None`, `scope == frozenset()`.
  - `test_send_memo_template`: 본문의 `template_object` JSON이 `object_type == "text"`, `link.mobile_web_url == url`, `button_title == "기록하기"`; 헤더 `Authorization == "Bearer a"`.
  - `test_auth_errors` (parametrize): (401, `{}`), (400, `{"code": -402}`), (400, `{"error": "invalid_grant"}`) → `KakaoAuthError`.
  - `test_other_errors`: 500 응답 → `KakaoError`이고 `KakaoAuthError` 아님; handler가 `httpx.ConnectError` 발생 → `KakaoError`.
- [ ] **Step 2: 실패 확인** — `pytest tests/test_kakao.py -q` FAIL.
- [ ] **Step 3: 구현** — 위 Interfaces대로.
- [ ] **Step 4: 통과 확인** — PASS.
- [ ] **Step 5: 커밋** — `feat: kakao oauth and memo client`

### Task 3: 새 표와 계정 서비스

**Files:**
- Modify: `app/models.py`
- Create: `app/accounts.py`
- Test: `tests/test_accounts.py` (fixture는 `tests/test_service.py`의 `db`와 같은 방식, Task 1의 `kakao_env`를 import해 사용)

**Interfaces:**
- Produces (`app/models.py`, 모두 새 표):
  - `KakaoAccount` (`kakao_accounts`): `kakao_id: BigInteger PK (autoincrement=False)`, `refresh_token_enc: Text | None`, `can_message: bool`, `notify: bool = True`, `created_at`.
  - `TrialOwner` (`trial_owners`): `token: PK, FK trials.token ondelete CASCADE`, `kakao_id: FK kakao_accounts.kakao_id`.
  - `SentMessage` (`sent_messages`): PK (`kakao_id`, `date: date`, `kind: String(8)`).
  - `NextTrial` (`next_trials`): `token: PK, FK trials.token ondelete CASCADE`, `next_token: FK trials.token`. (다음 도전 "한 번만" 보장용, spec 5.3 빌더 몫)
- Produces (`app/accounts.py`):
  - `save_account(db, kakao_id: int, refresh_token: str | None, can_message: bool) -> KakaoAccount` — 없으면 만들고, 있으면 `can_message` 갱신, `refresh_token`이 None이 아니면 암호화해 교체. commit.
  - `owner_of(db, token: str) -> KakaoAccount | None`
  - `link(db, token: str, kakao_id: int) -> bool` — 연결 없으면 만들고 True, 같은 계정이면 True, 다른 계정이면 아무것도 안 바꾸고 False.
  - `has_trials(db, kakao_id: int) -> bool`, `latest_trial(db, kakao_id: int) -> Trial | None` — `Trial.created_at` 가장 늦은 것.
  - `set_notify(db, kakao_id: int, on: bool) -> None`
  - `mark_dead(db, kakao_id: int) -> None` — `can_message=False`, `refresh_token_enc=None`.
  - `delete_account(db, kakao_id: int) -> None` — 그 계정의 `TrialOwner`, `SentMessage`, 계정 행 삭제(직접 delete, SQLite cascade 꺼짐).
  - `claim(db, kakao_id: int, day: date, kind: str) -> bool` — `SentMessage` insert 후 commit; 이미 있으면 False(`IntegrityError` → rollback).

- [ ] **Step 1: 실패하는 테스트 작성**
  - `test_save_account_encrypts_and_keeps_old_token_when_none`: 저장 후 `refresh_token_enc != "r1"`이고 `kakao.decrypt(...) == "r1"`; `save_account(..., None, True)` 다시 → 여전히 `"r1"`.
  - `test_link_rules`: 새 연결 True, 같은 계정 다시 True, 다른 계정 False이고 `owner_of(...).kakao_id`는 처음 계정.
  - `test_latest_trial_by_created_at`: 같은 계정에 체험 둘(두 번째 `created_at`이 더 늦게) → 두 번째. 연결 없으면 None, `has_trials` False.
  - `test_claim_once`: 첫 `claim` True, 같은 인자 두 번째 False, 다른 `kind`는 True.
  - `test_delete_account_removes_links_and_sent`: 삭제 후 `owner_of` None, `SentMessage` 0행, `Trial`은 그대로.
- [ ] **Step 2: 실패 확인** — `pytest tests/test_accounts.py -q` FAIL.
- [ ] **Step 3: 구현** — 위 Interfaces대로.
- [ ] **Step 4: 통과 확인** — 전체 `pytest -q` PASS.
- [ ] **Step 5: 커밋** — `feat: kakao account, trial link and sent-message tables`

### Task 4: 로그인 경로, 환영 메시지, /ready·기록 화면 연결 카드

첫 실험(spec 9장)에 필요한 최소 경로. 끝나면 Task 5에서 배포·실험.

**Files:**
- Create: `app/kakao_routes.py`, `app/messages.py` (이 Task에선 `WELCOME`만)
- Modify: `app/main.py` (`include_router`), `app/routes.py` (`check_page`·`ready_page`에 `kakao` 컨텍스트 추가, `AUTH_PER_IP = RateLimiter(10, 600)`를 `LIMITERS`에 추가), `app/templates/ready.html`, `app/templates/check.html`, `app/templates/landing.html`, `app/static/app.css`(`.kakao .btn`의 비활성 스타일은 활성 버튼용으로 정리)
- Test: `tests/test_kakao_routes.py` (client fixture는 `tests/test_routes.py`의 것을 import, `kakao_env`로 키 설정, `kakao.http`는 MockTransport)

**Interfaces:**
- Consumes: Task 1–3 전부.
- Produces:
  - `app/messages.py`: `WELCOME = "연결됐어요 ✅ 아침 7:30엔 오늘 계획, 저녁 9시엔 기록 확인을 보내 드릴게요."`
  - `app/accounts.py` 추가: `day_number(trial: Trial, today: date) -> int` — `(today - trial.start_date).days + 1` (자르지 않음).
  - `app/kakao_routes.py` 경로 (키 없으면 모두 404):
    - `GET /c/{token}/kakao` — 체험 없으면 404. 리미터 초과 429. `state = secrets.token_urlsafe(16)`, 쿠키 `wm_kakao = sign(f"{state}.{token}")` (HttpOnly, Secure는 `PUBLIC_BASE_URL`이 https일 때, SameSite=Lax, max_age 600) → 303 `authorize_url(state)`.
    - `GET /auth/kakao` — 같은 동작, 쿠키 값 `sign(f"{state}.")`.
    - `GET /auth/kakao/callback?code=&state=&error=` — 쿠키 삭제. 쿠키 없음/`unsign` 실패/`state` 불일치 → 400 "로그인 요청이 만료됐어요. 다시 시도해 주세요." `error`가 있으면: 체험에서 왔으면 303 `/c/{token}?kakao=cancel`, 아니면 400 "카카오 연결을 취소했어요." `code` 없음 → 400. 그다음 `exchange_code` → `user_id`. `KakaoError` → 502 "카카오 연결 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요."
      - 체험에서 왔을 때: 다른 계정에 연결된 체험이면 303 `?kakao=taken`(계정·토큰 저장 안 함). 아니면 `save_account` + `link`; `talk_message`가 scope에 없으면 303 `?kakao=nomsg`. 있으면 체험의 `day_number`가 1~30이고 `claim(db, id, today_kst(), "welcome")`이면 `send_memo(access, WELCOME, f"{PUBLIC_BASE_URL}/c/{token}", "기록 화면 열기")`(실패는 무시하고 `print` 한 줄) → 303 `?kakao=linked`.
      - 시작 화면에서 왔을 때: `has_trials`가 False면 저장하지 않고 404 "카카오에 연결된 체험이 없어요. 새로 시작해 주세요." 아니면 `save_account`(토큰 갱신) → 303 `/c/{latest_trial.token}`.
  - `check_page`·`ready_page` 템플릿 컨텍스트 `kakao`: 키 없으면 `None`, 아니면 `{"account": owner_of(...) or None, "flash": request.query_params.get("kakao")}` (flash는 `linked|cancel|nomsg|taken`만 인정).
- 화면(문구 고정):
  - ready.html: `kakao`가 있고 연결 안 됐으면 노란 카드 `<h2>카톡으로 아침 계획·저녁 체크 받기</h2>` + 버튼 `카카오로 연결` (`/c/{token}/kakao`), 그리고 이때는 `<meta http-equiv="refresh">`를 넣지 않는다(카드를 읽기 전에 넘어가지 않게).
  - check.html (`not finished`일 때만): 연결 안 됨 → 같은 노란 카드(작게). 연결됨 → 한 줄 `💬 카톡 알림 켜짐`(Task 7에서 끄기·끊기 버튼 추가). `can_message`가 False → `카톡 메시지 동의가 없어서 알림을 보낼 수 없어요` + `다시 연결` 링크(`/c/{token}/kakao`). flash: `linked` "카톡이 연결됐어요 ✅", `cancel` "카카오 연결을 취소했어요", `nomsg` "메시지 동의가 없어서 알림을 보낼 수 없어요", `taken` "이 체험은 다른 카카오 계정에 연결돼 있어요".
  - landing.html (`kakao` 활성일 때, `preparing`이 아닐 때): 시트 아래 보조 링크 `이미 하고 있나요? 카카오로 이어서 하기` → `/auth/kakao`. (`landing`에도 `kakao_on=kakao.enabled()` 전달)

- [ ] **Step 1: 실패하는 테스트 작성** (`today`는 실제 `today_kst()`, 체험은 `_start_and_setup`로 생성)
  - `test_kakao_routes_404_without_keys`: 키 없이 `/c/{t}/kakao`, `/auth/kakao`, 콜백 모두 404; 기록 화면·ready에 "카카오로 연결" 없음.
  - `test_start_redirects_to_kakao_without_trial_token`: 303 location이 `kauth.kakao.com`으로 시작, location에 체험 토큰 문자열 없음, `wm_kakao` 쿠키 있음.
  - `test_callback_links_trial_and_sends_welcome`: Mock이 token → `{"access_token":"a","refresh_token":"r","scope":"talk_message"}`, me → `{"id": 42}`, memo → 200. 콜백 후 303 `/c/{t}?kakao=linked`, `owner_of(t).kakao_id == 42`, memo 요청 1번, 본문에 "연결됐어요". 같은 흐름을 한 번 더 → memo 추가 요청 없음(welcome claim).
  - `test_callback_bad_state` (parametrize: 쿠키 없음 / 쿠키 위조 / state 다름) → 400, `KakaoAccount` 0행.
  - `test_callback_cancel_returns_to_trial`: `error=access_denied` → 303 `?kakao=cancel`, 카카오 요청 0번.
  - `test_callback_without_talk_message_scope`: scope `""` → 303 `?kakao=nomsg`, 계정 `can_message False`, memo 요청 없음.
  - `test_callback_trial_owned_by_other_account`: 42로 연결된 체험에 43으로 콜백 → 303 `?kakao=taken`, 43 계정 없음.
  - `test_callback_kakao_down`: token 엔드포인트 500 → 502.
  - `test_login_without_trial_finds_latest`: 42 계정에 체험 연결된 상태에서 `/auth/kakao` → 콜백 → 303 `/c/{t}`. 연결 없는 계정 → 404, 계정 행 생성 안 됨.
  - `test_ready_shows_card_and_no_refresh_when_not_linked`: 키 있음 → "카카오로 연결" 있고 `http-equiv="refresh"` 없음. 키 없음 → refresh 있음(기존 동작).
  - `test_auth_rate_limited`: `/c/{t}/kakao` 11번째 429.
- [ ] **Step 2: 실패 확인** — `pytest tests/test_kakao_routes.py -q` FAIL.
- [ ] **Step 3: 구현** — 위 Interfaces와 화면 문구대로.
- [ ] **Step 4: 통과 확인** — 전체 `pytest -q` PASS(기존 테스트 포함).
- [ ] **Step 5: 커밋** — `feat: kakao login, trial linking and welcome message`

### Task 5: 첫 배포와 실험 (사용자와 함께)

**Files:**
- Modify: `docs/server-runbook.md` (새 12장 "카카오 연동")

- [ ] **Step 1: 사용자에게 콘솔 작업 요청** — spec 9장 1–6 목록을 그대로 전달(Redirect URI `https://evrd.fyi/auth/kakao/callback`, `http://localhost:8000/auth/kakao/callback`; Web 도메인; `talk_message`만 선택 동의; 클라이언트 시크릿 ON). 사용자가 서버 `.env`에 `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`을 직접 넣는다. 실행자는 값을 보지 않는다. **사용자가 "넣었어요"라고 할 때까지 대기.**
- [ ] **Step 2: `TOKEN_KEY` 생성(값 출력 없이)** — `ssh evrd 'cd ~/watchme && grep -q ^TOKEN_KEY= .env || python3 -c "import base64,os;print(\"TOKEN_KEY=\"+base64.urlsafe_b64encode(os.urandom(32)).decode())" >> .env; grep -c ^TOKEN_KEY= .env'` → Expected `1`. (Fernet 키 = 32바이트 urlsafe base64, 호스트 python3 표준 라이브러리로 생성)
- [ ] **Step 3: 배포** — `git push evrd main` → 훅 출력의 healthz `{"ok":true}`. `ssh evrd 'cd ~/watchme && docker compose exec -T db psql -U watchme -c "\dt"'`에 `kakao_accounts`, `trial_owners`, `sent_messages`, `next_trials`가 보인다.
- [ ] **Step 4: 사용자 폰으로 실험** — 사용자가 새 체험을 만들고 /ready에서 "카카오로 연결". 확인할 것: ① 환영 메시지가 '나와의 채팅'에 도착, ② 푸시 알림이 울리는지, ③ 버튼이 기록 화면을 여는지, ④ 실패하면 `docker compose logs app`의 카카오 오류 코드. 결과를 사용자에게 묻고 기록.
- [ ] **Step 5: runbook 12장 작성** — 카카오 콘솔 설정 목록, `.env` 항목 이름(값 없이), `TOKEN_KEY` 생성 명령과 "잃어버리면 저장된 토큰을 못 풀어 사용자가 다시 연결해야 함", 실험 결과(알림 여부 포함). 알림이 안 울렸으면 Task 6의 `morning_text` 첫 줄을 바꾸지 말고 runbook에만 적는다(문구 조정은 사용자 확인 후).
- [ ] **Step 6: 커밋** — `docs: runbook kakao setup and first experiment`

### Task 6: 메시지 문장과 발송 루프

**Files:**
- Modify: `app/messages.py`, `app/accounts.py` (`active_trial`)
- Create: `app/notify.py`, `scripts/send.py`
- Test: `tests/test_messages.py`, `tests/test_notify.py`

**Interfaces:**
- Consumes: `build_plan`, `profile_of`, `get_decisions`, `get_logs`(app.service), `PlanDay`(app.plan), Task 2·3 함수, `day_number`.
- Produces:
  - `app/messages.py`:
    - `LIMIT = 200`, `fit(text: str) -> str` — 각 줄이 32자를 넘으면 31자 + "…", 전체가 200자를 넘으면 199자 + "…".
    - `morning(d: PlanDay, sunday: bool) -> str` — 줄: `Day {d.day} · 오늘 계획` / `🍳 아침 {meals["breakfast"]}` / `🍱 점심 {meals["lunch"]}` / `🍲 저녁 {meals["dinner"]}` / `🚶 {d.exercise}` / (일요일) `⚖️ 오늘은 체중 재는 날이에요`. `fit` 적용. 자유 한 끼 날은 `meals["dinner"]`가 이미 `FREE_DINNER`라 그대로.
    - `evening(n: int, logged: bool, sunday: bool) -> str` — 미기록: `오늘 잘 지키셨나요? 10초면 기록돼요.` (+일요일 ` 체중도 같이 적어 주세요.`), 기록함: `오늘 기록 고마워요. 바꿀 게 있으면 눌러 주세요.`; `n in (7, 14, 21, 28)`이면 줄 추가 `이번 주 요약이 나왔어요. 다음 주 강도도 골라 주세요.`
    - `REPORT = "30일 완주! 리포트가 나왔어요 🎉"`
    - 버튼 이름: 아침 `오늘 계획 보기`, 저녁 미기록 `기록하기` / 기록함 `기록 보기`, 리포트 `리포트 보기`.
  - `app/accounts.py`: `active_trial(db, kakao_id: int, today: date) -> Trial | None` — 계정에 연결된 체험 중 `setup_done`이고 `1 <= day_number <= 31`인 것 중 `created_at` 가장 늦은 것.
  - `app/notify.py`: `send_all(db, kind: Literal["morning", "evening"], today: date) -> tuple[int, int]` (보냄, 실패). 대상 = `notify and can_message and refresh_token_enc`. 계정마다:
    - 체험 `t = active_trial`; 없으면 건너뜀. `n = day_number(t, today)`.
    - morning: `n <= 30` → 종류 `morning`, 링크 `/c/{t.token}`; `n == 31` → 종류 `report`, 링크 `/c/{t.token}/report`. evening: `n <= 30`만, 종류 `evening`, `logged` = 그날(`n`) `DayLog` 있음.
    - `claim(...)`이 False면 건너뜀. 그다음 `refresh(decrypt(...))` → 새 refresh_token이 있으면 `save_account`로 교체 → `send_memo`.
    - `KakaoAuthError` → `mark_dead`, 실패+1. `KakaoError` → 실패+1. 다른 계정은 계속.
    - `sunday = today.weekday() == 6`.
  - `scripts/send.py`: `python -m scripts.send morning|evening` — `kakao.enabled()`가 False면 아무것도 안 하고 종료. 결과를 `f"{today} {kind} sent={s} failed={f}"`로 출력(0/0이면 출력 없음, purge와 같은 습관). 잘못된 인자는 사용법 출력 후 exit 2.

- [ ] **Step 1: 실패하는 테스트 작성**
  - `tests/test_messages.py`: `test_morning_lines`(일요일 아님: 5줄, 첫 줄 `Day 3 · 오늘 계획`, 체중 줄 없음), `test_morning_sunday_weight_line`, `test_evening_variants`(미기록/기록함/n=14 요약 줄/일요일 체중 문구), `test_fit_caps_200`(긴 메뉴 문자열로 만든 PlanDay → `len <= 200`, 줄마다 `<= 32`).
  - `tests/test_notify.py` (MockTransport가 token refresh → `{"access_token":"a"}`, memo → 200; 보낸 memo의 `text`를 모음):
    - `test_morning_day1_and_report_day31` (parametrize n → 기대: 0 → 0통, 1 → morning, 30 → morning, 31 → report(본문에 `완주`, 링크 `/report`), 32 → 0통).
    - `test_evening_skips_day31_and_uses_logged_copy`: n=31 → 0통; n=5 기록 있음 → `기록 고마워요`.
    - `test_run_twice_sends_once`: 같은 날 두 번 → 두 번째 결과 `(0, 0)`, memo 요청 총 1번.
    - `test_latest_trial_only`: 계정에 체험 둘(옛 것 n=31, 나중에 만든 새 것 n=1) → 1통, 본문 첫 줄 `Day 1 · 오늘 계획`. (옛 체험의 리포트 메시지는 새 도전을 만들기 전 31일째 아침에 이미 갔으므로 다시 보내지 않는 게 맞음)
    - `test_auth_error_marks_dead_and_continues`: 계정 A의 refresh가 `invalid_grant`, 계정 B 정상 → `(1, 1)`, A `can_message False`, `refresh_token_enc None`.
    - `test_new_refresh_token_saved`: refresh 응답에 `refresh_token: "r2"` → 저장된 값 decrypt == `"r2"`.
    - `test_notify_off_and_setup_not_done_skipped`: 둘 다 0통.
- [ ] **Step 2: 실패 확인** — `pytest tests/test_messages.py tests/test_notify.py -q` FAIL.
- [ ] **Step 3: 구현** — 위 Interfaces대로.
- [ ] **Step 4: 통과 확인** — 전체 `pytest -q` PASS.
- [ ] **Step 5: 커밋** — `feat: daily morning and evening kakao messages`

### Task 7: 알림 끄기·켜기, 연결 끊기, 일요일 체중 칸

**Files:**
- Modify: `app/kakao_routes.py`, `app/templates/check.html`
- Test: `tests/test_kakao_routes.py`

**Interfaces:**
- Consumes: `set_notify`, `delete_account`, `owner_of`, `refresh`, `unlink`, `decrypt`, `DAY_PER_IP`.
- Produces:
  - `POST /c/{token}/kakao/notify` form `on=1|0` → `set_notify` → 303 `/c/{token}`. 연결 없으면 400. 리미터 `DAY_PER_IP`.
  - `POST /c/{token}/kakao/unlink` → 토큰이 있으면 `refresh` → `unlink` 시도(`KakaoError`는 무시) → `delete_account` → 303 `/c/{token}?kakao=unlinked`. 연결 없으면 그냥 303.
  - check.html 연결 줄: 켜짐 `💬 카톡 알림 켜짐 · [끄기] · [연결 끊기]`, 꺼짐 `🔕 카톡 알림 꺼짐 · [켜기] · [연결 끊기]` (버튼은 각각 작은 POST 폼). flash `unlinked` "카카오 연결을 끊었어요. 저장한 정보도 지웠어요."
  - 일요일(`plan[selected-1].date.weekday() == 6`) 기록 카드의 체중 라벨 앞에 `⚖️ 오늘은 체중 재는 날` 강조(spec 6장 "눈에 띄게", 방식은 라벨 문구 + 기존 강조 클래스).
- [ ] **Step 1: 실패하는 테스트 작성**
  - `test_notify_toggle`: 끄기 → 계정 `notify False`, 기록 화면에 "알림 꺼짐"; 켜기 → True.
  - `test_unlink_deletes_even_if_kakao_fails`: unlink 엔드포인트 500 → 그래도 303 `?kakao=unlinked`, `KakaoAccount` 0행, `TrialOwner` 0행, 기록 화면 200.
  - `test_notify_without_link_400`.
  - `test_sunday_weight_label`: 기록 화면에서 선택한 날이 일요일이면 "체중 재는 날" 있음, 아니면 없음 (`?day=`로 일요일인 날을 고름, `test_routes.py:350`의 요일 계산 방식 참고).
- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 전체 PASS**
- [ ] **Step 5: 커밋** — `feat: kakao notify toggle and unlink`

### Task 8: 다음 30일 도전 + 리포트 카드

**Files:**
- Modify: `app/service.py` (`next_trial`), `app/routes.py` (`POST /c/{token}/next`, `report_page` 컨텍스트), `app/templates/report.html`
- Test: `tests/test_service.py`, `tests/test_routes.py`

**Interfaces:**
- Consumes: `start_trial`, `save_setup`, `get_logs`, `days_left`, `NextTrial`, `owner_of`, `link`.
- Produces:
  - `service.next_trial(db, trial: Trial, today: date, stats: dict | None) -> Trial` — `NextTrial`이 있으면 그 체험을 반환(새로 안 만듦). 없으면 `start_trial(sex, age, height_cm, 마지막 체중 기록 또는 trial.weight_kg, today, stats)`(variant는 `start_trial`이 새로 정함) → `save_setup`으로 답변 5개 복사 → `NextTrial(token, next_token)` 저장. 이전 체험의 `owner_of`가 있으면 새 체험도 `link`.
  - `POST /c/{token}/next` — `START_PER_IP` 리미터, 체험 없음 404, 셋업 안 됨 → 셋업으로, `days_left > 0` → 400 "30일을 마친 뒤에 시작할 수 있어요." → 303 `/c/{new}/ready`.
  - report.html 노란 카드(카카오 키와 무관하게 보임): `<h2>여기서 멈추면 아까워요</h2>`, `<p>지금 체중으로 다음 30일 계획을 바로 만들어 드려요.</p>`, POST 버튼 `다음 30일 도전하기`. 이미 다음 도전이 있으면 버튼 대신 링크 `다음 도전 이어 가기` → `/c/{next}`. 연결된 체험이면 `<p>새 도전도 카톡으로 이어서 알려 드려요.</p>` 추가. 기존 "곧 오픈" 문구·비활성 버튼 삭제.
- [ ] **Step 1: 실패하는 테스트 작성**
  - `tests/test_service.py::test_next_trial_copies_and_uses_last_weight`: 체중 기록 80.0(5일째), 78.5(20일째) → 새 체험 `weight_kg == 78.5`, `start_date == TODAY`, 답변 5개 같음, 다시 부르면 같은 토큰.
  - `test_next_trial_without_weights_uses_start_weight`.
  - `test_next_trial_inherits_kakao_link`: 이전 체험이 42에 연결 → 새 체험 `owner_of(...).kakao_id == 42`.
  - `tests/test_routes.py::test_next_before_30_days_400`, `test_next_twice_same_trial`(두 POST의 location 같음, `Trial` 행 수 +1), `test_report_card_has_next_button`("다음 30일 도전하기" 있음, "곧 오픈" 없음).
- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 전체 PASS**
- [ ] **Step 5: 커밋** — `feat: next 30-day challenge from report`

### Task 9: 보관 삭제 확장 + 개인정보 안내

**Files:**
- Modify: `app/service.py` (`purge_expired`), `app/templates/_macros.html` (`privacy`), `tests/test_routes.py` (`PRIVACY` 상수), `tests/test_service.py`

**Interfaces:**
- Produces:
  - `purge_expired`: 만료 체험의 `TrialOwner`, `NextTrial`(token 또는 next_token이 만료 체험인 행)을 기존 `DayLog` 삭제 옆에서 직접 삭제 → 체험 삭제 → `TrialOwner`가 하나도 없는 계정의 `SentMessage`와 계정 행 삭제 → `SentMessage.date < today - 40일` 삭제. 반환값(삭제한 체험 수)은 그대로.
  - 개인정보 문구: 기존 문장 끝(`보관: 체험 종료 후 90일.`) 뒤에 ` 카카오로 연결하면 카카오 회원번호와 메시지 발송 권한(암호화 보관)을 저장해요. 연결을 끊으면 바로 지워요.`
- [ ] **Step 1: 실패하는 테스트 작성**
  - `test_purge_removes_orphan_kakao_account`: 연결된 유일한 체험이 만료 → 계정 행 없음. 계정에 아직 살아 있는 체험이 있으면 계정 유지.
  - `test_purge_old_sent_messages`: 41일 전 행 삭제, 39일 전 행 유지.
  - `PRIVACY` 상수를 새 문구로 바꿔 기존 `test_routes.py:303` 테스트가 새 문구를 확인.
- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 전체 PASS**
- [ ] **Step 5: 커밋** — `feat: purge kakao data with trials, privacy notice`

### Task 10: 최종 배포 + cron 등록

**Files:**
- Modify: `docs/server-runbook.md` (12장에 발송 cron, 확인 방법 추가)

- [ ] **Step 1: 배포** — `git push evrd main` → healthz OK. `ssh evrd 'cd ~/watchme && docker compose exec -T app python -m scripts.send morning'` → 이미 보냈으면 출력 없음, 아니면 `sent=… failed=0`.
- [ ] **Step 2: cron 등록 (사용자 승인 후)** — 사용자에게 아래 두 줄 추가를 묻고 승인되면 runbook 8장의 방식(파일로 만든 뒤 `crontab /tmp/ct`, 기존 backup·purge·ddns 줄 유지)으로 등록:
  ```
  30 7 * * * cd $HOME/watchme && docker compose exec -T app python -m scripts.send morning >> $HOME/send.log 2>&1
  0 21 * * * cd $HOME/watchme && docker compose exec -T app python -m scripts.send evening >> $HOME/send.log 2>&1
  ```
  확인: `ssh evrd crontab -l`에 기존 줄 + 두 줄.
- [ ] **Step 3: 실사용 확인** — 다음 날 사용자에게 7:30·21:00 메시지 수신과 버튼 동작을 확인받고 `~/send.log`를 본다.
- [ ] **Step 4: runbook 12장 마무리 + 커밋** — 발송 cron 두 줄, `send.log` 보는 법, 다른 기기에서 "카카오로 이어서 하기" 확인 결과. `docs: runbook kakao messages cron`
