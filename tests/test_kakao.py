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
