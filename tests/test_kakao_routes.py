from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import accounts
from app.models import KakaoAccount
from tests.test_kakao import fake_kakao, form_of, kakao_env  # noqa: F401  (fixture)
from tests.test_routes import _set_day, _start_and_setup, client  # noqa: F401  (fixture)


def kakao_api(monkeypatch, kakao_id=42, scope="talk_message", token_status=200):
    """가짜 카카오: 토큰·회원정보·나에게 보내기. 받은 요청 목록을 돌려준다."""
    def handler(r):
        if r.url.path == "/oauth/token":
            if token_status != 200:
                return httpx.Response(token_status, text="down")
            return httpx.Response(200, json={"access_token": "a", "refresh_token": "r", "scope": scope})
        if r.url.path == "/v2/user/me":
            return httpx.Response(200, json={"id": kakao_id})
        return httpx.Response(200, json={"result_code": 0})
    return fake_kakao(monkeypatch, handler)


def memos(seen):
    return [form_of(r)["template_object"] for r in seen if r.url.path.endswith("/memo/default/send")]


def login(client, start_path):
    """로그인 시작 → 카카오가 돌려보낸 것처럼 콜백 호출."""
    r = client.get(start_path)
    assert r.status_code == 303
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    return client.get(f"/auth/kakao/callback?code=c1&state={state}")


def db_of(client):
    return Session(client.engine)


def count_accounts(client):
    with db_of(client) as db:
        return db.scalar(select(func.count()).select_from(KakaoAccount))


def test_kakao_routes_404_without_keys(client):
    loc = _start_and_setup(client)
    for path in (f"{loc}/kakao", "/auth/kakao", "/auth/kakao/callback?code=c&state=s"):
        assert client.get(path).status_code == 404
    assert "카카오로 연결" not in client.get(loc).text
    assert "카카오로 연결" not in client.get(f"{loc}/ready").text
    assert "카카오로 이어서 하기" not in client.get("/").text


def test_start_redirects_to_kakao_without_trial_token(client, kakao_env):
    loc = _start_and_setup(client)
    token = loc.removeprefix("/c/")
    r = client.get(f"{loc}/kakao")
    assert r.status_code == 303
    assert r.headers["location"].startswith("https://kauth.kakao.com/oauth/authorize?")
    assert token not in r.headers["location"]
    assert "wm_kakao" in r.cookies


def test_callback_links_trial_and_sends_welcome(client, kakao_env, monkeypatch):
    seen = kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    r = login(client, f"{loc}/kakao")
    assert r.status_code == 303 and r.headers["location"] == f"{loc}?kakao=linked"
    with db_of(client) as db:
        assert accounts.owner_of(db, loc.removeprefix("/c/")).kakao_id == 42
    assert len(memos(seen)) == 1 and "연결됐어요" in memos(seen)[0]
    assert "카톡이 연결됐어요" in client.get(r.headers["location"]).text
    login(client, f"{loc}/kakao")
    assert len(memos(seen)) == 1  # 환영 메시지는 하루 한 번


@pytest.mark.parametrize("case", ["no_cookie", "forged", "state_mismatch"])
def test_callback_bad_state(client, kakao_env, monkeypatch, case):
    seen = kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    r = client.get(f"{loc}/kakao")
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    if case == "no_cookie":
        client.cookies.clear()
    elif case == "forged":
        client.cookies.set("wm_kakao", f"{state}.{loc.removeprefix('/c/')}.deadbeef")
    elif case == "state_mismatch":
        state = "other"
    r = client.get(f"/auth/kakao/callback?code=c1&state={state}")
    assert r.status_code == 400
    assert count_accounts(client) == 0 and seen == []


