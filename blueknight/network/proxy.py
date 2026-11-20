"""Cross-platform proxy URL handling and the local SOCKS5-to-HTTP bridge."""

from __future__ import annotations

import ipaddress
import os
import select
import socket
import socketserver
import threading
from urllib.parse import quote, unquote, urlsplit


__all__ = [
    "Socks5HttpBridge",
    "apply_process_proxy",
    "display_proxy_url",
    "normalize_proxy_url",
]


_PROXY_ENV_KEYS = ("http_proxy", "https_proxy", "all_proxy",
                   "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")


def apply_process_proxy(proxy=None):
    """Point everything in this process at the proxy, or clear it.

    The app hands --proxy to yt-dlp, to streamlink and to its own fetcher, and
    when that was written those were everything. They are not: gallery-dl
    resolves a post over the network, ffmpeg can open a stream, and any library
    that reaches out on its own does so unasked. With a whole-device VPN none
    of that mattered, because there was no un-tunnelled connection left to leak
    to. With a local proxy client there is, so those requests went out from one
    address while the download went out from another — which is both a failure
    on a network that blocks them and, where they succeed, a session used from
    two places at once.

    HTTP and SOCKS are not set the same way on purpose. Only an HTTP proxy goes
    into http_proxy and https_proxy: those are read by things that cannot speak
    SOCKS at all — ffmpeg among them — and handing one a socks5 URL there turns
    a working direct request into a broken proxied one. A SOCKS proxy is
    published as all_proxy, which the Python side understands, and the callers
    that need a real HTTP endpoint keep building their own bridge for it.
    """
    for key in _PROXY_ENV_KEYS:
        os.environ.pop(key, None)
    if not proxy:
        return
    scheme = urlsplit(proxy).scheme.lower()
    keys = ("all_proxy", "ALL_PROXY")
    if not scheme.startswith("socks"):
        keys += ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY")
    for key in keys:
        os.environ[key] = proxy


def normalize_proxy_url(value, proxy_type="http"):
    """Validate a proxy URL and add the selected scheme when it is omitted."""
    value = value.strip()
    if not value:
        raise ValueError("Proxy URL is empty")
    if "://" not in value:
        # socks5h, not socks5, when we are the ones choosing: the h is what
        # sends the hostname to the proxy instead of resolving it here.
        #
        # It matters more than it sounds. YouTube hands out media on
        # googlevideo hosts that DNS steers to a node near whoever asked, so
        # resolving locally picks a node for this network and then fetches it
        # down a tunnel that comes out somewhere else entirely — and the
        # mismatch comes back 403 Forbidden. Local resolution also walks
        # straight into whatever the local resolver does to these names, which
        # on a network worth proxying is the reason the proxy is there.
        #
        # A whole-device tunnel never had this problem, because DNS went
        # through it too. A local SOCKS proxy only carries what it is asked to.
        if proxy_type == "socks5":
            proxy_type = "socks5h"
        value = f"{proxy_type}://{value}"

    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https", "socks5", "socks5h"}:
        raise ValueError("Proxy scheme must be http, https, socks5, or socks5h")
    if not parsed.hostname:
        raise ValueError("Proxy URL must include a host")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Proxy URL has an invalid port") from exc
    if port is None:
        port = 1080 if scheme.startswith("socks5") else 8080

    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    auth = ""
    if parsed.username is not None:
        auth = quote(unquote(parsed.username), safe="")
        if parsed.password is not None:
            auth += ":" + quote(unquote(parsed.password), safe="")
        auth += "@"
    return f"{scheme}://{auth}{host}:{port}"


def display_proxy_url(value):
    """Hide proxy credentials before displaying the URL in the activity log."""
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    auth = "***@" if parsed.username is not None else ""
    return f"{parsed.scheme}://{auth}{host}:{parsed.port}"


def _recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Proxy closed the connection")
        data.extend(chunk)
    return bytes(data)


