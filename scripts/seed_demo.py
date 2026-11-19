"""데모용 체험: 31일 전에 시작해 30일 기록이 채워진 체험을 만들고 리포트 URL을 출력.

서버: docker compose exec app python -m scripts.seed_demo
"""
import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import TestTrial
from app.plan import DAYS
from app.service import save_day, save_setup, start_trial


def seed(db: Session, today: date, stats: dict | None = None) -> str:
    start_weight = 82.0
    trial = start_trial(db, "M", 45, 172, start_weight, today=today - timedelta(days=DAYS + 1), stats=stats)
    db.add(TestTrial(token=trial.token))  # 데모 체험은 운영 지표에서 뺀다
    db.commit()
    save_setup(db, trial.token, "mixed", "out", "light", 25, [2, 5])
    for day in range(1, DAYS + 1):
        # 하루 약 0.08kg 감량 + 측정 흔들림, 체중은 대략 이틀에 한 번
        weight = round(start_weight - 0.08 * day + random.uniform(-0.3, 0.3), 1) if random.random() < 0.5 else None
        save_day(db, trial.token, day, random.random() < 0.8, weight)
    return trial.token


if __name__ == "__main__":
    from app.db import SessionLocal, init_db
    from app.clock import today_kst
    from app.routes import PUBLIC_BASE_URL

    init_db()
    with SessionLocal() as db:
        print(f"{PUBLIC_BASE_URL}/c/{seed(db, today_kst())}/report")
