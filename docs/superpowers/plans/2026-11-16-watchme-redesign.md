# Watchme 리디자인 + 맞춤 계획 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 1단계 서비스를 초록 디자인 체계·토스식 입력·맞춤 30일 계획(자유 한 끼, 팁, 정체 감지, 물어보고 강도 올리기)·주간 PDF로 개편한다.

**Architecture:** 지금 구조(FastAPI + Jinja2 서버 렌더링 + PostgreSQL) 유지. 디자인은 `app/static/app.css` + 바닐라 JS(`app/static/flow.js`, 자바스크립트 없어도 동작). 계획은 `app/data/`의 꼬리표 붙은 콘텐츠 풀에서 토큰 고정 시드로 조합(`app/plan.py`), 기록 기반 판단은 `app/progress.py`.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2, reportlab, pytest(TDD), Pretendard(OFL, 자체 호스팅).

**Spec:** `docs/superpowers/specs/2026-11-16-watchme-redesign-design.md` (승인됨). 시안: `.superpowers/brainstorm/933-1794808013/content/{hybrid-color,input-flow,check-report}.html`

## Global Constraints

- 색: 브랜드 `#0ca678`, 진한 `#087f5b`, 옅은 `#e6fcf5`, 글자 `#191f28`, 보조 `#6b7684`, 바탕 `#f7f8fa`. 위험 높음/증가 `#e03131`, 낮음/개선 `#1c7ed6` (브랜드와 무관하게 고정). 다크 모드 유지.
- 글꼴 Pretendard, 자체 호스팅. **외부(제3자) 요청 금지**: CDN·폰트 서비스·분석 스크립트 없음.
- 레이아웃: 위 초록 영역 + 아래 둥근 흰 시트 + 아래 고정 둥근 주 버튼, 폭 최대 480px, 폰 우선. 아이콘은 이모지.
- 전환: 질문 사이 좌우 슬라이드(앞으로 → 왼쪽, 뒤로 → 오른쪽), 페이지 사이 `@view-transition { navigation: auto; }`, `prefers-reduced-motion: reduce`면 애니메이션 없음.
- 자바스크립트가 꺼져도 시작·입력·맞춤 질문·기록이 동작(모든 문항이 한 폼에 보임).
- 문구: 친근한 존댓말("~해요"). 효과 장담·끼니 거르기 지시 금지(어떤 단계에도 "거르기/굶기" 없음). 면책 문구 `본 결과는 공개 통계 기반의 참고용이며 의학적 진단이 아닙니다.` 모든 화면·PDF에 유지.
- 위험도 숫자는 `app/risk.py`의 `assess`/`vs_text`/`scenario` 계산값만. 결과 화면 3개월 문구는 `scenario()`의 3개월 값.
- 그대로 유지: 입력 범위(나이 18–100, 키 120–220, 몸무게 30–250), 토큰 방식, 요청 제한(`/start` IP당 10분 5회 + 전체 하루 500회, 기록 저장 IP당 1분 30회), `today_kst`, 90일 보관 삭제, 접근 로그 없음.
- 맞춤 답변 값(저장·폼 값): `diet_style ∈ {veg, meat, mixed}`, `lunch_place ∈ {home, out, store}`, `breakfast ∈ {skip, light, full}`, `exercise_min ∈ {10, 25, 45}`, `free_days` = 서로 다른 요일 정확히 2개(0=월 … 6=일).
- 주차: 1주 1–7일, 2주 8–14, 3주 15–21, 4주 22–28, 5주 29–30. 강도 단계 최대 2. 자유 한 끼는 고른 요일의 저녁.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. 맞춤 질문 POST 값 조작(모르는 선택지, 요일 1개·3개·중복, 숫자 아님): 500이 아니라 400 + 폼 오류. → Task 7 테스트
2. 맞춤 질문을 안 끝낸 체험으로 기록·리포트·PDF 접근: 500이 아니라 맞춤 질문으로 이동(303). → Task 7 테스트
3. 주간 PDF 주차 조작(0, 6, 아직 안 온 주): 404/400 안내 화면, 스택트레이스 없음. → Task 9 테스트
4. 강도 질문 POST 반복·다른 주차·요약이 안 뜬 날: 두 번째부터 400, 단계가 두 번 오르지 않음. → Task 8 테스트
5. 체중을 한 번도 안 적은 사용자: 주간 요약·정체 판단·리포트가 예외 없이 "체중 기록 없음"으로 처리. → Task 4·8 테스트

---

### Task 1: 데이터 — 맞춤 답변·강도 결정 저장

**Files:**
- Modify: `app/models.py`, `app/service.py`, `scripts/seed_demo.py`
- Test: `tests/test_service.py`

