"""Pure fallback and retry policy for media download engines.

This module owns decisions that do not need the desktop, WebView, subprocesses
or network. The desktop imports the same constants and delegates its existing
methods here so behavior remains compatible and independently testable.
"""

import re


# YouTube is rolling out "PO tokens", and a client that needs one cannot serve a
# download without it. Per yt-dlp's PO Token Guide the exceptions are android_vr,
# web_embedded and tv — so those are the ones worth retrying as. tv_simply,
# web_safari and mweb all need a token, which is why they answered the earlier
# attempts with "Requested format is not available" rather than a video.
# Three clients ask YouTube for no proof-of-origin token: android_vr, tv and
# web_embedded. That list is from yt-dlp's PO Token Guide, and it is not the
# same as the REQUIRE_PO_TOKEN flag in its client table — that flag is about
# the player response, while the token that gates the media itself is the GVS
# one. android and ios pass the flag and still need a GVS or player token to
# fetch a stream, which arrives as exactly the 403 this ladder exists to climb
# out of. They are not rungs; they are the hole.
# Between one engine and the next. Long enough to not read as a burst, short
# enough that nobody watching a failed download counts it.
ENGINE_SPACING_SECONDS = 3.0
YT_NO_TOKEN_CLIENTS = frozenset({"android_vr", "tv", "web_embedded"})

# What a failure was actually about, so the answer can match the question.
# Switching extractor is the right move for some of these and a waste of the
# next few minutes for others.
FAILURE_EXTRACTOR = "extractor"        # this engine could not read the page
FAILURE_NO_FORMATS = "no-formats"      # read it, nothing offered
FAILURE_SABR = "sabr"                  # offered, but nothing fetchable
FAILURE_CDN_403 = "cdn-403"            # a media URL refused after the fact
FAILURE_BOT_CHECK = "bot-check"        # this client was refused as automated
FAILURE_IP_BLOCKED = "ip-blocked"      # every client was, which is different

# Each rung is either token-free or able to spend a session, and the ones that
# can spend one come after the ones that need nothing.
YT_CLIENT_LADDER = ("android_vr", "web_embedded,tv,default", "tv")
# The rungs that can carry a signed-in session, by yt-dlp's SUPPORTS_COOKIES.
YT_COOKIE_CLIENTS = frozenset({"web_embedded,tv,default", "tv"})

YOUTUBE_MEDIA_DENIED = re.compile(
    r"unable to download (?:video|audio) data.*(?:http error 403|forbidden)|"
    r"http error 403:\s*forbidden|fragment.*http error 403", re.I | re.S)
# On YouTube this does not mean "there is no video here". It means the client
# that answered had no formats it was allowed to offer, which is a thing another
# client can fix — so it belongs to the ladder, not to the give-up path it was
# falling into with every rung still unused.
YOUTUBE_NO_FORMATS = re.compile(
    r"requested format is not available|no video formats found", re.I)
# The warnings that explain an empty format list. yt-dlp prints these and then
# fails with a sentence that does not mention them.
YTDLP_TELLING_WARNING = re.compile(
    r"WARNING:.*(missing a url|sabr|po ?token|formats may be missing|"
    r"skipped as they are missing|only images are available|"
    r"nsig extraction failed|unable to extract nsig|player js)", re.I)
# YouTube's server-side adaptive streaming. When an account or session is in
# that experiment the streams arrive with no direct URL at all, and yt-dlp has
# no support for fetching them — so every client returns an empty list and no
# rung of any ladder can help. Worth saying outright rather than retrying.
# A second engine answers a site that would not answer the first. It cannot
# answer a full disk, a folder that refuses to be written to, or a person who
# pressed stop — and trying is not merely useless, it buries the real reason
# under a second failure that says something else. These end the run where it
# stands, whatever engines are left.
TERMINAL_FAILURE = re.compile(
    r"no space left|not enough space|disk (?:is )?full|quota exceeded|"
    r"permission denied|access is denied|read-only file system|"
    r"operation not permitted|file name too long|invalid argument|"
    r"cancell?ed|interrupted by user|keyboardinterrupt|"
    r"\bdrm\b|widevine|encrypted content", re.I)
