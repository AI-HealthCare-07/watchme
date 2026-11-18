"""자랑 카드 PNG (1080×1350). 체중·위험도·토큰은 인자로 받지 않아 카드에 들어갈 수 없다."""
import os
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

from app.weekly import Peer

W, H = 1080, 1350
PAD = 80
STOPS = ((0x20, 0xC9, 0x97), (0x0C, 0xA6, 0x78), (0x08, 0x7F, 0x5B))
HERE = Path(__file__).parent
BOLD, REGULAR = HERE / "fonts" / "NanumGothic-Bold.ttf", HERE / "fonts" / "NanumGothic-Regular.ttf"
ICON = HERE / "static" / "icons" / "icon-192.png"
GREEN = STOPS[1]


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _fit(draw: ImageDraw.ImageDraw, text: str, path: Path, size: int, max_w: int) -> ImageFont.FreeTypeFont:
    """한 줄에 들어갈 때까지 글자를 줄인다(긴 나이대 이름 대비)."""
    while size > 24 and draw.textlength(text, font=_font(path, size)) > max_w:
        size -= 2
    return _font(path, size)


def _background() -> Image.Image:
    # 작은 그림에 대각선 그라데이션을 칠하고 키운다(픽셀마다 계산하지 않으려고)
    w, h = W // 10, H // 10
    small = Image.new("RGB", (w, h))
    px = []
    for y in range(h):
        for x in range(w):
            t = (x / w + y / h) / 2
            a, b, u = (STOPS[0], STOPS[1], t * 2) if t < 0.5 else (STOPS[1], STOPS[2], t * 2 - 1)
            px.append(tuple(round(a[i] + (b[i] - a[i]) * u) for i in range(3)))
    small.putdata(px)
    return small.resize((W, H), Image.BICUBIC).convert("RGBA")


def _mark(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, mark: bool | None) -> None:
    if mark:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 255))
        draw.line([(cx - r * .42, cy + r * .02), (cx - r * .1, cy + r * .34), (cx + r * .45, cy - r * .3)],
                  fill=GREEN + (255,), width=r // 5, joint="curve")
    else:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 60))
        if mark is False:
            k = r * .3
            for d in (1, -1):
                draw.line([(cx - k, cy - k * d), (cx + k, cy + k * d)], fill=(255, 255, 255, 230), width=r // 7)
        else:
            draw.ellipse((cx - 6, cy - 6, cx + 6, cy + 6), fill=(255, 255, 255, 230))


def render_card(week: int, kept: int, marks: tuple[bool | None, ...], peer: Peer) -> bytes:
    img = _background()
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    white, soft = (255, 255, 255, 255), (255, 255, 255, 215)

    icon = Image.open(ICON).convert("RGBA").resize((96, 96), Image.LANCZOS)
    layer.alpha_composite(icon, (PAD, PAD))
    d.text((PAD + 120, PAD + 48), "WATCHME", font=_font(BOLD, 46), fill=white, anchor="lm")

    d.text((PAD, 330), f"30일 생활습관 챌린지 · {week}주차", font=_font(REGULAR, 48), fill=soft)
    big = _font(BOLD, 124)
    d.text((PAD, 410), f"7일 중 {kept}일", font=big, fill=white)
    d.text((PAD, 555), "해냈어요", font=big, fill=white)

    r, gap = 50, 26
    for i, mark in enumerate(marks):
        _mark(d, PAD + r + i * (2 * r + gap), 790, r, mark)

    box_w = W - 2 * PAD
    d.rounded_rectangle((PAD, 900, W - PAD, 1130), radius=36, fill=(255, 255, 255, 42))
    line1 = f"{peer.label} {peer.ratio}만"
    d.text((PAD + 48, 975), line1, font=_fit(d, line1, BOLD, 64, box_w - 96), fill=white, anchor="lm")
    d.text((PAD + 48, 1062), "이만큼 꾸준히 움직여요", font=_font(REGULAR, 54), fill=white, anchor="lm")

    host = urlparse(os.environ.get("PUBLIC_BASE_URL", "https://evrd.fyi")).netloc or "evrd.fyi"
    d.text((PAD, H - 90), "국민건강영양조사 · 걷기 기준", font=_font(REGULAR, 34), fill=soft, anchor="lm")
    d.text((W - PAD, H - 90), host, font=_font(BOLD, 40), fill=white, anchor="rm")

    img.alpha_composite(layer)
    out = BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