**Interfaces:**
- Consumes: 기존 `Trial`, `DayLog`, `start_trial`, `purge_expired`
- Produces:
  - `Trial`에 nullable 컬럼 `diet_style: str|None`, `lunch_place: str|None`, `breakfast: str|None`, `exercise_min: int|None`, `free_days: str|None`(정렬된 `"a,b"`), 프로퍼티 `Trial.setup_done -> bool`
  - 새 모델 `WeekDecision(token FK→trials ondelete CASCADE, week: int, level: int)`, PK `(token, week)`
  - `class InvalidSetup(ValueError)`
  - `save_setup(db, token: str, diet_style: str, lunch_place: str, breakfast: str, exercise_min: int, free_days: list[int]) -> None` (값 검증 실패 시 `InvalidSetup`, 한국어 메시지)
  - `get_decisions(db, token: str) -> dict[int, int]` (week → level)
  - `decide_level(db, token: str, week: int, up: bool) -> int` (새 단계 반환. `week ∉ 1..4` 또는 이미 결정한 주면 `ValueError`. 새 단계 = 직전 결정 단계(없으면 0)에서 up이면 +1, 최대 2)
  - `purge_expired`가 `WeekDecision`도 지움
  - `seed(db, today, stats)`가 맞춤 답변(`mixed, out, light, 25, [2, 5]`)도 저장

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_service.py`)
  - `test_save_setup_stores_answers`: 저장 후 `get_trial(...).setup_done is True`, `free_days == "2,5"` (입력 `[5, 2]`)
  - `test_save_setup_rejects_bad_values` (parametrize): `diet_style="x"`, `lunch_place=""`, `breakfast="none"`, `exercise_min=30`, `free_days=[1]`, `[1,2,3]`, `[3,3]`, `[7,1]` → `InvalidSetup`
  - `test_new_trial_setup_not_done`: `start_trial` 직후 `setup_done is False`
  - `test_decide_level_up_keep_and_cap`: week1 up → 1, week2 keep → 1, week3 up → 2, week4 up → 2; `get_decisions == {1:1, 2:1, 3:2, 4:2}`
  - `test_decide_level_twice_rejected`: 같은 주 두 번 → `ValueError`; `week=0`, `week=5` → `ValueError`
  - 기존 `test_purge_deletes_trials_90_days_after_end_with_logs`에 `decide_level(db, old_t, 1, True)` 추가 후 purge가 예외 없이 1 반환
- [ ] **Step 2: 실행해 실패 확인** — Run: `.venv/Scripts/python -m pytest tests/test_service.py -q` / Expected: FAIL (`save_setup` 없음)
- [ ] **Step 3: 구현** — 위 인터페이스대로. 검증 값은 Global Constraints의 집합. `purge_expired`는 `WeekDecision` → `DayLog` → `Trial` 순서로 삭제. `seed_demo.seed`에 `save_setup` 호출 추가.
- [ ] **Step 4: 실행해 통과 확인** — Run: `.venv/Scripts/python -m pytest -q` / Expected: 기존 포함 전부 PASS (라우트 테스트는 아직 setup 무관)
- [ ] **Step 5: 커밋** — `feat: store setup answers and weekly level decisions`

---

### Task 2: 콘텐츠 — 메뉴·운동·팁 풀

**Files:**
- Create: `app/data/meals.json`, `app/data/exercises.json`, `app/data/tips.json`
- (기존 `app/data/templates.json`은 Task 9에서 지움 — 그때까지 기존 `make_plan`이 씀)
- Test: `tests/test_content.py`

**Interfaces:**
- Produces (JSON 형식):
  - `meals.json`: `{"note": str, "breakfast": [{"text", "habit": "skip|light|full", "styles": [...]}], "lunch": [{"text", "place": "home|out|store", "styles": [...]}], "dinner": [{"text", "styles": [...]}]}`; `styles` ⊆ `{veg, meat, mixed}`
  - `exercises.json`: `{"<variant>": {"label": str, "activities": [str with "{m}"], "rest": str}}`, variant 4개(`normal, overweight, obese, high_risk`). 라벨은 지금 값 유지(유지·습관 만들기 / 가벼운 감량 / 무릎 보호 감량 / 안전 우선 저강도).
  - `tips.json`: `[{"text": str, "tags": [...]}]`, tags ⊆ `{general, store, out, skip_breakfast, free_meal}`

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_content.py`, 콘텐츠의 최소 기준을 고정)
  - `test_breakfast_pool_sizes`: 모든 (habit, style) 조합에 항목 ≥ 7
  - `test_lunch_pool_sizes`: 모든 (place, style) 조합에 항목 ≥ 10
  - `test_dinner_pool_sizes`: 모든 style에 항목 ≥ 12
  - `test_exercise_activities`: variant마다 activities ≥ 6, 전부 `"{m}"` 포함; `obese` activities에 `"계단"`, `"등산"`, `"달리기"`, `"줄넘기"`, `"점프"` 없음
  - `test_tips`: 전체 ≥ 40, `free_meal` ≥ 8, `store`·`out`·`skip_breakfast` 각 ≥ 5, 문장 중복 없음
  - `test_no_meal_skipping_or_promises`: 모든 문장에 `"거르"`, `"굶"`, `"단식"`, `"완치"`, `"치료"`, `"보장"` 없음
