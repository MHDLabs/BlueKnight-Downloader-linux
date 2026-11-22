"""Release flavor regression tests.

These checks protect the contract between the Linux build script, Windows
builder, frozen-app smoke test and the release workflow.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseFlavorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/downloader.yml").read_text("utf-8")
        cls.linux_build = (ROOT / "build_portable.sh").read_text("utf-8")
        cls.windows_build = (ROOT / "build_portable.ps1").read_text("utf-8")
        cls.app = (ROOT / "spotify_downloader.py").read_text("utf-8")

    def test_ci_builds_all_three_native_artifacts(self):
        self.assertIn("target: linux-x64, flavor: lite", self.workflow)
        self.assertIn("target: linux-x64, flavor: full", self.workflow)
        self.assertIn("target: windows-x64, flavor: full", self.workflow)
        self.assertIn("actions/upload-artifact@v6", self.workflow)
        self.assertIn("BLUEKNIGHT_EXPECT_FLAVOR", self.workflow)

    def test_release_is_explicitly_a_prerelease(self):
        self.assertIn("prerelease: true", self.workflow)
        self.assertIn("make_latest: false", self.workflow)

    def test_linux_lite_does_not_bundle_native_engines_or_full_sidecars(self):
        self.assertIn('--flavor)', self.linux_build)
        self.assertIn('if [ "$FLAVOR" = "full" ]; then', self.linux_build)
        self.assertIn('--add-binary "$VENDOR/spotdl:tools"', self.linux_build)
        self.assertIn('--add-binary "$VENDOR/yt-dlp:tools"', self.linux_build)
        self.assertIn('--add-binary "$VENDOR/deno:tools"', self.linux_build)
        self.assertIn('--add-binary "$VENDOR/ffmpeg:tools"', self.linux_build)
        self.assertIn('BlueKnightDownloader-linux-${ARCH}-${FLAVOR}.tar.gz', self.linux_build)
        self.assertIn('portable.mode release-flavor.txt', self.linux_build)

    def test_windows_is_built_as_the_full_flavor_and_has_a_marker(self):
        self.assertIn('Set-Content -LiteralPath $FlavorMarker -Value "full"', self.windows_build)
        self.assertIn('--add-data "$FlavorMarker;."', self.windows_build)
        self.assertIn('$FlavorMarker,', self.windows_build)
        self.assertIn('BlueKnightDownloader-windows-x64.zip', self.windows_build)

    def test_startup_only_discovers_engines(self):
        start = self.app.index("    def setup_dependencies(self):")
        end = self.app.index("    @contextlib.contextmanager", start)
        setup = self.app[start:end]
        self.assertIn("self.find_ffmpeg()", setup)
        self.assertIn('self.find_tool("spotdl")', setup)
        self.assertIn('self.find_tool("yt-dlp")', setup)
        self.assertNotIn("get_or_download_tool", setup)
        self.assertNotIn("get_or_download_ffmpeg", setup)

    def test_features_own_their_engine_installation(self):
        self.assertIn("def ensure_tool(self, name):", self.app)
        self.assertIn("def ensure_ffmpeg(self):", self.app)
        self.assertIn("def ensure_media_engines(self, kind):", self.app)
        self.assertIn('self.ensure_tool("spotdl")', self.app)
        self.assertIn('self.ensure_tool("yt-dlp")', self.app)
        self.assertIn('self.ensure_tool("deno")', self.app)
        self.assertIn("self.ensure_ffmpeg()", self.app)

    def test_lite_smoke_test_rejects_bundled_native_engines(self):
        self.assertIn('expected_flavor = os.environ.get(', self.app)
        self.assertIn('if expected_flavor == "lite":', self.app)
        self.assertIn('assert not bundled_tool(_spec["exe"])', self.app)
        self.assertIn('assert not bundled_tool(f"ffprobe{EXE}")', self.app)


if __name__ == "__main__":
    unittest.main()
