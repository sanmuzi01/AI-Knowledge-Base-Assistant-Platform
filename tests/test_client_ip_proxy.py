"""客户端真实 IP：nginx 在前面时，限流用的 request.client.host 必须是用户的真实 IP，且不能被伪造。

直接用 uvicorn 的 ProxyHeadersMiddleware，配上 Dockerfile 里写死的 FORWARDED_ALLOW_IPS，
所以改 Dockerfile 里的这个值也会被这里的用例检查到。
"""
import asyncio
import os
import re
import unittest
from unittest.mock import patch

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dockerfile_allow_ips() -> str:
    with open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8") as f:
        match = re.search(r'FORWARDED_ALLOW_IPS="([^"]+)"', f.read())
    assert match, "Dockerfile 里没有 FORWARDED_ALLOW_IPS"
    return match.group(1)


def _client_seen_by_app(peer: str, forwarded_for: str | None, trusted: str) -> str:
    seen = {}

    async def app(scope, receive, send):
        seen["client"] = scope["client"][0]

    headers = [(b"x-forwarded-for", forwarded_for.encode())] if forwarded_for else []
    scope = {"type": "http", "client": (peer, 5000), "headers": headers}
    asyncio.run(ProxyHeadersMiddleware(app, trusted_hosts=trusted)(scope, None, None))
    return seen["client"]


class ClientIpBehindNginxTest(unittest.TestCase):
    def setUp(self):
        self.trusted = _dockerfile_allow_ips()

    def test_real_client_ip_is_used_when_nginx_connects_from_the_docker_network(self):
        # nginx 在宿主机上：容器里看到的连接来源是 Docker 网关 172.18.0.1
        self.assertEqual(_client_seen_by_app("172.18.0.1", "203.0.113.9", self.trusted), "203.0.113.9")

    def test_forged_left_hand_entries_are_ignored(self):
        # 用户自己带了 X-Forwarded-For: 6.6.6.6，nginx（$proxy_add_x_forwarded_for）在右边追加真实 IP
        self.assertEqual(_client_seen_by_app("172.18.0.1", "6.6.6.6, 203.0.113.9", self.trusted), "203.0.113.9")

    def test_chain_through_two_proxies_still_finds_the_client(self):
        # 宿主机 nginx → 前端容器 nginx → api：右边多一个内网地址，要跳过
        self.assertEqual(_client_seen_by_app("172.18.0.5", "203.0.113.9, 172.18.0.1", self.trusted), "203.0.113.9")

    def test_headers_from_an_untrusted_peer_are_ignored(self):
        # 如果 api 端口被直接暴露到公网，直连的人带的 X-Forwarded-For 一律不信
        self.assertEqual(_client_seen_by_app("198.51.100.7", "6.6.6.6", self.trusted), "198.51.100.7")

    def test_no_header_keeps_the_peer_address(self):
        self.assertEqual(_client_seen_by_app("127.0.0.1", None, self.trusted), "127.0.0.1")

    def test_ipv6_client(self):
        self.assertEqual(_client_seen_by_app("172.18.0.1", "2001:db8::1", self.trusted), "2001:db8::1")

    def test_star_would_be_spoofable(self):
        # 反例：为什么 Dockerfile 里不能写 *
        self.assertEqual(_client_seen_by_app("172.18.0.1", "6.6.6.6, 203.0.113.9", "*"), "6.6.6.6")


class ProductionStarWarningTest(unittest.TestCase):
    def _checks(self, value):
        from service import config_validation

        env = {"APP_ENV": "production", "FORWARDED_ALLOW_IPS": value}
        with patch.dict(os.environ, env):
            return [c for c in config_validation.validate_runtime_config()["checks"] if c["name"] == "FORWARDED_ALLOW_IPS"]

    def test_star_in_production_warns_without_blocking(self):
        checks = self._checks("*")
        self.assertEqual([c["level"] for c in checks], ["warn"])
        self.assertTrue(checks[0]["ok"])

    def test_private_ranges_do_not_warn(self):
        self.assertEqual(self._checks("127.0.0.1,172.16.0.0/12"), [])


if __name__ == "__main__":
    unittest.main()