- [ ] **Step 2: 실행해 실패 확인** — Run: `.venv/Scripts/python -m pytest tests/test_content.py -q` / Expected: FAIL (파일 없음)
- [ ] **Step 3: 콘텐츠 작성** — 저염·저당 일반 가이드 수준, 짧은 한 줄. `veg`는 고기·생선 없음(달걀·유제품·두부 가능). `out`은 메뉴 고르는 요령("국밥이면 국물 반만, 밥 반 공기"), `store`는 편의점 조합("삶은 달걀 2 + 샐러드 + 두유"). `skip` 아침은 아주 간단(두유 한 팩, 바나나 등). `rest`는 "휴식 + 스트레칭 10분" 류. 기존 `templates.json`의 메뉴·운동은 재사용 가능.
- [ ] **Step 4: 실행해 통과 확인** — Expected: PASS
- [ ] **Step 5: 커밋** — `feat: tagged meal, exercise and tip content`

---

### Task 3: 맞춤 계획 생성

**Files:**
- Modify: `app/plan.py`, `pyproject.toml`(package-data 확인)
- Test: `tests/test_plan.py`

**Interfaces:**
- Consumes: Task 2 JSON, `Assessment`, `assess`
- Produces:
  - `@dataclass(frozen=True) Profile: variant: str, diet_style: str, lunch_place: str, breakfast: str, exercise_min: int, free_days: tuple[int, int]`
  - `@dataclass(frozen=True) PlanDay: day: int, date: date, meals: dict[str, str] (breakfast/lunch/dinner), exercise: str, free_meal: bool, notes: tuple[str, ...], tip: str, level: int`
  - `WEEKS = 5`, `MAX_LEVEL = 2`, `week_of(day: int) -> int`, `week_days(week: int) -> range`, `level_on(decisions: dict[int, int], day: int) -> int`
  - `build_plan(profile: Profile, start_date: date, seed: str, decisions: dict[int, int] | None = None) -> list[PlanDay]` (30개)
  - 기존 `DayPlan`·`make_plan(variant)`은 그대로 두어 지금 라우트·PDF가 계속 동작(새 날짜 계획 dataclass 이름은 `PlanDay`로 구분). Task 9에서 기존 것 삭제.
  - 유지: `choose_variant`, `variant_label`(이제 `exercises.json`의 label, 값 동일), `scenario`, `DAYS`, `VARIANTS`
