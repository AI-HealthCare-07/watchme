"""evrd.fyi의 A 레코드를 집 공인 IP로 맞춘다 (Porkbun DNS API). 서버 cron이 5분마다 실행.

  cd ~/watchme && set -a && . ./.env && python3 -m ddns.update
.env: PORKBUN_API_KEY, PORKBUN_SECRET_KEY. 표준 라이브러리만 쓰므로 호스트 python3로 바로 실행.
A 레코드는 Porkbun 화면에서 한 번 만들어 두어야 함 (이 스크립트는 수정만 함).
"""
import ipaddress
import json
import os
import urllib.request
from collections.abc import Callable
from datetime import datetime

DOMAIN = "evrd.fyi"
API = "https://api.porkbun.com/api/json/v3/dns"
IP_URL = "https://api.ipify.org"


def run(current_ip: str, get_record: Callable[[], str], set_record: Callable[[str], None]) -> bool:
    if get_record() == current_ip:
        return False
    set_record(current_ip)
    return True


def public_ipv4(raw: str) -> str:
    """IP 조회 응답 검증: 이상한 값(오류 페이지, 사설 IP)이 DNS에 들어가지 않게."""
    ip = ipaddress.IPv4Address(raw.strip())  # 형식이 아니면 ValueError
    if not ip.is_global:
        raise ValueError(f"공인 IP가 아님: {ip}")
    return str(ip)


def _porkbun(path: str, **body) -> dict:
    req = urllib.request.Request(
        f"{API}/{path}",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": os.environ["PORKBUN_API_KEY"],
            "X-Secret-API-Key": os.environ["PORKBUN_SECRET_KEY"],
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    if data.get("status") != "SUCCESS":
        raise RuntimeError(f"Porkbun {path}: {data}")
    return data


def _get_record() -> str:
    records = _porkbun(f"retrieveByNameType/{DOMAIN}/A/")["records"]
    if not records:
        raise RuntimeError(f"{DOMAIN} A 레코드가 없음: Porkbun에서 먼저 만들 것")
    return records[0]["content"]


if __name__ == "__main__":
    with urllib.request.urlopen(IP_URL, timeout=20) as r:
        ip = public_ipv4(r.read().decode())
    if run(ip, _get_record, lambda new: _porkbun(f"editByNameType/{DOMAIN}/A/", content=new, ttl=600)):
        print(f"{datetime.now():%Y-%m-%d %H:%M} {DOMAIN} A -> {ip}")
