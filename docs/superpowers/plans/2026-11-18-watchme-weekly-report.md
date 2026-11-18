# Watchme 주간 리포트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 1~4주차마다 리포트를 만든다. 리포트에는 국민건강영양조사 실제 값으로 계산한 또래 비교, 앱 사용자 순위, 체중 그래프, 자랑 카드 PNG가 들어간다. 8·15·22·29일째 아침 카톡으로 보낸다.

**Architecture:**
- 걷기 비율 표는 통계 스크립트가 `korea_stats.json`의 `walk`에 미리 계산해 둔다.
- 새 모듈은 셋이다.
  - `app/weekly.py`: 판단과 문구.
  - `app/chart.py`: SVG 그래프.
  - `app/card.py`: Pillow로 PNG 카드.
- 새 화면 두 개(리포트 HTML, 카드 PNG)와 카톡 아침 분기 하나를 붙인다.
- DB 표는 늘리지 않는다.

**Tech Stack:** FastAPI, Jinja2, SQLAlchemy, Pillow(reportlab이 이미 설치하므로 의존성에 명시만), pandas·pyreadstat(통계 스크립트 전용)

**Spec:** `docs/superpowers/specs/2026-11-18-watchme-weekly-report-design.md`

## Global Constraints
- 통계에 없는 숫자는 쓰지 않는다. 또래 비교는 `walk` 표 값으로만 계산한다. 표가 없으면 숨긴다.
- 또래 비교는 p ≤ 0.5일 때만 보여 준다. 잘 못한 주에 "하위"라는 표현은 절대 쓰지 않는다.
- 자랑 카드와 공유 문구에는 체중·위험도·토큰을 넣지 않는다. 공유 문구는 `PUBLIC_BASE_URL`만 넣는다.
- 출처 줄 문구는 정확히 `국민건강영양조사 2022–2024 · 걷기 기준`으로 한다.
- 새 DB 표, 새 라이브러리는 만들지 않는다. `.env`와 `data/raw/`는 커밋하지 않는다.
- 화면 문구는 해요체로 쓴다.
- 테스트 명령은 `.venv/Scripts/python -m pytest -q`이다. worktree에서 돌릴 때는 `../../../.venv/Scripts/python`.
- 커밋 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.

## Review Focus
1. **통계에 `walk`가 없을 때:** 테스트용 `STATS`나 예전 파일이면 리포트·카톡이 오류 없이 또래 줄만 빼고 나와야 한다. → Task 4·6 테스트.
2. **7일째 열람 조건:** 7일째에 그날 기록 전에 열면 400, 기록 후에는 200. 30일이 끝난 뒤에도 1~4주차는 열린다. → Task 4 테스트.
3. **고위험 계획의 "×2회" 운동:** 하루 분 수는 두 번을 합친 값이다. 쉬는 날(7의 배수)은 0분이다. → Task 2 테스트.
4. **카톡 줄 길이:** 줄이 32자를 넘으면 `messages.fit`이 "…"로 자른다. 가장 긴 나이대 이름 "70대 이상 남성"과 "100명 중 N명"에서도 잘리면 안 된다. → Task 6 테스트.
5. **잘 못한 주의 카드:** 또래 줄이 없는 주는 카드 주소가 404이고 [자랑하기]도 안 보인다. → Task 5 테스트.

---

### Task 1: 걷기 비율 표

**Files:**
- Modify: `scripts/knhanes_stats.py` (`COLS`, `load`, `build`)
- Modify: `app/data/korea_stats.json` (스크립트로 다시 생성)
- Test: `tests/test_knhanes_stats.py`

**Interfaces:**
- Produces:
  - `walk_table(df: pd.DataFrame) -> dict`
    - 입력 열: `sex`(1/2), `age_band`, `w`, `BE3_31`, `BE3_32`, `BE3_33`.
    - 반환: `{"M"|"F": {band: {"n": int, "share": {"10".."60": [p_k1..p_k7]}}}}`.
  - `korea_stats.json["walk"] = {"source": str, "groups": walk_table(df)}`.
  - `share[str(m)][k-1]`은 "주 k일 이상 걷고 하루 m분 이상"인 사람의 가중 비율이다(소수 4자리).

