"""Read literature inputs without evaluating content or executing files."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)


def normalize_record(row: dict) -> dict:
    result = {str(key).strip().lower(): value for key, value in row.items()}
    identifiers = result.get("identifiers") or {}
    if isinstance(identifiers, dict):
        for name, value in identifiers.items():
            if isinstance(value, dict):
                value = value.get("normalized") or value.get("value") or value.get("original")
            if value and not result.get(name):
                result[name] = value
    if isinstance(result.get("authors"), str):
        result["authors"] = [item.strip() for item in result["authors"].split(";") if item.strip()]
    return result


def read_records(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("records", data.get("results", data.get("targets", [data])))
        if not isinstance(data, list):
            raise ValueError("JSON input must contain a record list.")
        return [normalize_record(item) if isinstance(item, dict) else {"input": str(item)} for item in data]
    if suffix == ".csv":
        return [normalize_record(row) for row in csv.DictReader(text.splitlines())]
    if suffix in {".ris", ".bib", ".bibtex"}:
        # DOI-first imports deliberately avoid pretending to implement full citation grammars.
        fields = (re.findall(r"(?im)^DO\s*-\s*(.+)$", text) if suffix == ".ris"
                  else re.findall(r'(?i)\bdoi\s*=\s*[{"]([^}"]+)', text))
        dois = list(dict.fromkeys(match.group(0).rstrip(".,;")
                                 for field in fields for match in DOI_RE.finditer(field.replace(r"\_", "_"))))
        if not dois:
            raise ValueError("RIS/BibTeX import currently requires DOI-bearing entries; use text citations otherwise.")
        return [{"doi": doi} for doi in dois]
    if suffix not in {".txt", ".md"}:
        raise ValueError("Supported input formats: JSON, CSV, TXT, Markdown, DOI-bearing RIS and BibTeX.")
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+)", "", line)
        records.append({"input": line})
    return records


def identifier_for(record: dict) -> str:
    for field in ("doi", "pmid", "pmcid", "arxiv", "openalex", "id", "input", "citation",
                  "official_landing_page", "url", "title"):
        value = record.get(field)
        if value:
            return str(value)
    return ""


def collect_inputs(args) -> list[dict]:
    records = []
    for field in ("identifiers", "urls", "citations"):
        records.extend({"input": value} for value in (getattr(args, field, None) or []))
    for filename in getattr(args, "inputs", None) or []:
        records.extend(read_records(Path(filename)))
    if not records:
        raise ValueError("Provide --doi, --id, --url, --citation or --input.")
    for index, record in enumerate(records, 1):
        record.setdefault("input_id", f"input-{index:04d}")
    return records
