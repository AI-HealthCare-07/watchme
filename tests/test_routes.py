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


def _start(client):
    r = client.post("/start", data=FORM)
    assert r.status_code == 303
    return r.headers["location"]


def test_start_form_has_notice(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "수집 항목" in r.text


def test_start_redirects_to_check_page(client):
    loc = _start(client)
    assert loc.startswith("/c/")
    r = client.get(loc)
    assert r.status_code == 200
    assert "의학적 진단이 아닙니다" in r.text


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
    loc = _start(client)
    assert client.post(f"{loc}/day/1", data={"kept": "1", "weight_kg": "80.2"}).status_code == 303
    assert client.post(f"{loc}/day/1", data={"kept": "0", "weight_kg": ""}).status_code == 303
    with Session(client.engine) as s:
        rows = s.scalars(select(DayLog)).all()
    assert len(rows) == 1 and rows[0].kept is False and rows[0].weight_kg is None


@pytest.mark.parametrize("day,data", [(31, {"kept": "1"}), (0, {"kept": "1"}), (2, {"kept": "1"}), (1, {"kept": "1", "weight_kg": "abc"})])
def test_bad_day_post_is_400(client, day, data):
    # day 2는 아직 오지 않은 날(시작 당일은 day 1)
    loc = _start(client)
    assert client.post(f"{loc}/day/{day}", data=data).status_code == 400


def test_pdf_uses_public_base_url(client, monkeypatch):
    loc = _start(client)
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
    r = client.get(f"{_start(client)}/plan.pdf")
    assert r.content.startswith(b"%PDF")


def test_start_rate_limited_per_ip(client):
    for _ in range(5):
        _start(client)
    r = client.post("/start", data=FORM)
    assert r.status_code == 429
    # 다른 IP(Funnel이 넣어 주는 X-Forwarded-For)는 영향 없음
    assert client.post("/start", data=FORM, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 303


def test_without_stats_shows_preparing_not_500(client):
    app.dependency_overrides[get_stats] = lambda: None
    r = client.get("/")
    assert r.status_code == 200 and "준비 중" in r.text
    assert client.post("/start", data=FORM).status_code == 503


def test_report_before_30_days_shows_remaining(client):
    url = _start(client)
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
