"""Select PyPI wheels compatible with the running Python interpreter and platform."""

from __future__ import annotations

from packaging.tags import sys_tags
from packaging.utils import InvalidWheelFilename, parse_wheel_filename


def select_compatible_wheel(files, supported_tags=None):
    """Return the highest-priority compatible wheel from one PyPI release.

    supported_tags is injectable for deterministic cross-platform tests.
    At runtime, packaging sys_tags() handles interpreter, ABI and platform
    compatibility, including manylinux and musllinux rules.
    """
    tags = tuple(sys_tags() if supported_tags is None else supported_tags)
    priority = {tag: index for index, tag in enumerate(tags)}
    if not priority:
        return None

    candidates = []
    for item in files or ():
        if not isinstance(item, dict):
            continue
        if item.get("packagetype") != "bdist_wheel" or item.get("yanked", False):
            continue
        filename = item.get("filename", "")
        if not filename:
            continue
        try:
            _name, _version, _build, wheel_tags = parse_wheel_filename(filename)
        except InvalidWheelFilename:
            continue

        rank = min((priority[tag] for tag in wheel_tags if tag in priority), default=None)
        if rank is None:
            continue
        digest = (item.get("digests") or {}).get("sha256")
        if not item.get("url") or not digest:
            continue
        candidates.append((rank, filename, item))

    if not candidates:
        return None
    return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]
