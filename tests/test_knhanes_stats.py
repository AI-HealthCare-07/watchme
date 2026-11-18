import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("pyreadstat")

from scripts.knhanes_stats import fit_logistic  # noqa: E402


def test_fit_logistic_recovers_known_coefficients():
    rng = np.random.default_rng(0)
    x = rng.uniform(17, 35, 40_000)
    y = (rng.random(x.size) < 1 / (1 + np.exp(-(-8 + 0.25 * x)))).astype(float)
    w = rng.uniform(300, 30_000, x.size)  # 설문 가중치처럼 크기가 제각각
    b0, b1 = fit_logistic(x, y, w)
    assert b1 == pytest.approx(0.25, abs=0.03)
    assert b0 == pytest.approx(-8, abs=0.8)


def test_walk_table_shares():
    pd = pytest.importorskip("pandas")
    from scripts.knhanes_stats import walk_table
    df = pd.DataFrame({"sex": [1] * 6, "age_band": ["40"] * 6, "w": [1.0] * 6,
                       "BE3_31": [8, 7, 2, 1, 99, 8], "BE3_32": [0, 0, 1, 88, 0, 88], "BE3_33": [30, 20, 0, 88, 30, 88]})
    s = walk_table(df)["M"]["40"]
    assert s["n"] == 4  # 99(모름)·88(무응답 시간) 제외, 0일은 0분으로 남김
    assert s["share"]["20"][5] == 0.5  # 6일↑·20분↑: 7일30분, 6일20분
    assert s["share"]["30"][5] == 0.25
    assert s["share"]["10"][0] == 0.75  # 1일↑·10분↑
    assert s["share"]["60"][0] == 0.25  # 1일 60분