- 규칙 (스펙 5.3·5.5에서 고정한 값):
  - `level_on`: 결정된 주 w의 단계는 `7*w+1`일부터 적용. day에 적용되는 단계 = `7*w+1 <= day`인 결정 중 가장 큰 w의 단계, 없으면 0.
  - 메뉴: 끼니별로 프로필에 맞는 풀(아침: habit·style, 점심: place·style, 저녁: style)을 `random.Random(f"{seed}:{끼니}")`로 섞어 순서대로 순환. 연달아 같은 문장 금지(순환 경계 포함).
  - 자유 한 끼: `date.weekday() ∈ free_days`인 날 저녁 = `"자유 한 끼 🎉 먹고 싶은 걸 즐겨요"`, `free_meal=True`, notes에 `"국물·소스는 남기기"`, `"단 음료 대신 물"`. 그 날의 단계가 2면 `free_days` 중 큰 값(뒤쪽 요일)만 자유 한 끼.
  - 저녁 notes(자유 한 끼가 아닌 날, `high_risk` 제외): 단계 1 → `"밥은 1/3 공기"`, `"저녁 7시 이후엔 먹지 않기"`; 단계 2 → `"밥·면 없이 단백질·채소만"`, `"저녁 7시 이후엔 먹지 않기"`.
  - 운동: `day % 7 == 0`이면 variant의 `rest`. 그 외 분 = `max(10, ceil(exercise_min * ramp / 5) * 5) + 10 * level`, `ramp = {1: 0.6, 2: 0.75, 3: 0.9}.get(week, 1.0)`. 상한: `high_risk`는 한 번 30분 — 분이 30을 넘으면 `{m}`에 `min(30, ceil(분/2/5)*5)`를 넣고 문장 끝에 `" ×2회"`; 그 외 variant는 70분 상한. 활동 문장은 variant activities를 `seed:exercise`로 섞어 순환하며 `{m}`에 분을 넣음.
  - 팁: 30일 동안 중복 없음. 자유 한 끼 날은 `free_meal` 팁. 그 외 `day % 3 == 1`인 날은 프로필 관련 팁(`store`/`out`/`skip_breakfast` 중 해당하는 것)이 남아 있으면 그것, 아니면 `general`. 각 묶음은 `seed:tips`로 섞음.

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_plan.py`에 추가)
  - 공통 픽스처: `P = Profile("normal", "veg", "store", "skip", 25, (2, 5))`, `START = date(2026, 11, 16)`(월). 아래 테스트는 모두 `build_plan` 대상(기존 `make_plan` 테스트는 Task 9까지 유지)
  - `test_plan_is_30_days_and_deterministic`: 길이 30, 같은 seed 두 번 → 같은 결과, 다른 seed → 다른 결과
  - `test_free_meal_on_chosen_weekdays_dinner`: `free_meal`인 날의 요일이 전부 {2, 5}(수·토), 그날 dinner가 자유 한 끼 문구, 30일 중 8~9일
  - `test_no_same_meal_two_days_in_a_row`: 끼니별로 `plan[i].meals[k] != plan[i+1].meals[k]` (자유 한 끼 제외)
  - `test_veg_profile_gets_only_veg_menus`: 모든 아침·점심·저녁 문장이 `meals.json`에서 `veg`를 포함한 항목
  - `test_exercise_ramps_by_week`: `exercise_min=25`일 때 1주 평일 15분, 2주 20분, 3주 25분(22.5→올림), 4주 25분, 7·14·21·28일은 rest
  - `test_high_risk_session_cap`: `Profile("high_risk", ..., 45, ...)` + decisions `{1: 1}` → 2주 평일 운동 문장이 `"25분"`과 `"×2회"` 포함(35+10=45 → 25분씩 2회), 어떤 문장에도 30 초과 분 없음
  - `test_level_on_and_notes`: `level_on({1: 1, 2: 2}, 7) == 0`, `(…, 8) == 1`, `(…, 15) == 2`; decisions `{1: 1}`이면 8일 이후 자유 한 끼가 아닌 저녁 notes에 `"밥은 1/3 공기"`; `{1:1, 2:2}`이면 15일 이후 자유 한 끼 요일이 5(토)만
  - `test_high_risk_has_no_meal_notes`: high_risk + decisions `{1: 2}` → 모든 notes에 `"밥"` 없음
  - `test_tips_unique_and_relevant`: 30개 팁 중복 없음, 자유 한 끼 날 팁은 `free_meal` 태그, `store`·`skip_breakfast` 태그 팁이 1개 이상 포함
  - `test_week_helpers`: `week_of(7)==1`, `week_of(8)==2`, `week_of(29)==5`, `list(week_days(5)) == [29, 30]`
  - 기존 `choose_variant`·`scenario` 테스트 유지
- [ ] **Step 2: 실행해 실패 확인** — Expected: FAIL (`Profile` 없음)
- [ ] **Step 3: 구현** — 위 규칙대로 `build_plan` 추가(기존 `make_plan`은 손대지 않음).
- [ ] **Step 4: 실행해 통과 확인** — Run: `.venv/Scripts/python -m pytest -q` / Expected: 전부 PASS
- [ ] **Step 5: 커밋** — `feat: personalized 30-day plan generator`

---

### Task 4: 기록 기반 판단 — 연속 기록·정체·주간 요약

**Files:**
- Create: `app/progress.py`
- Modify: `app/report.py` (`Report.plateau: bool` 추가)
- Test: `tests/test_progress.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: `DayLog`, `Trial`, `assess`, `week_days`, `week_of`, `MAX_LEVEL`, `level_on`
- Produces:
  - `streak(logs: list[DayLog], today: int) -> int` — 오늘이 기록돼 있으면 오늘부터, 아니면 어제부터 거꾸로 연속 `kept` 일수
  - `plateau(logs: list[DayLog], end_day: int) -> bool` — `end_day-6..end_day` 중 kept ≥ 6 그리고 체중 기록 ≥ 2 그리고 마지막 체중 ≥ 첫 체중
  - `summary_week(today: int, logs: list[DayLog]) -> int | None` — `today ∈ {7,14,21,28}`이고 그날 기록이 있으면 `today // 7`; `today ∈ {8,15,22,29}`면 `(today-1) // 7`; 그 외 None
  - `@dataclass(frozen=True) WeekSummary: week: int, kept: int, days: int, weight_start: float|None, weight_end: float|None, weight_change: float|None, before: Assessment|None, after: Assessment|None, plateau: bool`
  - `week_summary(trial: Trial, logs: list[DayLog], week: int, stats: dict|None = None) -> WeekSummary` — 그 주 체중 기록 첫·마지막으로 before/after(`assess`), 체중 1개 이하면 change·before·after None
  - `can_level_up(logs, week: int, decisions: dict[int, int]) -> bool` — `plateau(logs, 7*week)` 그리고 week 미결정 그리고 직전 단계 < `MAX_LEVEL`
  - `Report.plateau` = `plateau(logs, 30)`

