"""Offline regressions: publisher boundary, identity, provenance and file commit.

No network or browser is used. PDF fixtures are built with pypdf alone.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literature_workflow._official_pdf import (identity_evidence, redact_text, redact_url,
                                                trusted_url, verify_pdf)
from literature_workflow.download import (SourceRejected, download_records, fetch_http,
                                          pdf_links, resolve_official_page)


def pdf_bytes(text="Quantum transport through molecular junctions Smith 10.1038/test.2026"):
    from io import BytesIO
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data((f"BT /F1 12 Tf 20 750 Td ({safe}) Tj ET\n%" + "pad" * 20000).encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class Response:
    def __init__(self, url, body=b"", status=200, headers=None):
        self.url, self.body, self.status_code = url, body, status
        self.headers = headers or {"Content-Type": "application/pdf", "Content-Length": str(len(body))}

    def iter_content(self, size):
        yield self.body

    def close(self):
        pass


class Session:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        assert kwargs["allow_redirects"] is False
        return self.responses[url]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


RECORD = {"record_id": "r1", "doi": "10.1038/test.2026", "title": "Quantum transport through molecular junctions", "first_author": "Smith", "pdf_url": "https://www.nature.com/articles/test.2026.pdf"}


class DownloadTests(unittest.TestCase):
    def test_exact_host_and_https_boundary(self):
        for bad in ("https://www.nature.com.evil.example/a.pdf", "https://evil.nature.com/a.pdf", "https://www.nature.com@evil.example/a", "http://www.nature.com/a", "https://www.nature.com:8443/a", "https://www.nature.com/bitstream/a"):
            self.assertFalse(trusted_url(bad, "NatureSpringer"), bad)
        self.assertTrue(trusted_url("https://www.nature.com/a.pdf?signature=secret", "NatureSpringer"))

    def test_reject_redirect_before_contacting_third_party(self):
        url = RECORD["pdf_url"]
        session = Session({url: Response(url, status=302, headers={"Location": "https://repo.example/paper.pdf"})})
        with self.assertRaises(SourceRejected):
            fetch_http(session, url, "NatureSpringer", timeout=1)
        self.assertEqual(session.calls, [url])

    def test_doi_resolver_only_to_registered_publisher(self):
        start, final = "https://doi.org/10.1038/test.2026", RECORD["pdf_url"]
        session = Session({start: Response(start, status=302, headers={"Location": final}), final: Response(final, b"PDF")})
        payload = fetch_http(session, start, "NatureSpringer", timeout=1)
        self.assertEqual(payload["url"], final)
        self.assertEqual(len(session.calls), 2)

    def test_source_and_secret_redaction(self):
        value = "https://user:password@www.nature.com/a.pdf?token=secret#cookie"
        self.assertEqual(redact_url(value), "https://www.nature.com/a.pdf")
        text = redact_text(value + " token=supersecret cookie=other C:\\Users\\Private\\key.txt /home/person/key")
        for secret in ("password", "supersecret", "other", "Private", "person", "?token", "#cookie"):
            self.assertNotIn(secret, text)

    def test_discovery_excludes_supplements_and_unknown_cdns(self):
        html = '<meta name="citation_pdf_url" content="/paper.pdf"><a href="https://evil.example/main.pdf">PDF</a><a href="/supplement.pdf">SI</a>'
        self.assertEqual(pdf_links(html, "https://www.nature.com/article", "NatureSpringer"), ["https://www.nature.com/paper.pdf"])

    def test_title_alone_does_not_verify(self):
        self.assertFalse(identity_evidence(RECORD["title"], RECORD)["identity_match"])
        self.assertTrue(identity_evidence(RECORD["title"] + " Smith", RECORD)["identity_match"])
        self.assertFalse(identity_evidence(RECORD["title"] + " Smith 10.1038/other", RECORD)["identity_match"])

    def test_doi_prefix_is_not_exact_identity(self):
        self.assertFalse(identity_evidence(RECORD["title"] + " 10.1038/test.20260", RECORD)["identity_match"])

    def test_valid_pdf_and_empty_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidate.pdf"
            path.write_bytes(pdf_bytes())
            self.assertTrue(verify_pdf(path, RECORD)["verification_ok"])
            path.write_bytes(pdf_bytes(""))
            self.assertEqual(verify_pdf(path, RECORD)["verification_note"], "empty_text_pdf")

    def test_truncated_pdf_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "partial.pdf"
            path.write_bytes(pdf_bytes()[:-10])
            self.assertEqual(verify_pdf(path, RECORD)["verification_note"], "invalid_or_partial_pdf")

    def test_verified_commit_public_report_and_no_overwrite(self):
        url = RECORD["pdf_url"] + "?token=secret"
        record = {**RECORD, "pdf_url": url, "notes": "cookie=private", "private_path": "C:\\Users\\Private"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = download_records([record], root, session=Session({url: Response(url, pdf_bytes())}), use_browser=False)
            self.assertEqual(first["targets"][0]["status"], "verified")
            final = root / first["verified_files"][0]["file"]
            before = final.read_bytes()
            self.assertTrue(final.exists())
            public = json.dumps(first)
            for secret in ("secret", "private_path", "Private", str(root)):
                self.assertNotIn(secret, public)
            second = download_records([record], root, session=Session({}), use_browser=False)
            self.assertIn("existing_file_unverified_no_overwrite", second["targets"][0]["errors"])
            self.assertEqual(final.read_bytes(), before)

    def test_different_paper_is_quarantined(self):
        url = RECORD["pdf_url"]
        with tempfile.TemporaryDirectory() as directory:
            result = download_records([{**RECORD, "official_landing_page": url}], Path(directory), session=Session({url: Response(url, pdf_bytes("An unrelated title Jones 10.1038/other"))}), use_browser=False)
            self.assertEqual(result["verified_files"], [])
            self.assertIn("pdf_identity_mismatch", result["targets"][0]["errors"])
            self.assertEqual(list((Path(directory) / "papers").iterdir()), [])
            self.assertEqual(len(list((Path(directory) / "download_runs").glob("*/quarantine/*.pdf"))), 1)

    def test_html_200_is_not_accepted(self):
        url = RECORD["pdf_url"]
        with tempfile.TemporaryDirectory() as directory:
            result = download_records([{**RECORD, "official_landing_page": url}], Path(directory), session=Session({url: Response(url, b"<html>Access denied</html>")}), use_browser=False)
            self.assertEqual(result["verified_files"], [])
            self.assertIn("non_pdf_response", result["targets"][0]["errors"])

    def test_unsafe_filename_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Session({})
            result = download_records([{**RECORD, "expected_output_filename": "../escape.pdf"}], Path(directory), session=session, use_browser=False)
            self.assertEqual(session.calls, [])
            self.assertIn("unsafe_output_filename", result["targets"][0]["errors"])

    def test_partial_http_response_not_accepted(self):
        url = RECORD["pdf_url"]
        session = Session({url: Response(url, pdf_bytes(), status=206)})
        with self.assertRaisesRegex(Exception, "http_206"):
            fetch_http(session, url, "NatureSpringer", timeout=1)

    def test_missing_browser_dependency_reports_manual_needed(self):
        url = RECORD["pdf_url"]
        with tempfile.TemporaryDirectory() as directory:
            from literature_workflow.download import DownloadFailure
            with patch("literature_workflow.download._browser_attempt", side_effect=DownloadFailure("dependency_missing:cloakbrowser")):
                result = download_records([{**RECORD, "official_landing_page": url}], Path(directory), session=Session({url: Response(url, status=403)}))
            self.assertEqual(result["targets"][0]["status"], "dependency_missing")
            self.assertEqual(len(result["manual_needed"]), 1)

    def test_missing_pdf_reader_never_commits(self):
        import builtins
        original_import = builtins.__import__
        body = pdf_bytes()
        def without_reader(name, *args, **kwargs):
            if name == "pypdf":
                raise ImportError("pypdf intentionally unavailable")
            return original_import(name, *args, **kwargs)
        url = RECORD["pdf_url"]
        with tempfile.TemporaryDirectory() as directory, patch("builtins.__import__", side_effect=without_reader):
            result = download_records([{**RECORD, "official_landing_page": url}], Path(directory), session=Session({url: Response(url, body)}), use_browser=False)
            self.assertEqual(result["verified_files"], [])
            self.assertEqual(result["targets"][0]["status"], "dependency_missing")

    def test_transport_exception_does_not_leak_secrets(self):
        session = Session({})
        session.get = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("cookie=SECRET https://user:password@www.nature.com/a?token=SECRET C:\\Users\\Private"))
        with tempfile.TemporaryDirectory() as directory:
            result = download_records([RECORD], Path(directory), session=session, use_browser=False)
            self.assertNotIn("SECRET", json.dumps(result))
            self.assertNotIn("Private", json.dumps(result))
            self.assertIn("transport_error:RuntimeError", result["targets"][0]["errors"])

    def test_failed_candidate_does_not_block_following_record(self):
        bad, good = "https://evil.example/wrong.pdf", RECORD["pdf_url"]
        with tempfile.TemporaryDirectory() as directory:
            result = download_records([{**RECORD, "record_id": "bad", "pdf_url": bad}, RECORD], Path(directory), session=Session({good: Response(good, pdf_bytes())}), use_browser=False)
            self.assertEqual([t["status"] for t in result["targets"]], ["source_rejected", "verified"])

    def test_official_page_citation_metadata_is_unverified_candidate(self):
        url = "https://www.nature.com/articles/no-doi-in-path?token=PRIVATE"
        html = b'''<META CONTENT="10.1038/test.v2" NAME="Citation_DOI">
        <meta name="DC.Identifier" content="doi:10.1038/test.v2">
        <meta name="citation_title" content="Quantum &amp; transport">
        <meta property="citation_author" content="Alice Smith">
        <meta name="citation_author" content="Bob Jones">
        <meta name="citation_publication_date" content="2026/10/09">
        <meta name="citation_pdf_url" content="/article.pdf?signature=PRIVATE">'''
        session = Session({url: Response(url, html, headers={"Content-Type": "text/html"})})
        with patch("requests.Session", return_value=session):
            result = resolve_official_page(url)
        self.assertEqual(result["doi"], "10.1038/test.v2")
        self.assertEqual(result["authors"], ["Alice Smith", "Bob Jones"])
        self.assertEqual(result["year"], "2026")
        self.assertEqual(result["title"], "Quantum & transport")
        self.assertFalse(result["metadata_verified"])
        self.assertFalse(result["manual_needed"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_unregistered_or_authenticated_page_does_not_request(self):
        for url in ("https://unknown.example/paper", "https://user:password@www.nature.com/a", "http://www.nature.com/a"):
            with patch("requests.Session") as factory:
                result = resolve_official_page(url)
                factory.assert_not_called()
                self.assertTrue(result["manual_needed"])
                self.assertNotIn("password", json.dumps(result))

    def test_page_metadata_missing_and_conflicting_doi(self):
        url = "https://www.nature.com/articles/no-doi"
        for html, expected in ((b'<meta name="citation_title" content="A title">', "page_doi_missing_needs_identity_resolution"),
                               (b'<meta name="citation_doi" content="10.1038/one"><meta name="DC.identifier" content="10.1038/two">', "ambiguous_page_doi")):
            with patch("requests.Session", return_value=Session({url: Response(url, html, headers={"Content-Type": "text/html"})})):
                result = resolve_official_page(url)
            self.assertTrue(result["manual_needed"])
            self.assertEqual(result["errors"], [expected])

    def test_official_page_redirect_cannot_leave_publisher(self):
        url = "https://www.nature.com/article"
        session = Session({url: Response(url, status=302, headers={"Location": "https://unknown.example/article"})})
        with patch("requests.Session", return_value=session):
            result = resolve_official_page(url)
        self.assertTrue(result["manual_needed"])
        self.assertEqual(session.calls, [url])

    def test_page_resolver_does_not_read_pdf_body(self):
        url = "https://www.nature.com/articles/paper.pdf"
        response = Response(url, b"should never be read")
        response.iter_content = lambda *args: (_ for _ in ()).throw(AssertionError("PDF body was requested"))
        with patch("requests.Session", return_value=Session({url: response})):
            result = resolve_official_page(url)
        self.assertEqual(result["errors"], ["article_html_required"])


if __name__ == "__main__":
    unittest.main()
