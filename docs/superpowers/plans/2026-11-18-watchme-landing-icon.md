# 랜딩 스토리형 개편 + 대표 아이콘 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 랜딩(`/`)을 5장면 스토리형 전환 화면으로 바꾸고, "맥박 W" 아이콘으로 탭·홈 화면·카톡 미리보기를 채운다.

**Architecture:** 서버가 장면 5개를 모두 HTML로 그린다(JS 없으면 세로로 쌓임). 새 `story.js`가 `.story`에 `js` 클래스를 붙여 한 장면씩 보이게 하고 진행 막대·자동 넘김을 맡는다. 막대 차오름·달력·카톡 말풍선 움직임은 CSS 애니메이션(`.scene.cur` 일 때만)이라 JS는 장면 전환만 한다. 아이콘 PNG는 Pillow 스크립트로 한 번 만들어 커밋한다.

**Tech Stack:** FastAPI + Jinja2, 바닐라 JS/CSS, Pillow(설치됨, 스크립트에서만).

**Spec:** `docs/superpowers/specs/2026-11-18-watchme-landing-icon-design.md`
**시안(참고, git 밖):** `.superpowers/brainstorm/3469-1794975385/content/story-v3.html` — 장면 문구·CSS 값의 출처.

## Global Constraints

- 색·글꼴 유지: `--brand #0ca678`, 그라데이션 `#20c997 → #0ca678 → #099268`, Pretendard. 새 라이브러리 없음.
- 아이콘 도형(100×100 기준): 둥근 사각형 rx 24, 흰 선 `12,52 25,52 32,32 42,70 50,40 58,70 68,32 75,52 88,52`, 굵기 7, 끝·꺾임 둥글게.
- 장면 시간 3000 / 3600 / 3800 / 4600ms, 마지막 장면은 자동으로 넘기지 않음. 카카오 꺼짐이면 카톡 장면을 빼고 시간 배열도 그에 맞춤.
- 카톡 장면 문구는 실제 발송과 같아야 함: 버튼 `messages.BUTTON["morning"]`·`["evening"]`, 저녁 문장 `messages.evening(1, False, False)`, 아침 문장 `messages.morning(...)`. 답장 말풍선 없음.
- "카카오로 이어서 하기"는 CTA 밑 작은 글씨 링크(`/auth/kakao`), `kakao_on`일 때만.
- `prefers-reduced-motion: reduce`이면 자동 넘김 끔(기존 CSS가 애니메이션·전환은 이미 끔).
- 문구는 해요체. `.env`·`data/raw/` 커밋 금지. 테스트: `.venv/Scripts/python -m pytest -q`.

## Review Focus

- JS가 꺼진 폰: 장면 5개가 모두 보이고 CTA로 시작할 수 있어야 함 → Task 2 `test_landing_story_works_without_js`.
- 카카오 키가 없는 서버: 카톡 장면·"이어서 하기"가 없어야 함 → Task 2 `test_landing_without_kakao_has_four_scenes`.
- 통계 준비 중(`preparing`): 스토리 대신 지금의 "준비 중" 카드, 시작 버튼 없음 → Task 2 `test_landing_preparing_keeps_simple_card`.
- 배포 직후 폰에 예전 CSS/JS가 남는 경우: 주소의 `?v=`가 파일 내용에 따라 바뀌어야 함 → Task 1 `test_static_urls_carry_content_version`.
- 카톡 링크 미리보기: `og:image`가 절대 주소여야 카카오가 가져감 → Task 1 `test_head_has_icons_and_link_preview`.

---

### Task 1: 아이콘 파일 + 머리 태그 + 정적 파일 버전

**Files:**
- Create: `scripts/make_icons.py`, `app/static/icons/favicon.svg`, `app/static/icons/apple-touch-icon.png`(180), `app/static/icons/icon-192.png`, `app/static/icons/icon-512.png`, `app/static/icons/og.png`(1200×630), `app/static/manifest.webmanifest`
- Modify: `app/routes.py:34-37` (템플릿 전역), `app/templates/base.html` (head·brand), `app/static/app.css` (`.brand` 아이콘)
- Test: `tests/test_routes.py`

