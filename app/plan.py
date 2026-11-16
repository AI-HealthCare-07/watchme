"""맞춤 30일 식단·운동 계획과 1년 체중 시나리오."""
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from math import ceil
from pathlib import Path

from app.risk import Assessment, assess

DATA = Path(__file__).parent / "data"
VARIANTS = ("normal", "overweight", "obese", "high_risk")
DAYS = 30
WEEKS = 5  # 1–7, 8–14, 15–21, 22–28, 29–30
MAX_LEVEL = 2  # 강도 단계 상한
FREE_DINNER = "자유 한 끼 🎉 먹고 싶은 걸 즐겨요"
FREE_NOTES = ("국물·소스는 남기기", "단 음료 대신 물")
LEVEL_NOTES = {1: ("밥은 1/3 공기", "저녁 7시 이후엔 먹지 않기"), 2: ("밥·면 없이 단백질·채소만", "저녁 7시 이후엔 먹지 않기")}
RAMP = {1: 0.6, 2: 0.75, 3: 0.9}  # 주차별 운동 시간 비율 (그 외 1.0)

# 시나리오 가정 (설계 문서): BMI 23 이상은 12개월간 6% 감량(선형), 미만은 유지
SCENARIO_MONTHS = (0, 3, 6, 12)
YEARLY_LOSS = 0.06


@dataclass(frozen=True)
class Profile:
    variant: str
    diet_style: str
    lunch_place: str
    breakfast: str
    exercise_min: int
    free_days: tuple[int, int]


@dataclass(frozen=True)
class PlanDay:
    day: int
    date: date
    meals: dict[str, str]
    exercise: str
    free_meal: bool
    notes: tuple[str, ...]
    tip: str
    level: int


@dataclass(frozen=True)
class ScenarioPoint:
    month: int
    weight_kg: float
    assessment: Assessment


@cache
def _content(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def variant_label(variant: str) -> str:
    return _content("exercises.json")[variant]["label"]


def week_of(day: int) -> int:
    return (day - 1) // 7 + 1


def week_days(week: int) -> range:
    return range(7 * week - 6, min(7 * week, DAYS) + 1)


def level_on(decisions: dict[int, int], day: int) -> int:
    """주 w의 결정은 7w+1일부터 적용."""
    applied = [w for w in decisions if 7 * w + 1 <= day]
    return decisions[max(applied)] if applied else 0


def _shuffled(items: list, seed: str, slot: str) -> list:
    items = list(items)
    random.Random(f"{seed}:{slot}").shuffle(items)
    return items


def _exercise(profile: Profile, day: int, level: int, activities: list[str], rest: str) -> str:
    if day % 7 == 0:
        return rest
    minutes = max(10, ceil(profile.exercise_min * RAMP.get(week_of(day), 1.0) / 5) * 5) + 10 * level
    text = activities[(day - 1) % len(activities)]
    if profile.variant == "high_risk":
        if minutes > 30:  # 한 번 30분 상한 → 나눠서 두 번
            return text.format(m=min(30, ceil(minutes / 2 / 5) * 5)) + " ×2회"
        return text.format(m=minutes)
    return text.format(m=min(minutes, 70))


def build_plan(profile: Profile, start_date: date, seed: str, decisions: dict[int, int] | None = None) -> list[PlanDay]:
    decisions = decisions or {}
    meals, ex = _content("meals.json"), _content("exercises.json")[profile.variant]
    style = profile.diet_style
    pools = {
        "breakfast": [i["text"] for i in meals["breakfast"] if i["habit"] == profile.breakfast and style in i["styles"]],
        "lunch": [i["text"] for i in meals["lunch"] if i["place"] == profile.lunch_place and style in i["styles"]],
        "dinner": [i["text"] for i in meals["dinner"] if style in i["styles"]],
    }
    pools = {k: _shuffled(v, seed, k) for k, v in pools.items()}
    activities = _shuffled(ex["activities"], seed, "exercise")
    tips = _content("tips.json")
    relevant = {"skip_breakfast"} if profile.breakfast == "skip" else set()
    relevant |= {profile.lunch_place} & {"store", "out"}
    tip_pools = {
        "free_meal": _shuffled([t["text"] for t in tips if "free_meal" in t["tags"]], seed, "tips"),
        "relevant": _shuffled([t["text"] for t in tips if relevant & set(t["tags"])], seed, "tips"),
        "general": _shuffled([t["text"] for t in tips if "general" in t["tags"]], seed, "tips"),
    }
    used: set[str] = set()

    def take(*kinds: str) -> str:
        for kind in kinds:
            for t in tip_pools[kind]:
                if t not in used:
                    used.add(t)
                    return t
        raise RuntimeError("팁이 모자라요")

    plan = []
    for d in range(1, DAYS + 1):
        day_date = start_date + timedelta(days=d - 1)
        level = level_on(decisions, d)
        free_days = profile.free_days if level < 2 else (max(profile.free_days),)
        free = day_date.weekday() in free_days
        day_meals = {k: pool[(d - 1) % len(pool)] for k, pool in pools.items()}
        if free:
            day_meals["dinner"], notes = FREE_DINNER, FREE_NOTES
        elif level and profile.variant != "high_risk":
            notes = LEVEL_NOTES[level]
        else:
            notes = ()
        if free:
            tip = take("free_meal", "general")
        elif d % 3 == 1:
            tip = take("relevant", "general")
        else:
            tip = take("general")
        plan.append(PlanDay(d, day_date, day_meals, _exercise(profile, d, level, activities, ex["rest"]), free, notes, tip, level))
    return plan


def choose_variant(a: Assessment) -> str:
    if "높음" in (a.hypertension_level, a.diabetes_level):
        return "high_risk"
    return {"비만": "obese", "과체중": "overweight"}.get(a.bmi_band, "normal")


def scenario(a: Assessment, stats: dict | None = None) -> list[ScenarioPoint]:
    rate = YEARLY_LOSS if a.bmi >= 23 else 0.0
    points = []
    for m in SCENARIO_MONTHS:
        w = round(a.weight_kg * (1 - rate * m / 12), 1)
        points.append(ScenarioPoint(m, w, assess(a.sex, a.age, a.height_cm, w, stats=stats)))
    return points
