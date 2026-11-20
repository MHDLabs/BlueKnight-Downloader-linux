"""Deterministic tests for the extracted engine discovery and version service."""

from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
import zipfile
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

from blueknight.engines.manager import EngineManager


class FakeOpener:
    def __init__(self, responses):
        self.responses = dict(responses)
        self.requests = []

    def open(self, request, timeout=0):
        url = request.full_url
        self.requests.append((url, timeout, request))
        response = self.responses[url]
        if isinstance(response, Exception):
            raise response
        return io.BytesIO(response)


class EngineManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.tools_dir = self.root / "tools"
        self.specs = {
            "demo": {"exe": "demo", "label": "Demo Tool", "urls": ("https://example.invalid/demo",)},
            "module-demo": {"exe": "module-demo", "label": "Module Demo", "module": "demo_module", "urls": ()},
        }

    def tearDown(self):
        self.temporary.cleanup()

    def manager(self, **overrides):
        options = {
            "bundled_tool": lambda name: None,
            "module_version": lambda name: "unknown",
            "process_runner": lambda command, timeout: SimpleNamespace(
                returncode=0, stdout="demo 1.2.3\n"),
            "is_windows": False,
            "is_macos": False,
            "system_which": lambda name: None,
            "minimum_executable_size": 4,
            "net_opener": lambda: nullcontext(FakeOpener({})),
            "ui_callback": lambda *args: None,
            "log_callback": lambda *args: None,
            "make_executable": lambda path: None,
            "app_name": "Blue Knight Tests",
            "app_version": "9.9.9",
            "spotdl_url_builder": lambda version: (f"https://spotdl.test/{version}",),
            "ytdlp_url_builder": lambda version: (f"https://ytdlp.test/{version}",),
        }
        options.update(overrides)
        tool_specs = options.pop("tool_specs", self.specs)
        return EngineManager(self.tools_dir, tool_specs, **options)

    def write_binary(self, path, prefix):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(prefix + b"\x00" * 8)
        return path

    def test_linux_elf_is_accepted(self):
        manager = self.manager()
        executable = self.write_binary(self.root / "demo", b"\x7fELF")
        self.assertTrue(manager.is_native_executable(executable))

    def test_windows_pe_is_accepted(self):
        manager = self.manager(is_windows=True)
        executable = self.write_binary(self.root / "demo.exe", b"MZ")
        self.assertTrue(manager.is_native_executable(executable))
        self.assertFalse(self.manager().is_native_executable(executable))

    def test_macos_thin_and_universal_macho_signatures_are_accepted(self):
        manager = self.manager(is_macos=True)
        for index, magic in enumerate((b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",
                                       b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca")):
            with self.subTest(magic=magic):
                executable = self.write_binary(self.root / f"mac-{index}", magic)
                self.assertTrue(manager.is_native_executable(executable))

    def test_wrong_signature_small_or_missing_files_are_rejected(self):
        manager = self.manager()
        wrong = self.write_binary(self.root / "html", b"<htm")
        small = self.root / "small"
        small.write_bytes(b"\x7fEL")
        self.assertFalse(manager.is_native_executable(wrong))
        self.assertFalse(manager.is_native_executable(small))
        self.assertFalse(manager.is_native_executable(self.root / "missing"))

    def test_version_probe_uses_ffmpeg_flag_and_parses_version(self):
        calls = []

        def runner(command, timeout):
            calls.append((command, timeout))
            return SimpleNamespace(returncode=0, stdout="ffmpeg version 7.1.2 Copyright\n")

        manager = self.manager(process_runner=runner)
        self.assertEqual(manager.tool_version("/tmp/ffmpeg"), "7.1.2")
        self.assertEqual(calls[0][0][-1], "-version")
        self.assertEqual(calls[0][1], 45)

    def test_version_probe_handles_deno_and_generic_tools(self):
        manager = self.manager(process_runner=lambda command, timeout: SimpleNamespace(
            returncode=0, stdout="deno 2.9.5\n"))
        self.assertEqual(manager.tool_version("deno"), "2.9.5")
        generic = self.manager(process_runner=lambda command, timeout: SimpleNamespace(
            returncode=0, stdout="tool\nversion 4.5.6\n"))
        self.assertEqual(generic.tool_version("demo"), "version 4.5.6")

    def test_failed_or_empty_version_probes_return_unknown(self):
        failed = self.manager(process_runner=lambda command, timeout: SimpleNamespace(
            returncode=1, stdout="failure"))
        empty = self.manager(process_runner=lambda command, timeout: SimpleNamespace(
            returncode=0, stdout=""))
        broken = self.manager(process_runner=lambda command, timeout: (_ for _ in ()).throw(OSError("no exec")))
        self.assertEqual(failed.tool_version("demo"), "unknown")
        self.assertEqual(empty.tool_version("demo"), "unknown")
        self.assertEqual(broken.tool_version("demo"), "unknown")

    def test_downloaded_copy_has_precedence_over_bundle_and_path(self):
        self.write_binary(self.tools_dir / "demo", b"\x7fELF")
        manager = self.manager(
            bundled_tool=lambda name: "/bundled/" + name,
            system_which=lambda name: "/usr/bin/" + name,
        )
        self.assertEqual(manager.find_tool("demo"), str(self.tools_dir / "demo"))

    def test_bundle_precedes_system_path_and_module_fallback(self):
        manager = self.manager(
            bundled_tool=lambda name: "/bundled/" + name,
            system_which=lambda name: "/usr/bin/" + name,
            module_version=lambda name: "9.9.9",
        )
        self.assertEqual(manager.find_tool("demo"), "/bundled/demo")

    def test_system_path_precedes_python_module_fallback(self):
        manager = self.manager(
            system_which=lambda name: "/usr/bin/" + name,
            module_version=lambda name: "9.9.9",
        )
        self.assertEqual(manager.find_tool("module-demo"), "/usr/bin/module-demo")

    def test_python_module_is_last_fallback_and_missing_tool_returns_none(self):
        manager = self.manager(module_version=lambda name: "1.0")
        self.assertEqual(manager.find_tool("module-demo"), "module-demo")
        self.assertIsNone(manager.find_tool("demo"))

    def test_invalid_downloaded_file_falls_back_to_bundled_copy(self):
        self.tools_dir.mkdir(parents=True)
        (self.tools_dir / "demo").write_text("not an executable", encoding="utf-8")
        manager = self.manager(bundled_tool=lambda name: "/bundled/" + name)
        self.assertEqual(manager.find_tool("demo"), "/bundled/demo")

    def test_versioned_release_urls_keep_existing_mirror_rules(self):
        specs = {
            **self.specs,
            "spotdl": {"exe": "spotdl", "urls": ()},
            "yt-dlp": {"exe": "yt-dlp", "urls": ()},
        }
        spotdl = EngineManager.release_urls(
            "spotdl", "v9.9.9", specs,
            lambda version: (f"spotdl/{version}",), lambda version: ())
        ytdlp = EngineManager.release_urls(
            "yt-dlp", "2026.07.04", specs,
            lambda version: (), lambda version: (f"yt-dlp/{version}",))
        default = EngineManager.release_urls(
            "demo", None, specs, lambda version: (), lambda version: ())
        self.assertEqual(spotdl, ("spotdl/9.9.9",))
        self.assertEqual(ytdlp, ("yt-dlp/2026.07.04",))
        self.assertEqual(default, self.specs["demo"]["urls"])


    def test_download_with_fallbacks_retries_mirrors_and_activates_atomically(self):
        urls = ("https://one.example/tool", "https://two.example/tool")
        opener = FakeOpener({urls[0]: OSError("mirror unavailable"), urls[1]: b"downloaded payload"})
        ui_events, log_events = [], []
        manager = self.manager(
            net_opener=lambda: nullcontext(opener),
            ui_callback=lambda *args: ui_events.append(args),
            log_callback=lambda *args: log_events.append(args))
        destination = self.tools_dir / "tool.bin"

        result = manager.download_with_fallbacks(urls, destination, "Demo Tool")

        self.assertEqual(result, destination)
        self.assertEqual(destination.read_bytes(), b"downloaded payload")
        self.assertFalse(destination.with_suffix(".bin.part").exists())
        self.assertEqual([call[0] for call in opener.requests], list(urls))
        self.assertEqual(len(ui_events), 2)
        self.assertTrue(any(event[1] == "warning" for event in log_events))

    def test_download_with_fallbacks_rejects_empty_files_and_cleans_partial_data(self):
        urls = ("https://empty.example/tool", "https://offline.example/tool")
        opener = FakeOpener({urls[0]: b"", urls[1]: OSError("connection refused")})
        manager = self.manager(net_opener=lambda: nullcontext(opener))
        destination = self.tools_dir / "tool.bin"

        with self.assertRaisesRegex(RuntimeError, "All Demo Tool download sources failed"):
            manager.download_with_fallbacks(urls, destination, "Demo Tool")

        self.assertFalse(destination.exists())
        self.assertFalse(destination.with_suffix(".bin.part").exists())
        self.assertEqual(len(opener.requests), 2)

    def test_latest_version_normalizes_release_tags_and_sends_app_headers(self):
        url = "https://api.example.test/releases/latest"
        opener = FakeOpener({url: b'{"tag_name":"v2.3.4"}'})
        specs = {**self.specs, "demo": {**self.specs["demo"], "api": url}}
        manager = self.manager(net_opener=lambda: nullcontext(opener), tool_specs=specs)

        self.assertEqual(manager.latest_version("demo"), "2.3.4")
        request = opener.requests[0][2]
        self.assertEqual(request.get_header("User-agent"), "Blue Knight Tests/9.9.9")
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertEqual(opener.requests[0][1], 20)

    def test_latest_version_without_api_or_with_network_failure_returns_none(self):
        self.assertIsNone(self.manager().latest_version("demo"))
        url = "https://api.example.test/releases/latest"
        specs = {**self.specs, "demo": {**self.specs["demo"], "api": url}}
        opener = FakeOpener({url: OSError("offline")})
        offline = self.manager(net_opener=lambda: nullcontext(opener), tool_specs=specs)
        self.assertIsNone(offline.latest_version("demo"))

    def test_tool_installation_reuses_existing_tool_without_network(self):
        existing = self.write_binary(self.tools_dir / "demo", b"\x7fELF")
        manager = self.manager(net_opener=lambda: (_ for _ in ()).throw(
            AssertionError("network should not be used")))
        self.assertEqual(manager.get_or_download_tool("demo"), str(existing))

    def test_tool_installation_validates_version_before_atomic_activation(self):
        url = self.specs["demo"]["urls"][0]
        opener = FakeOpener({url: b"\x7fELF" + b"\x00" * 16})
        chmod_calls = []
        manager = self.manager(
            net_opener=lambda: nullcontext(opener),
            make_executable=lambda path: chmod_calls.append(Path(path)),
            process_runner=lambda command, timeout: SimpleNamespace(
                returncode=0, stdout="1.2.3\\n"))

        result = manager.get_or_download_tool("demo", force=True, version="1.2.3")

        target = self.tools_dir / "demo"
        self.assertEqual(result, str(target))
        self.assertEqual(target.read_bytes(), b"\x7fELF" + b"\x00" * 16)
        self.assertEqual(chmod_calls, [target.with_name("demo.new")])
        self.assertFalse(target.with_name("demo.new").exists())
        self.assertFalse(target.with_name("demo.new.part").exists())

    def test_archive_installation_checks_sha256_and_extracts_expected_member(self):
        binary = b"\x7fELF" + b"\x00" * 16
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("bin/demo", binary)
        archive_bytes = buffer.getvalue()
        digest = hashlib.sha256(archive_bytes).hexdigest()
        specs = {"archive-demo": {
            "exe": "archive-demo", "label": "Archive Demo",
            "urls": ("https://download.example/archive.zip",),
            "archive_member": "bin/demo",
            "checksum_urls": ("https://download.example/archive.sha256",)}}
        opener = FakeOpener({
            specs["archive-demo"]["urls"][0]: archive_bytes,
            specs["archive-demo"]["checksum_urls"][0]: f"{digest}  archive.zip\n".encode()})
        manager = self.manager(
            tool_specs=specs, net_opener=lambda: nullcontext(opener),
            process_runner=lambda command, timeout: SimpleNamespace(
                returncode=0, stdout="archive-demo 1.0.0\n"))

        result = manager.get_or_download_tool("archive-demo", force=True)

        target = self.tools_dir / "archive-demo"
        self.assertEqual(result, str(target))
        self.assertEqual(target.read_bytes(), binary)
        self.assertFalse(target.with_name("archive-demo.zip.new").exists())
        self.assertFalse(target.with_name("archive-demo.sha256.new").exists())
        self.assertFalse(target.with_name("archive-demo.new").exists())

    def test_archive_checksum_mismatch_never_activates_candidate(self):
        binary = b"\x7fELF" + b"\x00" * 16
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("bin/demo", binary)
        archive_bytes = buffer.getvalue()
        specs = {"archive-demo": {
            "exe": "archive-demo", "label": "Archive Demo",
            "urls": ("https://download.example/archive.zip",),
            "archive_member": "bin/demo",
            "checksum_urls": ("https://download.example/archive.sha256",)}}
        opener = FakeOpener({
            specs["archive-demo"]["urls"][0]: archive_bytes,
            specs["archive-demo"]["checksum_urls"][0]: (b"0" * 64) + b"  archive.zip\n"})
        manager = self.manager(tool_specs=specs, net_opener=lambda: nullcontext(opener))

        with self.assertRaisesRegex(RuntimeError, "failed its SHA-256 check"):
            manager.get_or_download_tool("archive-demo", force=True)

        self.assertFalse((self.tools_dir / "archive-demo").exists())
        self.assertFalse((self.tools_dir / "archive-demo.new").exists())
        self.assertFalse((self.tools_dir / "archive-demo.zip.new").exists())
        self.assertFalse((self.tools_dir / "archive-demo.sha256.new").exists())

    def test_archive_missing_expected_member_is_rejected_and_cleaned(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("wrong/path", b"\x7fELF" + b"\x00" * 16)
        specs = {"archive-demo": {
            "exe": "archive-demo", "label": "Archive Demo",
            "urls": ("https://download.example/archive.zip",),
            "archive_member": "bin/demo"}}
        opener = FakeOpener({specs["archive-demo"]["urls"][0]: buffer.getvalue()})
        manager = self.manager(tool_specs=specs, net_opener=lambda: nullcontext(opener))

        with self.assertRaisesRegex(RuntimeError, "does not contain bin/demo"):
            manager.get_or_download_tool("archive-demo", force=True)

        self.assertFalse((self.tools_dir / "archive-demo").exists())
        self.assertFalse((self.tools_dir / "archive-demo.zip.new").exists())

    def test_version_mismatch_preserves_previous_installed_binary(self):
        target = self.write_binary(self.tools_dir / "demo", b"\x7fELF")
        previous = target.read_bytes()
        url = self.specs["demo"]["urls"][0]
        opener = FakeOpener({url: b"\x7fELF" + b"\x00" * 16})
        manager = self.manager(
            net_opener=lambda: nullcontext(opener),
            process_runner=lambda command, timeout: SimpleNamespace(
                returncode=0, stdout="demo 9.9.9\n"))

        with self.assertRaisesRegex(RuntimeError, "expected 1.2.3"):
            manager.get_or_download_tool("demo", force=True, version="1.2.3")

        self.assertEqual(target.read_bytes(), previous)
        self.assertFalse(target.with_name("demo.new").exists())


if __name__ == "__main__":
    unittest.main()
