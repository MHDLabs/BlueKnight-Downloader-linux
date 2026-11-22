# GitHub Pages live demo

The public demo reuses the desktop application's existing HTML, CSS and
JavaScript. The Pages build adds a browser-only API adapter; it does not change
the desktop web/index.html or the native Python bridge.

## What the demo can do

- Navigate the same source pages and change the visible settings.
- Run a clearly labelled, simulated download flow with progress and activity logs.
- Preview the available UI without installing the desktop application.

The demo does **not** download media, contact extractors, use local files,
install tools, sign in to services, read cookies, test a proxy, or connect to a
desktop process. The banner and completion messages identify the run as a
simulation.

## Publish

In the repository settings, open **Settings → Pages** and set **Build and
deployment → Source** to **GitHub Actions** once.

The Live demo (GitHub Pages) workflow then builds the static site from
web/ and deploys it after changes reach main. Pull requests build and test
the preview but do not publish it.

Expected project site:

https://mhdlabs.github.io/BlueKnight-Downloader-linux/

## Architecture

web/js/demo.js implements the same method names declared in
contracts/desktop-bridge-v1.json. The Pages build injects that adapter before
runtime.js and adds web/css/demo.css. The source desktop page never includes
the adapter, so desktop builds continue using pywebview's native API and work
offline with their packaged frontend.

Do not load the public Pages version inside a privileged desktop WebView. The
remote page is for human previews only; the installed application should keep
loading its packaged local interface.
