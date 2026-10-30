"""Unified CLI for a bounded search, verification and official-download workflow."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import __version__
from .doctor import check_dependencies
from .export import export_candidates
from .inputs import collect_inputs, identifier_for, read_records
from .privacy import redact_text, sanitize


def _common(parser) -> None:
    parser.add_argument("--output", help="New run directory; existing result files are never overwritten")
    parser.add_argument("--language", choices=("en", "zh"), default="en")


def _input_arguments(parser) -> None:
    parser.add_argument("--id", "--doi", dest="identifiers", action="append")
    parser.add_argument("--url", dest="urls", action="append")
    parser.add_argument("--citation", dest="citations", action="append")
    parser.add_argument("--input", dest="inputs", action="append")
    parser.add_argument("--expected-title")
    parser.add_argument("--expected-year", type=int)


def _search_arguments(parser) -> None:
    parser.add_argument("query")
    parser.add_argument("--sources", default="crossref,europe_pmc", help="Comma-separated source names")
    parser.add_argument("--rows", type=int, default=3, help="Results per source, between 1 and 50")
    parser.add_argument("--date-from", help="Earliest publication date, YYYY-MM-DD")
    parser.add_argument("--date-to", help="Latest publication date, YYYY-MM-DD")
    parser.add_argument("--author", help="Author filter, according to source support")
    parser.add_argument("--document-type", action="append", help="Document type filter, e.g. journal-article")


def _download_arguments(parser) -> None:
    parser.add_argument("--profile-root", type=Path, help="Parent directory for new isolated browser profiles; existing sessions are not reused")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--wait", type=int, default=60)
    parser.add_argument("--no-browser", action="store_true", help="Use HTTP only; report browser-needed targets")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="literature-workflow", description="Search, verify and collect official publisher PDFs.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="Check dependencies and configuration without network or cookies")
    doctor.add_argument("--mode", choices=("search", "download", "all"), default="all")
    search = sub.add_parser("search", help="Retrieve publication candidates with source coverage")
    _common(search)
    _search_arguments(search)
    for name in ("verify", "download"):
        item = sub.add_parser(name, help="Resolve and verify papers" if name == "verify" else "Acquire and check official PDFs")
        _common(item)
        _input_arguments(item)
        if name == "download":
            _download_arguments(item)
    pipeline = sub.add_parser("search-download", help="Run search, verification and official acquisition in one task")
    _common(pipeline)
    _search_arguments(pipeline)
    _download_arguments(pipeline)
    export = sub.add_parser("export", help="Format verified publication candidates")
    _common(export)
    export.add_argument("--input", required=True)
    export.add_argument("--format", choices=("ris", "bibtex"), default="ris")
    return parser


def _new_output(value: str | None) -> Path:
    output = Path(value) if value else Path("outputs") / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory is not empty. Choose a new directory to preserve previous runs.")
    output.mkdir(parents=True, exist_ok=True)
    return output


def _write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(sanitize(value), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _resolve_inputs(records: list[dict], args) -> list[dict]:
    from .search import resolve_record
    result = []
    for original in records:
        expected = {name: original[name] for name in ("title", "year", "journal", "authors", "doi", "pmid") if original.get(name)}
        if getattr(args, "expected_title", None):
            expected["title"] = args.expected_title
        if getattr(args, "expected_year", None):
            expected["year"] = args.expected_year
        identifier = identifier_for(original)
        if not identifier:
            result.append({"metadata_status": "unresolved", "identity_status": "manual_needed",
                           "reason": "No resolvable identifier or citation text in this input.", "entity_type": "publication"})
            continue
        try:
            resolved = resolve_record(identifier, expected=expected or None)
            if identifier.startswith(("https://", "http://")) and resolved.get("identity_status") == "manual_needed":
                from .download import resolve_official_page
                page = resolve_official_page(identifier)
                if page.get("status") == "resolved" and page.get("doi"):
                    page_expected = {name: page[name] for name in ("title", "authors", "year") if page.get(name)}
                    page_expected.update(expected)
                    resolved = resolve_record(page["doi"], expected=page_expected or None)
                    resolved["official_landing_page"] = page["official_landing_page"]
                    if page.get("official_pdf_url_candidate"):
                        resolved["official_pdf_url_candidate"] = page["official_pdf_url_candidate"]
                    resolved["page_identity_evidence"] = page
            resolved["input_refs"] = [original.get("input_id") or original.get("record_id") or identifier]
            resolved["expected_fields"] = expected
            result.append(resolved)
        except Exception as exc:
            result.append({"input_refs": [identifier], "metadata_status": "unresolved",
                           "identity_status": "manual_needed", "reason": redact_text(str(exc)), "entity_type": "publication"})
    return result


def _report(run: dict, records: list[dict], language: str) -> str:
    zh = language == "zh"
    title = "文献工作流结果" if zh else "Literature workflow results"
    count = sum(record.get("metadata_status") == "verified" for record in records)
    lines = ["# " + title, "", ("任务" if zh else "Task") + ": " + run["intent"],
             ("记录数" if zh else "Records") + ": " + str(len(records)),
             ("元数据核验通过" if zh else "Metadata verified") + ": " + str(count), ""]
    if run.get("download"):
        download = run["download"]
        lines += [("已验收 PDF" if zh else "Verified PDFs") + ": " + str(len(download.get("verified_files") or [])),
                  ("人工待处理" if zh else "Manual action needed") + ": " + str(len(download.get("manual_needed") or [])), ""]
    if run.get("export"):
        export = run["export"]
        lines += [("已导出候选" if zh else "Candidates exported") + ": " + str(export["exported_count"]),
                  ("未导出" if zh else "Omitted") + ": " + str(len(export["omitted"])), ""]
        for item in export["omitted"]:
            ref = ", ".join(item.get("input_refs") or [item.get("record_id") or item.get("doi") or "Input"])
            lines.append("- " + ref + ": " + str(item["reason"]))
        lines.append("")
    lines += ["| " + ("输入" if zh else "Input") + " | " + ("论文" if zh else "Paper") + " | " + ("元数据状态" if zh else "Metadata status") +
              " | " + ("核验字段" if zh else "Verification scope") + " |", "|---|---|---|---|"]
    for record in records:
        label = str(record.get("title") or record.get("doi") or record.get("input_refs") or "Unresolved")
        label = redact_text(label).replace("|", "\\|").replace("\n", " ")
        ref = ", ".join(record.get("input_refs") or [record.get("record_id") or "-"]).replace("|", "\\|")
        scope = ", ".join(record.get("verification_scope") or []) or "-"
        lines.append("| " + ref + " | " + label + " | " + str(record.get("metadata_status", "not_checked")) + " | " + scope + " |")
    for record in records:
        checks = {name: check for name, check in (record.get("field_checks") or {}).items()
                  if isinstance(check, dict) and check.get("status") in {"mismatch", "missing", "uncheckable"}}
        if checks:
            ref = ", ".join(record.get("input_refs") or [record.get("record_id") or "Input"])
            lines += ["", ("核验差异" if zh else "Verification differences") + " (" + ref + "):",
                      json.dumps(sanitize(checks), ensure_ascii=False, indent=2)]
    if run.get("search"):
        lines += ["", ("来源与覆盖" if zh else "Sources and coverage") + ":",
                  json.dumps(sanitize({key: run["search"].get(key) for key in
                                      ("sources_queried", "sources_succeeded", "sources_failed", "sources_not_queried", "errors", "coverage")}),
                             ensure_ascii=False, indent=2)]
    if run.get("download"):
        for target in run["download"].get("targets") or []:
            if target.get("pdf_status") != "verified" and target.get("status") != "verified":
                reason = target.get("reason") or target.get("error") or target.get("errors") or target.get("message") or target.get("pdf_status") or target.get("status")
                lines += ["", "- " + redact_text(str(target.get("doi") or target.get("title") or target.get("record_id") or "Target")) +
                          ": " + redact_text(str(reason))]
    lines += ["", ("书目核验与 PDF 验收不代表论断支持或人工选引。" if zh else
                  "Metadata verification and PDF checks do not establish claim support or manuscript citation selection."), ""]
    return "\n".join(lines)


def execute(args) -> tuple[dict, int]:
    if args.command == "doctor":
        report = check_dependencies(args.mode)
        return report, 0 if report["ok"] else 2
    mode = "download" if args.command in {"download", "search-download"} else "search"
    if args.command != "export":
        dependencies = check_dependencies(mode)
        if not dependencies["ok"]:
            return {"status": "dependency_missing", "dependencies": dependencies, "message": "Prepare the listed dependencies before this stage."}, 2
    output = _new_output(args.output)
    run = {"schema_version": "1.0", "implementation_version": __version__,
           "run_id": uuid4().hex, "started_at": datetime.now(timezone.utc).isoformat(), "intent": args.command,
           "selection_status": "not_recorded", "claim_support_status": "not_assessed", "artifacts": []}
    records, exit_code = [], 0
    if args.command in {"search", "search-download"}:
        from .search import search_papers, verify_records
        filters = {key: value for key, value in {
            "date_from": args.date_from, "date_to": args.date_to,
            "author": args.author, "document_type": args.document_type,
        }.items() if value}
        response = search_papers(args.query, sources=[item.strip() for item in args.sources.split(",") if item.strip()],
                                 rows=args.rows, filters=filters or None)
        records = response.get("records") or response.get("results") or []
        run["search"] = {key: value for key, value in response.items() if key not in {"records", "results"}}
        run["requested_filters"] = filters
        if not response.get("sources_succeeded"):
            exit_code = 1
        if args.command == "search-download":
            records = verify_records(records)
    elif args.command in {"verify", "download"}:
        records = _resolve_inputs(collect_inputs(args), args)
        if not any(record.get("metadata_status") in {"verified", "partial"} for record in records):
            exit_code = 1
    elif args.command == "export":
        records = read_records(Path(args.input))
        text, export_result = export_candidates(records, args.format)
        name = "references.ris" if args.format == "ris" else "references.bib"
        with (output / name).open("x", encoding="utf-8") as handle:
            handle.write(text)
        run["export"] = export_result
        run["artifacts"].append(name)
        if not export_result["exported_count"]:
            exit_code = 1
    if args.command in {"download", "search-download"}:
        from .download import download_records
        download = download_records(records, output, profile_root=args.profile_root, headless=args.headless,
                                    wait_seconds=args.wait, use_browser=not args.no_browser)
        run["download"] = download
        _write_json(output / "download_manifest.json", download)
        run["artifacts"].append("download_manifest.json")
        if not download.get("verified_files"):
            exit_code = 1
    run["completed_at"] = datetime.now(timezone.utc).isoformat()
    run["record_count"] = len(records)
    run["metadata_verified_count"] = sum(record.get("metadata_status") == "verified" for record in records)
    run["artifacts"] += ["run.json", "records.json", "report.md"]
    _write_json(output / "records.json", records)
    _write_json(output / "run.json", run)
    with (output / "report.md").open("x", encoding="utf-8") as handle:
        handle.write(_report(run, records, args.language))
    return {"status": "completed" if exit_code == 0 else "completed_with_unresolved_results",
            "output": str(output), "records": len(records), "metadata_verified": run["metadata_verified_count"],
            "verified_pdfs": len((run.get("download") or {}).get("verified_files") or []),
            "artifacts": run["artifacts"]}, exit_code


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result, code = execute(args)
    except (ValueError, FileNotFoundError, OSError) as exc:
        result, code = {"status": "failed", "error": redact_text(str(exc))}, 2
    except Exception as exc:
        result, code = {"status": "failed", "error_type": type(exc).__name__, "error": redact_text(str(exc))}, 1
    print(json.dumps(sanitize(result), ensure_ascii=False, indent=2))
    return code
