"""Publisher policy and PDF validation adapted from official_pdf_cli.py.

The publisher registry/DOI routes derive from the local workflow snapshot.
No browser profile, binary or credentials are bundled. Unknown hosts fail closed.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

MIN_PDF_BYTES = 50 * 1024
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
PUBLISHER_HOSTS = {
    "AIP": {"pubs.aip.org", "aip.scitation.org", "watermark.silverchair.com", "watermark02.silverchair.com"},
    "APS": {"journals.aps.org", "link.aps.org"}, "ACS": {"pubs.acs.org"},
    "Wiley": {"onlinelibrary.wiley.com", "advanced.onlinelibrary.wiley.com"},
    "AAAS": {"science.org", "www.science.org", "sciencemag.org", "www.sciencemag.org"},
    "NatureSpringer": {"nature.com", "www.nature.com", "springer.com", "www.springer.com", "link.springer.com", "static-content.springer.com", "media.springernature.com"},
    "RSC": {"pubs.rsc.org"}, "IOP": {"iopscience.iop.org", "stacks.iop.org"},
    "Elsevier": {"sciencedirect.com", "www.sciencedirect.com", "linkinghub.elsevier.com", "elsevier.com", "www.elsevier.com", "ac.els-cdn.com"},
    "TaylorFrancis": {"tandfonline.com", "www.tandfonline.com"},
    "SAGE": {"journals.sagepub.com", "sagepub.com", "www.sagepub.com"},
    "IEEE": {"ieeexplore.ieee.org", "ieee.org", "www.ieee.org"},
    "OUP": {"academic.oup.com", "oup.com", "www.oup.com"},
    "CUP": {"cambridge.org", "www.cambridge.org"}, "PNAS": {"pnas.org", "www.pnas.org"},
    "MDPI": {"mdpi.com", "www.mdpi.com"}, "Frontiers": {"frontiersin.org", "www.frontiersin.org"},
    "PLOS": {"journals.plos.org", "dx.plos.org", "plos.org", "www.plos.org"},
}
DOI_PREFIX_FAMILIES = dict(zip(
    ("10.1063", "10.1103", "10.1021", "10.1002", "10.1126", "10.1038", "10.1007", "10.1039", "10.1088", "10.1016", "10.1080", "10.1177", "10.1109", "10.1093", "10.1017", "10.1073", "10.3390", "10.3389", "10.1371"),
    ("AIP", "APS", "ACS", "Wiley", "AAAS", "NatureSpringer", "NatureSpringer", "RSC", "IOP", "Elsevier", "TaylorFrancis", "SAGE", "IEEE", "OUP", "CUP", "PNAS", "MDPI", "Frontiers", "PLOS"),
))
DISALLOWED_RE = re.compile(r"arxiv|biorxiv|medrxiv|sci-hub|libgen|core\.ac\.uk|unpaywall|semanticscholar|researchgate|academia\.edu|/(?:repository|repositories|bitstream)(?:/|$)", re.I)
SUPPLEMENT_RE = re.compile(r"supplement|supporting.?information|supporting.?info|attachment|suppl|pb-assets", re.I)


def normalize_doi(value: object) -> str:
    text = unquote(str(value or "").strip())
    match = DOI_RE.search(text)
    if not match:
        return ""
    doi = match.group().rstrip(".,;:]}>'\"")
    while doi.endswith(")") and doi.count("(") < doi.count(")"):
        doi = doi[:-1]
    return doi.lower()


def family_from_url(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""
    return next((f for f, hosts in PUBLISHER_HOSTS.items() if host in hosts), "")


def trusted_url(url: str, family: str) -> bool:
    try:
        parts = urlsplit(url)
        return bool(parts.scheme == "https" and not parts.username and not parts.password
                    and parts.port in (None, 443) and parts.hostname in PUBLISHER_HOSTS.get(family, ())
                    and not DISALLOWED_RE.search(parts.path))
    except ValueError:
        return False


def resolver_url(url: str) -> bool:
    try:
        p = urlsplit(url)
        return p.scheme == "https" and p.hostname in ("doi.org", "dx.doi.org") and p.port in (None, 443) and not p.username and not p.password
    except ValueError:
        return False


def redact_url(value: str) -> str:
    try:
        p = urlsplit(value)
        if p.scheme not in ("https", "http") or not p.hostname:
            return "[redacted-location]"
        return urlunsplit((p.scheme, p.hostname, p.path, "", ""))
    except ValueError:
        return "[redacted-url]"


def redact_text(value: object) -> str:
    text = str(value)
    text = re.sub(r"https?://[^\s<>\"']+", lambda m: redact_url(m.group()), text)
    text = re.sub(r"(?i)(?:bearer\s+|(?:api[_-]?key|token|password|authorization|cookie|signature)\s*[=:]\s*)[^\s,;]+", "[redacted-secret]", text)
    text = re.sub(r"(?i)[a-z]:[\\/][^\s\"'<>]*|(?<!\w)/(?:home|Users|tmp|var|private|root|mnt|opt)/[^\s\"'<>]*", "[redacted-path]", text)
    return text


def derived_pdf_candidates(record: dict) -> list[str]:
    doi = normalize_doi(record.get("doi"))
    family = record.get("publisher_family") or DOI_PREFIX_FAMILIES.get(doi.split("/", 1)[0], "")
    if not doi:
        return []
    if family == "APS":
        suffix = doi.split("/", 1)[1]
        routes = {"physreva": ("pra", "PhysRevA"), "physrevb": ("prb", "PhysRevB"), "physrevc": ("prc", "PhysRevC"), "physrevd": ("prd", "PhysRevD"), "physreve": ("pre", "PhysRevE"), "physrevlett": ("prl", "PhysRevLett"), "physrevx": ("prx", "PhysRevX"), "revmodphys": ("rmp", "RevModPhys"), "prapplied": ("prapplied", "PhysRevApplied"), "prmaterials": ("prmaterials", "PhysRevMaterials"), "prresearch": ("prresearch", "PhysRevResearch"), "prfluids": ("prfluids", "PhysRevFluids"), "prquantum": ("prquantum", "PRXQuantum")}
        route = routes.get(suffix.split(".", 1)[0])
        if route and "." in suffix:
            return [f"https://journals.aps.org/{route[0]}/pdf/10.1103/{route[1]}.{suffix.split('.', 1)[1]}"]
    template = {"ACS": "https://pubs.acs.org/doi/pdf/{}", "Wiley": "https://onlinelibrary.wiley.com/doi/pdfdirect/{}", "AAAS": "https://www.science.org/doi/pdf/{}", "IOP": "https://iopscience.iop.org/article/{}/pdf", "PNAS": "https://www.pnas.org/doi/pdf/{}"}.get(family)
    if template:
        return [template.format(doi)]
    if family == "NatureSpringer" and doi.startswith("10.1038/"):
        return ["https://www.nature.com/articles/" + doi.split("/", 1)[1] + ".pdf"]
    if family == "PLOS":
        journal = doi.split("/", 1)[1].split(".")
        routes = {"pone": "plosone", "pgen": "plosgenetics", "pcbi": "ploscompbiol",
                  "pbio": "plosbiology", "pmed": "plosmedicine", "ppat": "plospathogens",
                  "pntd": "plosntds"}
        route = routes.get(journal[1]) if len(journal) > 1 and journal[0] == "journal" else None
        if route:
            return [f"https://journals.plos.org/{route}/article/file?id={doi}&type=printable"]
    return []


def _words(text: object) -> list[str]:
    return re.findall(r"\w+", str(text or "").lower(), re.UNICODE)


def identity_evidence(text: str, record: dict) -> dict:
    # First-page text only: a target DOI buried in a reference list is not evidence.
    words = _words(text)
    title = _words(re.sub(r"<[^>]+>", " ", str(record.get("title") or "")))
    title_words = [w for w in title if len(w) > 2]
    title_match = bool(title_words and sum(w in words for w in title_words) / len(title_words) >= 0.85)
    doi = normalize_doi(record.get("doi"))
    found = {normalize_doi(m.group()) for m in DOI_RE.finditer(re.sub(r"(?<=/)\s+", "", text))}
    doi_match = bool(doi and doi in found)
    authors = record.get("authors") or ""
    author = record.get("first_author") or ""
    if not author and isinstance(authors, list) and authors:
        a = authors[0]
        author = (a.get("family") or a.get("name") or "") if isinstance(a, dict) else str(a).split()[-1]
    elif not author and isinstance(authors, str):
        author = authors.split(";", 1)[0].split(",", 1)[0].split()[-1] if authors.strip() else ""
    author_words = _words(author)
    author_match = bool(author_words and all(w in words for w in author_words))
    # Supplying a title adds a consistency gate even if the DOI matches.
    ok = (doi_match and (not title or title_match)) or (title_match and author_match and not found)
    return {"doi_match": doi_match, "title_match": title_match, "author_match": author_match, "identity_match": bool(ok)}


def verify_pdf(path: Path, record: dict) -> dict:
    data = path.read_bytes()
    result = {"verification_ok": False, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "page_count": 0, "text_extractable": False}
    if not data.startswith(b"%PDF-") or len(data) < MIN_PDF_BYTES or not data.rstrip().endswith(b"%%EOF"):
        result["verification_note"] = "invalid_or_partial_pdf"
        return result
    try:
        from pypdf import PdfReader
    except ImportError:
        result["verification_note"] = "dependency_missing:pypdf"
        return result
    try:
        reader = PdfReader(path, strict=True)
        result["page_count"] = len(reader.pages)
        if not result["page_count"]:
            result["verification_note"] = "pdf_has_no_pages"
            return result
        # Access every page tree entry, but inspect identity only on page one.
        for page in reader.pages:
            _ = page.mediabox
        text = reader.pages[0].extract_text() or ""
        result["text_extractable"] = bool(text.strip())
        result.update(identity_evidence(text, record))
        result["verification_ok"] = bool(result["text_extractable"] and result["identity_match"])
        result["verification_note"] = "verified" if result["verification_ok"] else ("empty_text_pdf" if not text.strip() else "pdf_identity_mismatch")
    except Exception:
        result["verification_note"] = "unreadable_pdf"
    return result
