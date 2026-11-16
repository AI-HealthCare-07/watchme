import os
import time
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.clock import today_kst
from app.db import get_db
from app.pdf import DISCLAIMER, render_pdf
from app.plan import DAYS, make_plan, scenario, variant_label
from app.ratelimit import RateLimiter, client_ip
from app.report import build_report, days_left
from app.risk import InvalidInput, assess, get_stats, vs_text
from app.service import current_day, get_logs, get_trial, save_day, start_trial

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


@router.get("/c/{token}")
def check_page(request: Request, token: str, day: int | None = None,
               db: Session = Depends(get_db), stats: dict = Depends(get_stats)):
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요. 링크를 다시 확인해 주세요.")
    today = current_day(trial, today_kst())
    logs = {log.day: log for log in get_logs(db, token)}
    selected = day if day and 1 <= day <= today else today
    return _page(
        request, "check.html",
        token=token, a=assess(trial.sex, trial.age, trial.height_cm, trial.weight_kg, stats=stats),
        label=variant_label(trial.plan_variant), plan=make_plan(trial.plan_variant), logs=logs,
        today=today, selected=selected, days=DAYS,
        finished=not days_left(trial, today_kst()),
    )


@router.post("/c/{token}/day/{n}")
def save(request: Request, token: str, n: int, kept: str = Form(""), weight_kg: str = Form(""),
         db: Session = Depends(get_db)):
    if not DAY_PER_IP.hit(client_ip(request), time.time()):
        return _too_many(request)
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요.")
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
    today = today_kst()
    report = build_report(trial, get_logs(db, token), today, stats=stats)
    return _page(request, "report.html", token=token, report=report, left=days_left(trial, today))


@router.get("/c/{token}/plan.pdf")
def plan_pdf(request: Request, token: str, db: Session = Depends(get_db), stats: dict = Depends(get_stats)):
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요.")
    a = assess(trial.sex, trial.age, trial.height_cm, trial.weight_kg, stats=stats)
    pdf = render_pdf(a, make_plan(trial.plan_variant), scenario(a, stats=stats), f"{PUBLIC_BASE_URL}/c/{token}",
                     variant_label(trial.plan_variant))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="watchme-30days.pdf"'})
