# Blue Knight Downloader

A desktop app for downloading from **Spotify, YouTube, YouTube Music,
TikTok, Instagram, SoundCloud, X, PDF/ebook documents, and other
yt-dlp-supported video sites**, sorting what it fetches, and handling restricted
networks and common sign-in walls.

The maintained desktop targets are Linux and Windows. Linux is the primary development target; Windows compatibility is checked in CI.
The downloader currently uses a Python engine and a local WebView interface.
The interface is split into HTML, CSS and ordered JavaScript files; the engine
and platform packaging are being modularized without dropping existing features.

The **Update all components** button checks bundled downloaders and converters,
verifies Python wheels against PyPI's SHA-256 digest, and activates validated
Python updates on restart.

<sub>Telegram: <a href="https://t.me/BlueKnight_Net">@BlueKnight_Net</a></sub>

---

## Run it

1. Extract the full Windows ZIP or Linux TAR.GZ package.
2. Run `BlueKnightDownloader.exe` on Windows or `./BlueKnightDownloader` on Linux.
3. Pick a source in the sidebar, paste a link, press **Download**.

Built for 64-bit Linux and Windows 10/11. Internet access is still needed to
resolve metadata and fetch media.

## What each source takes

| Source | Accepts | Output |
| --- | --- | --- |
| **Spotify** | track · album · playlist | MP3 320 kbps or FLAC, tagged |
| **YouTube** | video · Short · playlist | MP4 up to best/1080/720/480, or audio-only as MP3 |
| **YouTube Music** | song · album · playlist | MP3 or FLAC, tagged with artist, album and cover art |
| **TikTok** | video link · `@username` · hashtag page | MP4 |
| **Instagram** | reel · post · `@username` | source quality, photo or video |
| **SoundCloud** | track · set · profile, including account-entitled Go/Go+ streams | MP3 or FLAC |
| **X** | `x.com` or `twitter.com` post - video, photo, GIF, multi-image | MP4, or JPG/PNG at full resolution |
| **Video** | public video page or direct media URL, excluding YouTube | MP4 or audio-only |
| **Documents & Ebooks** | documents, Office files, ebooks, comic archives, or an index page | original format |
| **Manga / manhwa** | public or account-authorized chapter page | PDF and CBZ |

Playlist and profile downloads take an optional item limit.

### More than one engine

yt-dlp only understands video. A post that is a photo, a GIF or a mix of both
is not a failure - it is a job for a different engine, so the X and **Video**
pages fall through automatically:

1. **yt-dlp** - video, everywhere it has an extractor.
2. **NewPipeExtractor (JVM helper)** - a desktop fallback for YouTube, YouTube
   Music, SoundCloud, Bandcamp, PeerTube and media.ccc.de after yt-dlp exhausts
   its extractor/client retries.
3. **Streamlink** - live and HLS streams on its supported services.
4. **HTML5 resolver** - standard video/audio tags and social media metadata.
5. **gallery-dl** - photos, GIFs, galleries and mixed posts.
6. **direct download** - the link treated as the file itself, using neither
   yt-dlp nor ffmpeg.

The hand-off is silent. NewPipeExtractor is also tried on desktop after yt-dlp's
useful retries are spent. The generic engines are used when yt-dlp reports that
there is no video at the link. A genuine DRM failure stops where it happened
rather than being retried pointlessly. The engines use the app's proxy and Stop button.

For a General-site bot check, CAPTCHA, or HTTP 401/403 response, yt-dlp gets a
separate challenge ladder before engine hand-off: the bundled Deno runtime,
then a browser-impersonated request, then a signed-in browser or exported jar
only when it contains cookies applicable to that exact hostname. Impersonation
is not forced on normal downloads because yt-dlp documents a speed and stability
cost. YouTube's player-client and PO-token arguments remain exclusive to the
YouTube pages and are never sent to other sites.

### What it cannot do

