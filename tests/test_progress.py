from datetime import date

from app.models import DayLog, Trial
from app.progress import can_level_up, plateau, streak, summary_week, week_summary
from tests.test_risk import STATS


def _log(day, kept=True, w=None):
    return DayLog(token="t", day=day, kept=kept, weight_kg=w)


def _trial():
    return Trial(token="t", start_date=date(2026, 11, 16), sex="M", age=45, height_cm=172, weight_kg=82, plan_variant="obese")


def _week1(kept_days=7, first=80.0, last=80.2):
    logs = [_log(d, kept=d <= kept_days) for d in range(1, 8)]
    if first is not None:
        logs[0].weight_kg = first
    if last is not None:
        logs[6].weight_kg = last
    return logs


def test_streak():
    logs = [_log(d) for d in range(1, 6)]
    assert streak(logs, 6) == 5
    assert streak(logs + [_log(6)], 6) == 6
    logs[3].kept = False
    assert streak(logs, 6) == 1
    assert streak(logs + [_log(6)], 6) == 2
    assert streak([], 1) == 0


def test_plateau_true_and_false():
    assert plateau(_week1(), 7) is True
    assert plateau(_week1(last=79.8), 7) is False
    assert plateau(_week1(kept_days=5), 7) is False
    assert plateau(_week1(last=None), 7) is False
    assert plateau(_week1(first=None, last=None), 7) is False
    assert plateau([], 7) is False


def test_summary_week_window():
    has7 = [_log(7)]
    assert summary_week(7, has7) == 1
    assert summary_week(7, []) is None
    assert summary_week(8, []) == 1
    assert summary_week(9, has7) is None
    assert summary_week(29, []) == 4
    assert summary_week(30, []) is None
    assert summary_week(28, [_log(28)]) == 4


def test_week_summary_without_weights():
    s = week_summary(_trial(), _week1(kept_days=4, first=None, last=None), 1, stats=STATS)
    assert (s.week, s.kept, s.days) == (1, 4, 7)
    assert s.weight_change is None and s.before is None and s.after is None and s.plateau is False


def test_week_summary_with_weights():
    s = week_summary(_trial(), _week1(first=80.0, last=79.0), 1, stats=STATS)
    assert (s.weight_start, s.weight_end, s.weight_change) == (80.0, 79.0, -1.0)
    assert s.after.diabetes_vs_avg < s.before.diabetes_vs_avg
    assert week_summary(_trial(), [_log(29, w=80.0), _log(30, w=80.1)], 5, stats=STATS).days == 2


def test_can_level_up():
    logs = _week1()
    assert can_level_up(logs, 1, {}) is True
    assert can_level_up(logs, 1, {1: 1}) is False
    assert can_level_up(_week1(last=79.0), 1, {}) is False
    week2 = [_log(d, w=80.0 if d in (8, 14) else None) for d in range(8, 15)]
    assert can_level_up(week2, 2, {1: 1}) is True
    assert can_level_up(week2, 2, {1: 2}) is False
