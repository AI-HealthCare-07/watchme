from datetime import date, timedelta

from sqlalchemy import select

from app.metrics import count_landing, is_bot, record_run
from app.models import LandingView, SendRun
from tests.test_service import db  # noqa: F401

D = date(2026, 11, 18)


def test_is_bot():
    assert is_bot("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)") is False
    for ua in ("kakaotalk-scrap/1.0", "facebookexternalhit/1.1", "", "Googlebot/2.1"):
        assert is_bot(ua) is True


def test_count_landing_adds_per_day(db):
    count_landing(db, "Mozilla/5.0", D)
    count_landing(db, "Mozilla/5.0", D)
    count_landing(db, "Mozilla/5.0", D + timedelta(days=1))
    count_landing(db, "Googlebot/2.1", D)
    assert db.get(LandingView, D).count == 2
    assert db.get(LandingView, D + timedelta(days=1)).count == 1


def test_record_run_accumulates(db):
    record_run(db, D, "morning", 3, 1)
    record_run(db, D, "morning", 3, 1)
    record_run(db, D, "evening", 1, 0)
    m = db.get(SendRun, (D, "morning"))
    assert (m.sent, m.failed) == (6, 2)
    assert db.get(SendRun, (D, "evening")).sent == 1
    assert len(db.scalars(select(SendRun)).all()) == 2


# --- collect ---
from datetime import datetime  # noqa: E402

import pytest  # noqa: E402

from app import accounts  # noqa: E402
from app.metrics import collect  # noqa: E402
from app.models import TestTrial, Trial  # noqa: E402
from app.service import save_day, save_setup  # noqa: E402
from tests.test_service import GOOD_SETUP, _start  # noqa: E402


@pytest.fixture
def token_key(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("TOKEN_KEY", Fernet.generate_key().decode())


def _trial(db, created=datetime(2026, 11, 18, 1, 0), start=D, setup=False):
    t = _start(db, today=start)
    t.created_at = created
    db.commit()
    if setup:
        save_setup(db, t.token, **GOOD_SETUP)
    return t.token


def _account(db, kid, token, can=True, notify=True):
    accounts.save_account(db, kid, "r", can)
    accounts.link(db, token, kid)
    if not notify:
        accounts.set_notify(db, kid, False)


def test_collect_empty_db_is_all_zero(db):
    m = collect(db, D, None)
    assert m.kakao == m.kakao.__class__(0, 0, 0, 0, 0)
    assert len(m.daily) == 30 and m.daily[0].day == D and m.daily[-1].day == D - timedelta(days=29)
    assert all((r.views, r.starts, r.setups, r.links, r.checkers) == (0, 0, 0, 0, 0) for r in m.daily)
    assert [s.pct for s in m.funnel] == [None, None, None, None]
    assert [(r.day, r.kept, r.eligible) for r in m.retention] == [(1, 0, 0), (7, 0, 0), (14, 0, 0), (30, 0, 0)]
    assert m.ai == {"ok": 0, "empty": 0, "failed": 0} and m.next_count == 0 and m.sends == []


def test_kakao_stats_split(db, token_key):
    _account(db, 1, _trial(db))
    _account(db, 2, _trial(db), notify=False)
    _account(db, 3, _trial(db))
    accounts.mark_dead(db, 3)
    mine = _trial(db)
    db.add(TestTrial(token=mine))
    db.commit()
    _account(db, 4, mine)
    k = collect(db, D, None).kakao
    assert (k.receiving, k.off, k.dead, k.total) == (1, 1, 1, 3)


def test_since_and_test_trials_excluded(db):
    _trial(db, created=datetime(2026, 11, 16, 12, 0))  # KST 11/16 → since 전
    mine = _trial(db)
    db.add(TestTrial(token=mine))
    db.commit()
    _trial(db, created=datetime(2026, 11, 17, 12, 0))
    m = collect(db, D, date(2026, 11, 17))
    assert m.funnel[1].name == "시작" and m.funnel[1].count == 1


def test_daily_rows_by_kst_date(db):
    _trial(db, created=datetime(2026, 11, 17, 16, 0))  # UTC 16시 = KST 11/18 01시
    m = collect(db, D, None)
    assert m.daily[0].starts == 1 and m.daily[1].starts == 0


def test_funnel_pct(db, token_key):
    for _ in range(10):
        count_landing(db, "Mozilla/5.0", D)
    tokens = [_trial(db, setup=i < 3) for i in range(4)]
    _account(db, 1, tokens[0])
    m = collect(db, D, None)
    assert [s.name for s in m.funnel] == ["랜딩 조회", "시작", "질문 완료", "카톡 연결"]
    assert [s.count for s in m.funnel] == [10, 4, 3, 1]
    assert [s.pct for s in m.funnel] == [None, 40, 75, 33]


def test_retention(db):
    a = _trial(db, start=D - timedelta(days=7), setup=True)
    b = _trial(db, start=D - timedelta(days=7), setup=True)
    save_day(db, a, 7, True, None)
    save_day(db, a, 8, True, None)
    save_day(db, b, 1, True, None)
    r = {x.day: (x.kept, x.eligible) for x in collect(db, D, None).retention}
    assert r[1] == (2, 2) and r[7] == (1, 2) and r[14] == (0, 0)


def test_checkers_by_log_date(db):
    a = _trial(db, start=D - timedelta(days=1), setup=True)
    save_day(db, a, 2, True, None)  # 2일째 = 오늘
    save_day(db, a, 1, True, None)  # 1일째 = 어제
    m = collect(db, D, None)
    assert m.daily[0].checkers == 1 and m.daily[1].checkers == 1 and m.daily[2].checkers == 0


def test_sends_last_7_days(db):
    record_run(db, D, "morning", 5, 2)
    record_run(db, D - timedelta(days=6), "evening", 1, 0)
    record_run(db, D - timedelta(days=7), "evening", 9, 9)
    s = collect(db, D, None).sends
    assert [(x.day, x.kind, x.sent, x.failed) for x in s] == [
        (D, "morning", 5, 2), (D - timedelta(days=6), "evening", 1, 0)]


def test_since_excludes_old_accounts(db, token_key):
    t = _trial(db, created=datetime(2026, 11, 17, 12, 0))
    _account(db, 1, t)
    db.get(accounts.KakaoAccount, 1).created_at = datetime(2026, 11, 10, 12, 0)
    db.commit()
    assert collect(db, D, date(2026, 11, 17)).kakao.total == 0
