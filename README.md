# Blue Knight Downloader

A portable desktop downloader for Linux and Windows, built around a local
WebView interface and a shared Python engine.

Official releases provide Linux Lite, Linux Full and Windows Full packages.
The Lite package keeps large native engines out of the initial download and
installs them only when a selected feature needs them.

[Live demo (simulated)](https://mhdlabs.github.io/BlueKnight-Downloader-linux/) ·
[Releases](https://github.com/MHDLabs/BlueKnight-Downloader-linux/releases) ·
[Issues](https://github.com/MHDLabs/BlueKnight-Downloader-linux/issues) ·
[Development guide](DEVELOPING.md) ·
[Architecture](docs/architecture.md)

---

## What it supports

| Workspace | Supported content |
| --- | --- |
| Spotify | Tracks, albums and playlists |
| YouTube | Videos, Shorts, playlists and audio |
| YouTube Music | Songs, albums and playlists |
| TikTok | Videos, supported posts, profiles and hashtag pages |
| Instagram | Reels, posts, profiles and supported media |
| SoundCloud | Tracks, sets and profiles, including account-entitled streams |
| X | Videos, photos, GIFs and multi-image posts |
| Video | Public video pages and direct media links supported by the available extractors |
| Documents & Ebooks | PDF, EPUB, MOBI, AZW/AZW3, FB2, Office, OpenDocument, DjVu, CHM, RTF, text and CBZ |
| Manga / manhwa | Public or account-authorized chapter pages, saved as PDF or CBZ |

Availability depends on the source, account permissions, region and changes made
by third-party services. The app does not bypass DRM, subscriptions, paywalls or
access controls.

## Download engines

Blue Knight keeps multiple engines because no single extractor handles every
kind of media:

- **yt-dlp** handles video and audio on supported sites.
- **spotDL** resolves Spotify metadata and matches available audio.
- **NewPipeExtractor** is a desktop JVM fallback for supported sources such as
  YouTube, YouTube Music and SoundCloud.
- **Streamlink** handles supported live and HLS streams.
- **gallery-dl** resolves photos, GIFs, galleries and mixed posts.
- **Deno** runs yt-dlp's JavaScript challenge components.
- **FFmpeg** handles media conversion and audio/video processing.
- **YoutubeExplode** is retained as an additional YouTube helper.
- Built-in document and image resolvers cover supported files and pages.

Fallbacks are selected according to the kind of failure. A DRM or permission
failure is not treated as a reason to try to bypass the restriction.

## Main features

### Downloads and fallback handling

The application preserves source-specific download workflows, progress
reporting, item limits for supported collections, and separate output folders.
It can refresh expired YouTube media URLs and retry supported extractor clients
before reporting that sign-in or another action is required.

### Sign-in and cookies

Sign-in is available inside the app for supported services. The application
keeps cookie sessions separated by site and checks that exported cookie files
belong to the requested domain before using them. It can also read supported
browser profiles when the browser's cookie database is accessible.

Cookie files and active sessions are sensitive. Do not share an application
folder that contains a signed-in session.

### Proxy support

HTTP and SOCKS5 proxies are supported, including common local clients such as
v2rayN and Clash. The app includes proxy presets, manual configuration and a
connection test. A local bridge allows HTTP-only tools such as spotDL to use a
SOCKS5 connection.

### Conversion

The local converter supports common audio and video formats including MP3,
FLAC, WAV, M4A, OGG, AAC, MP4, MKV, WebM, MOV and AVI. FFmpeg performs the
transcode.

The document tools can create PDFs from images, build CBZ archives and handle
supported document conversions. LibreOffice and Calibre are detected when
installed for workflows that need them.

---

## Installation

### Linux

1. Open the repository's [Releases](https://github.com/MHDLabs/BlueKnight-Downloader-linux/releases).
2. Choose one of the Linux x64 archives:
   - **Lite:** `BlueKnightDownloader-linux-x64-lite.tar.gz` — smaller initial download; native tools are fetched as needed.
   - **Full:** `BlueKnightDownloader-linux-x64-full.tar.gz` — native tools and desktop fallbacks are included.
3. Extract the complete archive into a writable directory.
4. Install WebKitGTK 4.1 and the required GTK runtime libraries.
5. Run `./BlueKnightDownloader` from the extracted directory.

Lite and Full share the same main application and download workflows.
Lite excludes the optional .NET and JVM fallback helpers, so a few sources may
have fewer fallback routes when the primary extractor cannot handle them. Lite
stores downloaded native engines under the app's portable data directory and
never installs them globally or asks for administrator privileges. If a feature
needs a missing engine, the app downloads it at that point. Full is preferable
for offline setup and maximum fallback coverage.

Neither Linux package bundles the complete WebKitGTK browser runtime.
WebKitGTK 4.1 must be provided by the host distribution.

Package dependencies on common distributions:

- Arch Linux: `sudo pacman -S webkit2gtk-4.1 gtk3`
- Debian/Ubuntu: install the WebKitGTK 4.1 runtime and GTK libraries from the distribution repositories.
- Fedora: install the WebKitGTK 4.1 and GTK runtime packages from the distribution repositories.

Package names may vary by distribution release.

### Windows

Download `BlueKnightDownloader-windows-x64.zip` from Releases. It is the Full
package and includes the native engines and available desktop fallback helpers.
Extract the archive and run `BlueKnightDownloader.exe`. Microsoft Edge
WebView2 Runtime must be available on the system.

---

## Portable data and file locations

Official desktop archives include a `portable.mode` marker beside the
executable. While it is present:

- Updateable tools and application-managed runtime data are stored under
  `data/SpotifyDownloader/` beside the application.
- Downloads are stored in the `BlueKnightdownloader/` folder beside the app,
  separated by source.
- Cookie sessions and exported cookie files use their own app-side locations.

Keep the marker beside the executable and extract the archive into a writable
folder. A writable USB drive can be used. Removing the marker changes future
application data to the normal per-user location; it does not delete the
existing `data/` directory.

The optional `BLUEKNIGHT_DATA` environment variable overrides the application
data location.

---

## System requirements

### Linux

- 64-bit Linux with a compatible glibc runtime.
- WebKitGTK 4.1 and the required GTK runtime libraries.
- A writable application directory when using portable mode.
- Internet access for metadata, updates and online downloads.

### Windows

- Windows 10 or Windows 11, 64-bit.
- Microsoft Edge WebView2 Runtime for embedded web content and sign-in.
- A writable application directory when using portable mode.
- Internet access for metadata, updates and online downloads.

Some conversion features use optional system applications such as LibreOffice
or Calibre. They are detected when installed; they are not silently substituted
with a DRM or access-control bypass.

---

## Building from source

The repository contains the desktop engine, UI assets, helper projects and
packaging scripts.

Linux Lite:

~~~bash
python3 -m pip install -r requirements.txt
bash ./build_portable.sh --flavor lite
~~~

Linux Full:

~~~bash
python3 -m pip install -r requirements.txt
bash ./build_portable.sh --flavor full
~~~

Windows:

~~~powershell
python -m pip install -r requirements.txt
.\build_portable.ps1
~~~

The Linux build requires WebKitGTK 4.1 development libraries. The NewPipe and
YoutubeExplode helpers use Java 17 and .NET 8 respectively; install those SDKs
when building a package that should include both helpers.

The build scripts place distributable packages under `release/`:

- `BlueKnightDownloader-linux-x64-lite.tar.gz`
- `BlueKnightDownloader-linux-x64-full.tar.gz`
- `BlueKnightDownloader-windows-x64.zip`

CI builds and smoke-tests all three packages on their native operating-system
runners. Release tags publish these artifacts as a GitHub Pre-release.

### Tests

Run the deterministic Python tests:

~~~bash
python -m pip install "packaging>=24"
python -m unittest discover -s tests -p "test_*.py" -v
~~~

Run the WebView and bridge checks:

~~~bash
python tests/check_web_assets.py
node tests/check_web_scripts.mjs
python tests/check_bridge_contract.py
~~~

These checks do not replace a visual test of the actual desktop window on the
target Linux or Windows system.

---

## Repository layout

| Path | Purpose |
| --- | --- |
| `spotify_downloader.py` | Desktop engine, download workflows and Python-to-WebView API |
| `blueknight_paths.py` | Application paths, output folders and cookie discovery |
| `blueknight/engines/` | Platform catalog, wheel compatibility and tool discovery/validation |
| `blueknight/network/` | Proxy configuration and SOCKS5 bridge |
| `web/` | Local HTML, CSS and ordered JavaScript interface assets |
| `contracts/` | Versioned desktop bridge contract |
| `tests/` | Deterministic regression and frontend checks |
| `jvm/` | NewPipe desktop helper |
| `dotnet/` | YoutubeExplode desktop helper |

For implementation details and module boundaries, see
[DEVELOPING.md](DEVELOPING.md) and [docs/architecture.md](docs/architecture.md).

## Third-party components

This project uses third-party software including yt-dlp, spotDL, FFmpeg, Deno,
gallery-dl, Streamlink, NewPipeExtractor, YoutubeExplode and Python libraries.
Their respective licenses and source links are listed in
[THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt).

## License

The Blue Knight Downloader project is licensed under
**GNU GPL-3.0-only**. See [LICENSE](LICENSE). Third-party components retain
their own licenses.

Download only content that you own or have permission to download. Follow the
laws and platform terms that apply to you.

## Community

Telegram: [@BlueKnight_Net](https://t.me/BlueKnight_Net)

Report bugs and request features through the repository
[Issues](https://github.com/MHDLabs/BlueKnight-Downloader-linux/issues) page.
Include your operating system, app version, source and relevant error output.
