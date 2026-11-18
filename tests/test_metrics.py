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
