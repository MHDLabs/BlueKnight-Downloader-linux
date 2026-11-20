"""Where downloads land, and where cookies come from. Shared by the GUI and
the standalone scripts."""

import contextlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Which desktop platform is this.
# ---------------------------------------------------------------------------
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = not (IS_WINDOWS or IS_MACOS)
OS_TAG = "win" if IS_WINDOWS else "mac" if IS_MACOS else "linux"
# Only Windows puts a suffix on an executable. Every bundled tool name is built
# from this, so `yt-dlp.exe` and `yt-dlp` are the same line of code.
EXE = ".exe" if IS_WINDOWS else ""
ARCH = "arm64" if (platform.machine() or "").lower() in {
    "arm64", "aarch64", "armv8l"} else "x64"

# PyInstaller's bootloader hands the frozen process a set of _PYI*/_MEIPASS2
# variables pointing at this app's unpacked bundle, and child processes inherit
# them. Any other PyInstaller-built tool we launch — yt-dlp.exe is one — sees
# them, notices its parent is a different executable, and refuses to start with
# "Security validation failure" (PyInstaller >= 6.9). The bootloader has already
# done its job by the time Python runs, so drop them here, once, for every
# subprocess the app will ever start.
for _leaked in [k for k in os.environ if k.startswith("_PYI") or k == "_MEIPASS2"]:
    del os.environ[_leaked]

ROOT_NAME = "BlueKnightdownloader"
SOURCES = {
    "spotify": "Spotify",
    "youtube": "YouTube",
    "ytmusic": "YouTube Music",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "soundcloud": "SoundCloud",
    "x": "X",
    "general": "Video",
    "pdf": "Documents & Ebooks",
    "converted": "Converted",
}

# yt-dlp browser name -> the profile directory that only exists once it is installed.
# Firefox first: on Windows, Chrome and Edge encrypt their cookie DB with DPAPI and
# yt-dlp often cannot decrypt it, while Firefox stores a plain SQLite file.
# Firefox first everywhere: it keeps cookies in a plain SQLite file that can be
# read while it runs. Every Chromium browser below holds an exclusive lock on
# its own database whenever it is open. Names are the ones yt-dlp accepts for
# --cookies-from-browser; the path is passed explicitly as `name:path` because
# yt-dlp only knows each browser's default location, and the interesting
# installs — Opera GX above all — do not live there.
_BROWSER_DIRS = {
    "win32": [
        ("firefox", "~/AppData/Roaming/Mozilla/Firefox"),
        ("librewolf", "~/AppData/Roaming/librewolf"),
        ("opera", "~/AppData/Roaming/Opera Software/Opera GX Stable"),
        ("opera", "~/AppData/Roaming/Opera Software/Opera Stable"),
        ("opera", "~/AppData/Roaming/Opera Software/Opera Crypto Stable"),
        ("brave", "~/AppData/Local/BraveSoftware/Brave-Browser/User Data"),
        ("vivaldi", "~/AppData/Local/Vivaldi/User Data"),
        ("edge", "~/AppData/Local/Microsoft/Edge/User Data"),
        ("chrome", "~/AppData/Local/Google/Chrome/User Data"),
        ("chromium", "~/AppData/Local/Chromium/User Data"),
        ("whale", "~/AppData/Local/Naver/Naver Whale/User Data"),
    ],
    "darwin": [
        ("firefox", "~/Library/Application Support/Firefox"),
        ("safari", "~/Library/Safari"),
        ("opera", "~/Library/Application Support/com.operasoftware.OperaGX"),
        ("opera", "~/Library/Application Support/com.operasoftware.Opera"),
        ("brave", "~/Library/Application Support/BraveSoftware/Brave-Browser"),
        ("vivaldi", "~/Library/Application Support/Vivaldi"),
        ("edge", "~/Library/Application Support/Microsoft Edge"),
        ("chrome", "~/Library/Application Support/Google/Chrome"),
        ("chromium", "~/Library/Application Support/Chromium"),
    ],
    "linux": [
        ("firefox", "~/.mozilla/firefox"),
        ("librewolf", "~/.librewolf"),
        ("opera", "~/.config/opera-gx"),
        ("opera", "~/.config/opera"),
        ("brave", "~/.config/BraveSoftware/Brave-Browser"),
        ("vivaldi", "~/.config/vivaldi"),
        ("edge", "~/.config/microsoft-edge"),
        ("chrome", "~/.config/google-chrome"),
        ("chromium", "~/.config/chromium"),
    ],
}

