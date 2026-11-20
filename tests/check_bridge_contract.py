#!/usr/bin/env python3
"""Guard the frontend-to-engine API used by the desktop WebView."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "desktop-bridge-v1.json"
ENGINE = ROOT / "spotify_downloader.py"
SCRIPT_FILES = [
    ROOT / "web/js/shell.js",
    ROOT / "web/js/routing.js",
    ROOT / "web/js/components.js",
    ROOT / "web/js/runtime.js",
]


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def read_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def engine_api(source: str) -> dict[str, list[str]]:
    tree = ast.parse(source, filename=str(ENGINE))
    api_class = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Api"),
        None,
    )
    if api_class is None:
        raise AssertionError("The desktop Api class is missing")

    methods: dict[str, list[str]] = {}
    for node in api_class.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith("_"):
            continue
        methods[node.name] = [arg.arg for arg in node.args.args[1:]]
    return methods


def emitted_events(source: str) -> set[str]:
    tree = ast.parse(source, filename=str(ENGINE))
    emitted: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue

        # Engine events and Api adapter events are forwarded unchanged by drain().
        if dotted_name(node.func) in {"self.ui", "self._app.ui"}:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                emitted.add(first.value)

        # log() and _flush_logs() enqueue batch_log directly; drain() exposes it
        # to the page as the normalized "log" event.
        if dotted_name(node.func) == "self.ui_queue.put":
            first = node.args[0]
            if (isinstance(first, ast.Tuple) and first.elts
                    and isinstance(first.elts[0], ast.Constant)
                    and isinstance(first.elts[0].value, str)):
                emitted.add(first.elts[0].value)

    if "batch_log" in emitted:
        emitted.remove("batch_log")
        emitted.add("log")
    return emitted


def main() -> int:
    contract = read_contract()
    if contract.get("version") != 1:
        raise AssertionError("Unsupported desktop bridge contract version")

    python_source = ENGINE.read_text(encoding="utf-8")
    declared_api = engine_api(python_source)
    expected_api = {
        item["name"]: item["args"] for item in contract["api"]
    }
    if declared_api != expected_api:
        missing = sorted(set(expected_api) - set(declared_api))
        unexpected = sorted(set(declared_api) - set(expected_api))
        changed = sorted(
            name for name in set(declared_api) & set(expected_api)
            if declared_api[name] != expected_api[name]
        )
        raise AssertionError(
            f"Python Api differs from contract. Missing={missing}; "
            f"unexpected={unexpected}; changed signatures={changed}"
        )

    scripts = [path.read_text(encoding="utf-8") for path in SCRIPT_FILES]
    javascript = "\n".join(scripts)
    frontend_api = set(re.findall(r"\bapi\(\)\.([A-Za-z_]\w*)\s*\(", javascript))
    if frontend_api != set(expected_api):
        raise AssertionError(
            f"Frontend API calls differ from contract. "
            f"Missing={sorted(set(expected_api) - frontend_api)}; "
            f"unexpected={sorted(frontend_api - set(expected_api))}"
        )

    handled_events = set(re.findall(r'case\s+"([^"]+)"\s*:', javascript))
    expected_events = set(contract["events"])
    if handled_events != expected_events:
        raise AssertionError(
            f"Frontend event handlers differ from contract. "
            f"Missing={sorted(expected_events - handled_events)}; "
            f"unexpected={sorted(handled_events - expected_events)}"
        )

    emitted = emitted_events(python_source)
    if emitted != expected_events:
        raise AssertionError(
            f"Python event output differs from contract. "
            f"Missing={sorted(expected_events - emitted)}; "
            f"unexpected={sorted(emitted - expected_events)}"
        )

    print(f"Desktop bridge contract v{contract['version']}: OK")
    print(f"  API methods and signatures: {len(expected_api)}")
    print(f"  shared UI events: {len(expected_events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
