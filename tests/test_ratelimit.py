from app.ratelimit import RateLimiter


def test_limit_and_window():
    rl = RateLimiter(5, 600)
    assert all(rl.hit("a", 0) for _ in range(5))
    assert not rl.hit("a", 1)
    assert rl.hit("b", 1)  # 다른 키는 독립
    assert rl.hit("a", 601)  # 창이 지나면 다시 허용
