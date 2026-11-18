from io import BytesIO

from PIL import Image

from app.card import render_card
from app.weekly import Peer


def test_render_card_is_png_1080x1350():
    peer = Peer(days=6, minutes=20, share=0.29, label="70대 이상 남성")
    img = Image.open(BytesIO(render_card(1, 6, (True, True, True, False, True, True, None), peer)))
    assert img.format == "PNG" and img.size == (1080, 1350)
