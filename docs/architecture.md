# Desktop Architecture and Rust Migration

> Status: architectural plan. This document does not claim that the Python modules
> or Rust crates described below have already been implemented.

## Scope

- **Primary target:** Linux desktop.
- **Secondary compatibility target:** Windows desktop code and packaging are retained, but automated Windows builds are temporarily paused. Re-enable them after Linux stabilization and cross-platform regression coverage.
- **Platform scope:** desktop only. Linux is the active build and test target;
  Windows is a retained secondary compatibility target; mobile application
  code is outside this fork.
- **Feature policy:** one complete application. Existing engines and user-facing
  capabilities are not removed to make packaging smaller.
- **UI policy:** preserve the current interface and its behaviour while the internals
  are reorganized.

## Current desktop runtime

The current desktop path is:

1. spotify_downloader.py creates the SpotifyDownloader application object.
2. Api exposes the desktop methods to pywebview through js_api.
3. web/index.html loads the local HTML, stylesheet and classic JavaScript files.
4. The page calls window.pywebview.api; poll() drains events from the Python
   queue and the page updates progress, status, logs and controls.
5. The application launches or coordinates the existing media and conversion tools.

The Python desktop engine is still a large compatibility surface: the
SpotifyDownloader class, desktop Api adapter and module-level helpers remain
concentrated in spotify_downloader.py. blueknight_paths.py and pyshell.py
already isolate application paths, cookie discovery and process-launch
behaviour. Exact line and method counts are intentionally omitted because they
change during routine maintenance.

## Frontend layout

The WebView interface is now split into separate assets:

- web/index.html — page structure and resource loading order.
- web/css/app.css — visual design and layout.
- web/js/shell.js — shared state, navigation and responsive shell.
- web/js/routing.js — URL routing, previews, page selection and theme.
- web/js/components.js — converter controls, notifications, log and progress UI.
- web/js/runtime.js — API event handling, UI wiring and boot sequence.

The JavaScript files are intentionally classic scripts, not ES modules. The
desktop page is loaded from a local file URL, and the scripts share a global
lexical scope. Preserve their order and keep top-level declaration names unique.

## Stable WebView boundary

contracts/desktop-bridge-v1.json records the current frontend-to-engine boundary:

- 27 API methods, including their argument names.
- The event names emitted by the desktop engine and consumed by the page.

The bridge is a migration boundary, not an implementation detail to casually
change. A new Python module or Rust service should continue to satisfy this
contract until there is a deliberate, tested version change.

## Responsibilities currently concentrated in the Python engine

The following are logical responsibilities, not completed modules yet:

| Responsibility | Existing code examples |
| --- | --- |
| Application lifecycle and UI events | snapshot, begin, drain, ui, log, stop_download |
| Network and proxy | blueknight/network/proxy.py now owns URL normalization, credential-safe display, process proxy environment and the SOCKS5 bridge; SpotifyDownloader still owns UI-facing proxy settings and connection tests |
| Tool installation and updates | blueknight/engines/catalog.py owns version/platform manifests and release URLs; SpotifyDownloader still owns installation, validation and activation |
| Authentication and cookies | probe_cookie, usable_cookies, sign_in, finish_sign_in, refresh_session, cookie_status |
| Spotify | start_download, download_with_spotdl, Spotify metadata and matching helpers |
| Media download orchestration | start_media_download, download_with_ytdlp, download_with_streamlink, gallery-dl fallback |
| YouTube fallbacks | YoutubeExplode, NewPipe, YouTube.js and PO-token helpers |
| Documents and manga | start_pdf_download, download_pdfs, download_manga, HTML/file validation |
| Conversion | media_conversion_command, convert_media_file, convert_document_file, image-to-PDF helpers |
| Desktop API | Api methods exposed to pywebview |

## First extracted module

The first network extraction is implemented:

- `blueknight/network/proxy.py` contains the standalone proxy URL and SOCKS5
  bridge helpers.
- `spotify_downloader.py` re-exports those names so the current desktop engine
  and older helper scripts retain their import surface.
- `tests/test_network_proxy.py` covers URL validation, redaction, proxy
  environment variables and a loopback SOCKS5 tunnel.
- `ProxyManager` in `blueknight/network/proxy.py` owns connection checks and
  urllib opener lifetimes through injected settings and UI callbacks.
