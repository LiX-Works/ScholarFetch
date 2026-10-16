# Request examples

The following requests can be given directly to an Agent. They illustrate task scope, not research results that have already been produced.

## Topic search

```text
Use $scholarfetch to find research on exciton transport in two-dimensional semiconductors from 2022 to 2026.
Start with 10 candidate papers, including preprints, and clearly distinguish preprints from published versions.
State which sources were actually searched, which requests failed, and which fields were verified.
```

For a Chinese topic, the Agent first prepares English keywords suitable for the databases, then selects available sources. The paper count is a target scale, not evidence that the databases have been searched exhaustively.

When using the CLI directly, you can set dates, author, and document types explicitly. For example:

```bash
literature-workflow search "Sharing Detailed Research Data" --sources crossref --rows 3 --date-from 2007-01-01 --date-to 2007-12-31 --author Piwowar --document-type journal-article --language zh --output runs/filtered-search
```

Dates use `YYYY-MM-DD`; `--document-type` can be repeated. The same filters apply to `search-download`. The command records requested filters; actual execution scope depends on source support. The presence of a parameter does not establish that filtering succeeded.

## Verify existing references

```text
Use $scholarfetch to check the reference list I paste.
Check DOIs, titles, first authors, and years, and preserve the original input.
Separate matching, conflicting, and unresolved items; do not invent missing fields.
```

A DOI alone can be checked to see whether it resolves to a record. To check whether the original citation is correct, also supply its expected title, author, or year for comparison.

## Download specific papers

```text
Use $scholarfetch to download PDFs for the DOIs or official publisher links I provide.
Keep only files that pass provenance and identity checks, using this project's official_papers output directory.
For unavailable items, retain the DOI, failure reason, and suggested next step.
```

A topic search is not required first. Download success depends on publisher pages, file readability, and current access rights. Access-restricted items remain in the pending records.

## Search and download

```text
Use $scholarfetch to find research from the past five years on room-temperature photodetection in two-dimensional materials.
Verify the first 5 candidates and try to download their official PDFs.
Complete these stages in one task and report each paper's verification status, file status, and gaps.
```

Preprints found during search can be retained as candidate records. Automated PDF downloads still follow the official publisher source rules.

## Export citation exchange files

```text
Use $scholarfetch to export this run's verified papers as RIS and BibTeX.
List omitted records and reasons, and retain source records for my review.
```

Exported files are for subsequent reference management. The Skill does not automatically import into Zotero or insert or refresh Word citation fields.

## Missing dependencies

```text
Use $scholarfetch to check the current environment first.
Tell me which dependency is missing, which stage is affected, and the minimum preparation needed; continue stages that can run now.
```

For example, when optional browser components are missing, search, verification, and direct HTTP download attempts can still run. Browser acquisition requires those components to be prepared first.