YOUTUBE_SABR = re.compile(
    r"sabr|missing a url|skipped as they are missing a url", re.I)
PO_TOKEN_PATTERN = re.compile(r"^mweb\.gvs\+[A-Za-z0-9._~=/+-]{20,4096}$")
SIGNIN_DEMANDED = re.compile(
    r"not a bot|sign ?in to confirm|login required|account.*cookies|"
    r"this video is only available|use --cookies", re.I)
GENERAL_CHALLENGE = re.compile(
    r"captcha|cloudflare|cf-chl|attention required|verify (?:that )?you are human|"
    r"not a bot|login required|sign ?in|use --cookies|http error 40[13]|forbidden", re.I)

# What to try when yt-dlp comes back empty-handed. yt-dlp is always first.
ENGINES = {
    "x": ("gallery-dl", "html5", "direct"),
    "instagram": ("gallery-dl",),
    "general": ("youtube-explode", "newpipe", "streamlink", "html5",
                "gallery-dl", "direct"),
    "youtube": ("youtube-explode", "newpipe", "youtube-js"),
    "ytmusic": ("youtube-explode", "newpipe", "youtube-js"),
    "soundcloud": ("newpipe",),
}

# yt-dlp saying "there is no video here" is not the same as yt-dlp failing. The
# first means another engine should look; the second means the job is over.
NO_VIDEO_FOR_YTDLP = re.compile(
    r"no video could be found|there'?s no video|unsupported url|"
    r"no media found|no video formats found|requested format is not available", re.I)


def may_fall_back(is_downloading, detail):
    """Whether another engine can usefully try after this failure."""
    if not is_downloading:
        return False
    return not TERMINAL_FAILURE.search(str(detail or ""))


def classify_youtube_refusal(spent_clients):
    """Classify a refusal by whether every token-free YouTube client was tried."""
    refused = set()
    for rung in spent_clients:
        refused.update(name.strip() for name in str(rung).split(","))
    if refused >= YT_NO_TOKEN_CLIENTS:
        return FAILURE_IP_BLOCKED
    return FAILURE_BOT_CHECK

YOUTUBE_KINDS = {"youtube", "ytmusic"}


def plan_next_extractor_retry(kind, attempt, spent, challenge=False,
                              has_po_token_provider=False):
    """Plan one extractor-only retry without performing side effects.

    The caller owns the spent set and any logging. Keeping this decision pure
    makes the one-time retry ladder deterministic and independently testable.
    The returned mapping contains the spent key, a reason code, and the next
    attempt dictionary; None means this part of the ladder is exhausted.
    """
    if kind == "general" and challenge and "impersonate" not in spent:
        return {
            "spent_key": "impersonate",
            "reason": "impersonate",
            "attempt": {**attempt, "impersonate": True},
        }

    if kind not in YOUTUBE_KINDS:
        return None

    for index, clients in enumerate(YT_CLIENT_LADDER):
        key = f"clients-{index}"
        if key not in spent:
            return {
                "spent_key": key,
                "reason": "youtube-client",
                "attempt": {**attempt, "clients": clients, "fresh": True},
            }

    # Some signed-in accounts are served no direct URLs on any player client.
    # One signed-out attempt checks the session as the variable.
    if attempt.get("cookies") and "no-cookies" not in spent:
        return {
            "spent_key": "no-cookies",
            "reason": "no-cookies",
            "attempt": {
                **attempt, "cookies": None,
                "clients": YT_CLIENT_LADDER[0], "fresh": True,
            },
        }

    if has_po_token_provider and "po-token" not in spent:
        return {
            "spent_key": "po-token",
            "reason": "po-token",
            "attempt": {
                **attempt, "clients": "mweb,default",
                "po_token": True, "fresh": True,
            },
        }

    return None
