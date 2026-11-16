from dataclasses import replace

import pytest

from app.plan import VARIANTS, choose_variant, make_plan, scenario
from app.risk import assess
from tests.test_risk import STATS


def _a(h, w, sex="M", age=40):
    return assess(sex, age, h, w, stats=STATS)


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_variant_has_30_full_days(variant):
    plan = make_plan(variant)
    assert [d.day for d in plan] == list(range(1, 31))
    for d in plan:
        assert set(d.meals) == {"breakfast", "lunch", "dinner"}
        assert all(d.meals.values()) and d.exercise


def test_plan_is_deterministic():
    assert make_plan("obese") == make_plan("obese")


def test_variant_by_band_and_risk():
    normal = _a(175, 65)  # BMI 21.2, 위험 보통
    obese = _a(170, 80)  # BMI 27.7, 당뇨 vs_avg 2.0 → 높음
    assert choose_variant(normal) == "normal"
    assert choose_variant(obese) == "high_risk"
    assert choose_variant(replace(obese, diabetes_level="보통", hypertension_level="보통")) == "obese"
    assert choose_variant(replace(normal, bmi_band="과체중")) == "overweight"
    assert choose_variant(replace(normal, bmi_band="저체중")) == "normal"


def test_scenario_loses_6_percent_a_year_when_bmi_23_or_more():
    pts = scenario(_a(170, 80), stats=STATS)
    assert [p.month for p in pts] == [0, 3, 6, 12]
    assert [p.weight_kg for p in pts] == [80.0, 78.8, 77.6, 75.2]
    assert all(p.assessment.age == 40 for p in pts)
    assert pts[-1].assessment.bmi < pts[0].assessment.bmi


def test_scenario_keeps_weight_when_bmi_below_23():
    pts = scenario(_a(175, 65), stats=STATS)
    assert {p.weight_kg for p in pts} == {65.0}
