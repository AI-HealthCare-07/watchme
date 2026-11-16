"""카카오 연동: 설정, 토큰 암호화, 쿠키 서명, 카카오 API 호출을 한곳에 모은다.

환경변수는 호출할 때마다 읽는다(키가 없으면 카카오 기능 전체가 꺼짐).
"""
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

ENV_VARS = ("KAKAO_REST_API_KEY", "KAKAO_CLIENT_SECRET", "TOKEN_KEY")
AUTH = "https://kauth.kakao.com"
API = "https://kapi.kakao.com"
# 다시 로그인해야 하는 응답 코드: -401 토큰 무효, -402 동의 없음, -101 앱과 연결 안 된 사용자
AUTH_CODES = {-401, -402, -101}

http = httpx.Client(timeout=10)  # 테스트에서 MockTransport 클라이언트로 바꿔 끼운다


class KakaoError(Exception):
    pass


class KakaoAuthError(KakaoError):
    """토큰 무효·동의 철회·연결 끊김: 사용자가 다시 연결해야 한다."""


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str | None
    scope: frozenset[str]


def enabled() -> bool:
    return all(os.environ.get(name) for name in ENV_VARS)


def _fernet() -> Fernet:
    return Fernet(os.environ["TOKEN_KEY"])


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:  # TOKEN_KEY가 바뀌었거나 잃어버림 → 다시 연결해야 함
        raise KakaoAuthError("저장된 토큰을 풀 수 없음 (TOKEN_KEY 변경?)") from None


def _mac(value: str) -> str:
    return hmac.new(os.environ["TOKEN_KEY"].encode(), value.encode(), hashlib.sha256).hexdigest()


def sign(value: str) -> str:
    return f"{value}.{_mac(value)}"


def unsign(signed: str) -> str | None:
    value, sep, mac = signed.rpartition(".")
    if not sep or not hmac.compare_digest(mac, _mac(value)):
        return None
    return value


def redirect_uri() -> str:
    base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}/auth/kakao/callback"


def authorize_url(state: str) -> str:
    query = urlencode({
        "client_id": os.environ["KAKAO_REST_API_KEY"], "redirect_uri": redirect_uri(),
        "response_type": "code", "state": state, "scope": "talk_message",
    })
    return f"{AUTH}/oauth/authorize?{query}"


def _call(method: str, url: str, access_token: str | None = None, data: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    try:
        resp = http.request(method, url, headers=headers, data=data)
    except httpx.HTTPError as e:
        raise KakaoError(f"{url}: {e}") from e
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if resp.is_success:
        return body
    if resp.status_code == 401 or body.get("code") in AUTH_CODES or body.get("error") == "invalid_grant":
        raise KakaoAuthError(f"{url}: {resp.status_code} {body}")
    raise KakaoError(f"{url}: {resp.status_code} {body}")


def _tokens(data: dict) -> Tokens:
    body = _call("POST", f"{AUTH}/oauth/token", data={
        **data, "client_id": os.environ["KAKAO_REST_API_KEY"], "client_secret": os.environ["KAKAO_CLIENT_SECRET"],
    })
    return Tokens(body["access_token"], body.get("refresh_token"), frozenset(body.get("scope", "").split()))


def exchange_code(code: str) -> Tokens:
    return _tokens({"grant_type": "authorization_code", "redirect_uri": redirect_uri(), "code": code})


def refresh(refresh_token: str) -> Tokens:
    """리프레시 토큰은 남은 기간이 1개월 미만일 때만 새로 온다(없으면 refresh_token=None)."""
    return _tokens({"grant_type": "refresh_token", "refresh_token": refresh_token})


def user_id(access_token: str) -> int:
    return int(_call("GET", f"{API}/v2/user/me", access_token)["id"])


def send_memo(access_token: str, text: str, url: str, button: str) -> None:
    template = {"object_type": "text", "text": text,
                "link": {"web_url": url, "mobile_web_url": url}, "button_title": button}
    _call("POST", f"{API}/v2/api/talk/memo/default/send", access_token,
          data={"template_object": json.dumps(template, ensure_ascii=False)})


def unlink(access_token: str) -> None:
    _call("POST", f"{API}/v1/user/unlink", access_token)
