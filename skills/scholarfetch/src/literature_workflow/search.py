"""Bounded discovery and field verification using vendored nature adapters.

Source adapters/discovery/comparison originate in nature-academic-search 0.3.1,
MIT (wp-a); see LICENSES/nature-academic-search-MIT.txt. This module adds public
workflow records, conservative citation resolution and explicit source coverage.
"""
from __future__ import annotations

import asyncio
import copy
import os
import re
from collections.abc import Mapping, Sequence
from difflib import SequenceMatcher
from urllib.parse import unquote, urlsplit, urlunsplit

from ._vendor.nature_academic_search import search as native
from ._vendor.nature_academic_search.config import get_config
from ._vendor.nature_academic_search.errors import DataSourceError
from ._vendor.nature_academic_search.provenance import stable_record_id
from ._vendor.nature_academic_search.sources.registry import (
    DEFAULT_PUBLICATION_SOURCES, SOURCE_ENTITY_TYPES, build_adapters,
)
from ._vendor.nature_academic_search.verification import verify_record
from ._vendor.nature_academic_search.sources.crossref import _publication_status

ID_FIELDS = native.IDENTIFIER_FIELDS
PUBLICATION_SOURCES = tuple(s for s, entity in SOURCE_ENTITY_TYPES.items() if entity == "publication")
_EMPTY = (None, "", [], {})


def normalize_identifier(field: str, value: object) -> str:
    """Canonicalize an identifier without losing a DOI character or arXiv revision."""
    value = str(value or "").strip()
    if field == "doi":
        value = re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", value, flags=re.I)
        return unquote(value).lower()
    if field == "arxiv_id":
        value = re.sub(r"^(?:arxiv:\s*|https?://arxiv\.org/(?:abs|pdf)/)", "", value, flags=re.I)
        return value.removesuffix(".pdf")
    if field == "openalex_id":
        return re.sub(r"^(?:openalex:\s*|https?://openalex\.org/)", "", value, flags=re.I).upper()
    if field == "semantic_scholar_id":
        return value.rstrip("/").rsplit("/", 1)[-1] if "semanticscholar.org/" in value else value
    if field == "pmid":
        value = re.sub(r"^pmid:\s*", "", value, flags=re.I)
        match = re.fullmatch(r"https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?", value, re.I)
        return match.group(1) if match else value
    if field in {"pmcid", "nct_id"}:
        return re.sub(r"^(?:pmcid:|nct:)\s*", "", value, flags=re.I).upper()
    return value


def _identifier(value: str) -> tuple[str, str] | None:
    raw = str(value or "").strip()
    if raw.startswith(("https://", "http://")):
        parts = urlsplit(raw)
        path = unquote(parts.path)
        match = re.search(r"(?:^|/)(10\.\d{4,9}/\S+)$", path)
        if match:
            return "doi", match.group(1).lower()
        if (parts.hostname or "").lower() in {"nature.com", "www.nature.com"}:
            match = re.fullmatch(r"/articles/([A-Za-z0-9.-]+?)(?:\.pdf)?", path)
            if match:
                return "doi", "10.1038/" + match.group(1).lower()
    doi = normalize_identifier("doi", raw)
    if re.fullmatch(r"10\.\d{4,9}/\S+", doi):
        return "doi", doi
    arxiv = normalize_identifier("arxiv_id", raw)
    if re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", arxiv):
        return "arxiv_id", arxiv
    pmid = normalize_identifier("pmid", raw)
    if re.fullmatch(r"\d{1,9}", pmid):
        return "pmid", pmid
    pmcid = normalize_identifier("pmcid", raw)
    if re.fullmatch(r"PMC\d+", pmcid):
        return "pmcid", pmcid
    openalex = normalize_identifier("openalex_id", raw)
    if re.fullmatch(r"W\d+", openalex):
        return "openalex_id", openalex
    nct = normalize_identifier("nct_id", raw.rstrip("/").rsplit("/", 1)[-1])
    if re.fullmatch(r"NCT\d{8}", nct):
        return "nct_id", nct
    s2 = normalize_identifier("semantic_scholar_id", raw)
    if re.fullmatch(r"[a-fA-F0-9]{40}", s2):
        return "semantic_scholar_id", s2
    return None


