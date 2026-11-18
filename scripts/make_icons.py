"""대표 아이콘(맥박 W) 파일을 만든다. 한 번 실행해서 결과를 커밋한다.

실행: .venv/Scripts/python scripts/make_icons.py  (Pillow 필요, 서버에는 필요 없음)
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"
STOPS = ["#20c997", "#0ca678", "#099268"]  # 왼쪽 위 → 오른쪽 아래
LINE = [(12, 52), (25, 52), (32, 32), (42, 70), (50, 40), (58, 70), (68, 32), (75, 52), (88, 52)]  # 100×100 기준
SS = 4  # 4배로 그리고 줄여서 계단 현상을 없앤다

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="{STOPS[0]}"/><stop offset=".55" stop-color="{STOPS[1]}"/><stop offset="1" stop-color="{STOPS[2]}"/>
</linearGradient></defs>
<rect width="100" height="100" rx="24" fill="url(#g)"/>
<polyline points="{' '.join(f'{x},{y}' for x, y in LINE)}" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


def rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def gradient(w: int, h: int) -> Image.Image:
    """대각선 3색 그라데이션 (작은 판을 만들어 늘린다)."""
    a, b, c = (rgb(s) for s in STOPS)
    n = 64
    small = Image.new("RGB", (n, n))
    for y in range(n):
        for x in range(n):
            t = (x + y) / (2 * (n - 1))
            lo, hi, u = (a, b, t / .55) if t < .55 else (b, c, (t - .55) / .45)
            small.putpixel((x, y), tuple(round(lo[i] + (hi[i] - lo[i]) * u) for i in range(3)))
    return small.resize((w, h), Image.BILINEAR)


def pulse(draw: ImageDraw.ImageDraw, pts, width: int, fill) -> None:
    draw.line(pts, fill=fill, width=width, joint="curve")
    r = width / 2
    for x, y in (pts[0], pts[-1]):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def icon(size: int, rounded: bool) -> Image.Image:
    s = size * SS
    img = gradient(s, s).convert("RGBA")
    if rounded:
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=round(s * .24), fill=255)
        img.putalpha(mask)
    k = s / 100
    pulse(ImageDraw.Draw(img), [(x * k, y * k) for x, y in LINE], round(7 * k), "white")
    return img.resize((size, size), Image.LANCZOS)


def og() -> Image.Image:
    """카톡·SNS 링크 미리보기 1200×630: 초록 바탕, 가로 맥박선, 가운데 흰 아이콘."""
    w, h = 1200 * 2, 630 * 2
    img = gradient(w, h).convert("RGBA")
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cy = h // 2
    pulse(d, [(-20, cy), (w + 20, cy)], 10, (255, 255, 255, 70))
    box = 520
    x0, y0 = (w - box) // 2, (h - box) // 2
    d.rounded_rectangle((x0, y0, x0 + box, y0 + box), radius=round(box * .24), fill="white")
    k = box / 100
    pulse(d, [(x0 + x * k, y0 + y * k) for x, y in LINE], round(7 * k), rgb(STOPS[1]))
    img.alpha_composite(layer)
    return img.convert("RGB").resize((1200, 630), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "favicon.svg").write_text(SVG, encoding="utf-8")
    icon(180, rounded=False).convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)  # iOS가 모서리를 깎음
    icon(192, rounded=True).save(OUT / "icon-192.png", optimize=True)
    icon(512, rounded=True).save(OUT / "icon-512.png", optimize=True)
    og().save(OUT / "og.png", optimize=True)
    print("\n".join(f"{p.name} {p.stat().st_size}" for p in sorted(OUT.iterdir())))
