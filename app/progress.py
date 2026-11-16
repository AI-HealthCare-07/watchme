"""기록 기반 판단: 연속 기록, 체중 정체, 주간 요약, 강도 질문 여부."""
from dataclasses import dataclass

from app.models import DayLog, Trial
from app.plan import MAX_LEVEL, level_on, week_days
from app.risk import Assessment, assess


def streak(logs: list[DayLog], today: int) -> int:
    """오늘 기록이 있으면 오늘부터, 없으면 어제부터 거꾸로 연속으로 지킨 날 수."""
    kept = {log.day: log.kept for log in logs}
    day = today if today in kept else today - 1
    n = 0
    while kept.get(day):
        n, day = n + 1, day - 1
    return n


def _weights(logs: list[DayLog], days) -> list[float]:
    return [log.weight_kg for log in sorted(logs, key=lambda log: log.day) if log.day in days and log.weight_kg is not None]


def plateau(logs: list[DayLog], end_day: int) -> bool:
    """최근 7일 중 6일 이상 지켰는데 체중이 그대로거나 늘었음."""
    window = range(end_day - 6, end_day + 1)
    kept = sum(log.kept for log in logs if log.day in window)
    w = _weights(logs, window)
    return kept >= 6 and len(w) >= 2 and w[-1] >= w[0]


def summary_week(today: int, logs: list[DayLog]) -> int | None:
    """주간 요약을 보여줄 주차: 7k일 기록 뒤부터 7k+1일까지."""
    if today in (7, 14, 21, 28) and any(log.day == today for log in logs):
        return today // 7
    if today in (8, 15, 22, 29):
        return (today - 1) // 7
    return None


@dataclass(frozen=True)
class WeekSummary:
    week: int
    kept: int
    days: int
    weight_start: float | None
    weight_end: float | None
    weight_change: float | None
    before: Assessment | None
    after: Assessment | None
    plateau: bool


def week_summary(trial: Trial, logs: list[DayLog], week: int, stats: dict | None = None) -> WeekSummary:
    days = week_days(week)
    w = _weights(logs, days)
    two = len(w) >= 2
    a = lambda kg: assess(trial.sex, trial.age, trial.height_cm, kg, stats=stats)
    return WeekSummary(
        week=week,
        kept=sum(log.kept for log in logs if log.day in days),
        days=len(days),
        weight_start=w[0] if w else None,
        weight_end=w[-1] if w else None,
        weight_change=round(w[-1] - w[0], 1) if two else None,
        before=a(w[0]) if two else None,
        after=a(w[-1]) if two else None,
        plateau=plateau(logs, days[-1]),
    )


def can_level_up(logs: list[DayLog], week: int, decisions: dict[int, int]) -> bool:
    return plateau(logs, 7 * week) and week not in decisions and level_on(decisions, 7 * week) < MAX_LEVEL