def _safe_text(value: object) -> str:
    text = str(value)
    for name in ("NCBI_API_KEY", "OPENALEX_API_KEY", "S2_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"):
        secret = os.environ.get(name)
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(r"https?://[^\s<>\"']+", lambda m: _safe_url(m.group(0)), text)
    return re.sub(r"(?i)(api[_-]?key|token|authorization|password)\s*[:=]\s*[^\s,;]+", r"\1=[redacted]", text)


def _safe_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))


def _record(raw: Mapping) -> dict:
    record = copy.deepcopy(dict(raw))
    identifiers = dict(record.get("identifiers") or {})
    for field in ID_FIELDS:
        value = record.get(field) or identifiers.get(field)
        if isinstance(value, Mapping):
            value = value.get("normalized") or value.get("value")
        if value:
            identifiers[field] = normalize_identifier(field, value)
            record[field] = identifiers[field]
    record["identifiers"] = identifiers
    record.setdefault("entity_type", "trial" if identifiers.get("nct_id") else "publication")
    for field in ("title", "journal", "publisher", "official_landing_page", "version"):
        record.setdefault(field, "")
    authors = record.get("authors") or []
    if isinstance(authors, str):
        authors = [a.strip() for a in authors.split(";") if a.strip()]
    record["authors"] = [str(a.get("name") or a.get("family") or "") if isinstance(a, Mapping) else str(a) for a in authors]
    record["first_author"] = record["authors"][0] if record["authors"] else str(record.get("first_author") or "")
    record.setdefault("year", None)
    inferred = _publication_status(record)
    archive = str(record.get("doi") or "").startswith("10.1038/npre.") or str(record.get("journal") or "").casefold().strip() == "nature precedings"
    posted = str(record.get("document_type") or record.get("type") or "").casefold() == "posted-content"
    preprint = bool(inferred == "preprint" or record.get("source") == "arxiv" or (not posted and not archive and (record.get("is_preprint") or record.get("publication_status") == "preprint")))
    record["publication_status"] = "preprint" if preprint else "unknown" if archive or posted else record.get("publication_status") or inferred
    record["is_preprint"] = preprint
    if record.get("arxiv_id") and not record["version"]:
        match = re.search(r"v\d+$", record["arxiv_id"])
        record["version"] = match.group(0) if match else ""
    # A DOI is a stable resolver entry, not proof of an official host or permission.
    if not record["official_landing_page"] and record.get("doi") and not preprint:
        record["official_landing_page"] = _safe_url(str(record.get("url") or f"https://doi.org/{record['doi']}"))
    record.setdefault("source_validation", "not_checked")
    record.setdefault("metadata_status", "not_checked")
    record.setdefault("verification_scope", [])
    record.setdefault("unchecked_fields", [])
    record.setdefault("unchecked_identifiers", [])
    record.setdefault("conflicts", [])
    record.setdefault("claim_support_status", "not_assessed")
    record.setdefault("selection_status", "not_recorded")
    record.setdefault("pdf_status", "not_requested")
    sources = list(record.get("sources") or [])
    if record.get("source") and record["source"] not in sources:
        sources.append(record["source"])
    record["sources"] = sources
    source_records = list(record.get("source_records") or [])
    if record.get("source"):
        source_records.append({"source": record["source"], "source_id": record.get("source_id", ""),
                               "source_url": _safe_url(str(record.get("source_url") or record.get("url") or "")),
                               "metadata": {field: record.get(field) for field in (*ID_FIELDS, "title", "authors", "year", "journal", "publisher", "version") if record.get(field) not in _EMPTY}})
    record["source_records"] = source_records
    record["record_id"] = stable_record_id(record)
    return record


class _CheckedAdapter:
    def __init__(self, source: str, adapter: object):
        self.source, self.adapter, self.outcome = source, adapter, None

    def search(self, query, rows=5, **kwargs):
        result = self.adapter.search(query, rows=rows, **kwargs)
        if not isinstance(result, Mapping) or not isinstance(result.get("results"), list):
            raise DataSourceError(self.source, "Malformed normalized search response")
        if any(not isinstance(r, Mapping) or not r.get("title") for r in result["results"]):
            raise DataSourceError(self.source, "Search response contains invalid records")
        outcome = dict(result)
        result = dict(result)
        result["results"] = [_record({**r, "source": self.source}) for r in result["results"]]
        self.outcome = outcome
        return result


