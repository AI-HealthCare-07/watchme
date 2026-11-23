"""아침·저녁 카톡 발송. 서버 cron(KST)이 30분마다(매시 0·30분) 실행.
지금 시각의 30분 칸이 아침 시각인 사람에게 아침 메시지, 저녁 시각인 사람에게 저녁 메시지를 보낸다.

  docker compose exec -T app python -m scripts.send
"""
from datetime import UTC, datetime

from app import kakao
from app.clock import slot_kst, today_kst
from app.db import SessionLocal
from app.metrics import record_run
from app.notify import send_all

if __name__ == "__main__":
    if not kakao.enabled():
        raise SystemExit(0)
    now = datetime.now(UTC)
    today, slot = today_kst(now), slot_kst(now)
    with SessionLocal() as db:
        for kind in ("morning", "evening"):
            sent, failed = send_all(db, kind, today, slot)
            record_run(db, today, kind, sent, failed)  # 0이라도 남겨서 cron이 도는지 /admin에서 보이게
            if sent or failed:
                print(f"{today} {slot:%H:%M} {kind} sent={sent} failed={failed}")
