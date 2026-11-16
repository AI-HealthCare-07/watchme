"""참고 위험도: 같은 성별·연령대 평균 대비, 내 BMI에서의 예상 유병률 배수.

vs_avg = sigmoid(b0 + b1·BMI) / 유병률(성별, 연령대, 전체)
b0, b1은 성별×연령대×질환마다 가중 로지스틱 회귀로 구함 (scripts/knhanes_stats.py,
국민건강영양조사 원시자료). 결과는 app/data/korea_stats.json.
"""
import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path

STATS_PATH = Path(__file__).parent / "data" / "korea_stats.json"

LIMITS = {"age": (18, 100), "height_cm": (120, 220), "weight_kg": (30, 250)}
LABELS = {"age": "나이", "height_cm": "키", "weight_kg": "몸무게"}
# 자료가 드문 극단 BMI는 외삽하지 않고 경계값으로 계산
MODEL_BMI_RANGE = (16.0, 40.0)


class InvalidInput(ValueError):
    pass


@dataclass(frozen=True)
class Assessment:
    sex: str
    age: int
    height_cm: float
    weight_kg: float
    bmi: float
    bmi_band: str
    avg_height_cm: float
    avg_weight_kg: float
    hypertension_vs_avg: float
    diabetes_vs_avg: float
    hypertension_level: str
    diabetes_level: str


@cache
def load_stats() -> dict:
    return json.loads(STATS_PATH.read_text(encoding="utf-8"))


def get_stats() -> dict | None:
    """FastAPI 의존성 (테스트에서 교체). 통계 파일이 아직 없으면 None → 화면에서 '준비 중'."""
    try:
        return load_stats()
    except FileNotFoundError:
        return None


def bmi_band(bmi: float) -> str:
    # 대한비만학회 기준
    if bmi < 18.5:
        return "저체중"
    if bmi < 23:
        return "정상"
    if bmi < 25:
        return "과체중"
    return "비만"


def age_band(age: int) -> str:
    # 10세 단위, 18–29는 "20", 70 이상은 "70"
    return str(min(max(age // 10 * 10, 20), 70))


def group_label(sex: str, age: int) -> str:
    """비교 집단 이름: 같은 성별·10세 나이대 (예: "40대 남성")."""
    band = age_band(age)
    years = "18~29세" if age < 20 else "70대 이상" if band == "70" else f"{band}대"
    return f"{years} {'남성' if sex == 'M' else '여성'}"


def level(vs_avg: float) -> str:
    if vs_avg < 0.8:
        return "낮음"
    if vs_avg < 1.3:
        return "보통"
    return "높음"


def vs_avg(model: dict, bmi: float) -> float:
    x = min(max(bmi, MODEL_BMI_RANGE[0]), MODEL_BMI_RANGE[1])
    p = 1 / (1 + math.exp(-(model["b0"] + model["b1"] * x)))
    return p / model["all"]


def vs_text(vs: float) -> str:
    pct = round((vs - 1) * 100)
    if pct == 0:
        return "평균 수준"
    return f"평균보다 {abs(pct)}% {'높음' if pct > 0 else '낮음'}"


def _validate(sex, age, height_cm, weight_kg) -> None:
    if sex not in ("M", "F"):
        raise InvalidInput("성별을 선택해 주세요.")
    for key, value in (("age", age), ("height_cm", height_cm), ("weight_kg", weight_kg)):
        lo, hi = LIMITS[key]
        if not lo <= value <= hi:
            raise InvalidInput(f"{LABELS[key]}는 {lo}~{hi} 사이로 입력해 주세요.")


def assess(sex: str, age: int, height_cm: float, weight_kg: float, stats: dict | None = None) -> Assessment:
    _validate(sex, age, height_cm, weight_kg)
    stats = stats or load_stats()
    group = stats["groups"][sex].get(age_band(age))
    if group is None:
        raise InvalidInput("해당 연령대의 통계가 없습니다.")

    bmi = round(weight_kg / (height_cm / 100) ** 2, 1)
    band = bmi_band(bmi)
    ht = vs_avg(group["hypertension"], bmi)
    dm = vs_avg(group["diabetes"], bmi)
    return Assessment(
        sex=sex,
        age=age,
        height_cm=height_cm,
        weight_kg=weight_kg,
        bmi=bmi,
        bmi_band=band,
        avg_height_cm=group["avg_height_cm"],
        avg_weight_kg=group["avg_weight_kg"],
        hypertension_vs_avg=round(ht, 2),
        diabetes_vs_avg=round(dm, 2),
        hypertension_level=level(ht),
        diabetes_level=level(dm),
    )
