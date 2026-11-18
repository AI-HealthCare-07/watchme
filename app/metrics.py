"""운영 지표: 랜딩 조회 카운터, 발송 기록."""
import re
from datetime import date

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LandingView, SendRun

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
