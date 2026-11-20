# Frontend scripts

These files are loaded as **classic scripts**, in the order listed below by
`web/index.html`:

1. `shell.js` — shared state, navigation, responsive shell and phone layout.
2. `routing.js` — URL routing, previews, page selection, sign-in and theme UI.
3. `components.js` — converter controls, notifications, activity log, progress UI.
4. `runtime.js` — Python bridge event handling, event polling, wiring and boot.

They intentionally do not use JavaScript modules (`import`/`export`). The
desktop opens the page from a local `file://` URL through pywebview, so keeping
these as ordered classic scripts avoids depending on module-loading behaviour
for local files. Top-level declarations share the page's global lexical scope:
keep declaration names unique across files and preserve this load order.

When adding a new file, add it to the script list in `web/index.html`, update
the asset smoke test in `tests/check_web_assets.py`, and keep all script tags
after the page markup.
