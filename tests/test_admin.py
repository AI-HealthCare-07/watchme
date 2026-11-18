from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TestTrial
from tests.test_routes import FORM, client  # noqa: F401

KEY = "k" * 32


def _login(client):
    r = client.get(f"/admin?key={KEY}")
    assert r.status_code == 303
    return r


def _marks(client):
    with Session(client.engine) as s:
        return set(s.scalars(select(TestTrial.token)))


def test_admin_off_without_key(client, monkeypatch):
    monkeypatch.delenv("ADMIN_KEY", raising=False)
    assert client.get("/admin").status_code == 404
    r = client.get("/admin?key=")
    assert r.status_code == 404 and "set-cookie" not in r.headers


def test_admin_blank_key_env_stays_off(client, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "  ")
    r = client.get("/admin?key=")
    assert r.status_code == 404 and "set-cookie" not in r.headers


def test_admin_login_sets_cookie_and_strips_key(client, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", KEY)
    r = _login(client)
    assert r.headers["location"] == "/admin"
    assert "wm_admin=" in r.headers["set-cookie"] and KEY not in r.headers["set-cookie"]
    r = client.get("/admin")
    assert r.status_code == 200
    assert "no-store" in r.headers["cache-control"] and r.headers["x-robots-tag"] == "noindex"


def test_admin_wrong_key_404_then_rate_limited(client, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", KEY)
    for _ in range(10):
        r = client.get("/admin?key=nope")
        assert r.status_code == 404 and "set-cookie" not in r.headers
    assert client.get("/admin?key=nope").status_code == 429


def test_admin_without_cookie_404(client, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", KEY)
    r = client.get("/admin")
    assert r.status_code == 404 and r.headers["x-robots-tag"] == "noindex"


def test_admin_started_trial_marked_test(client, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", KEY)
    _login(client)
    mine = client.post("/start", data=FORM).headers["location"].split("/")[2]
    client.cookies.clear()
    real = client.post("/start", data=FORM).headers["location"].split("/")[2]
    assert _marks(client) == {mine}
    assert real != mine


def _seed_receiving(client, n, monkeypatch):
    from cryptography.fernet import Fernet

    from app import accounts
    from app.clock import today_kst
    from app.service import start_trial
    from tests.test_risk import STATS
    monkeypatch.setenv("TOKEN_KEY", Fernet.generate_key().decode())
    with Session(client.engine) as s:
        for kid in range(1, n + 1):
            t = start_trial(s, "M", 40, 170, 80, today=today_kst(), stats=STATS)
            accounts.save_account(s, kid, "r", True)
            accounts.link(s, t.token, kid)


def test_admin_page_shows_kakao_count_first(client, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", KEY)
    _seed_receiving(client, 2, monkeypatch)
    _login(client)
    html = client.get("/admin").text
    assert html.index("지금 카톡 알림 받는 사람") < html.index("단계별 전환")
    h1 = html[html.index("<h1"):html.index("</h1>")]
    assert ">2<" in h1 or ">2 " in h1 or "2명" in h1


def test_admin_page_empty_db_renders(client, monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", KEY)
    _login(client)
    r = client.get("/admin")
    assert r.status_code == 200
    assert "아직 없음" in r.text and "기록 없음" in r.text
    table = r.text[r.text.index('class="mtable daily"'):]
    table = table[:table.index("</table>")]
    assert table.count("<tr") - 1 == 30


def test_admin_page_shows_send_failures(client, monkeypatch):
    from app.clock import today_kst
    from app.metrics import record_run
    monkeypatch.setenv("ADMIN_KEY", KEY)
    with Session(client.engine) as s:
        record_run(s, today_kst(), "morning", 5, 2)
    _login(client)
    html = client.get("/admin").text
    sends = html[html.index("카톡 발송"):]
    assert ">5<" in sends and 'class="bad"' in sends