**Netflix, Crunchyroll, Disney+ and similar services are not supported and
cannot be added.** Every stream they serve is encrypted with Widevine DRM, and
downloading one means breaking that encryption. yt-dlp refuses these sites
outright, and so does this app. The same applies to individual protected tracks
elsewhere which still report `DRM protected` after account authentication. Those
stop without an attempted bypass. Unprotected media on those same sites works.

### SoundCloud Go / Go+

Use **Sign in to SoundCloud** on the SoundCloud page, finish the normal SoundCloud
login, and save the session. Downloads then begin with that account's verified
`oauth_token`, allowing yt-dlp to request premium or original formats the account
is entitled to. Public tracks still work without signing in. Authentication does
not decrypt DRM: if SoundCloud only returns an encrypted stream, the app reports
that limitation and leaves it untouched.

### Documents

The **Documents & Ebooks** page takes either a direct file link, or a page that
links to documents — a course page, a manual index, a journal issue — and collects
validated PDF, EPUB, MOBI, AZW/AZW3, FB2, Office, OpenDocument, RTF, text, DjVu,
CHM and CBZ files. Each link is checked by reading the file's first
bytes rather than trusting its name, so pages that serve documents from
`/download?id=…` work, and an HTML error page never lands on disk as a broken
`.pdf`. Sites that build their viewer in JavaScript hide the real file from the
page source; there, open the PDF in a browser and paste that address.

Switch the same page to **Manga / manhwa** for a public or account-authorized
chapter URL. gallery-dl is tried first, then the built-in HTML image resolver.
The extractor/HTML reading sequence is preserved and saved permanently as
`00001`, `00002`, ... inside a chapter folder; PDF and CBZ are built from that
same ordered list. It does not bypass DRM, subscriptions, paywalls, or site
access controls.

## Where files go

Everything lands next to the app, one folder per source:

```
BlueKnightdownloader/
├─ Spotify/
├─ YouTube/
├─ YouTube Music/
├─ TikTok/
├─ Instagram/
├─ SoundCloud/
├─ X/
├─ Video/
└─ Documents & Ebooks/
```

Change the parent folder in **Downloader settings**; the per-source folders follow.

## Local conversion

**Downloader settings** includes a local media converter for MP3, FLAC, WAV, M4A,
OGG, AAC, MP4, MKV, WebM, MOV and AVI. Video conversion offers H.264, H.265 and
VP9, three quality profiles, original/preset/custom dimensions, source/24/30/60
FPS, and selectable audio bitrate. FFmpeg performs a real transcode and writes
the result beside the selected source without overwriting it.

The document converter creates PDF from images, CBZ archives and PDF using the
bundled libraries. **Choose image folder** collects up to 500 images recursively,
uses numeric-aware ordering (`page2` before `page10`), and creates one PDF beside
the folder. Every readable image is fitted onto a legal portrait or landscape PDF
page without cropping; corrupt files and tracking pixels are skipped without
changing the remaining order. Office and OpenDocument conversion uses
LibreOffice when installed; ebook conversion uses Calibre when installed.
Downloaded PDFs are checked for a complete end marker, and EPUB/Office/CBZ ZIP
containers are CRC-checked before they are accepted. DRM-protected inputs are
not decrypted or bypassed.

The media converter has separate Video and Audio workspaces and contained format
buttons instead of an operating-system dropdown, so unrelated controls stay out
of the way and the output chooser cannot open outside the app window. Every app
launch begins in dark mode. Video profiles include archival CRF encoding,
detailed Lanczos or smooth Spline scaling,
denoise/deband/sharpen/color presets, and optional motion-compensated frame-rate
interpolation. Audio profiles include -14 LUFS normalization, gentle music dynamics,
and broadband noise cleanup; WAV uses 24-bit PCM. These are real FFmpeg resampling
and DSP operations, but they do not claim to reconstruct detail missing from the
source. FLAC/WAV prevent additional lossy compression rather than improving an
already lossy input by themselves.