- [ ] **Step 1: 실패하는 테스트 쓰기**
```python
def test_walk_table_shares():
    from scripts.knhanes_stats import walk_table
    df = pd.DataFrame({"sex": [1]*6, "age_band": ["40"]*6, "w": [1.0]*6,
                       "BE3_31": [8, 7, 2, 1, 99, 8], "BE3_32": [0, 0, 1, 88, 0, 88], "BE3_33": [30, 20, 0, 88, 30, 88]})
    s = walk_table(df)["M"]["40"]
    assert s["n"] == 4                      # 99(모름)·88(무응답 시간) 제외, 0일은 0분으로 남김
    assert s["share"]["20"][5] == 0.5       # 6일↑·20분↑: 7일30분, 6일20분
    assert s["share"]["30"][5] == 0.25
    assert s["share"]["10"][0] == 0.75      # 1일↑·10분↑
    assert s["share"]["60"][0] == 0.25      # 1일 60분
```
`pd`는 `pytest.importorskip("pandas")`로 가져온다(파일 맨 위 패턴을 따른다).

- [ ] **Step 2: 실행해서 실패 확인**
  - Run: `.venv/Scripts/python -m pytest -q tests/test_knhanes_stats.py`
  - Expected: FAIL (`walk_table` 없음)

- [ ] **Step 3: 구현**
  - `COLS`에 `BE3_31`, `BE3_32`, `BE3_33`을 더한다.
  - `walk_table`을 쓴다.
    - days = BE3_31 − 1 (1~8만 쓴다).
    - 분 = BE3_32×60 + BE3_33 (둘 다 88 미만일 때만). days = 0이면 0분.
  - `build()` 반환값에 `"walk": {"source": "국민건강영양조사 2022–2024 BE3_31·BE3_32·BE3_33(걷기 일수·하루 걷기 시간), 19세 이상, 가중치 wt_itvex", "groups": walk_table(df)}`를 넣는다.

- [ ] **Step 4: 통과 확인 + 실제 표 다시 만들기**
  - Run: `.venv/Scripts/python -m pytest -q tests/test_knhanes_stats.py`, 이어서 `.venv/Scripts/python -m scripts.knhanes_stats`
  - Expected:
    - 테스트 PASS.
    - JSON이 다시 쓰이고, `walk.groups.M["40"].share["20"][5]`이 0.29 근처(0.25~0.33)이다. 시안 값은 BMI 필터 없이 0.291이었다.
    - 기존 `groups`(위험도) 값은 바뀌지 않는다: `git diff app/data/korea_stats.json`에 `walk`만 추가돼 있다.

- [ ] **Step 5: 커밋** — `feat: walking share table from KNHANES`

---

### Task 2: 주간 판단과 문구 (`app/weekly.py`)

**Files:**
- Modify: `app/plan.py` (`PlanDay` 맨 끝에 `exercise_min: int = 0` 추가. 기본값은 위치 인자로 만드는 기존 테스트용. `_exercise`가 문장과 분을 같이 돌려준다)
- Create: `app/weekly.py`
- Test: `tests/test_weekly.py`, `tests/test_plan.py`

**Interfaces:**
- Consumes:
  - Task 1의 `stats["walk"]`.
  - 기존 `group_label`, `age_band`(risk), `week_days`(plan), `week_summary`·`WeekSummary`(progress), `plan_for`·`get_logs`·`current_day`(service).
