"""Small cross-platform helpers for launching tools and reading their versions.

The downloader keeps subprocess defaults consistent on Windows, Linux, and
macOS. Python packages are only probed for version reporting; command execution
always goes through the executable or entry point selected by the engine.
"""

import os
import subprocess

from blueknight_paths import IS_WINDOWS

NO_WINDOW = ({"creationflags": subprocess.CREATE_NO_WINDOW}
             if IS_WINDOWS and hasattr(subprocess, "CREATE_NO_WINDOW") else {})

MODULES = {
    "yt-dlp": "yt_dlp",
    "gallery-dl": "gallery_dl",
    "streamlink": "streamlink",
}


def popen(cmd, **kwargs):
    """Start a child process with consistent text and stream defaults."""
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.STDOUT)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    return subprocess.Popen(cmd, **{**NO_WINDOW, **kwargs})


def run(cmd, **kwargs):
    """Run a child process to completion with consistent output handling."""
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.STDOUT)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    return subprocess.run(cmd, **{**NO_WINDOW, **kwargs})


def module_version(name):
    """Return an installed Python tool's version, or 'unknown'."""
    module_name = MODULES.get(os.path.splitext(os.path.basename(str(name)))[0])
    if not module_name:
        return "unknown"
    try:
        module = __import__(module_name, fromlist=["*"])
        return str(getattr(module, "__version__", "unknown"))
    except Exception:
        return "unknown"


def demo():
    """Self-check the process wrappers."""
    result = run([os.sys.executable, "-c", "print('hello'); raise SystemExit(3)"])
    assert result.returncode == 3, result.returncode
    assert "hello" in result.stdout, result.stdout

    child = popen([os.sys.executable, "-c",
                   "[print(i, flush=True) for i in range(3)]"])
    assert [line.strip() for line in child.stdout] == ["0", "1", "2"]
    assert child.wait() == 0
    print("pyshell: ok")


if __name__ == "__main__":
    demo()
