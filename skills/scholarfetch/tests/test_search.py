"""Offline invariants; no live API or production runtime is used."""
import copy
import unittest
from unittest.mock import patch

from literature_workflow import search
from literature_workflow._vendor.nature_academic_search.errors import DataSourceError
from literature_workflow._vendor.nature_academic_search.sources.arxiv import ArxivSource
from literature_workflow._vendor.nature_academic_search.sources.crossref import CrossRefSource
from literature_workflow._vendor.nature_academic_search.sources.europe_pmc import _result_items
from literature_workflow._vendor.nature_academic_search.sources.pubmed import PubMedSource, _parse_article
from literature_workflow._vendor.nature_academic_search.provenance import stable_record_id
from literature_workflow._vendor.nature_academic_search.http import request_json, _SourceSession
import requests
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from literature_workflow._vendor.nature_academic_search.sources import pubmed


PAPER = {"title": "Finite size optical response in two dimensional materials", "authors": ["Jane Doe"],
         "year": 2025, "journal": "Example Journal", "publisher": "Example Publisher", "doi": "10.1234/example",
         "source": "crossref"}


class Adapter:
    def __init__(self, records=None, total=None, failure=None):
        self.records = copy.deepcopy(records if records is not None else [PAPER])
        self.total = len(self.records) if total is None else total
        self.failure = failure
        self.calls = []

    def search(self, query, rows=5, **kwargs):
        self.calls.append(("search", query, rows))
        if self.failure:
            raise self.failure
        return {"results": copy.deepcopy(self.records[:rows]), "total": self.total}

    def get_by_doi(self, value):
        self.calls.append(("lookup", value))
        if self.failure:
            raise self.failure
        return copy.deepcopy(self.records[0])

    get_by_id = get_by_doi
    get_by_pmid = get_by_doi


