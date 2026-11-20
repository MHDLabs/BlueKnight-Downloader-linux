"""Deterministic tests for the extracted engine discovery and version service."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from blueknight.engines.manager import EngineManager


class EngineManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.tools_dir = self.root / "tools"
        self.specs = {
            "demo": {"exe": "demo", "urls": ("https://example.invalid/demo",)},
            "module-demo": {"exe": "module-demo", "module": "demo_module", "urls": ()},
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
        }
        options.update(overrides)
        return EngineManager(self.tools_dir, self.specs, **options)

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


if __name__ == "__main__":
    unittest.main()
