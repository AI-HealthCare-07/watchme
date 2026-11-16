"""카카오톡 '나에게 보내기' 메시지 문장. 텍스트 템플릿은 200자 제한."""
from app.plan import PlanDay

LIMIT = 200
LINE = 32  # 폰 말풍선에서 한 줄로 읽히는 정도
SUMMARY_DAYS = (7, 14, 21, 28)

WELCOME = "연결됐어요 ✅ 아침 7:30엔 오늘 계획, 저녁 9시엔 기록 확인을 보내 드릴게요."
REPORT = "30일 완주! 리포트가 나왔어요 🎉"
BUTTON = {"morning": "오늘 계획 보기", "evening": "기록하기", "evening_logged": "기록 보기", "report": "리포트 보기"}


def fit(text: str) -> str:
    lines = [line if len(line) <= LINE else line[:LINE - 1] + "…" for line in text.split("\n")]
    text = "\n".join(lines)
    return text if len(text) <= LIMIT else text[:LIMIT - 1] + "…"


def morning(d: PlanDay, sunday: bool) -> str:
    lines = [
        f"Day {d.day} · 오늘 계획",
        f"🍳 아침 {d.meals['breakfast']}",
        f"🍱 점심 {d.meals['lunch']}",
        f"🍲 저녁 {d.meals['dinner']}",  # 자유 한 끼 날은 이미 FREE_DINNER
        f"🚶 {d.exercise}",
    ]
    if sunday:
        lines.append("⚖️ 오늘은 체중 재는 날이에요")
    return fit("\n".join(lines))


def evening(n: int, logged: bool, sunday: bool) -> str:
    if logged:
        text = "오늘 기록 고마워요. 바꿀 게 있으면 눌러 주세요."
    else:
        text = "오늘 잘 지키셨나요? 10초면 기록돼요." + (" 체중도 같이 적어 주세요." if sunday else "")
    if n in SUMMARY_DAYS:
        text += "\n이번 주 요약이 나왔어요. 다음 주 강도도 골라 주세요."
    return text
