import pytest

from app.risk import InvalidInput, assess


def _group(h, w, ht, dm):
    return {"avg_height_cm": h, "avg_weight_kg": w, "hypertension": ht, "diabetes": dm}


FLAT = {"all": 0.2, "저체중": 0.2, "정상": 0.2, "과체중": 0.2, "비만": 0.2}
STATS = {
    "source": "test",
    "year": "test",
    "groups": {
        "M": {
            "40": _group(172.0, 75.0, FLAT, {"all": 0.2, "저체중": 0.1, "정상": 0.15, "과체중": 0.2, "비만": 0.4}),
        },
        "F": {
            "40": _group(160.0, 58.0, FLAT, FLAT),
        },
    },
}


def test_same_as_group_average_is_one():
    a = assess("F", 45, 160, 58, stats=STATS)
    assert a.hypertension_vs_avg == pytest.approx(1.0)
    assert a.hypertension_level == "보통"
    assert (a.avg_height_cm, a.avg_weight_kg) == (160.0, 58.0)


def test_obese_band_double_prevalence():
    a = assess("M", 40, 170, 80, stats=STATS)  # BMI 27.7
    assert a.bmi_band == "비만"
    assert a.diabetes_vs_avg == pytest.approx(2.0)
    assert a.diabetes_level == "높음"


def test_low_band_level():
    a = assess("M", 40, 180, 58, stats=STATS)  # BMI 17.9
    assert a.bmi_band == "저체중"
    assert a.diabetes_vs_avg == pytest.approx(0.5)
    assert a.diabetes_level == "낮음"


def test_bmi_boundary_23_is_overweight():
    # 23.0 정확히: 키 100cm면 몸무게 23kg이 BMI 23이지만 범위 밖이라, 200cm·92kg 사용
    a = assess("M", 40, 200, 92, stats=STATS)
    assert a.bmi == pytest.approx(23.0)
    assert a.bmi_band == "과체중"


def test_age_maps_to_decade_band():
    assert assess("M", 49, 172, 75, stats=STATS).avg_height_cm == 172.0


@pytest.mark.parametrize(
    "sex,age,h,w",
    [
        ("M", 17, 170, 70),
        ("M", 101, 170, 70),
        ("M", 40, 119, 70),
        ("M", 40, 221, 70),
        ("M", 40, 170, 29),
        ("M", 40, 170, 251),
        ("X", 40, 170, 70),
        ("", 40, 170, 70),
    ],
)
def test_out_of_range_rejected(sex, age, h, w):
    with pytest.raises(InvalidInput):
        assess(sex, age, h, w, stats=STATS)


def test_missing_age_group_rejected():
    with pytest.raises(InvalidInput):
        assess("M", 70, 170, 70, stats=STATS)  # STATS에 70대 없음
