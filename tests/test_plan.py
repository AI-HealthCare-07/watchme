from dataclasses import replace

import pytest

from datetime import date as _date

from app.plan import VARIANTS, Profile as _Profile, build_plan as _build, choose_variant, scenario, variant_label
from app.risk import assess
from tests.test_risk import STATS


def _a(h, w, sex="M", age=40):
    return assess(sex, age, h, w, stats=STATS)


@pytest.mark.parametrize("variant", VARIANTS)
def test_every_variant_has_30_full_days(variant):
    for diet, lunch, bf, minutes in (("veg", "home", "full", 10), ("meat", "out", "skip", 45), ("mixed", "store", "light", 25)):
        plan = _build(_Profile(variant, diet, lunch, bf, minutes, (0, 6)), _date(2026, 11, 16), "s", {1: 1, 2: 2})
        assert [d.day for d in plan] == list(range(1, 31))
        for d in plan:
            assert set(d.meals) == {"breakfast", "lunch", "dinner"}
            assert all(d.meals.values()) and d.exercise and d.tip
    assert variant_label(variant)


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


def test_scenario_risk_falls_as_weight_falls():
    pts = scenario(_a(170, 80), stats=STATS)
    dm = [p.assessment.diabetes_vs_avg for p in pts]
    assert dm == sorted(dm, reverse=True) and dm[-1] < dm[0]


# --- 맞춤 계획 (build_plan) ---
import json
import re
from datetime import date

from app.plan import Profile, build_plan, level_on, week_days, week_of

P = Profile("normal", "veg", "store", "skip", 25, (2, 5))
START = date(2026, 11, 16)  # 월요일
FREE = "자유 한 끼 🎉 먹고 싶은 걸 즐겨요"
_DATA = __import__("pathlib").Path(__file__).parent.parent / "app" / "data"
MEALS = json.loads((_DATA / "meals.json").read_text(encoding="utf-8"))
TIP_TAGS = {t["text"]: t["tags"] for t in json.loads((_DATA / "tips.json").read_text(encoding="utf-8"))}


def _minutes(text):
    return [int(m) for m in re.findall(r"(\d+)분", text)]


def test_plan_is_30_days_and_deterministic():
    plan = build_plan(P, START, "seed-a")
    assert len(plan) == 30 and [d.day for d in plan] == list(range(1, 31))
    assert plan[0].date == START and plan[29].date == date(2026, 12, 15)
    assert build_plan(P, START, "seed-a") == plan
    assert build_plan(P, START, "seed-b") != plan


def test_free_meal_on_chosen_weekdays_dinner():
    plan = build_plan(P, START, "s")
    free = [d for d in plan if d.free_meal]
    assert 8 <= len(free) <= 9
    assert {d.date.weekday() for d in free} == {2, 5}
    assert all(d.meals["dinner"] == FREE for d in free)
    assert all("국물·소스는 남기기" in d.notes and "단 음료 대신 물" in d.notes for d in free)
    assert not any(d.free_meal for d in plan if d.date.weekday() not in (2, 5))


def test_no_same_meal_two_days_in_a_row():
    plan = build_plan(P, START, "s")
    for a, b in zip(plan, plan[1:]):
        for k in ("breakfast", "lunch", "dinner"):
            if k == "dinner" and (a.free_meal or b.free_meal):
                continue
            assert a.meals[k] != b.meals[k], (a.day, k)


def test_veg_profile_gets_only_veg_menus():
    veg = {k: {i["text"] for i in MEALS[k] if "veg" in i["styles"]} for k in ("breakfast", "lunch", "dinner")}
    for d in build_plan(P, START, "s"):
        assert d.meals["breakfast"] in veg["breakfast"]
        assert d.meals["lunch"] in veg["lunch"]
        assert d.free_meal or d.meals["dinner"] in veg["dinner"]
    skip_store = {i["text"] for i in MEALS["breakfast"] if i["habit"] == "skip"} | {i["text"] for i in MEALS["lunch"] if i["place"] == "store"}
    assert all(d.meals["breakfast"] in skip_store and d.meals["lunch"] in skip_store for d in build_plan(P, START, "s"))


def test_exercise_ramps_by_week():
    plan = build_plan(P, START, "s")
    expected = {1: 15, 2: 20, 3: 25, 4: 25, 5: 25}
    for d in plan:
        if d.day % 7 == 0:
            assert d.exercise == "휴식 + 스트레칭 10분", d.day
        else:
            assert _minutes(d.exercise) == [expected[week_of(d.day)]], (d.day, d.exercise)


