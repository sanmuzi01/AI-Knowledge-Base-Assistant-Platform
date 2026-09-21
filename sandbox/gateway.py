"""沙箱网关：api / worker → 网关 → 沙箱。

为什么需要它：之前 api 和 worker 直接挂在沙箱的内部网络上才能调到沙箱，
这样沙箱里的脚本虽然出不了外网，却能访问到同一个网络里的 api 容器。
现在的拓扑：

    api / worker ──(默认网络)──▶ sandbox-gw ──(sandbox_net)──▶ sandbox
                                                                 └ 网络里只有网关和沙箱自己

网关同时在两个网络上，但只会把请求转发给**固定的上游**（沙箱），且只放行 GET /health 和 POST /run。
沙箱里的脚本能看到网关，可网关只通向沙箱自己，到不了 api / db / redis。
"""
import http.client
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

UPSTREAM = urlparse(os.environ.get("GATEWAY_UPSTREAM", "http://sandbox:8090"))
MAX_BODY = 100 * 1024 * 1024
UPSTREAM_TIMEOUT = int(os.environ.get("GATEWAY_UPSTREAM_TIMEOUT", "150"))
ALLOWED = {("GET", "/health"), ("POST", "/run")}
FORWARD_HEADERS = ("Content-Type", "X-Sandbox-Token")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 不把请求内容写进日志
        pass

    def _reply(self, status: int, body: bytes = b"", content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, method: str):
        if (method, self.path) not in ALLOWED:
            return self._reply(404 if method == "GET" or self.path != "/run" else 405, b'{"detail":"not allowed"}')
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._reply(413, b'{"detail":"body too large"}')
        body = self.rfile.read(length) if length else None
        headers = {h: self.headers[h] for h in FORWARD_HEADERS if self.headers.get(h)}
        try:
            conn = http.client.HTTPConnection(UPSTREAM.hostname, UPSTREAM.port or 80, timeout=UPSTREAM_TIMEOUT)
            conn.request(method, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            self._reply(resp.status, data, resp.getheader("Content-Type", "application/json"))
            conn.close()
        except (OSError, http.client.HTTPException):
            self._reply(502, b'{"detail":"sandbox unreachable"}')

    def do_GET(self):
        self._proxy("GET")

    def do_POST(self):
        self._proxy("POST")


def serve(port: int = 8090) -> None:
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    serve(int(os.environ.get("GATEWAY_PORT", "8090")))
