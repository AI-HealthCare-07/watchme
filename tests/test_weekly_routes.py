import re

from app.main import app
from app.risk import get_stats
from tests.test_routes import _set_day, _start_and_setup, _start_only, client  # noqa: F401  (fixture)
from tests.test_weekly import WALK


def _log(client, loc, days, weight=""):  # noqa: F811
    for n in days:
        assert client.post(f"{loc}/day/{n}", data={"kept": "1", "weight_kg": weight}).status_code == 303


def test_week_report_locked_until_day7_logged(client):  # noqa: F811
    loc = _start_and_setup(client)
    _set_day(client, loc, 7)
    r = client.get(f"{loc}/week/1")
    assert r.status_code == 400 and "1주차 리포트는 7일째 기록 후에 열려요." in r.text
    _log(client, loc, [7])
    assert client.get(f"{loc}/week/1").status_code == 200


def test_week_report_opens_after_trial_ends(client):  # noqa: F811
    loc = _start_and_setup(client)
    _set_day(client, loc, 40)
    assert client.get(f"{loc}/week/4").status_code == 200
    for w in (0, 5):
        r = client.get(f"{loc}/week/{w}")
        assert r.status_code == 404 and "없는 주차예요." in r.text
    assert client.get("/c/nope/week/1").status_code == 404


def test_week_report_before_setup_redirects(client):  # noqa: F811
    loc = _start_only(client)
    r = client.get(f"{loc}/week/1")
    assert r.status_code == 303 and r.headers["location"].endswith("/setup")


def test_week_report_without_walk_stats_hides_peer(client):  # noqa: F811
    loc = _start_and_setup(client)
    _set_day(client, loc, 8)
    _log(client, loc, range(1, 8))
    r = client.get(f"{loc}/week/1")
    assert r.status_code == 200 and "7일 중 7일 지켰어요" in r.text
    assert "🏅" not in r.text and "자랑하기" not in r.text and "국민건강영양조사" not in r.text


def test_week_report_with_walk_shows_peer_and_share(client):  # noqa: F811
    app.dependency_overrides[get_stats] = lambda: WALK
    loc = _start_and_setup(client)
    _set_day(client, loc, 8)
    _log(client, loc, range(1, 8))
    r = client.get(f"{loc}/week/1")
    assert "10명 중 3명" in r.text and "국민건강영양조사 2022–2024 · 걷기 기준" in r.text
    assert f"{loc}/week/1/card.png" in r.text
    text = re.search(r'data-text="([^"]*)"', r.text).group(1)
    assert text and loc.rsplit("/", 1)[1] not in text


def test_check_summary_links_week_report(client):  # noqa: F811
    loc = _start_and_setup(client)
    _set_day(client, loc, 7)
    _log(client, loc, [7])
    assert f'{loc}/week/1"' in client.get(loc).text


def test_week_report_weight_chart(client):  # noqa: F811
    loc = _start_and_setup(client)
    _set_day(client, loc, 8)
    r = client.get(f"{loc}/week/1")
    assert "<svg" not in r.text and "체중을 적으면 그래프가 생겨요." in r.text
    _log(client, loc, [3], weight="79.4")
    assert "<svg" in client.get(f"{loc}/week/1").text


def test_final_report_has_weight_chart(client):  # noqa: F811
    loc = _start_and_setup(client)
    _set_day(client, loc, 31)
    _log(client, loc, [5], weight="79.0")
    assert "<svg" in client.get(f"{loc}/report").text
