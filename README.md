# ScholarFetch

**English** | [简体中文](README.zh-CN.md)

ScholarFetch is a Skill that lets an AI agent search the scholarly literature broadly, verify what it finds, and download PDFs straight from official publishers. Give it a topic, a reference list, or a DOI; it returns checked papers, traceable records, and a short list of anything that still needs you.

- **Search broadly.** Queries Crossref, PubMed, OpenAlex, Europe PMC, Semantic Scholar, and arXiv, then merges duplicates into one candidate list with source records.
- **Verify before trusting.** Compares titles, authors, years, and DOIs against your input, and flags every conflict or missing field.
- **Download automatically.** Fetches PDFs only from official publishers, uses a dedicated browser for pages a plain download cannot reach, and checks each PDF's identity before accepting it.

<img src="assets/overview.png" alt="Start from a topic, a reference list, or a DOI or link. ScholarFetch searches six scholarly databases and deduplicates the results, verifies metadata field by field, and downloads official publisher PDFs through a dedicated browser, checking each PDF's identity. Outputs are candidates with sources, a match report, RIS or BibTeX export, checked PDFs, and items that need attention." width="1600">

## How it works

Start from whichever step you need: a topic runs the full chain, an existing reference list starts at verification, and a DOI or publisher link goes straight to download. Verified records can be exported as RIS or BibTeX.

Search results are candidates. Matching metadata, confirming a PDF's identity, and deciding whether a paper supports a claim are separate judgments, and citation choices stay with you. ScholarFetch does not import into Zotero or edit Word citations; [Zotero-Word-AutoCite](https://github.com/LiX-Works/Zotero-Word-AutoCite) covers that step.

## Getting started

Install from the repository root and check the environment:

```bash
python -m pip install .
literature-workflow doctor --mode all
```

- **Python 3.11 or later.** The base install adds requests and pypdf for search, verification, direct downloads, and PDF checks.
- **Browser route (optional).** Run `python -m pip install ".[browser]"` and prepare the cloakbrowser binary as its documentation describes. Without it, the other stages still run.
- **Source settings.** Some sources need configuration, such as `PUBMED_EMAIL` for PubMed; `doctor` reports what is missing.
- **Publisher access.** Restricted papers use your own existing access.

No MCP server, external language model, or paid relay is required. Accounts, cookies, browser profiles, and browser binaries are not bundled. See [setup and dependencies](references/setup.md).

Place the repository in your agent's skill directory as `scholarfetch` (for Codex, usually `~/.codex/skills/scholarfetch/`), then ask:

```text
Use $scholarfetch to find recent research on excitons in two-dimensional materials.
Report the sources and search scope, verify the candidates, and download their official PDFs.
```

You can set dates, result counts, preprint preferences, and the output directory. Inputs can be text, JSON, CSV, or DOI-bearing RIS/BibTeX; see [request examples](examples/requests.md). The same stages are available from the command line:

```bash
literature-workflow search "exciton transport two dimensional materials" --sources crossref,europe_pmc --rows 3 --language en --output runs/search
literature-workflow verify --doi "10.1371/journal.pone.0000308" --language en --output runs/verify
literature-workflow download --input papers.txt --no-browser --language en --output runs/download
literature-workflow search-download "exciton transport two dimensional materials" --rows 3 --no-browser --language en --output runs/search-download
literature-workflow export --input runs/search-download/records.json --format ris --language en --output runs/export
```

Use a new or empty output directory for each run; existing results are never overwritten. To check an original reference rather than only resolve a DOI, add `--expected-title` and `--expected-year`. See `--help` for all options.

## Outputs and limits

Each run writes `run.json`, `records.json`, and `report.md`. Downloads add `download_manifest.json` and put accepted PDFs in `papers/`; anything unavailable or uncertain stays in the records and report with a reason. Exports write `references.ris` or `references.bib`. Fields and statuses are defined in the [workflow contract](references/workflow-contract.md).

Searches are bounded and do not promise exhaustive coverage. Automated acquisition accepts verifiable official publisher sources only, with no fallback to repository or third-party copies. Each browser session uses a fresh isolated profile, and credentials stay local.

## Verified scope

65 offline tests pass, covering source errors, identifier and version conflicts, PDF identity checks, overwrite protection, and sensitive-information handling. Live checks with Crossref and Europe PMC completed a search → verify → download → RIS export run that produced an accepted official PDF. Conflicting records were kept out of exports, and signed URL parameters and email addresses were removed from RIS/BibTeX.

The browser route and the PubMed, arXiv, OpenAlex, and Semantic Scholar sources have not yet had live regression runs for this version. These checks do not establish support for every source or publisher.

## Attribution and license

ScholarFetch integrates discovery and verification code from [nature-academic-search](https://github.com/wp-a/nature-academic-search), source-operation knowledge from `paper-lookup` in [K-Dense Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills), and an official PDF acquisition workflow. This project adds a unified command interface, stage handoffs, dependency diagnostics, and traceable outputs. Upstream knowledge coverage does not imply that every upstream database is implemented.

New project code is released under [MIT](LICENSE). Upstream code and runtime dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md) for contributions and preserved license texts.
