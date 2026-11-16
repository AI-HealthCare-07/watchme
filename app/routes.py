import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.clock import today_kst
from app.db import get_db
from app.pdf import DISCLAIMER, render_week_pdf
from app.plan import DAYS, LEVEL_NOTES, WEEKS, build_plan, level_on, scenario, variant_label, week_days, week_of
from app.ratelimit import RateLimiter, client_ip
from app.progress import can_level_up, plateau, streak, summary_week, week_summary
from app.report import build_report, days_left
from app.risk import InvalidInput, assess, get_stats, vs_text
from app.service import (
    InvalidSetup, current_day, decide_level, get_decisions, get_logs, get_trial, profile_of, save_day, save_setup,
    start_trial,
)

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

START_PER_IP = RateLimiter(5, 600)
START_GLOBAL = RateLimiter(500, 86400)
DAY_PER_IP = RateLimiter(30, 60)
LIMITERS = (START_PER_IP, START_GLOBAL, DAY_PER_IP)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["DISCLAIMER"] = DISCLAIMER
templates.env.filters["vs_text"] = vs_text
router = APIRouter()


def _page(request: Request, name: str, status: int = 200, **ctx):
    return templates.TemplateResponse(request, name, ctx, status_code=status)


def _error(request: Request, status: int, message: str):
    return _page(request, "error.html", status, message=message)


def _too_many(request: Request):
    return _error(request, 429, "요청이 너무 많아요. 잠시 후 다시 시도해 주세요.")


def _to_setup(token: str):
    return RedirectResponse(f"/c/{token}/setup", status_code=303)


def _num(raw: str, cast, label: str):
    try:
        return cast(raw)
    except ValueError:
        raise InvalidInput(f"{label}를 숫자로 입력해 주세요.") from None


EXAMPLE = ("M", 45, 172, 82)  # 시작 화면 예시 인물


@router.get("/")
def landing(request: Request, stats: dict | None = Depends(get_stats)):
    example = assess(*EXAMPLE, stats=stats) if stats else None
    return _page(request, "landing.html", example=example, preparing=stats is None)


@router.get("/start")
def start_form(request: Request, stats: dict | None = Depends(get_stats)):
    return _page(request, "start.html", form={}, error=None, preparing=stats is None)


@router.post("/start")
def start(
    request: Request,
    sex: str = Form(""),
    age: str = Form(""),
    height_cm: str = Form(""),
    weight_kg: str = Form(""),
    db: Session = Depends(get_db),
    stats: dict | None = Depends(get_stats),
):
    if stats is None:
        return _error(request, 503, "통계 데이터를 준비 중이에요. 곧 열릴 예정입니다.")
    now = time.time()
    if not START_PER_IP.hit(client_ip(request), now) or not START_GLOBAL.hit("global", now):
        return _too_many(request)
    form = {"sex": sex, "age": age, "height_cm": height_cm, "weight_kg": weight_kg}
    try:
        trial = start_trial(
            db, sex, _num(age, int, "나이"), _num(height_cm, float, "키"), _num(weight_kg, float, "몸무게"),
            today=today_kst(), stats=stats,
        )
    except InvalidInput as e:
        return _page(request, "start.html", 400, form=form, error=str(e))
    return RedirectResponse(f"/c/{trial.token}/result", status_code=303)


@router.get("/c/{token}/result")
def result_page(request: Request, token: str, db: Session = Depends(get_db), stats: dict = Depends(get_stats)):
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요. 링크를 다시 확인해 주세요.")
    a = assess(trial.sex, trial.age, trial.height_cm, trial.weight_kg, stats=stats)
    return _page(request, "result.html", token=token, a=a, later=scenario(a, stats=stats)[1].assessment)


@router.get("/c/{token}/setup")
def setup_form(request: Request, token: str, db: Session = Depends(get_db)):
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요. 링크를 다시 확인해 주세요.")
    if trial.setup_done:
        return RedirectResponse(f"/c/{token}", status_code=303)
    return _page(request, "setup.html", token=token, form={"free_days": []}, error=None)


@router.post("/c/{token}/setup")
def setup(
    request: Request,
    token: str,
    diet_style: str = Form(""),
    lunch_place: str = Form(""),
    breakfast: str = Form(""),
    exercise_min: str = Form(""),
    free_days: list[str] = Form([]),
    db: Session = Depends(get_db),
):
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요.")
    if trial.setup_done:
        return RedirectResponse(f"/c/{token}", status_code=303)
    form = {"diet_style": diet_style, "lunch_place": lunch_place, "breakfast": breakfast,
            "exercise_min": exercise_min, "free_days": free_days}
    try:
        try:
            minutes, days = int(exercise_min), [int(d) for d in free_days]
        except ValueError:
            raise InvalidSetup("선택지 중에서 골라 주세요") from None
        save_setup(db, token, diet_style, lunch_place, breakfast, minutes, days)
    except InvalidSetup as e:
        return _page(request, "setup.html", 400, token=token, form=form, error=str(e))
    return RedirectResponse(f"/c/{token}", status_code=303)