- [ ] **Step 1: 실패하는 테스트 작성**
  - `test_streak`: 1~5 kept, 오늘=6 미기록 → 5; 6 기록 kept → 6; 4가 못 지킴 → 오늘 6 기준 2
  - `test_plateau_true_and_false`: 7일 중 6일 kept, 체중 80.0(1일)·80.2(7일) → True; 79.8로 끝나면 False; 5일 kept → False; 체중 1개 → False; 체중 0개 → False
  - `test_summary_week_window`: (7, 7일 기록 있음) → 1; (7, 없음) → None; (8, 아무거나) → 1; (9, …) → None; (29, …) → 4; (30, …) → None
  - `test_week_summary_without_weights`: 체중 기록 없는 주 → `weight_change is None and before is None`, kept 정확
  - `test_week_summary_with_weights`: 80.0 → 79.0이면 `weight_change == -1.0`, `after.diabetes_vs_avg < before.diabetes_vs_avg` (STATS)
  - `test_can_level_up`: 정체 주 + 미결정 → True; 이미 결정 → False; 직전 단계 2 → False
  - `tests/test_report.py`: 마지막 주 정체 로그면 `Report.plateau is True`, 기록 없음이면 False
- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python -m pytest tests/test_progress.py tests/test_report.py -q` / Expected: FAIL
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** — Expected: PASS
- [ ] **Step 5: 커밋** — `feat: streak, plateau and weekly summary`

---

### Task 5: 디자인 체계 — 정적 파일·글꼴·기본 레이아웃

**Files:**
- Create: `app/static/app.css`, `app/static/flow.js`(빈 골격, Task 6에서 채움), `app/static/fonts/` (Pretendard woff2 Regular/SemiBold/Bold/ExtraBold, `OFL.txt`)
- Modify: `app/main.py` (`/static` 마운트), `app/templates/base.html`, `app/templates/_macros.html`, `app/templates/error.html`, `pyproject.toml` (package-data에 `static/*`, `static/fonts/*`)
- Test: `tests/test_routes.py`

**Interfaces:**
- Produces: `base.html` 블록 `title`, `hero`(초록 영역), `sheet`(흰 시트), `cta`(하단 고정 버튼 영역); CSS 클래스 `card`, `btn`, `btn-dark`, `btn-soft`, `bar`(위험 막대 + 평균선), `chip`; 매크로 `risk(vs, lvl)`(색 고정 규칙), `risk_bar(vs)`(평균선 50% 기준, 너비 = `min(vs/2, 1)*100%`)
- 글꼴 받기는 외부 다운로드라 **사용자에게 먼저 확인**(파일명·출처·크기). 출처: `github.com/orioncactus/pretendard` v1.3.9 릴리스의 woff2(서브셋). `.gitattributes`에 `*.woff2 binary`.

- [ ] **Step 1: 실패하는 테스트 작성**
  - `test_static_css_served`: `GET /static/app.css` 200, `text/css`, 본문에 `#0ca678`, `@view-transition`, `prefers-reduced-motion`
  - `test_pages_have_no_external_requests`: `/`, 오류 화면(`/c/nope`)의 HTML에 `http://`·`https://`로 시작하는 `src=`/`href=` 없음(같은 사이트 링크만)
  - `test_error_page_uses_layout`: `/c/nope` 404 본문에 `/static/app.css`와 면책 문구
- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현** — 사용자 확인 후 글꼴 받기. CSS는 Global Constraints 색·레이아웃·전환 규칙, 다크 모드 변수. `error.html`을 새 레이아웃으로.
- [ ] **Step 4: 통과 확인** + 개발 서버(스크래치 `dev_server.py`)로 오류 화면을 폰 크기·다크 모드에서 스크린샷 확인
- [ ] **Step 5: 커밋** — `feat: green design system, self-hosted Pretendard`

---

### Task 6: 시작 화면·토스식 입력·결과 화면

**Files:**
- Create: `app/templates/landing.html`, `app/templates/result.html`
- Modify: `app/templates/start.html`(몸 정보 4문항 단계 폼), `app/static/flow.js`, `app/routes.py`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: Task 5 레이아웃, `assess`, `scenario`, `vs_text`, `get_stats`
- Produces:
  - `GET /` → `landing.html`: 예시 인물 `assess("M", 45, 172, 82)` 결과, 특징 3개(1분 / 맞춤 계획 / 무료), "이름·연락처는 받지 않아요", 버튼 "내 위험도 확인하기" → `/start`. 통계 없으면 '준비 중'(지금 규칙).
  - `GET /start` → `start.html` 단계 폼(`<form class="steps" method="post" action="/start">`, 문항마다 `<fieldset class="step">`). 통계 없으면 '준비 중'.
  - `POST /start` 성공 → `303 /c/{token}/result` (검증·요청 제한·400 재표시는 지금 그대로)
  - `GET /c/{token}/result` → `result.html`: 수준별 요약 문장(둘 다 낮음 / 하나라도 높음 / 그 외), 위험 막대 2개, `"계획대로 3개월 꾸준히 하면 고혈압 {지금} → {3개월}까지 낮아질 수 있어요"`(`scenario()` 3개월, BMI 23 미만이면 이 줄 대신 유지 격려), 버튼 "내 30일 계획 만들기" → `/c/{token}/setup`
  - `flow.js`: `form.steps` 안 `fieldset.step`을 한 번에 하나만 보이게, 진행 막대(n/전체), ← 뒤로, 라디오는 고르면 다음으로, 숫자는 `checkValidity()` 통과 시 "다음", 답한 항목을 아래에 쌓고 누르면 그 단계로, 좌우 슬라이드. JS 없으면 아무것도 숨기지 않음(숨김은 JS가 `form`에 클래스를 붙여서만).

- [ ] **Step 1: 실패하는 테스트 작성** (기존 시작 테스트 수정 포함)
  - `test_landing_shows_example_from_model`: `/` 200, 본문에 `vs_text(assess("M",45,172,82,stats=STATS).hypertension_vs_avg)`, "내 위험도 확인하기", "이름·연락처는 받지 않아요"
  - `test_start_form_works_without_js`: `/start` 200, 하나의 `<form`에 `name="sex"`, `name="age"`, `name="height_cm"`, `name="weight_kg"` 모두, 각 문항 `fieldset class="step"`
  - `test_start_redirects_to_result`: POST 정상 → 303, location이 `/c/<token>/result`
  - `test_result_page`: 200, 본문에 두 질환의 `vs_text` 값, `/c/<token>/setup` 링크; BMI 27.7 예시엔 "3개월" 문구
  - `test_result_unknown_token_404`
  - 기존 `test_invalid_start_is_400_with_message`, 요청 제한, 통계 없음(준비 중·503) 테스트는 `/start` 기준으로 유지
- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현** — 라우트·템플릿·`flow.js`
- [ ] **Step 4: 통과 확인** + 개발 서버에서 폰 크기로 `/` → 4문항 → 결과까지 직접 눌러 확인(슬라이드, 뒤로, 답한 항목 수정, 숫자 범위 밖 안내), 브라우저 JS 끈 상태에서도 제출되는지 확인
- [ ] **Step 5: 커밋** — `feat: landing, step-by-step onboarding and result screen`

---

### Task 7: 맞춤 질문 5문항

**Files:**
- Create: `app/templates/setup.html`
- Modify: `app/routes.py`, `app/service.py`(필요 시 `profile_of`)
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `save_setup`, `InvalidSetup`, `Trial.setup_done`, `choose_variant`, `Profile`, `flow.js`
- Produces:
  - `profile_of(trial: Trial) -> Profile` (setup 완료 전제; variant는 `trial.plan_variant`, `free_days`는 `tuple(int)`)
  - `GET /c/{token}/setup` → `setup.html` 단계 폼 5문항(식사 스타일 / 점심은 주로 어디서 / 아침 / 하루 운동 가능 시간 / 자유 한 끼 요일 2개 체크박스, JS는 2개 고르면 다음 활성·3번째 선택 막음)
  - `POST /c/{token}/setup` 성공 → `303 /c/{token}`; `InvalidSetup`·숫자 아님 → 400 폼 재표시 + 오류 문구
  - setup 안 된 체험의 `GET /c/{token}`, `/c/{token}/report`, `/c/{token}/week/{n}.pdf`, `POST /c/{token}/day/{n}` → `303 /c/{token}/setup`
  - 시작 화면·`start.html`의 개인정보 안내 문구: `"수집 항목: 성별·나이·키·몸무게, 생활 답변(식사 스타일·점심 장소·아침 습관·운동 시간·자유 한 끼 요일), 일일 체크 기록. 이름·연락처는 받지 않아요. 보관: 체험 종료 후 90일."`

- [ ] **Step 1: 실패하는 테스트 작성**
  - 공통 헬퍼 `_start_and_setup(client)`(기존 `_start` 대체): 시작 → setup POST(`veg, store, skip, 25, free_days=[2,5]`) → 기록 화면 URL 반환. 기존 기록·PDF·리포트 테스트는 이 헬퍼로.
  - `test_setup_saves_and_redirects`: 303 → `/c/<token>`, 이후 기록 화면 200
  - `test_setup_bad_values_400` (parametrize): `diet_style="x"`; `free_days` 1개·3개·중복; `exercise_min="abc"` → 400 + 폼 재표시, 서버 예외 없음
  - `test_pages_redirect_to_setup_until_done`: setup 전 `/c/<t>`, `/c/<t>/report`, `/c/<t>/week/1.pdf`, `POST /c/<t>/day/1` → 303 `/c/<t>/setup`
  - `test_privacy_notice_lists_setup_answers`: `/start` 본문에 위 안내 문구
- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** + 개발 서버에서 결과 → 5문항 → 기록 화면 흐름을 폰 크기로 확인
- [ ] **Step 5: 커밋** — `feat: setup questions for personalized plan`

---

### Task 8: 기록 화면 — 오늘 계획·팁·의심·주간 요약·강도 질문

**Files:**
- Modify: `app/templates/check.html`, `app/routes.py`
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `build_plan`, `profile_of`, `get_decisions`, `decide_level`, `level_on`, `streak`, `plateau`, `summary_week`, `week_summary`, `can_level_up`, `week_of`
- Produces:
  - `GET /c/{token}` 화면 구성(스펙 5.2-5·6): 초록 영역 `Day N`, 연속 기록 문구(`streak ≥ 2`면 `"{n}일 연속 지키는 중이에요 🔥"`, 아니면 격려 문구), 진행 링 N/30, 강도 단계 > 0이면 배지 `"강도 {n}단계 진행 중"`. 시트: 선택한 날 계획 카드(이모지 아이콘, 자유 한 끼 강조, notes), 체중 입력, 지켰어요/못 지켰어요, 오늘의 팁, 의심 카드(`plateau(logs, today)`일 때: 장난스러운 의심 한 줄 + 원인 하나(음료·간식·소스·양을 `today % 4`로 순환) + `"물 무게 때문에 1~2주 정체는 흔해요"`), 주간 요약 카드(`summary_week`가 w일 때: `week_summary`, `can_level_up`이면 질문과 [올리기][이대로 유지] 버튼, 결정했으면 결과 한 줄, 다음 주 PDF 버튼), 30일 도장판, 참고 위험도 카드 + 이번 주 PDF 버튼(`/c/{token}/week/{week_of(today)}.pdf`)
  - `POST /c/{token}/week/{w}/level` (폼 `choice=up|keep`) → `summary_week(today, logs) == w` 이고 `can_level_up` 일 때만 `decide_level` 후 `303 /c/{token}`; 그 외 400 안내 화면. 요청 제한은 기록 저장과 같은 `DAY_PER_IP`.
  - 계획은 매 요청 `build_plan(profile_of(trial), trial.start_date, trial.token, get_decisions(...))`

- [ ] **Step 1: 실패하는 테스트 작성** (날짜는 `trial.start_date`를 DB에서 직접 과거로 옮겨 만든다)
  - `test_check_shows_today_plan_tip_and_streak`: Day 1 화면에 그날 `build_plan` 아침 문장·팁 문장, 기록 2일 연속 kept 후 Day 3에 `"2일 연속"`
  - `test_free_meal_day_highlighted`: 자유 한 끼 요일인 날 화면에 `"자유 한 끼"`
  - `test_plateau_card`: 1~7일 kept + 체중 80.0/80.3, Day 7 → `"정체는 흔해요"` 포함; 체중이 줄면 미포함
  - `test_week_summary_and_level_up`: 위 정체 + Day 7 기록 후 화면에 강도 질문, `POST week/1/level choice=up` → 303, Day 8 화면에 `"강도 1단계"`와 저녁 notes `"밥은 1/3 공기"`
  - `test_level_post_rejected_cases`: 같은 주 두 번째 POST → 400, `week/2/level`을 Day 8에 → 400, 정체 아닌 주 → 400, 단계가 2를 넘지 않음
  - `test_no_weights_week_summary`: 체중 없이 Day 7 기록 → 200, 주간 요약에 `"체중 기록 없음"`
  - 기존 기록 저장·더블 탭·미래 날짜 400 테스트 유지
- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** + 개발 서버에서 시드 데이터로 Day 1·Day 7(정체)·Day 8(강도 1단계) 화면을 폰 크기·다크 모드로 확인
- [ ] **Step 5: 커밋** — `feat: daily check redesign with tips, plateau nudge and level-up question`

---

### Task 9: 주간 PDF

**Files:**
- Modify: `app/pdf.py`, `app/routes.py`, `app/plan.py`, `app/fonts/` (Pretendard TTF 추가 시), `tests/test_pdf.py`, `tests/test_routes.py`, `tests/test_plan.py`
- Delete: `app/data/templates.json`

**Interfaces:**
- Consumes: `PlanDay`, `build_plan`, `week_days`, `week_of`, `level_on`, `scenario`, `Assessment`
- Produces:
  - `render_week_pdf(a: Assessment, week: int, days: list[PlanDay], label: str, level: int, check_url: str, points: list[ScenarioPoint] | None = None) -> bytes` — 한 장: 제목(`"{week}주차 · {첫 날짜}~{끝 날짜} · {label}"` + 단계 > 0이면 `"· 강도 {level}단계"`), 표(요일·날짜 / 아침 / 점심 / 저녁(+notes) / 운동 / `지킴 ○/×` 빈칸 / 체중 빈칸), 자유 한 끼 행 옅은 초록 배경, 이번 주 팁(그 주 첫 날의 팁), QR, 면책 문구 푸터. `points`가 있으면(1주차) 두 번째 장 "내 결과 요약": 나와 한국 평균, 참고 위험도, 1년 시나리오, QR.
  - `GET /c/{token}/week/{w}.pdf`: `1 ≤ w ≤ 5`, 그리고 `w == 1` 또는 `current_day ≥ 7*(w-1)`일 때 PDF(`inline; filename="watchme-week{w}.pdf"`), 범위 밖 404, 아직 안 된 주 400 안내 화면
  - `GET /c/{token}/plan.pdf` → `303 /c/{token}/week/{week_of(current_day)}.pdf`
  - 기존 `render_pdf`, `plan.DayPlan`, `plan.make_plan`, `templates.json`과 그 테스트 삭제(이제 아무도 안 씀)
  - 글꼴: Pretendard TTF를 쓰려면 Task 5와 같은 확인 절차. 릴리스에 TTF가 없고 OTF(CFF)뿐이면 reportlab이 못 읽으므로 NanumGothic 유지(색·레이아웃만 초록 체계)

- [ ] **Step 1: 실패하는 테스트 작성**
  - `test_week_pdf_one_page_with_week_days`: 1주 외 주차는 페이지 1장, 텍스트에 각 날 아침 문장, `"지킴"`, 면책 문구, 자유 한 끼 날이면 `"자유 한 끼"`
  - `test_week1_pdf_has_summary_page`: `points` 주면 2장, `"시나리오"` 포함
  - `test_week_pdf_shows_level`: level 1 → 제목에 `"강도 1단계"`
  - 라우트: `week/1.pdf` 200 `application/pdf`; `week/0.pdf`·`week/6.pdf` 404; Day 1에 `week/2.pdf` 400, Day 7에 `week/2.pdf` 200; `plan.pdf` → 303 현재 주; PDF QR 텍스트가 `PUBLIC_BASE_URL/c/<token>`(기존 테스트 이식)
- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** + pymupdf로 1주차·2주차 PDF를 PNG로 렌더해 눈으로 확인(글자 깨짐·표 넘침 없음)
- [ ] **Step 5: 커밋** — `feat: weekly plan PDF`

---

### Task 10: 30일 리포트·안내 문구 정리

**Files:**
- Modify: `app/templates/report.html`, `app/routes.py`(필요 시)
- Test: `tests/test_routes.py`

**Interfaces:**
- Consumes: `Report`(+ `plateau`), `days_left`, 매크로 `risk`, `risk_bar`
- Produces: 스펙 5.2-7 화면. 초록 영역 문구: 지킨 날 ≥ 24 → `"30일 완주! {n}일을 지켰어요 🎉"`, 12~23 → `"30일 완주! {n}일을 지켰어요"`, < 12 → `"30일이 지났어요. {n}일을 지켰어요"`. 체중 변화 크게, 평균 비교(처음 값 취소선 → 지금 값, 좋아진 값 파랑), `plateau`면 의심 한 줄, 카카오 노란 카드(`#fee500`, 버튼 비활성 "카카오톡으로 이어가기 (곧 오픈)"), 기록 부족 안내 유지. 30일 전이면 `"{N}일 남았어요"` 화면(새 레이아웃).

- [ ] **Step 1: 실패하는 테스트 작성**
  - `test_seeded_demo_report` 갱신: 200, `"30일 완주"` 또는 `"30일이 지났어요"`, `"카카오톡으로 이어가기"`
  - `test_report_completion_copy` (parametrize kept 25/15/5 → 위 세 문구)
  - `test_report_plateau_line`: 마지막 7일 정체 로그 → `"정체"` 포함
  - 기존 `"N일 남았어요"`, 404 테스트 유지
- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** + 개발 서버에서 시드 리포트를 폰 크기로 확인
- [ ] **Step 5: 커밋** — `feat: report redesign`

---

### Task 11: 배포 — DB 재생성·시드·폰 확인

**Files:**
- Modify: `docs/server-runbook.md`(11장: 리디자인 배포, DB 재생성 기록)

- [ ] **Step 1:** 전체 테스트 — Run: `.venv/Scripts/python -m pytest -q` / Expected: 전부 PASS
- [ ] **Step 2:** **사용자 확인 후** 운영 DB 표 재생성: 지울 대상(체험 수·기록 수)을 조회해 보여주고 승인받은 뒤 `trials`, `day_logs` 삭제 → 배포(`git push evrd main`)로 `init_db`가 새 표 생성. 백업이 하루 1회 있음을 함께 안내.
- [ ] **Step 3:** 서버에서 시드 실행(`docker compose exec -T app python -m scripts.seed_demo`), 리포트 URL 200 확인, `https://evrd.fyi/` 200·외부 요청 없음 확인
- [ ] **Step 4:** 사용자에게 LTE 폰으로 처음부터(시작 → 4문항 → 결과 → 5문항 → 기록 → 1주차 PDF) 확인 요청
- [ ] **Step 5:** runbook·ledger 기록, 커밋 `docs: runbook redesign deploy`