def test_callback_without_code_or_error_400(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    r = client.get(f"{loc}/kakao")
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    assert client.get(f"/auth/kakao/callback?state={state}").status_code == 400


def test_callback_cancel_returns_to_trial(client, kakao_env, monkeypatch):
    seen = kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    r = client.get(f"{loc}/kakao")
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    r = client.get(f"/auth/kakao/callback?error=access_denied&state={state}")
    assert r.status_code == 303 and r.headers["location"] == f"{loc}?kakao=cancel"
    assert seen == []
    assert "카카오 연결을 취소했어요" in client.get(r.headers["location"]).text


def test_callback_without_talk_message_scope(client, kakao_env, monkeypatch):
    seen = kakao_api(monkeypatch, scope="")
    loc = _start_and_setup(client)
    r = login(client, f"{loc}/kakao")
    assert r.headers["location"] == f"{loc}?kakao=nomsg"
    with db_of(client) as db:
        assert db.get(KakaoAccount, 42).can_message is False
    assert memos(seen) == []
    assert "다시 연결" in client.get(loc).text


def test_callback_trial_owned_by_other_account(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch, kakao_id=42)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    kakao_api(monkeypatch, kakao_id=43)
    r = login(client, f"{loc}/kakao")
    assert r.headers["location"] == f"{loc}?kakao=taken"
    with db_of(client) as db:
        assert db.get(KakaoAccount, 43) is None


def test_callback_kakao_down(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch, token_status=500)
    loc = _start_and_setup(client)
    assert login(client, f"{loc}/kakao").status_code == 502


def test_login_without_trial_finds_latest(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch, kakao_id=42)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    r = login(client, "/auth/kakao")
    assert r.status_code == 303 and r.headers["location"] == loc
    kakao_api(monkeypatch, kakao_id=99)
    assert login(client, "/auth/kakao").status_code == 404
    with db_of(client) as db:
        assert db.get(KakaoAccount, 99) is None


def test_ready_shows_card_and_no_refresh_when_not_linked(client, kakao_env):
    loc = _start_and_setup(client)
    page = client.get(f"{loc}/ready").text
    assert "카카오로 연결" in page and 'http-equiv="refresh"' not in page
    # 카카오 버튼 바로 밑에 카카오 없이 시작하는 선택지
    assert page.index("카카오로 연결</a>") < page.index(f'<a class="btn btn-skip" href="{loc}">바로 시작</a>')
    assert "카카오로 이어서 하기" in client.get("/").text


def test_ready_keeps_refresh_without_keys(client):
    loc = _start_and_setup(client)
    assert 'http-equiv="refresh"' in client.get(f"{loc}/ready").text


def test_check_shows_linked_line(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    assert "카카오로 연결" in client.get(loc).text
    login(client, f"{loc}/kakao")
    page = client.get(loc).text
    assert "카카오톡 연결됨" in page and "카카오로 연결" not in page


def test_notify_toggle(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    assert client.post(f"{loc}/kakao/notify", data={"on": "0"}).status_code == 303
    with db_of(client) as db:
        assert db.get(KakaoAccount, 42).notify is False
    assert "카톡 메시지 꺼짐" in client.get(loc).text
    client.post(f"{loc}/kakao/notify", data={"on": "1"})
    with db_of(client) as db:
        assert db.get(KakaoAccount, 42).notify is True


def test_notify_without_link_400(client, kakao_env):
    loc = _start_and_setup(client)
    assert client.post(f"{loc}/kakao/notify", data={"on": "0"}).status_code == 400


def test_unlink_deletes_even_if_kakao_fails(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    fake_kakao(monkeypatch, lambda r: httpx.Response(500, text="down"))
    r = client.post(f"{loc}/kakao/unlink")
    assert r.status_code == 303 and r.headers["location"] == f"{loc}?kakao=unlinked"
    assert count_accounts(client) == 0
    with db_of(client) as db:
        assert accounts.owner_of(db, loc.removeprefix("/c/")) is None
    page = client.get(r.headers["location"])
    assert page.status_code == 200 and "연결을 끊었어요" in page.text


def test_unlink_with_undecryptable_token_still_deletes(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    with db_of(client) as db:
        db.get(KakaoAccount, 42).refresh_token_enc = "made-with-an-old-TOKEN_KEY"
        db.commit()
    r = client.post(f"{loc}/kakao/unlink")
    assert r.status_code == 303 and count_accounts(client) == 0


def test_unlink_calls_kakao_unlink(client, kakao_env, monkeypatch):
    seen = kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    client.post(f"{loc}/kakao/unlink")
    assert any(r.url.path == "/v1/user/unlink" for r in seen)


def test_dead_token_shows_reconnect(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    with db_of(client) as db:
        accounts.mark_dead(db, 42)
    page = client.get(loc).text
    assert "카톡 연결이 끊겼어요" in page and "다시 연결" in page


def test_sunday_weight_label(client):
    from tests.test_routes import _set_day
    from app.clock import today_kst
    loc = _start_and_setup(client)
    _set_day(client, loc, 10)
    start = today_kst() - timedelta(days=9)
    sunday = next(n for n in range(1, 11) if (start + timedelta(days=n - 1)).weekday() == 6)
    weekday = next(n for n in range(1, 11) if (start + timedelta(days=n - 1)).weekday() == 2)
    assert "체중 재는 날" in client.get(f"{loc}?day={sunday}").text
    assert "체중 재는 날" not in client.get(f"{loc}?day={weekday}").text


def test_auth_rate_limited(client, kakao_env):
    loc = _start_and_setup(client)
    codes = [client.get(f"{loc}/kakao").status_code for _ in range(11)]
    assert codes[:10] == [303] * 10 and codes[10] == 429


SELF_CHECK = "'나와의 채팅'을 직접 열어"


def test_self_check_notice_on_card_welcome_and_linked_line(client, kakao_env, monkeypatch):
    seen = kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    assert SELF_CHECK in client.get(f"{loc}/ready").text
    login(client, f"{loc}/kakao")
    assert SELF_CHECK in memos(seen)[0]
    assert SELF_CHECK in client.get(loc).text


def test_kakao_bar_sits_above_everything(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    assert client.get(loc).text.index("카카오로 연결") < client.get(loc).text.index('<h1 class="day">')
    login(client, f"{loc}/kakao")
    _set_day(client, loc, 2)
    page = client.get(f"{loc}?day=1").text
    assert 'class="kbar on"' in page
    assert page.index("카카오톡 연결됨") < page.index('<header class="hero">') < page.index("지난 기록을 고치는 중")


def test_landing_kakao_scene_matches_real_messages(client, kakao_env):
    from app import messages
    page = client.get("/").text
    assert page.count('<section class="scene') == 5 and "나와의 채팅" in page
    assert messages.BUTTON["morning"] in page and messages.BUTTON["evening"] in page
    assert messages.evening(1, False, False) in page
    assert page.index("내 위험도 확인하기") < page.index('href="/auth/kakao"')  # CTA 밑 작은 링크


def test_landing_kakao_morning_is_the_real_day12_message(client, kakao_env):
    from app import messages, routes
    from app.clock import today_kst
    from app.plan import Profile, build_plan, choose_variant
    from app.risk import assess
    from tests.test_risk import STATS
    day = build_plan(Profile(choose_variant(assess(*routes.EXAMPLE, stats=STATS)), "mixed", "out", "light", 25, (5, 6)),
                     today_kst(), "landing-demo")[11]
    assert messages.morning(day, day.date.weekday() == 6) in client.get("/").text


def test_times_saved_and_shown(client, kakao_env, monkeypatch):
    kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    page = client.get(loc).text
    assert "아침 7:30 / 저녁 9시" in page
    assert 'name="morning"' in page and 'name="evening"' in page and 'value="07:30" selected' in page
    r = client.post(f"{loc}/kakao/times", data={"morning": "06:00", "evening": "22:30"})
    assert r.status_code == 303 and r.headers["location"] == loc
    with db_of(client) as db:
        acc = db.get(KakaoAccount, 42)
        assert (acc.morning_at.strftime("%H:%M"), acc.evening_at.strftime("%H:%M")) == ("06:00", "22:30")
    page = client.get(loc).text
    assert "아침 6시 / 저녁 10:30" in page and 'value="06:00" selected' in page


@pytest.mark.parametrize("m, e", [("06:15", "21:00"), ("abc", "21:00"), ("07:30", "")])
def test_times_outside_list_400(client, kakao_env, monkeypatch, m, e):
    kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    assert client.post(f"{loc}/kakao/times", data={"morning": m, "evening": e}).status_code == 400


def test_times_without_link_400(client, kakao_env):
    loc = _start_and_setup(client)
    assert client.post(f"{loc}/kakao/times", data={"morning": "06:00", "evening": "21:00"}).status_code == 400


def test_welcome_uses_account_times(client, kakao_env, monkeypatch):
    seen = kakao_api(monkeypatch)
    loc = _start_and_setup(client)
    login(client, f"{loc}/kakao")
    assert "아침 7:30엔" in memos(seen)[0] and "저녁 9시엔" in memos(seen)[0]


def test_landing_kakao_messages_have_typing_dots(client, kakao_env):
    page = client.get("/").text
    assert page.count('class="typing"') == 2
