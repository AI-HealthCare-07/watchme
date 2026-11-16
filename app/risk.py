"""참고 위험도: 같은 성별·연령대 평균 대비 BMI 구간 유병률 배수.

vs_avg = 유병률(성별, 연령대, BMI 구간) / 유병률(성별, 연령대, 전체)
수치는 app/data/korea_stats.json (국민건강영양조사 원시자료에서 계산, scripts/knhanes_stats.py).
"""
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

STATS_PATH = Path(__file__).parent / "data" / "korea_stats.json"

LIMITS = {"age": (18, 100), "height_cm": (120, 220), "weight_kg": (30, 250)}
LABELS = {"age": "나이", "height_cm": "키", "weight_kg": "몸무게"}


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


def level(vs_avg: float) -> str:
    if vs_avg < 0.8:
        return "낮음"
    if vs_avg < 1.3:
        return "보통"
    return "높음"


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
    ht = group["hypertension"][band] / group["hypertension"]["all"]
    dm = group["diabetes"][band] / group["diabetes"]["all"]
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
