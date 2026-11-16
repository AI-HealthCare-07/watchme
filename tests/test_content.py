import json
from itertools import product
from pathlib import Path

DATA = Path(__file__).parent.parent / "app" / "data"
STYLES = ("veg", "meat", "mixed")
BANNED = ("거르", "굶", "단식", "완치", "치료", "보장")


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _count(items, style, **tag):
    return sum(1 for i in items if style in i["styles"] and all(i[k] == v for k, v in tag.items()))


def test_breakfast_pool_sizes():
    meals = _load("meals.json")
    for habit, style in product(("skip", "light", "full"), STYLES):
        assert _count(meals["breakfast"], style, habit=habit) >= 7, (habit, style)


def test_lunch_pool_sizes():
    meals = _load("meals.json")
    for place, style in product(("home", "out", "store"), STYLES):
        assert _count(meals["lunch"], style, place=place) >= 10, (place, style)


def test_dinner_pool_sizes():
    meals = _load("meals.json")
    for style in STYLES:
        assert _count(meals["dinner"], style) >= 12, style


def test_exercise_activities():
    ex = _load("exercises.json")
    assert set(ex) == {"normal", "overweight", "obese", "high_risk"}
    for v in ex.values():
        assert len(v["activities"]) >= 6 and all("{m}" in a for a in v["activities"])
        assert v["label"] and v["rest"]
    for word in ("계단", "등산", "달리기", "줄넘기", "점프"):
        assert not any(word in a for a in ex["obese"]["activities"]), word


def test_tips():
    tips = _load("tips.json")
    texts = [t["text"] for t in tips]
    assert len(texts) >= 40 and len(set(texts)) == len(texts)
    tagged = lambda tag: sum(tag in t["tags"] for t in tips)
    assert tagged("free_meal") >= 8
    for tag in ("store", "out", "skip_breakfast"):
        assert tagged(tag) >= 5, tag
    allowed = {"general", "store", "out", "skip_breakfast", "free_meal"}
    assert all(set(t["tags"]) <= allowed for t in tips)


def test_no_meal_skipping_or_promises():
    text = "".join((DATA / n).read_text(encoding="utf-8") for n in ("meals.json", "exercises.json", "tips.json"))
    for word in BANNED:
        assert word not in text, word
