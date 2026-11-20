"""Safe, platform-aware installation of the FFmpeg/ffprobe binary pair."""

from __future__ import annotations

import contextlib
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path


def extract_binaries(archive_path, wanted):
    """Extract only named executables from a ZIP or TAR distribution archive."""
    archive_path = Path(archive_path)
    targets = {name.lower(): Path(target) for name, target in wanted.items()}
    found = set()

    def base(member):
        return Path(member.replace("\\", "/")).name.lower()

    def claim(member, opener):
        stem, suffix = os.path.splitext(base(member))
        if suffix not in ("", ".exe"):
            return
        target = targets.get(stem)
        if target is None or stem in found:
            return
        with opener() as source, target.open("wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
        found.add(stem)

    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.namelist():
                claim(member, lambda m=member: archive.open(m))
    else:
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                if member.isfile():
                    claim(member.name,
                          lambda m=member: contextlib.closing(archive.extractfile(m)))

    missing = sorted(set(targets) - found)
    if missing:
        raise RuntimeError(f"{archive_path.name} is missing {', '.join(missing)}")


class FFmpegInstaller:
    """Stage and launch-check both FFmpeg programs before swapping either one."""

    def __init__(
            self, archives, app_data_dir, ffmpeg_dir, ffmpeg_exe, *,
            executable_suffix="", download_with_fallbacks, ui_callback,
            make_executable, is_native_executable, tool_version):
        self.archives = tuple(archives or ())
        self.app_data_dir = Path(app_data_dir)
        self.ffmpeg_dir = Path(ffmpeg_dir)
        self.ffmpeg_exe = Path(ffmpeg_exe)
        self.executable_suffix = executable_suffix
        self.download_with_fallbacks = download_with_fallbacks
        self.ui_callback = ui_callback or (lambda *args: None)
        self.make_executable = make_executable or (lambda path: None)
        self.is_native_executable = is_native_executable
        self.tool_version = tool_version

    def _activate_pair(self, stage):
        targets = {
            "ffprobe": self.ffmpeg_exe.with_name(f"ffprobe{self.executable_suffix}"),
            "ffmpeg": self.ffmpeg_exe,
        }
        sources = {
            name: Path(stage) / f"{name}{self.executable_suffix}"
            for name in targets
        }
        backup_dir = Path(tempfile.mkdtemp(
            prefix=".ffmpeg-rollback-", dir=self.ffmpeg_exe.parent))
        backups = {}
        replaced = []
        preserve_backups = False
        try:
            # Snapshot every current binary before changing either target.
            for name, target in targets.items():
                backup = backup_dir / target.name
                if target.is_file():
                    shutil.copy2(target, backup)
                    backups[name] = backup
                else:
                    backups[name] = None

            try:
                for name in ("ffprobe", "ffmpeg"):
                    os.replace(sources[name], targets[name])
                    replaced.append(name)
            except Exception as activation_error:
                rollback_errors = []
                for name in reversed(replaced):
                    target = targets[name]
                    backup = backups[name]
                    try:
                        if backup is None:
                            target.unlink(missing_ok=True)
                        else:
                            os.replace(backup, target)
                    except Exception as rollback_error:
                        rollback_errors.append(f"{target.name}: {rollback_error}")
                if rollback_errors:
                    preserve_backups = True
                    raise RuntimeError(
                        "FFmpeg activation failed and rollback was incomplete; "
                        f"recovery copies were kept at {backup_dir}: "
                        + "; ".join(rollback_errors)) from activation_error
                raise
        finally:
            if not preserve_backups:
                shutil.rmtree(backup_dir, ignore_errors=True)

    def install(self):
        """Download all platform archives, validate both binaries, then activate."""
        if not self.archives:
            raise RuntimeError(
                "FFmpeg is not downloadable on this platform and none is bundled.")

        archive_path = self.app_data_dir / "ffmpeg.archive.new"
        try:
            self.app_data_dir.mkdir(parents=True, exist_ok=True)
            self.ffmpeg_dir.mkdir(parents=True, exist_ok=True)
            self.ffmpeg_exe.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.ffmpeg_dir) as temp:
                stage = Path(temp)
                # macOS uses separate archives; Windows and Linux provide both
                # programs in one archive. The manifest handles either layout.
                for wanted, urls in self.archives:
                    archive_path.unlink(missing_ok=True)
                    self.download_with_fallbacks(urls, archive_path, "FFmpeg")
                    self.ui_callback(
                        "setup", "Extracting FFmpeg...", "Setting up audio converter")
                    extract_binaries(
                        archive_path,
                        {name: stage / f"{name}{self.executable_suffix}"
                         for name in wanted},
                    )

                # Neither half is activated unless both have a valid signature
                # and can launch successfully.
                for name in ("ffmpeg", "ffprobe"):
                    candidate = stage / f"{name}{self.executable_suffix}"
                    self.make_executable(candidate)
                    if (not self.is_native_executable(candidate)
                            or self.tool_version(candidate) == "unknown"):
                        raise RuntimeError(
                            f"The downloaded {candidate.name} did not pass its launch check")

                self._activate_pair(stage)
            return str(self.ffmpeg_exe)
        except Exception as exc:
            raise RuntimeError(f"FFmpeg setup failed: {exc}") from exc
        finally:
            archive_path.unlink(missing_ok=True)
