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
from app.risk import get_stats
from tests.test_risk import STATS

FORM = {"sex": "M", "age": "45", "height_cm": "170", "weight_kg": "80"}


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
           "일일 체크 기록. 이름·연락처는 받지 않아요. 보관: 체험 종료 후 90일.")


def _start_only(client):
    r = client.post("/start", data=FORM)
    assert r.status_code == 303
    return r.headers["location"].removesuffix("/result")


def _start_and_setup(client):
    loc = _start_only(client)
    r = client.post(f"{loc}/setup", data=SETUP)
    assert r.status_code == 303 and r.headers["location"] == loc
    return loc


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
    for name in ("sex", "age", "height_cm", "weight_kg"):
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


def test_result_unknown_token_404(client):
    assert client.get("/c/nope/result").status_code == 404


@pytest.mark.parametrize("field,value", [("age", "0"), ("age", "abc"), ("height_cm", ""), ("sex", "")])
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

    def fake_render(a, plan, points, check_url, label):
        seen["url"] = check_url
        return b"%PDF-fake"

    monkeypatch.setattr(routes, "render_pdf", fake_render)
    monkeypatch.setattr(routes, "PUBLIC_BASE_URL", "https://public.example")
    r = client.get(f"{loc}/plan.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert r.headers["content-type"] == "application/pdf"
    assert seen["url"] == f"https://public.example{loc}"


def test_real_pdf_renders(client):
    r = client.get(f"{_start_and_setup(client)}/plan.pdf")
    assert r.content.startswith(b"%PDF")


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
    assert "30일 결과" in r.text
    assert "카카오톡" in r.text
    assert client.get(f"/c/{token}").status_code == 200


# --- 디자인 체계 ---
from app.pdf import DISCLAIMER

EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""", re.I)


def test_static_css_served(client):
    r = client.get("/static/app.css")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/css")
    for needle in ("#0ca678", "@view-transition", "prefers-reduced-motion"):
        assert needle in r.text


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


def test_setup_saves_and_redirects(client):
    loc = _start_only(client)
    r = client.post(f"{loc}/setup", data=SETUP)
    assert r.status_code == 303 and r.headers["location"] == loc
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
    for r in (client.get(loc), client.get(f"{loc}/report"), client.get(f"{loc}/plan.pdf"),
              client.post(f"{loc}/day/1", data={"kept": "1"})):
        assert r.status_code == 303 and r.headers["location"] == f"{loc}/setup"


def test_privacy_notice_lists_setup_answers(client):
    assert PRIVACY in client.get("/start").text
