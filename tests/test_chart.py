import re

from app.chart import weight_svg


def _coords(svg):
    pts = re.search(r'points="([^"]+)"', svg).group(1)
    return [tuple(map(float, p.split(","))) for p in pts.split()]


def test_needs_two_points():
    assert weight_svg([(0, 80.0)], 7) is None


def test_draws_line_dots_and_labels():
    svg = str(weight_svg([(0, 80.0), (3, 79.5), (7, 79.2)], 7))
    assert svg.startswith("<svg") and svg.count("<circle") == 3
    assert len(_coords(svg)) == 3
    assert "80.0" in svg and "79.2" in svg
    assert 'aria-label="체중 그래프: 80.0kg에서 79.2kg"' in svg
    assert all(0 <= x <= 300 and 0 <= y <= 120 for x, y in _coords(svg))


def test_flat_weights_do_not_divide_by_zero():
    svg = str(weight_svg([(0, 80.0), (5, 80.0)], 30))
    assert all(0 <= x <= 300 and 0 <= y <= 120 for x, y in _coords(svg))
