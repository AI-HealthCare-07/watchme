from datetime import UTC, date, datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Trial(Base):
    __tablename__ = "trials"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    start_date: Mapped[date]
    sex: Mapped[str] = mapped_column(String(1))
    age: Mapped[int]
    height_cm: Mapped[float]
    weight_kg: Mapped[float]
    plan_variant: Mapped[str] = mapped_column(String(32))


class DayLog(Base):
    __tablename__ = "day_logs"

    # (token, day) 복합 기본키 = 같은 날 기록은 하나뿐
    token: Mapped[str] = mapped_column(ForeignKey("trials.token", ondelete="CASCADE"), primary_key=True)
    day: Mapped[int] = mapped_column(primary_key=True)
    kept: Mapped[bool]
    weight_kg: Mapped[float | None]