## Sign-in and cookies

Some things are simply not served to a logged-out client — most Instagram
content, and YouTube whenever it decides your IP looks like a robot.

**The easy way.** Press **Sign in** on the YouTube, X, or Instagram page. The app
opens a real login window of its own, you sign in normally, and it keeps the
session itself. That login survives restarts, and the app quietly re-reads it
when a site rotates its cookies — which YouTube does constantly.

**The manual way.** Export a `cookies.txt` (Netscape format — the
*Get cookies.txt LOCALLY* extension writes one) and drop it in the app folder,
your `Downloads`, or the download folder. Any `*cookies*.txt` is picked up.
For a jar that lasts, follow yt-dlp's own advice: sign in using a **private
window**, visit `robots.txt` in that same tab, export, then close the window
and never reopen it.

Cookie jars are kept **per site** in `cookies/<site>/`, with a small registry
recording what each holds and when it expires. An Instagram jar is never
offered to YouTube. General-site cookie retries are challenge-triggered and
domain checked; unrelated cookies in a browser or export are not sent to the
requested host.

> Use a throwaway account, not your main one. yt-dlp's wiki warns that
> accounts used for downloading can be banned.

The app can also read a browser you are already signed into (Firefox,
Opera GX, Brave, Vivaldi, Edge, Chrome, Chromium, LibreWolf, Whale) — but a
running Chromium browser holds an exclusive lock on its cookie database, so it
has to be **closed** first. Firefox stays readable while open. Chrome 127+
encrypts its jar app-bound and cannot be read at all; use the in-app sign-in or
an exported file instead.

## Restricted networks

Open **Connection**, switch the proxy on, and pick a preset:

| Preset | Address |
| --- | --- |
| V2RayN HTTP | `http://127.0.0.1:10809` |
| V2RayN SOCKS5 | `socks5://127.0.0.1:10808` |
| Clash | `http://127.0.0.1:7890` |

**Test proxy** checks it before you commit to a download. SOCKS5 is handled
through a temporary local HTTP bridge, because spotDL only speaks HTTP — and
note that spotDL reads `HTTP_PROXY`/`HTTPS_PROXY`, which the app sets for it.
If Spotify resolves but never downloads, the proxy toggle is the first thing
to check.

## When YouTube asks for a bot check

The app bundles Deno so yt-dlp can execute its EJS JavaScript challenge solver,
then retries the current token-free and HLS-capable clients before asking for a
fresh signed-in session. Playlist requests are spaced out to reduce session
rate limits.

If a GoogleVideo URL expires or returns HTTP 403, the app discards stale partial
state, asks YouTube for a fresh delivery URL, and walks the client ladder before
requesting sign-in. Machine-wide yt-dlp configuration files are ignored so an
old local override cannot silently break the bundled downloader.

If YouTube still requires proof-of-origin attestation, **Connection settings**
accepts an `mweb.gvs+TOKEN` value in yt-dlp's official format. It is kept in
memory only. These tokens are session/video-bound and expire, so this is an
advanced fallback rather than a permanent credential. A signed-in throwaway
account or a different IP may still be required.

## Keeping it current

**Update all components** refreshes spotDL, yt-dlp, Deno, FFmpeg, gallery-dl,
Streamlink, img2pdf, Pillow, pikepdf and the certifi CA bundle. Executables download
to temporary files and must launch successfully before an atomic replacement.
Python wheels are SHA-256 checked, staged as one set, and exercised together by a
fresh process before their registry is committed; they activate on restart. A
failed or incompatible update leaves the working downloader unchanged. Downloads
and conversions cannot start during activation, preventing a tool from changing
underneath a running job.

The tools use mirrored hosts (GitHub, with SourceForge as an escape hatch where
available). The check also reports whether usable Instagram and SoundCloud
sessions are on file. Sites change frequently, so keeping yt-dlp and the fallback
engines current is important.

## Building from source

**Windows**

