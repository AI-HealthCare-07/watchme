import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import routes
from app.db import Base, get_db
from app.main import app
from app.models import DayLog
from app.clock import today_kst as _today
from app.risk import get_stats
from tests.test_risk import STATS

FORM = {"sex": "M", "birth_year": str(_today().year - 45), "height_cm": "170", "weight_kg": "80"}


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def _db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_stats] = lambda: STATS
    for limiter in routes.LIMITERS:
        limiter.hits.clear()
    c = TestClient(app, follow_redirects=False)
    c.engine = engine
    yield c
    app.dependency_overrides.clear()


SETUP = {"diet_style": "veg", "lunch_place": "store", "breakfast": "skip", "exercise_min": "25", "free_days": ["2", "5"]}
PRIVACY = ("수집 항목: 성별·나이·키·몸무게, 생활 답변(식사 스타일·점심 장소·아침 습관·운동 시간·자유 한 끼 요일), "
           "일일 체크 기록. 이름·연락처는 받지 않아요. 보관: 체험 종료 후 90일. "
           "카카오로 연결하면 카카오 회원번호와 메시지 발송 권한(암호화 보관)을 저장해요. 연결을 끊으면 바로 지워요. "
           "한 줄 요청을 적으면 그 내용은 AI(구글 Gemini)로 보내고, 체험과 함께 지워요.")


def _start_only(client):
    r = client.post("/start", data=FORM)
    assert r.status_code == 303
    return r.headers["location"].removesuffix("/result")


def _start_and_setup(client):
    loc = _start_only(client)
    r = client.post(f"{loc}/setup", data=SETUP)
    assert r.status_code == 303 and r.headers["location"] == f"{loc}/ready"
    return loc


def _ok_pick_on_today_breakfast(client, loc):
    """오늘(Day 1) 아침을 AI가 뺀 것으로 저장하고 그 문장을 돌려준다."""
    import json
    from app.models import AiPick
    from app.service import get_trial, plan_for
    with Session(client.engine) as s:
        t = get_trial(s, loc.removeprefix("/c/"))
        gone = plan_for(s, t)[0].meals["breakfast"]
        s.add(AiPick(token=t.token, request="r", excluded=json.dumps([gone]), reason="x", status="ok"))
        s.commit()
    return gone


def test_check_page_applies_ai_exclusion(client):
    loc = _start_and_setup(client)
    gone = _ok_pick_on_today_breakfast(client, loc)
    assert gone not in client.get(loc).text


def test_start_form_has_notice(client):
    for path in ("/", "/start"):
        r = client.get(path)
        assert r.status_code == 200
        assert "수집 항목" in r.text


def test_landing_shows_example_from_model(client):
    from app.risk import assess, vs_text

    a = assess("M", 45, 172, 82, stats=STATS)
    r = client.get("/")
    assert r.status_code == 200
    assert vs_text(a.hypertension_vs_avg) in r.text and vs_text(a.diabetes_vs_avg) in r.text
    assert "내 위험도 확인하기" in r.text and 'href="/start"' in r.text
    assert "이름·연락처는 받지 않아요" in r.text


def test_start_form_works_without_js(client):
    r = client.get("/start")
    assert r.status_code == 200
    assert r.text.count("<form") == 1
    for name in ("sex", "birth_year", "height_cm", "weight_kg"):
        assert f'name="{name}"' in r.text
    assert r.text.count('<fieldset class="step"') == 4


def test_start_redirects_to_result(client):
    r = client.post("/start", data=FORM)
    assert r.status_code == 303
    assert re.fullmatch(r"/c/[\w-]+/result", r.headers["location"])


def test_result_page(client):
    from app.risk import assess, vs_text

    loc = _start_only(client)
    a = assess("M", 45, 170, 80, stats=STATS)
    r = client.get(f"{loc}/result")
    assert r.status_code == 200
    assert vs_text(a.hypertension_vs_avg) in r.text and vs_text(a.diabetes_vs_avg) in r.text
    assert f'href="{loc}/setup"' in r.text
    assert "3개월" in r.text


def test_birth_year_becomes_age(client):
    r = client.get(f"{_start_only(client)}/result")
    assert "45세" in r.text


