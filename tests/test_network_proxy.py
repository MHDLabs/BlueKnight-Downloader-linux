#!/usr/bin/env python3
"""Unit and loopback integration tests for the desktop proxy module."""

from __future__ import annotations

import os
import socket
import socketserver
import threading
import unittest
from urllib.parse import urlsplit

from blueknight.network.proxy import (
    Socks5HttpBridge,
    apply_process_proxy,
    display_proxy_url,
    normalize_proxy_url,
)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("unexpected EOF")
        data.extend(chunk)
    return bytes(data)


def recv_until(sock: socket.socket, marker: bytes) -> bytes:
    data = bytearray()
    while marker not in data:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("unexpected EOF before response headers")
        data.extend(chunk)
    return bytes(data)


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class EchoHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while True:
            data = self.request.recv(4096)
            if not data:
                return
            self.request.sendall(data)


class SocksHandler(socketserver.BaseRequestHandler):
    """Minimal local SOCKS5 server used only by the bridge integration test."""

    def handle(self) -> None:
        version, count = recv_exact(self.request, 2)
        if version != 5:
            raise AssertionError("unexpected SOCKS version")
        recv_exact(self.request, count)
        self.request.sendall(b"\x05\x00")

        version, command, _, address_type = recv_exact(self.request, 4)
        if version != 5 or command != 1:
            raise AssertionError("expected a SOCKS5 CONNECT request")

        if address_type == 1:
            host = socket.inet_ntoa(recv_exact(self.request, 4))
        elif address_type == 3:
            length = recv_exact(self.request, 1)[0]
            host = recv_exact(self.request, length).decode("idna")
        elif address_type == 4:
            host = socket.inet_ntop(socket.AF_INET6, recv_exact(self.request, 16))
        else:
            raise AssertionError("unsupported SOCKS address type")

        port = int.from_bytes(recv_exact(self.request, 2), "big")
        upstream = socket.create_connection((host, port), timeout=5)
        self.request.sendall(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00")
        try:
            Socks5HttpBridge._relay(self.request, upstream)
        finally:
            upstream.close()


class ProxyUrlTests(unittest.TestCase):
    def test_adds_http_scheme_and_default_port(self) -> None:
        self.assertEqual(
            normalize_proxy_url("127.0.0.1:10809", "http"),
            "http://127.0.0.1:10809",
        )

    def test_adds_remote_dns_scheme_for_bare_socks5(self) -> None:
        self.assertEqual(
            normalize_proxy_url("127.0.0.1", "socks5"),
            "socks5h://127.0.0.1:1080",
        )

    def test_preserves_encoded_credentials(self) -> None:
        self.assertEqual(
            normalize_proxy_url("socks5://user:p%40ss@localhost:10808"),
            "socks5://user:p%40ss@localhost:10808",
        )

    def test_supports_ipv6_authorities(self) -> None:
        self.assertEqual(
            normalize_proxy_url("[::1]:7890", "http"),
            "http://[::1]:7890",
        )

    def test_uses_scheme_specific_default_ports(self) -> None:
        self.assertEqual(
            normalize_proxy_url("http://proxy.example"),
            "http://proxy.example:8080",
        )
        self.assertEqual(
            normalize_proxy_url("socks5h://proxy.example"),
            "socks5h://proxy.example:1080",
        )

    def test_rejects_empty_or_unsupported_values(self) -> None:
        for value, kind in [
            ("", "http"),
            ("proxy.example:8080", "ftp"),
            ("http://", "http"),
            ("http://proxy.example:bad", "http"),
        ]:
            with self.subTest(value=value, kind=kind):
                with self.assertRaises(ValueError):
                    normalize_proxy_url(value, kind)

    def test_hides_proxy_credentials_in_display(self) -> None:
        self.assertEqual(
            display_proxy_url("http://mahdi:secret@example.test:8080"),
            "http://***@example.test:8080",
        )

    def test_socks_bridge_accepts_only_socks5(self) -> None:
        bridge = Socks5HttpBridge("user:p%40ss@127.0.0.1:1080")
        self.assertEqual(bridge.host, "127.0.0.1")
        self.assertEqual(bridge.port, 1080)
        self.assertEqual(bridge.username, "user")
        self.assertEqual(bridge.password, "p@ss")
        with self.assertRaises(ValueError):
            Socks5HttpBridge("http://127.0.0.1:8080")


class ProcessProxyEnvironmentTests(unittest.TestCase):
    KEYS = (
        "http_proxy", "https_proxy", "all_proxy",
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    )

    def setUp(self) -> None:
        self.original = {key: os.environ.get(key) for key in self.KEYS}

    def tearDown(self) -> None:
        for key, value in self.original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_http_proxy_sets_http_and_all_proxy_variables(self) -> None:
        apply_process_proxy("http://127.0.0.1:8080")
        for key in self.KEYS:
            self.assertEqual(os.environ.get(key), "http://127.0.0.1:8080")

    def test_socks_proxy_does_not_poison_http_only_clients(self) -> None:
        apply_process_proxy("socks5h://127.0.0.1:1080")
        self.assertEqual(os.environ.get("all_proxy"), "socks5h://127.0.0.1:1080")
        self.assertEqual(os.environ.get("ALL_PROXY"), "socks5h://127.0.0.1:1080")
        for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
            self.assertNotIn(key, os.environ)

    def test_none_clears_previous_proxy_environment(self) -> None:
        for key in self.KEYS:
            os.environ[key] = "http://stale.example:8080"
        apply_process_proxy(None)
        for key in self.KEYS:
            self.assertNotIn(key, os.environ)


class SocksBridgeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.echo = ThreadingServer(("127.0.0.1", 0), EchoHandler)
        self.socks = ThreadingServer(("127.0.0.1", 0), SocksHandler)
        self.echo_thread = threading.Thread(target=self.echo.serve_forever, daemon=True)
        self.socks_thread = threading.Thread(target=self.socks.serve_forever, daemon=True)
        self.echo_thread.start()
        self.socks_thread.start()
        socks_url = f"socks5://127.0.0.1:{self.socks.server_address[1]}"
        self.bridge = Socks5HttpBridge(socks_url)
        self.bridge_url = self.bridge.start()

    def tearDown(self) -> None:
        self.bridge.close()
        self.socks.shutdown()
        self.socks.server_close()
        self.echo.shutdown()
        self.echo.server_close()

    def test_connect_tunnel_through_local_socks_server(self) -> None:
        parsed = urlsplit(self.bridge_url)
        client = socket.create_connection((parsed.hostname, parsed.port), timeout=5)
        try:
            target_port = self.echo.server_address[1]
            client.sendall(
                f"CONNECT 127.0.0.1:{target_port} HTTP/1.1\r\n"
                "Host: 127.0.0.1\r\n\r\n".encode("ascii")
            )
            response = recv_until(client, b"\r\n\r\n")
            self.assertIn(b"200 Connection Established", response)
            client.sendall(b"bridge works")
            self.assertEqual(recv_exact(client, 12), b"bridge works")
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
