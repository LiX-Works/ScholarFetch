"""Official-publisher-only downloads with isolated optional browser fallback."""
from __future__ import annotations

import hashlib
import re
import tempfile
import uuid
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin

from ._official_pdf import (DOI_PREFIX_FAMILIES, PUBLISHER_HOSTS, SUPPLEMENT_RE,
                           derived_pdf_candidates, family_from_url, normalize_doi,
                           redact_text, redact_url, resolver_url, trusted_url, verify_pdf)


class SourceRejected(ValueError):
    pass


class DownloadFailure(RuntimeError):
    pass


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta" and attrs.get("name", "").lower() == "citation_pdf_url":
            self.links.append(attrs.get("content", ""))
        elif tag == "link" and attrs.get("type", "").lower() == "application/pdf":
            self.links.append(attrs.get("href", ""))
        elif tag == "a":
            href = attrs.get("href", "")
            if re.search(r"\.pdf(?:[?#]|$)|/pdf(?:direct)?/|articlepdf|/pdf$", href, re.I):
                self.links.append(href)


def pdf_links(html: str, base: str, family: str) -> list[str]:
    parser = _Links()
    parser.feed(html)
    return list(dict.fromkeys(urljoin(base, s) for s in parser.links
                             if s and not SUPPLEMENT_RE.search(s)
                             and trusted_url(urljoin(base, s), family)))