def test_high_risk_session_cap():
    hr = Profile("high_risk", "mixed", "home", "full", 45, (2, 5))
    plan = build_plan(hr, START, "s", {1: 1})
    week2 = [d for d in plan if week_of(d.day) == 2 and d.day % 7]
    assert all("25분" in d.exercise and d.exercise.endswith(" ×2회") for d in week2)
    assert all(m <= 30 for d in plan for m in _minutes(d.exercise))


def test_level_on_and_notes():
    assert level_on({1: 1, 2: 2}, 7) == 0
    assert level_on({1: 1, 2: 2}, 8) == 1
    assert level_on({1: 1, 2: 2}, 15) == 2
    assert level_on({}, 30) == 0
    plan = build_plan(P, START, "s", {1: 1})
    for d in plan:
        assert d.level == (1 if d.day >= 8 else 0)
        if d.day >= 8 and not d.free_meal:
            assert d.notes == ("밥은 1/3 공기", "저녁 7시 이후엔 먹지 않기")
        if d.day < 8 and not d.free_meal:
            assert d.notes == ()
    plan2 = build_plan(P, START, "s", {1: 1, 2: 2})
    assert {d.date.weekday() for d in plan2 if d.free_meal and d.day >= 15} == {5}
    assert all(d.notes == ("밥·면 없이 단백질·채소만", "저녁 7시 이후엔 먹지 않기") for d in plan2 if d.day >= 15 and not d.free_meal)
    assert all(m <= 70 for d in plan2 for m in _minutes(d.exercise))
    assert _minutes(plan2[28].exercise) == [45]  # 29일: 25 + 10*2


def test_high_risk_has_no_meal_notes():
    hr = Profile("high_risk", "meat", "out", "light", 25, (0, 6))
    assert all("밥" not in n for d in build_plan(hr, START, "s", {1: 2}) for n in d.notes)


def test_tips_unique_and_relevant():
    plan = build_plan(P, START, "s")
    tips = [d.tip for d in plan]
    assert len(set(tips)) == 30
    assert all("free_meal" in TIP_TAGS[d.tip] for d in plan if d.free_meal)
    tags = {t for tip in tips for t in TIP_TAGS[tip]}
    assert {"store", "skip_breakfast"} <= tags


def test_week_helpers():
    assert (week_of(1), week_of(7), week_of(8), week_of(28), week_of(29)) == (1, 1, 2, 4, 5)
    assert list(week_days(1)) == list(range(1, 8))
    assert list(week_days(5)) == [29, 30]


import re  # noqa: E402

from app.plan import candidates, floor_ok  # noqa: E402

PROFILE = _Profile("overweight", "mixed", "out", "light", 25, (2, 5))
START = _date(2026, 11, 16)


def test_candidates_ids_and_raw_text():
    c = candidates(PROFILE)
    assert {k[0] for k in c} == {"b", "l", "d", "e"} and all(k[1:].isdigit() for k in c)
    assert "b1" in c and "e1" in c
    assert any("{m}" in v for k, v in c.items() if k.startswith("e"))


def test_build_plan_excludes_texts_everywhere():
    c = candidates(PROFILE)
    gone = frozenset({c["d1"], c["e1"]})
    before = _build(PROFILE, START, "seed")
    plan = _build(PROFILE, START, "seed", exclude=gone)
    assert any(d.meals["dinner"] == c["d1"] for d in before)
    assert all(d.meals["dinner"] != c["d1"] for d in plan)
    e1 = re.compile(re.escape(c["e1"]).replace(re.escape("{m}"), r"\d+"))
    assert any(e1.fullmatch(d.exercise) for d in before)
    assert not any(e1.fullmatch(d.exercise) for d in plan)


def test_build_plan_without_exclude_unchanged():
    assert _build(PROFILE, START, "seed") == _build(PROFILE, START, "seed", exclude=frozenset())


def test_floor_ok_half_rule():
    c = candidates(PROFILE)
    for kind in "blde":
        items = [v for k, v in c.items() if k[0] == kind]
        keep = -(-len(items) // 2)  # 올림
        assert floor_ok(PROFILE, frozenset(items[: len(items) - keep]))
        assert not floor_ok(PROFILE, frozenset(items[: len(items) - keep + 1]))
