#!/usr/bin/env python3
"""Validate the generated Pages demo and its desktop bridge contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "desktop-bridge-v1.json"
DEMO_SOURCE = ROOT / "web" / "js" / "demo.js"


def main() -> int:
    site = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
    index = site / "index.html"
    demo_js = site / "js" / "demo.js"
    demo_css = site / "css" / "demo.css"

    for path in (index, demo_js, demo_css):
        if not path.is_file():
            raise AssertionError(f"Missing generated demo asset: {path}")

    html = index.read_text(encoding="utf-8")
    if html.count('<script src="./js/demo.js"></script>') != 1:
        raise AssertionError("The Pages index must load the demo adapter exactly once")
    if html.index('<script src="./js/demo.js"></script>') > html.index(
            '<script src="./js/runtime.js"></script>'):
        raise AssertionError("The demo adapter must load before runtime.js")
    if 'class="demo-banner"' not in html or "No files are downloaded" not in html:
        raise AssertionError("The demo must visibly disclose that it is simulated")
    if 'href="https://github.com/MHDLabs/BlueKnight-Downloader-linux/releases"' not in html:
        raise AssertionError("The demo must link to the desktop releases")
    if '<link rel="stylesheet" href="./css/demo.css">' not in html:
        raise AssertionError("The demo stylesheet is not linked")

    desktop_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    if '<script src="./js/demo.js"></script>' in desktop_html:
        raise AssertionError("The desktop source must not load the browser-only demo adapter")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = DEMO_SOURCE.read_text(encoding="utf-8")
    match = re.search(r"const api = Object\.freeze\(\{([\s\S]*?)\n  \}\);", source)
    if not match:
        raise AssertionError("Could not locate the demo API object")
    methods = set(re.findall(r"^\s{4}([a-z_][a-z0-9_]*)\s*\(", match.group(1), re.M))
    expected = {item["name"] for item in contract["api"]}
    if methods != expected:
        raise AssertionError(
            f"Demo API differs from desktop contract. "
            f"Missing={sorted(expected - methods)}; unexpected={sorted(methods - expected)}"
        )

    forbidden = (
        r"\bfetch\s*\(",
        r"\bXMLHttpRequest\b",
        r"\bWebSocket\b",
        r"\bnavigator\.sendBeacon\b",
        r"\bEventSource\b",
    )
    for pattern in forbidden:
        if re.search(pattern, source):
            raise AssertionError(f"Demo adapter must not make backend/network API calls: {pattern}")

    for reference in ("css/app.css", "css/demo.css", "js/shell.js",
                      "js/routing.js", "js/components.js", "js/demo.js",
                      "js/runtime.js", "logo.png", "backdrop.png"):
        if not (site / reference).is_file():
            raise AssertionError(f"Missing Pages asset: {reference}")

    print("GitHub Pages live demo: OK")
    print(f"  demo API methods: {len(methods)} (matches desktop bridge contract)")
    print("  browser demo is explicitly labelled as simulated")
    print("  no backend/network API calls in the demo adapter")
    print("  all required local assets exist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