def _available(sources, adapters, entity_type):
    ready, skipped, pool = [], [], {}
    for source in dict.fromkeys(sources):
        if source not in SOURCE_ENTITY_TYPES:
            skipped.append({"source": source, "reason": "adapter_not_implemented"})
        elif SOURCE_ENTITY_TYPES[source] != entity_type:
            skipped.append({"source": source, "reason": "incompatible_entity_type"})
        elif adapters is not None and source not in adapters:
            skipped.append({"source": source, "reason": "adapter_not_available"})
        elif adapters is None and source == "pubmed" and not get_config().pubmed_email:
            skipped.append({"source": source, "reason": "Set PUBMED_EMAIL to a real contact email before using PubMed"})
        else:
            pool[source] = adapters[source] if adapters is not None else build_adapters([source])[source]
            ready.append(source)
    return ready, skipped, pool


def search_papers(query, sources=None, rows=5, **kwargs) -> dict:
    """Return bounded per-source discovery, not an exhaustive database sweep.

    Supported options: entity_type, filters, ranking, adapters (test injection).
    Each selected source is executed once; duplicate source names are collapsed.
    """
    entity = kwargs.pop("entity_type", "publication")
    filters = kwargs.pop("filters", None)
    ranking = kwargs.pop("ranking", "relevance")
    adapters = kwargs.pop("adapters", None)
    if kwargs:
        raise TypeError(f"Unknown search options: {', '.join(kwargs)}")
    if entity not in {"publication", "trial"} or not str(query).strip():
        raise ValueError("A nonempty query and a supported entity_type are required")
    if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= 50:
        raise ValueError("rows must be an integer from 1 to 50 per source")
    if isinstance(sources, str):
        sources = [s.strip() for s in sources.split(",") if s.strip()]
    selected = list(DEFAULT_PUBLICATION_SOURCES if sources is None and entity == "publication" else ["clinicaltrials_gov"] if sources is None else sources)
    if not selected:
        raise ValueError("At least one source is required")
    ready, skipped, pool = _available(selected, adapters, entity)
    checked = {source: _CheckedAdapter(source, adapter) for source, adapter in pool.items()}
    result = asyncio.run(native.search_all(str(query), ready, rows, adapters=checked, entity_type=entity, filters=filters, ranking=ranking)) if ready else {
        "results": [], "sources_queried": [], "sources_succeeded": [], "errors": [], "search_run": {}, "source_meta": {},
    }
    result["records"] = [_record(r) for r in result["results"]]
    result["results"] = result["records"]
    errors = result.get("errors") or []
    for error in errors:
        error["error"] = _safe_text(error.get("error", "Source failed"))
    result["errors"] = errors
    result["sources_failed"] = list(dict.fromkeys(error["source"] for error in errors))
    result["sources_not_queried"] = skipped
    coverage = {}
    for source in ready:
        outcome = checked[source].outcome
        if outcome is None or source in result["sources_failed"]:
            coverage[source] = {"status": "unknown", "reason": "source_failed"}
            continue
        total, received = outcome.get("total"), len(outcome["results"])
        partial = bool((outcome.get("source_meta") or {}).get("partial"))
        status = "unknown" if total is None else "partial" if partial or total > received else "complete_within_scope"
        coverage[source] = {"status": status, "reported_total": total, "received": received,
                            "requested_rows": rows, "truncated": status == "partial",
                            "reason": "single_page_limit_or_parse_gap" if status == "partial" else ""}
    result["coverage"] = coverage
    result["result_count"] = len(result["records"])
    return result


def _expectation(expected):
    expected = dict(expected or {})
    ids = expected.pop("identifiers", {}) or {}
    for field, value in ids.items():
        if field in ID_FIELDS:
            expected.setdefault(field, value.get("normalized") or value.get("value") if isinstance(value, Mapping) else value)
    return {field: value for field, value in expected.items() if field in (*ID_FIELDS, "title", "authors", "first_author", "year", "journal", "publisher", "version", "publication_status") and value not in _EMPTY}


