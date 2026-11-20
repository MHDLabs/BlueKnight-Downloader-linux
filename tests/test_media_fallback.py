"""Deterministic tests for media fallback and retry policies."""

import unittest

from blueknight.media.fallback import (
    ENGINES,
    FAILURE_BOT_CHECK,
    FAILURE_IP_BLOCKED,
    GENERAL_CHALLENGE,
    NO_VIDEO_FOR_YTDLP,
    PO_TOKEN_PATTERN,
    SIGNIN_DEMANDED,
    TERMINAL_FAILURE,
    YT_CLIENT_LADDER,
    YT_COOKIE_CLIENTS,
    YT_NO_TOKEN_CLIENTS,
    YOUTUBE_MEDIA_DENIED,
    YOUTUBE_NO_FORMATS,
    YOUTUBE_SABR,
    YTDLP_TELLING_WARNING,
    classify_youtube_refusal,
    may_fall_back,
)


class FallbackDecisionTests(unittest.TestCase):
    def test_stopped_download_never_falls_back(self):
        self.assertFalse(may_fall_back(False, "extractor could not read the page"))
        self.assertFalse(may_fall_back(False, ""))
        self.assertFalse(may_fall_back(False, "No space left on device"))

    def test_storage_and_filesystem_failures_are_terminal(self):
        failures = (
            "No space left on device",
            "Not enough space to write the file",
            "Disk full",
            "Disk is full",
            "Quota exceeded",
            "Permission denied",
            "Access is denied",
            "Read-only file system",
            "Operation not permitted",
            "File name too long",
            "Invalid argument",
        )
        for detail in failures:
            with self.subTest(detail=detail):
                self.assertFalse(may_fall_back(True, detail))

    def test_cancellation_and_drm_failures_are_terminal(self):
        failures = (
            "Download cancelled",
            "Download canceled",
            "Interrupted by user",
            "KeyboardInterrupt",
            "Widevine DRM",
            "DRM protected content",
            "Encrypted content",
        )
        for detail in failures:
            with self.subTest(detail=detail):
                self.assertFalse(may_fall_back(True, detail))

    def test_recoverable_extractor_and_network_failures_can_fall_back(self):
        failures = (
            "Unable to extract player response",
            "HTTP Error 403: Forbidden",
            "Unsupported URL",
            "The extractor returned no usable streams",
            "Connection reset by peer",
            "A site challenge blocked this client",
        )
        for detail in failures:
            with self.subTest(detail=detail):
                self.assertTrue(may_fall_back(True, detail))

    def test_empty_error_matches_existing_policy(self):
        self.assertTrue(may_fall_back(True, None))
        self.assertTrue(may_fall_back(True, ""))


class YouTubeRefusalPolicyTests(unittest.TestCase):
    def test_token_free_client_set_and_ladder_are_explicit(self):
        self.assertEqual(YT_NO_TOKEN_CLIENTS,
                         frozenset({"android_vr", "tv", "web_embedded"}))
        self.assertEqual(YT_CLIENT_LADDER,
                         ("android_vr", "web_embedded,tv,default", "tv"))
        self.assertEqual(YT_COOKIE_CLIENTS,
                         frozenset({"web_embedded,tv,default", "tv"}))

    def test_partial_client_refusals_are_bot_checks(self):
        cases = (
            set(),
            {"android_vr"},
            {"web_embedded,tv,default"},
            {"tv"},
            {"android_vr", "tv"},
        )
        for spent in cases:
            with self.subTest(spent=spent):
                self.assertEqual(classify_youtube_refusal(spent), FAILURE_BOT_CHECK)

    def test_all_token_free_clients_being_refused_means_ip_block(self):
        self.assertEqual(
            classify_youtube_refusal({"android_vr", "web_embedded,tv,default"}),
            FAILURE_IP_BLOCKED,
        )

    def test_client_rungs_are_split_and_whitespace_is_normalized(self):
        spent = {"android_vr", " web_embedded , tv , default "}
        self.assertEqual(classify_youtube_refusal(spent), FAILURE_IP_BLOCKED)

    def test_extra_clients_do_not_change_ip_block_classification(self):
        spent = {"android_vr", "web_embedded,tv,default", "mweb,default"}
        self.assertEqual(classify_youtube_refusal(spent), FAILURE_IP_BLOCKED)

    def test_empty_client_rung_is_not_a_token_free_client(self):
        self.assertEqual(classify_youtube_refusal({""}), FAILURE_BOT_CHECK)


