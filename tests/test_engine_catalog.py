"""Tests for the platform-aware external engine catalog."""

from __future__ import annotations

import unittest

from blueknight.engines.catalog import (
    BGUTIL_DOWNLOAD_URLS, BGUTIL_PLUGIN_URL, DENO_DOWNLOAD_URLS,
    FFMPEG_DOWNLOADS, SPOTDL_ASSETS, SPOTDL_DOWNLOAD_URLS, SPOTDL_VERSION,
    TOOLS, YTDLP_ASSETS, YTDLP_DOWNLOAD_URLS, YTDLP_VERSION,
    bgutil_urls, deno_urls, spotdl_urls, ytdlp_urls,
)
from blueknight_paths import EXE, OS_TAG


class EngineCatalogTests(unittest.TestCase):
    def test_primary_engines_remain_in_the_catalog(self):
        self.assertTrue({"spotdl", "yt-dlp", "deno"} <= set(TOOLS))
        for name in ("spotdl", "yt-dlp", "deno"):
            with self.subTest(engine=name):
                self.assertTrue(TOOLS[name]["urls"])
                self.assertTrue(TOOLS[name]["label"])
                self.assertTrue(TOOLS[name]["exe"].endswith(EXE))

    def test_optional_po_token_engine_is_preserved(self):
        urls = bgutil_urls()
        self.assertEqual(urls, BGUTIL_DOWNLOAD_URLS)
        self.assertIn("bgutil-ytdlp-pot-provider-rs.zip", BGUTIL_PLUGIN_URL)
        if urls:
            self.assertIn("bgutil", TOOLS)
            self.assertTrue(TOOLS["bgutil"].get("optional"))
            self.assertEqual(TOOLS["bgutil"]["urls"], urls)

    def test_spotdl_versioned_urls_keep_the_platform_asset(self):
        asset = SPOTDL_ASSETS[OS_TAG]
        urls = spotdl_urls("9.9.9")
        if asset:
            expected = asset.format(v="9.9.9")
            self.assertEqual(len(urls), 2)
            self.assertTrue(all(expected in url for url in urls))
            self.assertIn("/v9.9.9/", urls[0])
        else:
            self.assertEqual(urls, ())
        self.assertEqual(SPOTDL_DOWNLOAD_URLS, spotdl_urls())

    def test_ytdlp_keeps_latest_and_versioned_mirrors(self):
        asset = YTDLP_ASSETS[OS_TAG]
        urls = ytdlp_urls("2026.07.04")
        if asset:
            self.assertEqual(len(urls), 3)
            self.assertIn(asset, urls[0])
            self.assertIn("/2026.07.04/", urls[1])
            self.assertIn(asset, urls[2])
        else:
            self.assertEqual(urls, ())
        self.assertEqual(YTDLP_DOWNLOAD_URLS, ytdlp_urls())
        self.assertEqual(YTDLP_VERSION, "2026.07.04")

    def test_deno_urls_are_platform_specific(self):
        self.assertEqual(deno_urls(), DENO_DOWNLOAD_URLS)
        if OS_TAG in {"win", "linux", "mac"}:
            self.assertTrue(DENO_DOWNLOAD_URLS)
            self.assertTrue(all("deno" in url for url in DENO_DOWNLOAD_URLS))

    def test_ffmpeg_manifest_contains_ffmpeg_and_ffprobe(self):
        archives = FFMPEG_DOWNLOADS[OS_TAG]
        if OS_TAG == "android":
            self.assertEqual(archives, ())
        else:
            names = {name for binaries, _urls in archives for name in binaries}
            self.assertTrue({"ffmpeg", "ffprobe"} <= names)
            self.assertTrue(all(urls for _binaries, urls in archives))

    def test_versions_are_explicit(self):
        self.assertEqual(SPOTDL_VERSION, "4.5.2")
        self.assertEqual(YTDLP_VERSION, "2026.07.04")


if __name__ == "__main__":
    unittest.main()
