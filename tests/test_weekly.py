from datetime import date, timedelta

from sqlalchemy import select

from app.models import Trial
from app.service import plan_for, save_day, save_setup, start_trial
from app.weekly import Peer, app_rank, build_week, cheer, peer_of, ratio_text, walk_share, week_ready
from tests.test_risk import STATS
from tests.test_service import db  # noqa: F401  (fixture)

WALK = STATS | {"walk": {"groups": {"M": {"40": {"n": 1, "share": {
    str(m): [0.9, 0.8, 0.7, 0.6, 0.41, 0.29, 0.2] for m in (10, 20, 30, 40, 50, 60)}}}}}}
TODAY = date(2026, 11, 18)


def _trial(db, start=TODAY - timedelta(days=7), minutes=45):  # noqa: F811
    t = start_trial(db, "M", 45, 170, 80, today=start, stats=STATS)  # BMI 27.7 → high_risk
    save_setup(db, t.token, "mixed", "out", "light", minutes, [2, 5])
    return t


def _week1(db, t):  # noqa: F811
    return [d for d in plan_for(db, t) if d.day <= 7]


def test_ratio_text():
    assert ratio_text(0.291) == "10명 중 3명"
    assert ratio_text(0.07) == "100명 중 7명"
    assert ratio_text(0.004) == "100명 중 1명"


def test_walk_share_floors_minutes_and_handles_missing():
    assert walk_share(WALK, "M", 45, 6, 25) == 0.29
    assert walk_share(STATS, "M", 45, 6, 25) is None
    assert walk_share(WALK, "M", 45, 0, 25) is None
    assert walk_share(WALK, "F", 45, 6, 25) is None


def test_peer_counts_only_exercise_days(db):  # noqa: F811
    t = _trial(db)
    for n in range(1, 8):
        save_day(db, t.token, n, True, None)
    from app.service import get_logs
    peer = peer_of(t, _week1(db, t), get_logs(db, t.token), WALK)
    assert peer == Peer(days=6, minutes=30, share=0.29, label="40대 남성")
    assert peer.ratio == "10명 중 3명"


def test_peer_hidden_when_over_half(db):  # noqa: F811
    t = _trial(db)
    for n in (1, 2, 3, 4):
        save_day(db, t.token, n, True, None)
    from app.service import get_logs
    assert peer_of(t, _week1(db, t), get_logs(db, t.token), WALK) is None  # 4일 → 0.6


def test_week_ready(db):  # noqa: F811
    t = _trial(db)
    from app.service import get_logs
    assert week_ready(7, [], 1) is False
    save_day(db, t.token, 7, True, None)
    assert week_ready(7, get_logs(db, t.token), 1) is True
    assert week_ready(8, [], 1) is True
    assert week_ready(30, [], 4) is True
    assert week_ready(30, [], 5) is False
    assert week_ready(30, [], 0) is False


def _peers(db, n, kept, logged=True):  # noqa: F811
    for _ in range(n):
        p = _trial(db)
        if logged:
            for d in range(1, 8):
                save_day(db, p.token, d, d <= kept, None)


def test_app_rank_needs_30_peers_and_top_half(db):  # noqa: F811
    me = _trial(db)
    _peers(db, 29, 3)
    _peers(db, 5, 0, logged=False)  # 그 주 기록 없는 체험은 안 셈
    assert app_rank(db, me, 1, 6, TODAY) is None
    _peers(db, 1, 3)
    assert app_rank(db, me, 1, 6, TODAY) == 4  # ceil(100·1/31)
    assert app_rank(db, me, 1, 3, TODAY) is None  # 30명 모두 같은 3일 → ceil(100·31/31)=100: 동점은 내 위로 센다
    _peers(db, 30, 7)
    assert app_rank(db, me, 1, 3, TODAY) is None


def test_cheer_copy():
    assert cheer(1, 0, None) == "이번 주는 쉬어 갔어요. 오늘부터 다시 하루씩 채워 봐요."
    assert cheer(1, 6, None) == "첫 주부터 6일! 이 속도면 30일 완주 충분해요."
    assert cheer(2, 6, 4) == "지난주보다 2일 더 지켰어요. 점점 몸에 붙고 있어요."
    assert cheer(3, 3, 5) == "이번 주는 조금 쉬어 갔어요. 다음 주에 다시 올려 봐요."
    assert cheer(2, 4, 4) == "지난주만큼 꾸준히 지켰어요. 꾸준함이 제일 어려운 거예요."


def test_build_week_weights_start_at_day0(db):  # noqa: F811
    t = _trial(db, start=TODAY - timedelta(days=14))
    save_day(db, t.token, 3, True, 79.5)
    save_day(db, t.token, 10, False, 79.0)
    r = build_week(db, t, 1, TODAY, WALK)
    assert r.weights == [(0, 80.0), (3, 79.5)]
    assert r.marks == (None, None, True, None, None, None, None)
    assert r.kept == 1 and r.first == t.start_date and r.last == t.start_date + timedelta(days=6)
    assert r.peer is None and r.rank is None and r.summary.week == 1
    assert build_week(db, t, 2, TODAY, WALK).cheer == "이번 주는 쉬어 갔어요. 오늘부터 다시 하루씩 채워 봐요."