class RetrySignalTests(unittest.TestCase):
    def test_youtube_no_format_and_sabr_signals_are_distinct(self):
        self.assertTrue(YOUTUBE_NO_FORMATS.search("Requested format is not available"))
        self.assertTrue(YOUTUBE_NO_FORMATS.search("no video formats found"))
        self.assertTrue(YOUTUBE_SABR.search("Some streams are missing a URL (SABR)"))
        self.assertFalse(YOUTUBE_SABR.search("Requested format is not available"))

    def test_ytdlp_warning_match_is_limited_to_known_retry_signals(self):
        self.assertTrue(YTDLP_TELLING_WARNING.search(
            "WARNING: formats may be missing due to PO token"))
        self.assertTrue(YTDLP_TELLING_WARNING.search(
            "WARNING: some streams are skipped as they are missing a URL"))
        self.assertFalse(YTDLP_TELLING_WARNING.search(
            "WARNING: Falling back on generic information extractor"))
        self.assertFalse(YTDLP_TELLING_WARNING.search(
            "[download] 12.0% of 5.00MiB at 1.00MiB/s"))

    def test_media_denial_and_signin_patterns(self):
        self.assertTrue(YOUTUBE_MEDIA_DENIED.search(
            "Unable to download video data: HTTP Error 403: Forbidden"))
        self.assertTrue(SIGNIN_DEMANDED.search("Sign in to confirm you are not a bot"))
        self.assertTrue(GENERAL_CHALLENGE.search("Attention Required: Cloudflare"))
        self.assertFalse(GENERAL_CHALLENGE.search("The download is complete"))

    def test_no_video_routing_signal_does_not_match_unrelated_errors(self):
        self.assertTrue(NO_VIDEO_FOR_YTDLP.search("Unsupported URL"))
        self.assertTrue(NO_VIDEO_FOR_YTDLP.search("There is no video in this post"))
        self.assertTrue(NO_VIDEO_FOR_YTDLP.search("Requested format is not available"))
        self.assertFalse(NO_VIDEO_FOR_YTDLP.search("Permission denied"))
        self.assertFalse(NO_VIDEO_FOR_YTDLP.search("HTTP Error 503"))

    def test_terminal_failure_regex_is_the_policy_used_by_wrapper(self):
        self.assertTrue(TERMINAL_FAILURE.search("No space left on device"))
        self.assertFalse(TERMINAL_FAILURE.search("Unable to extract player response"))

    def test_po_token_validation_pattern(self):
        self.assertTrue(PO_TOKEN_PATTERN.fullmatch("mweb.gvs+" + "A" * 32))
        self.assertFalse(PO_TOKEN_PATTERN.fullmatch("mweb.gvs+short"))
        self.assertFalse(PO_TOKEN_PATTERN.fullmatch("other.gvs+" + "A" * 32))


class FallbackEngineOrderTests(unittest.TestCase):
    def test_youtube_fallback_order_is_preserved(self):
        self.assertEqual(ENGINES["youtube"],
                         ("youtube-explode", "newpipe", "youtube-js"))
        self.assertEqual(ENGINES["ytmusic"], ENGINES["youtube"])

    def test_general_fallback_order_is_preserved(self):
        self.assertEqual(
            ENGINES["general"],
            ("youtube-explode", "newpipe", "streamlink", "html5", "gallery-dl", "direct"),
        )

    def test_social_site_fallbacks_are_preserved(self):
        self.assertEqual(ENGINES["instagram"], ("gallery-dl",))
        self.assertEqual(ENGINES["x"], ("gallery-dl", "html5", "direct"))
        self.assertEqual(ENGINES["soundcloud"], ("newpipe",))
        self.assertEqual(ENGINES.get("unknown", ()), ())


if __name__ == "__main__":
    unittest.main()
