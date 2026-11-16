"""국민건강영양조사(KNHANES) 2022–2024 원시자료 → app/data/korea_stats.json

성별 × 연령대(10세) × 질환마다:
  - all: 가중 유병률
  - b0, b1: 유병 ~ BMI 가중 로지스틱 회귀 (IRLS)
  - avg_height_cm, avg_weight_kg: 가중 평균
가중치는 검진·설문 가중치 wt_itvex, 3개년 통합이라 연도 수로 나눔.
점추정만 하므로 층(kstrata)·집락(psu)은 쓰지 않음 (표준오차가 필요해지면 추가).

실행 (저장소 루트, 원시자료는 data/raw/ — 커밋 금지):
  pip install ".[stats]"
  python -m scripts.knhanes_stats data/raw
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

from app.risk import STATS_PATH, age_band, bmi_band

YEARS = ("22", "23", "24")
COLS = ["sex", "age", "HE_ht", "HE_wt", "HE_BMI", "HE_HP", "HE_DM_HbA1c", "wt_itvex"]
# 질환: (변수, 유병 코드)
DISEASES = {"hypertension": ("HE_HP", 4), "diabetes": ("HE_DM_HbA1c", 3)}
DEFINITIONS = {
    "hypertension": "HE_HP=4: 수축기 140mmHg 이상 또는 이완기 90mmHg 이상 또는 고혈압 약 복용",
    "diabetes": "HE_DM_HbA1c=3: 공복혈당 126mg/dL 이상, 의사 진단, 혈당강하제·인슐린, 또는 당화혈색소 6.5% 이상",
}
AGE_BANDS = ("20", "30", "40", "50", "60", "70")


def fit_logistic(x: np.ndarray, y: np.ndarray, w: np.ndarray, iters: int = 50) -> tuple[float, float]:
    """가중 로지스틱 회귀 y ~ sigmoid(b0 + b1·x), IRLS(뉴턴법). (b0, b1) 반환."""
    X = np.column_stack([np.ones_like(x), x])
    b = np.zeros(2)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        hessian = X.T @ (X * (w * p * (1 - p))[:, None])
        step = np.linalg.solve(hessian, X.T @ (w * (y - p)))
        b += step
        if np.abs(step).max() < 1e-10:
            break
    return float(b[0]), float(b[1])


def load(raw_dir: Path) -> pd.DataFrame:
    frames = [pyreadstat.read_sas7bdat(raw_dir / f"hn{y}_all.sas7bdat", usecols=COLS)[0] for y in YEARS]
    df = pd.concat(frames, ignore_index=True)
    df["w"] = df["wt_itvex"] / len(YEARS)
    df = df[(df["age"] >= 19) & df["HE_BMI"].notna() & df["w"].notna()].copy()
    df["age_band"] = df["age"].astype(int).map(age_band)
    return df


def build(df: pd.DataFrame) -> dict:
    groups: dict = {"M": {}, "F": {}}
    for code, sex in ((1, "M"), (2, "F")):
        for band in AGE_BANDS:
            g = df[(df["sex"] == code) & (df["age_band"] == band)]
            entry = {
                "n": len(g),
                "avg_height_cm": round(float(np.average(g["HE_ht"], weights=g["w"])), 1),
                "avg_weight_kg": round(float(np.average(g["HE_wt"], weights=g["w"])), 1),
            }
            for name, (col, code_pos) in DISEASES.items():
                d = g[g[col].notna()]
                y = (d[col] == code_pos).to_numpy(float)
                b0, b1 = fit_logistic(d["HE_BMI"].to_numpy(float), y, d["w"].to_numpy(float))
                entry[name] = {
                    "n": len(d),
                    "all": round(float(np.average(y, weights=d["w"])), 4),
                    "b0": round(b0, 5),
                    "b1": round(b1, 5),
                }
            groups[sex][band] = entry
    return {
        "source": "국민건강영양조사 2022–2024 원시자료 (질병관리청), 19세 이상, 가중치 wt_itvex",
        "year": "2022-2024",
        "method": "성별×연령대(10세)별 가중 로지스틱 회귀: 유병 ~ BMI",
        "definitions": DEFINITIONS,
        "groups": groups,
    }


def calibration(df: pd.DataFrame, stats: dict) -> None:
    """검증 출력: BMI 구간별 실제 가중 유병률 vs 모델 평균 예측. 크게 어긋나면 모델을 다시 볼 것."""
    df = df.assign(bmi_band=df["HE_BMI"].map(bmi_band))
    print(f"{'group':8}{'disease':14}{'band':6}{'n':>6}{'obs':>8}{'model':>8}")
    for code, sex in ((1, "M"), (2, "F")):
        for age in AGE_BANDS:
            g = df[(df["sex"] == code) & (df["age_band"] == age)]
            for name, (col, code_pos) in DISEASES.items():
                m = stats["groups"][sex][age][name]
                for band in ("저체중", "정상", "과체중", "비만"):
                    d = g[g[col].notna() & (g["bmi_band"] == band)]
                    if len(d) < 30:
                        continue
                    obs = np.average(d[col] == code_pos, weights=d["w"])
                    pred = np.average(1 / (1 + np.exp(-(m["b0"] + m["b1"] * d["HE_BMI"]))), weights=d["w"])
                    print(f"{sex + age:8}{name:14}{band:6}{len(d):6}{obs:8.3f}{pred:8.3f}")


if __name__ == "__main__":
    data = load(Path(sys.argv[1] if len(sys.argv) > 1 else "data/raw"))
    stats = build(data)
    STATS_PATH.write_text(json.dumps(stats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    calibration(data, stats)
    print(f"wrote {STATS_PATH} ({len(data)} adults)")
