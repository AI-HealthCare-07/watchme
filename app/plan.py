"""30일 식단·운동 계획과 1년 체중 시나리오."""
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from app.risk import Assessment, assess

TEMPLATES_PATH = Path(__file__).parent / "data" / "templates.json"
VARIANTS = ("normal", "overweight", "obese", "high_risk")
DAYS = 30

# 시나리오 가정 (설계 문서): BMI 23 이상은 12개월간 6% 감량(선형), 미만은 유지
SCENARIO_MONTHS = (0, 3, 6, 12)
YEARLY_LOSS = 0.06


@dataclass(frozen=True)
class DayPlan:
    day: int
    meals: dict[str, str]
    exercise: str


@dataclass(frozen=True)
class ScenarioPoint:
    month: int
    weight_kg: float
    assessment: Assessment


@cache
def _templates() -> dict:
    return json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))


def variant_label(variant: str) -> str:
    return _templates()["variants"][variant]["label"]


def choose_variant(a: Assessment) -> str:
    if "높음" in (a.hypertension_level, a.diabetes_level):
        return "high_risk"
    return {"비만": "obese", "과체중": "overweight"}.get(a.bmi_band, "normal")


def make_plan(variant: str) -> list[DayPlan]:
    t = _templates()
    meals, exercise = t["meals"], t["variants"][variant]["exercise"]
    return [DayPlan(day=d, meals=dict(meals[(d - 1) % 7]), exercise=exercise[(d - 1) % 7]) for d in range(1, DAYS + 1)]


def scenario(a: Assessment, stats: dict | None = None) -> list[ScenarioPoint]:
    rate = YEARLY_LOSS if a.bmi >= 23 else 0.0
    points = []
    for m in SCENARIO_MONTHS:
        w = round(a.weight_kg * (1 - rate * m / 12), 1)
        points.append(ScenarioPoint(m, w, assess(a.sex, a.age, a.height_cm, w, stats=stats)))
    return points
