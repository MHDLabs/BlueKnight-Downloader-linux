"""Regression tests for partial media-file cleanup and storage failures."""

import contextlib
import errno
import sys
import tempfile
import types
import unittest
from email.message import Message
from pathlib import Path
from unittest import mock

# These tests exercise the download methods without opening a desktop window.
# The frontend-check runner is headless and does not install a native WebView backend.
sys.modules.setdefault("webview", types.ModuleType("webview"))

from spotify_downloader import SpotifyDownloader


class FakeResponse:
    def __init__(self, content_length, *, error_after_head=None):
        self.headers = Message()
        self.headers["Content-Type"] = "video/mp4"
        self.headers["Content-Length"] = str(content_length)
        self.error_after_head = error_after_head
        self.read_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _size):
        self.read_count += 1
        if self.read_count == 1:
            return b"m" * 512
        if self.error_after_head is not None:
            raise self.error_after_head
        return b""


class DownloadStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.app = SpotifyDownloader.__new__(SpotifyDownloader)
        self.app.is_downloading = True
        self.app.last_ui_update = 0
        self.app.ui = lambda *_args: None
        self.app._batch_log = lambda *_args: None
        self.app._flush_logs = lambda: None

    def tearDown(self):
        self.temp.cleanup()

    def test_truncated_media_response_is_rejected_and_partial_is_removed(self):
        response = FakeResponse(1024)

        with self.assertRaisesRegex(RuntimeError, "closed the media file early"):
            self.app._save_stream(
                response, self.output, "https://media.example/video.mp4",
                1, 1, suffix=".mp4", name_hint="video.mp4")

        self.assertEqual(list(self.output.iterdir()), [])

    def test_storage_failure_aborts_resolved_media_batch_and_cleans_partial(self):
        response = FakeResponse(
            1024, error_after_head=OSError(errno.ENOSPC, "No space left on device"))
        self.app._net_opener = lambda: contextlib.nullcontext(object())
        self.app._open_url = lambda _opener, _url: response

        with self.assertRaisesRegex(OSError, "No space left on device"):
            self.app._download_media_urls(
                [("https://media.example/video.mp4", "video.mp4", "mp4")],
                self.output, "video")

        self.assertEqual(list(self.output.iterdir()), [])

    def test_streamlink_read_failure_closes_handle_and_removes_partial(self):
        handle_state = {"closed": False}

        class Handle:
            def read(self, _size):
                raise OSError(errno.ENOSPC, "No space left on device")

            def close(self):
                handle_state["closed"] = True

        class Stream:
            def open(self):
                return Handle()

        class Session:
            def set_option(self, *_args):
                pass

            def streams(self, _url):
                return {"best": Stream()}

        streamlink = types.ModuleType("streamlink")
        streamlink.Streamlink = Session
        self.app.use_proxy = types.SimpleNamespace(get=lambda: False)
        self.app.proxy_url = types.SimpleNamespace(get=lambda: "")
        self.app.proxy_type = types.SimpleNamespace(get=lambda: "http")

        with mock.patch.dict(sys.modules, {"streamlink": streamlink}):
            with self.assertRaisesRegex(OSError, "No space left on device"):
                self.app._download_with_streamlink(
                    "https://media.example/live", self.output, "best", False)

        self.assertTrue(handle_state["closed"])
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
