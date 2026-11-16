"""카카오 계정·체험 연결·발송 기록 DB 조작."""
from datetime import date

from sqlalchemy import delete, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import kakao
from app.models import KakaoAccount, SentMessage, Trial, TrialOwner


def save_account(db: Session, kakao_id: int, refresh_token: str | None, can_message: bool) -> KakaoAccount:
    acc = db.get(KakaoAccount, kakao_id) or KakaoAccount(kakao_id=kakao_id)
    acc.can_message = can_message
    if refresh_token is not None:
        acc.refresh_token_enc = kakao.encrypt(refresh_token)
    db.add(acc)
    db.commit()
    return acc


def owner_of(db: Session, token: str) -> KakaoAccount | None:
    owner = db.get(TrialOwner, token)
    return db.get(KakaoAccount, owner.kakao_id) if owner else None


def link(db: Session, token: str, kakao_id: int) -> bool:
    """체험을 계정에 연결. 이미 다른 계정에 연결돼 있으면 바꾸지 않고 False."""
    owner = db.get(TrialOwner, token)
    if owner:
        return owner.kakao_id == kakao_id
    db.add(TrialOwner(token=token, kakao_id=kakao_id))
    db.commit()
    return True


def has_trials(db: Session, kakao_id: int) -> bool:
    return bool(db.scalar(select(exists().where(TrialOwner.kakao_id == kakao_id))))


def latest_trial(db: Session, kakao_id: int) -> Trial | None:
    return db.scalar(
        select(Trial).join(TrialOwner, TrialOwner.token == Trial.token)
        .where(TrialOwner.kakao_id == kakao_id).order_by(Trial.created_at.desc()).limit(1)
    )


def set_notify(db: Session, kakao_id: int, on: bool) -> None:
    db.get(KakaoAccount, kakao_id).notify = on
    db.commit()


def mark_dead(db: Session, kakao_id: int) -> None:
    acc = db.get(KakaoAccount, kakao_id)
    acc.can_message, acc.refresh_token_enc = False, None
    db.commit()


def delete_account(db: Session, kakao_id: int) -> None:
    # SQLite는 FK cascade가 기본으로 꺼져 있어 직접 지움
    db.execute(delete(TrialOwner).where(TrialOwner.kakao_id == kakao_id))
    db.execute(delete(SentMessage).where(SentMessage.kakao_id == kakao_id))
    db.execute(delete(KakaoAccount).where(KakaoAccount.kakao_id == kakao_id))
    db.commit()


def claim(db: Session, kakao_id: int, day: date, kind: str) -> bool:
    """(계정, 날짜, 종류) 발송권을 먼저 기록. 이미 있으면 False (최대 한 번 발송)."""
    db.add(SentMessage(kakao_id=kakao_id, day=day, kind=kind))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True
