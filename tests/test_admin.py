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
