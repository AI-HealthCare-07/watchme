"""체중 그래프: 서버에서 그리는 작은 SVG (라이브러리 없음)."""
from markupsafe import Markup

W, H = 300, 120
LEFT, RIGHT, TOP, BOTTOM = 12, 252, 22, 100  # 오른쪽 여백은 마지막 값 글자 자리


def weight_svg(points: list[tuple[int, float]], last_day: int) -> Markup | None:
    """points: (일차, kg). 0일차 = 시작 체중. 점이 2개 미만이면 None."""
    if len(points) < 2:
        return None
    kgs = [kg for _, kg in points]
    lo, hi = min(kgs) - 0.5, max(kgs) + 0.5
    xy = [(LEFT + (RIGHT - LEFT) * day / max(last_day, 1), TOP + (BOTTOM - TOP) * (hi - kg) / (hi - lo))
          for day, kg in points]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{5 if i == len(xy) - 1 else 3.5}"/>' for i, (x, y) in enumerate(xy))
    (x0, y0), (x1, y1) = xy[0], xy[-1]
    first, last = kgs[0], kgs[-1]
    return Markup(
        f'<svg class="wchart" viewBox="0 0 {W} {H}" role="img" aria-label="체중 그래프: {first:.1f}kg에서 {last:.1f}kg">'
        f'<line x1="0" y1="{BOTTOM + 12}" x2="{W}" y2="{BOTTOM + 12}" stroke="#e5e8eb"/>'
        f'<polyline points="{line}" fill="none" stroke="#0ca678" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<g fill="#0ca678">{dots}</g>'
        f'<text x="{x0:.1f}" y="{y0 - 9:.1f}" font-size="12" fill="#6b7684">{first:.1f}</text>'
        f'<text x="{x1 + 8:.1f}" y="{y1 + 4:.1f}" font-size="13" font-weight="700" fill="#191f28">{last:.1f}</text>'
        "</svg>"
    )
