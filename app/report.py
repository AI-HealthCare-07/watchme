"""30일 결과 리포트: 시작 입력값(before) vs 마지막 체중 기록(after)."""
from dataclasses import dataclass
from datetime import date

from app.models import DayLog, Trial
from app.plan import DAYS
from app.risk import Assessment, assess


@dataclass(frozen=True)
class Report:
    kept_days: int
    logged_days: int
    start_weight: float
    end_weight: float | None
    weight_change: float | None
    before: Assessment
    after: Assessment | None
    enough_data: bool


def days_left(trial: Trial, today: date) -> int:
    return max(DAYS - (today - trial.start_date).days, 0)


def build_report(trial: Trial, logs: list[DayLog], today: date, stats: dict | None = None) -> Report | None:
    if days_left(trial, today):
        return None
    before = assess(trial.sex, trial.age, trial.height_cm, trial.weight_kg, stats=stats)
    weighed = sorted((log for log in logs if log.weight_kg is not None), key=lambda log: log.day)
    end = weighed[-1].weight_kg if weighed else None
    return Report(
        kept_days=sum(log.kept for log in logs),
        logged_days=len(logs),
        start_weight=trial.weight_kg,
        end_weight=end,
        weight_change=round(end - trial.weight_kg, 1) if end is not None else None,
        before=before,
        after=assess(trial.sex, trial.age, trial.height_cm, end, stats=stats) if end is not None else None,
        enough_data=len(weighed) >= 2 and len(logs) >= 10,
    )
