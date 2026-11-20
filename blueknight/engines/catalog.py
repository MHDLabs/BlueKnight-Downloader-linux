"""Platform-aware manifest and release URLs for bundled downloader engines."""

from __future__ import annotations

from blueknight_paths import ARCH, EXE, OS_TAG


# Every tool publishes one release asset per platform under a name of its own
# choosing. The names are collected here, keyed the same way, so that adding a
# platform is a table entry rather than a branch in the download code.
SPOTDL_VERSION = "4.5.2"
SPOTDL_ASSETS = {"win": "spotdl-{v}-win32.exe", "mac": "spotdl-{v}-darwin",
                 "linux": "spotdl-{v}-linux", "android": None}
YTDLP_VERSION = "2026.07.04"
YTDLP_ASSETS = {"win": "yt-dlp.exe", "mac": "yt-dlp_macos",
                "linux": "yt-dlp_linux_aarch64" if ARCH == "arm64" else "yt-dlp_linux",
                "android": None}
DENO_ASSETS = {
    "win": "deno-x86_64-pc-windows-msvc.zip",
    "mac": f"deno-{'aarch64' if ARCH == 'arm64' else 'x86_64'}-apple-darwin.zip",
    "linux": f"deno-{'aarch64' if ARCH == 'arm64' else 'x86_64'}-unknown-linux-gnu.zip",
    # Deno publishes no Android build. The Android shell answers yt-dlp's
    # JavaScript challenges with the system WebView instead; see js_runtime().
    "android": None,
}


def spotdl_urls(version=SPOTDL_VERSION):
    asset = SPOTDL_ASSETS[OS_TAG]
    if not asset:
        return ()
    asset = asset.format(v=version)
    return (f"https://github.com/spotDL/spotify-downloader/releases/download/"
            f"v{version}/{asset}",
            f"https://sourceforge.net/projects/spotdl.mirror/files/v{version}/"
            f"{asset}/download")


def ytdlp_urls(version=YTDLP_VERSION):
    asset = YTDLP_ASSETS[OS_TAG]
    if not asset:
        return ()
    # Independent hosts, tried in order. SourceForge is the escape hatch for
    # networks that block GitHub release downloads.
    return (f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/{asset}",
            f"https://github.com/yt-dlp/yt-dlp/releases/download/{version}/{asset}",
            f"https://sourceforge.net/projects/yt-dlp.mirror/files/{version}/"
            f"{asset}/download")


def deno_urls():
    asset = DENO_ASSETS[OS_TAG]
    if not asset:
        return ()
    return (f"https://github.com/denoland/deno/releases/latest/download/{asset}",
            f"https://dl.deno.land/release-latest/{asset}")


SPOTDL_DOWNLOAD_URLS = spotdl_urls()
YTDLP_DOWNLOAD_URLS = ytdlp_urls()
DENO_DOWNLOAD_URLS = deno_urls()


def bgutil_urls():
    """The proof-of-origin token generator, per platform.

    YouTube's bot check is answered with a token minted by running BotGuard, an
    obfuscated JavaScript VM, in something browser-shaped. Every client that
    still works does this somehow: NewPipe runs it in a WebView, others pair a
    JavaScript runtime with a DOM. This is the Rust build of that, which carries
    its own engine — one binary, no Node, no Deno, nothing to keep running.

    Android is absent deliberately. The project publishes no Android target, and
    a phone already has the browser-shaped thing these builds go to such lengths
    to imitate; using it is a different piece of work, not a download.
    """
    base = ("https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/"
            "releases/latest/download/")
    names = {
        ("win", "x64"): "bgutil-pot-windows-x86_64.exe",
        ("linux", "x64"): "bgutil-pot-linux-x86_64",
        ("linux", "arm64"): "bgutil-pot-linux-aarch64",
        ("mac", "x64"): "bgutil-pot-macos-x86_64",
        ("mac", "arm64"): "bgutil-pot-macos-aarch64",
    }
    asset = names.get((OS_TAG, ARCH))
    return (base + asset,) if asset else ()


BGUTIL_DOWNLOAD_URLS = bgutil_urls()
# The yt-dlp side is pure Python and tiny; it is what teaches yt-dlp to ask the
# binary for a token at all.
BGUTIL_PLUGIN_URL = ("https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/"
                     "releases/latest/download/bgutil-ytdlp-pot-provider-rs.zip")

# FFmpeg is the one tool with no single project publishing every platform.
# Each entry is (binaries this archive should contain, mirrors to try) — macOS
# needs two archives because evermeet.cx packages ffmpeg and ffprobe apart.
FFMPEG_DOWNLOADS = {
    "win": ((("ffmpeg", "ffprobe"), (
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip")),),
    "linux": ((("ffmpeg", "ffprobe"), (
        f"https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
        f"ffmpeg-master-latest-linux{'arm64' if ARCH == 'arm64' else '64'}-gpl.tar.xz",)),),
    "mac": ((("ffmpeg",), ("https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",)),
            (("ffprobe",), ("https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip",))),
    # Android ships FFmpeg inside the APK as a native library; there is nowhere
    # on the device it is allowed to download and mark executable at runtime.
    "android": (),
}

# Every downloadable tool is described once, so finding, downloading and
# updating are one code path instead of one per tool.
TOOLS = {
    "spotdl": {
        "label": "spotDL", "exe": f"spotdl{EXE}", "urls": SPOTDL_DOWNLOAD_URLS,
        "api": "https://api.github.com/repos/spotDL/spotify-downloader/releases/latest",
    },
    "yt-dlp": {
        "label": "yt-dlp", "exe": f"yt-dlp{EXE}", "urls": YTDLP_DOWNLOAD_URLS,
        "api": "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
        # Android has no release binary and no second Python to spawn, so the
        # importable package stands in and pyshell runs it in this process.
        "module": "yt_dlp",
    },
    "deno": {
        "label": "Deno", "exe": f"deno{EXE}", "urls": DENO_DOWNLOAD_URLS,
        "api": "https://api.github.com/repos/denoland/deno/releases/latest",
        "checksum_urls": tuple(url + ".sha256sum" for url in DENO_DOWNLOAD_URLS),
        "archive_member": f"deno{EXE}",
    },
    "bgutil": {
        # Fetched only when the ladder has run out, never at setup: it is ~45 MB
        # and most downloads never need it.
        "label": "PO token provider", "exe": f"bgutil-pot{EXE}",
        "urls": BGUTIL_DOWNLOAD_URLS, "optional": True,
        "api": ("https://api.github.com/repos/jim60105/"
                "bgutil-ytdlp-pot-provider-rs/releases/latest"),
        # The release asset is the bare executable — nothing to unpack, and the
        # project publishes no checksum files to verify it against.
    },
}
# A platform with neither a release asset nor an importable package has no tool
# to find, download or update, and every check for one would only ever fail.
TOOLS = {name: spec for name, spec in TOOLS.items()
         if spec["urls"] or spec.get("module")}
