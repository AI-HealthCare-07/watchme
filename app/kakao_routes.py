"""카카오 로그인·연결 경로. 카카오 키가 없으면 모두 404."""
import secrets
import time
from datetime import time as dtime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import accounts, kakao
from app.clock import today_kst
from app.db import get_db
from app.messages import welcome
from app.plan import DAYS
from app.ratelimit import client_ip
from app.routes import AUTH_PER_IP, DAY_PER_IP, PUBLIC_BASE_URL, _error, _too_many
from app.service import get_trial

COOKIE = "wm_kakao"
router = APIRouter()


def _require_enabled():
    if not kakao.enabled():
        raise HTTPException(404)


def _begin(request: Request, trial_token: str):
    if not AUTH_PER_IP.hit(client_ip(request), time.time()):
        return _too_many(request)
    state = secrets.token_urlsafe(16)
    # 체험 토큰은 서명한 쿠키에만 두고 카카오로 가는 URL엔 넣지 않는다
    resp = RedirectResponse(kakao.authorize_url(state), status_code=303)
    resp.set_cookie(COOKIE, kakao.sign(f"{state}.{trial_token}"), max_age=600, httponly=True,
                    secure=PUBLIC_BASE_URL.startswith("https://"), samesite="lax")
    return resp


@router.get("/c/{token}/kakao", dependencies=[Depends(_require_enabled)])
def kakao_start(request: Request, token: str, db: Session = Depends(get_db)):
    if get_trial(db, token) is None:
        return _error(request, 404, "체험을 찾을 수 없어요.")
    return _begin(request, token)


@router.get("/auth/kakao", dependencies=[Depends(_require_enabled)])
def kakao_login(request: Request):
    return _begin(request, "")


@router.get("/auth/kakao/callback", dependencies=[Depends(_require_enabled)])
def kakao_callback(request: Request, code: str = "", state: str = "", error: str = "",
                   db: Session = Depends(get_db)):
    value = kakao.unsign(request.cookies.get(COOKIE, ""))
    saved_state, _, token = (value or "").partition(".")
    if not value or not state or not secrets.compare_digest(saved_state, state):
        resp = _error(request, 400, "로그인 요청이 만료됐어요. 다시 시도해 주세요.")
    elif error:
        resp = (RedirectResponse(f"/c/{token}?kakao=cancel", status_code=303) if token
                else _error(request, 400, "카카오 연결을 취소했어요."))
    elif not code:
        resp = _error(request, 400, "로그인 요청이 올바르지 않아요. 다시 시도해 주세요.")
    else:
        try:
            tokens = kakao.exchange_code(code)
            kakao_id = kakao.user_id(tokens.access_token)
        except kakao.KakaoError as e:
            print(f"kakao callback failed: {e}")
            resp = _error(request, 502, "카카오 연결 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요.")
        else:
            resp = _link_trial(request, db, token, kakao_id, tokens) if token else _find_trial(request, db, kakao_id, tokens)
    resp.delete_cookie(COOKIE)
    return resp


def _link_trial(request: Request, db: Session, token: str, kakao_id: int, tokens: kakao.Tokens):
    trial = get_trial(db, token)
    if trial is None:
        return _error(request, 404, "체험을 찾을 수 없어요.")
    owner = accounts.owner_of(db, token)
    if owner and owner.kakao_id != kakao_id:
        return RedirectResponse(f"/c/{token}?kakao=taken", status_code=303)
    can_message = "talk_message" in tokens.scope
    acc = accounts.save_account(db, kakao_id, tokens.refresh_token, can_message)
    accounts.link(db, token, kakao_id)
    if not can_message:
        return RedirectResponse(f"/c/{token}?kakao=nomsg", status_code=303)
    today = today_kst()
    if 1 <= accounts.day_number(trial, today) <= DAYS and accounts.claim(db, kakao_id, today, "welcome"):
        try:
            kakao.send_memo(tokens.access_token, welcome(acc.morning_at, acc.evening_at), f"{PUBLIC_BASE_URL}/c/{token}", "기록 화면 열기")
        except kakao.KakaoError as e:
            print(f"kakao welcome failed: {e}")
    return RedirectResponse(f"/c/{token}?kakao=linked", status_code=303)


@router.post("/c/{token}/kakao/notify", dependencies=[Depends(_require_enabled)])
def kakao_notify(request: Request, token: str, on: str = Form(""), db: Session = Depends(get_db)):
    if not DAY_PER_IP.hit(client_ip(request), time.time()):
        return _too_many(request)
    acc = accounts.owner_of(db, token)
    if acc is None:
        return _error(request, 400, "카카오에 연결된 체험이 아니에요.")
    accounts.set_notify(db, acc.kakao_id, on == "1")
    return RedirectResponse(f"/c/{token}", status_code=303)


@router.post("/c/{token}/kakao/times", dependencies=[Depends(_require_enabled)])
def kakao_times(request: Request, token: str, morning: str = Form(""), evening: str = Form(""),
                db: Session = Depends(get_db)):
    if not DAY_PER_IP.hit(client_ip(request), time.time()):
        return _too_many(request)
    acc = accounts.owner_of(db, token)
    if acc is None:
        return _error(request, 400, "카카오에 연결된 체험이 아니에요.")
    try:
        accounts.set_times(db, acc.kakao_id, dtime.fromisoformat(morning), dtime.fromisoformat(evening))
    except ValueError:
        return _error(request, 400, "목록에 있는 시간을 골라 주세요.")
    return RedirectResponse(f"/c/{token}", status_code=303)


@router.post("/c/{token}/kakao/unlink", dependencies=[Depends(_require_enabled)])
def kakao_unlink(request: Request, token: str, db: Session = Depends(get_db)):
    if not DAY_PER_IP.hit(client_ip(request), time.time()):
        return _too_many(request)
    acc = accounts.owner_of(db, token)
    if acc is None:
        return RedirectResponse(f"/c/{token}", status_code=303)
    if acc.refresh_token_enc:
        try:  # 카카오 쪽 동의 철회. 실패해도 우리 쪽 정보는 지운다
            kakao.unlink(kakao.refresh(kakao.decrypt(acc.refresh_token_enc)).access_token)
        except kakao.KakaoError as e:
            print(f"kakao unlink failed: {e}")
    accounts.delete_account(db, acc.kakao_id)
    return RedirectResponse(f"/c/{token}?kakao=unlinked", status_code=303)


def _find_trial(request: Request, db: Session, kakao_id: int, tokens: kakao.Tokens):
    if not accounts.has_trials(db, kakao_id):
        return _error(request, 404, "카카오에 연결된 체험이 없어요. 새로 시작해 주세요.")
    accounts.save_account(db, kakao_id, tokens.refresh_token, "talk_message" in tokens.scope)
    return RedirectResponse(f"/c/{accounts.latest_trial(db, kakao_id).token}", status_code=303)
