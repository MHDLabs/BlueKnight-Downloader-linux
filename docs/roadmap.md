# Blue Knight Downloader — Development Roadmap

This roadmap describes the intended destination of the MHDLabs desktop fork.
It is deliberately incremental: each phase should leave a working application
and preserve the existing feature set.

## Product decisions

- Linux is the primary development, build and release target.
- Windows remains a secondary compatibility target. Its automated CI build is
  temporarily paused; `build_portable.ps1` is retained.
- Android application code is out of scope and has been removed from this fork.
- One complete product is maintained. Do not create Lite/Full editions or drop
  download engines to make the package smaller.
- Keep the current WebView UI and bridge stable while replacing internals.
- Rust is the intended destination for the application core, not a reason to
  rewrite or discard third-party engines.

## Phase 0 — Product scope and desktop boundary

**Status: Complete**

- Removed the Android application, Chaquopy bridge, APK tooling and Android CI.
- Moved the Gradle Wrapper needed by the NewPipe JVM helper to `jvm/`.
- Kept the existing desktop download engines and fallback capabilities.
- Split the WebView into HTML, CSS and ordered JavaScript files.
- Recorded and tested the desktop Python-to-WebView bridge contract.
- Extracted the network proxy manager and engine release catalog.
- Added portable package mode using a `portable.mode` marker.

**Exit criteria:** desktop-only scope is explicit, mobile build paths are absent,
and the branch can produce Linux and Windows packages.

## Phase 1 — Linux stabilization and release baseline

**Status: In progress — current phase**

Priorities:

1. Verify the actual GUI on a Linux desktop using the packaged executable,
   including first launch, theme/layout, sign-in windows and error handling.
2. Verify portable data paths, write permissions and upgrades. Portable mode
   now performs a one-time, copy-only migration of tools, FFmpeg, plugins and
   Python-engine updates from the old per-user directory. It never deletes
   source data or overwrites files already present in the portable destination;
   cookies, downloads and unrelated folders are excluded. Deterministic tests
   cover interrupted retries, registry path rebasing and marker/override rules.
3. Add deterministic tests for tool discovery, downloads, process exit,
   cancellation, proxy routing, cookie/session handling and conversion paths.
4. Run controlled end-to-end checks for representative sources and formats:
   Spotify, YouTube, TikTok, Instagram, SoundCloud/X, documents and media
   conversion. Record unsupported or externally blocked cases honestly.
5. Ensure the Linux archive contains every required app asset and helper;
   document system requirements such as WebKitGTK 4.1.

**Exit criteria:** Linux build and frozen smoke test pass, the real GUI has been
visually exercised, portable data behaviour is verified, and core workflows
have regression coverage.

## Phase 2 — Engine installation and lifecycle service

**Status: In progress — discovery and version probing extracted**

The platform-specific Python wheel selector lives in
`blueknight/engines/wheels.py`. It matches PyPI wheel tags against the running
interpreter and platform, with deterministic coverage for Linux, Windows and
universal wheels.

The engine manager in `blueknight/engines/manager.py` now owns native
executable validation, tool discovery, version probing, release metadata,
mirror downloads, archive member extraction, SHA-256 validation, version checks
and atomic activation. The desktop methods remain compatibility adapters and
inject the existing proxy-aware opener plus UI/log callbacks.

Python wheel discovery, SHA-256 validation and staging remain in their existing
dedicated path. The remaining work in this phase is to move the Python-engine
staging/registry lifecycle and the FFmpeg-specific installer behind focused
service interfaces, then verify update/rollback behaviour end to end. Do not
change the set of engines or their update sources without a separate, tested
reason.
**Exit criteria:** the manager has focused unit tests and the GUI still reports,
installs, updates and launches the same tools as before.

## Phase 3 — Download orchestration and engine adapters

**Status: Planned**

Separate job orchestration from individual source adapters. Preserve the
existing fallback chain and its decision rules for authentication failures,
bot checks, unsupported formats, DRM, rate limits and cancellation.

Keep third-party engines as external tools/libraries where appropriate:
spotDL, yt-dlp, Deno, FFmpeg, gallery-dl, Streamlink, NewPipeExtractor,
YoutubeExplode and YouTube.js.

**Exit criteria:** fallback order and hand-off reasons are covered by tests;
stop/cancel and progress events remain compatible with the existing bridge.

## Phase 4 — Authentication, cookies, settings and network boundaries

**Status: Planned — proxy extraction already started**

Complete the separation of sign-in lifecycle, cookie discovery/validation,
per-site cookie registry, settings persistence, proxy policy and browser
integration. Keep session data isolated by site and preserve current user
sessions when the storage layout changes.

**Exit criteria:** sign-in, refresh, imported cookies, proxy routing and portable
storage have dedicated tests and no cross-site cookie leakage.

## Phase 5 — Documents, media conversion and specialized workflows

**Status: Planned**

Separate PDF/ebook fetching, manga/image-to-PDF, document conversion, audio/video
conversion and output planning. Keep optional system converters such as
LibreOffice and Calibre discoverable rather than silently removing their
capabilities.

**Exit criteria:** each workflow has format fixtures, clear missing-dependency
messages, cancellation support and tested output placement.

## Phase 6 — Rust application core

**Status: Planned — only after the Python boundaries are stable**

Introduce Rust behind the existing desktop bridge. Migrate application-owned
responsibilities incrementally:

- job lifecycle, queues, cancellation and progress;
- tool registry, installation, validation and updates;
- settings, paths, portable data and cookie-file permissions;
- proxy configuration and child-process orchestration;
- conversion planning and desktop integration.

Do not rewrite yt-dlp, spotDL, gallery-dl, Streamlink, FFmpeg, NewPipe,
YoutubeExplode, Deno or YouTube.js as part of this phase. Keep the WebView
contract stable until a deliberate, versioned migration is tested.

**Exit criteria:** Rust and Python implementations pass the same contract and
fixture tests; the Linux application reaches feature parity before the Python
host is retired.

## Phase 7 — Linux packaging and release hardening

**Status: Planned**

Harden the portable TAR.GZ, test upgrades and data migration, document runtime
dependencies, validate archive contents and checksums, and improve release
automation. Evaluate AppImage only after WebKitGTK, GTK and other native runtime
dependencies have a credible compatibility strategy.

**Exit criteria:** repeatable Linux release artifacts, tested upgrades, clear
system requirements and reproducible smoke tests.

## Phase 8 — Resume Windows CI and cross-platform validation

**Status: Paused**

After Linux architecture and regression tests are stable:

1. Re-enable the Windows runner.
2. Resolve any platform-specific packaging or path differences.
3. Run the same bridge, engine, cookie, proxy and conversion contract tests.
4. Restore Windows smoke tests and artifact publication.

The Windows build script remains available during the pause. No promise is made
that it is currently exercised by CI.

**Exit criteria:** Windows x64 packaging and smoke tests pass alongside Linux
without reducing feature parity.

## Working rules

- `main` is the maintained branch. Use a short-lived branch only when a PR
  or parallel work is explicitly requested.
- One responsibility per extraction, with tests before removing the old path.
- Preserve all current engines, fallbacks and user-facing capabilities.
- Avoid speculative rewrites and broad dependency replacement.
- Prefer small, reversible commits with a clear report of changed files and
  verification results.
- Never call a build or test "passed" unless its actual CI/local result is green.
