from datetime import UTC, date, datetime, time

import pytest

from app.clock import slot_kst, today_kst


def test_today_kst_crosses_midnight():
    # UTC 16:00 = KST 다음날 01:00
    assert today_kst(datetime(2026, 11, 13, 16, 0, tzinfo=UTC)) == date(2026, 11, 14)


def test_today_kst_same_day():
    assert today_kst(datetime(2026, 11, 13, 14, 59, tzinfo=UTC)) == date(2026, 11, 13)


@pytest.mark.parametrize("utc, slot", [((22, 30), time(7, 30)), ((22, 59), time(7, 30)), ((23, 0), time(8, 0)),
                                       ((12, 0), time(21, 0)), ((14, 45), time(23, 30))])
def test_slot_kst_floors_to_30_minutes(utc, slot):
    # UTC 22:30 = KST 07:30
    assert slot_kst(datetime(2026, 11, 13, *utc, tzinfo=UTC)) == slot
