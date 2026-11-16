"""주간 계획 PDF (읽기·인쇄용). 기록은 QR로 연결되는 웹 체크 페이지에서 한다."""
import re
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

from app.plan import PlanDay, ScenarioPoint
from app.risk import Assessment, group_label, vs_text

DISCLAIMER = "본 결과는 공개 통계 기반의 참고용이며 의학적 진단이 아닙니다."

FONTS = Path(__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("NanumGothic", FONTS / "NanumGothic-Regular.ttf"))
pdfmetrics.registerFont(TTFont("NanumGothic-Bold", FONTS / "NanumGothic-Bold.ttf"))
pdfmetrics.registerFontFamily("NanumGothic", normal="NanumGothic", bold="NanumGothic-Bold")

INK = colors.HexColor("#191f28")
MUTED = colors.HexColor("#6b7684")
LINE = colors.HexColor("#e5e8eb")
BRAND = colors.HexColor("#0ca678")
BRAND_INK = colors.HexColor("#087f5b")
BRAND_SOFT = colors.HexColor("#e6fcf5")
LEVEL_COLOR = {"낮음": "#1c7ed6", "보통": "#191f28", "높음": "#e03131"}
WEEKDAYS = "월화수목금토일"
# 나눔고딕에 없는 이모지는 PDF에서 뺀다
EMOJI = re.compile("[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F]")


def _plain(text: str) -> str:
    return EMOJI.sub("", text).replace("  ", " ").strip()


def _style(size=10, bold=False, color=INK, leading=None, **kw) -> ParagraphStyle:
    return ParagraphStyle(
        "s", fontName="NanumGothic-Bold" if bold else "NanumGothic", fontSize=size,
        leading=leading or size * 1.45, textColor=color, wordWrap="CJK", **kw,
    )


H1, H2 = _style(18, True, color=BRAND_INK), _style(13, True, spaceBefore=6, spaceAfter=4)
BODY, SMALL, CELL, CELL_B = _style(10), _style(8, color=MUTED), _style(8.5), _style(8.5, True)


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
        style.append(("BACKGROUND", (0, 0), (-1, 0), BRAND_SOFT))
    t.setStyle(TableStyle(style))
    return t


def _risk(vs: float, lvl: str) -> str:
    return f'{vs_text(vs)} <font color="{LEVEL_COLOR[lvl]}">({lvl})</font>'


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


def _qr_box(check_url: str) -> Table:
    return _table(
        [[_qr(check_url, 28 * mm), Paragraph(
            "<b>매일 기록하기</b><br/>QR을 찍으면 내 기록 화면이 열려요. 지켰는지와 체중을 기록하면 "
            f"주간 요약과 30일 리포트를 볼 수 있어요.<br/><font color='#6b7684' size='7.5'>{check_url}</font>", BODY)]],
        [34 * mm, 146 * mm], header=False,
    )


def _summary_page(a: Assessment, points: list[ScenarioPoint], check_url: str, label: str) -> list:
    sex = "남성" if a.sex == "M" else "여성"
    group = group_label(a.sex, a.age)
    return [
        Paragraph("내 결과 요약", H1),
        Spacer(0, 2 * mm),
        Paragraph(f"{sex} · {a.age}세 · 계획: {label}", _style(11, color=MUTED)),
        Spacer(0, 5 * mm),
        Paragraph(f"나와 {group} 평균", H2),
        _table(
            [["", "나", f"{group} 평균"],
             ["키", f"{a.height_cm:g} cm", f"{a.avg_height_cm:.1f} cm"],
             ["몸무게", f"{a.weight_kg:g} kg", f"{a.avg_weight_kg:.1f} kg"],
             ["BMI", f"{a.bmi:.1f} ({a.bmi_band})", "—"]],
            [40 * mm, 70 * mm, 70 * mm],
        ),
        Paragraph("참고 위험도", H2),
        Paragraph(f"{group} 평균과 비교한 내 BMI의 예상 유병률이에요.", SMALL),
        _table(
            [["", f"{group} 평균 대비"],
             ["고혈압", _risk(a.hypertension_vs_avg, a.hypertension_level)],
             ["당뇨", _risk(a.diabetes_vs_avg, a.diabetes_level)]],
            [40 * mm, 140 * mm],
        ),
        Paragraph("1년 시나리오", H2),
        Paragraph("계획을 꾸준히 지켰을 때의 가정이에요 (BMI 23 이상: 1년에 체중 6% 감량, 미만: 유지). 예측이 아니에요.", SMALL),
        _table(
            [["시점", "체중", "BMI", "고혈압", "당뇨"]]
            + [[("지금" if p.month == 0 else f"{p.month}개월"), f"{p.weight_kg:g} kg",
                f"{p.assessment.bmi:.1f}", _risk(p.assessment.hypertension_vs_avg, p.assessment.hypertension_level),
                _risk(p.assessment.diabetes_vs_avg, p.assessment.diabetes_level)] for p in points],
            [26 * mm, 28 * mm, 22 * mm, 52 * mm, 52 * mm],
        ),
        Spacer(0, 6 * mm),
        _qr_box(check_url),
    ]


def render_week_pdf(a: Assessment, week: int, days: list[PlanDay], label: str, level: int, check_url: str,
                    points: list[ScenarioPoint] | None = None) -> bytes:
    first, last = days[0].date, days[-1].date
    title = f"{week}주차 · {first.month}/{first.day}~{last.month}/{last.day} · {label}"
    if level:
        title += f" · 강도 {level}단계"
    rows = [["날짜", "아침", "점심", "저녁", "운동", "지킴<br/>○/×", "체중"]]
    for d in days:
        dinner = _plain(d.meals["dinner"])
        if d.notes:
            dinner += "<br/><font color='#087f5b' size='7.5'>" + " · ".join(d.notes) + "</font>"
        rows.append([
            Paragraph(f"<b>{d.date.month}/{d.date.day}</b><br/>{WEEKDAYS[d.date.weekday()]} · Day {d.day}", CELL),
            _plain(d.meals["breakfast"]), _plain(d.meals["lunch"]),
            Paragraph(dinner, CELL_B if d.free_meal else CELL), _plain(d.exercise), "", "",
        ])
    table = _table(rows, [17 * mm, 33 * mm, 34 * mm, 36 * mm, 30 * mm, 12 * mm, 18 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, i + 1), (-1, i + 1), BRAND_SOFT) for i, d in enumerate(days) if d.free_meal]))
    story = [
        Paragraph("Watchme 30일 생활습관 챌린지", _style(9, True, color=BRAND)),
        Spacer(0, 1 * mm),
        Paragraph(title, H1),
        Spacer(0, 4 * mm),
        table,
        Spacer(0, 2 * mm),
        Paragraph("초록 줄은 자유 한 끼 날이에요. 인쇄해서 써도 되지만, 리포트에는 웹 기록 화면에 적은 값만 반영돼요.", SMALL),
        Spacer(0, 4 * mm),
        _table([[Paragraph(f"<b>이번 주 팁</b> · {_plain(days[0].tip)}", BODY)]], [180 * mm], header=False),
        Spacer(0, 4 * mm),
        _qr_box(check_url),
    ]
    if points:
        story += [PageBreak(), *_summary_page(a, points, check_url, label)]

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                            bottomMargin=18 * mm, title=f"Watchme {week}주차 계획", author="Watchme")
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
