#!/usr/bin/env python3
"""Validate the local frontend assets used by the desktop WebView."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
INDEX = WEB / "index.html"

EXPECTED_STYLESHEETS = ["./css/app.css"]
EXPECTED_SCRIPTS = [
    "./js/shell.js",
    "./js/routing.js",
    "./js/components.js",
    "./js/runtime.js",
]


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stylesheets: list[str] = []
        self.scripts: list[tuple[str | None, str]] = []
        self.html_assets: list[str] = []
        self.style_blocks = 0
        self.inline_style_attributes = 0
        self.inline_event_attributes: list[str] = []
        self._inside_inline_script = False
        self.inline_script_bodies = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}

        if "style" in values:
            self.inline_style_attributes += 1

        self.inline_event_attributes.extend(
            key for key in values if key.startswith("on") and len(key) > 2
        )

        if tag in {"img", "source", "audio", "video"}:
            reference = values.get("src") or values.get("poster")
            if reference:
                self.html_assets.append(reference)

        if tag == "style":
            self.style_blocks += 1

        if tag == "link" and "stylesheet" in values.get("rel", "").lower().split():
            self.stylesheets.append(values.get("href", ""))

        if tag == "script":
            src = values.get("src") or None
            script_type = values.get("type", "").lower()
            self.scripts.append((src, script_type))
            self._inside_inline_script = src is None

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._inside_inline_script:
            self.inline_script_bodies += 1
            self._inside_inline_script = False


def local_file(reference: str, base: Path) -> Path:
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc:
        raise AssertionError(f"Expected a local asset reference, got: {reference!r}")
    if not parsed.path:
        raise AssertionError(f"Empty local asset reference: {reference!r}")

    candidate = (base / unquote(parsed.path)).resolve()
    if not candidate.is_relative_to(WEB.resolve()):
        raise AssertionError(f"Asset escapes the web directory: {reference!r}")
    if not candidate.is_file():
        raise AssertionError(f"Referenced asset does not exist: {reference!r}")
    return candidate


def main() -> int:
    if not INDEX.is_file():
        raise AssertionError("web/index.html is missing")

    html = INDEX.read_text(encoding="utf-8")
    parser = AssetParser()
    parser.feed(html)
    parser.close()

    if parser.stylesheets != EXPECTED_STYLESHEETS:
        raise AssertionError(
            f"Stylesheet order/references changed: {parser.stylesheets!r}"
        )

    script_refs = [src for src, _ in parser.scripts]
    if script_refs != EXPECTED_SCRIPTS:
        raise AssertionError(f"Script order/references changed: {script_refs!r}")

    if any(script_type == "module" for _, script_type in parser.scripts):
        raise AssertionError("Frontend scripts must remain classic scripts for local WebView")

    if parser.style_blocks:
        raise AssertionError("Inline <style> blocks are not allowed")

    if parser.inline_script_bodies:
        raise AssertionError("Inline JavaScript blocks are not allowed")

    if parser.inline_style_attributes:
        raise AssertionError("Inline style attributes are not allowed")

    if parser.inline_event_attributes:
        raise AssertionError(
            f"Inline event handlers are not allowed: {parser.inline_event_attributes!r}"
        )

    for reference in parser.stylesheets:
        local_file(reference, WEB)

    for reference in script_refs:
        local_file(reference, WEB)

    for reference in parser.html_assets:
        local_file(reference, WEB)

    css_path = local_file(parser.stylesheets[0], WEB)
    css = css_path.read_text(encoding="utf-8")
    components = (WEB / "js" / "components.js").read_text(encoding="utf-8")

    if 'role="progressbar"' not in html or 'aria-valuenow="0"' not in html:
        raise AssertionError("Download progress must expose its initial accessible value")
    if 'aria-label="Setting up media components"' not in html:
        raise AssertionError("Setup progress must expose an indeterminate accessible label")
    if 'setAttribute("aria-valuenow"' not in components:
        raise AssertionError("Download progress must keep its accessible value in sync")

    required_visual_rules = (
        "--chrome-surface:",
        "--chrome-filter:",
        ".bar::after",
        "@media (prefers-reduced-transparency: reduce)",
    )
    missing_visual_rules = [rule for rule in required_visual_rules if rule not in css]
    if missing_visual_rules:
        raise AssertionError(f"Frosted navigation/progress rules missing: {missing_visual_rules!r}")

    css_urls = re.findall(r"url\(\s*(['\"]?)(.*?)\1\s*\)", css, re.IGNORECASE)
    for _, reference in css_urls:
        reference = reference.strip()
        if not reference or reference.startswith(("#", "data:", "http:", "https:", "var(")):
            continue
        local_file(reference, css_path.parent)

    print("Web assets: OK")
    print(f"  stylesheet: {parser.stylesheets[0]}")
    for reference in script_refs:
        print(f"  script:     {reference}")
    print(f"  HTML media assets: {len(parser.html_assets)} checked")
    print("  inline CSS/JavaScript/styles: none")
    print("  local CSS URLs: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
