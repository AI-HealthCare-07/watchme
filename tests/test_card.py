from io import BytesIO

from PIL import Image

from app.card import render_card
from app.weekly import Peer


def test_render_card_is_png_1080x1350():
    peer = Peer(days=6, minutes=20, share=0.29, label="70대 이상 남성")
    img = Image.open(BytesIO(render_card(1, 6, (True, True, True, False, True, True, None), peer)))
    assert img.format == "PNG" and img.size == (1080, 1350)


def test_card_states_the_compared_criteria(monkeypatch):
    from PIL import ImageDraw
    texts = []
    real = ImageDraw.ImageDraw.text
    monkeypatch.setattr(ImageDraw.ImageDraw, "text", lambda self, xy, text, *a, **k: (texts.append(text), real(self, xy, text, *a, **k))[1])
    render_card(1, 7, (True,) * 7, Peer(days=6, minutes=20, share=0.29, label="40대 남성"))
    assert "40대 남성 10명 중 3명만" in texts and "주 6일·하루 20분 이상 걸어요" in texts
    assert not any("이만큼" in t for t in texts)  # '7일 중 7일'(쉬는 날 포함)을 가리키지 않게