class _ArticleMetadata(HTMLParser):
    """Parse publisher citation tags without executing page code."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        attributes = {k.lower(): v for k, v in attrs}
        name = (attributes.get("name") or attributes.get("property") or "").lower()
        value = (attributes.get("content") or "").strip()
        if name and value:
            self.values.setdefault(name, []).append(value)


def resolve_official_page(url: str, *, timeout: int = 25) -> dict:
    """Read registered publisher citation metadata; DOI identity needs a later lookup.

    Unknown/authenticated/non-HTTPS hosts fail before any request. No profile,
    cookies, browser, PDF download or arbitrary-web fallback is used here.
    """
    family = family_from_url(url)
    result = {"doi": "", "title": "", "authors": [], "year": "",
              "official_landing_page": redact_url(url), "pdf_url": "",
              "official_pdf_url_candidate": "", "publisher_family": family,
              "status": "manual_needed", "manual_needed": True,
              "metadata_verified": False, "provenance": [], "errors": []}
    if not family or not trusted_url(url, family):
        result["errors"] = ["supplied_landing_source_untrusted"]
        return result
    try:
        import requests
        # A new session has no user/browser cookies; it is closed after one page.
        with requests.Session() as session:
            # Keep configured network routing, but prevent requests' implicit .netrc auth.
            session.auth = lambda request: request
            class HtmlSession:
                def get(self, request_url, **options):
                    options.setdefault("headers", {})["Accept"] = "text/html, application/xhtml+xml"
                    response = session.get(request_url, **options)
                    content_type = response.headers.get("Content-Type", "").lower()
                    if response.status_code == 200 and content_type and "html" not in content_type:
                        response.close()
                        raise DownloadFailure("article_html_required")
                    return response

            page = fetch_http(HtmlSession(), url, family, timeout=max(1, min(int(timeout), 600)),
                              max_bytes=8 * 1024 * 1024)
        result["official_landing_page"] = redact_url(page["url"])
        result["provenance"] = [{"source_url": redact_url(page["url"]),
                                 "redirect_chain": page["chain"], "method": "publisher_html_citation_metadata",
                                 "metadata_verified": False}]
        if page["body"].startswith(b"%PDF-"):
            result["errors"] = ["article_html_required"]
            return result
        content_type = page["content_type"].lower()
        if content_type and "html" not in content_type:
            result["errors"] = ["article_html_required"]
            return result
        parser = _ArticleMetadata()
        parser.feed(page["body"].decode("utf-8", "replace"))
        meta = parser.values
        dois = set()
        for key in ("citation_doi", "dc.identifier", "dc.identifier.doi", "dc.identifier.uri", "prism.doi"):
            for value in meta.get(key, []):
                doi = normalize_doi(value)
                if doi:
                    dois.add(doi)
        if len(dois) > 1:
            result["errors"] = ["ambiguous_page_doi"]
            return result
        result["doi"] = next(iter(dois), "")
        result["title"] = redact_text(next(iter(meta.get("citation_title", meta.get("dc.title", []))), ""))
        result["authors"] = list(dict.fromkeys(redact_text(value) for value in meta.get("citation_author", meta.get("dc.creator", []))))
        dates = meta.get("citation_publication_date", meta.get("citation_date", meta.get("dc.date", [])))
        if dates:
            year = re.search(r"\b(?:18|19|20|21)\d{2}\b", dates[0])
            result["year"] = year.group() if year else ""
        links = pdf_links(page["body"].decode("utf-8", "replace"), page["url"], family)
        if links:
            # Only a discovery candidate; redirect/source/PDF checks are mandatory later.
            result["pdf_url"] = result["official_pdf_url_candidate"] = redact_url(links[0])
        if result["doi"]:
            result.update(status="resolved", manual_needed=False)
        else:
            result["errors"] = ["page_doi_missing_needs_identity_resolution"]
        return result
    except Exception as exc:
        result["errors"] = [str(exc) if isinstance(exc, (SourceRejected, DownloadFailure)) else f"page_resolution_error:{type(exc).__name__}"]
        return result


def fetch_http(session, url: str, family: str, *, timeout: int, max_bytes: int = 100 * 1024 * 1024) -> dict:
    """Validate every redirect BEFORE requesting its destination; never auto-follow."""
    chain = []
    current = url
    for _ in range(9):
        if not (trusted_url(current, family) or (not chain and resolver_url(current))):
            raise SourceRejected("untrusted_source_or_redirect")
        response = session.get(current, allow_redirects=False, timeout=timeout, stream=True,
                               headers={"User-Agent": "literature-search-download/0.1 (official publisher research workflow)"})
        try:
            actual = str(response.url or current)
            if actual != current and not trusted_url(actual, family):
                raise SourceRejected("untrusted_response_source")
            chain.append(redact_url(actual))
            status = response.status_code
            if status in (301, 302, 303, 307, 308):
                location = response.headers.get("Location")
                if not location:
                    raise DownloadFailure("redirect_without_location")
                candidate = urljoin(current, location)
                if not family:
                    family = family_from_url(candidate)
                if not trusted_url(candidate, family):
                    raise SourceRejected("untrusted_source_or_redirect")
                current = candidate
                continue
            if not trusted_url(actual, family):
                raise SourceRejected("resolver_is_not_pdf_source")
            if status != 200:
                raise DownloadFailure(f"http_{status}")
            if response.headers.get("Content-Range"):
                raise DownloadFailure("partial_http_response")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise DownloadFailure("response_too_large")
            length = response.headers.get("Content-Length")
            # requests decompresses encoded responses; compare only unencoded length.
            if length and not response.headers.get("Content-Encoding") and len(data) != int(length):
                raise DownloadFailure("incomplete_http_response")
            return {"body": bytes(data), "url": actual, "family": family, "chain": chain,
                    "content_type": response.headers.get("Content-Type", "")}
        finally:
            response.close()
    raise DownloadFailure("redirect_limit")


def _browser_attempt(entry: str, candidates: list[str], family: str, profile_root: Path | None,
                     headless: bool, wait_seconds: int) -> list[dict]:
    try:
        from cloakbrowser import launch_persistent_context
    except ImportError as exc:
        raise DownloadFailure("dependency_missing:cloakbrowser") from exc
    # Even an explicitly supplied root is a container, never an existing profile.
    root = Path(profile_root) if profile_root is not None else Path(tempfile.gettempdir()) / "literature-workflow-profiles"
    profile = root / ("isolated-" + uuid.uuid4().hex)
    profile.mkdir(parents=True, exist_ok=False)
    captured = []
    context = launch_persistent_context(str(profile), headless=headless, accept_downloads=True)
    try:
        def route_request(route):
            url = route.request.url
            if trusted_url(url, family):
                route.continue_()
            else:
                route.abort()

        context.route("**/*", route_request)
        page = context.new_page()

        def capture(response):
            if response.status != 200 or not trusted_url(response.url, family):
                return
            if "pdf" not in response.headers.get("content-type", "").lower():
                return
            if response.headers.get("content-range"):
                return
            request = response.request
            while request is not None:
                if not trusted_url(request.url, family):
                    return
                request = request.redirected_from
            try:
                body = response.body()
                if len(body) <= 100 * 1024 * 1024:
                    captured.append({"body": body, "url": response.url, "family": family,
                                     "chain": [redact_url(response.url)], "method": "isolated_browser_response"})
            except Exception:
                pass

        page.on("response", capture)
        if entry and trusted_url(entry, family):
            try:
                page.goto(entry, wait_until="domcontentloaded", timeout=wait_seconds * 1000)
                # Passive wait permits manual consent/challenge completion. No solver or bypass.
                page.wait_for_timeout(wait_seconds * 1000)
                candidates = pdf_links(page.content(), page.url, family) + candidates
            except Exception:
                pass
        for candidate in list(dict.fromkeys(candidates))[:4]:
            if captured:
                break
            if not trusted_url(candidate, family):
                continue
            try:
                page.goto(candidate, wait_until="domcontentloaded", timeout=wait_seconds * 1000)
            except Exception:
                pass
            page.wait_for_timeout(min(wait_seconds, 3) * 1000)
        return captured
    finally:
        context.close()


def _filename(record: dict) -> str:
    supplied = str(record.get("expected_output_filename") or "")
    if supplied:
        # Reject path syntax, including Windows drives, instead of silently rewriting it.
        if any(c in supplied for c in '/\\:') or supplied in (".", "..") or not supplied.lower().endswith(".pdf"):
            raise ValueError("unsafe_output_filename")
        name = re.sub(r"[^\w .()-]", "_", supplied).strip(" .")
        if not name or name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise ValueError("unsafe_output_filename")
        return name[:-4][:176] + ".pdf"
    title = re.sub(r"[^\w -]", "", redact_text(record.get("title") or "article"))[:80].strip() or "article"
    seed = normalize_doi(record.get("doi")) or str(record.get("record_id") or record.get("candidate_id") or title)
    return f"{title}_{hashlib.sha256(seed.encode()).hexdigest()[:12]}.pdf"


def download_records(records: list[dict], output_dir: Path, *, profile_root: Path | None = None,
                     headless: bool = False, wait_seconds: int = 60, **kwargs) -> dict:
    """Download normalized records. Reports contain no credentials or absolute paths.

    Optional kwargs: use_browser (default True), session (HTTP test/transport adapter).
    Final PDFs are in output_dir/papers; unaccepted files stay in a unique quarantine.
    Existing files are never accepted merely by filename and are never overwritten.
    """
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    papers = root / "papers"
    if papers.is_symlink():
        raise ValueError("unsafe_papers_directory")
    papers.mkdir(exist_ok=True)
    if papers.resolve().parent != root:
        raise ValueError("unsafe_papers_directory")
    runs = root / "download_runs"
    if runs.is_symlink():
        raise ValueError("unsafe_runs_directory")
    if runs.exists() and runs.resolve().parent != root:
        raise ValueError("unsafe_runs_directory")
    run = runs / uuid.uuid4().hex
    run.mkdir(parents=True, exist_ok=False)
    quarantine = run / "quarantine"
    quarantine.mkdir()
    timeout = max(1, min(int(wait_seconds), 600))
    session = kwargs.get("session")
    own_session = session is None
    if session is None:
        import requests
        session = requests.Session()
        # Explicit API/session auth only; do not silently read personal .netrc credentials.
        session.auth = lambda request: request
    result = {"targets": [], "verified_files": [], "manual_needed": [], "errors": [], "provenance": []}
    try:
        for index, original in enumerate(records, 1):
            record = dict(original)
            doi = normalize_doi(record.get("doi"))
            record["doi"] = doi
            landing = str(record.get("official_landing_page") or record.get("publisher_url") or record.get("url") or "")
            supplied = str(record.get("official_pdf_url_candidate") or record.get("pdf_url") or "")
            family = DOI_PREFIX_FAMILIES.get(doi.split("/", 1)[0], "") or family_from_url(landing) or family_from_url(supplied)
            record["publisher_family"] = family
            target = {"record_id": redact_text(record.get("record_id") or record.get("candidate_id") or f"record-{index}"),
                      "doi": doi, "title": redact_text(record.get("title") or ""), "publisher_family": family,
                      "pdf_status": "manual_needed", "status": "manual_needed", "errors": [], "provenance": []}
            attempts = []
            attempted_urls = set()
            accepted = False
            browser_eligible = False
            try:
                filename = _filename(record)
                final = papers / filename
                if final.exists() or final.is_symlink():
                    raise DownloadFailure("existing_file_unverified_no_overwrite")
                if not family and not doi:
                    raise SourceRejected("official_publisher_not_established")
                if supplied and not trusted_url(supplied, family):
                    raise SourceRejected("supplied_pdf_source_untrusted")
                if landing and not (trusted_url(landing, family) or resolver_url(landing)):
                    raise SourceRejected("supplied_landing_source_untrusted")
                entry = landing or ("https://doi.org/" + quote(doi, safe="/()") if doi else "")
                candidates = list(dict.fromkeys(([supplied] if supplied else []) + derived_pdf_candidates(record)))

                def accept(payload: dict) -> bool:
                    if not trusted_url(payload["url"], payload["family"]):
                        raise SourceRejected("untrusted_final_source")
                    candidate = quarantine / (uuid.uuid4().hex + ".pdf")
                    candidate.write_bytes(payload["body"])
                    verification = verify_pdf(candidate, record)
                    event = {"source_url": redact_url(payload["url"]), "redirect_chain": payload.get("chain", []),
                             "method": payload.get("method", "requests_http"), "verification": verification,
                             "source_validation": "verified_official_publisher_response"}
                    target["provenance"].append(event)
                    if not verification["verification_ok"]:
                        attempts.append(verification["verification_note"])
                        return False
                    created = False
                    try:
                        with final.open("xb") as handle:
                            created = True
                            handle.write(payload["body"])
                    except Exception:
                        if created:
                            final.unlink(missing_ok=True)
                        raise DownloadFailure("final_file_commit_failed")
                    candidate.unlink()
                    target.update(pdf_status="verified", status="verified", file=final.relative_to(root).as_posix(), verification=verification)
                    return True

                for url in candidates[:4]:
                    try:
                        attempted_urls.add(url)
                        payload = fetch_http(session, url, family, timeout=timeout)
                        if payload["body"].startswith(b"%PDF-"):
                            accepted = accept(payload)
                        else:
                            attempts.append("non_pdf_response")
                            browser_eligible = True
                        if accepted:
                            break
                    except SourceRejected:
                        raise
                    except DownloadFailure as exc:
                        attempts.append(str(exc))
                        browser_eligible = browser_eligible or str(exc) in ("http_403", "http_401", "http_429", "non_pdf_response")
                        if str(exc) in ("http_403", "http_401", "http_429"):
                            break  # No hard retry with alternate spellings/endpoints.
                if not accepted and entry and entry not in attempted_urls:
                    try:
                        attempted_urls.add(entry)
                        page = fetch_http(session, entry, family, timeout=timeout)
                        family = page["family"]
                        target["publisher_family"] = family
                        if page["body"].startswith(b"%PDF-"):
                            accepted = accept(page)
                        else:
                            found = pdf_links(page["body"].decode("utf-8", "replace"), page["url"], family)
                            candidates = list(dict.fromkeys(found + candidates))
                            browser_eligible = True
                            for url in found[:4]:
                                if url in attempted_urls:
                                    continue
                                try:
                                    attempted_urls.add(url)
                                    payload = fetch_http(session, url, family, timeout=timeout)
                                    if payload["body"].startswith(b"%PDF-"):
                                        accepted = accept(payload)
                                    else:
                                        attempts.append("non_pdf_response")
                                    if accepted:
                                        break
                                except DownloadFailure as exc:
                                    attempts.append(str(exc))
                                    if str(exc) in ("http_403", "http_401", "http_429"):
                                        break
                    except SourceRejected:
                        raise
                    except DownloadFailure as exc:
                        attempts.append(str(exc))
                        browser_eligible = True
                if not accepted and browser_eligible and kwargs.get("use_browser", kwargs.get("allow_browser", True)) and family:
                    for payload in _browser_attempt(entry, candidates, family, profile_root or root / "private_profiles", headless, timeout):
                        if accept(payload):
                            accepted = True
                            break
                if not accepted and not attempts:
                    attempts.append("official_pdf_not_found")
            except SourceRejected as exc:
                target.update(pdf_status="source_rejected", status="source_rejected")
                attempts.append(str(exc))
            except Exception as exc:
                # Do not echo exception strings: requests/browser errors may contain credentials.
                attempts.append(str(exc) if isinstance(exc, (DownloadFailure, ValueError)) else f"transport_error:{type(exc).__name__}")
            if not accepted:
                target["errors"] = list(dict.fromkeys(redact_text(x) for x in attempts))
                if any(x.startswith("dependency_missing:") for x in target["errors"]):
                    target["pdf_status"] = target["status"] = "dependency_missing"
                target["suggested_manual_action"] = "Open the official publisher article, obtain the publisher PDF, and verify its DOI/title and authors."
                result["manual_needed"].append(target.copy())
                result["errors"].extend({"record_id": target["record_id"], "code": code} for code in target["errors"])
            else:
                result["verified_files"].append({"record_id": target["record_id"], "file": target["file"], "sha256": target["verification"]["sha256"]})
            result["targets"].append(target)
            result["provenance"].extend({"record_id": target["record_id"], **p} for p in target["provenance"])
    finally:
        if own_session:
            session.close()
    return result
