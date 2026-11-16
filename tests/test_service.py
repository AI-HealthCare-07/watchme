from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import DayLog
from app.risk import InvalidInput
from app.service import (
    InvalidSetup, current_day, decide_level, get_decisions, get_logs, get_trial,
    purge_expired, save_day, save_setup, start_trial,
)
from tests.test_risk import STATS

TODAY = date(2026, 11, 16)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _start(db, **kw):
    args = dict(sex="M", age=40, height_cm=170, weight_kg=80, today=TODAY, stats=STATS) | kw
    return start_trial(db, **args)


def test_start_trial_creates_unguessable_token_and_variant(db):
    t1, t2 = _start(db), _start(db)
    assert len(t1.token) >= 22 and t1.token != t2.token
    assert t1.plan_variant == "high_risk"  # BMI 27.7, 당뇨 vs_avg 2.0
    assert get_trial(db, t1.token).start_date == TODAY


def test_start_trial_validates_input(db):
    with pytest.raises(InvalidInput):
        _start(db, age=0)


def test_save_day_overwrites_same_day(db):
    t = _start(db)
    save_day(db, t.token, 3, True, 80.5)
    save_day(db, t.token, 3, False, None)
    rows = db.scalars(select(DayLog).where(DayLog.token == t.token)).all()
    assert len(rows) == 1
    assert (rows[0].kept, rows[0].weight_kg) == (False, None)


@pytest.mark.parametrize("day,weight", [(0, None), (31, None), (5, 29.9), (5, 250.1)])
def test_save_day_rejects_out_of_range(db, day, weight):
    t = _start(db)
    with pytest.raises(ValueError):
        save_day(db, t.token, day, True, weight)


def test_get_logs_sorted_by_day(db):
    t = _start(db)
    for d in (5, 1, 3):
        save_day(db, t.token, d, True, None)
    assert [log.day for log in get_logs(db, t.token)] == [1, 3, 5]


def test_current_day_clamped(db):
    t = _start(db)
    assert current_day(t, TODAY) == 1
    assert current_day(t, TODAY + timedelta(days=29)) == 30
    assert current_day(t, TODAY + timedelta(days=100)) == 30
    assert current_day(t, TODAY - timedelta(days=1)) == 1


def test_unknown_token_is_none(db):
    assert get_trial(db, "없는토큰") is None


def test_purge_deletes_trials_90_days_after_end_with_logs(db):
    # 체험 30일 + 보관 90일 = 시작 후 120일째에 삭제
    old = _start(db, today=TODAY - timedelta(days=120))
    kept = _start(db, today=TODAY - timedelta(days=119))
    old_t, kept_t = old.token, kept.token
    save_day(db, old_t, 1, True, 80.0)
    save_day(db, kept_t, 1, True, 80.0)
    decide_level(db, old_t, 1, True)
    assert purge_expired(db, TODAY) == 1
    assert get_trial(db, old_t) is None and get_logs(db, old_t) == []
    assert get_trial(db, kept_t) is not None and len(get_logs(db, kept_t)) == 1


GOOD_SETUP = dict(diet_style="mixed", lunch_place="out", breakfast="light", exercise_min=25, free_days=[5, 2])


def test_new_trial_setup_not_done(db):
    assert _start(db).setup_done is False


def test_save_setup_stores_answers(db):
    t = _start(db).token
    save_setup(db, t, **GOOD_SETUP)
    trial = get_trial(db, t)
    assert trial.setup_done is True
    assert trial.free_days == "2,5"
    assert (trial.diet_style, trial.lunch_place, trial.breakfast, trial.exercise_min) == ("mixed", "out", "light", 25)


@pytest.mark.parametrize("bad", [
    {"diet_style": "x"}, {"lunch_place": ""}, {"breakfast": "none"}, {"exercise_min": 30},
    {"free_days": [1]}, {"free_days": [1, 2, 3]}, {"free_days": [3, 3]}, {"free_days": [7, 1]},
])
def test_save_setup_rejects_bad_values(db, bad):
    t = _start(db).token
    with pytest.raises(InvalidSetup):
        save_setup(db, t, **(GOOD_SETUP | bad))
    assert get_trial(db, t).setup_done is False


def test_decide_level_up_keep_and_cap(db):
    t = _start(db).token
    assert decide_level(db, t, 1, True) == 1
    assert decide_level(db, t, 2, False) == 1
    assert decide_level(db, t, 3, True) == 2
    assert decide_level(db, t, 4, True) == 2
    assert get_decisions(db, t) == {1: 1, 2: 1, 3: 2, 4: 2}


def test_decide_level_twice_rejected(db):
    t = _start(db).token
    decide_level(db, t, 1, True)
    for week in (1, 0, 5):
        with pytest.raises(ValueError):
            decide_level(db, t, week, True)
    assert get_decisions(db, t) == {1: 1}


# --- 다음 30일 도전 ---

def _finished_trial(db, weights):
    t = _start(db, today=TODAY - timedelta(days=30))
    save_setup(db, t.token, **GOOD_SETUP)
    for d, w in weights.items():
        save_day(db, t.token, d, True, w)
    return t


def test_next_trial_copies_and_uses_last_weight(db):
    from app.service import next_trial
    old = _finished_trial(db, {5: 80.0, 20: 78.5})
    new = next_trial(db, old, TODAY, stats=STATS)
    assert new.token != old.token and new.weight_kg == 78.5 and new.start_date == TODAY
    pick = lambda t: (t.sex, t.age, t.height_cm, t.diet_style, t.lunch_place, t.breakfast, t.exercise_min, t.free_days)  # noqa: E731
    assert pick(new) == pick(old)
    assert next_trial(db, old, TODAY, stats=STATS).token == new.token


def test_next_trial_without_weights_uses_start_weight(db):
    from app.service import next_trial
    old = _finished_trial(db, {})
    assert next_trial(db, old, TODAY, stats=STATS).weight_kg == 80


def test_next_trial_inherits_kakao_link(db, monkeypatch):
    from cryptography.fernet import Fernet

    from app import accounts
    from app.service import next_trial
    monkeypatch.setenv("TOKEN_KEY", Fernet.generate_key().decode())
    old = _finished_trial(db, {})
    accounts.save_account(db, 42, "r", True)
    accounts.link(db, old.token, 42)
    new = next_trial(db, old, TODAY, stats=STATS)
    assert accounts.owner_of(db, new.token).kakao_id == 42
