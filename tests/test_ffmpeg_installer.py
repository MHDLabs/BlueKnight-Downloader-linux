"""Deterministic tests for FFmpeg pair extraction and installation."""

from __future__ import annotations

import io
import os
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from blueknight.engines.ffmpeg import FFmpegInstaller, extract_binaries


def zip_archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class FFmpegInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app_data = self.root / "data"
        self.ffmpeg_dir = self.app_data / "ffmpeg"
        self.bin_dir = self.ffmpeg_dir / "bin"
        self.ffmpeg = self.bin_dir / "ffmpeg"
        self.ffprobe = self.bin_dir / "ffprobe"
        self.binary = b"\x7fELF" + b"\x00" * 64

    def tearDown(self):
        self.temp.cleanup()

    def installer(self, payloads, *, archives=None, version_by_name=None):
        downloads, ui, chmod = [], [], []
        version_by_name = version_by_name or {"ffmpeg": "7.1.0", "ffprobe": "7.1.0"}

        def download(urls, destination, label):
            downloads.append((tuple(urls), label))
            Path(destination).write_bytes(payloads[urls[0]])
            return Path(destination)

        def version(path):
            return version_by_name.get(Path(path).name.removesuffix(".exe"), "unknown")

        service = FFmpegInstaller(
            archives=archives or ((("ffmpeg", "ffprobe"), ("https://example.invalid/pair.zip",)),),
            app_data_dir=self.app_data, ffmpeg_dir=self.ffmpeg_dir,
            ffmpeg_exe=self.ffmpeg, download_with_fallbacks=download,
            ui_callback=lambda *args: ui.append(args),
            make_executable=lambda path: chmod.append(Path(path)),
            is_native_executable=lambda path: Path(path).read_bytes().startswith(b"\x7fELF"),
            tool_version=version,
        )
        return service, downloads, ui, chmod

    def test_extract_binaries_reads_zip_members_and_ignores_documentation(self):
        archive = self.root / "bundle.zip"
        archive.write_bytes(zip_archive({
            "docs/ffmpeg.html": b"html",
            "bin/ffmpeg": self.binary,
            "bin/ffprobe": self.binary + b"probe",
        }))
        out = self.root / "out"
        out.mkdir()
        extract_binaries(archive, {"ffmpeg": out / "ffmpeg", "ffprobe": out / "ffprobe"})
        self.assertEqual((out / "ffmpeg").read_bytes(), self.binary)
        self.assertEqual((out / "ffprobe").read_bytes(), self.binary + b"probe")

    def test_extract_binaries_supports_tar_archives(self):
        archive_path = self.root / "bundle.tar.xz"
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w:xz") as archive:
            for name, body in (("bundle/bin/ffmpeg", self.binary),
                               ("bundle/bin/ffprobe", self.binary + b"p")):
                info = tarfile.TarInfo(name)
                info.size = len(body)
                archive.addfile(info, io.BytesIO(body))
        archive_path.write_bytes(payload.getvalue())
        out = self.root / "out"
        out.mkdir()
        extract_binaries(archive_path, {"ffmpeg": out / "ffmpeg", "ffprobe": out / "ffprobe"})
        self.assertEqual((out / "ffmpeg").read_bytes(), self.binary)
        self.assertEqual((out / "ffprobe").read_bytes(), self.binary + b"p")

    def test_install_validates_and_activates_both_binaries(self):
        payload = zip_archive({"bin/ffmpeg": self.binary, "bin/ffprobe": self.binary + b"p"})
        service, downloads, ui, chmod = self.installer(
            {"https://example.invalid/pair.zip": payload})
        result = service.install()
        self.assertEqual(result, str(self.ffmpeg))
        self.assertEqual(self.ffmpeg.read_bytes(), self.binary)
        self.assertEqual(self.ffprobe.read_bytes(), self.binary + b"p")
        self.assertEqual(len(downloads), 1)
        self.assertEqual(len(ui), 1)
        self.assertEqual({path.name for path in chmod}, {"ffmpeg", "ffprobe"})
        self.assertFalse((self.app_data / "ffmpeg.archive.new").exists())
        self.assertEqual(list(self.ffmpeg_dir.glob(".ffmpeg-rollback-*")), [])

    def test_split_archives_keep_macos_ffmpeg_pair_flow(self):
        ffmpeg_url = "https://example.invalid/ffmpeg.zip"
        ffprobe_url = "https://example.invalid/ffprobe.zip"
        payloads = {
            ffmpeg_url: zip_archive({"ffmpeg": self.binary}),
            ffprobe_url: zip_archive({"ffprobe": self.binary + b"p"}),
        }
        archives = ((("ffmpeg",), (ffmpeg_url,)), (("ffprobe",), (ffprobe_url,)))
        service, downloads, _, _ = self.installer(payloads, archives=archives)
        service.install()
        self.assertEqual([urls[0] for urls, _ in downloads], [ffmpeg_url, ffprobe_url])
        self.assertEqual(self.ffmpeg.read_bytes(), self.binary)
        self.assertEqual(self.ffprobe.read_bytes(), self.binary + b"p")

    def test_missing_binary_never_replaces_existing_pair(self):
        self.bin_dir.mkdir(parents=True)
        self.ffmpeg.write_bytes(b"old-ffmpeg")
        self.ffprobe.write_bytes(b"old-ffprobe")
        payload = zip_archive({"ffmpeg": self.binary})
        service, _, _, _ = self.installer({"https://example.invalid/pair.zip": payload})
        with self.assertRaisesRegex(RuntimeError, "missing ffprobe"):
            service.install()
        self.assertEqual(self.ffmpeg.read_bytes(), b"old-ffmpeg")
        self.assertEqual(self.ffprobe.read_bytes(), b"old-ffprobe")

    def test_failed_launch_validation_preserves_existing_pair(self):
        self.bin_dir.mkdir(parents=True)
        self.ffmpeg.write_bytes(b"old-ffmpeg")
        self.ffprobe.write_bytes(b"old-ffprobe")
        payload = zip_archive({"ffmpeg": self.binary, "ffprobe": self.binary + b"p"})
        service, _, _, _ = self.installer(
            {"https://example.invalid/pair.zip": payload},
            version_by_name={"ffmpeg": "7.1.0", "ffprobe": "unknown"})
        with self.assertRaisesRegex(RuntimeError, "did not pass its launch check"):
            service.install()
        self.assertEqual(self.ffmpeg.read_bytes(), b"old-ffmpeg")
        self.assertEqual(self.ffprobe.read_bytes(), b"old-ffprobe")

    def test_second_replace_failure_rolls_back_the_first_binary(self):
        self.bin_dir.mkdir(parents=True)
        self.ffmpeg.write_bytes(b"old-ffmpeg")
        self.ffprobe.write_bytes(b"old-ffprobe")
        payload = zip_archive({"ffmpeg": self.binary, "ffprobe": self.binary + b"p"})
        service, _, _, _ = self.installer({"https://example.invalid/pair.zip": payload})
        real_replace = os.replace

        def fail_ffmpeg_source(source, target):
            if Path(source).name == "ffmpeg":
                raise OSError("simulated ffmpeg activation failure")
            return real_replace(source, target)

        with mock.patch("blueknight.engines.ffmpeg.os.replace", side_effect=fail_ffmpeg_source):
            with self.assertRaisesRegex(RuntimeError, "simulated ffmpeg activation failure"):
                service.install()
        self.assertEqual(self.ffmpeg.read_bytes(), b"old-ffmpeg")
        self.assertEqual(self.ffprobe.read_bytes(), b"old-ffprobe")
        self.assertEqual(list(self.ffmpeg_dir.glob(".ffmpeg-rollback-*")), [])

    def test_activation_failure_removes_new_probe_when_no_previous_pair_exists(self):
        payload = zip_archive({"ffmpeg": self.binary, "ffprobe": self.binary + b"p"})
        service, _, _, _ = self.installer({"https://example.invalid/pair.zip": payload})
        real_replace = os.replace

        def fail_ffmpeg_source(source, target):
            if Path(source).name == "ffmpeg":
                raise OSError("simulated activation failure")
            return real_replace(source, target)

        with mock.patch("blueknight.engines.ffmpeg.os.replace", side_effect=fail_ffmpeg_source):
            with self.assertRaisesRegex(RuntimeError, "simulated activation failure"):
                service.install()
        self.assertFalse(self.ffmpeg.exists())
        self.assertFalse(self.ffprobe.exists())


if __name__ == "__main__":
    unittest.main()