def test_birth_year_out_of_range_message(client):
    r = client.post("/start", data=FORM | {"birth_year": "1800"})
    assert r.status_code == 400
    assert "출생연도는" in r.text


def test_result_unknown_token_404(client):
    assert client.get("/c/nope/result").status_code == 404


@pytest.mark.parametrize("field,value", [("birth_year", "0"), ("birth_year", "abc"), ("birth_year", str(_today().year)), ("height_cm", ""), ("sex", "")])
def test_invalid_start_is_400_with_message(client, field, value):
    r = client.post("/start", data=FORM | {field: value})
    assert r.status_code == 400
    assert "입력" in r.text or "선택" in r.text


def test_unknown_token_404(client):
    assert client.get("/c/없는토큰").status_code == 404
    assert client.get("/c/nope/plan.pdf").status_code == 404
    assert client.post("/c/nope/day/1", data={"kept": "1"}).status_code == 404


def test_double_submit_same_day_keeps_one_row(client):
    loc = _start_and_setup(client)
    assert client.post(f"{loc}/day/1", data={"kept": "1", "weight_kg": "80.2"}).status_code == 303
    assert client.post(f"{loc}/day/1", data={"kept": "0", "weight_kg": ""}).status_code == 303
    with Session(client.engine) as s:
        rows = s.scalars(select(DayLog)).all()
    assert len(rows) == 1 and rows[0].kept is False and rows[0].weight_kg is None


@pytest.mark.parametrize("day,data", [(31, {"kept": "1"}), (0, {"kept": "1"}), (2, {"kept": "1"}), (1, {"kept": "1", "weight_kg": "abc"})])
def test_bad_day_post_is_400(client, day, data):
    # day 2는 아직 오지 않은 날(시작 당일은 day 1)
    loc = _start_and_setup(client)
    assert client.post(f"{loc}/day/{day}", data=data).status_code == 400


def test_pdf_uses_public_base_url(client, monkeypatch):
    loc = _start_and_setup(client)
    seen = {}

    def fake_render(a, week, days, label, level, check_url, points=None):
        seen.update(url=check_url, week=week, n=len(days), points=points is not None)
        return b"%PDF-fake"

    monkeypatch.setattr(routes, "render_week_pdf", fake_render)
    monkeypatch.setattr(routes, "PUBLIC_BASE_URL", "https://public.example")
    r = client.get(f"{loc}/week/1.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-type"] == "application/pdf"
    assert 'filename="watchme-week1.pdf"' in r.headers["content-disposition"]
    assert seen == {"url": f"https://public.example{loc}", "week": 1, "n": 7, "points": True}


