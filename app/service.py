import json
import secrets
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import accounts
from app.models import AiPick, DayLog, KakaoAccount, NextTrial, SentMessage, Trial, TrialOwner, WeekDecision
from app.plan import DAYS, MAX_LEVEL, PlanDay, Profile, build_plan, choose_variant
from app.risk import LIMITS, assess

RETENTION_DAYS = 90  # 체험 종료 후 보관 기간 (시작 화면 안내와 같게)
SENT_KEEP_DAYS = 40  # 중복 발송 방지 기록은 이만큼만 (체험 30일 + 여유)
SETUP_CHOICES = {
    "diet_style": {"veg", "meat", "mixed"},
    "lunch_place": {"home", "out", "store"},
    "breakfast": {"skip", "light", "full"},
    "exercise_min": {10, 25, 45},
}


class InvalidSetup(ValueError):
    pass


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


def save_setup(db: Session, token: str, diet_style: str, lunch_place: str, breakfast: str, exercise_min: int, free_days: list[int]) -> None:
    answers = dict(diet_style=diet_style, lunch_place=lunch_place, breakfast=breakfast, exercise_min=exercise_min)
    for key, value in answers.items():
        if value not in SETUP_CHOICES[key]:
            raise InvalidSetup("선택지 중에서 골라 주세요")
    days = sorted(set(free_days))
    if len(days) != 2 or len(free_days) != 2 or not all(0 <= d <= 6 for d in days):
        raise InvalidSetup("자유 한 끼 요일은 서로 다른 2개를 골라 주세요")
    trial = db.get(Trial, token)
    for key, value in answers.items():
        setattr(trial, key, value)
    trial.free_days = ",".join(map(str, days))
    db.commit()


def profile_of(trial: Trial) -> Profile:
    a, b = (int(d) for d in trial.free_days.split(","))
    return Profile(trial.plan_variant, trial.diet_style, trial.lunch_place, trial.breakfast, trial.exercise_min, (a, b))


def get_decisions(db: Session, token: str) -> dict[int, int]:
    rows = db.scalars(select(WeekDecision).where(WeekDecision.token == token))
    return {r.week: r.level for r in rows}


def excluded_of(db: Session, token: str) -> frozenset[str]:
    pick = db.get(AiPick, token)
    return frozenset(json.loads(pick.excluded)) if pick and pick.status == "ok" else frozenset()


def plan_for(db: Session, trial: Trial) -> list[PlanDay]:
    """계획을 만드는 곳은 모두 여기를 거친다(강도 결정 + AI 제외 목록)."""
    return build_plan(profile_of(trial), trial.start_date, trial.token,
                      get_decisions(db, trial.token), excluded_of(db, trial.token))


def decide_level(db: Session, token: str, week: int, up: bool) -> int:
    decisions = get_decisions(db, token)
    if not 1 <= week <= 4 or week in decisions:
        raise ValueError("이 주차는 결정할 수 없어요")
    prev = decisions[max(decisions)] if decisions else 0
    level = min(prev + 1, MAX_LEVEL) if up else prev
    db.add(WeekDecision(token=token, week=week, level=level))
    db.commit()
    return level


def get_logs(db: Session, token: str) -> list[DayLog]:
    return list(db.scalars(select(DayLog).where(DayLog.token == token).order_by(DayLog.day)))


def current_day(trial: Trial, today: date) -> int:
    return min(max((today - trial.start_date).days + 1, 1), DAYS)


def next_trial(db: Session, trial: Trial, today: date, stats: dict | None = None) -> Trial:
    """다음 30일 도전: 지금 체중(마지막 기록, 없으면 시작 체중)으로 새 체험, 맞춤 답변 복사. 한 체험에서 한 번만."""
    done = db.get(NextTrial, trial.token)
    if done:
        return db.get(Trial, done.next_token)
    weighed = [log.weight_kg for log in get_logs(db, trial.token) if log.weight_kg is not None]
    new = start_trial(db, trial.sex, trial.age, trial.height_cm, weighed[-1] if weighed else trial.weight_kg,
                      today=today, stats=stats)
    p = profile_of(trial)
    save_setup(db, new.token, p.diet_style, p.lunch_place, p.breakfast, p.exercise_min, list(p.free_days))
    db.add(NextTrial(token=trial.token, next_token=new.token))
    try:
        db.commit()
    except IntegrityError:  # 두 번 연달아 눌러 다른 요청이 먼저 저장함 → 방금 만든 체험은 지우고 그쪽으로
        db.rollback()
        db.delete(new)
        db.commit()
        return db.get(Trial, db.scalar(select(NextTrial.next_token).where(NextTrial.token == trial.token)))
    owner = accounts.owner_of(db, trial.token)
    if owner:
        accounts.link(db, new.token, owner.kakao_id)
    return new


def purge_expired(db: Session, today: date) -> int:
    """보관 기간이 끝난 체험과 기록 삭제. 삭제한 체험 수 반환."""
    cutoff = today - timedelta(days=DAYS + RETENTION_DAYS)
    expired = select(Trial.token).where(Trial.start_date <= cutoff)
    # SQLite는 FK cascade가 기본으로 꺼져 있어 기록부터 직접 지움
    db.execute(delete(WeekDecision).where(WeekDecision.token.in_(expired)))
    db.execute(delete(DayLog).where(DayLog.token.in_(expired)))
    db.execute(delete(AiPick).where(AiPick.token.in_(expired)))
    db.execute(delete(TrialOwner).where(TrialOwner.token.in_(expired)))
    db.execute(delete(NextTrial).where(NextTrial.token.in_(expired) | NextTrial.next_token.in_(expired)))
    n = db.execute(delete(Trial).where(Trial.start_date <= cutoff)).rowcount
    # 남은 체험이 없는 카카오 계정은 토큰째 삭제
    orphans = select(KakaoAccount.kakao_id).where(~KakaoAccount.kakao_id.in_(select(TrialOwner.kakao_id)))
    db.execute(delete(SentMessage).where(
        SentMessage.kakao_id.in_(orphans) | (SentMessage.day < today - timedelta(days=SENT_KEEP_DAYS))))
    db.execute(delete(KakaoAccount).where(KakaoAccount.kakao_id.in_(orphans)))
    db.commit()
    return n
