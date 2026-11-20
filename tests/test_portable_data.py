"""Safe, copy-only migration tests for portable application data."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import blueknight_paths


class PortableDataMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.home = self.root / "application"
        self.xdg = self.root / "legacy-xdg"
        self.home.mkdir()
        self.env = patch.dict(os.environ, {
            "BLUEKNIGHT_HOME": str(self.home),
            "XDG_DATA_HOME": str(self.xdg),
        })
        self.env.start()
        os.environ.pop("BLUEKNIGHT_DATA", None)
        self.platform_patches = [
            patch("blueknight_paths.IS_WINDOWS", False),
            patch("blueknight_paths.IS_MACOS", False),
        ]
        for item in self.platform_patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.platform_patches):
            item.stop()
        self.env.stop()
        self.temporary.cleanup()

    def legacy_root(self, name="TestDownloader"):
        return self.xdg / name

    def portable_root(self, name="TestDownloader"):
        return self.home / "data" / name

    def enable_portable(self):
        (self.home / "portable.mode").touch()

    def test_copies_only_managed_folders_and_rebases_engine_registry(self):
        name = "TestDownloader"
        legacy = self.legacy_root(name)
        engine_dir = legacy / "python-engines" / "gallery-dl-1.0"
        (legacy / "tools").mkdir(parents=True)
        (legacy / "tools" / "yt-dlp").write_text("old yt-dlp", encoding="utf-8")
        (legacy / "ffmpeg" / "bin").mkdir(parents=True)
        (legacy / "ffmpeg" / "bin" / "ffmpeg").write_text("old ffmpeg", encoding="utf-8")
        (legacy / "plugins" / "yt_dlp_plugins" / "extractor").mkdir(parents=True)
        (legacy / "plugins" / "yt_dlp_plugins" / "extractor" / "plugin.py").write_text("plugin", encoding="utf-8")
        engine_dir.mkdir(parents=True)
        (engine_dir / "__init__.py").write_text("engine", encoding="utf-8")
        old_registry = {"gallery-dl": {"version": "1.0", "path": str(engine_dir)}}
        (legacy / "python-engines" / "registry.json").write_text(json.dumps(old_registry), encoding="utf-8")

        # These locations are deliberately outside the migration allow-list.
        (legacy / "cookies").mkdir()
        (legacy / "cookies" / "secret.txt").write_text("cookie", encoding="utf-8")
        (legacy / "downloads").mkdir()
        (legacy / "downloads" / "video.mp4").write_text("download", encoding="utf-8")
        (legacy / "unknown").mkdir()
        (legacy / "unknown" / "state.bin").write_text("unknown", encoding="utf-8")
        (self.home / "cookies" / "youtube").mkdir(parents=True)
        (self.home / "cookies" / "youtube" / "cookies.txt").write_text("session", encoding="utf-8")
        (self.home / "BlueKnightdownloader" / "YouTube").mkdir(parents=True)
        (self.home / "BlueKnightdownloader" / "YouTube" / "video.mp4").write_text("download", encoding="utf-8")

        self.enable_portable()
        result = blueknight_paths.app_data_dir(name)
        target = self.portable_root(name)

        self.assertEqual(result, target)
        self.assertEqual((target / "tools" / "yt-dlp").read_text(encoding="utf-8"), "old yt-dlp")
        self.assertEqual((target / "ffmpeg" / "bin" / "ffmpeg").read_text(encoding="utf-8"), "old ffmpeg")
        self.assertEqual((target / "plugins" / "yt_dlp_plugins" / "extractor" / "plugin.py").read_text(encoding="utf-8"), "plugin")
        copied_engine = target / "python-engines" / "gallery-dl-1.0"
        self.assertTrue((copied_engine / "__init__.py").is_file())
        migrated_registry = json.loads((target / "python-engines" / "registry.json").read_text(encoding="utf-8"))
        self.assertEqual(migrated_registry["gallery-dl"]["path"], str(copied_engine.resolve()))
        self.assertEqual(json.loads((legacy / "python-engines" / "registry.json").read_text(encoding="utf-8")), old_registry)

        self.assertFalse((target / "cookies").exists())
        self.assertFalse((target / "downloads").exists())
        self.assertFalse((target / "unknown").exists())
        self.assertTrue((self.home / "cookies" / "youtube" / "cookies.txt").is_file())
        self.assertTrue((self.home / "BlueKnightdownloader" / "YouTube" / "video.mp4").is_file())
        self.assertTrue((target / blueknight_paths._PORTABLE_MIGRATION_MARKER).is_file())

    def test_existing_portable_files_win_and_migration_is_one_time(self):
        name = "TestDownloader"
        legacy = self.legacy_root(name)
        (legacy / "tools").mkdir(parents=True)
        (legacy / "tools" / "yt-dlp").write_text("legacy", encoding="utf-8")
        (legacy / "tools" / "spotdl").write_text("new tool", encoding="utf-8")
        target = self.portable_root(name)
        (target / "tools").mkdir(parents=True)
        (target / "tools" / "yt-dlp").write_text("portable custom", encoding="utf-8")

        self.enable_portable()
        blueknight_paths.app_data_dir(name)
        self.assertEqual((target / "tools" / "yt-dlp").read_text(encoding="utf-8"), "portable custom")
        self.assertEqual((target / "tools" / "spotdl").read_text(encoding="utf-8"), "new tool")

        (legacy / "tools" / "spotdl").write_text("legacy changed later", encoding="utf-8")
        blueknight_paths.app_data_dir(name)
        self.assertEqual((target / "tools" / "spotdl").read_text(encoding="utf-8"), "new tool")

    def test_transient_files_and_symlinks_are_not_copied(self):
        name = "TestDownloader"
        legacy = self.legacy_root(name)
        (legacy / "tools").mkdir(parents=True)
        for suffix in (".part", ".new", ".tmp", ".lock"):
            (legacy / "tools" / ("download" + suffix)).write_text("temporary", encoding="utf-8")
        (legacy / "tools" / "stable.bin").write_text("stable", encoding="utf-8")
        outside = self.root / "outside-secret.txt"
        outside.write_text("outside", encoding="utf-8")
        try:
            (legacy / "tools" / "linked-secret.txt").symlink_to(outside)
        except (OSError, NotImplementedError):
            pass

        self.enable_portable()
        target = blueknight_paths.app_data_dir(name)
        self.assertTrue((target / "tools" / "stable.bin").is_file())
        for suffix in (".part", ".new", ".tmp", ".lock"):
            self.assertFalse((target / "tools" / ("download" + suffix)).exists())
        self.assertFalse((target / "tools" / "linked-secret.txt").exists())
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside")

    def test_interrupted_migration_retries_without_overwriting_the_blocker(self):
        name = "TestDownloader"
        legacy = self.legacy_root(name)
        (legacy / "tools").mkdir(parents=True)
        (legacy / "tools" / "yt-dlp").write_text("legacy", encoding="utf-8")
        target = self.portable_root(name)
        target.mkdir(parents=True)
        (target / "tools").write_text("user file", encoding="utf-8")

        self.enable_portable()
        blueknight_paths.app_data_dir(name)
        self.assertFalse((target / blueknight_paths._PORTABLE_MIGRATION_MARKER).exists())
        self.assertEqual((target / "tools").read_text(encoding="utf-8"), "user file")

        (target / "tools").unlink()
        blueknight_paths.app_data_dir(name)
        self.assertEqual((target / "tools" / "yt-dlp").read_text(encoding="utf-8"), "legacy")
        self.assertTrue((target / blueknight_paths._PORTABLE_MIGRATION_MARKER).is_file())

    def test_without_marker_keeps_using_per_user_data(self):
        legacy = self.legacy_root()
        legacy.mkdir(parents=True)
        result = blueknight_paths.app_data_dir()
        self.assertEqual(result, legacy)
        self.assertFalse(self.portable_root().exists())

    def test_explicit_data_override_takes_precedence_and_skips_migration(self):
        name = "TestDownloader"
        legacy = self.legacy_root(name)
        (legacy / "tools").mkdir(parents=True)
        (legacy / "tools" / "yt-dlp").write_text("legacy", encoding="utf-8")
        self.enable_portable()
        override = self.root / "custom-data"
        with patch.dict(os.environ, {"BLUEKNIGHT_DATA": str(override)}):
            self.assertEqual(blueknight_paths.app_data_dir(name), override)
        self.assertFalse(self.portable_root(name).exists())
        self.assertTrue((legacy / "tools" / "yt-dlp").is_file())

    def test_no_managed_legacy_folders_does_not_create_portable_data(self):
        self.enable_portable()
        result = blueknight_paths.app_data_dir("EmptyDownloader")
        self.assertEqual(result, self.portable_root("EmptyDownloader"))
        self.assertFalse(result.exists())


if __name__ == "__main__":
    unittest.main()
