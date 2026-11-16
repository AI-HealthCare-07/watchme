from io import BytesIO

from pypdf import PdfReader

from app.pdf import DISCLAIMER, render_pdf
from app.plan import choose_variant, make_plan, scenario
from app.risk import assess
from tests.test_risk import STATS


def _pdf():
    a = assess("M", 40, 170, 80, stats=STATS)
    plan = make_plan(choose_variant(a))
    return render_pdf(a, plan, scenario(a, stats=STATS), "https://example.test/c/abc", "저장된계획"), plan


def test_pdf_has_korean_text_and_required_sections():
    pdf, plan = _pdf()
    assert pdf.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) >= 3
    text = "".join(p.extract_text() for p in reader.pages).replace(" ", "").replace("\n", "")
    assert DISCLAIMER.replace(" ", "") in text
    assert "시나리오" in text
    assert plan[0].meals["breakfast"].replace(" ", "") in text


def test_pdf_embeds_font():
    pdf, _ = _pdf()
    assert b"NanumGothic" in pdf


def test_pdf_uses_given_plan_label():
    # 통계가 나중에 바뀌어도 PDF 계획 이름은 체험 시작 때 저장된 계획을 따른다
    pdf, _ = _pdf()
    assert "저장된계획" in PdfReader(BytesIO(pdf)).pages[0].extract_text()
