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
