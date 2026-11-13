from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def today_kst(now: datetime | None = None) -> date:
    """모든 '오늘' 판단은 여기서만 한다 (서버/컨테이너 시간대와 무관)."""
    return (now or datetime.now(UTC)).astimezone(KST).date()