def _check(expected, actual, field, value):
    expected = _expectation(expected)
    # The requested ID must be checked even if the caller omitted it.
    if field in expected and normalize_identifier(field, expected[field]) != value:
        actual.setdefault("conflicts", []).append({"field": field, "expected": expected[field], "lookup": value, "reason": "input_identifier_conflict"})
    expected.setdefault(field, value)
    compare = copy.deepcopy(actual)
    if field == "arxiv_id" and not re.search(r"v\d+$", value):
        compare[field] = re.sub(r"v\d+$", "", str(compare.get(field) or ""))
    verification = verify_record(expected, compare)
    fields = verification["fields"]
    actual["verification_scope"] = list(fields)
    actual["field_checks"] = fields
    actual["unchecked_fields"] = [name for name, check in fields.items() if check["status"] in {"missing", "uncheckable"}]
    actual["unchecked_identifiers"] = [name for name in actual["unchecked_fields"] if name in ID_FIELDS]
    actual["verified_fields"] = [name for name, check in fields.items() if check["status"] == "match"]
    for name, check in fields.items():
        if check["status"] == "mismatch":
            actual["conflicts"].append({"field": name, **check})
    status = verification["status"]
    actual["metadata_status"] = "mismatch" if actual["conflicts"] else "partial" if status == "manual_needed" else "unresolved" if status == "not_found" else status
    actual["verification"] = {**verification, "status": actual["metadata_status"], "lookup_id": value, "lookup_id_type": field}
    return actual


_LOOKUP_SOURCES = {"doi": ["crossref"], "pmid": ["pubmed"], "pmcid": ["europe_pmc"], "arxiv_id": ["arxiv"],
                   "openalex_id": ["openalex"], "semantic_scholar_id": ["semantic_scholar"], "nct_id": ["clinicaltrials_gov"]}


def resolve_record(identifier, expected=None, **kwargs) -> dict:
    """Resolve a strong ID, or conservatively resolve a bounded citation search."""
    adapters = kwargs.pop("adapters", None)
    selected = kwargs.pop("sources", None)
    include_relations = kwargs.pop("include_relations", False)
    if kwargs:
        raise TypeError(f"Unknown resolve options: {', '.join(kwargs)}")
    parsed = _identifier(str(identifier))
    if parsed is None:
        if str(identifier).startswith(("https://", "http://")):
            result = _record({"official_landing_page": _safe_url(str(identifier)), "metadata_status": "unresolved"})
            result.update(identity_status="manual_needed", sources_queried=[], sources_succeeded=[],
                          sources_failed=[], sources_not_queried=[], errors=[])
            result["manual_needed"] = {"reason": "Article URL identity is not known; provide its DOI or verified citation metadata"}
            return result
        return _resolve_citation(str(identifier), expected, adapters=adapters)
    field, value = parsed
    entity = "trial" if field == "nct_id" else "publication"
    if isinstance(selected, str):
        selected = [s.strip() for s in selected.split(",") if s.strip()]
    ready, skipped, pool = _available(selected or _LOOKUP_SOURCES[field], adapters, entity)
    queried, succeeded, errors, resolved = [], [], [], []
    for source in ready:
        adapter = pool[source]
        method = "get_by_doi" if source == "crossref" and field == "doi" else "get_by_pmid" if source == "pubmed" and field == "pmid" else "get_by_id"
        if not hasattr(adapter, method) or (source == "crossref" and field != "doi") or (source == "pubmed" and field != "pmid") or (source == "europe_pmc" and field not in {"pmid", "pmcid"}) or (source == "arxiv" and field != "arxiv_id"):
            skipped.append({"source": source, "reason": "identifier_namespace_not_supported"})
            continue
        queried.append(source)
        lookup = f"{field.replace('_id', '').upper()}:{value}" if source == "semantic_scholar" and field != "semantic_scholar_id" else value
        try:
            raw = getattr(adapter, method)(lookup)
            if not isinstance(raw, Mapping) or not raw.get("title"):
                raise DataSourceError(source, "Lookup returned an invalid record")
            current = _record({**raw, "source": source})
            if current["entity_type"] != entity:
                raise DataSourceError(source, "Lookup returned the wrong entity type")
            resolved.append(_check(expected, current, field, value))
            succeeded.append(source)
        except Exception as exc:
            errors.append({"source": source, "error": _safe_text(exc), "kind": "rate_limited" if "429" in str(exc) else "source_error"})
    if resolved:
        actual = resolved[0]
        for other in resolved[1:]:
            differences = [name for name in (*ID_FIELDS, "publication_status", "version") if actual.get(name) not in _EMPTY and other.get(name) not in _EMPTY and actual[name] != other[name]]
            if differences or other["metadata_status"] == "mismatch":
                actual["conflicts"].append({"fields": differences, "source": other.get("source"), "reason": "conflicting_source_lookup", "incoming": other["identifiers"]})
                actual["metadata_status"] = "mismatch"
            actual["source_records"].extend(other["source_records"])
        # Optional relation queries are explicitly requested, never implicit LLM work.
        if include_relations and entity == "publication" and not actual["conflicts"]:
            from ._vendor.nature_academic_search.graph import build_citation_graph
            actual["citation_graph"] = build_citation_graph(actual, depth=1, rows=5, relation_sources=ready, adapters=pool)
    else:
        actual = _record({"entity_type": entity, field: value, "metadata_status": "unresolved"})
        actual["manual_needed"] = {"reason": "No matching source record was obtained", "identifier": value}
    actual.update(sources_queried=queried, sources_succeeded=succeeded,
                  sources_failed=list(dict.fromkeys(e["source"] for e in errors)), sources_not_queried=skipped, errors=errors)
    actual["lookup_id"] = value
    actual["lookup_id_type"] = field
    actual["identity_status"] = "resolved" if resolved and actual["metadata_status"] != "mismatch" else "manual_needed"
    return actual


