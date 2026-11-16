import secrets
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DayLog, Trial
from app.plan import DAYS, choose_variant
from app.risk import LIMITS, assess


def start_trial(db: Session, sex: str, age: int, height_cm: float, weight_kg: float, today: date, stats: dict | None = None) -> Trial:
    a = assess(sex, age, height_cm, weight_kg, stats=stats)  # 검증 겸 계획 종류 결정
    trial = Trial(
        token=secrets.token_urlsafe(16),
        start_date=today,
        sex=sex,
        age=age,
        height_cm=height_cm,
        weight_kg=weight_kg,
        plan_variant=choose_variant(a),
    )
    db.add(trial)
    db.commit()
    return trial


def get_trial(db: Session, token: str) -> Trial | None:
    return db.get(Trial, token)


def save_day(db: Session, token: str, day: int, kept: bool, weight_kg: float | None) -> None:
    if not 1 <= day <= DAYS:
        raise ValueError(f"day는 1~{DAYS}")
    lo, hi = LIMITS["weight_kg"]
    if weight_kg is not None and not lo <= weight_kg <= hi:
        raise ValueError(f"몸무게는 {lo}~{hi}kg")
    log = db.get(DayLog, (token, day)) or DayLog(token=token, day=day)
    log.kept, log.weight_kg = kept, weight_kg
    db.add(log)
    db.commit()


def get_logs(db: Session, token: str) -> list[DayLog]:
    return list(db.scalars(select(DayLog).where(DayLog.token == token).order_by(DayLog.day)))


def current_day(trial: Trial, today: date) -> int:
    return min(max((today - trial.start_date).days + 1, 1), DAYS)
