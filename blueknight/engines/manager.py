"""Low-level discovery and validation for the external desktop engines.

Installation and update orchestration remain in the application service for
now. This module owns the deterministic parts that can be tested separately:
native executable validation, tool lookup order and version probing.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path


class EngineManager:
    def __init__(
            self, tools_dir, tool_specs, *, bundled_tool, module_version,
            process_runner, is_windows=False, is_macos=False,
            system_which=None, minimum_executable_size=1024 * 1024):
        self.tools_dir = Path(tools_dir)
        self.tool_specs = tool_specs
        self.bundled_tool = bundled_tool
        self.module_version = module_version
        self.process_runner = process_runner
        self.system_which = system_which or shutil.which
        self.is_windows = is_windows
        self.is_macos = is_macos
        self.minimum_executable_size = minimum_executable_size

    def is_native_executable(self, path, minimum_size=None):
        """Validate a local executable signature and minimum file size."""
        if self.is_windows:
            magics = (b"MZ",)
        elif self.is_macos:
            magics = (
                b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",
                b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
            )
        else:
            magics = (b"\x7fELF",)
        try:
            path = Path(path)
            with path.open("rb") as handle:
                head = handle.read(4)
            required_size = (self.minimum_executable_size
                             if minimum_size is None else minimum_size)
            return (path.stat().st_size >= required_size
                    and any(head.startswith(magic) for magic in magics))
        except OSError:
            return False

    def find_tool(self, name):
        """Resolve the newest usable tool before trying older fallbacks.

        Precedence matches the legacy desktop behaviour: app-managed update,
        bundled copy, system PATH, then an installed Python module.
        """
        spec = self.tool_specs[name]
        downloaded = self.tools_dir / spec["exe"]
        if self.is_native_executable(downloaded):
            return str(downloaded)
        packaged = self.bundled_tool(spec["exe"])
        if packaged:
            return packaged
        found = self.system_which(name)
        if found:
            return found
        if spec.get("module") and self.module_version(name) != "unknown":
            return name
        return None

    def tool_version(self, path):
        """Run a tool version probe and normalize its output."""
        try:
            stem = Path(path).stem.lower()
            if stem.startswith("lib") and stem[3:] in {"ffmpeg", "ffprobe"}:
                stem = stem[3:]
            version_flag = "-version" if stem in {"ffmpeg", "ffprobe"} else "--version"
            result = self.process_runner([path, version_flag], timeout=45)
            lines = result.stdout.strip().splitlines()
            if result.returncode != 0 or not lines:
                return "unknown"
            if stem == "deno":
                match = re.match(r"deno\s+([0-9][^\s]*)", lines[0])
                return match.group(1) if match else lines[0].strip()
            if stem in {"ffmpeg", "ffprobe"}:
                match = re.match(r"ff(?:mpeg|probe) version\s+([^\s]+)", lines[0], re.I)
                return match.group(1) if match else lines[0].strip()
            return lines[-1].strip()
        except Exception:
            return "unknown"

    @staticmethod
    def release_urls(name, version=None, tool_specs=None,
                     spotdl_url_builder=None, ytdlp_url_builder=None):
        """Return version-specific mirror URLs or the catalog defaults."""
        if name == "spotdl" and version:
            return spotdl_url_builder(version.lstrip("vV"))
        if name == "yt-dlp" and version:
            return ytdlp_url_builder(version)
        return tool_specs[name]["urls"]


__all__ = ["EngineManager"]