- Produces:
  - `PlanDay.exercise_min: int`: 그날 총 분. 쉬는 날은 0, "×2회"면 두 번을 합친 값.
  - `@dataclass(frozen=True) class Peer: days: int; minutes: int; share: float; label: str`와 `@property ratio -> str`.
  - `ratio_text(share: float) -> str`
    - share ≥ 0.1이면 `f"10명 중 {round(share*10)}명"`.
    - 아니면 `f"100명 중 {max(1, round(share*100))}명"`.
  - `walk_share(stats: dict | None, sex: str, age: int, days: int, minutes: int) -> float | None`
    - minutes를 10분 단위로 내려 10~60에 맞춘다.
    - 자료가 없거나 days < 1이면 None.
  - `peer_of(trial: Trial, days: list[PlanDay], logs: list[DayLog], stats: dict | None) -> Peer | None`
    - k = 지킨 운동하는 날 수(`exercise_min > 0`).
    - m = 그 주 운동하는 날의 `exercise_min` 최솟값.
    - 여기서 비율은 `walk_share(stats, trial.sex, trial.age, k, m)`이다. 이 값이 없거나 0.5를 넘으면 None.
  - `week_ready(today_day: int, logs: list[DayLog], week: int) -> bool`
    - 1 ≤ week ≤ 4이고, (today_day > 7·week 또는 (today_day == 7·week이고 그날 기록 있음)).
  - `app_rank(db: Session, trial: Trial, week: int, kept: int, today: date) -> int | None`
    - 비교 대상: 다른 체험 중 `start_date <= today - 7·week일`이고, 그 주 `DayLog`가 1개 이상인 체험.
    - 비교 대상이 30명 미만이면 None.
    - N = ceil(100·(나보다 kept가 크거나 같은 수 + 1)/(비교 대상 수 + 1)). N > 50이면 None.
  - `cheer(week: int, kept: int, prev_kept: int | None) -> str`: 문구는 아래에 정확히 적었다.
  - `@dataclass(frozen=True) class WeekReport`
    - `week: int`
    - `first: date`, `last: date`
    - `marks: tuple[bool | None, ...]`: 날마다 지킴 / 못 지킴 / 기록 없음.
    - `kept: int`
    - `peer: Peer | None`, `rank: int | None`
    - `cheer: str`
    - `weights: list[tuple[int, float]]`: (0, 시작 체중) + 7·week일까지의 체중 기록.
    - `summary: WeekSummary`
  - `build_week(db: Session, trial: Trial, week: int, today: date, stats: dict | None) -> WeekReport`

`cheer` 문구(정확히):
- kept == 0: `"이번 주는 쉬어 갔어요. 오늘부터 다시 하루씩 채워 봐요."`
- week == 1, kept ≥ 5: `f"첫 주부터 {kept}일! 이 속도면 30일 완주 충분해요."`
- week == 1 (그 밖): `f"첫 주 {kept}일, 시작이 반이에요. 다음 주엔 하루만 더 지켜 봐요."`
- 지난주보다 늘었을 때: `f"지난주보다 {diff}일 더 지켰어요. 점점 몸에 붙고 있어요."`
- 지난주와 같을 때: `"지난주만큼 꾸준히 지켰어요. 꾸준함이 제일 어려운 거예요."`
- 지난주보다 줄었을 때: `"이번 주는 조금 쉬어 갔어요. 다음 주에 다시 올려 봐요."`

- [ ] **Step 1: 실패하는 테스트 쓰기** (`tests/test_weekly.py`)
  - `WALK`: `STATS | {"walk": {"groups": {"M": {"40": {"n": 1, "share": {str(m): [0.9, 0.8, 0.7, 0.6, 0.41, 0.29, 0.2] for m in (10, 20, 30, 40, 50, 60)}}}}}}`.
  - `test_ratio_text`: 0.291 → `"10명 중 3명"`, 0.07 → `"100명 중 7명"`, 0.004 → `"100명 중 1명"`.
  - `test_walk_share_floors_minutes_and_handles_missing`
    - `walk_share(WALK, "M", 45, 6, 25) == 0.29`
    - `walk_share(STATS, "M", 45, 6, 25) is None`
    - `walk_share(WALK, "M", 45, 0, 25) is None`
    - `walk_share(WALK, "F", 45, 6, 25) is None`
  - `test_peer_counts_only_exercise_days`
    - 45세 남성(170cm·80kg → high_risk), 설정 `("mixed","out","light",45,[2,5])`.
    - 1~7일을 모두 kept로 기록한다(7일째는 쉬는 날).
    - 1주차는 45×0.6 → 30분이므로 `peer.days == 6`, `peer.minutes == 30`, `peer.ratio == "10명 중 3명"`, `peer.label == "40대 남성"`.
  - `test_peer_hidden_when_over_half`: 운동하는 날 4일만 kept → 0.6 > 0.5 → None.
  - `test_week_ready`
    - `week_ready(7, [], 1) is False`
    - 7일째 기록이 있으면 `week_ready(7, logs, 1)`는 True.
    - `week_ready(8, [], 1)` True, `week_ready(30, [], 4)` True, `week_ready(30, [], 5)` False.
  - `test_app_rank_needs_30_peers_and_top_half`
    - 다른 체험 29개(기록 있음) → None.
    - 30개가 모두 kept 3이고 내가 6 → `ceil(100·(0+1)/(30+1)) == 4`.
    - 30개가 모두 7이고 내가 3 → `ceil(100·31/31) = 100 > 50` → None.
    - 그 주 기록이 없는 체험은 세지 않는다.
  - `test_cheer_copy`: 위 문구 6갈래 중 대표 4개를 문자열 그대로 비교한다.
  - `test_build_week_weights_start_at_day0`: 체중 기록 (3, 79.5), (10, 79.0)이면 week 1의 weights는 `[(0, 80.0), (3, 79.5)]`.
