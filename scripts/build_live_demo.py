#!/usr/bin/env python3
"""Build the browser-only GitHub Pages version of the Blue Knight UI."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "web"
DEFAULT_OUTPUT = ROOT / "_site"

DEMO_STYLESHEET = '<link rel="stylesheet" href="./css/demo.css">'
DEMO_SCRIPT = '<script src="./js/demo.js"></script>'
RUNTIME_SCRIPT = '<script src="./js/runtime.js"></script>'
BODY = "<body>"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if not (source / "index.html").is_file():
        raise SystemExit(f"Web source not found: {source}")
    if source == output or source in output.parents:
        raise SystemExit("Output must be outside the source web directory")
    if output.exists():
        raise SystemExit(f"Output already exists; refusing to overwrite: {output}")

    required = (
        source / "css" / "app.css",
        source / "js" / "runtime.js",
        source / "logo.png",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing web assets: " + ", ".join(missing))

    shutil.copytree(source, output)

    demo_js = ROOT / "web" / "js" / "demo.js"
    demo_css = ROOT / "web" / "css" / "demo.css"
    if not demo_js.is_file() or not demo_css.is_file():
        shutil.rmtree(output)
        raise SystemExit("The browser demo adapter or stylesheet is missing")

    index_path = output / "index.html"
    html = index_path.read_text(encoding="utf-8")
    if html.count(BODY) != 1 or html.count(RUNTIME_SCRIPT) != 1:
        shutil.rmtree(output)
        raise SystemExit("Unexpected web/index.html structure; refusing an unsafe injection")
    if DEMO_SCRIPT in html or DEMO_STYLESHEET in html:
        shutil.rmtree(output)
        raise SystemExit("Demo assets are already injected into the source index")

    html = html.replace(BODY, BODY + '\n<div class="demo-banner" role="status">'
                        '<strong>LIVE DEMO</strong>'
                        '<span>Sample environment · No files are downloaded</span>'
                        '<a href="https://github.com/MHDLabs/BlueKnight-Downloader-linux/releases" '
                        'target="_blank" rel="noopener noreferrer">Get the app</a>'
                        '</div>', 1)
    html = html.replace("</head>", DEMO_STYLESHEET + "\n</head>", 1)
    html = html.replace(RUNTIME_SCRIPT, DEMO_SCRIPT + "\n" + RUNTIME_SCRIPT, 1)
    index_path.write_text(html, encoding="utf-8")

    print(f"Built browser demo: {output}")
    print("Desktop source files were copied without modification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
