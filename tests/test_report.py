from datetime import date, timedelta

from app.models import DayLog, Trial
from app.report import build_report
from tests.test_risk import STATS

START = date(2026, 10, 1)
DONE = START + timedelta(days=30)  # 31일째 = 30일 경과


def _trial():
    return Trial(token="t", start_date=START, sex="M", age=40, height_cm=170, weight_kg=80, plan_variant="obese")


def _logs(kept_days, weights):
    return [DayLog(token="t", day=d, kept=d <= kept_days, weight_kg=weights.get(d)) for d in range(1, 31)]


def test_report_counts_and_weight_change():
    logs = _logs(20, {1: 80.0, 10: 79.0, 20: 78.2, 28: 77.5})
    r = build_report(_trial(), logs, DONE, stats=STATS)
    assert r.kept_days == 20
    assert r.logged_days == 30
    assert r.start_weight == 80
    assert r.end_weight == 77.5
    assert r.weight_change == round(77.5 - 80, 1)
    assert r.enough_data
    assert r.after.bmi != r.before.bmi


def test_report_without_logs_has_no_after():
    r = build_report(_trial(), [], DONE, stats=STATS)
    assert r.kept_days == 0 and r.logged_days == 0
    assert r.end_weight is None and r.weight_change is None and r.after is None
    assert not r.enough_data


def test_report_needs_two_weights_and_ten_checks():
    one_weight = _logs(20, {28: 77.5})
    assert not build_report(_trial(), one_weight, DONE, stats=STATS).enough_data
    few_checks = _logs(20, {1: 80.0, 28: 77.5})[:9]
    assert not build_report(_trial(), few_checks, DONE, stats=STATS).enough_data


def test_no_report_before_30_days():
    assert build_report(_trial(), [], START + timedelta(days=28), stats=STATS) is None  # 29일째
    assert build_report(_trial(), [], START + timedelta(days=29), stats=STATS) is None  # 30일째
