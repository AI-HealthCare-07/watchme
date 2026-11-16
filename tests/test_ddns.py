import pytest

from ddns.update import public_ipv4, run


def test_same_ip_does_not_update():
    calls = []
    assert run("1.0.0.1", lambda: "1.0.0.1", calls.append) is False
    assert calls == []


def test_changed_ip_updates_once():
    calls = []
    assert run("1.0.0.2", lambda: "1.0.0.1", calls.append) is True
    assert calls == ["1.0.0.2"]


@pytest.mark.parametrize("raw", ["<html>error</html>", "192.168.0.48", "100.64.0.1", "", "::1"])
def test_bad_ip_response_never_reaches_dns(raw):
    with pytest.raises(ValueError):
        public_ipv4(raw)


def test_ip_response_is_trimmed():
    assert public_ipv4("1.0.0.1\n") == "1.0.0.1"
