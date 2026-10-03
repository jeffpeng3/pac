"""Serve proxy.pac rendered from proxy.pac.template.

No proxy configuration needed: the container's own LAN IP (macvlan)
is detected at startup and advertised as the SOCKS5 endpoint.
GOST in the same container listens on 1080.

Env:
  PORT: listen port (default 8080)

Routes:
  GET/HEAD /proxy.pac, /wpad.dat -> rendered PAC
  GET/HEAD /healthz -> ok
"""
import fcntl
import ipaddress
import os
import socket
import struct
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "proxy.pac.template"
MIME = "application/x-ns-proxy-autoconfig"
SOCKS_PORT = 1080

# 這些開頭的網卡不是對外 LAN（tunnel、虛擬網卡），直接略過
_SKIP_PREFIXES = (
    "lo",
    "CloudflareWARP",
    "tun",
    "wg",
    "tailscale",
    "docker",
    "br-",
    "veth",
    "cni",
    "flannel",
    "cali",
)
_LOOPBACK = ipaddress.ip_network("127.0.0.0/8")


def _ifaddr(name: str) -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            packed = fcntl.ioctl(
                s.fileno(), 0x8915, struct.pack("256s", name[:15].encode())
            )
            return socket.inet_ntoa(packed[20:24])
    except OSError:
        return None


def detect_ip() -> str:
    """容器對外 LAN IP：第一個非 loopback、非 tunnel/虛擬網卡的 IPv4。"""
    try:
        names = sorted(os.listdir("/sys/class/net"))
    except OSError:
        names = []
    for name in names:
        if name.startswith(_SKIP_PREFIXES):
            continue
        ip = _ifaddr(name)
        if not ip:
            continue
        if ipaddress.ip_address(ip) in _LOOPBACK:
            continue
        return ip
    # 退路：hostname 解析（結果不保證，僅避免啟動失敗）
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


SELF_IP = detect_ip()
PROXY_LINE = f"SOCKS5 {SELF_IP}:{SOCKS_PORT}; DIRECT"


def render() -> bytes:
    text = TEMPLATE.read_text(encoding="utf-8")
    text = text.replace("__PROXY_TYPE__", "SOCKS5").replace(
        "__PROXY_ADDR__", f"{SELF_IP}:{SOCKS_PORT}"
    )
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
    print(f"pac-server: advertising {PROXY_LINE}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
