"""30일 계획 PDF (읽기·인쇄용). 기록은 QR로 연결되는 웹 체크 페이지에서 한다."""
from io import BytesIO
from pathlib import Path

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.plan import DayPlan, ScenarioPoint, choose_variant, variant_label
from app.risk import Assessment

DISCLAIMER = "본 결과는 공개 통계 기반의 참고용이며 의학적 진단이 아닙니다."

FONTS = Path(__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("NanumGothic", FONTS / "NanumGothic-Regular.ttf"))
pdfmetrics.registerFont(TTFont("NanumGothic-Bold", FONTS / "NanumGothic-Bold.ttf"))
pdfmetrics.registerFontFamily("NanumGothic", normal="NanumGothic", bold="NanumGothic-Bold")

INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#6b7280")
LINE = colors.HexColor("#d1d5db")
HEAD_BG = colors.HexColor("#eef2f7")
LEVEL_COLOR = {"낮음": "#15803d", "보통": "#1f2933", "높음": "#b91c1c"}


def _style(size=10, bold=False, color=INK, leading=None, **kw) -> ParagraphStyle:
    return ParagraphStyle(
        "s", fontName="NanumGothic-Bold" if bold else "NanumGothic", fontSize=size,
        leading=leading or size * 1.45, textColor=color, wordWrap="CJK", **kw,
    )


H1, H2, BODY, SMALL, CELL = _style(20, True), _style(13, True, spaceBefore=6, spaceAfter=4), _style(10), _style(8, color=MUTED), _style(8.5)


def _table(rows, widths, header=True) -> Table:
    data = [[c if not isinstance(c, str) else Paragraph(c, CELL) for c in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
    t.setStyle(TableStyle(style))
    return t


def _risk(vs: float, lvl: str) -> str:
    return f'평균의 {vs:.1f}배 <font color="{LEVEL_COLOR[lvl]}">({lvl})</font>'


def _qr(url: str, size=32 * mm) -> Drawing:
    w = QrCodeWidget(url)
    x0, y0, x1, y1 = w.getBounds()
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(w)
    return d


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("NanumGothic", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(15 * mm, 10 * mm, DISCLAIMER)
    canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"{doc.page}")
    canvas.restoreState()


def render_pdf(a: Assessment, plan: list[DayPlan], points: list[ScenarioPoint], check_url: str) -> bytes:
    sex = "남성" if a.sex == "M" else "여성"
    band = f"{a.age // 10 * 10}대" if a.age < 70 else "70대 이상"
    story = [
        Paragraph("Watchme 30일 생활습관 챌린지", H1),
        Spacer(0, 2 * mm),
        Paragraph(f"{sex} · {a.age}세 · 계획: {variant_label(choose_variant(a))}", _style(11, color=MUTED)),
        Spacer(0, 6 * mm),
        Paragraph(f"나와 한국 평균 ({sex} {band})", H2),
        _table(
            [["", "나", "한국 평균"],
             ["키", f"{a.height_cm:g} cm", f"{a.avg_height_cm:.1f} cm"],
             ["몸무게", f"{a.weight_kg:g} kg", f"{a.avg_weight_kg:.1f} kg"],
             ["BMI", f"{a.bmi:.1f} ({a.bmi_band})", "—"]],
            [40 * mm, 60 * mm, 60 * mm],
        ),
        Paragraph("참고 위험도", H2),
        Paragraph("같은 성별·연령대 평균과 비교한 유병률 배수입니다.", SMALL),
        _table(
            [["", "평균 대비"],
             ["고혈압", _risk(a.hypertension_vs_avg, a.hypertension_level)],
             ["당뇨", _risk(a.diabetes_vs_avg, a.diabetes_level)]],
            [40 * mm, 120 * mm],
        ),
        Paragraph("1년 시나리오", H2),
        Paragraph("계획을 꾸준히 지켰을 때의 가정입니다 (BMI 23 이상: 1년에 체중 6% 감량, 미만: 유지). 예측이 아닙니다.", SMALL),
        _table(
            [["시점", "체중", "BMI", "고혈압", "당뇨"]]
            + [[("지금" if p.month == 0 else f"{p.month}개월"), f"{p.weight_kg:g} kg",
                f"{p.assessment.bmi:.1f}", _risk(p.assessment.hypertension_vs_avg, p.assessment.hypertension_level),
                _risk(p.assessment.diabetes_vs_avg, p.assessment.diabetes_level)] for p in points],
            [24 * mm, 26 * mm, 20 * mm, 45 * mm, 45 * mm],
        ),
        Spacer(0, 6 * mm),
        _table(
            [[_qr(check_url), Paragraph(
                "<b>매일 기록하기</b><br/>QR을 찍으면 내 체크 페이지가 열립니다. 지켰는지와 체중을 기록하면 "
                f"30일 뒤 변화 리포트를 볼 수 있어요.<br/><font color='#6b7280' size='7.5'>{check_url}</font>", BODY)]],
            [38 * mm, 122 * mm], header=False,
        ),
        Spacer(0, 4 * mm),
        Paragraph(DISCLAIMER, SMALL),
    ]

    for week in range(0, len(plan), 7):
        days = plan[week:week + 7]
        story += [
            PageBreak(),
            Paragraph(f"{week // 7 + 1}주차 (Day {days[0].day}–{days[-1].day})", H2),
            _table(
                [["일", "아침", "점심", "저녁", "운동", "지킴<br/>○/×", "체중"]]
                + [[str(d.day), d.meals["breakfast"], d.meals["lunch"], d.meals["dinner"], d.exercise, "", ""] for d in days],
                [9 * mm, 33 * mm, 35 * mm, 35 * mm, 30 * mm, 10 * mm, 16 * mm],
            ),
            Spacer(0, 3 * mm),
            Paragraph("인쇄해서 쓰셔도 되지만, 리포트에는 웹 체크 페이지에 기록한 값만 반영됩니다.", SMALL),
        ]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm,
                            bottomMargin=18 * mm, title="Watchme 30일 계획", author="Watchme")
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
