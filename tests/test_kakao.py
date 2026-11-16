import json
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.fernet import Fernet

from app import kakao


@pytest.fixture
def kakao_env(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "rest-key")
    monkeypatch.setenv("KAKAO_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TOKEN_KEY", Fernet.generate_key().decode())


def test_enabled_needs_all_three_vars(kakao_env, monkeypatch):
    assert kakao.enabled()
    monkeypatch.delenv("KAKAO_CLIENT_SECRET")
    assert not kakao.enabled()
    monkeypatch.delenv("KAKAO_REST_API_KEY")
    monkeypatch.delenv("TOKEN_KEY")
    assert not kakao.enabled()


def test_encrypt_roundtrip_and_not_plain(kakao_env):
    enc = kakao.encrypt("rt-123")
    assert "rt-123" not in enc
    assert kakao.decrypt(enc) == "rt-123"


def test_sign_roundtrip_and_tamper(kakao_env):
    signed = kakao.sign("abc.tok")
    assert kakao.unsign(signed) == "abc.tok"
    tampered = signed[:-1] + ("0" if signed[-1] != "0" else "1")
    for bad in (tampered, "garbage", ""):
        assert kakao.unsign(bad) is None


# --- 카카오 HTTP 클라이언트 (실제 카카오 대신 MockTransport) ---

def fake_kakao(monkeypatch, handler):
    """handler(request) -> httpx.Response. 받은 요청 목록을 돌려준다."""
    seen = []

    def wrapped(request):
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(kakao, "http", httpx.Client(transport=httpx.MockTransport(wrapped)))
    return seen


def form_of(request) -> dict:
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


def test_authorize_url_has_only_talk_message_scope(kakao_env, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://evrd.example/")
    q = parse_qs(urlsplit(kakao.authorize_url("s1")).query)
    assert q["scope"] == ["talk_message"]
    assert q["state"] == ["s1"]
    assert q["redirect_uri"] == ["https://evrd.example/auth/kakao/callback"]
    assert q["client_id"] == ["rest-key"] and q["response_type"] == ["code"]


def test_exchange_code_sends_secret_and_parses_scope(kakao_env, monkeypatch):
    seen = fake_kakao(monkeypatch, lambda r: httpx.Response(
        200, json={"access_token": "a", "refresh_token": "r", "scope": "talk_message"}))
    assert kakao.exchange_code("c1") == kakao.Tokens("a", "r", frozenset({"talk_message"}))
    body = form_of(seen[0])
    assert body["client_secret"] == "secret" and body["code"] == "c1"
    assert body["grant_type"] == "authorization_code"


def test_refresh_without_new_refresh_token(kakao_env, monkeypatch):
    seen = fake_kakao(monkeypatch, lambda r: httpx.Response(200, json={"access_token": "a2"}))
    t = kakao.refresh("r1")
    assert t.access_token == "a2" and t.refresh_token is None and t.scope == frozenset()
    assert form_of(seen[0])["grant_type"] == "refresh_token"


def test_user_id(kakao_env, monkeypatch):
    seen = fake_kakao(monkeypatch, lambda r: httpx.Response(200, json={"id": 42}))
    assert kakao.user_id("a") == 42
    assert seen[0].headers["authorization"] == "Bearer a"


def test_send_memo_template(kakao_env, monkeypatch):
    seen = fake_kakao(monkeypatch, lambda r: httpx.Response(200, json={"result_code": 0}))
    kakao.send_memo("a", "오늘 잘 지키셨나요?", "https://evrd.example/c/t", "기록하기")
    req = seen[0]
    assert req.headers["authorization"] == "Bearer a"
    tpl = json.loads(form_of(req)["template_object"])
    assert tpl["object_type"] == "text" and tpl["text"] == "오늘 잘 지키셨나요?"
    assert tpl["link"]["mobile_web_url"] == "https://evrd.example/c/t"
    assert tpl["button_title"] == "기록하기"


@pytest.mark.parametrize("status, body", [(401, {}), (400, {"code": -402}), (400, {"error": "invalid_grant"})])
def test_auth_errors(kakao_env, monkeypatch, status, body):
    fake_kakao(monkeypatch, lambda r: httpx.Response(status, json=body))
    with pytest.raises(kakao.KakaoAuthError):
        kakao.refresh("r1")


def test_other_errors(kakao_env, monkeypatch):
    fake_kakao(monkeypatch, lambda r: httpx.Response(500, text="oops"))
    with pytest.raises(kakao.KakaoError) as e:
        kakao.send_memo("a", "t", "https://x", "b")
    assert not isinstance(e.value, kakao.KakaoAuthError)

    def down(request):
        raise httpx.ConnectError("down")

    fake_kakao(monkeypatch, down)
    with pytest.raises(kakao.KakaoError):
        kakao.unlink("a")