def _text(value):
    return re.sub(r"[^\w]+", " ", str(value).casefold()).strip()


def _resolve_citation(citation, expected, adapters=None):
    if not citation.strip():
        raise ValueError("A nonempty identifier or citation is required")
    search = search_papers(citation, sources=["crossref"], rows=3, ranking="none", adapters=adapters)
    scored = []
    query = _text(citation)
    years = set(re.findall(r"\b(?:19|20)\d{2}\b", citation))
    explicit = _expectation(expected)
    wanted_title = _text(explicit.get("title") or citation)
    for record in search["records"]:
        title = _text(record["title"])
        exact = bool(title and title == wanted_title and (not years or str(record.get("year")) in years))
        contained = bool(len(title.split()) >= 5 and title in query)
        year_ok = not years or str(record.get("year")) in years
        score = 1.0 if exact else .96 if contained and year_ok else SequenceMatcher(None, wanted_title, title).ratio()
        scored.append((score, record, exact or (contained and year_ok)))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    candidates = [{"record_id": r["record_id"], "doi": r.get("doi"), "title": r["title"], "year": r.get("year"), "score": round(score, 4)} for score, r, _ in scored]
    unique = bool(scored and scored[0][2] and scored[0][1].get("doi") and (len(scored) == 1 or scored[0][0] - scored[1][0] >= .1))
    if unique:
        score, record, _ = scored[0]
        compare = {"title": record["title"], **explicit}
        if len(years) == 1:
            compare.setdefault("year", next(iter(years)))
        result = resolve_record(record["doi"], expected=compare, adapters=adapters)
        result["resolution_confidence"] = {"level": "high", "score": score, "basis": "unique_exact_or_contained_title_with_no_year_conflict"}
    else:
        result = _record({"title": citation, "metadata_status": "unresolved"})
        result.update({key: search[key] for key in ("sources_queried", "sources_succeeded", "sources_failed", "sources_not_queried", "errors")})
        result["identity_status"] = "manual_needed"
        result["resolution_confidence"] = {"level": "insufficient", "basis": "No unique exact or corroborated title match"}
        result["manual_needed"] = {"reason": "Supply a DOI or clarify the citation identity"}
    result["resolution_candidates"] = candidates
    return result


def verify_records(records: Sequence[Mapping], **kwargs) -> list[dict]:
    """Re-query each identity and compare supplied fields; do not infer claim support."""
    output = []
    for original in records:
        candidate = _record(original)
        expected = _expectation(candidate)
        if candidate["conflicts"]:
            candidate["metadata_status"] = "mismatch"
            candidate["identity_status"] = "manual_needed"
            candidate["manual_needed"] = {"reason": "Resolve the input's identifier or version conflicts first"}
            output.append(candidate)
            continue
        ids = candidate["identifiers"]
        identifier = next((f"{field.replace('_id', '').upper()}:{ids[field]}" if field in {"doi", "pmid", "arxiv_id"} else ids[field] for field in ID_FIELDS if ids.get(field)), candidate["title"])
        checked = resolve_record(identifier, expected=expected, **kwargs)
        checked["input_record_id"] = candidate["record_id"]
        checked["input_metadata"] = expected
        for field in ("input_refs", "claim_support_status", "selection_status", "pdf_status"):
            if field in original:
                checked[field] = copy.deepcopy(original[field])
        if checked["metadata_status"] == "partial":
            checked["manual_needed"] = {"reason": "Some supplied metadata or identifiers could not be independently verified"}
        output.append(checked)
    return output
