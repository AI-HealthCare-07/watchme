"""주간 리포트: 또래 비교(국민건강영양조사 걷기), 앱 사용자 순위, 응원 문구."""
from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import DayLog, Trial
from app.plan import PlanDay, week_days
from app.progress import WeekSummary, week_summary
from app.risk import age_band, group_label
from app.service import get_logs, plan_for

PEER_MAX = 0.5  # 또래 중 이 비율 이하일 때만 자랑
RANK_MIN_PEERS = 30
RANK_MAX = 50
REPORT_WEEKS = range(1, 5)  # 5주차(29~30일)는 30일 리포트가 맡는다


def ratio_text(share: float) -> str:
    if share >= 0.1:
        return f"10명 중 {round(share * 10)}명"
    return f"100명 중 {max(1, round(share * 100))}명"


@dataclass(frozen=True)
class Peer:
    days: int  # 지킨 운동하는 날
    minutes: int  # 비교 기준 하루 분(10분 단위로 내림)
    share: float
    label: str  # "40대 남성"

    @property
    def ratio(self) -> str:
        return ratio_text(self.share)


def _floor_minutes(minutes: int) -> int:
    return min(60, max(10, minutes // 10 * 10))


def walk_share(stats: dict | None, sex: str, age: int, days: int, minutes: int) -> float | None:
    """주 days일 이상, 하루 minutes분 이상 걷는 같은 성별·나이대 비율. 자료가 없으면 None."""
    if not stats or "walk" not in stats or not 1 <= days <= 7:
        return None
    group = stats["walk"]["groups"].get(sex, {}).get(age_band(age))
    return group["share"][str(_floor_minutes(minutes))][days - 1] if group else None


def peer_of(trial: Trial, days: list[PlanDay], logs: list[DayLog], stats: dict | None) -> Peer | None:
    exercise = [d for d in days if d.exercise_min > 0]  # 쉬는 날은 걷기 비교에서 뺀다
    if not exercise:
        return None
    kept = {log.day for log in logs if log.kept}
    k = sum(d.day in kept for d in exercise)
    m = min(d.exercise_min for d in exercise)
    share = walk_share(stats, trial.sex, trial.age, k, m)
    if share is None or share > PEER_MAX:
        return None
    return Peer(k, _floor_minutes(m), share, group_label(trial.sex, trial.age))


def week_ready(today_day: int, logs: list[DayLog], week: int) -> bool:
    end = 7 * week
    return week in REPORT_WEEKS and (today_day > end or (today_day == end and any(log.day == end for log in logs)))


def app_rank(db: Session, trial: Trial, week: int, kept: int, today: date) -> int | None:
    """같은 주를 마치고 그 주 기록이 있는 다른 체험 중 상위 N%. 동점은 내 위로 센다."""
    # ponytail: 열 때마다 집계. 사용자가 많아지면 주차별 캐시
    rows = db.scalars(
        select(func.sum(case((DayLog.kept, 1), else_=0)))
        .join(Trial, Trial.token == DayLog.token)
        .where(Trial.token != trial.token, Trial.start_date <= today - timedelta(days=7 * week),
               DayLog.day.in_(list(week_days(week))))
        .group_by(DayLog.token)
    ).all()
    if len(rows) < RANK_MIN_PEERS:
        return None
    ahead = sum(k >= kept for k in rows)
    n = ceil(100 * (ahead + 1) / (len(rows) + 1))
    return n if n <= RANK_MAX else None


def cheer(week: int, kept: int, prev_kept: int | None) -> str:
    if kept == 0:
        return "이번 주는 쉬어 갔어요. 오늘부터 다시 하루씩 채워 봐요."
    if week == 1 or prev_kept is None:
        if kept >= 5:
            return f"첫 주부터 {kept}일! 이 속도면 30일 완주 충분해요."
        return f"첫 주 {kept}일, 시작이 반이에요. 다음 주엔 하루만 더 지켜 봐요."
    diff = kept - prev_kept
    if diff > 0:
        return f"지난주보다 {diff}일 더 지켰어요. 점점 몸에 붙고 있어요."
    if diff == 0:
        return "지난주만큼 꾸준히 지켰어요. 꾸준함이 제일 어려운 거예요."
    return "이번 주는 조금 쉬어 갔어요. 다음 주에 다시 올려 봐요."


@dataclass(frozen=True)
class WeekReport:
    week: int
    first: date
    last: date
    marks: tuple[bool | None, ...]  # 날마다 지킴 / 못 지킴 / 기록 없음
    kept: int
    peer: Peer | None
    rank: int | None
    cheer: str
    weights: list[tuple[int, float]]  # (0, 시작 체중) + 그 주까지의 기록
    summary: WeekSummary


def build_week(db: Session, trial: Trial, week: int, today: date, stats: dict | None) -> WeekReport:
    plan = plan_for(db, trial)
    span = week_days(week)
    days = [plan[d - 1] for d in span]
    logs = get_logs(db, trial.token)
    by_day = {log.day: log for log in logs}
    marks = tuple(by_day[d].kept if d in by_day else None for d in span)
    kept = sum(m is True for m in marks)
    prev = sum(d in by_day and by_day[d].kept for d in week_days(week - 1)) if week > 1 else None
    weights = [(0, trial.weight_kg)] + [(log.day, log.weight_kg) for log in logs
                                        if log.weight_kg is not None and log.day <= span[-1]]
    return WeekReport(
        week=week, first=days[0].date, last=days[-1].date, marks=marks, kept=kept,
        peer=peer_of(trial, days, logs, stats), rank=app_rank(db, trial, week, kept, today),
        cheer=cheer(week, kept, prev), weights=weights, summary=week_summary(trial, logs, week, stats=stats),
    )
