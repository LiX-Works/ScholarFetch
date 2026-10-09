"""Offline checks for orchestration, privacy, exports and output preservation."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from literature_workflow.cli import _new_output, build_parser, execute
from literature_workflow.export import export_candidates
from literature_workflow.privacy import sanitize


class WorkflowTests(unittest.TestCase):
    def test_recursive_auth_redaction(self):
        safe = sanitize({"doi": "10.1234/example", "cookies": "real-cookie",
                         "nested": {"api_key": "private", "url": "https://user:password@publisher.example/paper?token=private"},
                         "error": "Cookie=private contact person@example.org"})
        self.assertNotIn("real-cookie", str(safe))
        self.assertNotIn("private", str(safe))
        self.assertNotIn("person@example.org", str(safe))
        self.assertEqual(safe["nested"]["url"], "https://publisher.example/paper")

    def test_previous_run_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run"
            _new_output(str(path))
            (path / "records.json").write_text("original")
            with self.assertRaises(ValueError):
                _new_output(str(path))
            self.assertEqual((path / "records.json").read_text(), "original")

    def test_export_separates_trials_and_unverified_records(self):
        good = {"record_id": "a", "entity_type": "publication", "metadata_status": "verified", "title": "A checked paper", "doi": "10.1234/a"}
        partial = dict(good, record_id="b", metadata_status="partial")
        trial = dict(good, record_id="c", entity_type="trial")
        text, report = export_candidates([good, partial, trial], "ris")
        self.assertEqual(report["exported_count"], 1)
        self.assertEqual(len(report["omitted"]), 2)
        self.assertIn("10.1234/a", text)
        self.assertEqual(report["selection_status"], "not_recorded")

    def test_unchecked_doi_not_exported(self):
        text, report = export_candidates([{"metadata_status": "verified", "title": "Checked title",
                                          "doi": "10.1234/unverified", "unchecked_identifiers": ["doi"]}], "bibtex")
        self.assertNotIn("10.1234/unverified", text)
        self.assertEqual(report["exported_count"], 1)

    def test_export_redacts_signed_urls_and_contact_fields(self):
        record = {"metadata_status": "verified",
                  "title": "Paper https://example.invalid/paper?token=SIGNED_QUERY&signature=SIGNED_VALUE",
                  "authors": ["synthetic-person@example.invalid"], "doi": "10.1234/example"}
        for format in ("ris", "bibtex"):
            text, _ = export_candidates([record], format)
            self.assertNotIn("SIGNED_QUERY", text)
            self.assertNotIn("SIGNED_VALUE", text)
            self.assertNotIn("synthetic-person@", text)

    def test_duplicate_paper_inputs_keep_distinct_input_references(self):
        from literature_workflow.inputs import collect_inputs
        args = build_parser().parse_args(["verify", "--doi", "10.1234/a", "--doi", "10.1234/a"])
        records = collect_inputs(args)
        self.assertNotEqual(records[0]["input_id"], records[1]["input_id"])

    def test_search_forwards_declared_filters_and_records_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            args = build_parser().parse_args(["search", "data sharing", "--date-from", "2007-01-01",
                    "--date-to", "2007-12-31", "--document-type", "journal-article",
                    "--output", str(Path(directory) / "filtered")])
            with patch("literature_workflow.search.search_papers", return_value={"records": [],
                       "sources_succeeded": ["crossref"], "sources_queried": ["crossref"]}) as search:
                _, code = execute(args)
            self.assertEqual(code, 0)
            self.assertEqual(search.call_args.kwargs["filters"]["date_from"], "2007-01-01")
            self.assertEqual(search.call_args.kwargs["filters"]["document_type"], ["journal-article"])

    def test_bibtex_doi_round_trip_and_non_identifier_mentions(self):
        from literature_workflow.inputs import read_records
        record = {"metadata_status": "verified", "title": "A checked paper mentioning 10.1234/other",
                  "doi": "10.1234/example_id"}
        text, _ = export_candidates([record], "bibtex")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "papers.bib"
            source.write_text(text, encoding="utf-8")
            self.assertEqual(read_records(source), [{"doi": "10.1234/example_id"}])

    def test_missing_dependencies_do_not_create_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "never-created"
            args = build_parser().parse_args(["verify", "--doi", "10.1234/a", "--output", str(path)])
            with patch("literature_workflow.cli.check_dependencies", return_value={"ok": False, "missing_required": ["requests"]}):
                result, code = execute(args)
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "dependency_missing")
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
