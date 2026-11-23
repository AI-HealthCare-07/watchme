from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today_kst(now: datetime | None = None) -> date:
    """모든 '오늘' 판단은 여기서만 한다 (서버/컨테이너 시간대와 무관)."""
    return (now or datetime.now(UTC)).astimezone(KST).date()


def slot_kst(now: datetime | None = None) -> time:
    """지금 KST 시각을 30분 칸으로 내림 (cron이 0·30분에 조금 늦게 돌아도 같은 칸)."""
    t = (now or datetime.now(UTC)).astimezone(KST)
    return time(t.hour, t.minute // 30 * 30)