# 의심 카드 원인: 날마다 하나씩 돌아가며
DOUBTS = (
    "라떼·주스 같은 음료에 숨은 당은 없었나요?",
    "입이 심심할 때 집어 먹은 간식은 없었나요?",
    "소스·드레싱·국물을 생각보다 많이 먹진 않았나요?",
    "한 그릇 양이 조금씩 늘진 않았나요?",
)


@router.get("/c/{token}")
def check_page(request: Request, token: str, day: int | None = None,
               db: Session = Depends(get_db), stats: dict = Depends(get_stats)):
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요. 링크를 다시 확인해 주세요.")
    if not trial.setup_done:
        return _to_setup(token)
    today = current_day(trial, today_kst())
    log_list = get_logs(db, token)
    decisions = get_decisions(db, token)
    plan = build_plan(profile_of(trial), trial.start_date, token, decisions)
    w = summary_week(today, log_list)
    summary = week_summary(trial, log_list, w, stats=stats) if w else None
    can_up = bool(w) and can_level_up(log_list, w, decisions)
    next_level = min(plan[today - 1].level + 1, 2)
    return _page(
        request, "check.html",
        token=token, a=assess(trial.sex, trial.age, trial.height_cm, trial.weight_kg, stats=stats),
        label=variant_label(trial.plan_variant), plan=plan, logs={log.day: log for log in log_list},
        today=today, selected=day if day and 1 <= day <= today else today, days=DAYS,
        level=plan[today - 1].level, streak=streak(log_list, today),
        doubt=DOUBTS[today % 4] if plateau(log_list, today) else None,
        summary=summary, can_up=can_up, decided=decisions.get(w) if w else None,
        next_level=next_level, next_notes=() if trial.plan_variant == "high_risk" else LEVEL_NOTES[next_level],
        week=week_of(today), finished=not days_left(trial, today_kst()),
    )


@router.post("/c/{token}/week/{w}/level")
def level(request: Request, token: str, w: int, choice: str = Form(""), db: Session = Depends(get_db)):
    if not DAY_PER_IP.hit(client_ip(request), time.time()):
        return _too_many(request)
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요.")
    if not trial.setup_done:
        return _to_setup(token)
    logs = get_logs(db, token)
    ok = choice in ("up", "keep") and summary_week(current_day(trial, today_kst()), logs) == w
    if not ok or not can_level_up(logs, w, get_decisions(db, token)):
        return _error(request, 400, "지금은 강도를 정할 수 없어요. 기록 화면에서 다시 확인해 주세요.")
    decide_level(db, token, w, choice == "up")
    return RedirectResponse(f"/c/{token}", status_code=303)


@router.post("/c/{token}/day/{n}")
def save(request: Request, token: str, n: int, kept: str = Form(""), weight_kg: str = Form(""),
         db: Session = Depends(get_db)):
    if not DAY_PER_IP.hit(client_ip(request), time.time()):
        return _too_many(request)
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요.")
    if not trial.setup_done:
        return _to_setup(token)
    if not 1 <= n <= current_day(trial, today_kst()):
        return _error(request, 400, "아직 기록할 수 없는 날이에요.")
    try:
        weight = float(weight_kg) if weight_kg.strip() else None
        save_day(db, token, n, kept == "1", weight)
    except ValueError:
        return _error(request, 400, "몸무게는 30~250 사이 숫자로 입력해 주세요.")
    return RedirectResponse(f"/c/{token}", status_code=303)


@router.get("/c/{token}/report")
def report_page(request: Request, token: str, db: Session = Depends(get_db), stats: dict = Depends(get_stats)):
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요.")
    if not trial.setup_done:
        return _to_setup(token)
    today = today_kst()
    report = build_report(trial, get_logs(db, token), today, stats=stats)
    return _page(request, "report.html", token=token, report=report, left=days_left(trial, today))


@router.get("/c/{token}/plan.pdf")
def plan_pdf(request: Request, token: str, db: Session = Depends(get_db)):
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요.")
    week = week_of(current_day(trial, today_kst()))
    return RedirectResponse(f"/c/{token}/week/{week}.pdf", status_code=303)


@router.get("/c/{token}/week/{w}.pdf")
def week_pdf(request: Request, token: str, w: str, db: Session = Depends(get_db), stats: dict = Depends(get_stats)):
    trial = get_trial(db, token)
    week = int(w) if w.isdigit() else 0
    if trial is None or not 1 <= week <= WEEKS:
        return _error(request, 404, "계획표를 찾을 수 없어요.")
    if not trial.setup_done:
        return _to_setup(token)
    if week > 1 and current_day(trial, today_kst()) < 7 * (week - 1):
        return _error(request, 400, f"{week}주차 계획표는 {7 * (week - 1)}일째부터 받을 수 있어요.")
    decisions = get_decisions(db, token)
    plan = build_plan(profile_of(trial), trial.start_date, token, decisions)
    days = [plan[d - 1] for d in week_days(week)]
    a = assess(trial.sex, trial.age, trial.height_cm, trial.weight_kg, stats=stats)
    pdf = render_week_pdf(a, week, days, variant_label(trial.plan_variant), level_on(decisions, days[0].day),
                          f"{PUBLIC_BASE_URL}/c/{token}", scenario(a, stats=stats) if week == 1 else None)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="watchme-week{week}.pdf"'})
