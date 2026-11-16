"""카카오 연동: 설정, 토큰 암호화, 쿠키 서명, 카카오 API 호출을 한곳에 모은다.

환경변수는 호출할 때마다 읽는다(키가 없으면 카카오 기능 전체가 꺼짐).
"""
import hashlib
import hmac
import os

from cryptography.fernet import Fernet

ENV_VARS = ("KAKAO_REST_API_KEY", "KAKAO_CLIENT_SECRET", "TOKEN_KEY")


def enabled() -> bool:
    return all(os.environ.get(name) for name in ENV_VARS)


def _fernet() -> Fernet:
    return Fernet(os.environ["TOKEN_KEY"])


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def _mac(value: str) -> str:
    return hmac.new(os.environ["TOKEN_KEY"].encode(), value.encode(), hashlib.sha256).hexdigest()


def sign(value: str) -> str:
    return f"{value}.{_mac(value)}"


def unsign(signed: str) -> str | None:
    value, sep, mac = signed.rpartition(".")
    if not sep or not hmac.compare_digest(mac, _mac(value)):
        return None
    return value
