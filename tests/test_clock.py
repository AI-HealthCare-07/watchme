from datetime import UTC, date, datetime

from app.clock import today_kst


def test_today_kst_crosses_midnight():
    # UTC 16:00 = KST 다음날 01:00
    assert today_kst(datetime(2026, 11, 13, 16, 0, tzinfo=UTC)) == date(2026, 11, 14)


def test_today_kst_same_day():
    assert today_kst(datetime(2026, 11, 13, 14, 59, tzinfo=UTC)) == date(2026, 11, 13)