def test_real_pdf_renders(client):
    r = client.get(f"{_start_and_setup(client)}/week/1.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_week_pdf_range_and_timing(client):
    loc = _start_and_setup(client)
    for w in (0, 6):
        assert client.get(f"{loc}/week/{w}.pdf").status_code == 404
    assert client.get(f"{loc}/week/x.pdf").status_code == 404
    r = client.get(f"{loc}/week/2.pdf")
    assert r.status_code == 400 and "의학적 진단" in r.text  # 아직 안 온 주: 안내 화면
    _set_day(client, loc, 7)
    assert client.get(f"{loc}/week/2.pdf").status_code == 200
    assert client.get("/c/nope/week/1.pdf").status_code == 404


def test_plan_pdf_redirects_to_current_week(client):
    loc = _start_and_setup(client)
    _set_day(client, loc, 9)
    r = client.get(f"{loc}/plan.pdf")
    assert r.status_code == 303 and r.headers["location"] == f"{loc}/week/2.pdf"


def test_week_pdf_redirects_to_setup(client):
    loc = _start_only(client)
    r = client.get(f"{loc}/week/1.pdf")
    assert r.status_code == 303 and r.headers["location"] == f"{loc}/setup"


def test_start_rate_limited_per_ip(client):
    for _ in range(5):
        _start_only(client)
    r = client.post("/start", data=FORM)
    assert r.status_code == 429
    # 다른 IP(Funnel이 넣어 주는 X-Forwarded-For)는 영향 없음
    assert client.post("/start", data=FORM, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 303


def test_without_stats_shows_preparing_not_500(client):
    app.dependency_overrides[get_stats] = lambda: None
    for path in ("/", "/start"):
        r = client.get(path)
        assert r.status_code == 200 and "준비 중" in r.text
    assert client.post("/start", data=FORM).status_code == 503


def test_report_before_30_days_shows_remaining(client):
    url = _start_and_setup(client)
    r = client.get(f"{url}/report")
    assert r.status_code == 200
    assert "30일 남았어요" in r.text


def test_report_unknown_token_404(client):
    assert client.get("/c/nope/report").status_code == 404


def test_seeded_demo_report(client):
    from app.clock import today_kst
    from scripts.seed_demo import seed

    with Session(client.engine) as db:
        token = seed(db, today_kst(), stats=STATS)
    r = client.get(f"/c/{token}/report")
    assert r.status_code == 200
    assert "30일 완주" in r.text or "30일이 지났어요" in r.text
    assert "다음 30일 도전하기" in r.text
    assert client.get(f"/c/{token}").status_code == 200


# --- 디자인 체계 ---
from app.pdf import DISCLAIMER

EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""", re.I)


def test_static_css_served(client):
    r = client.get("/static/app.css")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/css")
    for needle in ("#0ca678", "@view-transition", "prefers-reduced-motion"):
        assert needle in r.text


def test_head_has_icons_and_link_preview(client):
    page = client.get("/").text
    assert '<link rel="icon" href="/static/icons/favicon.svg" type="image/svg+xml">' in page
    assert '<link rel="apple-touch-icon" href="/static/icons/apple-touch-icon.png">' in page
    assert '<link rel="manifest" href="/static/manifest.webmanifest">' in page
    assert '<meta property="og:image" content="http://localhost:8000/static/icons/og.png">' in page
    assert '<meta property="og:title" content="Watchme · 30일 생활습관 챌린지">' in page
    for path in ("icons/favicon.svg", "icons/apple-touch-icon.png", "icons/icon-192.png", "icons/icon-512.png",
                 "icons/og.png", "manifest.webmanifest"):
        assert client.get(f"/static/{path}").status_code == 200


def test_static_urls_carry_content_version(client):
    from app.routes import ASSET_V
    page = client.get("/").text
    assert len(ASSET_V) == 8 and f"/static/app.css?v={ASSET_V}" in page and f"/static/flow.js?v={ASSET_V}" in page


def test_brand_shows_icon_on_every_page(client):
    assert '<img class="brand-icon" src="/static/icons/favicon.svg"' in client.get("/start").text


def test_pages_have_no_external_requests(client):
    for path in ("/", "/c/nope"):
        html = client.get(path).text
        assert not EXTERNAL.search(html), path
        assert "@import" not in html and "url(http" not in html


def test_error_page_uses_layout(client):
    r = client.get("/c/nope")
    assert r.status_code == 404
    assert "/static/app.css" in r.text and DISCLAIMER in r.text


# --- 맞춤 질문 ---
def test_setup_form_has_five_steps(client):
    loc = _start_only(client)
    r = client.get(f"{loc}/setup")
    assert r.status_code == 200
    assert r.text.count('<fieldset class="step"') == 5
    for name in ("diet_style", "lunch_place", "breakfast", "exercise_min", "free_days"):
        assert f'name="{name}"' in r.text


def test_setup_choices_avoid_card_list_class(client):
    # 기록 화면 카드용 .list(여백·첫 항목 위 테두리 제거)가 선택지에 걸리면 첫 상자 위가 잘려 보인다
    loc = _start_only(client)
    page = client.get(f"{loc}/setup").text
    assert 'class="pick list"' not in page and 'class="pick stack"' in page


def test_setup_saves_and_redirects(client):
    loc = _start_only(client)
    r = client.post(f"{loc}/setup", data=SETUP)
    assert r.status_code == 303 and r.headers["location"] == f"{loc}/ready"
    assert client.get(loc).status_code == 200
    # 한 번 정하면 끝: 다시 열면 기록 화면으로
    assert client.get(f"{loc}/setup").headers["location"] == loc


@pytest.mark.parametrize("bad", [
    {"diet_style": "x"}, {"free_days": ["2"]}, {"free_days": ["1", "2", "3"]}, {"free_days": ["3", "3"]},
    {"free_days": ["a", "1"]}, {"exercise_min": "abc"}, {"exercise_min": "30"},
])
def test_setup_bad_values_400(client, bad):
    loc = _start_only(client)
    r = client.post(f"{loc}/setup", data=SETUP | bad)
    assert r.status_code == 400
    assert 'class="error"' in r.text and 'name="free_days"' in r.text
    assert client.get(loc).status_code == 303  # 저장 안 됨


def test_setup_unknown_token_404(client):
    assert client.get("/c/nope/setup").status_code == 404
    assert client.post("/c/nope/setup", data=SETUP).status_code == 404


def test_pages_redirect_to_setup_until_done(client):
    loc = _start_only(client)
    for r in (client.get(loc), client.get(f"{loc}/report"), client.get(f"{loc}/week/1.pdf"),
              client.get(f"{loc}/ready"), client.post(f"{loc}/day/1", data={"kept": "1"})):
        assert r.status_code == 303 and r.headers["location"] == f"{loc}/setup"


def test_ready_page_cheers_warns_and_moves_on_to_day_1(client):
    loc = _start_and_setup(client)
    r = client.get(f"{loc}/ready")
    assert r.status_code == 200
    assert "30일 챌린지" in r.text and "같이 힘내" in r.text
    assert "의료진" in r.text and "의학적 진단이 아니에요" in r.text
    assert f'http-equiv="refresh" content="6;url={loc}"' in r.text  # JS 없이도 Day 1로
    assert f'href="{loc}"' in r.text
    assert client.get("/c/nope/ready").status_code == 404


def test_privacy_notice_lists_setup_answers(client):
    assert PRIVACY in client.get("/start").text


# --- 기록 화면 ---
from datetime import timedelta

from markupsafe import escape

from app.clock import today_kst
from app.models import Trial
from app.plan import build_plan
from app.service import get_decisions, profile_of


def _set_day(client, loc, n):
    """체험 시작일을 옮겨 오늘을 n일째로 만든다."""
    with Session(client.engine) as s:
        trial = s.get(Trial, loc.rsplit("/", 1)[1])
        trial.start_date = today_kst() - timedelta(days=n - 1)
        s.commit()


def _plan(client, loc):
    token = loc.rsplit("/", 1)[1]
    with Session(client.engine) as s:
        trial = s.get(Trial, token)
        return build_plan(profile_of(trial), trial.start_date, token, get_decisions(s, token))


def _log(client, loc, day, kept=True, weight=""):
    assert client.post(f"{loc}/day/{day}", data={"kept": "1" if kept else "0", "weight_kg": weight}).status_code == 303


def test_check_shows_today_plan_tip_and_streak(client):
    loc = _start_and_setup(client)
    day1 = _plan(client, loc)[0]
    r = client.get(loc)
    assert r.status_code == 200 and "Day 1" in r.text
    assert str(escape(day1.meals["breakfast"])) in r.text and str(escape(day1.tip)) in r.text
    _set_day(client, loc, 3)
    _log(client, loc, 1)
    _log(client, loc, 2)
    assert "2일 연속" in client.get(loc).text


def test_free_meal_day_highlighted(client):
    # 오늘 요일을 자유 한 끼로 고르면 오늘(Day 1) 저녁이 자유 한 끼
    wd = today_kst().weekday()
    loc = _start_only(client)
    client.post(f"{loc}/setup", data=SETUP | {"free_days": [str(wd), str((wd + 1) % 7)]})
    r = client.get(loc)
    assert "자유 한 끼" in r.text and "국물·소스는 남기기" in r.text


def _plateau_week(client, loc, week, weights=("80.0", "80.3")):
    _set_day(client, loc, 7 * week)
    for d in range(7 * week - 6, 7 * week + 1):
        w = weights[0] if d == 7 * week - 6 else weights[1] if d == 7 * week else ""
        _log(client, loc, d, True, w)


def test_plateau_card(client):
    loc = _start_and_setup(client)
    _plateau_week(client, loc, 1)
    assert "정체는 흔해요" in client.get(loc).text
    loc2 = _start_and_setup(client)
    _plateau_week(client, loc2, 1, weights=("80.0", "79.4"))
    assert "정체는 흔해요" not in client.get(loc2).text


def _set_variant(client, loc, variant):
    with Session(client.engine) as s:
        s.get(Trial, loc.rsplit("/", 1)[1]).plan_variant = variant
        s.commit()


def test_week_summary_and_level_up(client):
    loc = _start_and_setup(client)
    _set_variant(client, loc, "overweight")  # high_risk는 식사 notes가 없음
    _plateau_week(client, loc, 1)
    r = client.get(loc)
    assert "1주차 요약" in r.text and f'action="{loc}/week/1/level"' in r.text
    assert client.post(f"{loc}/week/1/level", data={"choice": "up"}).status_code == 303
    _set_day(client, loc, 9)
    n = 9 if _plan(client, loc)[7].free_meal else 8  # 자유 한 끼(수·토) 저녁엔 메모가 없어서, 아닌 날을 본다
    r = client.get(f"{loc}?day={n}")
    assert "강도 1단계" in r.text and "밥은 1/3 공기" in r.text
    assert f'action="{loc}/week/1/level"' not in r.text  # 이미 정함


def test_level_post_rejected_cases(client):
    loc = _start_and_setup(client)
    _plateau_week(client, loc, 1)
    assert client.post(f"{loc}/week/1/level", data={"choice": "sideways"}).status_code == 400
    assert client.post(f"{loc}/week/2/level", data={"choice": "up"}).status_code == 400  # 아직 안 온 주
    assert client.post(f"{loc}/week/1/level", data={"choice": "up"}).status_code == 303
    assert client.post(f"{loc}/week/1/level", data={"choice": "up"}).status_code == 400  # 두 번째
    _plateau_week(client, loc, 2)
    assert client.post(f"{loc}/week/2/level", data={"choice": "up"}).status_code == 303
    routes.DAY_PER_IP.hits.clear()  # 기록 저장이 많아 분당 제한을 비움
    _plateau_week(client, loc, 3)
    assert client.post(f"{loc}/week/3/level", data={"choice": "up"}).status_code == 400  # 최대 2단계
    token = loc.rsplit("/", 1)[1]
    with Session(client.engine) as s:
        assert get_decisions(s, token) == {1: 1, 2: 2}
    routes.DAY_PER_IP.hits.clear()
    other = _start_and_setup(client)
    _plateau_week(client, other, 1, weights=("80.0", "79.0"))
    assert client.post(f"{other}/week/1/level", data={"choice": "up"}).status_code == 400  # 정체 아님
    assert client.post("/c/nope/week/1/level", data={"choice": "up"}).status_code == 404


def test_no_weights_week_summary(client):
    loc = _start_and_setup(client)
    _set_day(client, loc, 7)
    _log(client, loc, 7)
    r = client.get(loc)
    assert r.status_code == 200 and "1주차 요약" in r.text and "체중 기록 없음" in r.text


# --- 30일 리포트 ---
from app.service import save_day


def _finished(client, kept, weights=None):
    loc = _start_and_setup(client)
    _set_day(client, loc, 31)
    token = loc.rsplit("/", 1)[1]
    with Session(client.engine) as s:
        for d in range(1, 31):
            save_day(s, token, d, d <= kept, (weights or {}).get(d))
    return loc


@pytest.mark.parametrize("kept,copy", [
    (25, "30일 완주! 25일을 지켰어요 🎉"), (15, "30일 완주! 15일을 지켰어요"), (5, "30일이 지났어요. 5일을 지켰어요"),
])
def test_report_completion_copy(client, kept, copy):
    r = client.get(f"{_finished(client, kept, {1: 80.0, 30: 78.5})}/report")
    assert r.status_code == 200 and copy in r.text
    assert "-1.5kg" in r.text or "−1.5kg" in r.text
    if kept < 24:
        assert "🎉</h1>" not in r.text


def test_report_plateau_line(client):
    r = client.get(f"{_finished(client, 30, {24: 80.0, 30: 80.2})}/report")
    assert "정체" in r.text
    r2 = client.get(f"{_finished(client, 30, {24: 80.0, 30: 79.0})}/report")
    assert "정체" not in r2.text


def test_report_without_weights(client):
    r = client.get(f"{_finished(client, 20)}/report")
    assert r.status_code == 200 and "체중 기록이 없어요" in r.text


def test_self_hosted_fonts(client):
    css = client.get("/static/app.css").text
    for w in ("Regular", "SemiBold", "Bold", "ExtraBold"):
        path = f"/static/fonts/Pretendard-{w}.subset.woff2"
        assert path in css
        r = client.get(path)
        assert r.status_code == 200 and r.content[:4] == b"wOF2"


def test_average_is_labeled_by_age_and_sex(client):
    assert "40대 남성 평균" in client.get("/").text  # 예시 인물 45세 남성
    loc = _start_and_setup(client)  # FORM: 45세 남성
    assert "40대 남성 평균" in client.get(f"{loc}/result").text
    assert "40대 남성 평균" in client.get(loc).text
    rep = client.get(f"{_finished(client, 20, {1: 80.0, 30: 79.0})}/report").text
    assert "40대 남성 평균" in rep
    for html in (client.get("/").text, rep):
        assert "한국인 평균" not in html.replace("40대 남성 평균", "")


def test_next_before_30_days_400(client):
    loc = _start_and_setup(client)
    assert client.post(f"{loc}/next").status_code == 400


def test_next_twice_same_trial(client):
    loc = _finished(client, 20, {30: 78.5})
    with Session(client.engine) as s:
        before = len(s.scalars(select(Trial)).all())
    r1, r2 = client.post(f"{loc}/next"), client.post(f"{loc}/next")
    assert r1.status_code == 303 and r1.headers["location"].endswith("/ready")
    assert r1.headers["location"] == r2.headers["location"] != f"{loc}/ready"
    with Session(client.engine) as s:
        assert len(s.scalars(select(Trial)).all()) == before + 1
    assert client.get(r1.headers["location"]).status_code == 200
    rep = client.get(f"{loc}/report").text
    assert "다음 도전 이어 가기" in rep


def test_report_card_has_next_button(client):
    rep = client.get(f"{_finished(client, 20)}/report").text
    assert "다음 30일 도전하기" in rep and "곧 오픈" not in rep


def test_past_day_view_is_clearly_marked(client):
    loc = _start_and_setup(client)
    _set_day(client, loc, 2)
    page = client.get(f"{loc}?day=1").text
    assert '<h1 class="day">Day 1</h1>' in page
    assert "지난 기록을 고치는 중" in page and f'href="{loc}"' in page and "오늘(Day 2)로 돌아가기" in page
    today = client.get(loc).text
    assert '<h1 class="day">Day 2</h1>' in today and "지난 기록을 고치는 중" not in today


def test_saving_past_day_stays_on_that_day(client):
    loc = _start_and_setup(client)
    _set_day(client, loc, 2)
    r = client.post(f"{loc}/day/1", data={"kept": "1", "weight_kg": ""})
    assert r.headers["location"] == f"{loc}?day=1"
    assert "✅ 지켰어요" in client.get(r.headers["location"]).text
    assert client.post(f"{loc}/day/2", data={"kept": "1", "weight_kg": ""}).headers["location"] == loc


def test_pages_are_light_only(client):
    css = client.get("/static/app.css").text
    assert "prefers-color-scheme" not in css and "color-scheme: only light" in css
    assert '<meta name="color-scheme" content="only light">' in client.get("/").text


def test_check_screen_is_compact(client):
    loc = _start_and_setup(client)
    page = client.get(loc).text
    assert "<b>아침</b>" not in page and "지난 날짜를 누르면" not in page and "오늘의 팁" not in page
    assert '<span class="chip">' in page.split('<main', 1)[0]  # 계획 이름은 제목 밑 칩
    assert "<details" in page and "참고 위험도" in page


def test_landing_story_works_without_js(client):
    page = client.get("/").text
    assert page.count('<section class="scene') == 4  # 테스트 기본은 카카오 꺼짐
    assert 'class="story"' in page and '<script src="/static/story.js?v=' in page
    assert "지금 내 위험도부터" in page and 'href="/start"' in page
    assert " hidden" not in page.split('class="story"', 1)[1].split("</main>", 1)[0]  # 숨김은 JS가 붙이는 .js 클래스로만


def test_landing_without_kakao_has_four_scenes(client):
    page = client.get("/").text
    assert "나와의 채팅" not in page and "카카오로 이어서 하기" not in page
    assert page.count('class="seg"') == 4


def test_landing_has_no_tap_overlay(client):
    # 화면 전체를 덮는 버튼이 있으면 작은 폰에서 넘친 장면을 스크롤할 수 없다
    assert 'class="tap"' not in client.get("/").text


def test_landing_calendar_matches_demo_plan(client):
    from app.clock import today_kst
    from app.plan import Profile, build_plan, choose_variant
    from app.risk import assess
    plan = build_plan(Profile(choose_variant(assess(*routes.EXAMPLE, stats=STATS)), "mixed", "out", "light", 25, (5, 6)),
                      today_kst(), "landing-demo")
    page = client.get("/").text
    cal = page.split('<div class="cal"', 1)[1].split("</div>", 1)[0]
    free = [int(m) for m in re.findall(r'class="free">(\d+)<', cal)]
    assert free == [d.day for d in plan if d.free_meal] and len(free) == 8


def test_manifest_keeps_users_on_their_own_page(client):
    import json
    m = json.loads(client.get("/static/manifest.webmanifest").text)
    assert "start_url" not in m and "display" not in m  # 개인 링크(/c/토큰)에서 홈 화면에 추가하면 그 링크로 열려야 한다


def test_landing_preparing_keeps_simple_card(client):
    app.dependency_overrides[get_stats] = lambda: None
    page = client.get("/").text
    assert "준비 중" in page and 'class="story"' not in page and 'href="/start"' not in page


def test_landing_and_result_are_compact(client):
    page = client.get("/").text
    assert '<details class="card fold"><summary>🔒 이름·연락처는 받지 않아요</summary>' in page and PRIVACY in page
    loc = _start_only(client)
    page = client.get(f"{loc}/result").text
    assert "다음은 생활 질문 5개예요" not in page and "질문 5개로 맞춤 계획" in page


def _views(client):
    from app.clock import today_kst
    from app.models import LandingView
    with Session(client.engine) as s:
        row = s.get(LandingView, today_kst())
        return row.count if row else 0


def test_landing_counts_view_but_not_bots(client):
    assert client.get("/", headers={"user-agent": "Mozilla/5.0"}).status_code == 200
    assert _views(client) == 1
    assert client.get("/", headers={"user-agent": "kakaotalk-scrap/1.0"}).status_code == 200
    assert _views(client) == 1


def test_landing_survives_counter_error(client, monkeypatch):
    def boom(*a):
        raise RuntimeError("no table")
    monkeypatch.setattr(routes, "count_landing", boom)
    assert client.get("/", headers={"user-agent": "Mozilla/5.0"}).status_code == 200


def test_landing_hero_counts_up_real_sample_size(client):
    import copy
    stats = copy.deepcopy(STATS)
    for sex in stats["groups"].values():
        for g in sex.values():
            g["n"] = 1234
    app.dependency_overrides[get_stats] = lambda: stats
    page = client.get("/").text
    n = 1234 * sum(len(sex) for sex in stats["groups"].values())
    assert '<svg class="ecg"' in page
    assert f'data-count="{n}">{n:,}</b>명' in page  # JS가 없어도 최종 숫자
    assert "국민건강영양조사 성인 기준" in page


def test_landing_example_scene_says_birth_year(client):
    assert "성별·출생연도·키·몸무게만" in client.get("/").text


def test_landing_example_is_ring_gauges(client):
    from app.risk import assess, vs_text

    a = assess(*routes.EXAMPLE, stats=STATS)
    page = client.get("/").text
    assert len(re.findall(r'class="gauge( lo)?"', page)) == 2 and '<div class="bar"' not in page.split('<main', 1)[1]
    for vs in (a.hypertension_vs_avg, a.diabetes_vs_avg):
        pct = abs(round((vs - 1) * 100))
        assert f'aria-label="{vs_text(vs)}"' in page
        assert f'data-count="{pct}">{pct}</span>%' in page  # JS가 없어도 최종 숫자