**Interfaces:**
- Produces: 템플릿 전역 `ASSET_V: str`(정적 파일 내용 해시 앞 8자), `PUBLIC_BASE_URL: str`. base.html의 `<script src="/static/flow.js?v={{ ASSET_V }}">` 패턴 — Task 2의 `story.js`도 같은 방식.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_routes.py`)

```python
def test_head_has_icons_and_link_preview(client):
    page = client.get("/").text
    assert '<link rel="icon" href="/static/icons/favicon.svg" type="image/svg+xml">' in page
    assert '<link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png">' in page
    assert '<link rel="manifest" href="/static/manifest.webmanifest">' in page
    assert '<meta property="og:image" content="http://localhost:8000/static/icons/og.png">' in page
    assert '<meta property="og:title" content="Watchme · 30일 생활습관 챌린지">' in page
    for path in ("icons/favicon.svg", "icons/apple-touch-icon.png", "icons/icon-192.png", "icons/icon-512.png", "icons/og.png", "manifest.webmanifest"):
        assert client.get(f"/static/{path}").status_code == 200

def test_static_urls_carry_content_version(client):
    from app.routes import ASSET_V
    page = client.get("/").text
    assert len(ASSET_V) == 8 and f"/static/app.css?v={ASSET_V}" in page and f"/static/flow.js?v={ASSET_V}" in page

def test_brand_shows_icon_on_every_page(client):
    assert '<img class="brand-icon" src="/static/icons/favicon.svg"' in client.get("/start").text
```

- [ ] **Step 2: 실행해서 실패 확인** — `.venv/Scripts/python -m pytest -q tests/test_routes.py -k "icons or version or brand_shows"` → 3 failed.

- [ ] **Step 3: `scripts/make_icons.py` 작성·실행**
  - `favicon.svg`: Global Constraints의 도형, 배경은 위 3색 대각선 그라데이션.
  - PNG는 Pillow로 4배 크기에 그린 뒤 `LANCZOS`로 줄임(계단 현상 방지). 그라데이션은 대각선 보간, 선은 `ImageDraw.line(..., joint="curve")` + 끝점에 원.
  - `apple-touch-icon.png`(180)는 iOS가 모서리를 깎으므로 **둥근 모서리 없이** 꽉 채움. 192·512는 둥근 사각형(투명 바탕).
  - `og.png`: 1200×630 그라데이션 바탕, 가운데에 흰 둥근 사각형 아이콘(초록 선, 260px) + 좌우로 이어지는 흰 반투명 맥박 가로선. 글자 없음(카톡이 제목·설명을 글자로 따로 보여 줌).
  - 실행: `.venv/Scripts/python scripts/make_icons.py` → 파일 6개 생성, 결과물을 눈으로 확인(Read로 PNG 열기).

- [ ] **Step 4: 템플릿 전역과 head**
  - `app/routes.py`: `ASSET_V = hashlib.sha256(b"".join(p.read_bytes() for p in sorted(STATIC.glob("*.[cj]s*")))).hexdigest()[:8]` 수준(대상: `app.css`, `flow.js`, Task 2 이후 `story.js`). `templates.env.globals["ASSET_V"]`, `["PUBLIC_BASE_URL"]` 등록.
  - `base.html` head: icon / apple-touch-icon / manifest 링크, `og:type website`, `og:site_name Watchme`, `og:title "Watchme · 30일 생활습관 챌린지"`, `og:description "내 혈압·혈당 위험을 또래 평균과 비교하고, 30일 맞춤 계획을 받아 보세요."`, `og:image {{ PUBLIC_BASE_URL }}/static/icons/og.png`. CSS·JS 주소에 `?v={{ ASSET_V }}`.
  - brand: `<a class="brand" href="/"><span class="brand-name"><img class="brand-icon" src="/static/icons/favicon.svg" width="20" height="20" alt="">WATCHME</span> <small>…</small></a>`, CSS `.brand-name { display:flex; align-items:center; gap:7px; } .brand-icon { border-radius:5px; box-shadow:0 0 0 1.5px rgba(255,255,255,.5); }`.
  - `manifest.webmanifest`: `name`·`short_name` "Watchme", `start_url "/"`, `display "standalone"`, `theme_color`·`background_color "#0ca678"`, icons 192·512(png). StaticFiles가 `.webmanifest` 타입을 모르면 `application/manifest+json`이 아니어도 동작하므로 그대로 둠.

- [ ] **Step 5: 통과 확인** — 같은 명령 → 3 passed, 이어서 전체 `.venv/Scripts/python -m pytest -q` → 모두 통과.

- [ ] **Step 6: 커밋** — `git add scripts/make_icons.py app/static/icons app/static/manifest.webmanifest app/routes.py app/templates/base.html app/static/app.css tests/test_routes.py` → `feat: pulse-w icon, link preview tags, versioned static urls`

---

### Task 2: 스토리형 랜딩

**Files:**
- Create: `app/static/story.js`
- Modify: `app/templates/base.html` (`{% block page %}` 감싸기), `app/templates/landing.html` (전면 교체), `app/routes.py:76-78` (landing 문맥), `app/static/app.css` (`.story` 블록, `.feat`·`.kresume` 삭제), `app/routes.py` `ASSET_V` 대상에 story.js 포함
- Test: `tests/test_routes.py`, `tests/test_kakao_routes.py`

**Interfaces:**
- Consumes: Task 1의 `ASSET_V`, brand 마크업.
- Produces: landing 문맥 `example`, `preparing`, `kakao_on`, `demo_morning: str`, `demo_evening: str`, `buttons: dict` (= `messages.BUTTON`).

- [ ] **Step 1: 실패하는 테스트 작성**

```python
def test_landing_story_works_without_js(client):
    page = client.get("/").text
    assert page.count('<section class="scene') == 4  # kakao 꺼진 테스트 기본
    assert 'class="story"' in page and '<script src="/static/story.js?v=' in page
    assert "지금 내 위험도부터" in page and 'href="/start"' in page
    assert ' hidden' not in page.split('class="story"', 1)[1].split("</main>", 1)[0]  # 숨김은 JS가 붙이는 .js 클래스로만