class SearchInvariants(unittest.TestCase):
    def test_sources_called_once_and_empty_success_differs_from_failure_and_missing(self):
        good = Adapter([])
        failed = Adapter(failure=DataSourceError("openalex", "HTTP 429 from https://example.org?api_key=hidden"))
        result = search.search_papers("optics", sources=["crossref", "crossref", "openalex", "core"],
                                      adapters={"crossref": good, "openalex": failed})
        self.assertEqual(len(good.calls), 1)
        self.assertEqual(result["sources_succeeded"], ["crossref"])
        self.assertEqual(result["sources_failed"], ["openalex"])
        self.assertEqual(result["sources_not_queried"][0]["source"], "core")
        self.assertEqual(result["records"], [])
        self.assertNotIn("hidden", str(result["errors"]))
        self.assertEqual(result["coverage"]["crossref"]["status"], "complete_within_scope")

    def test_top_page_is_not_reported_as_exhaustive(self):
        result = search.search_papers("optics", sources=["crossref"], rows=1,
                                      adapters={"crossref": Adapter(total=500)})
        self.assertEqual(result["coverage"]["crossref"]["status"], "partial")
        self.assertEqual(result["coverage"]["crossref"]["reported_total"], 500)

    def test_same_title_different_doi_are_not_merged(self):
        records = [PAPER, {**PAPER, "doi": "10.1234/other"}]
        result = search.search_papers("optics", sources=["crossref"], adapters={"crossref": Adapter(records)})
        self.assertEqual(len(result["records"]), 2)

    def test_shared_id_with_conflicting_secondary_id_stays_separate(self):
        records = [{**PAPER, "pmid": "12345678"}, {**PAPER, "pmid": "87654321"}]
        result = search.search_papers("optics", sources=["crossref"], adapters={"crossref": Adapter(records)})
        self.assertEqual(len(result["records"]), 2)
        self.assertTrue(all(r["conflicts"] for r in result["records"]))
        self.assertTrue(all(r["metadata_status"] == "not_checked" for r in result["records"]))

    def test_preprint_and_published_work_do_not_merge_even_with_same_doi(self):
        preprint = {**PAPER, "source": "arxiv", "arxiv_id": "2401.12345v1", "is_preprint": True}
        result = search.search_papers("optics", sources=["crossref", "arxiv"],
                                      adapters={"crossref": Adapter(), "arxiv": Adapter([preprint])})
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(len({r["record_id"] for r in result["records"]}), 2)

    def test_arxiv_revisions_have_distinct_records_and_ids(self):
        records = [{"title": PAPER["title"], "arxiv_id": "2401.12345v1", "version": "v1", "source": "arxiv", "is_preprint": True},
                   {"title": PAPER["title"], "arxiv_id": "2401.12345v2", "version": "v2", "source": "arxiv", "is_preprint": True}]
        result = search.search_papers("optics", sources=["arxiv"], adapters={"arxiv": Adapter(records)})
        self.assertEqual(len(result["records"]), 2)
        self.assertNotEqual(stable_record_id(records[0]), stable_record_id(records[1]))

    def test_lookup_cannot_assign_verified_to_wrong_primary_id(self):
        actual = {**PAPER, "doi": "10.1234/wrong"}
        result = search.resolve_record(PAPER["doi"], adapters={"crossref": Adapter([actual])})
        self.assertEqual(result["metadata_status"], "mismatch")
        self.assertEqual(result["identity_status"], "manual_needed")

    def test_input_tracking_id_is_not_treated_as_a_metadata_expectation(self):
        result = search.resolve_record(PAPER["doi"], expected={"input_id": "row-1", "title": PAPER["title"]},
                                       adapters={"crossref": Adapter()})
        self.assertEqual(result["metadata_status"], "verified")
        self.assertNotIn("input_id", result["verification_scope"])
        self.assertNotIn("input_id", result["unchecked_fields"])

    def test_unchecked_secondary_id_kept_in_input_and_prevents_verified(self):
        original = {**PAPER, "pmid": "12345678"}
        result = search.verify_records([original], adapters={"crossref": Adapter()})[0]
        self.assertEqual(result["metadata_status"], "partial")
        self.assertIn("pmid", result["unchecked_identifiers"])
        self.assertEqual(result["input_metadata"]["pmid"], "12345678")
        self.assertNotIn("pmid", result["identifiers"])
        self.assertEqual(result["claim_support_status"], "not_assessed")
        self.assertEqual(result["selection_status"], "not_recorded")

    def test_expected_year_mismatch_is_not_fixed_by_lookup(self):
        result = search.verify_records([{**PAPER, "year": 1990}], adapters={"crossref": Adapter()})[0]
        self.assertEqual(result["metadata_status"], "mismatch")
        self.assertEqual(result["input_metadata"]["year"], 1990)

    def test_secondary_ids_conflict_between_independent_sources_is_mismatch(self):
        left = {**PAPER, "pmid": "12345678"}
        right = {**PAPER, "pmid": "87654321", "source": "openalex"}
        result = search.resolve_record(PAPER["doi"], sources=["crossref", "openalex"],
                                       adapters={"crossref": Adapter([left]), "openalex": Adapter([right])})
        self.assertEqual(result["metadata_status"], "mismatch")
        self.assertEqual(result["identity_status"], "manual_needed")
        self.assertTrue(result["conflicts"])

    def test_first_author_only_expectation_is_not_discarded(self):
        record = {"title": PAPER["title"], "doi": PAPER["doi"], "first_author": "Wrong Person"}
        result = search.verify_records([record], adapters={"crossref": Adapter()})[0]
        self.assertEqual(result["metadata_status"], "mismatch")
        self.assertEqual(result["input_metadata"]["first_author"], "Wrong Person")

    def test_supplied_arxiv_revision_is_verified_exactly(self):
        record = {"title": "Revision example", "arxiv_id": "2401.12345v2", "source": "arxiv", "is_preprint": True}
        result = search.resolve_record("arxiv:2401.12345v1", adapters={"arxiv": Adapter([record])})
        self.assertEqual(result["metadata_status"], "mismatch")

    def test_citation_first_hit_is_not_automatically_accepted(self):
        result = search.resolve_record("A short and uncertain optical citation", adapters={"crossref": Adapter()})
        self.assertEqual(result["identity_status"], "manual_needed")
        self.assertEqual(result["metadata_status"], "unresolved")

    def test_unknown_signed_url_is_not_sent_to_crossref_or_logged_as_citation(self):
        adapter = Adapter()
        result = search.resolve_record("https://publisher.example/article/abc?token=private", adapters={"crossref": adapter})
        self.assertEqual(result["identity_status"], "manual_needed")
        self.assertEqual(adapter.calls, [])
        self.assertNotIn("private", str(result))

    def test_doi_in_publisher_url_resolves_independently_without_query_tokens(self):
        adapter = Adapter()
        result = search.resolve_record("https://publisher.example/doi/10.1234/example?token=private", adapters={"crossref": adapter})
        self.assertEqual(result["doi"], PAPER["doi"])
        self.assertEqual(adapter.calls, [("lookup", PAPER["doi"])])
        self.assertNotIn("private", str(result))

    def test_unique_exact_title_then_doi_recheck_is_accepted(self):
        adapter = Adapter()
        result = search.resolve_record(PAPER["title"], adapters={"crossref": adapter})
        self.assertEqual(result["metadata_status"], "verified")
        self.assertEqual([call[0] for call in adapter.calls], ["search", "lookup"])
        self.assertEqual(result["resolution_confidence"]["level"], "high")

    def test_ambiguous_same_title_with_different_dois_stays_manual(self):
        result = search.resolve_record(PAPER["title"], adapters={"crossref": Adapter([PAPER, {**PAPER, "doi": "10.1234/other"}])})
        self.assertEqual(result["identity_status"], "manual_needed")

    def test_trial_is_never_merged_into_publication(self):
        trial = {"title": PAPER["title"], "nct_id": "NCT12345678", "entity_type": "trial", "source": "clinicaltrials_gov"}
        result = search.search_papers("optics", sources=["clinicaltrials_gov", "crossref"], entity_type="publication",
                                      adapters={"clinicaltrials_gov": Adapter([trial]), "crossref": Adapter()})
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["records"][0]["entity_type"], "publication")
        self.assertEqual(result["sources_not_queried"][0]["reason"], "incompatible_entity_type")


