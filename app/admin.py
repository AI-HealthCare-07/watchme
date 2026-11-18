"""나만 여는 운영 지표 화면. ADMIN_KEY가 비면 기능 전체가 꺼진다(404)."""
import hashlib
import hmac
import os
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.clock import today_kst
from app.db import get_db
from app.metrics import collect, since_from_env
from app.ratelimit import client_ip
from app.routes import AUTH_PER_IP, PUBLIC_BASE_URL, _error, _page, _too_many

COOKIE = "wm_admin"
NO_INDEX = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}
router = APIRouter()


def admin_key() -> str:
    return os.environ.get("ADMIN_KEY", "").strip()


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def is_admin(request: Request) -> bool:
    key = admin_key()
    return bool(key) and hmac.compare_digest(request.cookies.get(COOKIE, ""), _digest(key))


def _headers(resp):
    resp.headers.update(NO_INDEX)
    return resp


def _not_found(request: Request):
    return _headers(_error(request, 404, "페이지를 찾을 수 없어요."))


@router.get("/admin")
def admin(request: Request, db: Session = Depends(get_db)):
    key = admin_key()
    if not key:
        return _not_found(request)
    given = request.query_params.get("key")
    if given is not None:
        if not AUTH_PER_IP.hit(client_ip(request), time.time()):
            return _headers(_too_many(request))
        if not hmac.compare_digest(given.encode(), key.encode()):
            return _not_found(request)
        # 키는 주소창·방문 기록에 남기지 않고, 쿠키에는 키의 해시만 둔다
        resp = RedirectResponse("/admin", status_code=303)
        resp.set_cookie(COOKIE, _digest(key), max_age=180 * 86400, httponly=True,
                        secure=PUBLIC_BASE_URL.startswith("https://"), samesite="lax")
        return _headers(resp)
    if not is_admin(request):
        return _not_found(request)
    return _headers(_page(request, "admin.html", m=collect(db, today_kst(), since_from_env())))
