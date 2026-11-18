from datetime import date

from app import messages
from app.plan import FREE_DINNER, PlanDay


def day(n=3, dinner="현미밥과 생선구이", exercise="걷기 20분", free=False, lunch="닭가슴살 샐러드"):
    meals = {"breakfast": "그릭요거트와 견과", "lunch": lunch, "dinner": FREE_DINNER if free else dinner}
    return PlanDay(n, date(2026, 11, 18), meals, exercise, free, (), "팁", 0)


def test_morning_lines():
    lines = messages.morning(day(), sunday=False).split("\n")
    assert lines == ["Day 3 · 오늘 계획", "🍳 아침 그릭요거트와 견과", "🍱 점심 닭가슴살 샐러드",
                     "🍲 저녁 현미밥과 생선구이", "🚶 걷기 20분"]


def test_morning_sunday_weight_line_and_free_meal():
    text = messages.morning(day(free=True), sunday=True)
    assert text.split("\n")[-1] == "⚖️ 오늘은 체중 재는 날이에요"
    assert "자유 한 끼 🎉" in text


def test_evening_variants():
    assert messages.evening(5, logged=False, sunday=False) == "오늘 잘 지키셨나요? 10초면 기록돼요."
    assert messages.evening(5, logged=True, sunday=False) == "오늘 기록 고마워요. 바꿀 게 있으면 눌러 주세요."
    assert messages.evening(5, logged=False, sunday=True) == "오늘 잘 지키셨나요? 10초면 기록돼요. 체중도 같이 적어 주세요."
    assert messages.evening(14, logged=True, sunday=False).split("\n")[-1] == "이번 주 요약이 나왔어요. 다음 주 강도도 골라 주세요."
    assert "\n" not in messages.evening(15, logged=False, sunday=False)


def test_fit_caps_200():
    long = "아주 긴 메뉴 이름이 계속 이어지는 경우 " * 5
    text = messages.morning(day(dinner=long, lunch=long, exercise=long), sunday=True)
    assert len(text) <= messages.LIMIT
    assert all(len(line) <= 32 for line in text.split("\n"))
    assert messages.fit("가" * 300) == "가" * 31 + "…"


def test_week_message_lines_never_truncated():
    from app.weekly import Peer
    text = messages.week(4, 7, Peer(days=6, minutes=60, share=0.07, label="70대 이상 남성"))
    assert "…" not in text
    assert all(len(line) <= messages.LINE for line in text.split("\n"))
    assert text.split("\n") == ["🏅 4주차 리포트가 나왔어요!", "7일 중 7일 지켰어요.",
                                "주 6일·하루 60분 이상 걷는 70대 이상 남성은", "100명 중 7명이에요. 그 안에 드셨어요!"]


def test_week_message_without_peer():
    assert messages.week(1, 0, None).split("\n") == ["🏅 1주차 리포트가 나왔어요!", "이번 주는 쉬어 갔어요. 다시 시작해 봐요."]