- `tests/test_plan.py`의 `test_exercise_min_matches_text`
  - 쉬는 날은 0.
  - high_risk에서 45분이면 텍스트는 "×2회", `exercise_min == 2 × 회당분`.
  - 그 밖에는 텍스트의 N분과 같다.

- [ ] **Step 2: 실행해서 실패 확인**
  - Run: `.venv/Scripts/python -m pytest -q tests/test_weekly.py tests/test_plan.py`
  - Expected: FAIL (`app.weekly` 없음, `exercise_min` 없음)

- [ ] **Step 3: 구현**
  - `_exercise`가 `(문장, 분)`을 돌려주게 바꾸고, `build_plan`이 `PlanDay(exercise_min=...)`로 넘긴다.
  - `PlanDay`를 직접 만드는 다른 곳(테스트·`pdf`·`landing`)이 있으면 `grep -rn "PlanDay(" app tests`로 찾아 함께 고친다.
  - `app_rank`는 `DayLog`를 `Trial`과 조인하고 token별 `sum(kept)`를 한 번의 쿼리로 구한다.

- [ ] **Step 4: 통과 확인**
  - Run: `.venv/Scripts/python -m pytest -q`
  - Expected: 전체 PASS

- [ ] **Step 5: 커밋** — `feat: weekly report logic with KNHANES peer share`

---

### Task 3: 체중 그래프 (`app/chart.py`)

**Files:**
- Create: `app/chart.py`
- Test: `tests/test_chart.py`

**Interfaces:**
- Produces: `weight_svg(points: list[tuple[int, float]], last_day: int) -> Markup | None`
  - 점이 2개 미만이면 None.
  - viewBox는 `0 0 300 120`.
  - `<polyline>` 하나와 점마다 `<circle>`을 그린다.
  - 첫 값과 마지막 값을 `<text>`로 `"%.1f"` 적는다.
  - `aria-label`은 `"체중 그래프: 80.0kg에서 79.2kg"`.

- [ ] **Step 1: 실패하는 테스트**
  - `weight_svg([(0, 80.0)], 7) is None`.
  - `[(0, 80.0), (3, 79.5), (7, 79.2)]`이면 circle 3개, `points=`에 좌표 3쌍, `"79.2"`와 `"80.0"`이 들어 있고, `str(svg).startswith("<svg")`.
  - 체중이 모두 같으면(`[(0, 80.0), (5, 80.0)]`) 0으로 나누지 않고 SVG를 돌려준다.
  - 좌표는 모두 viewBox 안에 있다(정규식으로 points 숫자를 뽑아 0~300, 0~120 확인).
- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python -m pytest -q tests/test_chart.py` → FAIL
- [ ] **Step 3: 구현**
  - 가로는 day/last_day 비율로 놓는다.
  - 세로 범위는 min−0.5 ~ max+0.5.
  - `markupsafe.Markup`으로 감싼다. 값은 숫자만 들어가므로 따로 escape하지 않는다.
- [ ] **Step 4: 통과 확인** — 같은 명령 → PASS
- [ ] **Step 5: 커밋** — `feat: server-side weight chart svg`

---

### Task 4: 리포트 화면 + 기록 카드 링크 + 30일 리포트 그래프

**Files:**
- Modify: `app/routes.py`
  - 새 `week_report`를 추가한다.
  - `report_page`에 그래프를 넘긴다.
- Create: `app/templates/week.html`
- Modify: `app/templates/check.html` (요약 카드), `app/templates/report.html` (몸무게 카드 아래), `app/static/app.css`
- Test: `tests/test_weekly_routes.py`

**Interfaces:**
- Consumes: `build_week`, `week_ready`(Task 2), `weight_svg`(Task 3).
- Produces: `GET /c/{token}/week/{w:int}`. 템플릿 변수는 `token`, `r: WeekReport`, `chart: Markup | None`, `share_text: str`이다.

화면 규칙:
- **오류·이동**
  - 체험이 없으면 404.
  - 설정 전이면 setup으로 303.
  - w가 1~4가 아니면 404 `"없는 주차예요."`.
  - 아직 아니면 400 `f"{w}주차 리포트는 {7*w}일째 기록 후에 열려요."`.
- **머리**
  - kicker: `f"{w}주차 리포트 · {first:%-m/%-d}~{last:%-m/%-d}"`. 윈도 strftime에는 `%-m`이 없으니 `f"{d.month}/{d.day}"`로 만든다.
  - h1: `f"7일 중 {kept}일 지켰어요"`에 kept ≥ 5이면 `" 🎉"`.
  - `.wdots`: 날마다 ✓ / ✗ / ·.
- **카드 순서**
  - 🏅 또래: `f"주 {p.days}일 이상, 하루 {p.minutes}분 이상 걷는 {p.label}은 {p.ratio}이에요. 이번 주 그 안에 드셨어요."`, 그 아래 출처 줄.
  - 👥 순위: `f"이번 주를 기록한 Watchme 사용자 중 상위 {rank}%예요."`
  - 📈 cheer.
  - ⚖️ 체중: chart 또는 `"체중을 적으면 그래프가 생겨요."`, 그 아래 위험도 변화. 위험도는 지금 요약 카드 문구를 그대로 쓴다(`summary.before/after`가 있을 때만).
  - 버튼:
    - `<a class="btn btn-soft share" href="/c/{token}/week/{w}/card.png" data-text="{share_text}">자랑하기</a>` (peer가 있을 때만).
    - `<a class="btn" href="/c/{token}">오늘 계획 보기</a>`.
  - `share_text = f"Watchme 30일 생활습관 챌린지 {PUBLIC_BASE_URL}"`.
- **기록 화면 요약 카드**: h2 아래에 `<a class="more" href="/c/{token}/week/{summary.week}">주간 리포트 보기 →</a>`.
- **30일 리포트**: 몸무게 카드 아래에 `weight_svg(points, 30)`을 넣는다. 점은 (0, 시작) + 모든 체중 기록이다.

- [ ] **Step 1: 실패하는 테스트** (`tests/test_routes.py`의 `client`, `_start_and_setup` 패턴과 날짜 이동 방법을 따른다. `today_kst`를 monkeypatch하는 기존 테스트가 있으면 같은 방식으로)
  - `test_week_report_locked_until_day7_logged`: 7일째 기록 전 400(문구 포함) → 기록 후 200.
  - `test_week_report_opens_after_trial_ends`: 40일째에 w = 4는 200, w = 5는 404.
  - `test_week_report_without_walk_stats_hides_peer`: 기본 테스트 `STATS`면 200이고 "🏅"·"자랑하기"·"국민건강영양조사"가 없다.
  - `test_week_report_with_walk_shows_peer_and_share`
    - `get_stats` override를 `WALK`로 바꾸고 1~7일을 모두 kept로 기록한다.
    - "10명 중 3명", 출처 줄, `card.png`, `data-text`가 있다.
    - `data-text` 값에 token이 없다.
  - `test_check_summary_links_week_report`: 7일째 기록 후 기록 화면에 `/week/1"`이 있다.
  - `test_final_report_has_weight_chart`: 체중 기록이 있는 끝난 체험의 `/report`에 `<svg`가 있다.
- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python -m pytest -q tests/test_weekly_routes.py` → FAIL
- [ ] **Step 3: 구현** — 라우트는 `/c/{token}/week/{w:int}`로 쓴다. 기존 `.../week/{w}.pdf`와 충돌하지 않는지 기존 PDF 테스트로 확인한다.
- [ ] **Step 4: 통과 확인**
  - Run: `.venv/Scripts/python -m pytest -q` → 전체 PASS.
  - 미리보기에서 375px 폭으로 리포트 화면을 열어 넘침이 없는지 본다.
- [ ] **Step 5: 커밋** — `feat: weekly report page and weight charts`

---

### Task 5: 자랑 카드 PNG + 공유 버튼

**Files:**
- Create: `app/card.py`, `app/static/share.js`
- Modify: `app/routes.py`, `app/templates/week.html`(스크립트·대체 안내), `pyproject.toml`(`"pillow"` 명시), `app/static/app.css`
- Test: `tests/test_card.py`, `tests/test_weekly_routes.py`

**Interfaces:**
- Consumes: `Peer`, `WeekReport`(Task 2).
- Produces:
  - `render_card(week: int, kept: int, marks: tuple[bool | None, ...], peer: Peer) -> bytes`
    - 1080×1350 PNG.
    - 인자에 체중·토큰이 없으므로, 카드에 그런 정보가 들어갈 수 없다.
  - `GET /c/{token}/week/{w:int}/card.png`
    - 리포트와 같은 조건을 쓴다.
    - peer가 None이면 404 `"이번 주는 자랑 카드가 없어요."`.
    - 응답 헤더는 `media_type="image/png"`, `Cache-Control: private, no-store`, `X-Robots-Tag: noindex`.

카드 내용(위→아래):
- 아이콘(`static/icons/icon-192.png`)과 "WATCHME".
- `f"30일 생활습관 챌린지 · {week}주차"`.
- 큰 글씨 `f"7일 중 {kept}일"` / `"해냈어요"`.
- 점 7개.
- 반투명 상자 `f"{peer.label} {peer.ratio}만"` / `"이만큼 꾸준히 움직여요"`.
- 아래 왼쪽은 `"국민건강영양조사 · 걷기 기준"`, 오른쪽은 `PUBLIC_BASE_URL`의 호스트(`evrd.fyi`).
- 배경은 `#20c997 → #0ca678 → #087f5b` 대각선 그라데이션.
- 글꼴은 `app/fonts/NanumGothic-Bold.ttf`·`-Regular.ttf`.

`share.js` 동작:
- `a.share` 클릭을 가로챈다.
  1. `fetch(href)`로 이미지를 받아 `File`로 만든다.
  2. `navigator.canShare?.({files:[file]})`가 참이면 `navigator.share({files:[file], text: a.dataset.text})`를 연다.
  3. 공유가 안 되거나 실패하면 템플릿에 숨겨 둔 `<figure class="share-fallback" hidden>`(카드 `<img>`와 `"이미지를 길게 눌러 저장한 뒤 보내 주세요."`)를 연다.
- 사용자가 공유 창을 취소한 경우(`AbortError`)에는 아무것도 하지 않는다.
- JS가 없으면 링크가 PNG를 그대로 연다.

- [ ] **Step 1: 실패하는 테스트**
  - `test_render_card_is_png_1080x1350`: `PIL.Image.open(BytesIO(render_card(1, 6, marks, peer))).size == (1080, 1350)`.
  - `test_card_route_png_and_headers`: WALK 통계, 1~7일 모두 kept → 200, `image/png`, `no-store`.
  - `test_card_404_without_peer`: 기본 STATS → 404.
  - `test_week_page_loads_share_js`: `/static/share.js?v=`가 있다.
- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python -m pytest -q tests/test_card.py tests/test_weekly_routes.py` → FAIL
- [ ] **Step 3: 구현** — 위 내용대로 만든다. `pyproject.toml` dependencies에 `"pillow"`를 더한다.
- [ ] **Step 4: 확인**
  - 전체 테스트 PASS.
  - 카드 PNG를 Read 도구로 열어 눈으로 확인한다: 글자 잘림, 겹침, 한글 깨짐이 없어야 한다.
  - 미리보기에서 [자랑하기]를 누르면 데스크톱(공유 불가)에서 대체 안내가 열린다.
- [ ] **Step 5: 커밋** — `feat: shareable weekly brag card`

---

### Task 6: 8·15·22·29일째 아침 카톡

**Files:**
- Modify: `app/messages.py`(`week()`, `BUTTON["week"]`), `app/notify.py`(`_message` 아침 분기)
- Test: `tests/test_messages.py`, `tests/test_notify.py`

**Interfaces:**
- Consumes: `build_week`, `Peer`(Task 2), `risk.get_stats()`.
- Produces:
  - `messages.week(week: int, kept: int, peer: Peer | None) -> str`. 줄 구성:
    1. `f"🏅 {week}주차 리포트가 나왔어요!"`
    2. kept > 0이면 `f"7일 중 {kept}일 지켰어요."`, 아니면 `"이번 주는 쉬어 갔어요. 다시 시작해 봐요."`
    3. peer가 있으면 `f"주 {peer.days}일 이상 움직이는 {peer.label}은"`과 `f"{peer.ratio}이에요. 그 안에 드셨어요!"` 두 줄.
  - `BUTTON["week"] = "리포트 보기"`.
  - `_message`: 아침이고 n ∈ {8, 15, 22, 29}이면 `("week", messages.week(...), f"{link}/week/{(n-1)//7}", BUTTON["week"])`를 돌려준다. 그날 계획 메시지는 보내지 않는다. `_message`에 `today`를 넘기도록 시그니처를 바꾼다.

- [ ] **Step 1: 실패하는 테스트**
  - `test_week_message_lines_never_truncated`: label "70대 이상 남성", ratio "100명 중 7명", days 6, kept 7 → 모든 줄이 `len(line) <= messages.LINE`이고 "…"가 없다.
  - `test_week_message_without_peer`: 두 줄만 있고 "주 " 줄이 없다.
  - `tests/test_notify.py`의 `test_morning_week_report_days`를 `(8, "/week/1")`, `(15, "/week/2")`, `(29, "/week/4")`로 매개변수화한다.
    - 보낸 메시지는 1개이고, `"주차 리포트"`를 담고, 링크가 기대값으로 끝난다.
    - `"오늘 계획"`은 없다.
    - 같은 날 다시 돌려도 0개다.
- [ ] **Step 2: 실패 확인** — Run: `.venv/Scripts/python -m pytest -q tests/test_messages.py tests/test_notify.py` → FAIL
- [ ] **Step 3: 구현** — 위 내용대로 만든다.
- [ ] **Step 4: 통과 확인** — 전체 테스트 PASS (기존 `test_morning_day1_and_report_day31` 포함)
- [ ] **Step 5: 커밋** — `feat: weekly report kakao message on days 8/15/22/29`

---

### Task 7: 문서

**Files:**
- Modify: `docs/runbook.md` 또는 runbook이 있는 파일(`grep -rln "make_icons" docs`로 찾기)
- Modify: `docs/deliverables/requirements.md`, `api.md`, `wireframes.md`, `demo-script.md`, `README.md`
- Modify: spec 상태 줄

내용:
- **runbook**: 걷기 표를 다시 만드는 방법(`python -m scripts.knhanes_stats`, `data/raw`는 커밋 금지), 주간 카톡이 나가는 날.
- **requirements**: FR 번호를 이어서 붙인다(주간 리포트, 또래 비교, 앱 순위, 체중 그래프, 자랑 카드, 주간 카톡).
- **api**: 새 경로 2개.
- **wireframes**: 리포트 화면과 카드.
- **demo-script**: 시연 한 장면.
- **README**: 마지막 갱신 줄(기준 커밋, 테스트 수).

- [ ] **Step 1:** 문서를 고치고 `git diff --stat docs`로 확인한다.
- [ ] **Step 2: 커밋**
  - 코드 문서 커밋: `docs: weekly report runbook and spec status`.
  - 제출물은 배포 뒤 따로 `docs/deliverables`만 담아 커밋한다.