def test_landing_without_kakao_has_four_scenes(client):
    page = client.get("/").text
    assert "나와의 채팅" not in page and "카카오로 이어서 하기" not in page
    assert page.count('class="seg"') == 4

def test_landing_preparing_keeps_simple_card(client):
    app.dependency_overrides[get_stats] = lambda: None  # 기존 test_without_stats_shows_preparing_not_500 방식
    page = client.get("/").text
    assert "준비 중" in page and 'class="story"' not in page and 'href="/start"' not in page
```

`tests/test_kakao_routes.py`에 추가:

```python
def test_landing_kakao_scene_matches_real_messages(client, kakao_env):
    from app import messages
    page = client.get("/").text
    assert page.count('<section class="scene') == 5 and "나와의 채팅" in page
    assert messages.BUTTON["morning"] in page and messages.BUTTON["evening"] in page
    assert messages.evening(1, False, False) in page
    assert page.index("내 위험도 확인하기") < page.index('href="/auth/kakao"')  # CTA 밑 작은 링크
```

기존 테스트 손볼 곳: `test_landing_and_result_are_compact`의 landing 단언은 `PRIVACY in page`와 `🔒 이름·연락처는 받지 않아요` 존재로 유지(접기 마크업이 바뀌면 그에 맞춤). `test_average_is_labeled_by_age_and_sex`의 "40대 남성 평균"은 장면 2의 `risk_rows(example)`로 계속 통과해야 함.

- [ ] **Step 2: 실행해서 실패 확인** — `.venv/Scripts/python -m pytest -q -k "landing"` → 새 테스트들 failed.

- [ ] **Step 3: base.html** — `{% block topbar %}`부터 cta `div`까지를 `{% block page %}…{% endblock %}`로 감쌈(내용 변경 없음). `story.js`는 landing.html이 직접 넣음.

- [ ] **Step 4: landing 문맥 (`app/routes.py`)** — `demo_morning`은 예시 인물의 실제 계획에서 만든다: `Profile(choose_variant(example), "mixed", "out", "light", 25, (5, 6))`로 `build_plan(..., today_kst(), "landing-demo")`의 12일째(`[11]`)를 `messages.morning(day, False)`에 넣음. `demo_evening = messages.evening(1, False, False)`, `buttons = messages.BUTTON`. `preparing`이면 계산하지 않음.

- [ ] **Step 5: landing.html** — `{% block page %}{% if preparing %}{{ super() }}{% else %}…{% endif %}{% endblock %}`(준비 중일 때는 기존 hero/sheet 블록 = 지금의 준비 중 카드). 스토리 구조:
  - `<main class="story">` 안에 `.segs`(장면 수만큼 `<button type="button" class="seg" aria-label="N번째 장면"><i><b></b></i></button>`), brand 줄, 장면 `<section class="scene">` (초록 장면은 `scene g`), `.tap` 영역, 고정 `.story-cta`(`<a class="btn btn-dark" href="/start">내 위험도 확인하기</a>` + `kakao_on`이면 `<small>이미 시작했나요? <a href="/auth/kakao">카카오로 이어서 하기</a></small>`).
  - 장면 문구는 시안 story-v3.html 그대로(spec "랜딩 장면" 1~5). 장면 2는 `risk_rows(example)` + "예시 · 45세 남성". 장면 3 달력은 Jinja `for d in range(1, 31)`로 `<i style="--d:{{ d }}" class="{{ 'free' if d % 7 == 6 }}">{{ d }}</i>`. 장면 4는 `{% if kakao_on %}`, 말풍선 2개 텍스트 `demo_morning`/`demo_evening`(`white-space:pre-line`), 버튼 `buttons.morning`/`buttons.evening`. 장면 5 아래 `<details class="card fold"><summary>🔒 이름·연락처는 받지 않아요</summary>{{ privacy() }}</details>`.
  - `<script src="/static/story.js?v={{ ASSET_V }}" defer></script>`.

- [ ] **Step 6: CSS (`app.css` 끝에 `/* 랜딩 스토리 */` 블록)** — 기본(JS 없음): 장면이 세로로 쌓이는 일반 카드 흐름. `.story.js`일 때만 화면 높이(`100svh`, 폭 최대 480px 가운데) 고정 + 장면 `position:absolute` 겹침 + `.cur`/`.prev` 전환(시안의 opacity·translateX 값). 막대 차오름·달력(`animation-delay: calc(var(--d) * 45ms + .4s)`)·말풍선 등장은 `.story.js .scene.cur …` 선택자에 키프레임으로 → 장면이 바뀌어 다시 `.cur`가 될 때마다 다시 재생. 초록 장면일 때 `.story.lt` 로 brand·진행 막대·작은 글씨를 흰색. `.feat`, `.kresume` 규칙 삭제(쓰는 곳이 없어짐).

- [ ] **Step 7: `story.js`** — `flow.js`처럼 IIFE, `.story` 없으면 종료. `js` 클래스 추가 → `go(n)`(cur/prev 토글, `lt` 토글, 지난 칸 100%·이후 0), `.seg` 클릭 → `go(i)`, `.tap` 클릭 → 다음. 자동 넘김은 `setInterval(50ms)`로 현재 칸 너비 갱신, 시간 배열 `[3000, 3600, 3800, 4600]`을 장면 수-1개만큼 사용, 마지막 장면은 멈춤. `matchMedia("(prefers-reduced-motion: reduce)").matches`면 자동 넘김 없음. 탭이 숨겨지면(`document.hidden`) 시간 멈춤.

- [ ] **Step 8: 통과 확인** — `.venv/Scripts/python -m pytest -q` → 전부 통과.

- [ ] **Step 9: 화면 확인** — 로컬 서버(임시 `.claude/launch.json`, scratchpad sqlite)를 띄우고 브라우저 375×812에서: 자동 넘김 5장면, 진행 막대 클릭 이동, 화면 탭 다음, 마지막 장면 멈춤, CTA → `/start`. 데스크톱 폭에서 가운데 정렬. 확인 뒤 launch.json 삭제.

- [ ] **Step 10: 커밋** — `feat: story landing with tappable progress`

---

### Task 3: 문서 갱신

**Files:** `docs/server-runbook.md`(새 장: 아이콘·미리보기, 카카오 콘솔 아이콘 등록과 공유 디버거 캐시 지우기는 사용자 몫), `docs/deliverables/`(wireframes 랜딩 그림, requirements에 랜딩·아이콘 항목, README 마지막 갱신·기준 커밋), spec 상태 줄.

- [ ] **Step 1:** 문서 고치고 deliverables 커밋은 그 폴더만: `docs: deliverables landing story and icon`, 나머지 `docs: runbook landing and icon`.
