from datetime import UTC, date, datetime

from sqlalchemy import BigInteger, ForeignKey, String, Text
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
    # 맞춤 질문 답변 (시작 직후엔 비어 있음)
    diet_style: Mapped[str | None] = mapped_column(String(8))
    lunch_place: Mapped[str | None] = mapped_column(String(8))
    breakfast: Mapped[str | None] = mapped_column(String(8))
    exercise_min: Mapped[int | None]
    free_days: Mapped[str | None] = mapped_column(String(8))  # 정렬된 "a,b" (0=월)

    @property
    def setup_done(self) -> bool:
        return self.free_days is not None


class DayLog(Base):
    __tablename__ = "day_logs"

    # (token, day) 복합 기본키 = 같은 날 기록은 하나뿐
    token: Mapped[str] = mapped_column(ForeignKey("trials.token", ondelete="CASCADE"), primary_key=True)
    day: Mapped[int] = mapped_column(primary_key=True)
    kept: Mapped[bool]
    weight_kg: Mapped[float | None]


class WeekDecision(Base):
    __tablename__ = "week_decisions"

    # 주차마다 강도 결정은 한 번
    token: Mapped[str] = mapped_column(ForeignKey("trials.token", ondelete="CASCADE"), primary_key=True)
    week: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[int]


class KakaoAccount(Base):
    __tablename__ = "kakao_accounts"

    kakao_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # 카카오 회원번호
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)  # Fernet 암호문 (키는 서버 .env에만)
    can_message: Mapped[bool]  # talk_message 동의 + 토큰 유효
    notify: Mapped[bool] = mapped_column(default=True)  # 사용자가 켠/끈 상태
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class TrialOwner(Base):
    __tablename__ = "trial_owners"

    token: Mapped[str] = mapped_column(ForeignKey("trials.token", ondelete="CASCADE"), primary_key=True)
    kakao_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kakao_accounts.kakao_id"))


class SentMessage(Base):
    __tablename__ = "sent_messages"

    # (계정, 날짜, 종류)마다 한 번만 = 중복 발송 방지
    kakao_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    day: Mapped[date] = mapped_column(primary_key=True)  # KST 날짜 (속성 이름 date는 타입과 겹쳐서 day)
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)  # morning/evening/report/welcome


class NextTrial(Base):
    __tablename__ = "next_trials"

    # 한 체험에서 다음 30일 도전은 한 번만
    token: Mapped[str] = mapped_column(ForeignKey("trials.token", ondelete="CASCADE"), primary_key=True)
    next_token: Mapped[str] = mapped_column(ForeignKey("trials.token"))