# How each install is labelled in the log, keyed by a folder-name fragment.
_BROWSER_LABELS = {"opera gx": "Opera GX", "opera crypto": "Opera Crypto",
                   "opera stable": "Opera", "librewolf": "LibreWolf"}


def app_dir():
    """The folder the app actually lives in, frozen or not.

    On macOS the executable sits three levels down inside the .app bundle,
    which is read-only and not where a user would look for downloads; "next to
    the app" there means next to the bundle.
    """
    override = os.environ.get("BLUEKNIGHT_HOME")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        here = Path(sys.executable).resolve().parent
        if IS_MACOS and here.match("*.app/Contents/MacOS"):
            return here.parents[2]
        return here
    return Path(__file__).resolve().parent



# Only updater-managed application data is eligible for the portable migration.
# Downloads and cookie sessions deliberately live outside this directory.
_PORTABLE_MIGRATION_DIRS = ("tools", "ffmpeg", "plugins", "python-engines")
_PORTABLE_MIGRATION_MARKER = ".portable-migration-v1"
_PORTABLE_TRANSIENT_SUFFIXES = (".part", ".new", ".tmp", ".lock")


def _user_data_dir(name):
    """The normal per-user data location, regardless of portable mode."""
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA")
                    or Path.home() / "AppData" / "Local")
    elif IS_MACOS:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME")
                    or Path.home() / ".local" / "share")
    return base / name


def _is_portable_transient(name):
    return name.lower().endswith(_PORTABLE_TRANSIENT_SUFFIXES)


