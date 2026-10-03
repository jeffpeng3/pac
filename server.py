"""Serve proxy.pac rendered from proxy.pac.template with env config.

Env:
  PROXY_TYPE: PROXY or SOCKS5 (default PROXY)
  PROXY_ADDR: host:port (default 127.0.0.1:7890)
  PORT: listen port (default 8080)

Routes:
  GET/HEAD /proxy.pac, /wpad.dat -> rendered PAC
  GET/HEAD /healthz -> ok
"""
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "proxy.pac.template"
MIME = "application/x-ns-proxy-autoconfig"
ALLOWED_TYPES = {"PROXY", "SOCKS5"}


def render() -> bytes:
    proxy_type = os.environ.get("PROXY_TYPE", "PROXY").strip().upper() or "PROXY"
    if proxy_type not in ALLOWED_TYPES:
        proxy_type = "PROXY"
    proxy_addr = os.environ.get("PROXY_ADDR", "127.0.0.1:7890").strip() or "127.0.0.1:7890"
    text = TEMPLATE.read_text(encoding="utf-8")
    text = text.replace("__PROXY_TYPE__", proxy_type).replace("__PROXY_ADDR__", proxy_addr)
    return text.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "pac-server/1.0"

    def _send_pac(self) -> None:
        body = render()
        self.send_response(200)
        self.send_header("Content-Type", MIME)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command == "GET":
            self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] in ("/proxy.pac", "/wpad.dat"):
            self._send_pac()
        elif self.path.split("?", 1)[0] == "/healthz":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_HEAD(self) -> None:
        if self.path.split("?", 1)[0] in ("/proxy.pac", "/wpad.dat"):
            self._send_pac()
        elif self.path.split("?", 1)[0] == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "2")
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
