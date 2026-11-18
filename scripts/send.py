"""아침·저녁 카톡 발송. 서버 cron(KST)이 7:30 morning, 21:00 evening으로 실행.

  docker compose exec -T app python -m scripts.send morning
"""
import sys

from app import kakao
from app.clock import today_kst
from app.db import SessionLocal
from app.metrics import record_run
from app.notify import send_all

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("morning", "evening"):
        print("사용법: python -m scripts.send morning|evening")
        sys.exit(2)
    if not kakao.enabled():
        sys.exit(0)
    kind, today = sys.argv[1], today_kst()
    with SessionLocal() as db:
        sent, failed = send_all(db, kind, today)
        record_run(db, today, kind, sent, failed)
    if sent or failed:
        print(f"{today} {kind} sent={sent} failed={failed}")
