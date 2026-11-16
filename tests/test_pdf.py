from datetime import date
from io import BytesIO

from pypdf import PdfReader

from app.pdf import DISCLAIMER, render_week_pdf
from app.plan import Profile, build_plan, scenario, week_days
from app.risk import assess
from tests.test_risk import STATS

PROFILE = Profile("overweight", "mixed", "out", "light", 25, (2, 5))
START = date(2026, 11, 16)  # 월요일 → 수(3일)·토(6일)가 자유 한 끼


def _week(week, level=0, points=False):
    a = assess("M", 40, 170, 80, stats=STATS)
    plan = build_plan(PROFILE, START, "seed", {1: level} if level else None)
    days = [plan[d - 1] for d in week_days(week)]
    pdf = render_week_pdf(a, week, days, "저장된계획", level, "https://example.test/c/abc",
                          scenario(a, stats=STATS) if points else None)
    reader = PdfReader(BytesIO(pdf))
    text = "".join(p.extract_text() for p in reader.pages).replace(" ", "").replace("\n", "")
    return pdf, reader, text, days


def test_week_pdf_one_page_with_week_days():
    pdf, reader, text, days = _week(2)
    assert pdf.startswith(b"%PDF") and len(reader.pages) == 1
    for d in days:
        assert d.meals["breakfast"].replace(" ", "") in text
    assert "지킴" in text and DISCLAIMER.replace(" ", "") in text
    assert "자유한끼" in text and "저장된계획" in text and "2주차" in text
    assert b"NanumGothic" in pdf


def test_week1_pdf_has_summary_page():
    _, reader, text, _ = _week(1, points=True)
    assert len(reader.pages) == 2
    assert "시나리오" in text and "내결과요약" in text


def test_week_pdf_shows_level():
    _, _, text, _ = _week(2, level=1)
    assert "강도1단계" in text and "밥은1/3공기" in text
    _, _, text0, _ = _week(2)
    assert "강도" not in text0


def test_last_week_has_two_days():
    _, reader, text, days = _week(5)
    assert len(days) == 2 and len(reader.pages) == 1 and "5주차" in text
