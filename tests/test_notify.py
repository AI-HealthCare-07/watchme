import json
from datetime import UTC, date, datetime, time, timedelta

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
AM, PM = time(7, 30), time(21, 0)  # 기본 발송 시각


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
    send_all(db, "morning", TODAY, AM)
    if expect is None:
        assert sent == []
    else:
        assert len(sent) == 1 and expect in sent[0][1]
        assert sent[0][2].endswith(f"/c/{t.token}/report" if n == 31 else f"/c/{t.token}")


def test_morning_applies_ai_exclusion(db, monkeypatch):  # noqa: F811
    from app.models import AiPick
    from app.service import plan_for
    sent = kakao_ok(monkeypatch)
    t = linked_trial(db, 1)
    gone = plan_for(db, t)[0].meals["breakfast"]
    db.add(AiPick(token=t.token, request="r", excluded=json.dumps([gone]), reason="x", status="ok"))
    db.commit()
    send_all(db, "morning", TODAY, AM)
    assert gone[:20] not in sent[0][1]


def test_evening_skips_day31_and_uses_logged_copy(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    linked_trial(db, 31, kakao_id=1, refresh="r1")
    t = linked_trial(db, 5, kakao_id=2, refresh="r2")
    save_day(db, t.token, 5, True, None)
    assert send_all(db, "evening", TODAY, PM) == (1, 0)
    assert "기록 고마워요" in sent[0][1]


def test_run_twice_sends_once(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    linked_trial(db, 3)
    assert send_all(db, "morning", TODAY, AM) == (1, 0)
    assert send_all(db, "morning", TODAY, AM) == (0, 0)
    assert len(sent) == 1


def test_latest_trial_only(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    now = datetime.now(UTC)
    linked_trial(db, 31, created=now - timedelta(days=30))
    linked_trial(db, 1, created=now)
    assert send_all(db, "morning", TODAY, AM) == (1, 0)
    assert sent[0][1].split("\n")[0] == "Day 1 · 오늘 계획"


def test_auth_error_marks_dead_and_continues(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch, bad_tokens={"r1"})
    linked_trial(db, 3, kakao_id=1, refresh="r1")
    linked_trial(db, 3, kakao_id=2, refresh="r2")
    assert send_all(db, "morning", TODAY, AM) == (1, 1)
    dead = db.get(KakaoAccount, 1)
    assert dead.can_message is False and dead.refresh_token_enc is None
    assert sent[0][0] == "Bearer a-r2"


def test_undecryptable_token_marks_dead_and_continues(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    linked_trial(db, 3, kakao_id=1, refresh="r1")
    linked_trial(db, 3, kakao_id=2, refresh="r2")
    db.get(KakaoAccount, 1).refresh_token_enc = "made-with-an-old-TOKEN_KEY"
    db.commit()
    assert send_all(db, "morning", TODAY, AM) == (1, 1)
    assert db.get(KakaoAccount, 1).can_message is False
    assert sent[0][0] == "Bearer a-r2"


def test_kakao_5xx_continues_to_next_account(db, monkeypatch):  # noqa: F811
    sent = []

    def handler(r):
        if r.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": f"a-{form_of(r)['refresh_token']}"})
        if r.headers["authorization"] == "Bearer a-r1":
            return httpx.Response(500, text="down")
        sent.append(r.headers["authorization"])
        return httpx.Response(200, json={"result_code": 0})

    fake_kakao(monkeypatch, handler)
    linked_trial(db, 3, kakao_id=1, refresh="r1")
    linked_trial(db, 3, kakao_id=2, refresh="r2")
    assert send_all(db, "morning", TODAY, AM) == (1, 1)
    assert sent == ["Bearer a-r2"] and db.get(KakaoAccount, 1).can_message is True


def test_new_refresh_token_saved(db, monkeypatch):  # noqa: F811
    kakao_ok(monkeypatch, refresh_body={"access_token": "a", "refresh_token": "r2"})
    linked_trial(db, 3)
    send_all(db, "morning", TODAY, AM)
    assert kakao.decrypt(db.get(KakaoAccount, 42).refresh_token_enc) == "r2"


def test_notify_off_and_setup_not_done_skipped(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    linked_trial(db, 3, kakao_id=1, refresh="r1")
    accounts.set_notify(db, 1, False)
    linked_trial(db, 3, kakao_id=2, refresh="r2", setup=False)
    assert send_all(db, "morning", TODAY, AM) == (0, 0)
    assert sent == []


@pytest.mark.parametrize("n, path", [(8, "/week/1"), (15, "/week/2"), (29, "/week/4")])
def test_morning_week_report_days(db, monkeypatch, n, path):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    t = linked_trial(db, n)
    send_all(db, "morning", TODAY, AM)
    assert len(sent) == 1 and "주차 리포트" in sent[0][1] and "오늘 계획" not in sent[0][1]
    assert sent[0][2].endswith(f"/c/{t.token}{path}")
    send_all(db, "morning", TODAY, AM)
    assert len(sent) == 1


def test_one_broken_message_does_not_stop_the_run(db, monkeypatch):  # noqa: F811
    from app import notify
    sent = kakao_ok(monkeypatch)
    bad = linked_trial(db, 8, kakao_id=1, refresh="r1")
    linked_trial(db, 8, kakao_id=2, refresh="r2")
    real = notify.build_week

    def boom(db_, trial, *a):
        if trial.token == bad.token:
            raise RuntimeError("broken")
        return real(db_, trial, *a)

    monkeypatch.setattr(notify, "build_week", boom)
    assert send_all(db, "morning", TODAY, AM) == (1, 1)
    assert len(sent) == 1 and "r2" in sent[0][0]


def test_sends_only_to_accounts_in_this_slot(db, monkeypatch):  # noqa: F811
    sent = kakao_ok(monkeypatch)
    linked_trial(db, 3)
    accounts.set_times(db, 42, time(6, 0), time(22, 30))
    assert send_all(db, "morning", TODAY, AM) == (0, 0)
    assert send_all(db, "evening", TODAY, PM) == (0, 0)
    assert send_all(db, "morning", TODAY, time(6, 0)) == (1, 0)
    assert send_all(db, "evening", TODAY, time(22, 30)) == (1, 0)
    assert len(sent) == 2


def test_changing_time_same_day_does_not_resend(db, monkeypatch):  # noqa: F811
    kakao_ok(monkeypatch)
    linked_trial(db, 3)
    assert send_all(db, "morning", TODAY, AM) == (1, 0)
    accounts.set_times(db, 42, time(8, 0), time(21, 0))
    assert send_all(db, "morning", TODAY, time(8, 0)) == (0, 0)
