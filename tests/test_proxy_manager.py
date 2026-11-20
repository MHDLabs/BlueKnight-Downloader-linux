#!/usr/bin/env python3
"""Tests for the callback-driven desktop ProxyManager."""

from __future__ import annotations

import os
import ssl
import unittest
from unittest.mock import patch
import urllib.request
from urllib.parse import urlsplit

from blueknight.network.proxy import ProxyManager


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _HostOpener:
    def __init__(self, failures=()):
        self.failures = set(failures)
        self.requested = []

    def open(self, request, timeout=0):
        host = urlsplit(request.full_url).hostname
        self.requested.append((host, timeout, request.get_method()))
        if host in self.failures:
            raise TimeoutError(f"{host} timed out")
        return _Response()


class ProxyManagerTests(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "enabled": True,
            "type": "http",
            "url": "http://127.0.0.1:10809",
        }
        self.logs = []
        self.notifications = []
        self.batch_logs = []
        self.manager = ProxyManager(
            get_settings=lambda: (
                self.settings["enabled"],
                self.settings["type"],
                self.settings["url"],
            ),
            set_settings=self._set_settings,
            log=lambda message, level="info": self.logs.append((message, level)),
            notify=lambda message, kind="info": self.notifications.append((message, kind)),
            batch_log=lambda message, level="info": self.batch_logs.append((message, level)),
            ssl_context=ssl.create_default_context(),
            user_agent="BlueKnight-Proxy-Test/1",
            app_name="BlueKnight-Proxy-Test",
            app_version="1",
        )

    def _set_settings(self, enabled, proxy_type, url):
        self.settings.update(enabled=enabled, type=proxy_type, url=url)

    def test_configured_proxy_uses_current_settings(self):
        self.assertEqual(
            self.manager.configured_proxy(),
            "http://127.0.0.1:10809",
        )
        self.settings["enabled"] = False
        self.assertIsNone(self.manager.configured_proxy())

    def test_invalid_proxy_configuration_is_reported_as_unconfigured(self):
        self.settings["url"] = "ftp://proxy.example:21"
        self.assertIsNone(self.manager.configured_proxy())

    def test_preset_updates_application_settings_and_logs(self):
        self.manager.set_preset("socks5", "127.0.0.1:10808")
        self.assertEqual(
            self.settings,
            {"enabled": True, "type": "socks5", "url": "127.0.0.1:10808"},
        )
        self.assertTrue(any("local bridge" in message for message, _ in self.logs))

    def test_media_host_check_reports_split_route(self):
        opener = _HostOpener(failures={"redirector.googlevideo.com"})
        result = self.manager.check_media_hosts(opener)
        self.assertEqual(result, {
            "youtube.com": True,
            "googlevideo.com": False,
        })
        self.assertTrue(any(
            "Send googlevideo.com" in message and level == "error"
            for message, level in self.logs
        ))
        self.assertEqual(len(opener.requested), 2)
        self.assertTrue(all(timeout == 15 and method == "HEAD"
                            for _, timeout, method in opener.requested))

    def test_network_opener_uses_the_active_http_proxy(self):
        with self.manager.net_opener() as opener:
            handler = next(
                item for item in opener.handlers
                if isinstance(item, urllib.request.ProxyHandler)
            )
            self.assertEqual(handler.proxies, {
                "http": "http://127.0.0.1:10809",
                "https": "http://127.0.0.1:10809",
            })

    def test_network_opener_has_no_proxy_when_disabled(self):
        self.settings["enabled"] = False
        # urllib installs its own default ProxyHandler. With the environment
        # cleared, that default handler must remain empty when app proxy is off.
        with patch.dict(os.environ, {}, clear=True):
            with self.manager.net_opener() as opener:
                handler = next(
                    item for item in opener.handlers
                    if isinstance(item, urllib.request.ProxyHandler)
                )
                self.assertEqual(handler.proxies, {})

    def test_spotdl_adapter_does_not_create_bridge_for_http(self):
        proxy, bridge = self.manager.prepare_for_spotdl(
            "127.0.0.1:10809", "http"
        )
        self.assertEqual(proxy, "http://127.0.0.1:10809")
        self.assertIsNone(bridge)

    def test_invalid_proxy_test_notifies_without_starting_worker(self):
        self.settings["url"] = "ftp://proxy.example:21"
        self.manager.test_proxy()
        self.assertTrue(self.notifications)
        self.assertIn("Proxy scheme", self.notifications[-1][0])


if __name__ == "__main__":
    unittest.main()
