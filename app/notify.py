"""아침·저녁 카톡 발송. 서버 cron이 scripts/send.py로 30분마다 부르고, 그 칸이 내 시각인 사람에게만 보낸다."""
import os
from datetime import date, time
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import accounts, kakao, messages
from app.models import DayLog, KakaoAccount
from app.plan import DAYS
from app.risk import get_stats
from app.service import plan_for
from app.weekly import build_week


def _base() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


WEEK_REPORT_DAYS = (8, 15, 22, 29)  # 그날 아침은 계획 대신 지난주 리포트 하나만


def _message(db: Session, kind: str, trial, n: int, today: date) -> tuple[str, str, str, str] | None:
    """(발송 종류, 문장, 링크, 버튼) 또는 보낼 게 없으면 None."""
    link = f"{_base()}/c/{trial.token}"
    sunday = today.weekday() == 6
    if kind == "morning":
        if n == DAYS + 1:
            return "report", messages.REPORT, f"{link}/report", messages.BUTTON["report"]
        if n in WEEK_REPORT_DAYS:
            w = (n - 1) // 7
            r = build_week(db, trial, w, today, get_stats())
            return "week", messages.week(w, r.kept, r.peer), f"{link}/week/{w}", messages.BUTTON["week"]
        plan = plan_for(db, trial)
        return "morning", messages.morning(plan[n - 1], sunday), link, messages.BUTTON["morning"]
    if n > DAYS:
        return None
    logged = db.get(DayLog, (trial.token, n)) is not None
    button = messages.BUTTON["evening_logged" if logged else "evening"]
    return "evening", messages.evening(n, logged, sunday), link, button


def send_all(db: Session, kind: Literal["morning", "evening"], today: date, slot: time) -> tuple[int, int]:
    """(보냄, 실패). 같은 (계정, 날짜, 종류)는 최대 한 번: 먼저 기록하고 보내며, 실패해도 다시 보내지 않는다."""
    sent = failed = 0
    targets = db.scalars(select(KakaoAccount).where(
        KakaoAccount.notify, KakaoAccount.can_message, KakaoAccount.refresh_token_enc.is_not(None),
        (KakaoAccount.morning_at if kind == "morning" else KakaoAccount.evening_at) == slot))
    for acc in list(targets):
        trial = accounts.active_trial(db, acc.kakao_id, today)
        if trial is None:
            continue
        try:
            msg = _message(db, kind, trial, accounts.day_number(trial, today), today)
        except Exception as e:  # 한 사람의 문장 만들기 오류(리포트 계산 등)가 나머지 발송을 막지 않게
            db.rollback()
            print(f"kakao {acc.kakao_id} message error: {e!r}")
            failed += 1
            continue
        if msg is None or not accounts.claim(db, acc.kakao_id, today, msg[0]):
            continue
        try:
            tokens = kakao.refresh(kakao.decrypt(acc.refresh_token_enc))
            if tokens.refresh_token:
                accounts.save_account(db, acc.kakao_id, tokens.refresh_token, acc.can_message)
            kakao.send_memo(tokens.access_token, *msg[1:])
            sent += 1
        except kakao.KakaoAuthError as e:
            print(f"kakao {acc.kakao_id} disconnected: {e}")
            accounts.mark_dead(db, acc.kakao_id)
            failed += 1
        except kakao.KakaoError as e:
            print(f"kakao {acc.kakao_id} send failed: {e}")
            failed += 1
        except Exception as e:  # 한 계정의 예상 못 한 오류(이상한 응답 등)가 나머지 발송을 막지 않게
            db.rollback()
            print(f"kakao {acc.kakao_id} unexpected error: {e!r}")
            failed += 1
    return sent, failed