- `SpotifyDownloader` retains thin UI-facing compatibility methods; the
  existing WebView bridge does not need to change for this extraction.
- The application self-test still imports the legacy process-proxy helper
  through the same module.

## Engine catalog extraction

The platform-aware engine manifest now lives in `blueknight/engines/catalog.py`:
versions, OS-specific assets, release mirrors, FFmpeg archives, the optional
PO-token provider and the `TOOLS` registry. `spotify_downloader.py` imports
these names as compatibility exports.

Python wheel matching is separated into `blueknight/engines/wheels.py`. It
uses the ordered compatibility tags supplied by `packaging` rather than
hard-coded Windows filename fragments, so Linux manylinux/musllinux wheels,
Windows wheels and universal wheels are selected against the running runtime.
The five deterministic tests simulate Linux and Windows tag sets without
claiming that Windows CI is active.

These are focused boundaries, not a complete engine manager. Downloading,
native executable validation, version probing, checksum checks, installation
and activation still remain in the application service. No engine was removed.

## Intended module boundaries

The first modular Python layout should follow responsibilities already present in
the code, rather than inventing a new feature model:

    blueknight/
    ├── application/       # app lifecycle and orchestration
    ├── bridge/            # desktop API facade and event queue
    ├── network/           # proxy configuration, SOCKS bridge and HTTP helpers
    ├── auth/              # cookie store, browser sessions and sign-in
    ├── engines/           # tool registry, setup, versions and engine adapters
    ├── downloads/         # Spotify, media, documents and manga workflows
    ├── conversion/        # media and document conversion
    └── platform/          # Linux and Windows paths, process and desktop integration

This is a target map, not a request to move the whole class in one commit.
During extraction, spotify_downloader.py should remain a compatibility facade
so existing launchers and the Windows build do not lose their entry points.
Each extraction must have tests before the old implementation is removed.

## Rust destination

Rust should own the application core and the coordination layer:

- job lifecycle, cancellation, queueing and progress events;
- engine discovery, version tracking, updates and integrity checks;
- proxy configuration and process orchestration;
- persistent settings, paths and cookie-file permissions;
- conversion job planning and platform-specific integration;
- the desktop bridge consumed by the existing WebView.

The third-party engines remain engines. We do not need to rewrite yt-dlp,
spotDL, gallery-dl, Streamlink, Deno, FFmpeg, NewPipe, YoutubeExplode or
YouTube.js just to move the application core to Rust.

**A Rust core does not make every dependency Rust.** Some retained engines and
fallbacks are Python, Java, .NET or standalone native programs. Their runtimes
and packaging must be accounted for explicitly; they must not silently disappear
during the migration.

The eventual Rust desktop host should preserve the WebView contract through a
small adapter. The exact host technology should be selected only after checking
Linux WebKitGTK integration, Windows WebView2 integration, packaging size,
startup time and process/runtime requirements.

## Migration order

1. **Frontend assets:** split HTML, CSS and JavaScript without changing the UI.
   Completed; the current assets live under web/ and are loaded from the local WebView page.
2. **Bridge contract:** record and test the current API signatures and event names.
   Completed in contracts/desktop-bridge-v1.json.
3. **Regression baseline:** add tests/fixtures for queue events, process exit,
   cancellation, proxy handling, engine selection and representative downloads.
4. **Python extraction:** move one responsibility at a time behind the existing
   SpotifyDownloader and Api facades. Preserve the retained Windows packaging path; its automated CI is paused.
5. **Rust core:** introduce Rust modules behind the same contract and test each
   service with deterministic fixtures and fake engine processes.
6. **Desktop integration:** replace the Python desktop host only after Linux and
   Windows feature-parity tests pass.

## Acceptance criteria

A refactor is not complete merely because it compiles. Before merging a desktop
change, verify:

- the WebView loads every local HTML/CSS/JavaScript/image asset;
- all 27 bridge methods and the shared event contract still match;
- existing download engines and fallback order remain available;
- stop/cancel, proxy, sign-in, cookies, conversion and update operations work;
- Linux package build and frozen smoke test pass in active CI;
- the visible UI has no unintended layout or interaction change.
- Windows compatibility remains represented by the retained build script; do
  not claim automated Windows coverage until its CI runner is resumed.


This fork does not include a mobile application target.
