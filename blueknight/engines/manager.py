"""Low-level discovery and validation for the external desktop engines.

Installation and update orchestration remain in the application service for
now. This module owns the deterministic parts that can be tested separately:
native executable validation, tool lookup order and version probing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlsplit


class EngineManager:
    def __init__(
            self, tools_dir, tool_specs, *, bundled_tool, module_version,
            process_runner, is_windows=False, is_macos=False,
            system_which=None, minimum_executable_size=1024 * 1024,
            net_opener=None, ui_callback=None, log_callback=None,
            make_executable=None, app_name="Blue Knight Downloader",
            app_version="0", spotdl_url_builder=None, ytdlp_url_builder=None,
            python_components=None, engine_update_root=None,
            engine_update_registry=None, wheel_selector=None):
        self.tools_dir = Path(tools_dir)
        self.tool_specs = tool_specs
        self.bundled_tool = bundled_tool
        self.module_version = module_version
        self.process_runner = process_runner
        self.system_which = system_which or shutil.which
        self.is_windows = is_windows
        self.is_macos = is_macos
        self.minimum_executable_size = minimum_executable_size
        self.net_opener = net_opener
        self.ui_callback = ui_callback or (lambda *args: None)
        self.log_callback = log_callback or (lambda *args: None)
        self.make_executable = make_executable or (lambda path: None)
        self.app_name = app_name
        self.app_version = app_version
        self.spotdl_url_builder = spotdl_url_builder
        self.ytdlp_url_builder = ytdlp_url_builder
        self.python_components = python_components or {}
        self.engine_update_root = (Path(engine_update_root)
                                   if engine_update_root is not None else None)
        self.engine_update_registry = (Path(engine_update_registry)
                                       if engine_update_registry is not None else None)
        self.wheel_selector = wheel_selector

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


    def tool_download_urls(self, name, version=None):
        """Return the versioned mirrors already defined by the engine catalog."""
        return self.release_urls(
            name, version, self.tool_specs,
            self.spotdl_url_builder, self.ytdlp_url_builder)

    def latest_version(self, name):
        """Published version for a tool, or None when the check cannot run."""
        api = self.tool_specs[name].get("api")
        if not api or self.net_opener is None:
            return None
        try:
            with self.net_opener() as opener:
                request = urllib.request.Request(api, headers={
                    "User-Agent": f"{self.app_name}/{self.app_version}",
                    "Accept": "application/vnd.github+json",
                })
                with opener.open(request, timeout=20) as response:
                    tag = json.loads(
                        response.read().decode("utf-8", "replace")
                    ).get("tag_name", "")
            return tag.strip().lstrip("vV") or None
        except Exception:
            return None

    def latest_python_engine(self, name):
        """Return the newest allowed PyPI wheel compatible with this runtime."""
        if self.net_opener is None:
            raise RuntimeError("The Python engine updater has no network opener.")
        spec = self.python_components[name]
        url = f"https://pypi.org/pypi/{name}/json"
        with self.net_opener() as opener:
            request = urllib.request.Request(url, headers={
                "User-Agent": f"{self.app_name}/{self.app_version}",
                "Accept": "application/json",
            })
            with opener.open(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        selector = self.wheel_selector
        if selector is None:
            from blueknight.engines.wheels import select_compatible_wheel
            selector = select_compatible_wheel

        versions = []
        for raw_version, files in payload.get("releases", {}).items():
            if not re.fullmatch(r"\d+(?:\.\d+)*", raw_version):
                continue
            version_key = tuple(int(part) for part in raw_version.split("."))
            if version_key[0] >= spec["max_major"]:
                continue
            versions.append((version_key, raw_version, files))
        for _, version, files in sorted(versions, reverse=True):
            wheel = selector(files)
            if wheel:
                return (version, wheel["url"], wheel["digests"]["sha256"],
                        wheel["filename"])
        raise RuntimeError(
            f"PyPI has no wheel compatible with this Python/platform for {spec['label']}.")

    def install_python_engine(self, name, version, url, digest, filename):
        """Download, verify and safely stage one wheel without activating it."""
        if self.engine_update_root is None or self.net_opener is None:
            raise RuntimeError("The Python engine staging service is not configured.")
        update_root = self.engine_update_root
        update_root.mkdir(parents=True, exist_ok=True)
        wheel_path = update_root / (filename + ".part")
        wheel_path.unlink(missing_ok=True)
        try:
            with self.net_opener() as opener:
                request = urllib.request.Request(
                    url, headers={"User-Agent": f"{self.app_name}/{self.app_version}"})
                with opener.open(request, timeout=60) as response, wheel_path.open("wb") as target:
                    shutil.copyfileobj(response, target, length=1024 * 1024)
            actual = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
            if actual.lower() != digest.lower():
                raise RuntimeError("downloaded wheel failed its PyPI SHA-256 check")

            safe_version = re.sub(r"[^0-9A-Za-z_.-]", "_", version)
            target_dir = update_root / f"{name}-{safe_version}-{digest[:12].lower()}"
            if not target_dir.is_dir():
                with tempfile.TemporaryDirectory(dir=update_root) as temp:
                    staging = Path(temp) / "package"
                    staging.mkdir()
                    root = staging.resolve()
                    with zipfile.ZipFile(wheel_path) as wheel:
                        for member in wheel.infolist():
                            destination = (staging / member.filename).resolve()
                            destination.relative_to(root)
                        wheel.extractall(staging)
                    os.replace(staging, target_dir)
            return {"version": version, "path": str(target_dir), "sha256": digest.lower()}
        finally:
            wheel_path.unlink(missing_ok=True)

    def commit_python_engine_updates(self, records):
        """Atomically register a validated group for activation on next launch."""
        if self.engine_update_registry is None:
            raise RuntimeError("The Python engine registry is not configured.")
        registry_path = self.engine_update_registry
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            registry = json.loads(registry_path.read_text("utf-8"))
            if not isinstance(registry, dict):
                registry = {}
        except (OSError, ValueError):
            registry = {}
        registry.update(records)
        pending = registry_path.with_suffix(registry_path.suffix + ".new")
        try:
            pending.write_text(json.dumps(registry, indent=2), encoding="utf-8")
            os.replace(pending, registry_path)
        finally:
            pending.unlink(missing_ok=True)


    def download_with_fallbacks(self, urls, destination, label):
        """Download atomically, trying independent hosts in order."""
        if self.net_opener is None:
            raise RuntimeError("The engine download service has no network opener.")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(destination.suffix + ".part")
        errors = []
        try:
            with self.net_opener() as opener:
                for attempt, url in enumerate(urls, 1):
                    try:
                        partial.unlink(missing_ok=True)
                        host = urlsplit(url).hostname or "download server"
                        self.ui_callback(
                            "setup", f"Downloading {label}...",
                            f"Trying {host} ({attempt}/{len(urls)})")
                        self.log_callback(
                            f"Downloading {label} from {host} "
                            f"({attempt}/{len(urls)})…", "info")
                        request = urllib.request.Request(url, headers={
                            "User-Agent": f"{self.app_name}/{self.app_version}"})
                        with opener.open(request, timeout=45) as response, partial.open("wb") as output:
                            shutil.copyfileobj(response, output, length=1024 * 1024)
                        if partial.stat().st_size == 0:
                            raise RuntimeError("server returned an empty file")
                        os.replace(partial, destination)
                        return destination
                    except Exception as exc:
                        errors.append(f"{urlsplit(url).hostname}: {exc}")
                        self.log_callback(
                            f"{label} source {attempt} failed; trying the next source.",
                            "warning")
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"All {label} download sources failed: " + " | ".join(errors))

    def get_or_download_tool(self, name, force=False, version=None):
        """Download, verify and activate a tool while preserving the old flow."""
        spec = self.tool_specs[name]
        if not force:
            existing = self.find_tool(name)
            if existing:
                return existing

        target = self.tools_dir / spec["exe"]
        candidate = target.with_name(spec["exe"] + ".new")
        archive_path = None
        if spec.get("archive_member"):
            archive_path = target.with_name(spec["exe"] + ".zip.new")
            self.download_with_fallbacks(
                self.tool_download_urls(name, version), archive_path, spec["label"])
            try:
                if spec.get("checksum_urls"):
                    checksum_path = target.with_name(spec["exe"] + ".sha256.new")
                    try:
                        self.download_with_fallbacks(
                            spec["checksum_urls"], checksum_path,
                            f"{spec['label']} checksum")
                        manifest = checksum_path.read_text("ascii", "replace")
                        match = re.search(r"\b([0-9A-Fa-f]{64})\b", manifest)
                        if not match:
                            raise RuntimeError(
                                f"{spec['label']} checksum manifest is invalid.")
                        actual = hashlib.sha256(archive_path.read_bytes()).hexdigest()
                        if actual.lower() != match.group(1).lower():
                            raise RuntimeError(
                                f"{spec['label']} archive failed its SHA-256 check.")
                    finally:
                        checksum_path.unlink(missing_ok=True)
                with zipfile.ZipFile(archive_path) as archive:
                    member = spec["archive_member"]
                    if member not in archive.namelist():
                        raise RuntimeError(
                            f"{spec['label']} archive does not contain {member}.")
                    with archive.open(member) as source, candidate.open("wb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
            finally:
                archive_path.unlink(missing_ok=True)
        else:
            self.download_with_fallbacks(
                self.tool_download_urls(name, version), candidate, spec["label"])

        if not self.is_native_executable(candidate):
            candidate.unlink(missing_ok=True)
            raise RuntimeError(
                f"The downloaded {spec['label']} file is not a valid executable.")
        self.make_executable(candidate)
        candidate_version = self.tool_version(candidate)
        if candidate_version == "unknown":
            candidate.unlink(missing_ok=True)
            raise RuntimeError(
                f"The downloaded {spec['label']} executable did not start.")
        if version and candidate_version.lstrip("vV") != version.lstrip("vV"):
            candidate.unlink(missing_ok=True)
            raise RuntimeError(
                f"The {spec['label']} server returned {candidate_version}, expected {version}.")
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate, target)
        return str(target)


__all__ = ["EngineManager"]
