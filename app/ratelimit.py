from collections import deque

from fastapi import Request


class RateLimiter:
    """키(IP 등)별 슬라이딩 윈도 요청 제한.

    ponytail: 단일 uvicorn 프로세스 메모리에 둠. 워커를 늘리거나 재시작 후에도 유지해야 하면 Redis 등 공유 저장소로.
    """

    def __init__(self, limit: int, window_s: int):
        self.limit, self.window_s = limit, window_s
        self.hits: dict[str, deque[float]] = {}

    def hit(self, key: str, now: float) -> bool:
        q = self.hits.setdefault(key, deque())
        while q and q[0] <= now - self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


def client_ip(request: Request) -> str:
    # Tailscale Funnel은 X-Forwarded-For를 실제 방문자 IP로 덮어써서 넣는다(위조 불가, runbook 7장).
    # 컨테이너 포트는 127.0.0.1에만 열려 있어 Funnel 외의 경로로는 이 헤더를 넣을 수 없다.
    xff = request.headers.get("x-forwarded-for")
    return xff.split(",")[0].strip() if xff else request.client.host
