"""보관 기간(체험 종료 후 90일)이 끝난 체험 삭제. 서버 cron이 매일 실행.

  docker compose exec -T app python -m scripts.purge
"""
from app.clock import today_kst
from app.db import SessionLocal
from app.service import purge_expired

if __name__ == "__main__":
    with SessionLocal() as db:
        n = purge_expired(db, today_kst())
    if n:
        print(f"{today_kst()} purged {n} trials")
