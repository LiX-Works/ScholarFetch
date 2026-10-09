"""Format verified publication candidates, without selecting manuscript citations."""

from __future__ import annotations

import re
from .privacy import sanitize


def _text(value) -> str:
    return " ".join(str(value or "").split())


def _authors(record: dict) -> list[str]:
    result = []
    for author in record.get("authors") or []:
        if isinstance(author, dict):
            result.append(_text(author.get("name") or ", ".join(
                part for part in (author.get("family"), author.get("given")) if part)))
        else:
            result.append(_text(author))
    return [item for item in result if item]


def _bib(value) -> str:
    text = _text(value)
    for character, escaped in (("\\", r"\textbackslash{}"), ("{", r"\{"), ("}", r"\}"),
                               ("%", r"\%"), ("&", r"\&"), ("#", r"\#"), ("_", r"\_")):
        text = text.replace(character, escaped)
    return text


def export_candidates(records: list[dict], format: str) -> tuple[str, dict]:
    selected, omitted = [], []
    for record in sanitize(records):
        reason = None
        if record.get("entity_type", "publication") != "publication":
            reason = "not_a_publication"
        elif record.get("metadata_status") != "verified":
            reason = "metadata_not_verified"
        elif record.get("conflicts"):
            reason = "unresolved_conflict"
        elif not record.get("title"):
            reason = "title_missing"
        if reason:
            omitted.append({"record_id": record.get("record_id"), "input_refs": record.get("input_refs"),
                            "expected_fields": record.get("expected_fields"), "doi": record.get("doi"),
                            "metadata_status": record.get("metadata_status"), "reason": reason,
                            "field_checks": record.get("field_checks")})
            continue
        cleaned = dict(record)
        unchecked = record.get("unchecked_identifiers") or []
        if isinstance(unchecked, dict):
            unchecked = list(unchecked)
        for item in unchecked:
            key = item.get("field") or item.get("type") if isinstance(item, dict) else str(item)
            cleaned.pop(key, None)
        selected.append(cleaned)
    blocks = []
    for index, record in enumerate(selected, 1):
        authors = _authors(record)
        if format == "ris":
            lines = ["TY  - JOUR", "TI  - " + _text(record["title"])]
            lines += ["AU  - " + author for author in authors]
            for key, tag in (("year", "PY"), ("journal", "JO"), ("doi", "DO")):
                if record.get(key):
                    lines.append(tag + "  - " + _text(record[key]))
            lines.append("ER  - ")
            blocks.append("\n".join(lines))
        elif format == "bibtex":
            key = re.sub(r"[^A-Za-z0-9]", "", record.get("doi") or f"paper{index}") or f"paper{index}"
            fields = {"title": record["title"], "author": " and ".join(authors),
                      "year": record.get("year"), "journal": record.get("journal"), "doi": record.get("doi")}
            # DOI is an identifier, not prose: TeX escaping would change it on re-import.
            body = ",\n".join("  " + name + " = {" + (_text(value) if name == "doi" else _bib(value)) + "}"
                              for name, value in fields.items() if value)
            blocks.append("@article{" + key + ",\n" + body + "\n}")
        else:
            raise ValueError("Export format must be ris or bibtex.")
    return "\n\n".join(blocks) + ("\n" if blocks else ""), {
        "format": format, "exported_count": len(selected),
        "exported_record_ids": [record.get("record_id") for record in selected], "omitted": omitted,
        "selection_status": "not_recorded",
    }
