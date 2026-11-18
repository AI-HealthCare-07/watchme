import json

import httpx
import pytest

from app import ai

CANDS = {"b1": "현미밥 반 공기, 달걀찜", "d1": "매운 닭볶음탕", "e1": "평지 걷기 N분"}


@pytest.fixture
def gemini_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


def fake_gemini(monkeypatch, handler):
    """handler(request) -> httpx.Response. 받은 요청 목록을 돌려준다."""
    seen = []

    def wrapped(request):
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(ai, "http", httpx.Client(transport=httpx.MockTransport(wrapped)))
    return seen


def reply(text):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def test_enabled_needs_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert not ai.enabled()
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert ai.enabled()


def test_choose_parses_and_sends_only_request_and_candidates(gemini_env, monkeypatch):
    seen = fake_gemini(monkeypatch, lambda r: reply('{"exclude": ["d1"], "reason": "매운 메뉴를 뺐어요"}'))
    pick = ai.choose("매운 거 못 먹어요", CANDS)
    assert pick == ai.Pick(frozenset({"d1"}), "매운 메뉴를 뺐어요")
    req = seen[0]
    assert req.headers["x-goog-api-key"] == "test-key"
    assert req.url.path.endswith(":generateContent")
    body = json.loads(req.content)
    assert list(body) == ["contents"]
    text = body["contents"][0]["parts"][0]["text"]
    assert "매운 거 못 먹어요" in text and "d1" in text and "매운 닭볶음탕" in text


def test_model_from_env(gemini_env, monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "my-model")
    seen = fake_gemini(monkeypatch, lambda r: reply('{"exclude": [], "reason": ""}'))
    ai.choose("x", CANDS)
    assert "/models/my-model:generateContent" in seen[0].url.path


def test_choose_strips_code_fence(gemini_env, monkeypatch):
    fake_gemini(monkeypatch, lambda r: reply('```json\n{"exclude": [], "reason": ""}\n```'))
    assert ai.choose("x", CANDS) == ai.Pick(frozenset(), "")


def test_unknown_id_is_invalid(gemini_env, monkeypatch):
    fake_gemini(monkeypatch, lambda r: reply('{"exclude": ["x9"], "reason": "r"}'))
    with pytest.raises(ai.AiError) as e:
        ai.choose("x", CANDS)
    assert e.value.kind == "invalid"


@pytest.mark.parametrize("text", ["네 알겠어요", '["d1"]', '{"exclude": "d1", "reason": ""}',
                                  '{"exclude": [1], "reason": ""}', '{"exclude": [], "reason": 3}'])
def test_bad_json_is_invalid(gemini_env, monkeypatch, text):
    fake_gemini(monkeypatch, lambda r: reply(text))
    with pytest.raises(ai.AiError) as e:
        ai.choose("x", CANDS)
    assert e.value.kind == "invalid"


def test_missing_candidates_is_invalid(gemini_env, monkeypatch):
    fake_gemini(monkeypatch, lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(ai.AiError) as e:
        ai.choose("x", CANDS)
    assert e.value.kind == "invalid"


def test_http_error(gemini_env, monkeypatch):
    fake_gemini(monkeypatch, lambda r: httpx.Response(429, json={"error": {"code": 429}}))
    with pytest.raises(ai.AiError) as e:
        ai.choose("x", CANDS)
    assert e.value.kind == "http"


def test_timeout(gemini_env, monkeypatch):
    def boom(request):
        raise httpx.ReadTimeout("slow", request=request)

    fake_gemini(monkeypatch, boom)
    with pytest.raises(ai.AiError) as e:
        ai.choose("x", CANDS)
    assert e.value.kind == "timeout"


def test_reason_is_trimmed(gemini_env, monkeypatch):
    reason = "  a\n b  " + "가" * 100
    fake_gemini(monkeypatch, lambda r: reply(json.dumps({"exclude": [], "reason": reason})))
    got = ai.choose("x", CANDS).reason
    assert got.startswith("a b 가") and len(got) == 80