def _write_text_atomically(path, content):
    """Replace one small metadata file only after its full contents are ready."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=path.parent,
                prefix=f".{path.name}-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, path)
        return True
    except OSError:
        return False
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                temporary.unlink()


def _copy_portable_tree(source, destination):
    """Copy missing regular files, never following symlinks or replacing files."""
    if source.is_symlink() or not source.is_dir():
        return True
    if destination.is_symlink():
        return False

    try:
        destination.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    if destination.is_symlink() or not destination.is_dir():
        return False

    complete = True
    walk_errors = []

    def remember_walk_error(error):
        walk_errors.append(error)

    for current, directories, filenames in os.walk(
            source, topdown=True, followlinks=False, onerror=remember_walk_error):
        current_path = Path(current)
        directories[:] = [
            name for name in directories
            if not (current_path / name).is_symlink()
            and not _is_portable_transient(name)
        ]
        relative = current_path.relative_to(source)
        destination_dir = destination / relative
        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            complete = False
            directories.clear()
            continue
        if destination_dir.is_symlink() or not destination_dir.is_dir():
            complete = False
            directories.clear()
            continue

        for name in filenames:
            if _is_portable_transient(name):
                continue
            source_file = current_path / name
            if source_file.is_symlink() or not source_file.is_file():
                continue
            destination_file = destination_dir / name
            if os.path.lexists(destination_file):
                continue
            try:
                shutil.copy2(source_file, destination_file)
            except FileExistsError:
                # A file created by another process wins; never overwrite it.
                continue
            except OSError:
                # Remove a partial file produced by a failed copy so a later
                # launch can retry instead of treating it as migrated data.
                with contextlib.suppress(OSError):
                    destination_file.unlink()
                complete = False

    return complete and not walk_errors


def _rebase_portable_engine_registry(source_root, destination_root):
    """Rewrite copied absolute wheel paths to their new portable location."""
    source_engines = (source_root / "python-engines").resolve()
    destination_engines = (destination_root / "python-engines").resolve()
    registry = destination_engines / "registry.json"
    if not os.path.lexists(registry):
        return True
    if registry.is_symlink() or not registry.is_file():
        return False

    try:
        records = json.loads(registry.read_text("utf-8"))
    except (OSError, ValueError):
        # A malformed old registry is already ignored by the updater. Do not
        # block migration of otherwise usable native tools because of it.
        return True
    if not isinstance(records, dict):
        return True

    changed = False
    for record in records.values():
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            continue
        try:
            old_path = Path(record["path"]).expanduser().resolve()
            relative = old_path.relative_to(source_engines)
            new_path = destination_engines / relative
        except (OSError, ValueError):
            continue
        if new_path.is_dir():
            record["path"] = str(new_path.resolve())
            changed = True

    if not changed:
        return True
    return _write_text_atomically(registry, json.dumps(records, indent=2) + "\n")


def _migrate_portable_data(source_root, destination_root):
    """One-time copy of known managed data; the original user data is retained."""
    marker = destination_root / _PORTABLE_MIGRATION_MARKER
    if os.path.lexists(marker):
        return

    try:
        if source_root.resolve() == destination_root.resolve():
            return
    except OSError:
        return

    sources = []
    for name in _PORTABLE_MIGRATION_DIRS:
        source = source_root / name
        if source.is_dir() and not source.is_symlink():
            sources.append((source, destination_root / name))
    if not sources:
        return

    try:
        destination_root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    complete = True
    for source, destination in sources:
        if not _copy_portable_tree(source, destination):
            complete = False
    if not complete:
        return
    if not _rebase_portable_engine_registry(source_root, destination_root):
        return

    _write_text_atomically(marker, "portable-migration-v1\n")


def app_data_dir(name="SpotifyDownloader"):
    """Writable application state, with an opt-in portable package mode.

    Official desktop archives include a portable.mode marker beside the
    executable. In that mode, updater-managed data lives below data/ next to
    the program. On first use, known managed folders are copied from the old
    per-user location without deleting or overwriting anything. Downloads and
    cookie sessions are not part of this migration. BLUEKNIGHT_DATA always
    takes precedence and disables automatic migration.
    """
    override = os.environ.get("BLUEKNIGHT_DATA")
    if override:
        return Path(override)
    home = app_dir()
    if (home / "portable.mode").is_file():
        destination = home / "data" / name
        _migrate_portable_data(_user_data_dir(name), destination)
        return destination
    return _user_data_dir(name)



def download_root(base=None):
    return Path(base).expanduser() if base else app_dir() / ROOT_NAME


def download_dir(source, base=None):
    """Per-source folder, created on demand. source: a key of SOURCES.

    A folder that cannot be made is the end of the download, so it says which
    folder and why rather than surfacing an errno the person reading it cannot
    act on. The shell has already proved the root writable before the engine
    starts; this catches the rest — a volume that filled up or was unmounted
    between then and now.
    """
    folder = download_root(base) / SOURCES[source]
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as failure:
        raise RuntimeError(
            f"The download folder could not be created: {folder}. "
            f"{failure.strerror or failure}. Check there is free space, and "
            f"that the folder is on storage that is still attached."
        ) from failure
    if not os.access(folder, os.W_OK):
        raise RuntimeError(
            f"The download folder exists but cannot be written to: {folder}. "
            f"Pick a different folder in the app, or free some space.")
    return folder


COOKIE_FAILURE = re.compile(
    r"could not copy .*cookie database|could not find .*cookies database|"
    r"failed to decrypt|unable to (?:read|open) .*cookie", re.I)


# "Get cookies.txt LOCALLY" exports as <domain>_cookies.txt; other extensions
# use cookies.txt or cookies-<site>.txt. Match the shape, not a fixed list.
COOKIE_FILE_GLOBS = ("cookies.txt", "*cookies*.txt")

# Each site keeps its own folder. One shared file meant an Instagram export could
# be offered to YouTube, where it can only fail; separate folders mean a site's
# cookies cannot reach another site even by accident.
COOKIE_DIR_NAME = "cookies"
# YouTube Music has no folder of its own here: music.youtube.com IS youtube.com,
# so it shares that session rather than asking for a second login.
SITE_DOMAINS = {"youtube": "youtube.com", "instagram": "instagram.com",
                "tiktok": "tiktok.com", "spotify": "spotify.com",
                "soundcloud": "soundcloud.com", "x": "x.com"}
# The cookie that means "signed in". Anything less is just a visitor.
SITE_SESSION_COOKIES = {
    "youtube": ("SID", "__Secure-3PSID", "SAPISID", "__Secure-1PSID"),
    "instagram": ("sessionid",),
    "tiktok": ("sessionid", "sessionid_ss"),
    "spotify": ("sp_dc", "sp_key"),
    # yt-dlp's SoundCloud extractor verifies this browser token with
    # api-auth.soundcloud.com and then requests account-entitled formats.
    "soundcloud": ("oauth_token",),
    "x": ("auth_token",),
}
REGISTRY_NAME = "registry.json"


def write_netscape_jar(cookies, path):
    """Atomically save browser cookies with owner-only permissions on POSIX."""
    path = Path(path)
    lines = ["# Netscape HTTP Cookie File",
             "# Written by Blue Knight Downloader. Editing this is not needed.", ""]
    written = 0
    for cookie in cookies:
        for name, morsel in cookie.items():
            domain = morsel["domain"] or ""
            if not domain:
                continue
            expires = morsel["expires"]
            if expires:
                with contextlib.suppress(Exception):
                    expires = int(time.mktime(
                        time.strptime(expires, "%a, %d %b %Y %H:%M:%S %Z")))
            lines.append("\t".join([
                domain,
                "TRUE" if domain.startswith(".") else "FALSE",
                morsel["path"] or "/",
                "TRUE" if morsel["secure"] else "FALSE",
                str(expires or int(time.time()) + 60 * 60 * 24 * 180),
                name,
                morsel.value,
            ]))
            written += 1

    # Create beside the destination so os.replace stays on one filesystem.
    # mkstemp starts with owner-only permissions on POSIX; keep that mode when
    # the completed jar replaces an older, potentially over-permissive file.
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            if not IS_WINDOWS:
                os.fchmod(stream.fileno(), 0o600)
            stream.write("\n".join(lines) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if not IS_WINDOWS:
            path.chmod(0o600)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
    return written


def cookie_dir(site=None):
    """Where the app keeps private cookie jars. One folder per site."""
    root = app_dir() / COOKIE_DIR_NAME
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not IS_WINDOWS:
        root.chmod(0o700)

    if not site:
        return root

    folder = root / site
    folder.mkdir(mode=0o700, exist_ok=True)
    if not IS_WINDOWS:
        folder.chmod(0o700)
    return folder


def host_matches(host, domain):
    """Is this cookie host the site, or a subdomain of it?

    Substring matching was wrong in a way that only bites on short domains:
    "x.com" is inside "netflix.com", so a Netflix jar read as an X session and
    got handed to X — exactly the cross-site leak the per-site folders prevent.
    """
    host = (host or "").strip().lstrip(".").rstrip(".").lower()
    domain = (domain or "").strip().lstrip(".").rstrip(".").lower()
    return bool(domain) and (host == domain or host.endswith("." + domain))


def jar_line_host(line):
    """The domain field of a Netscape cookie line, or "" if it is not one."""
    parts = line.split("\t")
    return parts[0] if len(parts) >= 7 else ""


def jar_line_matches_domain(line, domain):
    """Whether a Netscape cookie can belong to this host/site boundary.

    Site-specific callers pass a registrable domain (``youtube.com``), while
    the General downloader passes the exact URL hostname. Accepting both
    directions is safe only when the jar's include-subdomains flag permits it.
    """
    parts = line.split("\t")
    if len(parts) < 7:
        return False
    cookie_host = parts[0].strip().lstrip(".").rstrip(".").lower()
    wanted = (domain or "").strip().lstrip(".").rstrip(".").lower()
    if not cookie_host or not wanted:
        return False
    if host_matches(cookie_host, wanted):
        return True
    include_subdomains = parts[1].strip().upper() == "TRUE"
    return include_subdomains and host_matches(wanted, cookie_host)


def site_for_domain(domain):
    """Which site a domain belongs to, or None."""
    for site, site_domain in SITE_DOMAINS.items():
        if domain and host_matches(domain, site_domain):
            return site
    return None


def jar_summary(path, site=None):
    """What is in a jar: count, session presence, and session expiry."""
    names, count, expiry = set(), 0, None
    wanted = SITE_SESSION_COOKIES.get(site or "", ())
    try:
        for line in Path(path).read_text("utf-8", "replace").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 7:
                continue
            count += 1
            names.add(parts[5])
            with contextlib.suppress(ValueError):
                stamp = int(parts[4])
                # Short-lived analytics cookies must not make a valid login
                # disappear from the registry. Only the authentication cookie
                # controls the stored session's lifetime.
                if parts[5] in wanted and stamp > 0 and (expiry is None or stamp < expiry):
                    expiry = stamp
    except OSError:
        return 0, False, None
    return count, any(name in names for name in wanted), expiry


def registry_path():
    return cookie_dir() / REGISTRY_NAME


def read_registry():
    """What the app knows about the jars it has written."""
    try:
        return json.loads(registry_path().read_text("utf-8"))
    except Exception:
        return {}


def record_jar(site, path, source):
    """Remember a jar, so its state can be shown and its age judged later."""
    count, has_session, expiry = jar_summary(path, site)
    registry = read_registry()
    registry[site] = {
        "jar": str(path),
        "source": source,
        "cookies": count,
        "signed_in": has_session,
        "saved_at": int(time.time()),
        "expires_at": expiry,
    }
    with contextlib.suppress(OSError):
        registry_path().write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return registry[site]


def registry_entry(site):
    """The recorded jar for a site, dropped if the file is gone or expired."""
    entry = read_registry().get(site)
    if not entry:
        return None
    if not Path(entry["jar"]).is_file():
        return None
    if entry.get("expires_at") and entry["expires_at"] < time.time():
        return None
    return entry


def cookie_files(domain=None):
    """Hand-exported cookie jars, newest first.

    Extensions drop these in Downloads under whatever name they like, and people
    leave them there, so the obvious places are searched rather than demanding
    an exact filename. With a domain given, only jars that actually carry that
    site are returned — a YouTube jar is no use to Instagram and vice versa.
    """
    site = site_for_domain(domain) if domain else None
    # The site's own folder first, then the shared places people drop exports.
    # Another site's folder is never searched, so its jars cannot leak across.
    folders = [cookie_dir(site)] if site else [cookie_dir()]
    folders += [app_dir(), download_root(), Path.home() / "Downloads"]

    seen, found = set(), []
    for folder in folders:
        for pattern in COOKIE_FILE_GLOBS:
            for path in sorted(folder.glob(pattern)):
                key = str(path).lower()
                if key in seen or not path.is_file():
                    continue
                seen.add(key)
                if domain and not jar_has_domain(path, domain):
                    continue
                found.append(path)
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def jar_has_domain(path, domain):
    """Does this Netscape jar hold cookies for the given site?"""
    try:
        for line in path.read_text("utf-8", "replace").splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                if jar_line_matches_domain(line, domain):
                    return True
    except OSError:
        return False
    return False


def cookie_candidates(domain=None):
    """Every place cookies could come from, best first, as ('file'|'browser', value).

    A browser's `Cookies` file is a SQLite database, NOT the Netscape cookies.txt
    that yt-dlp's `cookiefile` expects — handing one to `cookiefile` fails or,
    worse, silently reads nothing. Only a real cookies.txt goes down that path;
    browsers go through `cookiesfrombrowser`, which knows how to read the DB.

    A list, not a single pick, because "installed" does not mean "readable": a
    Chromium browser that is currently running holds a lock on its cookie DB
    (yt-dlp #7271), and Chrome 127+ encrypts it app-bound so DPAPI cannot open it
    at all (yt-dlp #10927). Exported files come first for exactly that reason —
    they are the only source nothing else can take away.
    """
    found = [("file", str(path)) for path in cookie_files(domain)]
    for name, profile in _BROWSER_DIRS.get(sys.platform, _BROWSER_DIRS["linux"]):
        path = os.path.expanduser(profile)
        if os.path.isdir(path):
            found.append(("browser", name, path))
    return found


def candidate_label(candidate):
    """What to call this cookie source in a message a person reads."""
    if candidate[0] == "file":
        return os.path.basename(candidate[1])
    path = (candidate[2] if len(candidate) > 2 else "").lower()
    for fragment, label in _BROWSER_LABELS.items():
        if fragment in path:
            return label
    return candidate[1].title()


def locked_by_browser(candidate):
    """True when a running browser holds this profile's cookie database.

    Chromium keeps that file open exclusively, so no amount of retrying or
    permission juggling gets at it — the browser has to close first.
    """
    if candidate[0] != "browser" or len(candidate) < 3:
        return False
    root = Path(candidate[2])
    for db in (root / "Default" / "Network" / "Cookies", root / "Default" / "Cookies",
               root / "Network" / "Cookies", root / "Cookies"):
        if db.is_file():
            try:
                with open(db, "rb"):
                    return False
            except PermissionError:
                return True
            except OSError:
                return False
    return False


def cookie_source():
    """The first candidate, or None. For display and for one-shot callers."""
    found = cookie_candidates()
    return found[0] if found else None


def ytdlp_cookie_opts(candidate=None):
    """A candidate as yt-dlp Python options."""
    candidate = candidate or cookie_source()
    if not candidate:
        return {}
    if candidate[0] == "file":
        return {"cookiefile": candidate[1]}
    profile = candidate[2] if len(candidate) > 2 else None
    return {"cookiesfrombrowser": (candidate[1], profile)}


def ytdlp_cookie_args(candidate=None):
    """A candidate as yt-dlp command-line arguments."""
    candidate = candidate or cookie_source()
    if not candidate:
        return []
    if candidate[0] == "file":
        return ["--cookies", candidate[1]]
    spec = candidate[1]
    if len(candidate) > 2:
        # yt-dlp only knows each browser's default folder; Opera GX and friends
        # are somewhere else entirely, so the profile is named outright.
        spec = f"{spec}:{candidate[2]}"
    return ["--cookies-from-browser", spec]


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        got = {name: download_dir(name, tmp) for name in SOURCES}
        assert all(p.is_dir() for p in got.values()), got

        # A folder that cannot be made ends the download, so it has to say
        # which one and why rather than leaking an errno nobody can act on.
        blocked = os.path.join(tmp, "a-file-not-a-folder")
        open(blocked, "w").close()
        try:
            download_dir("youtube", blocked)
        except RuntimeError as failure:
            assert "could not be created" in str(failure), failure
            assert "a-file-not-a-folder" in str(failure), failure
        else:
            raise AssertionError("a blocked download folder reported success")
        assert len({str(p) for p in got.values()}) == len(SOURCES), got
        assert got["instagram"].parent == Path(tmp), got["instagram"]
    assert download_root().name == ROOT_NAME
    assert download_root().parent == app_dir()

    # Release archives opt into portable data next to the executable.
    _old_home = os.environ.get("BLUEKNIGHT_HOME")
    _old_data = os.environ.get("BLUEKNIGHT_DATA")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["BLUEKNIGHT_HOME"] = tmp
            os.environ.pop("BLUEKNIGHT_DATA", None)
            (Path(tmp) / "portable.mode").touch()
            assert app_data_dir() == Path(tmp) / "data" / "SpotifyDownloader"
            override = Path(tmp) / "custom-data"
            os.environ["BLUEKNIGHT_DATA"] = str(override)
            assert app_data_dir() == override
    finally:
        if _old_home is None:
            os.environ.pop("BLUEKNIGHT_HOME", None)
        else:
            os.environ["BLUEKNIGHT_HOME"] = _old_home
        if _old_data is None:
            os.environ.pop("BLUEKNIGHT_DATA", None)
        else:
            os.environ["BLUEKNIGHT_DATA"] = _old_data

    # Whatever the machine has, the two renderings must agree — and a browser must
    # never be handed to cookiefile.
    found, args, opts = cookie_source(), ytdlp_cookie_args(), ytdlp_cookie_opts()
    if found is None:
        assert args == [] and opts == {}, (args, opts)
    elif found[0] == "file":
        assert args == ["--cookies", found[1]] and opts == {"cookiefile": found[1]}
    else:
        assert args == ["--cookies-from-browser", f"{found[1]}:{found[2]}"], args
        assert opts == {"cookiesfrombrowser": (found[1], found[2])}, opts
    assert cookie_candidates()[:1] == ([] if found is None else [found])

    # A profile yt-dlp could never find on its own must still be addressable.
    gx = ("browser", "opera", r"C:\Users\x\AppData\Roaming\Opera Software\Opera GX Stable")
    assert ytdlp_cookie_args(gx) == ["--cookies-from-browser", f"opera:{gx[2]}"]
    assert candidate_label(gx) == "Opera GX", candidate_label(gx)
    assert candidate_label(("browser", "firefox", "/x/firefox")) == "Firefox"

    # A locked Chromium DB must be recognised as "try the next candidate", and an
    # ordinary download failure must not be.
    assert COOKIE_FAILURE.search("ERROR: Could not copy Chrome cookie database. See ...")
    assert COOKIE_FAILURE.search("ERROR: could not find firefox cookies database in ...")
    assert not COOKIE_FAILURE.search("ERROR: Restricted Video: Sign in to confirm your age")

    # A jar belongs to one site. Short domains are where substring matching leaked:
    # "x.com" sits inside "netflix.com", and a cookie value can contain anything.
    assert host_matches("x.com", "x.com") and host_matches(".api.x.com", "x.com")
    assert not host_matches("netflix.com", "x.com")
    assert not host_matches("notyoutube.com", "youtube.com")
    assert jar_line_matches_domain(
        ".example.com\tTRUE\t/\tTRUE\t0\tsession\tx", "video.example.com")
    assert not jar_line_matches_domain(
        "example.com\tFALSE\t/\tTRUE\t0\tsession\tx", "video.example.com")
    assert not jar_line_matches_domain(
        ".notexample.com\tTRUE\t/\tTRUE\t0\tsession\tx", "example.com")
    assert site_for_domain("netflix.com") is None
    assert site_for_domain("x.com") == "x" and site_for_domain("www.youtube.com") == "youtube"
    with tempfile.TemporaryDirectory() as tmp:
        jar = Path(tmp) / "cookies.txt"
        jar.write_text("# comment\n"
                       ".netflix.com\tTRUE\t/\tTRUE\t0\tNetflixId\tx.com-lookalike\n",
                       encoding="utf-8")
        assert not jar_has_domain(jar, "x.com"), "a Netflix jar must not read as X"
        assert jar_has_domain(jar, "netflix.com")
    print("ok", cookie_candidates())