class Socks5HttpBridge:
    """Expose a local HTTP CONNECT proxy backed by a SOCKS5 proxy."""

    def __init__(self, proxy_url):
        parsed = urlsplit(normalize_proxy_url(proxy_url, "socks5"))
        if not parsed.scheme.startswith("socks5"):
            raise ValueError("The local bridge requires a SOCKS5 proxy")
        self.host = parsed.hostname
        self.port = parsed.port
        self.username = unquote(parsed.username) if parsed.username else None
        self.password = unquote(parsed.password) if parsed.password else ""
        self.server = None
        self.thread = None

    def _open_target(self, target_host, target_port):
        sock = socket.create_connection((self.host, self.port), timeout=15)
        methods = b"\x00\x02" if self.username is not None else b"\x00"
        sock.sendall(b"\x05" + bytes([len(methods)]) + methods)
        version, method = _recv_exact(sock, 2)
        if version != 5 or method == 0xFF:
            sock.close()
            raise ConnectionError("SOCKS5 proxy rejected authentication methods")
        if method == 2:
            if self.username is None:
                sock.close()
                raise ConnectionError("SOCKS5 proxy requires a username and password")
            user = self.username.encode("utf-8")
            password = self.password.encode("utf-8")
            if len(user) > 255 or len(password) > 255:
                sock.close()
                raise ValueError("SOCKS5 credentials are too long")
            sock.sendall(b"\x01" + bytes([len(user)]) + user + bytes([len(password)]) + password)
            if _recv_exact(sock, 2)[1] != 0:
                sock.close()
                raise ConnectionError("SOCKS5 authentication failed")
        elif method != 0:
            sock.close()
            raise ConnectionError("SOCKS5 proxy selected an unsupported authentication method")

        try:
            address = ipaddress.ip_address(target_host)
            atyp = 1 if address.version == 4 else 4
            encoded_host = address.packed
        except ValueError:
            encoded_host = target_host.encode("idna")
            if len(encoded_host) > 255:
                sock.close()
                raise ValueError("Target hostname is too long")
            atyp = 3
            encoded_host = bytes([len(encoded_host)]) + encoded_host

        sock.sendall(b"\x05\x01\x00" + bytes([atyp]) + encoded_host + target_port.to_bytes(2, "big"))
        version, result, _, bound_type = _recv_exact(sock, 4)
        if version != 5 or result != 0:
            sock.close()
            raise ConnectionError(f"SOCKS5 connection failed (code {result})")
        if bound_type == 1:
            _recv_exact(sock, 4)
        elif bound_type == 4:
            _recv_exact(sock, 16)
        elif bound_type == 3:
            _recv_exact(sock, _recv_exact(sock, 1)[0])
        else:
            sock.close()
            raise ConnectionError("SOCKS5 proxy returned an invalid address")
        _recv_exact(sock, 2)
        sock.settimeout(None)
        return sock

    @staticmethod
    def _split_authority(authority, default_port):
        parsed = urlsplit("//" + authority)
        if not parsed.hostname:
            raise ValueError("Invalid proxy request target")
        return parsed.hostname, parsed.port or default_port

    @staticmethod
    def _relay(client, upstream):
        sockets = (client, upstream)
        while True:
            readable, _, _ = select.select(sockets, [], [], 60)
            if not readable:
                return
            for source in readable:
                data = source.recv(65536)
                if not data:
                    return
                (upstream if source is client else client).sendall(data)

    def start(self):
        bridge = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.settimeout(15)
                header = bytearray()
                while b"\r\n\r\n" not in header:
                    chunk = self.request.recv(4096)
                    if not chunk:
                        return
                    header.extend(chunk)
                    if len(header) > 65536:
                        raise ValueError("HTTP proxy request headers are too large")

                head, body = bytes(header).split(b"\r\n\r\n", 1)
                lines = head.split(b"\r\n")
                method, target, version = lines[0].decode("latin-1").split(" ", 2)
                if method.upper() == "CONNECT":
                    host, port = bridge._split_authority(target, 443)
                    upstream = bridge._open_target(host, port)
                    self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                else:
                    parsed = urlsplit(target)
                    if not parsed.hostname:
                        raise ValueError("HTTP proxy requests must use an absolute URL")
                    host = parsed.hostname
                    port = parsed.port or (443 if parsed.scheme == "https" else 80)
                    upstream = bridge._open_target(host, port)
                    path = parsed.path or "/"
                    if parsed.query:
                        path += "?" + parsed.query
                    clean_headers = [line for line in lines[1:] if not line.lower().startswith(b"proxy-connection:")]
                    request_head = f"{method} {path} {version}\r\n".encode("latin-1")
                    upstream.sendall(request_head + b"\r\n".join(clean_headers) + b"\r\n\r\n" + body)
                try:
                    bridge._relay(self.request, upstream)
                finally:
                    upstream.close()

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

            def handle_error(self, request, client_address):
                pass

        self.server = Server(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
