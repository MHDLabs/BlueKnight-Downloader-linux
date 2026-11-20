"""Focused tests for the pure media validation helpers."""

import unittest

from blueknight.media.validation import (
    HtmlImageParser, HtmlMediaParser, PdfLinkParser,
    cookie_domain_for, detect_document_extension, normalize_media_url,
    normalize_page_url, safe_filename, youtube_video_id,
)


class MediaURLTests(unittest.TestCase):
    def test_accepts_supported_service_urls(self):
        cases = (
            ("youtube", "https://www.youtube.com/watch?v=abcdefghijk"),
            ("ytmusic", "https://music.youtube.com/watch?v=abcdefghijk"),
            ("tiktok", "https://www.tiktok.com/@creator/video/123"),
            ("instagram", "https://www.instagram.com/p/abc123/"),
            ("soundcloud", "https://soundcloud.com/artist/track"),
            ("x", "https://x.com/example/status/123"),
            ("general", "https://example.org/watch?id=1"),
        )
        for kind, value in cases:
            with self.subTest(kind=kind):
                self.assertEqual(normalize_media_url(kind, value), value)

    def test_normalizes_social_handles(self):
        self.assertEqual(normalize_media_url("tiktok", "@creator"),
                         "https://www.tiktok.com/@creator")
        self.assertEqual(normalize_media_url("instagram", "@creator/"),
                         "https://www.instagram.com/creator/")

    def test_rejects_wrong_services_and_unsupported_kind(self):
        cases = (
            ("youtube", "https://notyoutube.com/video"),
            ("instagram", "https://instagram.example.org/p/123"),
            ("tiktok", "ftp://www.tiktok.com/video/1"),
            ("general", "https://music.youtube.com/watch?v=abcdefghijk"),
        )
        for kind, value in cases:
            with self.subTest(kind=kind, value=value):
                with self.assertRaises(ValueError):
                    normalize_media_url(kind, value)
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            normalize_media_url("unknown", "https://example.org")

    def test_rejects_credentials_in_urls(self):
        for value in ("https://user:secret@example.org/video",
                      "https://name@example.org/video"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "username or password"):
                    normalize_media_url("general", value)

    def test_general_rejects_only_real_youtube_domains(self):
        with self.assertRaisesRegex(ValueError, "dedicated YouTube"):
            normalize_media_url("general", "https://sub.youtube.com/watch?v=1")
        self.assertEqual(normalize_media_url("general", "https://notyoutube.com/video"),
                         "https://notyoutube.com/video")

    def test_trims_surrounding_whitespace(self):
        self.assertEqual(normalize_media_url("general", "  https://example.org/a  "),
                         "https://example.org/a")

    def test_cookie_domain_selection(self):
        self.assertEqual(cookie_domain_for("youtube", "https://youtu.be/x"), "youtube.com")
        self.assertEqual(cookie_domain_for("ytmusic", "https://music.youtube.com"), "youtube.com")
        self.assertEqual(cookie_domain_for("instagram", "https://instagram.com"), "instagram.com")
        self.assertEqual(cookie_domain_for("general", "https://Sub.Example.org./a"),
                         "sub.example.org")
        self.assertIsNone(cookie_domain_for("unknown", "https://example.org"))
        self.assertIsNone(cookie_domain_for("general", "file:///tmp/example"))

    def test_youtube_video_id_variants(self):
        urls = (
            "https://www.youtube.com/watch?v=abcdefghijk",
            "https://youtu.be/abcdefghijk",
            "https://www.youtube.com/shorts/abcdefghijk",
            "https://www.youtube.com/embed/abcdefghijk",
            "https://www.youtube.com/v/abcdefghijk",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(youtube_video_id(url), "abcdefghijk")
        self.assertIsNone(youtube_video_id("https://example.org/video"))
        self.assertIsNone(youtube_video_id(None))


class PageAndFileValidationTests(unittest.TestCase):
    def test_normalizes_http_page_url(self):
        self.assertEqual(normalize_page_url("  https://example.org/path?q=1  "),
                         "https://example.org/path?q=1")
        self.assertEqual(normalize_page_url("http://example.org"), "http://example.org")

    def test_rejects_non_http_or_incomplete_page_urls(self):
        for value in ("", "example.org", "ftp://example.org/file", "https:///missing-host"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_page_url(value)

    def test_rejects_credentials_in_page_urls(self):
        with self.assertRaisesRegex(ValueError, "username or password"):
            normalize_page_url("https://user:secret@example.org/file")

    def test_safe_filename_removes_traversal_and_invalid_characters(self):
        self.assertEqual(safe_filename("../../unsafe?.txt"), "unsafe_.pdf")
        self.assertEqual(safe_filename(r"..\..\folder\report.pdf"), "report.pdf")

    def test_safe_filename_protects_windows_reserved_names(self):
        self.assertEqual(safe_filename("CON.txt"), "_CON.pdf")
        self.assertEqual(safe_filename("LPT1.pdf"), "_LPT1.pdf")

    def test_safe_filename_decodes_and_enforces_suffix(self):
        self.assertEqual(safe_filename("My%20Book.epub", suffix=".epub"), "My Book.epub")
        self.assertEqual(safe_filename("report.exe", suffix=".pdf"), "report.pdf")

    def test_safe_filename_uses_fallback_and_limits_stem(self):
        self.assertEqual(safe_filename("", fallback="download"), "download.pdf")
        self.assertEqual(len(safe_filename("a" * 150 + ".pdf")), 124)

    def test_detects_common_document_signatures(self):
        cases = (
            (b"prefix%PDF-" + b"x" * 20, "https://e.test/file", "", ".pdf"),
            (b"PK\x03\x04" + b"x" * 20, "https://e.test/file", "", ".zip"),
            (b"x" * 60 + b"BOOKMOBI" + b"x" * 8, "https://e.test/file.azw3", "", ".azw3"),
            (b"{\\rtf1 text", "https://e.test/file", "", ".rtf"),
            (b"AT&TFORM" + b"x" * 4 + b"DJVU", "https://e.test/file", "", ".djvu"),
            (b"ITSF" + b"x" * 20, "https://e.test/file", "", ".chm"),
            (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"x" * 8,
             "https://e.test/file.xls", "application/vnd.ms-excel", ".xls"),
        )
        for head, url, content_type, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(detect_document_extension(head, url, content_type), expected)

    def test_detects_suffix_dependent_document_types(self):
        self.assertEqual(detect_document_extension(b"<FictionBook><body/>",
                                                    "https://e.test/book.fb2"), ".fb2")
        self.assertEqual(detect_document_extension(b"text", "https://e.test/readme.md",
                                                    "text/markdown"), ".md")
        self.assertEqual(detect_document_extension(b"text", "https://e.test/data.csv",
                                                    "text/csv; charset=utf-8"), ".csv")

    def test_does_not_classify_html_as_document(self):
        self.assertIsNone(detect_document_extension(b"<html>not a document</html>",
                                                    "https://e.test/download", "text/html"))
        self.assertIsNone(detect_document_extension(b"text", "https://e.test/readme.md",
                                                    "application/json"))


class HTMLParserTests(unittest.TestCase):
    def test_pdf_parser_preserves_document_link_order(self):
        parser = PdfLinkParser()
        parser.feed('<a href="/one">one</a><embed src="/two">'
                    '<iframe src="/three"></iframe><object data="/four"></object>')
        self.assertEqual(parser.links, ["/one", "/two", "/three", "/four"])

    def test_media_parser_reads_html5_meta_and_file_links(self):
        parser = HtmlMediaParser()
        parser.feed(
            '<video src="/video.mp4"></video><source src="/audio.webm">'
            '<meta property="og:video:url" content="/social.mp4">'
            '<meta name="description" content="/ignore.mp4">'
            '<a href="/track.mp3?download=1">track</a>'
        )
        self.assertEqual(parser.links,
                         ["/video.mp4", "/audio.webm", "/social.mp4", "/track.mp3?download=1"])

    def test_image_parser_prefers_lazy_attributes_and_largest_srcset_candidate(self):
        parser = HtmlImageParser()
        parser.feed(
            '<img data-src="/lazy.jpg" src="/fallback.jpg">'
            '<img srcset="/small.jpg 1x, /large.jpg 2x">'
            '<source data-srcset="/small.webp 1x, /large.webp 2x">'
            '<a href="/linked.avif">image</a>'
        )
        self.assertEqual(parser.links,
                         ["/lazy.jpg", "/large.jpg", "/large.webp", "/linked.avif"])


if __name__ == "__main__":
    unittest.main()