"""Pure URL, filename, document and HTML validation helpers.

This module deliberately has no desktop, WebView, downloader or network
initialization. The desktop imports these names to preserve its existing API.
"""

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from blueknight_paths import host_matches as _host_matches


MEDIA_PATTERNS = {
    "youtube": re.compile(r"https?://(?:[\w-]+\.)*(?:youtube\.com|youtu\.be)/", re.I),
    "ytmusic": re.compile(r"https?://music\.youtube\.com/", re.I),
    "tiktok": re.compile(r"https?://(?:[\w-]+\.)*tiktok\.com/", re.I),
    "instagram": re.compile(r"https?://(?:[\w-]+\.)*instagram\.com/", re.I),
    "soundcloud": re.compile(r"https?://(?:[\w-]+\.)*soundcloud\.com/", re.I),
    "x": re.compile(r"https?://(?:[\w-]+\.)*(?:x\.com|twitter\.com)/", re.I),
}
MEDIA_LABELS = {
    "youtube": "YouTube", "ytmusic": "YouTube Music", "tiktok": "TikTok",
    "instagram": "Instagram", "soundcloud": "SoundCloud", "x": "X",
    "general": "Video",
}
YOUTUBE_DOMAINS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
COOKIE_DOMAINS = {
    "instagram": "instagram.com", "youtube": "youtube.com",
    "ytmusic": "youtube.com", "tiktok": "tiktok.com",
    "soundcloud": "soundcloud.com", "x": "x.com",
}
MEDIA_EXTENSIONS = {
    ".mp4", ".m4v", ".webm", ".mkv", ".mov", ".avi", ".flv", ".ts",
    ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif",
}
PDF_MAGIC = b"%PDF-"


def normalize_media_url(kind, value):
    """Validate a media source and return the URL yt-dlp should receive."""
    if kind not in MEDIA_LABELS:
        raise ValueError("Unsupported download source.")

    value = (value or "").strip()
    if kind == "tiktok" and value.startswith("@"):
        value = f"https://www.tiktok.com/{value}"
    elif kind == "instagram" and value.startswith("@"):
        value = f"https://www.instagram.com/{value[1:].strip('/')}/"

    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Paste a complete http:// or https:// link.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Links containing a username or password are not supported.")

    host = parsed.hostname.rstrip(".").lower()
    if kind == "general":
        if any(_host_matches(host, domain) for domain in YOUTUBE_DOMAINS):
            raise ValueError("YouTube links must use the dedicated YouTube downloader.")
    elif not MEDIA_PATTERNS[kind].search(value):
        raise ValueError(f"That is not a {MEDIA_LABELS[kind]} link.")
    return value


def cookie_domain_for(kind, url):
    """The only cookie domain an attempt may borrow for this URL."""
    fixed = COOKIE_DOMAINS.get(kind)
    if fixed:
        return fixed
    if kind != "general":
        return None
    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".") or None
    except ValueError:
        return None


def youtube_video_id(url):
    """The eleven characters YouTube identifies a video by, or None."""
    match = re.search(r"(?:v=|/shorts/|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})",
                      str(url or ""))
    return match.group(1) if match else None


class PdfLinkParser(HTMLParser):
    """Every href and embed/iframe source on a page, in document order.

    Deliberately not a .pdf-suffix filter: plenty of sites serve documents from
    /download?id=… with no extension anywhere in the URL. What a link actually
    is gets decided by fetching it and looking at the bytes.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        wanted = {"a": "href", "embed": "src", "iframe": "src", "object": "data"}.get(tag)
        if not wanted:
            return
        for name, value in attrs:
            if name == wanted and value:
                self.links.append(value.strip())


class HtmlMediaParser(HTMLParser):
    """Media URLs exposed by ordinary HTML5 markup and social meta tags."""

    META_NAMES = {"og:video", "og:video:url", "og:video:secure_url",
                  "twitter:player:stream", "og:audio", "og:audio:url"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"video", "audio", "source"} and values.get("src"):
            self.links.append(values["src"].strip())
        elif tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key in self.META_NAMES and values.get("content"):
                self.links.append(values["content"].strip())
        elif tag == "a" and values.get("href"):
            path = urlsplit(values["href"]).path.lower()
            if any(path.endswith(ext) for ext in MEDIA_EXTENSIONS):
                self.links.append(values["href"].strip())


class HtmlImageParser(HTMLParser):
    """Likely page images for sites without a gallery-dl extractor."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "img":
            value = (values.get("data-src") or values.get("data-original")
                     or values.get("data-lazy-src") or values.get("data-url"))
            srcset = (values.get("data-srcset") or values.get("data-lazy-srcset")
                      or values.get("srcset"))
            if not value and srcset:
                value = srcset.split(",")[-1].strip().split()[0]
            value = value or values.get("src")
            if value:
                self.links.append(value.strip())
        elif tag == "source" and (values.get("data-srcset") or values.get("srcset")):
            srcset = values.get("data-srcset") or values["srcset"]
            value = srcset.split(",")[-1].strip().split()[0]
            if value:
                self.links.append(value)
        elif tag == "a" and values.get("href"):
            path = urlsplit(values["href"]).path.lower()
            if Path(path).suffix in {".jpg", ".jpeg", ".png", ".webp", ".avif"}:
                self.links.append(values["href"].strip())


def normalize_page_url(value):
    """Validate any http(s) address a person pasted. Returns the URL."""
    value = (value or "").strip()
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Paste a complete http:// or https:// link.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Links containing a username or password are not supported.")
    return value


def safe_filename(name, fallback="document", suffix=".pdf"):
    """A remote-supplied name, reduced to something safe to write.

    The name comes from a server, so it is untrusted input: "../../boot.ini" and
    "CON" are both things a hostile Content-Disposition can say. Only the basename
    survives, and only characters Windows actually accepts.
    """
    name = unquote(name or "").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(". ")
    stem, _, ext = name.rpartition(".")
    if not stem:
        stem, ext = name, ext or suffix.lstrip(".")
    if stem.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                        *(f"LPT{i}" for i in range(1, 10))}:
        stem = f"_{stem}"
    stem = (stem or fallback)[:120]
    ext = (ext if ext.lower() == suffix.lstrip(".") else suffix.lstrip("."))
    return f"{stem}.{ext}"


def detect_document_extension(head, url, content_type=""):
    """Return a validated document suffix, or None for non-document content."""
    path_suffix = Path(urlsplit(url).path).suffix.lower()
    content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if PDF_MAGIC in head[:1024]:
        return ".pdf"
    if head.startswith(b"PK\x03\x04"):
        return ".zip"
    if len(head) >= 68 and head[60:68] == b"BOOKMOBI":
        return path_suffix if path_suffix in {".mobi", ".azw", ".azw3"} else ".mobi"
    if b"<FictionBook" in head[:4096] and path_suffix == ".fb2":
        return ".fb2"
    if head.startswith(b"{\\rtf"):
        return ".rtf"
    if head.startswith(b"AT&TFORM") and b"DJVU" in head[:32]:
        return ".djvu"
    if head.startswith(b"ITSF"):
        return ".chm"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        office = {
            "application/msword": ".doc",
            "application/vnd.ms-excel": ".xls",
            "application/vnd.ms-powerpoint": ".ppt",
        }
        return office.get(content_type, path_suffix if path_suffix in {".doc", ".xls", ".ppt"}
                          else ".doc")
    text_types = {".txt": {"text/plain"}, ".md": {"text/plain", "text/markdown"},
                  ".csv": {"text/csv", "text/plain"}}
    if path_suffix in text_types and content_type in text_types[path_suffix]:
        return path_suffix
    return None