class SourceSemanticFailures(unittest.TestCase):
    def test_crossref_posted_content_requires_subtype_evidence_and_doi_alone_is_unknown(self):
        adapter = CrossRefSource()
        payload = {"title": ["Posted research item"], "DOI": "10.1234/posting", "type": "posted-content",
                   "author": [{"given": "Jane", "family": "Doe"}], "published-online": {"date-parts": [[2025]]}}
        preprint = search._record(adapter._normalize_detail_item({**payload, "subtype": "preprint"}))
        posting = search._record(adapter._normalize_detail_item({**payload, "subtype": "other"}))
        bare_doi = search._record({"doi": "10.1234/registered", "title": "Registered item"})
        article = search._record(adapter._normalize_detail_item({**payload, "type": "journal-article"}))
        self.assertEqual(preprint["publication_status"], "preprint")
        self.assertEqual(posting["publication_status"], "unknown")
        self.assertFalse(posting["is_preprint"])
        self.assertEqual(bare_doi["publication_status"], "unknown")
        self.assertEqual(article["publication_status"], "published")

    def test_saved_nature_precedings_shape_does_not_imply_formal_journal_publication(self):
        # Shape/values observed in saved live_pipeline records; no live request.
        payload = {"title": ["Sharing Detailed Research Data Is Associated with Increased Citation Rate"],
                   "DOI": "10.1038/npre.2007.361.1", "type": "journal-article", "container-title": ["Nature Precedings"],
                   "author": [{"given": "Heather", "family": "Piwowar"}], "published-online": {"date-parts": [[2007]]}}
        record = search._record(CrossRefSource()._normalize_detail_item(payload))
        self.assertEqual(record["publication_status"], "unknown")
        self.assertFalse(record["is_preprint"])
        self.assertEqual(record["doi"], "10.1038/npre.2007.361.1")

    def test_json_200_error_never_becomes_a_valid_empty_result(self):
        class Response:
            status_code = 200
            headers = {}
            def json(self):
                return {"error": "Invalid request", "results": []}
        with patch("literature_workflow._vendor.nature_academic_search.http._SourceSession") as session:
            session.return_value.request.return_value = Response()
            with self.assertRaises(DataSourceError):
                request_json(source="openalex", method="GET", url="https://example.org/api")

    def test_source_session_never_loads_netrc_on_prepare_or_redirect(self):
        session = _SourceSession()
        with patch("requests.sessions.get_netrc_auth", return_value=("unrelated", "password")) as netrc:
            prepared = session.prepare_request(requests.Request("GET", "https://api.example.org/works"))
            self.assertNotIn("Authorization", prepared.headers)
            response = requests.Response()
            response.request = prepared
            redirected = session.prepare_request(requests.Request("GET", "https://other.example.org/works"))
            session.rebuild_auth(redirected, response)
            self.assertNotIn("Authorization", redirected.headers)
            netrc.assert_not_called()

    def test_explicit_api_headers_and_same_origin_auth_survive_without_netrc(self):
        session = _SourceSession()
        with patch("requests.sessions.get_netrc_auth") as netrc:
            prepared = session.prepare_request(requests.Request("GET", "https://api.example.org/works",
                headers={"Authorization": "Bearer explicit", "x-api-key": "explicit-key"}))
            self.assertEqual(prepared.headers["Authorization"], "Bearer explicit")
            self.assertEqual(prepared.headers["x-api-key"], "explicit-key")
            response = requests.Response()
            response.request = prepared
            same_origin = prepared.copy()
            same_origin.url = "https://api.example.org/next"
            session.rebuild_auth(same_origin, response)
            self.assertEqual(same_origin.headers["Authorization"], "Bearer explicit")
            other_origin = prepared.copy()
            other_origin.url = "https://other.example.org/next"
            session.rebuild_auth(other_origin, response)
            self.assertNotIn("Authorization", other_origin.headers)
            netrc.assert_not_called()

    def test_environment_proxy_and_ca_settings_are_preserved(self):
        session = _SourceSession()
        with patch.dict("os.environ", {"HTTPS_PROXY": "http://proxy.example:8080", "REQUESTS_CA_BUNDLE": "test-ca.pem"}, clear=True):
            settings = session.merge_environment_settings("https://api.example.org/works", {}, None, None, None)
        self.assertTrue(session.trust_env)
        self.assertEqual(settings["proxies"]["https"], "http://proxy.example:8080")
        self.assertEqual(settings["verify"], "test-ca.pem")

    def test_pubmed_actual_request_path_uses_explicit_key_and_timeout_without_netrc(self):
        captured = []
        def send(prepared, **kwargs):
            captured.append((prepared, kwargs))
            response = requests.Response()
            response.status_code = 200
            response._content = b"<eSearchResult><Count>0</Count></eSearchResult>"
            response.request = prepared
            response.url = prepared.url
            return response
        cfg = SimpleNamespace(pubmed_email="researcher@example.org", pubmed_api_key="explicit-source-key")
        with patch.object(_SourceSession, "send", side_effect=send), patch("requests.sessions.get_netrc_auth", return_value=("personal", "secret")) as netrc, patch.object(pubmed, "get_config", return_value=cfg), patch.object(pubmed, "_throttle"), patch.dict("os.environ", {"HTTPS_PROXY": "http://proxy.example:8080", "REQUESTS_CA_BUNDLE": "test-ca.pem"}, clear=True):
            response = pubmed._get("esearch.fcgi", {"db": "pubmed", "term": "optics"}, timeout=17)
            netrc.assert_not_called()
        self.assertEqual(response.status_code, 200)
        prepared, settings = captured[0]
        self.assertNotIn("Authorization", prepared.headers)
        self.assertIn("api_key=explicit-source-key", prepared.url)
        self.assertIn("email=researcher%40example.org", prepared.url)
        self.assertEqual(settings["timeout"], 17)
        self.assertEqual(settings["proxies"]["https"], "http://proxy.example:8080")
        self.assertEqual(settings["verify"], "test-ca.pem")

    def test_crossref_citation_actual_path_preserves_negotiation_and_timeout_without_netrc(self):
        captured = []
        def send(prepared, **kwargs):
            captured.append((prepared, kwargs))
            response = requests.Response()
            response.status_code = 200
            response._content = b"Verified format response"
            response.request = prepared
            response.url = prepared.url
            return response
        adapter = CrossRefSource()
        adapter._timeout = 13
        with patch.object(_SourceSession, "send", side_effect=send), patch("requests.sessions.get_netrc_auth", return_value=("personal", "secret")) as netrc:
            text = adapter.get_citation(PAPER["doi"], style="apa")
            netrc.assert_not_called()
        self.assertEqual(text, "Verified format response")
        prepared, settings = captured[0]
        self.assertNotIn("Authorization", prepared.headers)
        self.assertEqual(prepared.headers["Accept"], "text/x-bibliography; style=apa")
        self.assertEqual(settings["timeout"], 13)

    def test_arxiv_http200_error_feed_is_failure(self):
        xml = '<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#bad</id><title>Error</title></entry></feed>'
        with self.assertRaises(DataSourceError):
            ArxivSource()._parse_feed(xml)

    def test_arxiv_parser_keeps_revision_and_publication_link_separate(self):
        xml = '<feed xmlns="http://www.w3.org/2005/Atom" xmlns:a="http://arxiv.org/schemas/atom"><entry><id>http://arxiv.org/abs/2401.12345v2</id><title>Example title</title><a:doi>10.1234/published</a:doi></entry></feed>'
        record = ArxivSource()._parse_feed(xml)[0]
        self.assertEqual(record["arxiv_id"], "2401.12345v2")
        self.assertEqual(record["version"], "v2")
        self.assertEqual(record["doi"], "")
        self.assertEqual(record["relations"][0]["doi"], "10.1234/published")

    def test_europepmc_semantic_error_with_result_list_is_failure(self):
        with self.assertRaises(DataSourceError):
            _result_items({"errCode": 1, "resultList": {"result": []}})

    def test_crossref_http200_unsuccessful_envelope_is_failure(self):
        with patch("literature_workflow._vendor.nature_academic_search.sources.crossref.request_json", return_value=({"status": "failed", "message": {}}, {})):
            with self.assertRaises(DataSourceError):
                CrossRefSource().search("optics")

    def test_pubmed_xml_error_is_failure_instead_of_empty_results(self):
        class Response:
            content = b"<eSearchResult><ERROR>Unknown database</ERROR></eSearchResult>"
        with patch("literature_workflow._vendor.nature_academic_search.sources.pubmed.get_config") as cfg, patch("literature_workflow._vendor.nature_academic_search.sources.pubmed._get", return_value=Response()):
            cfg.return_value.pubmed_email = "researcher@example.org"
            cfg.return_value.max_rows = 50
            with self.assertRaises(DataSourceError):
                PubMedSource().search("optics")

    def test_pubmed_mixed_title_and_types_do_not_break_normalization(self):
        xml = '<PubmedArticle><MedlineCitation><PMID>12345678</PMID><Article><ArticleTitle>Finite <i>optical</i> response</ArticleTitle><PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList></Article></MedlineCitation></PubmedArticle>'
        record = _parse_article(ET.fromstring(xml))
        self.assertEqual(record["title"], "Finite optical response")
        self.assertEqual(record["publication_type"], "Journal Article")


if __name__ == "__main__":
    unittest.main()