```powershell
.\build_portable.ps1
```

**Linux**

```bash
bash ./build_portable.sh
```

Both desktop builds use Python 3.12. The scripts fetch or prepare the required
command-line tools and create a portable package under `release/`:

- Windows: `BlueKnightDownloader-windows-x64.zip`
- Linux: `BlueKnightDownloader-linux-x64.tar.gz`

The Linux build needs the WebKitGTK 4.1 and GTK development packages. The
resulting Linux archive does not bundle WebKitGTK; the matching runtime
libraries must be installed on the target system. Both release archives include
portable.mode, which stores updateable tools and application-managed data under
a data/ directory beside the executable. A JDK 17 and .NET 8 SDK are used to
build the NewPipe and YoutubeExplode fallback helpers when available.

CI validates Windows x64 and Linux x64 builds. Tags named
`downloader-v*` or `Blueknightv*` publish the desktop ZIP and TAR.GZ artifacts.

| File | Role |
| --- | --- |
| `spotify_downloader.py` | current desktop engine, download logic, Python bridge |
| `blueknight_paths.py` | download folders, cookie discovery, the jar registry |
| `web/index.html` | interface markup and asset loading order |
| `web/css/app.css` | interface styling |
| `web/js/` | ordered classic scripts for shell, routing, controls and runtime |
| `web/js/README.md` | frontend module responsibilities and loading constraints |
| `tests/check_web_assets.py` | local HTML/CSS asset reference checks |
| `tests/check_web_scripts.mjs` | JavaScript syntax and shared-binding checks |
| `build_portable.ps1` | Windows desktop build |
| `build_portable.sh` | Linux desktop build |

`blueknight_paths.py` runs its own checks with `python blueknight_paths.py`.


## Network module

Proxy URL validation, credential-safe display formatting, process proxy
environment setup, the local SOCKS5-to-HTTP CONNECT bridge, and the callback-driven
`ProxyManager` live in `blueknight/network/proxy.py`. The desktop engine keeps
thin compatibility methods so the current UI bridge is unchanged.

The platform-aware engine manifest lives in `blueknight/engines/catalog.py`.
It records existing versions, platform assets, release mirrors, FFmpeg archives
and the optional PO-token provider. It does not remove any engines.

The desktop engine imports these names through a compatibility layer, so older
call sites and the current WebView API do not need to change during extraction.
Run the isolated proxy tests with:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The loopback integration test creates a local SOCKS5 server and echo target; it
does not contact an external proxy or media website.

## Web interface

The desktop WebView opens `web/index.html` from the local filesystem. Keep its
asset references relative and do not switch the frontend files to ES modules
without replacing and testing the local-file loading strategy.

The classic scripts are loaded in this order:

1. `web/js/shell.js`
2. `web/js/routing.js`
3. `web/js/components.js`
4. `web/js/runtime.js`

The scripts share the page's global lexical scope, so top-level declaration
names must remain unique and the order must not change casually.

Run the frontend checks before submitting UI changes:

```bash
python tests/check_web_assets.py
node tests/check_web_scripts.mjs
python tests/check_bridge_contract.py
```

These checks validate local asset paths, script order, absence of inline code,
JavaScript syntax, and duplicate shared declarations. They do not replace a
visual smoke test in the actual Windows WebView and Linux WebKitGTK window.


## Desktop architecture

The current module boundaries, WebView bridge contract, Python engine responsibilities
and staged Rust migration plan are documented in [docs/architecture.md](docs/architecture.md).
Treat that document as the desktop refactor map; it does not imply that the target
Rust modules have already been implemented.

## Licensing

Released under **GPL-3.0** (`GPL-3.0.txt`). Bundled tools keep their own
licences — spotDL (MIT), yt-dlp (Unlicense), FFmpeg (GPL) — with sources and
full notices in `THIRD_PARTY_NOTICES.txt`.

Download only what you have the right to download. Respect each platform's
terms and the rights of the people who made the work.
