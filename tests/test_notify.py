import json
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from app import accounts, kakao
from app.models import KakaoAccount
from app.notify import send_all
from app.service import save_day, save_setup, start_trial
from tests.test_accounts import db  # noqa: F401  (fixture)
from tests.test_kakao import fake_kakao, form_of, kakao_env  # noqa: F401  (fixture)
from tests.test_risk import STATS

TODAY = date(2026, 11, 18)  # 수요일


def kakao_ok(monkeypatch, refresh_body=None, bad_tokens=()):
    """refresh → access 토큰(리프레시 토큰 이름 그대로), memo → 200. 보낸 (토큰, text, url) 목록."""
    sent = []

    def handler(r):
        if r.url.path == "/oauth/token":
            rt = form_of(r)["refresh_token"]
            if rt in bad_tokens:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json=refresh_body or {"access_token": f"a-{rt}"})
        tpl = json.loads(form_of(r)["template_object"])
        sent.append((r.headers["authorization"], tpl["text"], tpl["link"]["web_url"]))
        return httpx.Response(200, json={"result_code": 0})

    fake_kakao(monkeypatch, handler)
    return sent


def linked_trial(db, n, kakao_id=42, refresh="r42", setup=True, created=None):  # noqa: F811
    t = start_trial(db, "M", 45, 170, 80, today=TODAY - timedelta(days=n - 1), stats=STATS)
    if setup:
        save_setup(db, t.token, "mixed", "out", "light", 25, [2, 5])
    if created:
        t.created_at = created
        db.commit()
    accounts.save_account(db, kakao_id, refresh, True)
    accounts.link(db, t.token, kakao_id)
    return t


@pytest.mark.parametrize("n, expect", [(0, None), (1, "Day 1 · 오늘 계획"), (30, "Day 30 · 오늘 계획"),
                                       (31, "완주"), (32, None)])
def test_morning_day1_and_report_day31(db, monkeypatch, n, expect):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    t = linked_trial(db, n)
    send_all(db, "morning", TODAY)
    if expect is None:
        assert sent == []
    else:
        assert len(sent) == 1 and expect in sent[0][1]
        assert sent[0][2].endswith(f"/c/{t.token}/report" if n == 31 else f"/c/{t.token}")


def test_evening_skips_day31_and_uses_logged_copy(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    linked_trial(db, 31, kakao_id=1, refresh="r1")
    t = linked_trial(db, 5, kakao_id=2, refresh="r2")
    save_day(db, t.token, 5, True, None)
    assert send_all(db, "evening", TODAY) == (1, 0)
    assert "기록 고마워요" in sent[0][1]


def test_run_twice_sends_once(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    linked_trial(db, 3)
    assert send_all(db, "morning", TODAY) == (1, 0)
    assert send_all(db, "morning", TODAY) == (0, 0)
    assert len(sent) == 1


def test_latest_trial_only(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    now = datetime.now(UTC)
    linked_trial(db, 31, created=now - timedelta(days=30))
    linked_trial(db, 1, created=now)
    assert send_all(db, "morning", TODAY) == (1, 0)
    assert sent[0][1].split("\n")[0] == "Day 1 · 오늘 계획"


def test_auth_error_marks_dead_and_continues(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch, bad_tokens={"r1"})
    linked_trial(db, 3, kakao_id=1, refresh="r1")
    linked_trial(db, 3, kakao_id=2, refresh="r2")
    assert send_all(db, "morning", TODAY) == (1, 1)
    dead = db.get(KakaoAccount, 1)
    assert dead.can_message is False and dead.refresh_token_enc is None
    assert sent[0][0] == "Bearer a-r2"


def test_new_refresh_token_saved(db, monkeypatch):  # noqa: F811
    kakao_ok(monkeypatch, refresh_body={"access_token": "a", "refresh_token": "r2"})
    linked_trial(db, 3)
    send_all(db, "morning", TODAY)
    assert kakao.decrypt(db.get(KakaoAccount, 42).refresh_token_enc) == "r2"


def test_notify_off_and_setup_not_done_skipped(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    linked_trial(db, 3, kakao_id=1, refresh="r1")
    accounts.set_notify(db, 1, False)
    linked_trial(db, 3, kakao_id=2, refresh="r2", setup=False)
    assert send_all(db, "morning", TODAY) == (0, 0)
    assert sent == []
