"""운영 지표: 랜딩 조회 카운터, 발송 기록, /admin 집계."""
# ponytail: 열 때마다 전체 집계. 체험 수천 개를 넘으면 SQL 집계나 일별 스냅샷으로
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import KST
from app.models import AiPick, DayLog, KakaoAccount, LandingView, NextTrial, SendRun, TestTrial, Trial, TrialOwner

BOT = re.compile(r"bot|crawl|spider|slurp|scrap|facebookexternalhit|preview|headless|curl|wget|python", re.I)


def is_bot(user_agent: str) -> bool:
    return not user_agent or bool(BOT.search(user_agent))


def _bump(db: Session, model, key: dict, add: dict) -> None:
    """key 행에 add만큼 더한다. 없으면 만든다(동시에 만들면 한 번 더 더하기)."""
    def _update():
        q = update(model).filter_by(**key).values({c: getattr(model, c) + n for c, n in add.items()})
        return db.execute(q).rowcount
    if not _update():
        try:
            db.add(model(**key, **add))
            db.commit()
            return
        except IntegrityError:
            db.rollback()
            _update()
    db.commit()


def count_landing(db: Session, user_agent: str, today: date) -> None:
    if not is_bot(user_agent):
        _bump(db, LandingView, {"day": today}, {"count": 1})


def record_run(db: Session, day: date, kind: str, sent: int, failed: int) -> None:
    _bump(db, SendRun, {"day": day, "kind": kind}, {"sent": sent, "failed": failed})


def kst_date(dt: datetime) -> date:
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(KST).date()


def since_from_env() -> date | None:
    try:
        return date.fromisoformat(os.environ.get("METRICS_SINCE", "").strip())
    except ValueError:
        return None


@dataclass(frozen=True)
class KakaoStats:
    receiving: int
    total: int
    dead: int
    off: int
    new_today: int


@dataclass(frozen=True)
class DayRow:
    day: date
    views: int
    starts: int
    setups: int
    links: int
    checkers: int


@dataclass(frozen=True)
class Step:
    name: str
    count: int
    pct: int | None


@dataclass(frozen=True)
class Retention:
    day: int
    kept: int
    eligible: int


@dataclass(frozen=True)
class SendDay:
    day: date
    kind: str
    sent: int
    failed: int


@dataclass(frozen=True)
class Metrics:
    kakao: KakaoStats
    daily: list[DayRow]
    funnel: list[Step]
    retention: list[Retention]
    next_count: int
    ai: dict[str, int]
    sends: list[SendDay]
    since: date | None


RETENTION_DAYS = (1, 7, 14, 30)


def _pct(n: int, prev: int | None) -> int | None:
    return round(n * 100 / prev) if prev else None


def collect(db: Session, today: date, since: date | None) -> Metrics:
    tests = set(db.scalars(select(TestTrial.token)))
    trials = {t.token: t for t in db.scalars(select(Trial))
              if t.token not in tests and (since is None or kst_date(t.created_at) >= since)}
    owners = {o.token: o.kakao_id for o in db.scalars(select(TrialOwner)) if o.token in trials}
    linked = set(owners.values())
    accs = [a for a in db.scalars(select(KakaoAccount))
            if a.kakao_id in linked and (since is None or kst_date(a.created_at) >= since)]
    dead = [a for a in accs if a.refresh_token_enc is None or not a.can_message]
    kakao = KakaoStats(
        receiving=sum(a.can_message and a.notify and a.refresh_token_enc is not None for a in accs),
        total=len(accs), dead=len(dead), off=sum(not a.notify for a in accs if a not in dead),
        new_today=sum(kst_date(a.created_at) == today for a in accs))

    views = {v.day: v.count for v in db.scalars(select(LandingView))}
    logs = [g for g in db.scalars(select(DayLog)) if g.token in trials]
    checked = {(trials[g.token].start_date + timedelta(days=g.day - 1), g.token) for g in logs}
    daily = []
    for i in range(30):
        d = today - timedelta(days=i)
        made = [t for t in trials.values() if kst_date(t.created_at) == d]
        daily.append(DayRow(d, views.get(d, 0), len(made), sum(t.setup_done for t in made),
                            sum(kst_date(a.created_at) == d for a in accs), sum(day == d for day, _ in checked)))

    counts = [("랜딩 조회", sum(n for d, n in views.items() if since is None or d >= since)),
              ("시작", len(trials)), ("질문 완료", sum(t.setup_done for t in trials.values())),
              ("카톡 연결", len(owners))]
    funnel = [Step(name, n, _pct(n, counts[i - 1][1]) if i else None) for i, (name, n) in enumerate(counts)]

    last_day = {}
    for g in logs:
        last_day[g.token] = max(last_day.get(g.token, 0), g.day)
    retention = []
    for n in RETENTION_DAYS:
        eligible = [t for t in trials.values() if t.setup_done and t.start_date <= today - timedelta(days=n - 1)]
        retention.append(Retention(n, sum(last_day.get(t.token, 0) >= n for t in eligible), len(eligible)))

    ai = {"ok": 0, "empty": 0, "failed": 0}
    for p in db.scalars(select(AiPick)):
        if p.token in trials and p.status in ai:
            ai[p.status] += 1
    runs = db.scalars(select(SendRun).where(SendRun.day >= today - timedelta(days=6))
                      .order_by(SendRun.day.desc(), SendRun.kind.desc()))
    return Metrics(
        kakao=kakao, daily=daily, funnel=funnel, retention=retention,
        next_count=sum(t in trials for t in db.scalars(select(NextTrial.token))),
        ai=ai, sends=[SendDay(r.day, r.kind, r.sent, r.failed) for r in runs], since=since)
