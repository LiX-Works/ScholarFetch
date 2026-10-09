# ScholarFetch

**Academic Literature Search & PDF Download**

**English** | [简体中文](README.zh-CN.md)

ScholarFetch combines paper discovery, bibliographic verification, and official publisher PDF acquisition in one task, with traceable results and failure records. It provides an AI assistant with a focused workflow and supporting commands.

For researchers, students, and anyone organizing academic literature. Provide a topic, DOI (paper identifier), title, official publisher link, or paper list; receive candidate papers, verification results, checked PDFs, and items that need manual attention.

## What it does

| Your task | Workflow | Main output |
|---|---|---|
| Find papers on a topic | Select sources, search, and deduplicate | Candidates and source records |
| Check existing references | Resolve identifiers and compare titles, authors, years, and other fields | Matches, conflicts, and missing fields |
| Download specific papers | Locate official pages and PDFs; check provenance and identity | Checked official PDFs and unresolved items |
| Search and download | Run discovery, verification, and acquisition together | Linked paper records and files |
| Export references | Export eligible verified records as RIS or BibTeX | Files for subsequent reference management |

Search results are candidates. Matching metadata, confirming PDF identity, and deciding whether a paper supports a claim are separate judgments. Citation selection remains with the user; ScholarFetch does not automatically import into Zotero or edit Word citations.

## Dependencies

| Dependency | Purpose | Required? | What to prepare | If missing |
|---|---|---|---|---|
| Python ≥ 3.11 | Run the commands | Yes | Install Python; a separate virtual environment is recommended | Scripts cannot run |
| requests ≥ 2.31, < 3 | Database requests and HTTP downloads | Base installation | Run `python -m pip install .` from the repository root | Search, verification, and direct downloads are unavailable |
| pypdf ≥ 6, < 7 | Read PDFs and check pages and identity | Base installation | Installed with the base dependencies | PDFs cannot pass validation |
| cloakbrowser ≥ 0.4.10, < 0.5 and its browser binary | Access official pages requiring a browser | Optional | Install `.[browser]`; prepare the binary using the official instructions | Browser acquisition is unavailable; other stages can continue |
| Source configuration and network access | Reach selected databases and publishers | Depends on source | Set `PUBMED_EMAIL` for PubMed; follow diagnostic guidance for other email or API key settings | Affected sources fail or are limited; other results are retained |
| Publisher access rights | Obtain restricted papers | Depends on paper | Use your existing authorized access; log in manually in the current visible browser if needed | The paper remains in the manual-action list |

No MCP server, external language model, or paid relay is required. Accounts, cookies, browser profiles, and browser binaries are not bundled. See [setup and dependencies](references/setup.md).

## Getting started

Download the repository, then install and check dependencies from its root:

```bash
python -m pip install .
literature-workflow doctor --mode all
```

For optional browser acquisition, also run `python -m pip install ".[browser]"`.

Place the repository in your assistant's skill directory as `scholarfetch`. For Codex, the usual location is `~/.codex/skills/scholarfetch/`; see [setup.md](references/setup.md). Then ask:

```text
Use $scholarfetch to find recent research on excitons in two-dimensional materials.
Report the sources and search scope, verify the candidates, and try to download their official PDFs.
```

You can specify dates, result counts, preprint preferences, and the output directory. File inputs support JSON, CSV, and text. RIS/BibTeX input currently extracts DOI-bearing records only; files without DOIs are rejected. Supply ordinary titles or citations as text for conservative identity resolution. See [request examples](examples/requests.md). When a dependency is missing, the assistant should name it, explain the affected stage and minimum preparation, and continue stages that remain available.

You can also use the CLI directly:

```bash
literature-workflow search "exciton transport two dimensional materials" --sources crossref,europe_pmc --rows 3 --language en --output runs/search
literature-workflow verify --doi "10.1371/journal.pone.0000308" --language en --output runs/verify
literature-workflow download --input papers.txt --no-browser --language en --output runs/download
literature-workflow search-download "exciton transport two dimensional materials" --rows 3 --no-browser --language en --output runs/search-download
literature-workflow export --input runs/search-download/records.json --format ris --language en --output runs/export
```

The example DOI identifies *Sharing Detailed Research Data Is Associated with Increased Citation Rate* (2007), whose metadata has been checked. Future availability is not guaranteed. Use a new or empty output directory for each run; existing results are not overwritten. A DOI lookup alone does not verify an original reference: use `--expected-title` and `--expected-year` to compare supplied fields. From the source checkout, `python scripts/literature.py` accepts the same commands. See `--help` for full options.

## Sources, outputs, and limits

Implemented paper sources are Crossref, PubMed, arXiv, OpenAlex, Europe PMC, and Semantic Scholar. The default is Crossref and Europe PMC. The assistant selects sources according to the task and available configuration, and reports actual queries, failures, and coverage limits.

Completed workflow runs produce `run.json`, `records.json`, and `report.md`. Downloads also produce `download_manifest.json`; accepted PDFs go into `papers/`. Unavailable or uncertain items remain in the JSON and report. Exports produce `references.ris` or `references.bib`. See the [workflow contract](references/workflow-contract.md) for fields and statuses.

Searches are bounded and do not guarantee exhaustive coverage. Automated acquisition accepts verifiable official publisher sources only, with no fallback to repository or third-party copies. Page changes, access restrictions, or insufficient identity evidence may require manual action. Each browser session uses a new isolated profile; `--profile-root` specifies its parent directory and does not reuse existing logins or cookies. `doctor` checks local dependencies and some configuration, not connectivity, browser binary availability, or publisher access. Credentials and profiles stay local and must not be published with run outputs.

## Verified scope

65 offline tests passed, covering source errors, identifier and version conflicts, PDF identity checks, overwrite protection, and sensitive-information handling. Package installation and the command entry point were also checked in an isolated environment.

Live checks used Python 3.12, requests 2.34.2, and pypdf 6.20.0: Crossref and Europe PMC topic searches returned 2 records per source (4 total); the example PLOS DOI passed independent metadata verification and official HTTP PDF page and identity checks. A single-candidate search → verification → download run produced 1 accepted PDF, and RIS export produced 1 record.

Negative checks excluded title or year conflicts from export, removed signed URL parameters and email information from RIS/BibTeX, and retained input links and omission reasons. Browser fallback has not had a live regression test. PubMed, arXiv, OpenAlex, and Semantic Scholar have not had live regression tests for this version. These checks do not establish universal source or publisher support.

## Attribution and license

ScholarFetch integrates discovery and verification code from [nature-academic-search](https://github.com/wp-a/nature-academic-search), source-operation knowledge from `paper-lookup` in [K-Dense Scientific Agent Skills](https://github.com/K-Dense-AI/scientific-agent-skills), and an official PDF acquisition workflow. This project adds a unified command interface, stage handoffs, dependency diagnostics, and traceable outputs. Upstream knowledge coverage does not imply that every upstream database is implemented.

New project code is released under [MIT](LICENSE). Upstream code and runtime dependencies retain their own licenses. See [third-party notices](THIRD_PARTY_NOTICES.md) for contributions and preserved license texts.
