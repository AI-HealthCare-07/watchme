from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import accounts, kakao
from app.db import Base
from app.models import KakaoAccount, SentMessage, Trial
from app.service import save_setup, start_trial
from tests.test_kakao import kakao_env  # noqa: F401  (fixture)
from tests.test_risk import STATS

TODAY = date(2026, 11, 16)


@pytest.fixture
def db(kakao_env):  # noqa: F811
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def trial(db, start: date = TODAY, created: datetime | None = None) -> Trial:
    t = start_trial(db, "M", 45, 170, 80, today=start, stats=STATS)
    save_setup(db, t.token, "mixed", "out", "light", 25, [2, 5])
    if created:
        t.created_at = created
        db.commit()
    return t


def test_save_account_encrypts_and_keeps_old_token_when_none(db):
    acc = accounts.save_account(db, 42, "r1", True)
    assert acc.refresh_token_enc != "r1"
    assert kakao.decrypt(acc.refresh_token_enc) == "r1"
    acc = accounts.save_account(db, 42, None, False)
    assert kakao.decrypt(acc.refresh_token_enc) == "r1"
    assert acc.can_message is False and acc.notify is True


def test_link_rules(db):
    t = trial(db)
    accounts.save_account(db, 42, "r", True)
    accounts.save_account(db, 43, "r", True)
    assert accounts.link(db, t.token, 42)
    assert accounts.link(db, t.token, 42)
    assert not accounts.link(db, t.token, 43)
    assert accounts.owner_of(db, t.token).kakao_id == 42


def test_latest_trial_by_created_at(db):
    accounts.save_account(db, 42, "r", True)
    assert accounts.latest_trial(db, 42) is None
    assert not accounts.has_trials(db, 42)
    now = datetime.now(UTC)
    old, new = trial(db, created=now - timedelta(days=31)), trial(db, created=now)
    accounts.link(db, new.token, 42)
    accounts.link(db, old.token, 42)
    assert accounts.has_trials(db, 42)
    assert accounts.latest_trial(db, 42).token == new.token


def test_claim_once(db):
    accounts.save_account(db, 42, "r", True)
    assert accounts.claim(db, 42, TODAY, "morning")
    assert not accounts.claim(db, 42, TODAY, "morning")
    assert accounts.claim(db, 42, TODAY, "evening")


def test_set_notify_and_mark_dead(db):
    accounts.save_account(db, 42, "r", True)
    accounts.set_notify(db, 42, False)
    accounts.mark_dead(db, 42)
    acc = db.get(KakaoAccount, 42)
    assert acc.notify is False and acc.can_message is False and acc.refresh_token_enc is None


def test_delete_account_removes_links_and_sent(db):
    t = trial(db)
    accounts.save_account(db, 42, "r", True)
    accounts.link(db, t.token, 42)
    accounts.claim(db, 42, TODAY, "morning")
    accounts.delete_account(db, 42)
    assert accounts.owner_of(db, t.token) is None
    assert db.scalar(select(func.count()).select_from(SentMessage)) == 0
    assert db.get(Trial, t.token) is not None


def test_times_are_30_minute_lists():
    assert accounts.TIMES["morning"][0] == time(5, 0) and accounts.TIMES["morning"][-1] == time(10, 30)
    assert accounts.TIMES["evening"][0] == time(18, 0) and accounts.TIMES["evening"][-1] == time(23, 30)
    assert len(accounts.TIMES["morning"]) == len(accounts.TIMES["evening"]) == 12


def test_new_account_default_times(db):
    acc = accounts.save_account(db, 7, "r", True)
    assert (acc.morning_at, acc.evening_at) == (time(7, 30), time(21, 0))


def test_set_times(db):
    accounts.save_account(db, 7, "r", True)
    accounts.set_times(db, 7, time(6, 0), time(22, 30))
    acc = db.get(KakaoAccount, 7)
    assert (acc.morning_at, acc.evening_at) == (time(6, 0), time(22, 30))


@pytest.mark.parametrize("m, e", [(time(6, 15), time(21, 0)), (time(21, 0), time(7, 30)), (time(4, 30), time(21, 0))])
def test_set_times_rejects_outside_list(db, m, e):
    accounts.save_account(db, 7, "r", True)
    with pytest.raises(ValueError):
        accounts.set_times(db, 7, m, e)
